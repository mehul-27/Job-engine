from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from career_os.browser import BrowserSession, match_field


class MatchFieldTests(unittest.TestCase):
    def test_matches_email(self) -> None:
        self.assertEqual("email", match_field("Email Address"))
        self.assertEqual("email", match_field("E-mail"))
        self.assertEqual("email", match_field("email"))

    def test_matches_name(self) -> None:
        self.assertEqual("name", match_field("Full Name"))
        self.assertEqual("name", match_field("Your Name"))
        self.assertEqual("first_name", match_field("First Name"))
        self.assertEqual("last_name", match_field("Last Name"))

    def test_matches_phone(self) -> None:
        self.assertEqual("phone", match_field("Phone Number"))
        self.assertEqual("phone", match_field("Mobile"))
        self.assertEqual("phone", match_field("Telephone"))

    def test_matches_linkedin(self) -> None:
        self.assertEqual("linkedin", match_field("LinkedIn URL"))
        self.assertEqual("linkedin", match_field("LinkedIn Profile"))

    def test_matches_work_auth(self) -> None:
        self.assertEqual("work_authorization", match_field("Work Authorization"))
        self.assertEqual("work_authorization", match_field("Are you legally authorized to work in the US?"))

    def test_returns_none_for_unknown(self) -> None:
        self.assertIsNone(match_field("Favorite color"))
        self.assertIsNone(match_field("Pet name"))


class BrowserSessionTests(unittest.TestCase):
    def test_raises_without_start(self) -> None:
        session = BrowserSession("http://test.com", {}, "/tmp")
        with self.assertRaises(RuntimeError):
            session.detect_fields()
        with self.assertRaises(RuntimeError):
            session.fill_known_fields()
        with self.assertRaises(RuntimeError):
            session.screenshot()

    @patch("playwright.sync_api.sync_playwright")
    def test_start_launches_browser(self, mock_pw: MagicMock) -> None:
        mock_pw.return_value.start.return_value.chromium.launch.return_value.new_page.return_value = MagicMock()
        session = BrowserSession("http://test.com", {}, "/tmp")
        session.start()
        self.assertIsNotNone(session._page)
        session._page.goto.assert_called_with("http://test.com", timeout=30000)

    @patch("playwright.sync_api.sync_playwright")
    def test_detect_fields_returns_list(self, mock_pw: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.evaluate.return_value = [
            {"tag": "input", "type": "text", "name": "email", "id": "", "placeholder": "", "label": "Email", "required": True, "visible": True},
        ]
        mock_pw.return_value.start.return_value.chromium.launch.return_value.new_page.return_value = mock_page
        session = BrowserSession("http://test.com", {}, "/tmp")
        session.start()
        fields = session.detect_fields()
        self.assertEqual(1, len(fields))
        self.assertEqual("email", fields[0]["name"])

    @patch("playwright.sync_api.sync_playwright")
    def test_fill_known_fields(self, mock_pw: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.evaluate.return_value = [
            {"tag": "input", "type": "text", "name": "email", "id": "", "placeholder": "", "label": "Email", "required": True, "visible": True},
            {"tag": "input", "type": "text", "name": "fullname", "id": "", "placeholder": "", "label": "Full Name", "required": True, "visible": True},
            {"tag": "textarea", "type": "", "name": "notes", "id": "", "placeholder": "", "label": "Notes", "required": False, "visible": True},
        ]
        mock_pw.return_value.start.return_value.chromium.launch.return_value.new_page.return_value = mock_page
        session = BrowserSession("http://test.com", {"email": "a@b.com", "name": "Alice"}, "/tmp")
        session.start()
        session.detect_fields()
        session.fill_known_fields()
        self.assertIn("email", session.fields_filled)
        self.assertIn("name", session.fields_filled)
        self.assertEqual(0, len(session.fields_unknown))

    @patch("playwright.sync_api.sync_playwright")
    def test_pause_resume(self, mock_pw: MagicMock) -> None:
        mock_pw.return_value.start.return_value.chromium.launch.return_value.new_page.return_value = MagicMock()
        session = BrowserSession("http://test.com", {}, "/tmp")
        session.start()
        self.assertFalse(session.is_paused)
        session.pause("Unknown field: favorite_color")
        self.assertTrue(session.is_paused)
        self.assertEqual("Unknown field: favorite_color", session.pause_reason)
        session.resume()
        self.assertFalse(session.is_paused)
        self.assertIsNone(session.pause_reason)

    @patch("playwright.sync_api.sync_playwright")
    def test_close_cleans_up(self, mock_pw: MagicMock) -> None:
        mock_browser = MagicMock()
        mock_pw_obj = MagicMock()
        mock_pw_obj.chromium.launch.return_value = mock_browser
        mock_pw.return_value.start.return_value = mock_pw_obj
        session = BrowserSession("http://test.com", {}, "/tmp")
        session.start()
        session.close()
        mock_browser.close.assert_called_once()
        mock_pw_obj.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
