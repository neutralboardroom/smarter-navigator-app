import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import app as legacy

SRE_BRIDGE_RELEASE = "FN-SRE-BRIDGE-2.5.0-CANDIDATE"
legacy.SRE_BRIDGE_RELEASE = SRE_BRIDGE_RELEASE
legacy._state.setdefault("directOutreach", {}).setdefault("reengagement90dSent", 0)


def _normalize_copy(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    value = re.sub(r"[-–—]", " ", value)
    return re.sub(r"\s+", " ", value).strip().lower()


def _validate_direct_sequence_v250(sequence: dict):
    if not isinstance(sequence, dict):
        raise RuntimeError("DIRECT_SEQUENCE_INVALID")
    if str(sequence.get("schema") or "") != "sre.franklin.direct-outreach-sequence.v2":
        raise RuntimeError("DIRECT_SEQUENCE_SCHEMA_DRIFT")
    if str(sequence.get("campaign_id") or "") != "FN-FIRST10-2026-09":
        raise RuntimeError("DIRECT_SEQUENCE_CAMPAIGN_DRIFT")
    if str(sequence.get("sender") or "").strip() != "Franklin Navigator Community Team <community@franklinnavigator.com>":
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
    step_ids = [str(x.get("id") or "") for x in steps]
    expected_ids = ["initial", "followup_1", "followup_2", "reengagement_90d"]
    if step_ids != expected_ids:
        raise RuntimeError("DIRECT_SEQUENCE_STEP_DRIFT")

    expected_subjects = {
        "initial": "Your Franklin Navigator business profile",
        "followup_1": "A quick follow-up on your Franklin Navigator profile",
        "followup_2": "One more note about your Franklin Navigator profile",
        "reengagement_90d": "Checking in on your Franklin Navigator profile",
    }
    expected_business_waits = {"initial": 0, "followup_1": 5, "followup_2": 7}

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
            for phrase in (
                "no purchase is required",
                "$35/year",
                "commercial community outreach email from franklin navigator",
            ):
                if phrase not in normalized:
                    raise RuntimeError("DIRECT_SEQUENCE_REQUIRED_COPY_DRIFT")
            if "profile removal" not in normalized:
                raise RuntimeError("DIRECT_SEQUENCE_FREE_REMOVAL_COPY_DRIFT")
        if step_id in expected_business_waits:
            if int(step.get("wait_business_days_after_previous") or 0) != expected_business_waits[step_id]:
                raise RuntimeError("DIRECT_SEQUENCE_WAIT_DRIFT")
            if step.get("wait_calendar_days_after_previous") not in (None, 0):
                raise RuntimeError("DIRECT_SEQUENCE_WAIT_MODE_DRIFT")
        elif step_id == "reengagement_90d":
            if int(step.get("wait_calendar_days_after_previous") or 0) != 90:
                raise RuntimeError("DIRECT_SEQUENCE_90D_WAIT_DRIFT")
            if step.get("wait_business_days_after_previous") not in (None, 0):
                raise RuntimeError("DIRECT_SEQUENCE_90D_WAIT_MODE_DRIFT")
            normalized = _normalize_copy(body)
            if "last automatic message in this outreach sequence" not in normalized:
                raise RuntimeError("DIRECT_SEQUENCE_REENGAGEMENT_STOP_COPY_DRIFT")
    return sequence


def build_franklin_message_v250(to_email: str, subject: str, plain_body: str, html_body: str = ""):
    token = legacy.make_unsubscribe_token(to_email)
    one_click_url = f"{legacy.FN_OUTREACH_PUBLIC_BASE_URL}/unsubscribe/one-click/{token}"
    visible_url = f"{legacy.FN_OUTREACH_PUBLIC_BASE_URL}/unsubscribe/{token}"
    msg = legacy.EmailMessage(policy=legacy.email_policy.SMTP.clone(max_line_length=998))
    msg["From"] = f"Franklin Navigator Community Team <{legacy.FN_OUTREACH_SMTP_USER}>"
    msg["To"] = to_email
    msg["Reply-To"] = legacy.FN_OUTREACH_SMTP_USER
    msg["Subject"] = subject
    msg["Date"] = legacy.formatdate(localtime=True)
    msg["Message-ID"] = legacy.make_msgid(domain="franklinnavigator.com")
    msg["List-ID"] = f"<{legacy.FN_OUTREACH_LIST_ID}>"
    msg["List-Unsubscribe"] = f"<{one_click_url}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg["Feedback-ID"] = f"first10:profile:outreach:{legacy.FN_FEEDBACK_SENDER_ID}"

    footer_text = (
        "\n\nThis is a Franklin Navigator community outreach email.\n\n"
        "Franklin Navigator Community Team\n"
        "Franklin Navigator\n"
        "community@franklinnavigator.com\n"
        "(615) 656-7020\n"
        "franklinnavigator.com\n\n"
        f"UNSUBSCRIBE: {visible_url}\n\n"
        "2020 Fieldstone Pkwy, Ste 900, Franklin, TN 37069"
    )
    msg.set_content(str(plain_body or "").rstrip() + footer_text)

    if html_body:
        footer_html = (
            '<div style="margin-top:24px;">This is a Franklin Navigator community outreach email.</div>'
            '<div style="margin-top:20px;">Franklin Navigator Community Team<br>'
            'Franklin Navigator<br>'
            'community@franklinnavigator.com<br>'
            '(615) 656-7020<br>'
            'franklinnavigator.com</div>'
            '<div style="margin-top:24px;margin-bottom:24px;line-height:1.5;">'
            f'<a href="{visible_url}" style="font-size:16px;font-weight:700;">Unsubscribe</a>'
            '</div>'
            '<div>2020 Fieldstone Pkwy, Ste 900, Franklin, TN 37069</div>'
        )
        msg.add_alternative(str(html_body).rstrip() + footer_html, subtype="html")
    return msg


def _recipient_is_suppressed(email_addr: str, domain: str, unsubscribed, domain_suppressions, safety_state: dict) -> bool:
    if email_addr in set(unsubscribed or set()):
        return True
    if domain in set(domain_suppressions or set()):
        return True
    if domain in (safety_state.get("domain_holds") or {}):
        return True
    if domain in (safety_state.get("domain_suppressions") or {}):
        return True
    return False


def _step_due(step: dict, previous_dt, now_utc, tz) -> bool:
    calendar_days = int(step.get("wait_calendar_days_after_previous") or 0)
    if calendar_days:
        previous_date = previous_dt.astimezone(tz).date()
        current_date = now_utc.astimezone(tz).date()
        return (current_date - previous_date).days >= calendar_days
    business_days = int(step.get("wait_business_days_after_previous") or 0)
    return legacy._business_days_between(previous_dt, now_utc, tz) >= business_days


def _direct_scan_once_v250(send_if_due=False):
    checked_at = legacy.now_iso()
    sequence = legacy.load_direct_sequence()
    tz = ZoneInfo(sequence.get("timezone") or "America/Chicago")
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)
    alerts = []

    with legacy._imap_connect() as client:
        sent_mailbox, records = legacy._ledger_records(client)
        for seed_email, seed_iso in legacy.FIRST10_INCIDENT_SEEDED_SENT_AT.items():
            seed_key = legacy._direct_key(seed_email, "initial")
            if not any(r.get("key") == seed_key and r.get("status") == "SENT" for r in records):
                records.append({"key": seed_key, "status": "SENT", "to": seed_email, "subject": "Your Franklin Navigator business profile", "messageId": "INCIDENT-SEED", "date": datetime.fromisoformat(seed_iso)})

        sent_records = [r for r in records if r.get("status") == "SENT"]
        record_map = legacy._direct_record_map(sent_records)
        sent_keys = {str(r.get("key") or "") for r in sent_records if r.get("key")}
        reserved_without_sent = sorted({str(r.get("key") or "") for r in records if r.get("status") == "RESERVED" and r.get("key") and str(r.get("key") or "") not in sent_keys})

        unsubscribed = legacy._zoho_suppression_set()
        zoho_domain_suppressions = legacy._zoho_domain_suppression_set()
        suppressed = []
        bounce_holds = []
        complaint_holds = []
        stopped_replies = []
        next_eligible = []
        initial_sent = followup1_sent = followup2_sent = reengagement90d_sent = 0

        roster_emails = {str(x.get("email") or "").strip().lower() for x in legacy.FIRST10_CONTACT_ROSTER}
        pilot_unsubs = sorted(roster_emails & unsubscribed)
        global_hold = f"PILOT_UNSUBSCRIBE:{pilot_unsubs[0]}" if pilot_unsubs else None

        if reserved_without_sent:
            global_hold = global_hold or f"AMBIGUOUS_SEND_RESERVATION:{reserved_without_sent[0]}"
            alerts.append({"priority": "HIGH", "triggerType": "AMBIGUOUS_SEND_RESERVATION", "outreachKey": reserved_without_sent[0], "automaticAction": "DIRECT_OUTREACH_HOLD"})

        expected_initial_keys = {legacy._direct_key(str(x.get("email") or "").strip().lower(), "initial") for x in legacy.FIRST10_CONTACT_ROSTER}
        missing_closed_initial_keys = sorted(expected_initial_keys - set(record_map.keys()))
        if legacy.FN_INITIAL_COHORT_CLOSED and missing_closed_initial_keys:
            global_hold = global_hold or "INITIAL_COHORT_CLOSED_LEDGER_MISMATCH"
            alerts.append({"priority": "HIGH", "triggerType": "INITIAL_COHORT_CLOSED_LEDGER_MISMATCH", "missingCount": len(missing_closed_initial_keys), "automaticAction": "DIRECT_OUTREACH_HOLD"})

        dated_records = [r for r in sent_records if r.get("date")]
        last_send_dt = max([r["date"] for r in dated_records], default=None)
        today = now_local.date()
        sends_today = sum(1 for r in dated_records if r["date"].astimezone(tz).date() == today)

        for recipient in legacy.FIRST10_CONTACT_ROSTER:
            email_addr = str(recipient.get("email") or "").strip().lower()
            domain = legacy.email_domain(email_addr)
            safety_state = legacy.load_org_safety_state()
            if _recipient_is_suppressed(email_addr, domain, unsubscribed, zoho_domain_suppressions, safety_state):
                suppressed.append(email_addr)
                continue

            previous_record = None
            for index, step in enumerate(sequence.get("steps") or []):
                step_id = str(step.get("id") or "")
                key = legacy._direct_key(email_addr, step_id)
                if email_addr in legacy.FIRST10_INCIDENT_NO_FOLLOWUP_EMAILS and step_id != "initial":
                    break

                sent_record = record_map.get(key)
                if sent_record:
                    if step_id == "initial": initial_sent += 1
                    elif step_id == "followup_1": followup1_sent += 1
                    elif step_id == "followup_2": followup2_sent += 1
                    elif step_id == "reengagement_90d": reengagement90d_sent += 1
                    previous_record = sent_record
                    continue

                if index == 0:
                    eligible = not legacy.FN_INITIAL_COHORT_CLOSED
                else:
                    if not previous_record or not previous_record.get("date"):
                        eligible = False
                    else:
                        reply_signal = legacy._imap_reply_signal_since(client, email_addr, previous_record["date"])
                        if reply_signal:
                            stopped_replies.append(email_addr)
                            if reply_signal == "org_dnc":
                                legacy._persist_zoho_domain_suppression(domain, "organization_wide_do_not_contact")
                                global_hold = global_hold or f"ORGANIZATION_WIDE_DNC:{domain}"
                                alerts.append({"priority": "HIGH", "triggerType": "ORGANIZATION_WIDE_DO_NOT_CONTACT", "domain": domain, "email": email_addr, "automaticAction": "DOMAIN_SUPPRESSION_AND_DIRECT_OUTREACH_HOLD"})
                            eligible = False
                            break

                        problem = legacy._imap_detect_delivery_problem(client, email_addr, previous_record["date"])
                        if problem == "bounce":
                            bounce_holds.append(email_addr)
                            try: legacy._persist_zoho_suppression(email_addr, "bounce")
                            except Exception: pass
                            global_hold = global_hold or f"PILOT_BOUNCE:{email_addr}"
                            alerts.append({"priority": "HIGH", "triggerType": "BOUNCE", "email": email_addr, "automaticAction": "RECIPIENT_SUPPRESSION_AND_DIRECT_OUTREACH_HOLD"})
                            eligible = False
                            break
                        if problem == "complaint":
                            complaint_holds.append(email_addr)
                            try: legacy._persist_zoho_suppression(email_addr, "complaint")
                            except Exception: pass
                            global_hold = global_hold or f"PILOT_COMPLAINT:{email_addr}"
                            alerts.append({"priority": "HIGH", "triggerType": "SPAM_COMPLAINT", "email": email_addr, "domain": domain, "automaticAction": "RECIPIENT_SUPPRESSION_AND_DIRECT_OUTREACH_HOLD"})
                            eligible = False
                            break

                        if not legacy.FN_INITIAL_COHORT_CLOSED:
                            global_hold = global_hold or "FOLLOWUP_REQUIRES_INITIAL_COHORT_CLOSED"
                            alerts.append({"priority": "HIGH", "triggerType": "FOLLOWUP_REQUIRES_INITIAL_COHORT_CLOSED", "email": email_addr, "step": step_id, "automaticAction": "DIRECT_OUTREACH_HOLD"})
                            eligible = False
                        else:
                            eligible = _step_due(step, previous_record["date"], now_utc, tz)

                if eligible:
                    next_eligible.append({"email": email_addr, "step": step_id})
                    initial_override = legacy.FN_INITIAL_SEND_OVERRIDE and step_id == "initial"
                    if send_if_due and not global_hold and (legacy._within_direct_send_window(now_local, sequence) or initial_override):
                        min_gap = int((sequence.get("send_window") or {}).get("minimum_minutes_between_sends") or 12)
                        if last_send_dt and (now_utc - last_send_dt.astimezone(timezone.utc)).total_seconds() < min_gap * 60: break
                        max_daily = int((sequence.get("send_window") or {}).get("max_daily_initial_sends") or 10)
                        if sends_today >= max_daily: break

                        subject = str(step.get("subject") or "").strip()
                        body = legacy._render_direct_body(step.get("body") or "", recipient)
                        html_body = legacy._render_direct_body(step.get("html_body") or "", recipient)
                        profile_url = str(recipient.get("profileUrl") or "").strip()
                        if "{{" in body or "{{" in html_body:
                            global_hold = global_hold or f"RENDER_PLACEHOLDER_ERROR:{email_addr}"
                            alerts.append({"priority": "HIGH", "triggerType": "MESSAGE_RENDER_ERROR", "email": email_addr})
                            break
                        if profile_url not in body or profile_url not in html_body:
                            global_hold = global_hold or f"PROFILE_LINK_RENDER_ERROR:{email_addr}"
                            alerts.append({"priority": "HIGH", "triggerType": "PROFILE_LINK_RENDER_ERROR", "email": email_addr})
                            break
                        try: legacy._profile_url_preflight(recipient)
                        except Exception as exc:
                            global_hold = global_hold or f"PROFILE_URL_PREFLIGHT_FAIL:{email_addr}"
                            alerts.append({"priority": "HIGH", "triggerType": "PROFILE_URL_PREFLIGHT_FAIL", "email": email_addr, "error": str(exc)})
                            break
                        if not legacy._ledger_reserve(client, key, email_addr, subject): break
                        message_id = legacy.send_franklin_smtp_message(email_addr, subject, body, html_body=html_body, bcc_email=str(sequence.get("owner_bcc") or ""), outreach_key=key)
                        legacy._ledger_mark_sent(client, key, email_addr, subject, message_id)
                        print("SRE_BRIDGE DIRECT_OUTREACH_SENT " + json.dumps({"email": email_addr, "step": step_id, "messageId": message_id, "at": legacy.now_iso()}, sort_keys=True), flush=True)
                        last_send_dt = datetime.now(timezone.utc)
                        now_utc = last_send_dt
                        sends_today += 1
                    break

        summary = {
            "enabled": legacy.FN_DIRECT_OUTREACH_ENABLED,
            "lastCheckedAt": checked_at,
            "sentMailbox": sent_mailbox,
            "imapConnection": "PASS",
            "campaignId": sequence.get("campaign_id"),
            "release": SRE_BRIDGE_RELEASE,
            "configurationFingerprint": legacy._direct_config_fingerprint(sequence),
            "rosterCount": len(legacy.FIRST10_CONTACT_ROSTER),
            "ownerBcc": str(sequence.get("owner_bcc") or ""),
            "initialCohortClosed": legacy.FN_INITIAL_COHORT_CLOSED,
            "pilotInitialComplete": initial_sent == len(legacy.FIRST10_CONTACT_ROSTER),
            "reservedWithoutSent": reserved_without_sent,
            "initialSent": initial_sent,
            "followup1Sent": followup1_sent,
            "followup2Sent": followup2_sent,
            "reengagement90dSent": reengagement90d_sent,
            "stoppedForReply": sorted(set(stopped_replies)),
            "suppressed": sorted(set(suppressed)),
            "bounceHolds": sorted(set(bounce_holds)),
            "complaintHolds": sorted(set(complaint_holds)),
            "ownerAlerts": alerts,
            "globalHold": global_hold,
            "nextEligible": next_eligible[:20],
            "lastSendAt": last_send_dt.isoformat() if last_send_dt else None,
            "error": None,
        }
        with legacy._state_lock:
            legacy._state["directOutreach"].update(summary)
        return summary


if not callable(getattr(legacy, "persist_unsubscribe", None)):
    raise RuntimeError("UNSUBSCRIBE_PERSISTENCE_CONTRACT_MISSING")
if not callable(getattr(legacy, "_zoho_suppression_set", None)):
    raise RuntimeError("UNSUBSCRIBE_SUPPRESSION_READ_CONTRACT_MISSING")

legacy._validate_direct_sequence = _validate_direct_sequence_v250
legacy.build_franklin_message = build_franklin_message_v250
legacy._direct_scan_once = _direct_scan_once_v250

app = legacy.app
