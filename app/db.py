from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from app.utils import utc_now_iso


@dataclass(slots=True)
class UserRecord:
    id: int
    tg_user_id: int
    chat_id: int
    username: str | None
    first_name: str | None


@dataclass(slots=True)
class UserSettingsRecord:
    user_id: int
    category_slugs: str
    enabled: bool
    initialized: bool


@dataclass(slots=True)
class KeywordRecord:
    id: int
    user_id: int
    keyword: str
    normalized_keyword: str
    required_keywords: str
    hit_count: int
    last_hit_at: str | None


@dataclass(slots=True)
class BlockKeywordRecord:
    id: int
    user_id: int
    keyword: str
    normalized_keyword: str
    hit_count: int
    last_hit_at: str | None


@dataclass(slots=True)
class DeliveryRecord:
    id: int
    user_id: int
    item_key: str
    title: str
    link: str
    category_slug: str | None
    matched_keywords: str
    delivered_at: str


@dataclass(slots=True)
class PollingUserRecord:
    user: UserRecord
    settings: UserSettingsRecord
    keywords: list[KeywordRecord]
    block_keywords: list[BlockKeywordRecord]


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @asynccontextmanager
    async def _connect(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("PRAGMA busy_timeout = 5000;")
            yield db

    async def init(self) -> None:
        async with self._connect() as db:
            await db.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_user_id INTEGER NOT NULL UNIQUE,
                    chat_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    category_slugs TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    initialized INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    keyword TEXT NOT NULL,
                    normalized_keyword TEXT NOT NULL,
                    required_keywords TEXT NOT NULL DEFAULT '',
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    last_hit_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, normalized_keyword),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS block_keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    keyword TEXT NOT NULL,
                    normalized_keyword TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    last_hit_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, normalized_keyword),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS delivery_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    item_key TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    link TEXT NOT NULL DEFAULT '',
                    category_slug TEXT,
                    matched_keywords TEXT NOT NULL DEFAULT '',
                    delivery_status TEXT NOT NULL DEFAULT 'sent',
                    delivered_at TEXT NOT NULL,
                    UNIQUE(user_id, item_key),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_keywords_user_id ON keywords(user_id);
                CREATE INDEX IF NOT EXISTS idx_block_keywords_user_id ON block_keywords(user_id);
                CREATE INDEX IF NOT EXISTS idx_delivery_history_user_id ON delivery_history(user_id);
                """
            )
            await db.commit()

    async def upsert_user(
        self,
        tg_user_id: int,
        chat_id: int,
        username: str | None,
        first_name: str | None,
    ) -> UserRecord:
        now = utc_now_iso()
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO users (tg_user_id, chat_id, username, first_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tg_user_id) DO UPDATE SET
                    chat_id = excluded.chat_id,
                    username = excluded.username,
                    first_name = excluded.first_name,
                    updated_at = excluded.updated_at
                """,
                (tg_user_id, chat_id, username, first_name, now, now),
            )
            await db.commit()
            cursor = await db.execute(
                """
                SELECT id, tg_user_id, chat_id, username, first_name
                FROM users
                WHERE tg_user_id = ?
                """,
                (tg_user_id,),
            )
            row = await cursor.fetchone()
        return UserRecord(*row)

    async def ensure_user_profile(
        self,
        tg_user_id: int,
        chat_id: int,
        username: str | None,
        first_name: str | None,
    ) -> UserRecord:
        user = await self.upsert_user(tg_user_id, chat_id, username, first_name)
        await self.ensure_user_settings(user.id)
        return user

    async def ensure_user_settings(self, user_id: int) -> None:
        now = utc_now_iso()
        async with self._connect() as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO user_settings (
                    user_id, category_slugs, enabled, initialized, created_at, updated_at
                )
                VALUES (?, '', 1, 0, ?, ?)
                """,
                (user_id, now, now),
            )
            await db.commit()

    async def get_user_settings_by_tg_user(self, tg_user_id: int) -> UserSettingsRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT us.user_id, us.category_slugs, us.enabled, us.initialized
                FROM user_settings us
                JOIN users u ON u.id = us.user_id
                WHERE u.tg_user_id = ?
                """,
                (tg_user_id,),
            )
            row = await cursor.fetchone()
        return UserSettingsRecord(*row) if row else None

    async def set_user_enabled(self, tg_user_id: int, enabled: bool) -> bool:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                UPDATE user_settings
                SET enabled = ?, updated_at = ?
                WHERE user_id = (SELECT id FROM users WHERE tg_user_id = ?)
                """,
                (1 if enabled else 0, utc_now_iso(), tg_user_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def set_user_initialized(self, user_id: int) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE user_settings
                SET initialized = 1, updated_at = ?
                WHERE user_id = ?
                """,
                (utc_now_iso(), user_id),
            )
            await db.commit()

    async def set_user_categories(self, tg_user_id: int, slugs: list[str]) -> bool:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                UPDATE user_settings
                SET category_slugs = ?, updated_at = ?
                WHERE user_id = (SELECT id FROM users WHERE tg_user_id = ?)
                """,
                (",".join(slugs), utc_now_iso(), tg_user_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def add_keyword(
        self,
        tg_user_id: int,
        keyword: str,
        required_terms: list[str] | None = None,
    ) -> tuple[bool, KeywordRecord | None]:
        terms = [
            item.strip().lower()
            for item in (required_terms or [keyword])
            if item.strip()
        ]
        if not terms:
            return False, None
        seen_terms: set[str] = set()
        normalized_terms = []
        for term in terms:
            if term not in seen_terms:
                seen_terms.add(term)
                normalized_terms.append(term)
        normalized = (
            " + ".join(sorted(normalized_terms))
            if len(normalized_terms) > 1
            else normalized_terms[0]
        )
        required_keywords = ",".join(normalized_terms)
        now = utc_now_iso()
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT id
                FROM users
                WHERE tg_user_id = ?
                """,
                (tg_user_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return False, None
            user_id = int(row[0])
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO keywords (
                    user_id, keyword, normalized_keyword, required_keywords,
                    hit_count, last_hit_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 0, NULL, ?, ?)
                """,
                (user_id, keyword.strip(), normalized, required_keywords, now, now),
            )
            inserted = cursor.rowcount > 0
            await db.commit()
            cursor = await db.execute(
                """
                SELECT id, user_id, keyword, normalized_keyword, required_keywords,
                       hit_count, last_hit_at
                FROM keywords
                WHERE user_id = ? AND normalized_keyword = ?
                """,
                (user_id, normalized),
            )
            keyword_row = await cursor.fetchone()
        return inserted, KeywordRecord(*keyword_row) if keyword_row else None

    async def list_keywords_by_tg_user(self, tg_user_id: int) -> list[KeywordRecord]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT k.id, k.user_id, k.keyword, k.normalized_keyword,
                       k.required_keywords, k.hit_count, k.last_hit_at
                FROM keywords k
                JOIN users u ON u.id = k.user_id
                WHERE u.tg_user_id = ?
                ORDER BY k.id ASC
                """,
                (tg_user_id,),
            )
            rows = await cursor.fetchall()
        return [KeywordRecord(*row) for row in rows]

    async def delete_keyword(self, tg_user_id: int, keyword_id: int) -> bool:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                DELETE FROM keywords
                WHERE id = ?
                  AND user_id = (SELECT id FROM users WHERE tg_user_id = ?)
                """,
                (keyword_id, tg_user_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def add_block_keyword(
        self,
        tg_user_id: int,
        keyword: str,
    ) -> tuple[bool, BlockKeywordRecord | None]:
        normalized = keyword.strip().lower()
        if not normalized:
            return False, None
        now = utc_now_iso()
        async with self._connect() as db:
            cursor = await db.execute(
                "SELECT id FROM users WHERE tg_user_id = ?",
                (tg_user_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return False, None
            user_id = int(row[0])
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO block_keywords (
                    user_id, keyword, normalized_keyword, hit_count,
                    last_hit_at, created_at, updated_at
                )
                VALUES (?, ?, ?, 0, NULL, ?, ?)
                """,
                (user_id, keyword.strip(), normalized, now, now),
            )
            inserted = cursor.rowcount > 0
            await db.commit()
            cursor = await db.execute(
                """
                SELECT id, user_id, keyword, normalized_keyword, hit_count, last_hit_at
                FROM block_keywords
                WHERE user_id = ? AND normalized_keyword = ?
                """,
                (user_id, normalized),
            )
            block_row = await cursor.fetchone()
        return inserted, BlockKeywordRecord(*block_row) if block_row else None

    async def list_block_keywords_by_tg_user(self, tg_user_id: int) -> list[BlockKeywordRecord]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT b.id, b.user_id, b.keyword, b.normalized_keyword,
                       b.hit_count, b.last_hit_at
                FROM block_keywords b
                JOIN users u ON u.id = b.user_id
                WHERE u.tg_user_id = ?
                ORDER BY b.id ASC
                """,
                (tg_user_id,),
            )
            rows = await cursor.fetchall()
        return [BlockKeywordRecord(*row) for row in rows]

    async def delete_block_keyword(self, tg_user_id: int, block_keyword_id: int) -> bool:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                DELETE FROM block_keywords
                WHERE id = ?
                  AND user_id = (SELECT id FROM users WHERE tg_user_id = ?)
                """,
                (block_keyword_id, tg_user_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def bump_keyword_hits(self, user_id: int, normalized_keywords: list[str]) -> None:
        if not normalized_keywords:
            return
        async with self._connect() as db:
            for keyword in normalized_keywords:
                await db.execute(
                    """
                    UPDATE keywords
                    SET hit_count = hit_count + 1,
                        last_hit_at = ?,
                        updated_at = ?
                    WHERE user_id = ? AND normalized_keyword = ?
                    """,
                    (utc_now_iso(), utc_now_iso(), user_id, keyword.lower()),
                )
            await db.commit()

    async def bump_block_keyword_hits(self, user_id: int, normalized_keywords: list[str]) -> None:
        if not normalized_keywords:
            return
        async with self._connect() as db:
            for keyword in normalized_keywords:
                await db.execute(
                    """
                    UPDATE block_keywords
                    SET hit_count = hit_count + 1,
                        last_hit_at = ?,
                        updated_at = ?
                    WHERE user_id = ? AND normalized_keyword = ?
                    """,
                    (utc_now_iso(), utc_now_iso(), user_id, keyword.lower()),
                )
            await db.commit()

    async def list_history_by_tg_user(self, tg_user_id: int, limit: int) -> list[DeliveryRecord]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT d.id, d.user_id, d.item_key, d.title, d.link,
                       d.category_slug, d.matched_keywords, d.delivered_at
                FROM delivery_history d
                JOIN users u ON u.id = d.user_id
                WHERE u.tg_user_id = ?
                  AND d.delivery_status = 'sent'
                ORDER BY d.id DESC
                LIMIT ?
                """,
                (tg_user_id, limit),
            )
            rows = await cursor.fetchall()
        return [DeliveryRecord(*row) for row in rows]

    async def get_polling_users(self) -> list[PollingUserRecord]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT u.id, u.tg_user_id, u.chat_id, u.username, u.first_name,
                       us.category_slugs, us.enabled, us.initialized
                FROM users u
                JOIN user_settings us ON us.user_id = u.id
                WHERE us.enabled = 1
                ORDER BY u.id ASC
                """
            )
            user_rows = await cursor.fetchall()

            results: list[PollingUserRecord] = []
            for row in user_rows:
                user = UserRecord(*row[:5])
                settings = UserSettingsRecord(user.id, row[5], row[6], row[7])

                cursor = await db.execute(
                    """
                    SELECT id, user_id, keyword, normalized_keyword, required_keywords,
                           hit_count, last_hit_at
                    FROM keywords
                    WHERE user_id = ?
                    ORDER BY id ASC
                    """,
                    (user.id,),
                )
                keyword_rows = await cursor.fetchall()
                if not keyword_rows:
                    continue

                cursor = await db.execute(
                    """
                    SELECT id, user_id, keyword, normalized_keyword,
                           hit_count, last_hit_at
                    FROM block_keywords
                    WHERE user_id = ?
                    ORDER BY id ASC
                    """,
                    (user.id,),
                )
                block_keyword_rows = await cursor.fetchall()

                results.append(
                    PollingUserRecord(
                        user=user,
                        settings=settings,
                        keywords=[KeywordRecord(*item) for item in keyword_rows],
                        block_keywords=[BlockKeywordRecord(*item) for item in block_keyword_rows],
                    )
                )

        return results

    async def is_delivered(self, user_id: int, item_key: str) -> bool:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT 1
                FROM delivery_history
                WHERE user_id = ? AND item_key = ?
                """,
                (user_id, item_key),
            )
            row = await cursor.fetchone()
        return row is not None

    async def mark_delivered(
        self,
        user_id: int,
        item_key: str,
        *,
        title: str,
        link: str,
        category_slug: str | None,
        matched_keywords: list[str],
        delivery_status: str = "sent",
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO delivery_history (
                    user_id, item_key, title, link, category_slug,
                    matched_keywords, delivery_status, delivered_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    item_key,
                    title,
                    link,
                    category_slug,
                    ",".join(matched_keywords),
                    delivery_status,
                    utc_now_iso(),
                ),
            )
            await db.commit()
