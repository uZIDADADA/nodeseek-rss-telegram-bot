from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiosqlite

from app.bot import BotHandlers
from app.db import Database
from app.keyboard import build_main_menu


class KeywordManagementTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_keyword_menu_flow(self) -> None:
        self.assertEqual(
            [button.text for button in build_main_menu().keyboard[2]],
            ["删除关键词", "帮助"],
        )

        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "bot.db")
            await db.init()
            await db.ensure_user_profile(
                tg_user_id=12345,
                chat_id=12345,
                username="owner",
                first_name="Owner",
            )
            _, keyword = await db.add_keyword(12345, "oracle")
            handlers = BotHandlers(
                settings=SimpleNamespace(allowed_user_ids=(12345,)),
                db=db,
            )
            message = SimpleNamespace(text="删除关键词", reply_text=AsyncMock())
            update = SimpleNamespace(
                effective_message=message,
                effective_user=SimpleNamespace(
                    id=12345,
                    username="owner",
                    first_name="Owner",
                ),
                effective_chat=SimpleNamespace(id=12345, type="private"),
            )
            context = SimpleNamespace(user_data={})

            await handlers.handle_text_message(update, context)
            self.assertTrue(context.user_data["awaiting_delete_keyword"])
            self.assertIn("oracle", message.reply_text.await_args.args[0])

            message.text = str(keyword.id)
            await handlers.handle_text_message(update, context)
            self.assertEqual(await db.list_keywords_by_tg_user(12345), [])
            self.assertNotIn("awaiting_delete_keyword", context.user_data)

            await db.add_keyword(12345, "oracle")
            message.text = "删除关键词"
            await handlers.handle_text_message(update, context)
            message.text = "取消"
            await handlers.handle_text_message(update, context)
            self.assertEqual(len(await db.list_keywords_by_tg_user(12345)), 1)
            self.assertNotIn("awaiting_delete_keyword", context.user_data)

    async def test_more_than_fifty_keywords_and_combo_can_be_added(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "bot.db")
            await db.init()
            await db.ensure_user_profile(
                tg_user_id=12345,
                chat_id=12345,
                username="owner",
                first_name="Owner",
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

            message.text = f"/del {keywords[0].id}"
            await handlers.delete_keyword(update, SimpleNamespace(user_data={}))
            self.assertEqual(len(await db.list_keywords_by_tg_user(12345)), 51)

    async def test_new_keyword_schema_has_no_toggle_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "bot.db")
            await db.init()
            async with aiosqlite.connect(db.path) as connection:
                cursor = await connection.execute("PRAGMA table_info(keywords)")
                columns = {row[1] for row in await cursor.fetchall()}
            self.assertNotIn("enabled", columns)
