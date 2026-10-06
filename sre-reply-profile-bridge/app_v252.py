import re

import app_v251 as base

legacy = base.legacy
SRE_BRIDGE_RELEASE = "FN-SRE-BRIDGE-2.5.4-CANDIDATE"
legacy.SRE_BRIDGE_RELEASE = SRE_BRIDGE_RELEASE


def _normalize_copy(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    value = re.sub(r"[-–—]", " ", value)
    return re.sub(r"\s+", " ", value).strip().lower()


def _validate_direct_sequence_v252(sequence: dict):
    if not isinstance(sequence, dict):
        raise RuntimeError("DIRECT_SEQUENCE_INVALID")
    if str(sequence.get("schema") or "") != "sre.franklin.direct-outreach-sequence.v2":
        raise RuntimeError("DIRECT_SEQUENCE_SCHEMA_DRIFT")
    if str(sequence.get("campaign_id") or "") != "FN-FIRST10-2026-09":
        raise RuntimeError("DIRECT_SEQUENCE_CAMPAIGN_DRIFT")
    if str(sequence.get("sender") or "").strip() != "Roger Gillman at Franklin Navigator <community@franklinnavigator.com>":
        raise RuntimeError("DIRECT_SEQUENCE_SENDER_DRIFT")
    if str(sequence.get("owner_bcc") or "").strip().lower() != "reachrgnow@gmail.com":
        raise RuntimeError("DIRECT_SEQUENCE_OWNER_BCC_DRIFT")
    if str(sequence.get("timezone") or "") != "America/Chicago":
        raise RuntimeError("DIRECT_SEQUENCE_TIMEZONE_DRIFT")

    window = sequence.get("send_window") or {}
    if list(window.get("weekdays") or []) != ["MO", "TU", "WE", "TH", "FR"]:
        raise RuntimeError("DIRECT_SEQUENCE_WEEKDAY_DRIFT")
    if str(window.get("start") or "") != "09:00" or str(window.get("end") or "") != "16:00":
        raise RuntimeError("DIRECT_SEQUENCE_WINDOW_DRIFT")
    if int(window.get("minimum_minutes_between_sends") or 0) < 12:
        raise RuntimeError("DIRECT_SEQUENCE_SPACING_WEAKENED")
    if int(window.get("max_daily_initial_sends") or 0) > 10:
        raise RuntimeError("DIRECT_SEQUENCE_DAILY_CAP_WEAKENED")

    stop_rules = sequence.get("stop_rules") or {}
    required_stop_rules = (
        "any_reply_from_recipient",
        "any_unsubscribe",
        "any_bounce_global_pilot_hold",
        "any_spam_complaint_global_pilot_hold",
        "any_org_domain_hold_or_suppression",
        "no_followup_after_profile_correction_or_removal_request",
        "no_followup_after_claim_or_membership_if_signal_available",
        "single_reengagement_only",
        "no_automatic_recurring_reengagement",
    )
    if not all(stop_rules.get(key) is True for key in required_stop_rules):
        raise RuntimeError("DIRECT_SEQUENCE_STOP_RULE_DRIFT")

    steps = sequence.get("steps") or []
    expected_ids = ["initial", "followup_1", "followup_2", "reengagement_90d"]
    if [str(x.get("id") or "") for x in steps] != expected_ids:
        raise RuntimeError("DIRECT_SEQUENCE_STEP_DRIFT")

    expected_subjects = {
        "initial": "Your Franklin Navigator profile",
        "followup_1": "Quick follow-up on your Franklin Navigator profile",
        "followup_2": "One more note about your Franklin Navigator profile",
        "reengagement_90d": "Checking in on your Franklin Navigator profile",
    }
    expected_business_waits = {"initial": 0, "followup_1": 5, "followup_2": 7}
    forbidden_sales_phrases = (
        "$35/year",
        "coupons, specials, sales",
        "promotional flyers",
        "booking or quote links",
        "guarantee",
        "guaranteed",
        "promise",
    )

    for step in steps:
        step_id = str(step.get("id") or "")
        if str(step.get("subject") or "").strip() != expected_subjects[step_id]:
            raise RuntimeError("DIRECT_SEQUENCE_SUBJECT_DRIFT")
        body = str(step.get("body") or "")
        html_body = str(step.get("html_body") or "")
        if not body or not html_body:
            raise RuntimeError("DIRECT_SEQUENCE_CONTENT_MISSING")
        for template in (body, html_body):
            if "{{Outreach_Greeting}}" not in template or "{{Profile_URL}}" not in template:
                raise RuntimeError("DIRECT_SEQUENCE_TEMPLATE_DRIFT")
            normalized = _normalize_copy(template)
            if "optional paid community membership" not in normalized:
                raise RuntimeError("DIRECT_SEQUENCE_OPTIONAL_MEMBERSHIP_COPY_DRIFT")
            if "visibility in the franklin community" not in normalized:
                raise RuntimeError("DIRECT_SEQUENCE_VISIBILITY_COPY_DRIFT")
            for phrase in forbidden_sales_phrases:
                if phrase in normalized:
                    raise RuntimeError("DIRECT_SEQUENCE_SALES_COPY_TOO_HEAVY")

        if step_id == "initial":
            normalized = _normalize_copy(body)
            for phrase in ("i’m roger gillman", "basic profile is free", "no purchase is required", "correcting", "removed"):
                if phrase not in normalized:
                    raise RuntimeError("DIRECT_SEQUENCE_INITIAL_HUMAN_COPY_DRIFT")
            if len(normalized.split()) > 145:
                raise RuntimeError("DIRECT_SEQUENCE_INITIAL_TOO_LONG")
        elif step_id == "followup_1":
            normalized = _normalize_copy(body)
            if "basic profile is free" not in normalized or "no purchase is required" not in normalized:
                raise RuntimeError("DIRECT_SEQUENCE_FOLLOWUP1_FREE_COPY_DRIFT")
            if len(normalized.split()) > 120:
                raise RuntimeError("DIRECT_SEQUENCE_FOLLOWUP1_TOO_LONG")
        elif step_id == "followup_2":
            normalized = _normalize_copy(body)
            if "corrected or removed" not in normalized:
                raise RuntimeError("DIRECT_SEQUENCE_FOLLOWUP2_CORRECTION_COPY_DRIFT")
            if len(normalized.split()) > 110:
                raise RuntimeError("DIRECT_SEQUENCE_FOLLOWUP2_TOO_LONG")
        elif step_id == "reengagement_90d":
            normalized = _normalize_copy(body)
            if "last automatic email in this outreach sequence" not in normalized:
                raise RuntimeError("DIRECT_SEQUENCE_REENGAGEMENT_STOP_COPY_DRIFT")
            if len(normalized.split()) > 120:
                raise RuntimeError("DIRECT_SEQUENCE_REENGAGEMENT_TOO_LONG")

        if step_id in expected_business_waits:
            if int(step.get("wait_business_days_after_previous") or 0) != expected_business_waits[step_id]:
                raise RuntimeError("DIRECT_SEQUENCE_WAIT_DRIFT")
            if step.get("wait_calendar_days_after_previous") not in (None, 0):
                raise RuntimeError("DIRECT_SEQUENCE_WAIT_MODE_DRIFT")
        else:
            if int(step.get("wait_calendar_days_after_previous") or 0) != 90:
                raise RuntimeError("DIRECT_SEQUENCE_90D_WAIT_DRIFT")
            if step.get("wait_business_days_after_previous") not in (None, 0):
                raise RuntimeError("DIRECT_SEQUENCE_90D_WAIT_MODE_DRIFT")

    return sequence


legacy._validate_direct_sequence = _validate_direct_sequence_v252

_validate_direct_sequence_v252 = _validate_direct_sequence_v252
_validate_direct_sequence_v250 = _validate_direct_sequence_v252
_step_due = base._step_due
_recipient_is_suppressed = base._recipient_is_suppressed
build_franklin_message_v250 = base.build_franklin_message_v250
build_franklin_message_v251 = base.build_franklin_message_v251

app = legacy.app
