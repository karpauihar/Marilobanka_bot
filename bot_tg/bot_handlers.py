import asyncio
import logging
from decimal import Decimal

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from channel_access import issue_channel_access
from config import Settings
from database import Database
from payments import generate_payment_link

log = logging.getLogger(__name__)

MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["Мой доступ"],
        ["Оферта", "Поддержка"],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Выберите действие",
)


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Оферта", callback_data="offer")]]
    )


def payment_keyboard(payment_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Оплатить 🇷🇺 🇧🇾 🇪🇺", url=payment_url)],
            [InlineKeyboardButton("Оферта", callback_data="offer")],
        ]
    )


async def silence_service_chats(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    settings: Settings = context.application.bot_data["settings"]
    service_chat_ids = {
        chat_id
        for chat_id in (
            settings.welcome_chat_id,
            settings.offer_chat_id,
            settings.access_chat_id,
        )
        if chat_id is not None
    }
    if update.effective_chat and update.effective_chat.id in service_chat_ids:
        raise ApplicationHandlerStop


async def send_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    welcome_sent = False
    if settings.welcome_configured:
        try:
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=settings.welcome_chat_id,
                message_id=settings.welcome_message_id,
                reply_markup=start_keyboard(),
            )
            welcome_sent = True
        except TelegramError as exc:
            log.warning(
                "Welcome copy failed error_type=%s",
                type(exc).__name__,
            )

    if not welcome_sent:
        await update.effective_message.reply_text(
            "Добро пожаловать! ✨\n\n"
            "Здесь находится гайд «Домашний уход за стопами» и дополнительные "
            "информационные материалы. Сейчас бот работает в тестовом режиме.",
            reply_markup=start_keyboard(),
        )
    await update.effective_message.reply_text(
        "Используйте меню, чтобы посмотреть макет бота.",
        reply_markup=MAIN_MENU_KEYBOARD,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    database: Database = context.application.bot_data["database"]
    user = update.effective_user
    database.upsert_user(user.id, user.username)
    database.mark_welcome_sent(user.id)
    await send_welcome(update, context)
    await show_payment(update, context)


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Гайд «Домашний уход за стопами» содержит информационные материалы "
        "по безопасному домашнему уходу.\n\n"
        "Материалы не являются медицинской услугой, диагнозом или "
        "индивидуальным назначением и не заменяют консультацию врача.",
        reply_markup=MAIN_MENU_KEYBOARD,
    )


async def show_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    database: Database = context.application.bot_data["database"]
    user = update.effective_user
    database.upsert_user(user.id, user.username)

    if database.is_paid(user.id):
        await send_channel_access(update, context)
        return

    if not settings.payment_configured:
        await update.effective_message.reply_text(
            "Оплата пока недоступна: бот работает в тестовом режиме.\n\n"
            "После подключения Robokassa здесь появится кнопка оплаты, "
            "а доступ в закрытый канал будет выдаваться автоматически.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Оплата скоро появится", callback_data="payment_unavailable"
                        )
                    ],
                    [InlineKeyboardButton("Оферта", callback_data="offer")],
                ]
            ),
        )
        return

    if not settings.channel_configured:
        await update.effective_message.reply_text(
            "Закрытый канал ещё настраивается, поэтому оплата временно "
            "недоступна. Кнопка появится после подключения канала.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return

    order = database.get_or_create_pending_order(user.id, user.username, settings.cost)
    if order is None:
        await send_channel_access(update, context)
        return
    payment_url = generate_payment_link(
        settings, order["inv_id"], Decimal(order["amount"])
    )
    await update.effective_message.reply_text(
        "Гайд «Домашний уход за стопами»\n\n"
        f"<s>4990 руб</s> {settings.cost:g} руб\n\n"
        "После подтверждения оплаты бот пришлёт персональную ссылку.\n\n"
        "Нажимая «Оплатить», вы подтверждаете, что ознакомились "
        "с условиями публичной оферты и принимаете их.",
        parse_mode=ParseMode.HTML,
        reply_markup=payment_keyboard(payment_url),
    )


async def send_channel_access(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    settings: Settings = context.application.bot_data["settings"]
    database: Database = context.application.bot_data["database"]
    user = update.effective_user
    database.upsert_user(user.id, user.username)

    if not database.is_paid(user.id):
        await update.effective_message.reply_text(
            "Оплата ещё не подтверждена. Доступ в закрытый канал пока не открыт.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return
    if not settings.channel_configured:
        await update.effective_message.reply_text(
            "Оплата подтверждена, но закрытый канал ещё настраивается. "
            "Ссылка будет отправлена после подключения канала.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return

    try:
        await issue_channel_access(
            context.bot,
            settings,
            database,
            user.id,
            member_reply_markup=MAIN_MENU_KEYBOARD,
        )
    except TelegramError as exc:
        log.error(
            "Channel access failed user_id=%s error_type=%s",
            user.id,
            type(exc).__name__,
        )
        await update.effective_message.reply_text(
            "Не удалось создать ссылку на канал. Попробуйте позже.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if settings.support_url:
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Написать в поддержку", url=settings.support_url)]]
        )
        text = "Если возник вопрос, напишите в поддержку."
    else:
        markup = MAIN_MENU_KEYBOARD
        text = "Контакты поддержки появятся здесь перед полноценным запуском."
    await update.effective_message.reply_text(text, reply_markup=markup)


async def offer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if settings.offer_message_configured:
        try:
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=settings.offer_chat_id,
                message_id=settings.offer_message_id,
                protect_content=True,
            )
            return
        except TelegramError as exc:
            log.warning(
                "Offer copy failed error_type=%s",
                type(exc).__name__,
            )

    if settings.offer_file_path is not None:
        with settings.offer_file_path.open("rb") as document:
            await update.effective_message.reply_document(
                document=document,
                filename=settings.offer_file_path.name,
                reply_markup=MAIN_MENU_KEYBOARD,
                protect_content=True,
            )
        return

    await update.effective_message.reply_text(
        "Оферта будет опубликована перед подключением оплаты.",
        reply_markup=MAIN_MENU_KEYBOARD,
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == "buy_access":
        await show_payment(update, context)
    elif query.data == "about":
        await about(update, context)
    elif query.data == "offer":
        await offer(update, context)
    elif query.data == "payment_unavailable":
        await query.message.reply_text(
            "Мы сообщим о запуске оплаты после завершения настройки.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )


async def delivery_worker(application: Application) -> None:
    settings: Settings = application.bot_data["settings"]
    database: Database = application.bot_data["database"]
    if settings.access_chat_id is None:
        return
    while True:
        try:
            for user_id in database.paid_users_without_channel_access(
                settings.access_chat_id
            ):
                try:
                    await issue_channel_access(
                        application.bot, settings, database, user_id
                    )
                except TelegramError as exc:
                    log.warning(
                        "Channel delivery retry failed user_id=%s error_type=%s",
                        user_id,
                        type(exc).__name__,
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.error("Delivery worker error error_type=%s", type(exc).__name__)
        await asyncio.sleep(settings.delivery_retry_seconds)


async def post_init(application: Application) -> None:
    settings: Settings = application.bot_data["settings"]
    me = await application.bot.get_me()
    log.info(
        "Bot started username=%s payments_configured=%s channel_configured=%s "
        "welcome_configured=%s",
        me.username,
        settings.payment_configured,
        settings.channel_configured,
        settings.welcome_configured,
    )
    if settings.channel_configured:
        application.bot_data["delivery_task"] = asyncio.create_task(
            delivery_worker(application)
        )


async def post_shutdown(application: Application) -> None:
    task = application.bot_data.get("delivery_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Telegram handler error error_type=%s", type(context.error).__name__)


def build_application(settings: Settings, database: Database) -> Application:
    application = (
        ApplicationBuilder()
        .token(settings.token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data.update(settings=settings, database=database)
    application.add_handler(TypeHandler(Update, silence_service_chats), group=-1)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(
        MessageHandler(filters.Regex("^Оформить доступ$"), show_payment)
    )
    application.add_handler(
        MessageHandler(filters.Regex("^Мой доступ$"), send_channel_access)
    )
    application.add_handler(MessageHandler(filters.Regex("^О гайде$"), about))
    application.add_handler(MessageHandler(filters.Regex("^Поддержка$"), support))
    application.add_handler(MessageHandler(filters.Regex("^Оферта$"), offer))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, support))
    application.add_error_handler(error_handler)
    return application
