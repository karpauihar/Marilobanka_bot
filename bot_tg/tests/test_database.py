import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "bot.db")
        self.database.init_schema()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_payment_is_required_before_paid_status(self) -> None:
        order = self.database.get_or_create_pending_order(
            10, "visitor", Decimal("100.00")
        )
        self.assertFalse(self.database.is_paid(10))
        self.assertEqual(
            self.database.mark_order_paid(order["inv_id"], Decimal("100.00")),
            "paid_now",
        )
        self.assertTrue(self.database.is_paid(10))

    def test_rejects_wrong_amount(self) -> None:
        order = self.database.get_or_create_pending_order(11, None, Decimal("100.00"))
        self.assertEqual(
            self.database.mark_order_paid(order["inv_id"], Decimal("1.00")),
            "amount_mismatch",
        )
        self.assertFalse(self.database.is_paid(11))
