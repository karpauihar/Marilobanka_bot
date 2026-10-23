import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROBOKASSA_INV_ID_FLOOR = 1_000_000_000_000


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def init_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    status TEXT NOT NULL DEFAULT 'new'
                        CHECK (status IN ('new', 'pending', 'paid')),
                    welcome_sent_at TEXT,
                    current_inv_id INTEGER,
                    paid_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                    inv_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'paid', 'cancelled')),
                    created_at TEXT NOT NULL,
                    paid_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
                CREATE INDEX IF NOT EXISTS idx_orders_user_status
                    ON orders(user_id, status);
                CREATE TABLE IF NOT EXISTS channel_access (
                    user_id INTEGER PRIMARY KEY,
                    chat_id INTEGER,
                    invite_link TEXT,
                    invite_created_at TEXT,
                    invite_sent_at TEXT,
                    joined_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
                """
            )
            user_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(users)")
            }
            if "current_inv_id" not in user_columns:
                connection.execute(
                    "ALTER TABLE users ADD COLUMN current_inv_id INTEGER"
                )
            if "paid_at" not in user_columns:
                connection.execute("ALTER TABLE users ADD COLUMN paid_at TEXT")

    def upsert_user(self, user_id: int, username: str | None) -> sqlite3.Row:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO users (user_id, username, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    updated_at = excluded.updated_at
                """,
                (user_id, username, now, now),
            )
            return connection.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()

    def mark_welcome_sent(self, user_id: int) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "UPDATE users SET welcome_sent_at = COALESCE(welcome_sent_at, ?), updated_at = ? WHERE user_id = ?",
                (now, now, user_id),
            )

    def get_or_create_pending_order(
        self, user_id: int, username: str | None, amount: Decimal
    ) -> sqlite3.Row | None:
        now = utc_now()
        amount_text = f"{amount:.2f}"
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO users (user_id, username, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, updated_at = excluded.updated_at
                """,
                (user_id, username, now, now),
            )
            user = connection.execute(
                "SELECT status FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if user["status"] == "paid":
                return None
            pending = connection.execute(
                "SELECT * FROM orders WHERE user_id = ? AND status = 'pending' ORDER BY inv_id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if pending and pending["inv_id"] >= ROBOKASSA_INV_ID_FLOOR:
                return pending

            if pending:
                connection.execute(
                    "UPDATE orders SET status = 'cancelled' WHERE inv_id = ?",
                    (pending["inv_id"],),
                )

            latest_inv_id = connection.execute(
                "SELECT COALESCE(MAX(inv_id), 0) FROM orders"
            ).fetchone()[0]
            inv_id = max(
                ROBOKASSA_INV_ID_FLOOR,
                time.time_ns() // 1_000_000,
                latest_inv_id + 1,
            )
            connection.execute(
                "INSERT INTO orders (inv_id, user_id, amount, status, created_at) "
                "VALUES (?, ?, ?, 'pending', ?)",
                (inv_id, user_id, amount_text, now),
            )
            connection.execute(
                "UPDATE users SET status = 'pending', current_inv_id = ?, "
                "updated_at = ? WHERE user_id = ?",
                (inv_id, now, user_id),
            )
            return connection.execute(
                "SELECT * FROM orders WHERE inv_id = ?", (inv_id,)
            ).fetchone()

    def get_order(self, inv_id: int) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM orders WHERE inv_id = ?", (inv_id,)
            ).fetchone()

    def mark_order_paid(self, inv_id: int, amount: Decimal) -> str:
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            order = connection.execute(
                "SELECT * FROM orders WHERE inv_id = ?", (inv_id,)
            ).fetchone()
            if order is None:
                return "not_found"
            if Decimal(order["amount"]) != amount:
                return "amount_mismatch"
            if order["status"] == "paid":
                return "already_paid"
            if order["status"] == "cancelled":
                return "cancelled"
            connection.execute(
                "UPDATE orders SET status = 'paid', paid_at = ? WHERE inv_id = ?",
                (now, inv_id),
            )
            connection.execute(
                "UPDATE users SET status = 'paid', paid_at = COALESCE(paid_at, ?), "
                "current_inv_id = ?, updated_at = ? WHERE user_id = ?",
                (now, inv_id, now, order["user_id"]),
            )
            return "paid_now"

    def is_paid(self, user_id: int) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT status FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            return bool(row and row["status"] == "paid")

    def get_channel_access(self, user_id: int) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM channel_access WHERE user_id = ?", (user_id,)
            ).fetchone()

    def save_channel_invite(self, user_id: int, chat_id: int, link: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO channel_access (user_id, chat_id, invite_link, invite_created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id = excluded.chat_id,
                    invite_link = excluded.invite_link,
                    invite_created_at = excluded.invite_created_at,
                    invite_sent_at = NULL,
                    joined_at = NULL
                """,
                (user_id, chat_id, link, now),
            )

    def mark_channel_invite_sent(self, user_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE channel_access SET invite_sent_at = ? WHERE user_id = ?",
                (utc_now(), user_id),
            )

    def mark_channel_member(self, user_id: int, chat_id: int) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO channel_access (user_id, chat_id, invite_sent_at, joined_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id, joined_at = excluded.joined_at
                """,
                (user_id, chat_id, now, now),
            )

    def paid_users_without_channel_access(self, chat_id: int) -> list[int]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT users.user_id FROM users
                LEFT JOIN channel_access ON channel_access.user_id = users.user_id
                WHERE users.status = 'paid' AND (
                    channel_access.user_id IS NULL OR channel_access.chat_id != ? OR
                    (channel_access.invite_sent_at IS NULL AND channel_access.joined_at IS NULL)
                )
                """,
                (chat_id,),
            ).fetchall()
            return [row["user_id"] for row in rows]
