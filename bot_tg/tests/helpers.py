from decimal import Decimal
from pathlib import Path

from config import Settings


def make_settings(tmp_path: Path, *, configured: bool = True) -> Settings:
    return Settings(
        token="123:test-token",
        merchant_login="merchant" if configured else "",
        password_1="password-one" if configured else "",
        password_2="password-two" if configured else "",
        server_url="https://example.test" if configured else "",
        url_prefix="/bots/marilobanka",
        cost=Decimal("100.00") if configured else Decimal(0),
        access_chat_id=-1001234567890 if configured else None,
        support_url="",
        offer_file_path=None,
        database_path=tmp_path / "bot.db",
        log_path=tmp_path / "app.log",
        robokassa_test=True,
        delivery_retry_seconds=5,
        log_level="INFO",
    )
