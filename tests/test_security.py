from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.bot import BotHandlers
from app.config import Settings
from app.db import Database


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


class TargetAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_group_is_not_automatically_added_as_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "bot.db")
            await db.init()
            await db.ensure_user_profile(
                tg_user_id=12345,
                chat_id=-100123456,
                username="owner",
                first_name="Owner",
                chat_title="A group",
                chat_type="supergroup",
            )
            self.assertEqual(await db.list_targets_by_tg_user(12345), [])

            await db.ensure_user_profile(
                tg_user_id=12345,
                chat_id=12345,
                username="owner",
                first_name="Owner",
                chat_title="Owner",
                chat_type="private",
            )
            targets = await db.list_targets_by_tg_user(12345)
            self.assertEqual([target.chat_id for target in targets], [12345])

    async def test_non_admin_cannot_bind_group(self) -> None:
        reply_text = AsyncMock()
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=-100123456, type="supergroup"),
            effective_user=SimpleNamespace(id=12345),
            effective_message=SimpleNamespace(reply_text=reply_text),
        )
        context = SimpleNamespace(
            bot=SimpleNamespace(
                get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member"))
            )
        )
        handlers = BotHandlers(
            settings=SimpleNamespace(allowed_user_ids=(12345,)),
            db=AsyncMock(),
        )

        self.assertIsNone(await handlers._resolve_target_chat(update, context, None))
        reply_text.assert_awaited_once()

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
