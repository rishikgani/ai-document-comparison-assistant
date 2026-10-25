from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
import sqlite3


DATABASE_PATH = Path(__file__).parent / "data" / "app.db"


def _connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _database_connection():
    """Open, commit, and always close a database connection."""

    connection = _connect()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database() -> None:
    with _database_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS comparison_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                document_a TEXT NOT NULL,
                document_b TEXT NOT NULL,
                conclusion TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_email TEXT PRIMARY KEY,
                avatar TEXT NOT NULL DEFAULT 'Neon orb',
                workspace_reminder_seen INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS account_signins (
                user_email TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                provider TEXT NOT NULL,
                last_sign_in TEXT NOT NULL
            )
            """
        )
        profile_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(user_profiles)")
        }
        if "workspace_reminder_seen" not in profile_columns:
            connection.execute(
                "ALTER TABLE user_profiles ADD COLUMN workspace_reminder_seen INTEGER NOT NULL DEFAULT 0"
            )


def record_sign_in(user_email: str, display_name: str, provider: str) -> None:
    """Save the latest sign-in details for the account."""

    with _database_connection() as connection:
        connection.execute(
            """
            INSERT INTO account_signins
                (user_email, display_name, provider, last_sign_in)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_email) DO UPDATE SET
                display_name = excluded.display_name,
                provider = excluded.provider,
                last_sign_in = excluded.last_sign_in
            """,
            (
                user_email,
                display_name,
                provider,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )


def get_signed_in_accounts(limit: int = 100) -> list[dict[str, str]]:
    """Return recent account sign-ins for the private host dashboard."""

    with _database_connection() as connection:
        rows = connection.execute(
            """
            SELECT user_email, display_name, provider, last_sign_in
            FROM account_signins
            ORDER BY last_sign_in DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_avatar(user_email: str) -> str:
    with _database_connection() as connection:
        row = connection.execute(
            "SELECT avatar FROM user_profiles WHERE user_email = ?",
            (user_email,),
        ).fetchone()
    return row["avatar"] if row else "Neon orb"


def save_avatar(user_email: str, avatar: str) -> None:
    with _database_connection() as connection:
        connection.execute(
            """
            INSERT INTO user_profiles (user_email, avatar)
            VALUES (?, ?)
            ON CONFLICT(user_email) DO UPDATE SET avatar = excluded.avatar
            """,
            (user_email, avatar),
        )


def has_seen_workspace_reminder(user_email: str) -> bool:
    """Return whether this account has already received the workspace reminder."""

    with _database_connection() as connection:
        row = connection.execute(
            "SELECT workspace_reminder_seen FROM user_profiles WHERE user_email = ?",
            (user_email,),
        ).fetchone()
    return bool(row and row["workspace_reminder_seen"])


def mark_workspace_reminder_seen(user_email: str) -> None:
    """Persist that the account has received the post-login workspace reminder."""

    with _database_connection() as connection:
        connection.execute(
            """
            INSERT INTO user_profiles (user_email, workspace_reminder_seen)
            VALUES (?, 1)
            ON CONFLICT(user_email) DO UPDATE SET workspace_reminder_seen = 1
            """,
            (user_email,),
        )


def save_comparison(user_email: str, document_a: str, document_b: str, conclusion: str) -> None:
    with _database_connection() as connection:
        connection.execute(
            """
            INSERT INTO comparison_history
                (user_email, document_a, document_b, conclusion, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_email,
                document_a,
                document_b,
                conclusion,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )


def get_history(user_email: str, limit: int = 25) -> list[dict[str, str]]:
    with _database_connection() as connection:
        rows = connection.execute(
            """
            SELECT document_a, document_b, conclusion, created_at
            FROM comparison_history
            WHERE user_email = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_email, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def clear_history(user_email: str) -> None:
    """Delete comparison history belonging only to the specified user."""

    with _database_connection() as connection:
        connection.execute(
            "DELETE FROM comparison_history WHERE user_email = ?",
            (user_email,),
        )


def get_host_summary() -> dict[str, int]:
    with _database_connection() as connection:
        users = connection.execute(
            "SELECT COUNT(DISTINCT user_email) AS count FROM comparison_history"
        ).fetchone()["count"]
        comparisons = connection.execute(
            "SELECT COUNT(*) AS count FROM comparison_history"
        ).fetchone()["count"]
    return {"users": users, "comparisons": comparisons}


def get_all_history(limit: int = 50) -> list[dict[str, str]]:
    with _database_connection() as connection:
        rows = connection.execute(
            """
            SELECT user_email, document_a, document_b, conclusion, created_at
            FROM comparison_history
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
