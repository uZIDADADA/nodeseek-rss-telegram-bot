from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_id_list(value: str | None) -> tuple[int, ...]:
    if not value:
        return tuple()
    result = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        result.append(int(item))
    return tuple(result)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_path: Path
    rss_url: str
    history_limit: int
    poll_interval_seconds: int
    http_timeout_seconds: int
    max_entries_per_feed: int
    mark_as_read_on_first_poll: bool
    disable_web_page_preview: bool
    log_level: str
    allowed_user_ids: tuple[int, ...]

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()

        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            raise RuntimeError("BOT_TOKEN 未配置，请先复制 .env.example 为 .env 并填写。")

        database_path = Path(os.getenv("DATABASE_PATH", "data/bot.db"))
        database_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            allowed_user_ids = _parse_id_list(
                os.getenv("ALLOWED_USER_IDS", os.getenv("BOT_OWNER_IDS"))
            )
        except ValueError as exc:
            raise RuntimeError("ALLOWED_USER_IDS 必须填写一个 Telegram 数字用户 ID。") from exc
        if len(allowed_user_ids) != 1 or allowed_user_ids[0] <= 0:
            raise RuntimeError("ALLOWED_USER_IDS 必须填写且只能填写一个 Telegram 数字用户 ID。")

        return cls(
            bot_token=bot_token,
            database_path=database_path,
            rss_url=os.getenv("RSS_URL", "https://rss.nodeseek.com/").strip(),
            history_limit=int(os.getenv("HISTORY_LIMIT", "10")),
            poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "10")),
            http_timeout_seconds=int(os.getenv("HTTP_TIMEOUT_SECONDS", "20")),
            max_entries_per_feed=int(os.getenv("MAX_ENTRIES_PER_FEED", "30")),
            mark_as_read_on_first_poll=_parse_bool(os.getenv("MARK_AS_READ_ON_FIRST_POLL"), True),
            disable_web_page_preview=_parse_bool(os.getenv("DISABLE_WEB_PAGE_PREVIEW"), False),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            allowed_user_ids=allowed_user_ids,
        )
