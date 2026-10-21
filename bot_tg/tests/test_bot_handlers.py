import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram.error import TelegramError

from bot_handlers import (
    MAIN_MENU_KEYBOARD,
    offer,
    payment_keyboard,
    send_welcome,
    show_payment,
)
from database import Database
from tests.helpers import make_settings


class PaymentHandlerTests(unittest.IsolatedAsyncioTestCase):
    def test_main_menu_omits_redundant_buttons(self) -> None:
        rows = [[button.text for button in row] for row in MAIN_MENU_KEYBOARD.keyboard]

        self.assertEqual(rows, [["Мой доступ"], ["Оферта", "Поддержка"]])

    def test_payment_keyboard_matches_public_layout(self) -> None:
        payment_url = "https://example.test/payment"

        keyboard = payment_keyboard(payment_url)

        self.assertEqual(
            [[button.text for button in row] for row in keyboard.inline_keyboard],
            [["Оплатить 🇷🇺 🇧🇾 🇪🇺"], ["Оферта"]],
        )
        self.assertEqual(keyboard.inline_keyboard[0][0].url, payment_url)

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

    async def test_payment_message_uses_discount_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            database = Database(settings.database_path)
            database.init_schema()
            message = SimpleNamespace(reply_text=AsyncMock())
            update = SimpleNamespace(
                effective_user=SimpleNamespace(id=41, username="visitor"),
                effective_message=message,
            )
            context = SimpleNamespace(
                application=SimpleNamespace(
                    bot_data={"settings": settings, "database": database}
                )
            )

            await show_payment(update, context)

            response_text = message.reply_text.await_args.args[0]
            response_kwargs = message.reply_text.await_args.kwargs
            self.assertIn(
                f"<s>4990 руб</s> {settings.cost:g} руб",
                response_text,
            )
            self.assertEqual(response_kwargs["parse_mode"], "HTML")
            labels = [
                button.text
                for row in response_kwargs["reply_markup"].inline_keyboard
                for button in row
            ]
            self.assertEqual(labels, ["Оплатить 🇷🇺 🇧🇾 🇪🇺", "Оферта"])


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


class OfferHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_configured_offer_message_is_copied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = replace(
                make_settings(Path(directory)),
                offer_chat_id=-1004311095377,
                offer_message_id=6,
            )
            message = SimpleNamespace(reply_document=AsyncMock())
            bot = SimpleNamespace(copy_message=AsyncMock())
            update = SimpleNamespace(
                effective_chat=SimpleNamespace(id=50),
                effective_message=message,
            )
            context = SimpleNamespace(
                bot=bot,
                application=SimpleNamespace(bot_data={"settings": settings}),
            )

            await offer(update, context)

            bot.copy_message.assert_awaited_once_with(
                chat_id=50,
                from_chat_id=-1004311095377,
                message_id=6,
                protect_content=True,
            )
            message.reply_document.assert_not_awaited()

    async def test_offer_pdf_is_sent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            offer_path = Path(directory) / "offer.pdf"
            offer_path.write_bytes(b"%PDF-test")
            settings = replace(
                make_settings(Path(directory)), offer_file_path=offer_path
            )
            message = SimpleNamespace(reply_document=AsyncMock())
            update = SimpleNamespace(effective_message=message)
            context = SimpleNamespace(
                bot=SimpleNamespace(copy_message=AsyncMock()),
                application=SimpleNamespace(bot_data={"settings": settings}),
            )

            await offer(update, context)

            message.reply_document.assert_awaited_once()
            self.assertEqual(
                message.reply_document.await_args.kwargs["filename"],
                offer_path.name,
            )

    async def test_offer_pdf_is_fallback_when_copy_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            offer_path = Path(directory) / "offer.pdf"
            offer_path.write_bytes(b"%PDF-test")
            settings = replace(
                make_settings(Path(directory)),
                offer_chat_id=-1004311095377,
                offer_message_id=6,
                offer_file_path=offer_path,
            )
            message = SimpleNamespace(reply_document=AsyncMock())
            bot = SimpleNamespace(
                copy_message=AsyncMock(side_effect=TelegramError("copy failed"))
            )
            update = SimpleNamespace(
                effective_chat=SimpleNamespace(id=50),
                effective_message=message,
            )
            context = SimpleNamespace(
                bot=bot,
                application=SimpleNamespace(bot_data={"settings": settings}),
            )

            await offer(update, context)

            bot.copy_message.assert_awaited_once()
            message.reply_document.assert_awaited_once()
