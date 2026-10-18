import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from database import Database
from payments import calculate_signature
from tests.helpers import make_settings
from web import create_app


class WebTests(unittest.TestCase):
    def test_callback_is_disabled_without_payment_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory), configured=False)
            database = Database(settings.database_path)
            client = create_app(settings, database).test_client()
            response = client.post(f"{settings.url_prefix}/robokassa/result")
        self.assertEqual(response.status_code, 503)

    def test_valid_callback_marks_order_paid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            database = Database(settings.database_path)
            database.init_schema()
            order = database.get_or_create_pending_order(30, "buyer", Decimal("100.00"))
            inv_id = str(order["inv_id"])
            client = create_app(settings, database).test_client()
            response = client.post(
                f"{settings.url_prefix}/robokassa/result",
                data={
                    "OutSum": "100.00",
                    "InvId": inv_id,
                    "SignatureValue": calculate_signature(
                        "100.00", inv_id, settings.password_2
                    ),
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(database.is_paid(30))
