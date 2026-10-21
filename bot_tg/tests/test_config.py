import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from config import load_settings
from tests.helpers import make_settings


class ConfigTests(unittest.TestCase):
    def test_demo_settings_do_not_enable_payment_or_channel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory), configured=False)
        self.assertFalse(settings.payment_configured)
        self.assertFalse(settings.channel_configured)
        self.assertFalse(settings.welcome_configured)
        self.assertEqual(settings.cost, Decimal(0))

    def test_complete_settings_enable_payment_and_channel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
        self.assertTrue(settings.payment_configured)
        self.assertTrue(settings.channel_configured)
        self.assertTrue(settings.welcome_configured)

    def test_offer_message_requires_chat_and_message_id(self) -> None:
        environment = {
            "TOKEN": "123:test-token",
            "OFFER_CHAT_ID": "-1004311095377",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch("config.load_dotenv"),
        ):
            load_settings.cache_clear()
            with self.assertRaisesRegex(RuntimeError, "must be set together"):
                load_settings()
        load_settings.cache_clear()

    def test_access_channel_url_must_be_telegram_https(self) -> None:
        environment = {
            "TOKEN": "123:test-token",
            "ACCESS_CHANNEL_URL": "https://example.test/channel",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch("config.load_dotenv"),
        ):
            load_settings.cache_clear()
            with self.assertRaisesRegex(RuntimeError, "HTTPS t.me URL"):
                load_settings()
        load_settings.cache_clear()

    def test_test_mode_selects_test_password_pair(self) -> None:
        environment = {
            "TOKEN": "123:test-token",
            "PASS_1": "live-one",
            "PASS_2": "live-two",
            "PASS_TEST_1": "test-one",
            "PASS_TEST_2": "test-two",
            "ROBOKASSA_TEST": "1",
            "FISCALIZATION_MODE": "npd",
        }
        with patch.dict(os.environ, environment, clear=True):
            load_settings.cache_clear()
            settings = load_settings()
        load_settings.cache_clear()
        self.assertEqual(settings.password_1, "test-one")
        self.assertEqual(settings.password_2, "test-two")

    def test_production_mode_selects_live_password_pair(self) -> None:
        environment = {
            "TOKEN": "123:test-token",
            "PASS_1": "live-one",
            "PASS_2": "live-two",
            "PASS_TEST_1": "test-one",
            "PASS_TEST_2": "test-two",
            "ROBOKASSA_TEST": "0",
            "FISCALIZATION_MODE": "npd",
        }
        with patch.dict(os.environ, environment, clear=True):
            load_settings.cache_clear()
            settings = load_settings()
        load_settings.cache_clear()
        self.assertEqual(settings.password_1, "live-one")
        self.assertEqual(settings.password_2, "live-two")
