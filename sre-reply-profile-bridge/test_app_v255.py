import copy
import json
import os
import unittest

os.environ.setdefault("FN_GROWTH_COHORT_READY", "false")
os.environ.setdefault("FN_DIRECT_OUTREACH_ENABLED", "false")
os.environ.setdefault("FN_OUTREACH_COPY_READY", "false")

import app as candidate


class GrowthRuntimeV255Tests(unittest.TestCase):
    def test_production_entrypoint_activates_v255_release(self):
        self.assertEqual(candidate.SRE_BRIDGE_RELEASE, "FN-SRE-BRIDGE-2.5.5-CANDIDATE")
        self.assertIs(candidate.app, candidate.legacy.app)

    def test_sequence_is_exact_50_day_window(self):
        sequence = candidate.legacy.load_direct_sequence()
        validated = candidate._validate_direct_sequence_v255(sequence)
        window = validated["send_window"]
        self.assertEqual(window["start"], "08:00")
        self.assertEqual(window["end"], "18:00")
        self.assertEqual(window["minimum_minutes_between_sends"], 12)
        self.assertEqual(window["max_daily_initial_sends"], 50)

    def test_default_growth_cohort_is_fail_closed(self):
        active = candidate._active
        with open(active.GROWTH_COHORT_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        validated, prospects, certified = candidate._validate_growth_cohort(data)
        self.assertEqual(validated["status"], "HOLD_AWAITING_CERTIFICATION")
        self.assertEqual(prospects, [])
        self.assertFalse(certified)

    def test_certified_row_requires_all_point_of_send_gates(self):
        data = {
            "schema": "sre.franklin.growth-cohort.v1",
            "community": "FRANKLIN_TN",
            "status": "SEND_CERTIFIED",
            "certification": {
                "send_certified": True,
                "certified_count": 1,
                "suppression_rechecked": True,
                "organization_domain_guards_rechecked": True,
                "profile_claim_routes_rechecked": True,
                "first10_outcome_handling_accepted": True,
                "point_of_send_ready": False
            },
            "prospects": [{
                "email": "owner@example-business.com",
                "profileId": "FR-ORG-TEST-1",
                "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-TEST-1/",
                "outreachGreeting": "Example Business",
                "organizationGuardKey": "FR-ORG-TEST-1",
                "sendCertified": True,
                "suppressed": False,
                "held": False,
                "priorContacted": False
            }]
        }
        active = candidate._active
        original = active.FN_GROWTH_COHORT_READY
        try:
            active.FN_GROWTH_COHORT_READY = True
            with self.assertRaisesRegex(RuntimeError, "point_of_send_ready"):
                candidate._validate_growth_cohort(data)
        finally:
            active.FN_GROWTH_COHORT_READY = original

    def test_duplicate_domain_is_rejected(self):
        data = {
            "schema": "sre.franklin.growth-cohort.v1",
            "community": "FRANKLIN_TN",
            "status": "HOLD_AWAITING_CERTIFICATION",
            "certification": {"send_certified": False, "certified_count": 0},
            "prospects": []
        }
        row = {
            "email": "a@example-business.com",
            "profileId": "FR-ORG-A",
            "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-A/",
            "outreachGreeting": "A",
            "organizationGuardKey": "ORG-A",
            "sendCertified": True,
            "suppressed": False,
            "held": False,
            "priorContacted": False
        }
        row2 = copy.deepcopy(row)
        row2.update({"email": "b@example-business.com", "profileId": "FR-ORG-B", "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-B/", "organizationGuardKey": "ORG-B"})
        data["prospects"] = [row, row2]
        with self.assertRaisesRegex(RuntimeError, "DUPLICATE"):
            candidate._validate_growth_cohort(data)

    def test_copy_gate_still_forces_real_sending_off(self):
        self.assertTrue(candidate.legacy.FN_DIRECT_OUTREACH_REQUESTED)
        self.assertFalse(candidate.legacy.FN_OUTREACH_COPY_READY)
        self.assertFalse(candidate.legacy.FN_DIRECT_OUTREACH_ENABLED)

    def test_followups_default_off(self):
        self.assertFalse(candidate._active.FN_GROWTH_FOLLOWUPS_ENABLED)

    def test_personal_sender_and_unsubscribe_contract_preserved(self):
        msg = candidate.build_franklin_message_v250(
            "owner-test@example.com", "Test", "Plain body", "<p>HTML body</p>"
        )
        self.assertEqual(msg["From"], "Roger Gillman at Franklin Navigator <community@franklinnavigator.com>")
        self.assertIn("List-Unsubscribe", msg)
        self.assertEqual(msg["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        self.assertNotIn("List-ID", msg)
        self.assertNotIn("Feedback-ID", msg)


if __name__ == "__main__":
    unittest.main()
