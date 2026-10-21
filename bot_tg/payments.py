import hashlib
import hmac
import json
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus, urlencode

from config import Settings

ROBOKASSA_PAYMENT_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"


def calculate_signature(*parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def format_amount(amount: Decimal) -> str:
    return f"{amount:.2f}"


def generate_receipt(settings: Settings, amount: Decimal) -> str | None:
    if settings.fiscalization_mode != "receipt":
        return None
    receipt: dict[str, object] = {
        "items": [
            {
                "name": settings.receipt_item_name,
                "quantity": 1,
                "sum": float(format_amount(amount)),
                "payment_method": settings.receipt_payment_method,
                "payment_object": settings.receipt_payment_object,
                "tax": settings.receipt_tax,
            }
        ]
    }
    if settings.receipt_sno:
        receipt["sno"] = settings.receipt_sno
    return json.dumps(receipt, ensure_ascii=False, separators=(",", ":"))


def generate_payment_link(
    settings: Settings,
    inv_id: int,
    order_amount: Decimal | None = None,
) -> str:
    if not settings.payment_configured:
        raise RuntimeError("Robokassa is not configured")
    order_amount = order_amount if order_amount is not None else settings.cost
    amount = format_amount(order_amount)
    receipt = generate_receipt(settings, order_amount)
    signature_parts: list[object] = [settings.merchant_login, amount, inv_id]
    encoded_receipt = quote_plus(receipt) if receipt is not None else None
    if encoded_receipt is not None:
        signature_parts.append(encoded_receipt)
    signature_parts.append(settings.password_1)
    signature = calculate_signature(*signature_parts)
    params = {
        "MerchantLogin": settings.merchant_login,
        "OutSum": amount,
        "InvId": inv_id,
        "Description": "Гайд «Домашний уход за стопами»",
        "SignatureValue": signature,
        "IsTest": "1" if settings.robokassa_test else "0",
        "Culture": "ru",
    }
    if encoded_receipt is not None:
        params["Receipt"] = encoded_receipt
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
