import unittest

from auth_utils import get_account_identity


class AuthUtilsTests(unittest.TestCase):
    def test_extracts_microsoft_account_identity(self):
        identity = get_account_identity(
            {
                "iss": "https://login.microsoftonline.com/tenant-id/v2.0",
                "preferred_username": "Person@Example.com",
                "name": "Example Person",
            }
        )

        self.assertEqual(identity["email"], "person@example.com")
        self.assertEqual(identity["display_name"], "Example Person")
        self.assertEqual(identity["provider"], "Microsoft")

    def test_prefers_email_claim_and_detects_google(self):
        identity = get_account_identity(
            {
                "iss": "https://accounts.google.com",
                "email": "Person@Example.com",
                "preferred_username": "other@example.com",
                "name": "Example Person",
            }
        )

        self.assertEqual(identity["email"], "person@example.com")
        self.assertEqual(identity["provider"], "Google")

    def test_requires_an_email_or_username_claim(self):
        with self.assertRaisesRegex(ValueError, "did not provide an email"):
            get_account_identity({"iss": "https://login.microsoftonline.com/tenant/v2.0"})


if __name__ == "__main__":
    unittest.main()
