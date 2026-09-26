from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiosqlite

from app.bot import BotHandlers
from app.db import Database


class KeywordManagementTests(unittest.IsolatedAsyncioTestCase):
    async def test_more_than_fifty_keywords_and_combo_can_be_added(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "bot.db")
            await db.init()
            await db.ensure_user_profile(
                tg_user_id=12345,
                chat_id=12345,
                username="owner",
                first_name="Owner",
                chat_title="Owner",
                chat_type="private",
            )
            handlers = BotHandlers(
                settings=SimpleNamespace(allowed_user_ids=(12345,)),
                db=db,
            )
            message = SimpleNamespace(reply_text=AsyncMock())
            update = SimpleNamespace(
                effective_message=message,
                effective_user=SimpleNamespace(
                    id=12345,
                    username="owner",
                    first_name="Owner",
                    full_name="Owner",
                ),
                effective_chat=SimpleNamespace(id=12345, type="private", title=None),
            )

            await handlers._add_keywords_from_text(
                update,
                12345,
                ",".join(f"keyword-{index}-" + "x" * 50 for index in range(51)),
            )
            self.assertGreater(message.reply_text.await_count, 1)
            self.assertTrue(
                all(len(call.args[0]) <= 1800 for call in message.reply_text.await_args_list)
            )
            message.text = "/combo alpha,beta"
            await handlers.combo(update, SimpleNamespace())

            keywords = await db.list_keywords_by_tg_user(12345)
            self.assertEqual(len(keywords), 52)
            self.assertEqual(keywords[-1].keyword, "alpha + beta")

            message.reply_text.reset_mock()
            message.text = "/keywords"
            await handlers.keywords(update, SimpleNamespace())
            self.assertGreater(message.reply_text.await_count, 1)
            self.assertTrue(
                all(len(call.args[0]) <= 1800 for call in message.reply_text.await_args_list)
            )

    async def test_legacy_disabled_keyword_stays_unmonitored_until_readded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "bot.db")
            await db.init()
            await db.ensure_user_profile(
                tg_user_id=12345,
                chat_id=12345,
                username="owner",
                first_name="Owner",
                chat_title="Owner",
                chat_type="private",
            )
            _, paused = await db.add_keyword(12345, "paused")
            await db.add_keyword(12345, "active")
            async with aiosqlite.connect(db.path) as connection:
                await connection.execute(
                    "UPDATE keywords SET enabled = 0 WHERE id = ?", (paused.id,)
                )
                await connection.commit()

            await db.init()
            users = await db.get_polling_users()
            self.assertEqual([item.keyword for item in users[0].keywords], ["active"])

            self.assertTrue(await db.delete_keyword(12345, paused.id))
            self.assertTrue((await db.add_keyword(12345, "paused"))[0])
            users = await db.get_polling_users()
            self.assertEqual([item.keyword for item in users[0].keywords], ["active", "paused"])
