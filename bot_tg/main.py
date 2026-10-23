import asyncio
import logging
from logging.handlers import RotatingFileHandler

from telegram import Update
from telegram.ext import Application

from bot_handlers import build_application
from config import Settings, load_settings
from database import Database


def configure_logging(settings: Settings) -> None:
    settings.log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    rotating_file = RotatingFileHandler(
        settings.log_path,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    rotating_file.setFormatter(formatter)
    logging.basicConfig(level=settings.log_level, handlers=[console, rotating_file])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def run() -> None:
    settings = load_settings()
    configure_logging(settings)
    database = Database(settings.database_path)
    database.init_schema()
    application: Application = build_application(settings, database)
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    try:
        run()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
