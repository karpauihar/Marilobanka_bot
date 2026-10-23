import logging
from dataclasses import dataclass

from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.error import BadRequest, TelegramError

from config import Settings
from database import Database

log = logging.getLogger(__name__)
ACTIVE_MEMBER_STATUSES = {"member", "administrator", "creator"}


@dataclass(frozen=True)
class AccessResult:
    status: str
    invite_link: str | None = None


def is_active_member(member: object | None) -> bool:
    if member is None:
        return False
    status = getattr(member, "status", "")
    if status in ACTIVE_MEMBER_STATUSES:
        return True
    return status == "restricted" and bool(getattr(member, "is_member", False))


async def send_active_channel_access(
    bot: Bot,
    settings: Settings,
    database: Database,
    user_id: int,
    reply_markup: ReplyKeyboardMarkup | None = None,
) -> None:
    if settings.access_chat_id is None:
        return
    database.mark_channel_member(user_id, settings.access_chat_id)
    text = "Вы уже состоите в закрытом канале. Доступ активен."
    message_options: dict[str, object] = {}
    if settings.access_channel_url:
        text += (
            "\n\nЕсли вы не видите канал в списке чатов, "
            f'откройте его по <a href="{settings.access_channel_url}">этой '
            "ссылке</a>."
        )
        message_options["parse_mode"] = "HTML"
        message_options["disable_web_page_preview"] = True
    await bot.send_message(
        chat_id=user_id,
        text=text,
        reply_markup=reply_markup,
        protect_content=True,
        **message_options,
    )


async def issue_channel_access(
    bot: Bot,
    settings: Settings,
    database: Database,
    user_id: int,
    member_reply_markup: ReplyKeyboardMarkup | None = None,
) -> AccessResult:
    if not database.is_paid(user_id):
        return AccessResult("payment_required")
    if settings.access_chat_id is None:
        return AccessResult("channel_not_configured")

    try:
        member = await bot.get_chat_member(settings.access_chat_id, user_id)
    except BadRequest:
        member = None

    if is_active_member(member):
        await send_active_channel_access(
            bot,
            settings,
            database,
            user_id,
            reply_markup=member_reply_markup,
        )
        return AccessResult("already_member")

    previous = database.get_channel_access(user_id)
    if previous and previous["invite_link"]:
        try:
            await bot.revoke_chat_invite_link(
                previous["chat_id"] or settings.access_chat_id,
                previous["invite_link"],
            )
        except TelegramError as exc:
            log.info(
                "Previous invite could not be revoked user_id=%s error_type=%s",
                user_id,
                type(exc).__name__,
            )

    invite = await bot.create_chat_invite_link(
        chat_id=settings.access_chat_id,
        name=f"paid-user-{user_id}",
        member_limit=1,
    )
    database.save_channel_invite(user_id, settings.access_chat_id, invite.invite_link)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Вступить в закрытый канал", url=invite.invite_link)]]
    )
    await bot.send_message(
        chat_id=user_id,
        text=(
            "Оплата подтверждена — доступ открыт.\n\n"
            "Ссылка рассчитана на одно вступление. Если она устарела, "
            "нажмите «Мой доступ» и получите новую."
        ),
        reply_markup=keyboard,
        protect_content=True,
    )
    database.mark_channel_invite_sent(user_id)
    return AccessResult("invite_sent", invite.invite_link)
