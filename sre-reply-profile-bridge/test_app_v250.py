import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

os.environ.setdefault("FN_UNSUBSCRIBE_SIGNING_SECRET", "unit-test-secret-only")

import app as candidate


class OutreachV251Tests(unittest.TestCase):
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

    def test_production_entrypoint_activates_v251_release(self):
        self.assertEqual(candidate.SRE_BRIDGE_RELEASE, "FN-SRE-BRIDGE-2.5.1-CANDIDATE")
        self.assertIs(candidate.app, candidate.legacy.app)
        self.assertIs(candidate.legacy._direct_scan_once, __import__("app_v250")._direct_scan_once_v250)
        self.assertIs(candidate.legacy.build_franklin_message, __import__("app_v251").build_franklin_message_v251)

    def test_membership_visibility_is_primary_and_prominent_in_every_email(self):
        path = Path(__file__).with_name("direct_outreach_sequence.json")
        sequence = json.loads(path.read_text(encoding="utf-8"))
        visibility = "Its main benefit is helping increase your visibility in the Franklin community."
        for step in sequence["steps"]:
            body = step["body"]
            html_body = step["html_body"]
            self.assertIn(visibility, body, step["id"])
            self.assertIn(f"<strong>{visibility}</strong>", html_body, step["id"])
            self.assertLess(body.index(visibility), body.index("It also"), step["id"])

    def test_new_paid_member_benefits_are_present_in_every_email(self):
        path = Path(__file__).with_name("direct_outreach_sequence.json")
        sequence = json.loads(path.read_text(encoding="utf-8"))
        required_phrases = (
            "business logo or profile image",
            "coupons, specials, sales, and events",
            "promotional flyers and coupon graphics",
            "website/contact links",
            "booking or quote links where available",
        )
        for step in sequence["steps"]:
            body = step["body"]
            html_body = step["html_body"]
            for phrase in required_phrases:
                self.assertIn(phrase, body, f"{step['id']} plain missing {phrase}")
                self.assertIn(phrase, html_body, f"{step['id']} html missing {phrase}")

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

    def test_rendered_email_has_one_outreach_disclosure_not_two(self):
        path = Path(__file__).with_name("direct_outreach_sequence.json")
        sequence = json.loads(path.read_text(encoding="utf-8"))
        step = sequence["steps"][0]
        plain_body = step["body"].replace("{{Outreach_Greeting}}", "Test Business").replace("{{Profile_URL}}", "https://franklinnavigator.com/profiles/test/")
        html_body = step["html_body"].replace("{{Outreach_Greeting}}", "Test Business").replace("{{Profile_URL}}", "https://franklinnavigator.com/profiles/test/")
        msg = candidate.build_franklin_message_v250("owner-test@example.com", step["subject"], plain_body, html_body)
        rendered_plain = ""
        rendered_html = ""
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                rendered_plain = part.get_content().lower()
            elif part.get_content_type() == "text/html":
                rendered_html = part.get_content().lower()
        phrase = "commercial community-outreach email from franklin navigator"
        self.assertEqual(rendered_plain.count(phrase), 1)
        self.assertEqual(rendered_html.count(phrase), 1)

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
