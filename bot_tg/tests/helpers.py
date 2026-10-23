from decimal import Decimal
from pathlib import Path

from config import Settings


def make_settings(tmp_path: Path, *, configured: bool = True) -> Settings:
    return Settings(
        token="123:test-token",
        merchant_login="merchant" if configured else "",
        password_1="password-one" if configured else "",
        password_2="password-two" if configured else "",
        password_3="password-three" if configured else "",
        server_url="https://example.test" if configured else "",
        url_prefix="/bots/marilobanka",
        cost=Decimal("100.00") if configured else Decimal(0),
        access_chat_id=-1001234567890 if configured else None,
        access_channel_url=("https://t.me/c/3918171171/4" if configured else ""),
        welcome_chat_id=-1009876543210 if configured else None,
        welcome_message_id=4 if configured else None,
        offer_chat_id=None,
        offer_message_id=None,
        support_url="",
        offer_file_path=None,
        database_path=tmp_path / "bot.db",
        log_path=tmp_path / "app.log",
        robokassa_test=True,
        fiscalization_mode="receipt" if configured else "",
        receipt_sno="usn_income" if configured else "",
        receipt_tax="none" if configured else "",
        receipt_payment_method="full_payment" if configured else "",
        receipt_payment_object="service" if configured else "",
        receipt_item_name=("Гайд «Домашний уход за стопами»" if configured else ""),
        delivery_retry_seconds=5,
        log_level="INFO",
    )
