import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot_handlers import show_payment
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
