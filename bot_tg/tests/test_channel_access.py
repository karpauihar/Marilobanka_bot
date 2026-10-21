import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from channel_access import issue_channel_access
from database import Database
from tests.helpers import make_settings


class FakeBot:
    def __init__(self, member_status: str = "left") -> None:
        self.created: list[dict[str, object]] = []
        self.sent: list[dict[str, object]] = []
        self.member_status = member_status

    async def get_chat_member(self, chat_id: int, user_id: int) -> object:
        return SimpleNamespace(
            status=self.member_status,
            is_member=self.member_status == "member",
        )

    async def create_chat_invite_link(self, **kwargs: object) -> object:
        self.created.append(kwargs)
        return SimpleNamespace(invite_link="https://t.me/+single-use")

    async def send_message(self, **kwargs: object) -> None:
        self.sent.append(kwargs)


class ChannelAccessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings = make_settings(Path(self.temp_dir.name))
        self.database = Database(self.settings.database_path)
        self.database.init_schema()

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_unpaid_user_never_gets_invite(self) -> None:
        self.database.upsert_user(20, "visitor")
        bot = FakeBot()
        result = await issue_channel_access(bot, self.settings, self.database, 20)
        self.assertEqual(result.status, "payment_required")
        self.assertEqual(bot.created, [])

    async def test_paid_user_gets_single_member_invite(self) -> None:
        order = self.database.get_or_create_pending_order(
            21, "buyer", Decimal("100.00")
        )
        self.database.mark_order_paid(order["inv_id"], Decimal("100.00"))
        bot = FakeBot()
        result = await issue_channel_access(bot, self.settings, self.database, 21)
        self.assertEqual(result.status, "invite_sent")
        self.assertEqual(bot.created[0]["member_limit"], 1)

    async def test_existing_member_gets_direct_channel_link(self) -> None:
        order = self.database.get_or_create_pending_order(
            22, "member", Decimal("100.00")
        )
        self.database.mark_order_paid(order["inv_id"], Decimal("100.00"))
        bot = FakeBot(member_status="member")

        result = await issue_channel_access(bot, self.settings, self.database, 22)

        self.assertEqual(result.status, "already_member")
        self.assertEqual(bot.created, [])
        self.assertEqual(len(bot.sent), 1)
        message = bot.sent[0]
        self.assertIn(
            'по <a href="https://t.me/c/3918171171/5">этой ссылке</a>.',
            message["text"],
        )
        self.assertEqual(message["parse_mode"], "HTML")
        self.assertTrue(message["disable_web_page_preview"])
