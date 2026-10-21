import os
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def _optional_path(name: str) -> Path | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


def _path(name: str, default: str) -> Path:
    value = os.getenv(name, default).strip()
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _url_prefix(value: str) -> str:
    prefix = "/" + value.strip().strip("/")
    if not re.fullmatch(r"/[a-z0-9/_-]+", prefix):
        raise RuntimeError("URL_PREFIX contains unsupported characters")
    return prefix


@dataclass(frozen=True)
class Settings:
    token: str
    merchant_login: str
    password_1: str
    password_2: str
    password_3: str
    server_url: str
    url_prefix: str
    cost: Decimal
    access_chat_id: int | None
    welcome_chat_id: int | None
    welcome_message_id: int | None
    support_url: str
    offer_file_path: Path | None
    database_path: Path
    log_path: Path
    robokassa_test: bool
    fiscalization_mode: str
    receipt_sno: str
    receipt_tax: str
    receipt_payment_method: str
    receipt_payment_object: str
    receipt_item_name: str
    delivery_retry_seconds: int
    log_level: str

    @property
    def payment_configured(self) -> bool:
        return bool(
            self.merchant_login
            and self.password_1
            and self.password_2
            and self.server_url
            and self.cost > 0
            and self.fiscalization_configured
        )

    @property
    def fiscalization_configured(self) -> bool:
        if self.fiscalization_mode == "npd":
            return True
        if self.fiscalization_mode == "receipt":
            return bool(
                self.receipt_tax
                and self.receipt_payment_method
                and self.receipt_payment_object
                and self.receipt_item_name
            )
        return False

    @property
    def channel_configured(self) -> bool:
        return self.access_chat_id is not None

    @property
    def welcome_configured(self) -> bool:
        return self.welcome_chat_id is not None and self.welcome_message_id is not None


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    load_dotenv(PROJECT_DIR / ".env")
    load_dotenv(BASE_DIR / ".env")

    token = os.getenv("TOKEN", "").strip()
    if not token:
        raise RuntimeError("Required environment variable TOKEN is not set")

    raw_cost = os.getenv("COST", "").strip()
    try:
        cost = Decimal(raw_cost) if raw_cost else Decimal(0)
    except InvalidOperation as exc:
        raise RuntimeError("COST must be a valid decimal number") from exc
    if cost < 0:
        raise RuntimeError("COST cannot be negative")

    server_url = os.getenv("SERVER_URL", "").strip().rstrip("/")
    if server_url.startswith("http://") and "127.0.0.1" not in server_url:
        raise RuntimeError("SERVER_URL must use HTTPS outside local development")

    offer_file_path = _optional_path("OFFER_FILE_PATH")
    if offer_file_path is not None and not offer_file_path.is_file():
        raise RuntimeError(f"Offer file does not exist: {offer_file_path}")

    welcome_chat_id = _optional_int("WELCOME_CHAT_ID")
    welcome_message_id = _optional_int("WELCOME_MESSAGE_ID")
    if (welcome_chat_id is None) != (welcome_message_id is None):
        raise RuntimeError(
            "WELCOME_CHAT_ID and WELCOME_MESSAGE_ID must be set together"
        )
    if welcome_message_id is not None and welcome_message_id <= 0:
        raise RuntimeError("WELCOME_MESSAGE_ID must be greater than zero")

    robokassa_test = _as_bool(os.getenv("ROBOKASSA_TEST", "0"))
    password_1_name = "PASS_TEST_1" if robokassa_test else "PASS_1"
    password_2_name = "PASS_TEST_2" if robokassa_test else "PASS_2"

    fiscalization_mode = os.getenv("FISCALIZATION_MODE", "").strip().lower()
    if fiscalization_mode not in {"", "npd", "receipt"}:
        raise RuntimeError("FISCALIZATION_MODE must be 'npd' or 'receipt'")

    receipt_sno = os.getenv("RECEIPT_SNO", "").strip().lower()
    if receipt_sno and receipt_sno not in {
        "osn",
        "usn_income",
        "usn_income_outcome",
        "esn",
        "patent",
    }:
        raise RuntimeError("RECEIPT_SNO contains an unsupported value")

    receipt_tax = os.getenv("RECEIPT_TAX", "").strip().lower()
    if receipt_tax and receipt_tax not in {
        "none",
        "vat0",
        "vat5",
        "vat7",
        "vat10",
        "vat20",
        "vat22",
        "vat105",
        "vat107",
        "vat110",
        "vat120",
        "vat122",
    }:
        raise RuntimeError("RECEIPT_TAX contains an unsupported value")

    receipt_payment_method = os.getenv("RECEIPT_PAYMENT_METHOD", "").strip()
    if receipt_payment_method and receipt_payment_method not in {
        "full_prepayment",
        "prepayment",
        "advance",
        "full_payment",
        "partial_payment",
        "credit",
        "credit_payment",
    }:
        raise RuntimeError("RECEIPT_PAYMENT_METHOD contains an unsupported value")

    receipt_payment_object = os.getenv("RECEIPT_PAYMENT_OBJECT", "").strip()
    if receipt_payment_object and receipt_payment_object not in {
        "commodity",
        "job",
        "service",
        "intellectual_activity",
        "payment",
        "another",
        "property_right",
    }:
        raise RuntimeError("RECEIPT_PAYMENT_OBJECT contains an unsupported value")

    return Settings(
        token=token,
        merchant_login=os.getenv("MERCHANT_LOGIN", "").strip(),
        password_1=os.getenv(password_1_name, "").strip(),
        password_2=os.getenv(password_2_name, "").strip(),
        password_3=os.getenv("PASS_3", "").strip(),
        server_url=server_url,
        url_prefix=_url_prefix(os.getenv("URL_PREFIX", "/bots/marilobanka")),
        cost=cost,
        access_chat_id=_optional_int("ACCESS_CHAT_ID"),
        welcome_chat_id=welcome_chat_id,
        welcome_message_id=welcome_message_id,
        support_url=os.getenv("SUPPORT_URL", "").strip(),
        offer_file_path=offer_file_path,
        database_path=_path("DATABASE_PATH", "bot.db"),
        log_path=_path("LOG_PATH", "logs/app.log"),
        robokassa_test=robokassa_test,
        fiscalization_mode=fiscalization_mode,
        receipt_sno=receipt_sno,
        receipt_tax=receipt_tax,
        receipt_payment_method=receipt_payment_method,
        receipt_payment_object=receipt_payment_object,
        receipt_item_name=os.getenv("RECEIPT_ITEM_NAME", "").strip(),
        delivery_retry_seconds=max(5, int(os.getenv("DELIVERY_RETRY_SECONDS", "15"))),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
