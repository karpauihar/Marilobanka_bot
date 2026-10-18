import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot_handlers import send_welcome, show_payment
from database import Database
from tests.helpers import make_settings


class PaymentHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_payment_is_hidden_until_channel_is_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = replace(make_settings(Path(directory)), access_chat_id=None)
            database = Database(settings.database_path)
            database.init_schema()
            message = SimpleNamespace(reply_text=AsyncMock())
            update = SimpleNamespace(
                effective_user=SimpleNamespace(id=40, username="visitor"),
                effective_message=message,
            )
            context = SimpleNamespace(
                application=SimpleNamespace(
                    bot_data={"settings": settings, "database": database}
                )
            )

            await show_payment(update, context)

            response_text = message.reply_text.await_args.args[0]
            self.assertIn("оплата временно недоступна", response_text)
            self.assertFalse(database.is_paid(40))


class WelcomeHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_configured_welcome_message_is_copied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            message = SimpleNamespace(reply_text=AsyncMock())
            bot = SimpleNamespace(copy_message=AsyncMock())
            update = SimpleNamespace(
                effective_chat=SimpleNamespace(id=50),
                effective_message=message,
            )
            context = SimpleNamespace(
                bot=bot,
                application=SimpleNamespace(bot_data={"settings": settings}),
            )

            await send_welcome(update, context)

            bot.copy_message.assert_awaited_once()
            call = bot.copy_message.await_args.kwargs
            self.assertEqual(call["from_chat_id"], settings.welcome_chat_id)
            self.assertEqual(call["message_id"], settings.welcome_message_id)
            self.assertEqual(message.reply_text.await_count, 1)
