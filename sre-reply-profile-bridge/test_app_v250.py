import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

os.environ.setdefault("FN_UNSUBSCRIBE_SIGNING_SECRET", "unit-test-secret-only")

import app as candidate


class OutreachV254Tests(unittest.TestCase):
    def _sequence(self):
        path = Path(__file__).with_name("direct_outreach_sequence.json")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_four_step_sequence_validates(self):
        sequence = self._sequence()
        validated = candidate._validate_direct_sequence_v250(sequence)
        self.assertEqual(
            [step["id"] for step in validated["steps"]],
            ["initial", "followup_1", "followup_2", "reengagement_90d"],
        )
        self.assertEqual(validated["steps"][3]["wait_calendar_days_after_previous"], 90)
        self.assertTrue(validated["stop_rules"]["no_automatic_recurring_reengagement"])

    def test_production_entrypoint_activates_v254_release(self):
        self.assertEqual(candidate.SRE_BRIDGE_RELEASE, "FN-SRE-BRIDGE-2.5.4-CANDIDATE")
        self.assertIs(candidate.app, candidate.legacy.app)
        self.assertEqual(self._sequence()["sender"], "Roger Gillman at Franklin Navigator <community@franklinnavigator.com>")

    def test_outreach_copy_readiness_gate_forces_prospect_sending_off(self):
        self.assertTrue(candidate.legacy.FN_DIRECT_OUTREACH_REQUESTED)
        self.assertFalse(candidate.legacy.FN_OUTREACH_COPY_READY)
        self.assertFalse(candidate.legacy.FN_DIRECT_OUTREACH_ENABLED)
        self.assertFalse(candidate.legacy._state["directOutreach"]["enabled"])

    def test_owner_preview_uses_short_current_initial_copy_and_owner_only_path(self):
        fake_client = object()
        with patch.object(candidate.legacy, "_imap_connect") as imap_connect, \
             patch.object(candidate.legacy, "_ledger_reserve", return_value=True) as reserve, \
             patch.object(candidate.legacy, "_ledger_mark_sent") as mark_sent, \
             patch.object(candidate.legacy, "send_franklin_smtp_message", return_value="<owner-preview@test>") as send:
            imap_connect.return_value.__enter__.return_value = fake_client
            message_id = candidate.legacy.send_owner_rfc8058_test_once()
        self.assertEqual(message_id, "<owner-preview@test>")
        args, kwargs = send.call_args
        self.assertEqual(args[0], "reachrgnow@gmail.com")
        self.assertEqual(args[1], "Your Franklin Navigator profile")
        self.assertIn("I’m Roger Gillman with Franklin Navigator", args[2])
        self.assertIn("basic profile is free", args[2])
        self.assertIn("optional paid Community Membership", args[2])
        self.assertIn("visibility in the Franklin community", args[2])
        self.assertNotIn("$35/year", args[2])
        self.assertNotIn("coupons, specials, sales", args[2])
        self.assertNotIn("outreach_key", kwargs)
        self.assertNotIn("bcc_email", kwargs)
        reserve.assert_called_once()
        mark_sent.assert_called_once()

    def test_owner_preview_is_idempotent_when_preview_key_exists(self):
        fake_client = object()
        with patch.object(candidate.legacy, "_imap_connect") as imap_connect, \
             patch.object(candidate.legacy, "_ledger_reserve", return_value=False), \
             patch.object(candidate.legacy, "send_franklin_smtp_message") as send:
            imap_connect.return_value.__enter__.return_value = fake_client
            self.assertIsNone(candidate.legacy.send_owner_rfc8058_test_once())
        send.assert_not_called()

    def test_every_email_is_short_personal_and_visibility_first(self):
        sequence = self._sequence()
        limits = {"initial": 145, "followup_1": 120, "followup_2": 110, "reengagement_90d": 120}
        forbidden = ("$35/year", "coupons, specials, sales", "promotional flyers", "booking or quote links")
        for step in sequence["steps"]:
            body = step["body"]
            self.assertIn("optional paid Community Membership", body)
            self.assertIn("visibility in the Franklin community", body)
            self.assertLessEqual(len(body.split()), limits[step["id"]])
            for phrase in forbidden:
                self.assertNotIn(phrase, body)
        self.assertIn("I’m Roger Gillman", sequence["steps"][0]["body"])
        self.assertIn("Thanks,\nRoger", sequence["steps"][0]["body"])

    def test_followup_timing_and_single_90_day_reengagement_are_preserved(self):
        sequence = self._sequence()
        self.assertEqual(sequence["steps"][1]["wait_business_days_after_previous"], 5)
        self.assertEqual(sequence["steps"][2]["wait_business_days_after_previous"], 7)
        self.assertEqual(sequence["steps"][3]["wait_calendar_days_after_previous"], 90)
        self.assertIn("last automatic email in this outreach sequence", sequence["steps"][3]["body"])
        self.assertTrue(sequence["stop_rules"]["single_reengagement_only"])
        self.assertTrue(sequence["stop_rules"]["no_automatic_recurring_reengagement"])

    def test_reengagement_uses_90_calendar_days_not_business_days(self):
        tz = ZoneInfo("America/Chicago")
        previous = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)
        step = {"wait_calendar_days_after_previous": 90}
        too_early = datetime(2026, 3, 31, 18, 0, tzinfo=timezone.utc)
        due = datetime(2026, 4, 1, 18, 0, tzinfo=timezone.utc)
        self.assertFalse(candidate._step_due(step, previous, too_early, tz))
        self.assertTrue(candidate._step_due(step, previous, due, tz))

    def test_sender_footer_and_unsubscribe_are_personal_but_compliant(self):
        msg = candidate.build_franklin_message_v250(
            "owner-test@example.com", "Test", "Plain body", "<p>HTML body</p>"
        )
        self.assertEqual(msg["From"], "Roger Gillman at Franklin Navigator <community@franklinnavigator.com>")
        self.assertIn("List-Unsubscribe", msg)
        self.assertEqual(msg["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        self.assertNotIn("List-ID", msg)
        self.assertNotIn("Feedback-ID", msg)
        plain = ""
        html = ""
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                plain = part.get_content()
            elif part.get_content_type() == "text/html":
                html = part.get_content()
        self.assertIn("Roger Gillman", plain)
        self.assertIn("Franklin Navigator business outreach. Optional paid membership available.", plain)
        self.assertIn("\n\nUNSUBSCRIBE: ", plain.replace("\r\n", "\n"))
        self.assertIn("font-size:16px", html)
        self.assertIn("font-weight:700", html)

    def test_unsubscribe_persists_to_zoho_suppression_contract(self):
        with patch.object(candidate.legacy, "_persist_zoho_suppression") as persist:
            with patch.object(candidate.legacy, "MAILSHAKE_RUNTIME_ENABLED", False):
                candidate.legacy.persist_unsubscribe("test@example.com")
        persist.assert_called_once_with("test@example.com", "unsubscribe")

    def test_suppressed_recipient_is_never_eligible(self):
        self.assertTrue(candidate._recipient_is_suppressed(
            "stop@example.com", "example.com", {"stop@example.com"}, set(),
            {"domain_holds": {}, "domain_suppressions": {}},
        ))
        self.assertFalse(candidate._recipient_is_suppressed(
            "ok@example.com", "example.com", set(), set(),
            {"domain_holds": {}, "domain_suppressions": {}},
        ))

    def test_visible_unsubscribe_keeps_confirmation_step(self):
        token = candidate.legacy.make_unsubscribe_token("owner-test@example.com")
        page = candidate.legacy.visible_unsubscribe(token)
        body = page.body.decode("utf-8")
        self.assertIn('method="post"', body)
        self.assertIn("/unsubscribe/confirm/", body)
        self.assertIn('name="confirm" value="1"', body)


if __name__ == "__main__":
    unittest.main()
