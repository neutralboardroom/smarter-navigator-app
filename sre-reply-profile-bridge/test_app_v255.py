import copy
import json
import os
import unittest

os.environ.setdefault("FN_GROWTH_COHORT_READY", "false")
os.environ.setdefault("FN_DIRECT_OUTREACH_ENABLED", "false")
os.environ.setdefault("FN_OUTREACH_COPY_READY", "false")

import app_v255 as v255


class GrowthRuntimeV255Tests(unittest.TestCase):
    def test_sequence_is_exact_50_day_window(self):
        sequence = v255.legacy.load_direct_sequence()
        validated = v255._validate_direct_sequence_v255(sequence)
        window = validated["send_window"]
        self.assertEqual(window["start"], "08:00")
        self.assertEqual(window["end"], "18:00")
        self.assertEqual(window["minimum_minutes_between_sends"], 12)
        self.assertEqual(window["max_daily_initial_sends"], 50)

    def test_default_growth_cohort_is_fail_closed(self):
        with open(v255.GROWTH_COHORT_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        validated, prospects, certified = v255._validate_growth_cohort(data)
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
        with self.assertRaisesRegex(RuntimeError, "point_of_send_ready"):
            original = v255.FN_GROWTH_COHORT_READY
            try:
                v255.FN_GROWTH_COHORT_READY = True
                v255._validate_growth_cohort(data)
            finally:
                v255.FN_GROWTH_COHORT_READY = original

    def test_duplicate_domain_is_rejected(self):
        base = {
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
        base["prospects"] = [row, row2]
        with self.assertRaisesRegex(RuntimeError, "DUPLICATE"):
            v255._validate_growth_cohort(base)

    def test_followups_default_off(self):
        self.assertFalse(v255.FN_GROWTH_FOLLOWUPS_ENABLED)


if __name__ == "__main__":
    unittest.main()
