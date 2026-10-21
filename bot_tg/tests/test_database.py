import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from database import ROBOKASSA_INV_ID_FLOOR, Database


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

    def test_order_numbers_are_large_and_unique(self) -> None:
        first = self.database.get_or_create_pending_order(
            20, "first", Decimal("100.00")
        )
        second = self.database.get_or_create_pending_order(
            21, "second", Decimal("100.00")
        )
        self.assertGreaterEqual(first["inv_id"], ROBOKASSA_INV_ID_FLOOR)
        self.assertGreaterEqual(second["inv_id"], ROBOKASSA_INV_ID_FLOOR)
        self.assertNotEqual(first["inv_id"], second["inv_id"])

    def test_legacy_pending_order_is_replaced(self) -> None:
        self.database.upsert_user(22, "legacy")
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO orders "
                "(inv_id, user_id, amount, status, created_at) "
                "VALUES (7, 22, '100.00', 'pending', '2026-01-01T00:00:00+00:00')"
            )
            connection.execute("UPDATE users SET status = 'pending' WHERE user_id = 22")

        replacement = self.database.get_or_create_pending_order(
            22, "legacy", Decimal("100.00")
        )
        self.assertGreaterEqual(replacement["inv_id"], ROBOKASSA_INV_ID_FLOOR)
        self.assertEqual(self.database.get_order(7)["status"], "cancelled")
