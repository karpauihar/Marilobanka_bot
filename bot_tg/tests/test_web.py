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

    def test_invalid_signature_does_not_mark_order_paid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            database = Database(settings.database_path)
            database.init_schema()
            order = database.get_or_create_pending_order(31, "buyer", Decimal("100.00"))
            client = create_app(settings, database).test_client()
            response = client.post(
                f"{settings.url_prefix}/robokassa/result",
                data={
                    "OutSum": "100.00",
                    "InvId": str(order["inv_id"]),
                    "SignatureValue": "invalid",
                },
            )
            self.assertEqual(response.status_code, 400)
            self.assertFalse(database.is_paid(31))

    def test_repeat_callback_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            database = Database(settings.database_path)
            database.init_schema()
            order = database.get_or_create_pending_order(32, "buyer", Decimal("100.00"))
            inv_id = str(order["inv_id"])
            payload = {
                "OutSum": "100.00",
                "InvId": inv_id,
                "SignatureValue": calculate_signature(
                    "100.00", inv_id, settings.password_2
                ),
            }
            client = create_app(settings, database).test_client()
            first = client.post(f"{settings.url_prefix}/robokassa/result", data=payload)
            second = client.post(
                f"{settings.url_prefix}/robokassa/result", data=payload
            )
            self.assertEqual(first.data, second.data)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)

    def test_health_reports_readiness_without_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            client = create_app(settings).test_client()
            response = client.get(f"{settings.url_prefix}/health")
            payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["payments_configured"])
        self.assertNotIn("password", payload)
