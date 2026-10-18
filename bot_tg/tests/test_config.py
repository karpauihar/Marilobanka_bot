import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from tests.helpers import make_settings


class ConfigTests(unittest.TestCase):
    def test_demo_settings_do_not_enable_payment_or_channel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory), configured=False)
        self.assertFalse(settings.payment_configured)
        self.assertFalse(settings.channel_configured)
        self.assertEqual(settings.cost, Decimal(0))

    def test_complete_settings_enable_payment_and_channel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
        self.assertTrue(settings.payment_configured)
        self.assertTrue(settings.channel_configured)
