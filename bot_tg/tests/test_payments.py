import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote_plus, urlparse

from payments import calculate_signature, generate_payment_link, generate_receipt
from tests.helpers import make_settings


class PaymentTests(unittest.TestCase):
    def test_link_contains_protocol_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            params = parse_qs(urlparse(generate_payment_link(settings, 42)).query)
        self.assertEqual(params["OutSum"], ["100.00"])
        self.assertEqual(params["InvId"], ["42"])
        encoded_receipt = params["Receipt"][0]
        receipt = json.loads(unquote_plus(encoded_receipt))
        self.assertEqual(receipt["sno"], "usn_income")
        self.assertEqual(receipt["items"][0]["tax"], "none")
        self.assertEqual(receipt["items"][0]["name"], "Гайд «Домашний уход за стопами»")
        self.assertEqual(
            params["SignatureValue"],
            [
                calculate_signature(
                    "merchant",
                    "100.00",
                    42,
                    encoded_receipt,
                    "password-one",
                )
            ],
        )
        self.assertEqual(
            encoded_receipt, quote_plus(generate_receipt(settings, settings.cost))
        )

    def test_npd_mode_uses_signature_without_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = replace(make_settings(Path(directory)), fiscalization_mode="npd")
            params = parse_qs(urlparse(generate_payment_link(settings, 43)).query)

        self.assertNotIn("Receipt", params)
        self.assertEqual(
            params["SignatureValue"],
            [calculate_signature("merchant", "100.00", 43, "password-one")],
        )

    def test_link_is_blocked_without_real_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory), configured=False)
            with self.assertRaises(RuntimeError):
                generate_payment_link(settings, 1)
