import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import user_data


class UserDataTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "app.db"
        self.database_patch = patch.object(user_data, "DATABASE_PATH", self.database_path)
        self.database_patch.start()

    def tearDown(self):
        self.database_patch.stop()
        self.temp_dir.cleanup()

    def test_workspace_reminder_is_persisted_per_user(self):
        user_data.initialize_database()

        self.assertFalse(user_data.has_seen_workspace_reminder("one@example.com"))
        self.assertFalse(user_data.has_seen_workspace_reminder("two@example.com"))

        user_data.mark_workspace_reminder_seen("one@example.com")

        self.assertTrue(user_data.has_seen_workspace_reminder("one@example.com"))
        self.assertFalse(user_data.has_seen_workspace_reminder("two@example.com"))

    def test_clear_history_deletes_only_the_selected_users_records(self):
        user_data.initialize_database()
        user_data.save_comparison("one@example.com", "a.pdf", "b.pdf", "One's conclusion")
        user_data.save_comparison("two@example.com", "c.pdf", "d.pdf", "Two's conclusion")

        user_data.clear_history("one@example.com")

        self.assertEqual(user_data.get_history("one@example.com"), [])
        self.assertEqual(len(user_data.get_history("two@example.com")), 1)

    def test_sign_in_records_are_upserted_and_account_scoped(self):
        user_data.initialize_database()
        user_data.record_sign_in("one@example.com", "One", "Microsoft")
        user_data.record_sign_in("two@example.com", "Two", "Google")
        user_data.record_sign_in("one@example.com", "Updated One", "Microsoft")

        accounts = user_data.get_signed_in_accounts()
        accounts_by_email = {account["user_email"]: account for account in accounts}

        self.assertEqual(len(accounts), 2)
        self.assertEqual(accounts_by_email["one@example.com"]["display_name"], "Updated One")
        self.assertEqual(accounts_by_email["one@example.com"]["provider"], "Microsoft")
        self.assertTrue(accounts_by_email["one@example.com"]["last_sign_in"])
        self.assertEqual(accounts_by_email["two@example.com"]["provider"], "Google")

    def test_initialize_database_migrates_legacy_profiles(self):
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                "CREATE TABLE user_profiles (user_email TEXT PRIMARY KEY, avatar TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO user_profiles (user_email, avatar) VALUES (?, ?)",
                ("legacy@example.com", "Nova"),
            )
            connection.commit()
        finally:
            connection.close()

        user_data.initialize_database()

        connection = sqlite3.connect(self.database_path)
        try:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(user_profiles)")
            }
            reminder_value = connection.execute(
                "SELECT workspace_reminder_seen FROM user_profiles WHERE user_email = ?",
                ("legacy@example.com",),
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertIn("workspace_reminder_seen", columns)
        self.assertEqual(reminder_value, 0)


if __name__ == "__main__":
    unittest.main()
