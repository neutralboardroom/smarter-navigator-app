import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

os.environ.setdefault("FN_UNSUBSCRIBE_SIGNING_SECRET", "unit-test-secret-only")

import app_v250 as candidate


class OutreachV250Tests(unittest.TestCase):
    def test_four_step_sequence_validates(self):
        path = Path(__file__).with_name("direct_outreach_sequence.json")
        sequence = json.loads(path.read_text(encoding="utf-8"))
        validated = candidate._validate_direct_sequence_v250(sequence)
        self.assertEqual(
            [step["id"] for step in validated["steps"]],
            ["initial", "followup_1", "followup_2", "reengagement_90d"],
        )
        self.assertEqual(validated["steps"][3]["wait_calendar_days_after_previous"], 90)
        self.assertTrue(validated["stop_rules"]["no_automatic_recurring_reengagement"])

    def test_reengagement_uses_90_calendar_days_not_business_days(self):
        tz = ZoneInfo("America/Chicago")
        previous = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)
        step = {"wait_calendar_days_after_previous": 90}
        too_early = datetime(2026, 3, 31, 18, 0, tzinfo=timezone.utc)
        due = datetime(2026, 4, 1, 18, 0, tzinfo=timezone.utc)
        self.assertFalse(candidate._step_due(step, previous, too_early, tz))
        self.assertTrue(candidate._step_due(step, previous, due, tz))

    def test_unsubscribe_is_visually_isolated_and_prominent(self):
        msg = candidate.build_franklin_message_v250(
            "owner-test@example.com",
            "Test",
            "Plain body",
            "<p>HTML body</p>",
        )
        plain = None
        html = None
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                plain = part.get_content()
            elif part.get_content_type() == "text/html":
                html = part.get_content()
        self.assertIsNotNone(plain)
        self.assertIsNotNone(html)
        self.assertIn("\n\nUNSUBSCRIBE: ", plain.replace("\r\n", "\n"))
        self.assertIn("\n\n2020 Fieldstone Pkwy", plain.replace("\r\n", "\n"))
        self.assertIn("font-size:16px", html)
        self.assertIn("font-weight:700", html)
        self.assertIn("margin-top:24px", html)
        self.assertIn("margin-bottom:24px", html)
        self.assertIn("List-Unsubscribe", msg)
        self.assertEqual(msg["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_unsubscribe_persists_to_zoho_suppression_contract(self):
        with patch.object(candidate.legacy, "_persist_zoho_suppression") as persist:
            with patch.object(candidate.legacy, "MAILSHAKE_RUNTIME_ENABLED", False):
                candidate.legacy.persist_unsubscribe("test@example.com")
        persist.assert_called_once_with("test@example.com", "unsubscribe")

    def test_suppressed_recipient_is_never_eligible(self):
        self.assertTrue(
            candidate._recipient_is_suppressed(
                "stop@example.com",
                "example.com",
                {"stop@example.com"},
                set(),
                {"domain_holds": {}, "domain_suppressions": {}},
            )
        )
        self.assertTrue(
            candidate._recipient_is_suppressed(
                "other@example.com",
                "example.com",
                set(),
                {"example.com"},
                {"domain_holds": {}, "domain_suppressions": {}},
            )
        )
        self.assertFalse(
            candidate._recipient_is_suppressed(
                "ok@example.com",
                "example.com",
                set(),
                set(),
                {"domain_holds": {}, "domain_suppressions": {}},
            )
        )

    def test_visible_unsubscribe_keeps_confirmation_step(self):
        token = candidate.legacy.make_unsubscribe_token("owner-test@example.com")
        page = candidate.legacy.visible_unsubscribe(token)
        body = page.body.decode("utf-8")
        self.assertIn('method="post"', body)
        self.assertIn("/unsubscribe/confirm/", body)
        self.assertIn('name="confirm" value="1"', body)


if __name__ == "__main__":
    unittest.main()
