import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from config import Settings

ROBOKASSA_PAYMENT_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"


def calculate_signature(*parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def format_amount(amount: Decimal) -> str:
    return f"{amount:.2f}"


def generate_payment_link(
    settings: Settings,
    inv_id: int,
    order_amount: Decimal | None = None,
) -> str:
    if not settings.payment_configured:
        raise RuntimeError("Robokassa is not configured")
    amount = format_amount(order_amount if order_amount is not None else settings.cost)
    signature = calculate_signature(
        settings.merchant_login,
        amount,
        inv_id,
        settings.password_1,
    )
    params = {
        "MerchantLogin": settings.merchant_login,
        "OutSum": amount,
        "InvId": inv_id,
        "Description": "Доступ в закрытый маникюрный клуб",
        "SignatureValue": signature,
        "IsTest": "1" if settings.robokassa_test else "0",
        "Culture": "ru",
    }
    return f"{ROBOKASSA_PAYMENT_URL}?{urlencode(params)}"


def verify_result_signature(
    out_sum: str,
    inv_id: str,
    received_signature: str,
    password_2: str,
) -> bool:
    expected = calculate_signature(out_sum, inv_id, password_2)
    return hmac.compare_digest(expected.lower(), received_signature.lower())


def parse_amount(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid OutSum") from exc
