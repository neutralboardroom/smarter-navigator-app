import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import app_v252 as base

legacy = base.legacy
SRE_BRIDGE_RELEASE = "FN-SRE-BRIDGE-2.5.5-CANDIDATE"
legacy.SRE_BRIDGE_RELEASE = SRE_BRIDGE_RELEASE

GROWTH_COHORT_PATH = legacy.os.environ.get(
    "FN_GROWTH_COHORT_PATH",
    legacy.os.path.join(legacy.os.path.dirname(__file__), "growth_cohort.json"),
).strip()
FN_GROWTH_COHORT_READY = legacy.os.environ.get("FN_GROWTH_COHORT_READY", "false").strip().lower() in {"1", "true", "yes"}
FN_GROWTH_FOLLOWUPS_ENABLED = legacy.os.environ.get("FN_GROWTH_FOLLOWUPS_ENABLED", "false").strip().lower() in {"1", "true", "yes"}

legacy.FN_GROWTH_COHORT_READY = FN_GROWTH_COHORT_READY
legacy.FN_GROWTH_FOLLOWUPS_ENABLED = FN_GROWTH_FOLLOWUPS_ENABLED
legacy._state.setdefault("directOutreach", {}).update({
    "growthCohortReady": FN_GROWTH_COHORT_READY,
    "growthFollowupsEnabled": FN_GROWTH_FOLLOWUPS_ENABLED,
    "targetNewInitialsPerBusinessDay": 50,
})

_FIRST10_SCAN_READ_ONLY = legacy._direct_scan_once


def _normalize_copy(value: str) -> str:
    return base._normalize_copy(value)


def _validate_direct_sequence_v255(sequence: dict):
    if not isinstance(sequence, dict):
        raise RuntimeError("DIRECT_SEQUENCE_INVALID")
    if str(sequence.get("schema") or "") != "sre.franklin.direct-outreach-sequence.v2":
        raise RuntimeError("DIRECT_SEQUENCE_SCHEMA_DRIFT")
    if str(sequence.get("sender") or "").strip() != "Roger Gillman at Franklin Navigator <community@franklinnavigator.com>":
        raise RuntimeError("DIRECT_SEQUENCE_SENDER_DRIFT")
    if str(sequence.get("owner_bcc") or "").strip().lower() != "reachrgnow@gmail.com":
        raise RuntimeError("DIRECT_SEQUENCE_OWNER_BCC_DRIFT")
    if str(sequence.get("timezone") or "") != "America/Chicago":
        raise RuntimeError("DIRECT_SEQUENCE_TIMEZONE_DRIFT")

    window = sequence.get("send_window") or {}
    if list(window.get("weekdays") or []) != ["MO", "TU", "WE", "TH", "FR"]:
        raise RuntimeError("DIRECT_SEQUENCE_WEEKDAY_DRIFT")
    if str(window.get("start") or "") != "08:00" or str(window.get("end") or "") != "18:00":
        raise RuntimeError("DIRECT_SEQUENCE_WINDOW_DRIFT")
    if int(window.get("minimum_minutes_between_sends") or 0) < 12:
        raise RuntimeError("DIRECT_SEQUENCE_SPACING_WEAKENED")
    if int(window.get("max_daily_initial_sends") or 0) != 50:
        raise RuntimeError("DIRECT_SEQUENCE_DAILY_TARGET_DRIFT")

    stop_rules = sequence.get("stop_rules") or {}
    required = (
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
    if not all(stop_rules.get(key) is True for key in required):
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
    expected_waits = {"initial": 0, "followup_1": 5, "followup_2": 7}
    forbidden = ("$35/year", "coupons, specials, sales", "promotional flyers", "booking or quote links", "guarantee", "guaranteed", "promise")

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
            if any(phrase in normalized for phrase in forbidden):
                raise RuntimeError("DIRECT_SEQUENCE_SALES_COPY_TOO_HEAVY")
        if step_id in expected_waits:
            if int(step.get("wait_business_days_after_previous") or 0) != expected_waits[step_id]:
                raise RuntimeError("DIRECT_SEQUENCE_WAIT_DRIFT")
        else:
            if int(step.get("wait_calendar_days_after_previous") or 0) != 90:
                raise RuntimeError("DIRECT_SEQUENCE_90D_WAIT_DRIFT")
    return sequence


def _validate_growth_cohort(data: dict):
    if not isinstance(data, dict) or str(data.get("schema") or "") != "sre.franklin.growth-cohort.v1":
        raise RuntimeError("GROWTH_COHORT_SCHEMA_INVALID")
    if str(data.get("community") or "") != "FRANKLIN_TN":
        raise RuntimeError("GROWTH_COHORT_COMMUNITY_DRIFT")
    prospects = list(data.get("prospects") or [])
    certification = data.get("certification") or {}
    certified = str(data.get("status") or "") == "SEND_CERTIFIED" and certification.get("send_certified") is True
    if certified and not FN_GROWTH_COHORT_READY:
        certified = False

    seen_emails = set()
    seen_domains = set()
    seen_profile_ids = set()
    seen_orgs = set()
    normalized = []
    for raw in prospects:
        item = dict(raw or {})
        email = str(item.get("email") or "").strip().lower()
        profile_id = str(item.get("profileId") or "").strip()
        profile_url = str(item.get("profileUrl") or "").strip()
        greeting = str(item.get("outreachGreeting") or "").strip()
        org_guard = str(item.get("organizationGuardKey") or "").strip()
        if not email or "@" not in email or not profile_id or not profile_url or not greeting or not org_guard:
            raise RuntimeError("GROWTH_COHORT_REQUIRED_FIELD_MISSING")
        domain = legacy.email_domain(email)
        if not domain:
            raise RuntimeError("GROWTH_COHORT_EMAIL_DOMAIN_INVALID")
        if email in seen_emails or profile_id in seen_profile_ids or domain in seen_domains or org_guard in seen_orgs:
            raise RuntimeError("GROWTH_COHORT_DUPLICATE_EMAIL_PROFILE_DOMAIN_OR_ORG")
        if item.get("sendCertified") is not True:
            raise RuntimeError("GROWTH_COHORT_UNCERTIFIED_ROW_PRESENT")
        if item.get("suppressed") is True or item.get("held") is True or item.get("priorContacted") is True:
            raise RuntimeError("GROWTH_COHORT_INELIGIBLE_ROW_PRESENT")
        seen_emails.add(email); seen_domains.add(domain); seen_profile_ids.add(profile_id); seen_orgs.add(org_guard)
        item["email"] = email
        normalized.append(item)

    if certified:
        if int(certification.get("certified_count") or 0) != len(normalized):
            raise RuntimeError("GROWTH_COHORT_CERTIFIED_COUNT_MISMATCH")
        for key in ("suppression_rechecked", "organization_domain_guards_rechecked", "profile_claim_routes_rechecked", "first10_outcome_handling_accepted", "point_of_send_ready"):
            if certification.get(key) is not True:
                raise RuntimeError("GROWTH_COHORT_CERTIFICATION_GATE_MISSING:" + key)
    return data, normalized, certified


def load_growth_cohort():
    with open(GROWTH_COHORT_PATH, "r", encoding="utf-8") as handle:
        return _validate_growth_cohort(json.load(handle))


def _sent_in_last_24h_for_domain(sent_records, domain: str, now_utc):
    cutoff = now_utc - timedelta(hours=24)
    for record in sent_records:
        dt = record.get("date")
        if not dt or dt.astimezone(timezone.utc) < cutoff:
            continue
        if legacy.email_domain(str(record.get("to") or "")) == domain:
            return True
    return False


def _growth_scan_once(send_if_due=False):
    checked_at = legacy.now_iso()
    sequence = legacy.load_direct_sequence()
    data, roster, certified = load_growth_cohort()
    tz = ZoneInfo(sequence.get("timezone") or "America/Chicago")
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)

    summary = {
        "release": SRE_BRIDGE_RELEASE,
        "growthCohortStatus": str(data.get("status") or ""),
        "growthCohortReadyEnv": FN_GROWTH_COHORT_READY,
        "growthCertified": certified,
        "growthRosterCount": len(roster),
        "targetNewInitialsPerBusinessDay": 50,
        "growthFollowupsEnabled": FN_GROWTH_FOLLOWUPS_ENABLED,
        "newInitialSentToday": 0,
        "nextEligibleGrowth": [],
        "growthSuppressed": [],
        "growthHeld": [],
        "growthLastSendAt": None,
        "lastCheckedAt": checked_at,
        "growthError": None,
    }
    if not certified or not roster:
        return summary

    with legacy._imap_connect() as client:
        _, records = legacy._ledger_records(client)
        sent_records = [r for r in records if r.get("status") == "SENT"]
        record_map = legacy._direct_record_map(sent_records)
        unsubscribed = legacy._zoho_suppression_set()
        domain_suppressions = legacy._zoho_domain_suppression_set()
        safety_state = legacy.load_org_safety_state()
        dated_records = [r for r in sent_records if r.get("date")]
        last_send_dt = max([r["date"] for r in dated_records], default=None)
        today = now_local.date()
        initials_today = sum(
            1 for r in dated_records
            if str(r.get("key") or "").endswith(":initial") and r["date"].astimezone(tz).date() == today
        )
        summary["newInitialSentToday"] = initials_today
        summary["growthLastSendAt"] = last_send_dt.isoformat() if last_send_dt else None

        for recipient in roster:
            email_addr = str(recipient.get("email") or "").strip().lower()
            domain = legacy.email_domain(email_addr)
            if base._recipient_is_suppressed(email_addr, domain, unsubscribed, domain_suppressions, safety_state):
                summary["growthSuppressed"].append(email_addr)
                continue
            if _sent_in_last_24h_for_domain(sent_records, domain, now_utc):
                summary["growthHeld"].append({"email": email_addr, "reason": "DOMAIN_24H_INITIAL_GUARD"})
                continue

            previous_record = None
            for index, step in enumerate(sequence.get("steps") or []):
                step_id = str(step.get("id") or "")
                key = legacy._direct_key(email_addr, step_id)
                sent_record = record_map.get(key)
                if sent_record:
                    previous_record = sent_record
                    continue

                if index == 0:
                    eligible = True
                else:
                    if not FN_GROWTH_FOLLOWUPS_ENABLED or not previous_record or not previous_record.get("date"):
                        eligible = False
                    else:
                        reply_signal = legacy._imap_reply_signal_since(client, email_addr, previous_record["date"])
                        if reply_signal:
                            if reply_signal == "org_dnc":
                                legacy._persist_zoho_domain_suppression(domain, "organization_wide_do_not_contact")
                            summary["growthHeld"].append({"email": email_addr, "reason": "REPLY_OR_DNC"})
                            break
                        problem = legacy._imap_detect_delivery_problem(client, email_addr, previous_record["date"])
                        if problem in {"bounce", "complaint"}:
                            try: legacy._persist_zoho_suppression(email_addr, problem)
                            except Exception: pass
                            summary["growthHeld"].append({"email": email_addr, "reason": problem.upper()})
                            break
                        if recipient.get("stopFollowup") is True:
                            summary["growthHeld"].append({"email": email_addr, "reason": "PRODUCT_OR_MEMBER_STOP_SIGNAL"})
                            break
                        eligible = base._step_due(step, previous_record["date"], now_utc, tz)

                if eligible:
                    summary["nextEligibleGrowth"].append({"email": email_addr, "step": step_id})
                    if not send_if_due:
                        break
                    if not legacy._within_direct_send_window(now_local, sequence):
                        break
                    min_gap = int((sequence.get("send_window") or {}).get("minimum_minutes_between_sends") or 12)
                    if last_send_dt and (now_utc - last_send_dt.astimezone(timezone.utc)).total_seconds() < min_gap * 60:
                        break
                    if step_id == "initial" and initials_today >= 50:
                        break

                    subject = str(step.get("subject") or "").strip()
                    body = legacy._render_direct_body(step.get("body") or "", recipient)
                    html_body = legacy._render_direct_body(step.get("html_body") or "", recipient)
                    profile_url = str(recipient.get("profileUrl") or "").strip()
                    if "{{" in body or "{{" in html_body or profile_url not in body or profile_url not in html_body:
                        summary["growthHeld"].append({"email": email_addr, "reason": "MESSAGE_RENDER_OR_PROFILE_LINK_ERROR"})
                        break
                    legacy._profile_url_preflight(recipient)
                    if not legacy._ledger_reserve(client, key, email_addr, subject):
                        break
                    message_id = legacy.send_franklin_smtp_message(
                        email_addr,
                        subject,
                        body,
                        html_body=html_body,
                        bcc_email=str(sequence.get("owner_bcc") or ""),
                        outreach_key=key,
                    )
                    legacy._ledger_mark_sent(client, key, email_addr, subject, message_id)
                    print("SRE_BRIDGE GROWTH_OUTREACH_SENT " + json.dumps({"email": email_addr, "step": step_id, "messageId": message_id, "at": legacy.now_iso()}, sort_keys=True), flush=True)
                    last_send_dt = datetime.now(timezone.utc)
                    now_utc = last_send_dt
                    if step_id == "initial":
                        initials_today += 1
                        summary["newInitialSentToday"] = initials_today
                    summary["growthLastSendAt"] = last_send_dt.isoformat()
                    break
    return summary


def _direct_scan_once_v255(send_if_due=False):
    # Preserve read-only reconciliation of the historical first-10 lifecycle.
    first10 = _FIRST10_SCAN_READ_ONLY(send_if_due=False)
    growth = _growth_scan_once(send_if_due=send_if_due)
    combined = dict(first10 or {})
    combined.update(growth)
    combined["enabled"] = bool(legacy.FN_DIRECT_OUTREACH_ENABLED)
    combined["requestedEnabled"] = bool(getattr(legacy, "FN_DIRECT_OUTREACH_REQUESTED", False))
    combined["outreachCopyReady"] = bool(getattr(legacy, "FN_OUTREACH_COPY_READY", False))
    with legacy._state_lock:
        legacy._state["directOutreach"].update(combined)
    return combined


legacy._validate_direct_sequence = _validate_direct_sequence_v255
legacy._direct_scan_once = _direct_scan_once_v255

_validate_direct_sequence_v255 = _validate_direct_sequence_v255
_validate_growth_cohort = _validate_growth_cohort
_growth_scan_once = _growth_scan_once

app = legacy.app
