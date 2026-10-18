import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from payments import calculate_signature, generate_payment_link
from tests.helpers import make_settings


class PaymentTests(unittest.TestCase):
    def test_link_contains_protocol_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            params = parse_qs(urlparse(generate_payment_link(settings, 42)).query)
        self.assertEqual(params["OutSum"], ["100.00"])
        self.assertEqual(params["InvId"], ["42"])
        self.assertEqual(
            params["SignatureValue"],
            [calculate_signature("merchant", "100.00", 42, "password-one")],
        )

    def test_link_is_blocked_without_real_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory), configured=False)
            with self.assertRaises(RuntimeError):
                generate_payment_link(settings, 1)
