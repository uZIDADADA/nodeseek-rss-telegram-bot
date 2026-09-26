from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiosqlite
from telegram.ext import CommandHandler

from app.bot import BotHandlers, build_application
from app.config import Settings
from app.db import Database
from app.poller import FeedPoller


class OwnerConfigurationTests(unittest.TestCase):
    def test_owner_id_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {
                    "BOT_TOKEN": "test-token",
                    "DATABASE_PATH": str(Path(directory) / "bot.db"),
                    "ALLOWED_USER_IDS": "",
                },
                clear=True,
            ):
                with self.assertRaisesRegex(RuntimeError, "ALLOWED_USER_IDS"):
                    Settings.load()

    def test_only_one_owner_id_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = {
                "BOT_TOKEN": "test-token",
                "DATABASE_PATH": str(Path(directory) / "bot.db"),
                "ALLOWED_USER_IDS": "12345",
            }
            with patch.dict(os.environ, environment, clear=True):
                self.assertEqual(Settings.load().allowed_user_ids, (12345,))
                os.environ["ALLOWED_USER_IDS"] = "12345,67890"
                with self.assertRaisesRegex(RuntimeError, "只能填写一个"):
                    Settings.load()


class PrivateDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_database_sends_to_owner_without_target_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "bot.db")
            await db.init()
            async with aiosqlite.connect(db.path) as connection:
                cursor = await connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'targets'"
                )
                self.assertIsNone(await cursor.fetchone())

            await db.ensure_user_profile(
                tg_user_id=12345,
                chat_id=12345,
                username="owner",
                first_name="Owner",
            )
            await db.add_keyword(12345, "keyword")
            users = await db.get_polling_users()
            self.assertEqual(len(users), 1)

            settings = SimpleNamespace(
                allowed_user_ids=(12345,),
                http_timeout_seconds=20,
                max_entries_per_feed=10,
                mark_as_read_on_first_poll=False,
                disable_web_page_preview=True,
            )
            poller = FeedPoller(settings, db)
            entry = SimpleNamespace(
                item_key="post-1",
                title="keyword post",
                author="Author",
                link="https://www.nodeseek.com/post-1-1",
                source_text="keyword post",
                category_slug=None,
                category_name="未知",
            )
            bot = SimpleNamespace(send_message=AsyncMock())
            await poller._handle_user(bot, users[0], [entry])
            self.assertEqual(bot.send_message.await_args.kwargs["chat_id"], 12345)

    async def test_group_cannot_control_private_bot(self) -> None:
        reply_text = AsyncMock()
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=-100123456, type="supergroup"),
            effective_user=SimpleNamespace(id=12345),
            effective_message=SimpleNamespace(reply_text=reply_text),
        )
        db = AsyncMock()
        handlers = BotHandlers(
            settings=SimpleNamespace(allowed_user_ids=(12345,)),
            db=db,
        )

        self.assertIsNone(await handlers.ensure_user(update))
        reply_text.assert_awaited_once()
        db.ensure_user_profile.assert_not_awaited()

    async def test_other_users_cannot_create_profiles(self) -> None:
        reply_text = AsyncMock()
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=67890, type="private"),
            effective_user=SimpleNamespace(id=67890),
            effective_message=SimpleNamespace(reply_text=reply_text),
        )
        db = AsyncMock()
        handlers = BotHandlers(
            settings=SimpleNamespace(allowed_user_ids=(12345,)),
            db=db,
        )

        self.assertIsNone(await handlers.ensure_user(update))
        db.ensure_user_profile.assert_not_awaited()


class CommandRegistrationTests(unittest.TestCase):
    def test_only_private_delivery_commands_are_registered(self) -> None:
        application = build_application(
            SimpleNamespace(bot_token="12345:test-token"),
            AsyncMock(),
        )
        commands = {
            command
            for handlers in application.handlers.values()
            for handler in handlers
            if isinstance(handler, CommandHandler)
            for command in handler.commands
        }
        self.assertIn("del", commands)
        self.assertNotIn("delkw", commands)
        self.assertTrue(commands.isdisjoint({"target", "targets", "addtarget", "deltarget", "chatid"}))


class PollerAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_old_other_user_records_are_not_polled(self) -> None:
        owner = SimpleNamespace(user=SimpleNamespace(tg_user_id=12345))
        old_user = SimpleNamespace(user=SimpleNamespace(tg_user_id=67890))
        db = SimpleNamespace(get_polling_users=AsyncMock(return_value=[owner, old_user]))
        settings = SimpleNamespace(
            allowed_user_ids=(12345,),
            http_timeout_seconds=20,
            max_entries_per_feed=10,
            rss_url="https://rss.nodeseek.com/",
        )
        poller = FeedPoller(settings, db)
        poller.feed_client.fetch = AsyncMock(return_value=SimpleNamespace(entries=[]))
        poller._handle_user = AsyncMock()

        await poller.run_once(SimpleNamespace())

        poller._handle_user.assert_awaited_once()
        self.assertIs(poller._handle_user.await_args.args[1], owner)
