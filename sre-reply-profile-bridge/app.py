import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request

API_BASE = "https://api.reply.io/v3"
REPLY_API_KEY = os.environ.get("REPLY_API_KEY", "").strip()
MAILSHAKE_API_BASE = "https://api.mailshake.com/2017-04-01"
MAILSHAKE_API_KEY = os.environ.get("MAILSHAKE_API_KEY", "").strip()
MAILSHAKE_CAMPAIGN_ID = int(os.environ.get("MAILSHAKE_CAMPAIGN_ID", "0") or 0)
MAILSHAKE_MONITOR_INTERVAL_SECONDS = int(os.environ.get("MAILSHAKE_MONITOR_INTERVAL_SECONDS", "900"))
REPLY_SYNC_ENABLED = os.environ.get("REPLY_SYNC_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
MAILSHAKE_PUSH_SECRET = os.environ.get("MAILSHAKE_PUSH_SECRET", "").strip()
MAILSHAKE_PUBLIC_BASE_URL = os.environ.get("MAILSHAKE_PUBLIC_BASE_URL", "https://sre-reply-profile-bridge.onrender.com").rstrip("/")
MAILSHAKE_PUSH_SETUP_ON_STARTUP = os.environ.get("MAILSHAKE_PUSH_SETUP_ON_STARTUP", "false").strip().lower() in {"1", "true", "yes"}
MAILSHAKE_COMPLIANCE_HOLD = os.environ.get("MAILSHAKE_COMPLIANCE_HOLD", "true").strip().lower() in {"1", "true", "yes"}
DELIVERABILITY_POLICY_PATH = os.path.join(os.path.dirname(__file__), "roger_deliverability_policy.json")
SEQUENCE_ID = int(os.environ.get("REPLY_SEQUENCE_ID", "1768444"))
SYNC_INTERVAL_SECONDS = int(os.environ.get("SYNC_INTERVAL_SECONDS", "900"))
FIRST10_PROVISION_ON_STARTUP = os.environ.get("FIRST10_PROVISION_ON_STARTUP", "").strip().lower() in {"1", "true", "yes"}
FIRST10_PILOT_SEQUENCE_NAME = "Franklin Navigator — First 10 Pilot — First Touch Only — 2026-09-20"
FIRST10_PILOT_SCHEDULE_ID = 563862
FIRST10_PILOT_EMAIL_ACCOUNT_ID = 954440
FIRST10_STAGE_FIELDS_ON_STARTUP = os.environ.get("FIRST10_STAGE_FIELDS_ON_STARTUP", "").strip().lower() in {"1", "true", "yes"}
FIRST10_DOMAIN_HEALTH_PROBE_ON_STARTUP = os.environ.get("FIRST10_DOMAIN_HEALTH_PROBE_ON_STARTUP", "").strip().lower() in {"1", "true", "yes"}
FIRST10_PILOT_SEQUENCE_ID = 1776919
FIRST10_CONTACT_ROSTER = [
    {"contactId": 762750302, "email": "catering@littlehatsmarket.com", "business": "Little Hats Italian Market (Cool Springs)", "outreachGreeting": "Little Hats Italian Market", "profileId": "FR-ORG-17d04eafd603-little-hats-italian-market-cool-springs", "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-17d04eafd603-little-hats-italian-market-cool-springs/"},
    {"contactId": 762750303, "email": "chowell@healthmarkets.com", "business": "Chris Howell Insurance", "outreachGreeting": "Chris Howell Insurance", "profileId": "FR-ORG-3e820e6c84e2-chris-howell-insurance", "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-3e820e6c84e2-chris-howell-insurance/"},
    {"contactId": 762750304, "email": "events@daddysdogs.com", "business": "Daddy's Dogs", "outreachGreeting": "Daddy's Dogs", "profileId": "FR-ORG-305366afb36e-daddy-s-dogs", "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-305366afb36e-daddy-s-dogs/"},
    {"contactId": 762750305, "email": "firm@buscherlaw.com", "business": "Buscher Law LLC - Franklin, TN", "outreachGreeting": "Buscher Law", "profileId": "FR-ORG-61c3753cb5af085e", "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-61c3753cb5af085e/"},
    {"contactId": 762750306, "email": "franklin@mlrose.com", "business": "M.L. Rose Craft Beer & Burgers", "outreachGreeting": "M.L. Rose Franklin", "profileId": "FR-ORG-f6a218bfcaea-m-l-rose-craft-beer-and-burgers", "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-f6a218bfcaea-m-l-rose-craft-beer-and-burgers/"},
    {"contactId": 762750307, "email": "info@615blinds.com", "business": "615 Blinds", "outreachGreeting": "615 Blinds", "profileId": "FR-ORG-f7f66777334f-615-blinds", "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-f7f66777334f-615-blinds/"},
    {"contactId": 762750308, "email": "info@bartoninsurancegroupllc.com", "business": "Barton Insurance Group", "outreachGreeting": "Barton Insurance Group", "profileId": "FR-ORG-259647dc9d6a-barton-insurance-group", "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-259647dc9d6a-barton-insurance-group/"},
    {"contactId": 762750309, "email": "info@bentonwhite.com", "business": "Benton White Insurance", "outreachGreeting": "Benton White Insurance", "profileId": "FR-ORG-0b0ca869c9ebe059", "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-0b0ca869c9ebe059/"},
    {"contactId": 762750310, "email": "info@carriagehillinsurance.com", "business": "Carriage Hill Insurance & Risk Management", "outreachGreeting": "Carriage Hill Insurance", "profileId": "FR-ORG-6bce3aef91e8cc79", "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-6bce3aef91e8cc79/"},
    {"contactId": 762750311, "email": "jen@bravemaggiedesigns.com", "business": "Brave Maggie Designs", "outreachGreeting": "Brave Maggie Designs", "profileId": "FR-ORG-58abf804cb86-brave-maggie-designs", "profileUrl": "https://franklinnavigator.com/profiles/FR-ORG-58abf804cb86-brave-maggie-designs/"}
]
# The managed prospect roster is source-controlled with this bridge.
# Do not allow a stale Render environment override to silently pin an older cohort.
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "prospects.json")
CAMPAIGN_COPY_PATH = os.environ.get(
    "CAMPAIGN_COPY_PATH",
    os.path.join(os.path.dirname(__file__), "campaign_copy.json"),
)

OWNER_TEST_ON_STARTUP = os.environ.get("OWNER_TEST_ON_STARTUP", "").strip().lower() in {
    "1",
    "true",
    "yes",
}
OWNER_TEST_CONTACT_ID = int(os.environ.get("OWNER_TEST_CONTACT_ID", "0") or 0)
OWNER_TEST_EMAIL_ACCOUNT_ID = int(os.environ.get("OWNER_TEST_EMAIL_ACCOUNT_ID", "0") or 0)
OWNER_TEST_SUBJECT = os.environ.get("OWNER_TEST_SUBJECT", "").strip()
OWNER_TEST_BODY = os.environ.get("OWNER_TEST_BODY", "")

PROFILE_FIELD_ID = 150607
PROFILE_ID_FIELD_ID = 151134
GREETING_FIELD_ID = 151137
LINK_STATE_FIELD_ID = 151138

PROFILE_FIELD = "Profile URL"
PROFILE_ID_FIELD = "Franklin Profile ID"
GREETING_FIELD = "Outreach Greeting"
LINK_STATE_FIELD = "Franklin Profile Link State"

GENERIC_FRANKLIN_PATHS = {
    "/business-membership/",
    "/membership-start/",
    "/membership-enroll/",
    "/claim-profile/",
    "/directory/",
    "/",
}

app = FastAPI(title="SRE Outreach Provider Bridge", version="1.6.0")
_state_lock = threading.Lock()
_state = {
    "lastRunAt": None,
    "lastOutcome": "NOT_RUN",
    "sequenceId": SEQUENCE_ID,
    "processed": 0,
    "ready": 0,
    "held": [],
    "replacementNeeded": 0,
    "templateUpdated": False,
    "campaignCopyVersion": None,
    "error": None,
    "activation": {"attempted": False, "added": [], "notProcessed": None, "error": None},
    "mailshake": {
        "configured": bool(MAILSHAKE_API_KEY),
        "connection": "NOT_TESTED" if MAILSHAKE_API_KEY else "NOT_CONFIGURED",
        "lastCheckedAt": None,
        "error": None,
        "campaignId": MAILSHAKE_CAMPAIGN_ID or None,
        "campaignTitle": None,
        "campaignPaused": None,
        "lastPollAt": None,
        "rosterExact": None,
        "recipientCount": 0,
        "sentCount": 0,
        "replyCount": 0,
        "bounceCount": 0,
        "unsubscribeCount": 0,
        "outOfOfficeCount": 0,
        "delayNotificationCount": 0,
        "problem": None,
        "pushSubscriptions": {},
        "lastPushAt": None,
        "lastPushEvent": None,
    },
    "ownerTest": {
        "enabled": OWNER_TEST_ON_STARTUP,
        "status": "NOT_REQUESTED" if not OWNER_TEST_ON_STARTUP else "PENDING",
        "sentAt": None,
        "messageId": None,
        "error": None,
    },
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def auth_headers():
    if not REPLY_API_KEY:
        raise RuntimeError("REPLY_API_KEY is not configured")
    return {
        "Authorization": f"Bearer {REPLY_API_KEY}",
        "X-API-Key": REPLY_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def api(method, path, **kwargs):
    response = requests.request(
        method,
        API_BASE + path,
        headers=auth_headers(),
        timeout=30,
        **kwargs,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Reply API {method} {path} -> {response.status_code}: {response.text[:800]}"
        )
    if not response.content:
        return None
    return response.json()


def mailshake_api(method, path, **kwargs):
    if not MAILSHAKE_API_KEY:
        raise RuntimeError("MAILSHAKE_API_KEY is not configured")
    response = requests.request(
        method,
        MAILSHAKE_API_BASE + path,
        auth=(MAILSHAKE_API_KEY, ""),
        timeout=30,
        **kwargs,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Mailshake API {method} {path} -> {response.status_code}: {response.text[:500]}"
        )
    if not response.content:
        return None
    return response.json()


def test_mailshake_connection():
    checked_at = now_iso()
    if not MAILSHAKE_API_KEY:
        with _state_lock:
            _state["mailshake"].update(
                {
                    "configured": False,
                    "connection": "NOT_CONFIGURED",
                    "lastCheckedAt": checked_at,
                    "error": None,
                }
            )
        return False

    try:
        result = mailshake_api("GET", "/me") or {}
        if not result.get("user"):
            raise RuntimeError("MAILSHAKE_ME_RESPONSE_MISSING_USER")
        with _state_lock:
            _state["mailshake"].update(
                {
                    "configured": True,
                    "connection": "PASS",
                    "lastCheckedAt": checked_at,
                    "error": None,
                }
            )
        print("SRE_BRIDGE MAILSHAKE_CONNECTION PASS", flush=True)
        return True
    except Exception as exc:
        error = str(exc)
        with _state_lock:
            _state["mailshake"].update(
                {
                    "configured": True,
                    "connection": "FAIL",
                    "lastCheckedAt": checked_at,
                    "error": error,
                }
            )
        print(f"SRE_BRIDGE MAILSHAKE_CONNECTION FAIL {error}", flush=True)
        return False




def load_deliverability_policy():
    with open(DELIVERABILITY_POLICY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def policy_pause_reason(sent_count, bounce_count, unsubscribe_count, roster_exact, campaign):
    policy = load_deliverability_policy()
    current = policy.get("current_pilot") or {}
    if MAILSHAKE_COMPLIANCE_HOLD:
        return "COMPLIANCE_FOOTER_AND_UNSUBSCRIBE_CONFIRMATION_REQUIRED"
    if not roster_exact:
        return "ROSTER_OR_PROFILE_BINDING_MISMATCH"
    if int(current.get("max_messages_per_sequence") or 1) == 1:
        messages = campaign.get("messages") or []
        if len(messages) != 1:
            return "UNEXPECTED_SEQUENCE_MESSAGE_COUNT"
    sender = campaign.get("sender") or {}
    sender_email = str(sender.get("emailAddress") or "").strip().lower()
    if sender_email and sender_email != "community@franklinnavigator.com":
        return "UNEXPECTED_SENDER_MAILBOX"
    if bool(current.get("pause_on_any_bounce")) and bounce_count > 0:
        return "PILOT_BOUNCE_DETECTED"
    if bool(current.get("pause_on_any_unsubscribe")) and unsubscribe_count > 0:
        return "PILOT_UNSUBSCRIBE_DETECTED"
    max_total = int(current.get("max_total_sends") or 10)
    if sent_count >= max_total and not bool(campaign.get("isPaused")):
        return "FIRST_10_COMPLETE_LOCK_CLOSED"
    return None


def mailshake_fetch_resource(resource_url):
    if not resource_url or not str(resource_url).startswith(MAILSHAKE_API_BASE + "/"):
        raise RuntimeError("MAILSHAKE_PUSH_RESOURCE_URL_REJECTED")
    response = requests.get(
        resource_url,
        auth=(MAILSHAKE_API_KEY, ""),
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Mailshake push resource -> {response.status_code}: {response.text[:500]}"
        )
    return response.json() if response.content else {}


def setup_mailshake_pushes_once():
    if not MAILSHAKE_API_KEY or MAILSHAKE_CAMPAIGN_ID <= 0 or not MAILSHAKE_PUSH_SECRET:
        return
    results = {}
    for event_name in ("MessageSent", "Replied"):
        target = (
            f"{MAILSHAKE_PUBLIC_BASE_URL}/mailshake/push/"
            f"{MAILSHAKE_PUSH_SECRET}/{event_name.lower()}"
        )
        try:
            try:
                mailshake_api(
                    "POST",
                    "/push/delete",
                    data={"targetUrl": target},
                )
            except Exception:
                pass
            mailshake_api(
                "POST",
                "/push/create",
                json={
                    "event": event_name,
                    "targetUrl": target,
                    "filter": {"campaignID": MAILSHAKE_CAMPAIGN_ID},
                },
            )
            results[event_name] = "ACTIVE"
            print(f"SRE_BRIDGE MAILSHAKE_PUSH {event_name} ACTIVE", flush=True)
        except Exception as exc:
            results[event_name] = f"ERROR:{str(exc)[:200]}"
            print(f"SRE_BRIDGE MAILSHAKE_PUSH {event_name} ERROR {exc}", flush=True)
    with _state_lock:
        _state["mailshake"]["pushSubscriptions"] = results


def mailshake_paginated(path, params=None, per_page=100, max_pages=10):
    params = dict(params or {})
    params["perPage"] = min(int(per_page), 100)
    results = []
    next_token = None
    for _ in range(max_pages):
        page_params = dict(params)
        if next_token:
            page_params["nextToken"] = next_token
        page = mailshake_api("GET", path, params=page_params) or {}
        results.extend(page.get("results") or [])
        next_token = page.get("nextToken")
        if not next_token:
            break
    return results


def mailshake_monitor_once():
    checked_at = now_iso()
    if not MAILSHAKE_API_KEY:
        raise RuntimeError("MAILSHAKE_API_KEY is not configured")
    if MAILSHAKE_CAMPAIGN_ID <= 0:
        raise RuntimeError("MAILSHAKE_CAMPAIGN_ID is not configured")

    campaign = mailshake_api(
        "GET",
        "/campaigns/get",
        params={"campaignID": MAILSHAKE_CAMPAIGN_ID},
    ) or {}

    recipients = mailshake_paginated(
        "/recipients/list",
        {"campaignID": MAILSHAKE_CAMPAIGN_ID},
        per_page=100,
    )
    sent = mailshake_paginated(
        "/activity/sent",
        {
            "campaignID": MAILSHAKE_CAMPAIGN_ID,
            "excludeBody": "true",
        },
        per_page=25,
    )
    replies = mailshake_paginated(
        "/activity/replies",
        {"campaignID": MAILSHAKE_CAMPAIGN_ID},
        per_page=25,
    )

    expected_by_email = {
        item["email"].strip().lower(): item for item in FIRST10_CONTACT_ROSTER
    }
    actual_by_email = {
        str(item.get("emailAddress") or "").strip().lower(): item
        for item in recipients
        if str(item.get("emailAddress") or "").strip()
    }
    missing = sorted(set(expected_by_email) - set(actual_by_email))
    unexpected = sorted(set(actual_by_email) - set(expected_by_email))

    field_mismatches = []
    for email, expected in expected_by_email.items():
        actual = actual_by_email.get(email)
        if not actual:
            continue
        fields = actual.get("fields") or {}
        fields_ci = {str(key).strip().lower(): value for key, value in fields.items()}
        expected_fields = {
            "outreach_greeting": expected["outreachGreeting"],
            "profile_url": expected["profileUrl"],
            "franklin_profile_id": expected["profileId"],
            "outreach_state": "READY_EXACT_PROFILE_BOUND_FIRST_TOUCH_ONLY",
        }
        for key, value in expected_fields.items():
            if str(fields_ci.get(key) or "").strip() != str(value).strip():
                field_mismatches.append({"field": key, "email": email})

    reply_types = [str(item.get("type") or "").strip().lower() for item in replies]
    roster_exact = (
        len(recipients) == 10
        and not missing
        and not unexpected
        and not field_mismatches
    )
    sent_count = len(sent)
    bounce_count = sum(1 for value in reply_types if value == "bounce")
    unsubscribe_count = sum(1 for value in reply_types if value == "unsubscribe")
    safety_pause_reason = policy_pause_reason(
        sent_count,
        bounce_count,
        unsubscribe_count,
        roster_exact,
        campaign,
    )

    if safety_pause_reason and not bool(campaign.get("isPaused")):
        try:
            mailshake_api(
                "POST",
                "/campaigns/pause",
                data={"campaignID": MAILSHAKE_CAMPAIGN_ID},
            )
            campaign["isPaused"] = True
            print(
                f"SRE_BRIDGE MAILSHAKE_SAFETY_PAUSE reason={safety_pause_reason}",
                flush=True,
            )
        except Exception as exc:
            print(
                f"SRE_BRIDGE MAILSHAKE_SAFETY_PAUSE ERROR reason={safety_pause_reason} error={exc}",
                flush=True,
            )

    summary = {
        "campaignId": MAILSHAKE_CAMPAIGN_ID,
        "campaignTitle": campaign.get("title"),
        "campaignPaused": campaign.get("isPaused"),
        "lastPollAt": checked_at,
        "rosterExact": roster_exact,
        "recipientCount": len(recipients),
        "sentCount": sent_count,
        "replyCount": sum(1 for value in reply_types if value == "reply"),
        "bounceCount": bounce_count,
        "unsubscribeCount": unsubscribe_count,
        "outOfOfficeCount": sum(1 for value in reply_types if value == "out-of-office"),
        "delayNotificationCount": sum(1 for value in reply_types if value == "delay-notification"),
        "safetyPauseReason": safety_pause_reason if bool(campaign.get("isPaused")) else None,
        "problem": None if (not missing and not unexpected and not field_mismatches) else {
            "missingRecipientCount": len(missing),
            "unexpectedRecipientCount": len(unexpected),
            "fieldMismatchCount": len(field_mismatches),
        },
        "policyVersion": load_deliverability_policy().get("rule_id"),
        "complianceHold": MAILSHAKE_COMPLIANCE_HOLD,
        "error": None,
    }
    with _state_lock:
        _state["mailshake"].update(summary)

    print(
        "SRE_BRIDGE MAILSHAKE_MONITOR "
        + json.dumps(
            {
                "campaignId": MAILSHAKE_CAMPAIGN_ID,
                "paused": summary["campaignPaused"],
                "rosterExact": summary["rosterExact"],
                "recipients": summary["recipientCount"],
                "sent": summary["sentCount"],
                "replies": summary["replyCount"],
                "bounces": summary["bounceCount"],
                "unsubscribes": summary["unsubscribeCount"],
                "outOfOffice": summary["outOfOfficeCount"],
                "delays": summary["delayNotificationCount"],
                "missingRecipients": 0 if summary["problem"] is None else summary["problem"]["missingRecipientCount"],
                "unexpectedRecipients": 0 if summary["problem"] is None else summary["problem"]["unexpectedRecipientCount"],
                "fieldMismatches": 0 if summary["problem"] is None else summary["problem"]["fieldMismatchCount"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return summary


def mailshake_monitor_runner():
    while True:
        try:
            mailshake_monitor_once()
        except Exception as exc:
            error = str(exc)
            with _state_lock:
                _state["mailshake"].update(
                    {
                        "lastPollAt": now_iso(),
                        "error": error,
                    }
                )
            print(f"SRE_BRIDGE MAILSHAKE_MONITOR ERROR {error}", flush=True)
        time.sleep(max(300, MAILSHAKE_MONITOR_INTERVAL_SECONDS))


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("sequenceId") and int(data["sequenceId"]) != SEQUENCE_ID:
        raise RuntimeError("Configured sequenceId does not match REPLY_SEQUENCE_ID")
    return data


def load_campaign_copy():
    with open(CAMPAIGN_COPY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("sequenceId") and int(data["sequenceId"]) != SEQUENCE_ID:
        raise RuntimeError("Campaign copy sequenceId does not match REPLY_SEQUENCE_ID")
    emails = data.get("emails") or []
    if len(emails) != 4:
        raise RuntimeError(f"CAMPAIGN_COPY_REQUIRES_4_EMAILS:{len(emails)}")
    for index, email in enumerate(emails, start=1):
        if not str(email.get("message") or "").strip():
            raise RuntimeError(f"CAMPAIGN_COPY_EMAIL_{index}_EMPTY")
    return data


def normalize_text(value):
    return re.sub(r"\s+", " ", (value or "")).strip().lower()


def claim_link_matches(href, profile_id):
    if not href:
        return False
    parsed = urlparse(href)
    if parsed.netloc and parsed.netloc != "franklinnavigator.com":
        return False
    if parsed.path.rstrip("/") != "/claim-profile":
        return False
    return parse_qs(parsed.query).get("profile", [None])[0] == profile_id


def verify_profile(prospect):
    url = prospect["profileUrl"]
    profile_id = prospect["profileId"]
    business = prospect["business"]
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "franklinnavigator.com":
        return False, "PROFILE_URL_NOT_CANONICAL_FRANKLIN_HOST"
    expected_path = f"/profiles/{profile_id}/"
    if parsed.path != expected_path:
        return False, "PROFILE_URL_PROFILE_ID_MISMATCH"

    response = requests.get(url, timeout=30, allow_redirects=True)
    if response.status_code != 200:
        return False, f"PROFILE_HTTP_{response.status_code}"
    final = urlparse(response.url)
    if final.netloc != "franklinnavigator.com" or final.path != expected_path:
        return False, "PROFILE_REDIRECTED_AWAY_FROM_EXACT_CANONICAL"

    soup = BeautifulSoup(response.text, "html.parser")
    heading = soup.find("h1")
    h1 = normalize_text(heading.get_text(" ", strip=True) if heading else "")
    expected_business = normalize_text(business)
    if not h1 or (expected_business not in h1 and h1 not in expected_business):
        return False, f"PROFILE_NAME_MISMATCH:{h1}"

    if not any(claim_link_matches(a.get("href"), profile_id) for a in soup.find_all("a")):
        return False, "PROFILE_CLAIM_ACTION_MISSING"

    return True, "PASS"


def contact_get(contact_id):
    return api("GET", f"/contacts/{contact_id}")


def update_contact(prospect, state_value):
    contact = contact_get(prospect["contactId"])
    expected_email = prospect["email"].strip().lower()
    actual_email = (contact.get("email") or "").strip().lower()
    if actual_email != expected_email:
        raise RuntimeError(
            f"CONTACT_EMAIL_MISMATCH:{prospect['contactId']}:{actual_email}"
        )

    greeting = prospect["outreachGreeting"].strip()
    if not greeting:
        raise RuntimeError(f"EMPTY_OUTREACH_GREETING:{prospect['contactId']}")

    custom_fields = [
        {"id": PROFILE_FIELD_ID, "value": prospect["profileUrl"]},
        {"id": PROFILE_ID_FIELD_ID, "value": prospect["profileId"]},
        {"id": GREETING_FIELD_ID, "value": greeting},
        {"id": LINK_STATE_FIELD_ID, "value": state_value},
    ]

    payload = {
        "firstName": contact.get("firstName") or prospect["business"],
        "customFields": custom_fields,
    }
    return api("PATCH", f"/contacts/{prospect['contactId']}", json=payload)


def exact_profile_only_body(body):
    text = body or ""
    greeting_var = "{{Outreach_Greeting}}"
    profile_var = "{{Profile_URL}}"

    text, replaced = re.subn(
        r"(?is)^\s*(?:<p>\s*)?(?:hi|hello|hey)(?:\s+[^,<\r\n]{1,100})?,?",
        f"Hi {greeting_var},",
        text,
        count=1,
    )
    if not replaced:
        separator = "<br><br>" if "<br" in text.lower() else "\n\n"
        text = f"Hi {greeting_var},{separator}" + text.lstrip()

    text = re.sub(
        r"(?i)You can(?: also)? learn more here:",
        "Review your Franklin Navigator profile, claim or manage it, and see the optional Community Membership path here:",
        text,
    )

    franklin_url = re.compile(
        r"https://franklinnavigator\.com(?P<path>/[^\s<>\"]*)?", re.I
    )

    def replace_franklin_url(match):
        raw_path = match.group("path") or "/"
        path_only = raw_path.split("?", 1)[0].split("#", 1)[0]
        if path_only.startswith("/profiles/"):
            return profile_var
        if (
            path_only in GENERIC_FRANKLIN_PATHS
            or path_only.startswith("/membership-")
            or path_only.startswith("/business-membership")
        ):
            return profile_var
        return "__FRANKLIN_LINK_BLOCKED__"

    text = franklin_url.sub(replace_franklin_url, text)
    if "__FRANKLIN_LINK_BLOCKED__" in text:
        raise RuntimeError("TEMPLATE_CONTAINS_NON_PROFILE_FRANKLIN_LINK")

    if profile_var not in text:
        separator = "<br><br>" if "<br" in text.lower() else "\n\n"
        text = (
            text.rstrip()
            + separator
            + "Review your Franklin Navigator profile, claim or manage it, and see the optional Community Membership path here:"
            + ("<br>" if "<br" in text.lower() else "\n")
            + profile_var
        )

    first = text.find(profile_var)
    if first >= 0:
        before = text[: first + len(profile_var)]
        after = text[first + len(profile_var) :].replace(profile_var, "")
        text = before + after

    return text


def get_sequence():
    return api("GET", f"/sequences/{SEQUENCE_ID}")


def extract_email_step(step):
    email_template = ((step.get("template") or {}).get("emailTemplate") or {})
    execution_mode = (
        email_template.get("executionMode")
        or step.get("executionMode")
        or "Automatic"
    )
    templates = (
        email_template.get("templates")
        or step.get("templates")
        or step.get("variants")
        or []
    )

    if templates:
        return execution_mode, templates

    detail = api("GET", f"/sequences/{SEQUENCE_ID}/steps/{step['id']}") or {}
    detail_email = ((detail.get("template") or {}).get("emailTemplate") or {})
    execution_mode = (
        detail_email.get("executionMode")
        or detail.get("executionMode")
        or execution_mode
    )
    templates = (
        detail_email.get("templates")
        or detail.get("templates")
        or detail.get("variants")
        or []
    )

    if not templates:
        direct_template = detail.get("template") or {}
        if isinstance(direct_template, dict) and (
            "body" in direct_template or "message" in direct_template
        ):
            templates = [direct_template]

    return execution_mode, templates


def update_email_steps():
    sequence = get_sequence()
    steps = sequence.get("steps") or []
    email_steps = [
        step for step in steps if str(step.get("type") or "").lower() == "email"
    ]
    campaign_copy = load_campaign_copy()
    campaign_emails = campaign_copy["emails"]

    if len(email_steps) != len(campaign_emails):
        raise RuntimeError(
            f"SEQUENCE_EMAIL_STEP_COUNT_MISMATCH:{len(email_steps)}:{len(campaign_emails)}"
        )

    changed = False
    for index, step in enumerate(email_steps):
        step_id = step["id"]
        execution_mode, templates = extract_email_step(step)
        if not templates:
            raise RuntimeError(f"EMAIL_STEP_{step_id}_HAS_NO_TEMPLATES")
        if len(templates) != 1:
            raise RuntimeError(f"EMAIL_STEP_{step_id}_EXPECTED_ONE_VARIANT:{len(templates)}")

        desired = campaign_emails[index]
        desired_subject = str(desired.get("subject") or "")
        desired_body = exact_profile_only_body(str(desired.get("message") or ""))

        template = templates[0]
        variant_id = template.get("variantId") or template.get("id")
        if not variant_id:
            raise RuntimeError(f"EMAIL_STEP_{step_id}_VARIANT_HAS_NO_ID")

        old_subject = str(template.get("subject") or "")
        old_body = template.get("body") or template.get("message") or ""
        if old_subject == desired_subject and old_body == desired_body:
            continue

        item = {
            "id": variant_id,
            "subject": desired_subject,
            "message": desired_body,
        }
        email_template_id = template.get("emailTemplateId") or template.get("templateId")
        if email_template_id is not None:
            item["emailTemplateId"] = email_template_id
        if template.get("attachmentIds") is not None:
            item["attachmentIds"] = template.get("attachmentIds") or []

        payload = {
            "type": "Email",
            "delayInMinutes": int(step.get("delayInMinutes") or 0),
            "executionMode": execution_mode,
            "variants": [item],
        }
        if step.get("parentId") is not None:
            payload["parentId"] = step.get("parentId")
        if step.get("ifConditionPositive") is not None:
            payload["ifConditionPositive"] = bool(step.get("ifConditionPositive"))

        api(
            "PUT",
            f"/sequences/{SEQUENCE_ID}/steps/{step_id}",
            json=payload,
        )
        changed = True

    with _state_lock:
        _state["campaignCopyVersion"] = campaign_copy.get("version")
    return changed


def send_owner_test_once():
    if not OWNER_TEST_ON_STARTUP:
        return

    if OWNER_TEST_CONTACT_ID <= 0:
        error = "OWNER_TEST_CONTACT_ID is required"
    elif OWNER_TEST_EMAIL_ACCOUNT_ID <= 0:
        error = "OWNER_TEST_EMAIL_ACCOUNT_ID is required"
    elif not OWNER_TEST_SUBJECT:
        error = "OWNER_TEST_SUBJECT is required"
    elif not OWNER_TEST_BODY.strip():
        error = "OWNER_TEST_BODY is required"
    else:
        error = None

    if error:
        with _state_lock:
            _state["ownerTest"].update({"status": "ERROR", "error": error})
        print(f"SRE_BRIDGE OWNER_TEST ERROR {error}", flush=True)
        return

    try:
        result = api(
            "POST",
            f"/contacts/{OWNER_TEST_CONTACT_ID}/send-direct-email",
            json={
                "subject": OWNER_TEST_SUBJECT,
                "body": OWNER_TEST_BODY,
                "emailAccountId": OWNER_TEST_EMAIL_ACCOUNT_ID,
            },
        ) or {}
        sent_at = now_iso()
        with _state_lock:
            _state["ownerTest"].update(
                {
                    "status": str(result.get("status") or "SENT").upper(),
                    "sentAt": sent_at,
                    "messageId": result.get("messageId"),
                    "error": None,
                }
            )
        print(
            "SRE_BRIDGE OWNER_TEST SENT "
            + json.dumps(
                {
                    "status": result.get("status"),
                    "messageId": result.get("messageId"),
                    "sentAt": sent_at,
                },
                sort_keys=True,
            ),
            flush=True,
        )
    except Exception as exc:
        error = str(exc)
        with _state_lock:
            _state["ownerTest"].update({"status": "ERROR", "error": error})
        print(f"SRE_BRIDGE OWNER_TEST ERROR {error}", flush=True)


def sync_once():
    config = load_config()
    held = []
    ready = 0
    processed = 0

    for prospect in config["prospects"]:
        processed += 1
        ok, reason = verify_profile(prospect)
        if not ok:
            try:
                update_contact(prospect, f"HOLD:{reason}")
            except Exception as hold_exc:
                print(
                    f"SRE_BRIDGE hold-write-failed contact={prospect['contactId']} error={hold_exc}",
                    flush=True,
                )
            held.append(
                {
                    "contactId": prospect["contactId"],
                    "business": prospect["business"],
                    "reason": reason,
                }
            )
            continue

        update_contact(prospect, "READY_EXACT_PROFILE_BOUND")
        ready += 1

    template_updated = False
    if not held:
        template_updated = update_email_steps()

    activation_result = {"attempted": False, "added": [], "notProcessed": None, "error": None}
    activation_queue = [int(x) for x in (config.get("activationQueue") or []) if int(x) > 0]
    if not held and activation_queue:
        activation_result["attempted"] = True
        try:
            raw_activation = api(
                "POST",
                f"/sequences/{SEQUENCE_ID}/contact-links/bulk",
                json={
                    "contactIds": activation_queue,
                    "removeFromExisting": False,
                    "ignoreStepDelay": False,
                },
            ) or {}
            activation_result["added"] = raw_activation.get("added") or []
            activation_result["notProcessed"] = raw_activation.get("notProcessed")
            print(
                "SRE_BRIDGE activation "
                + json.dumps(
                    {
                        "requested": activation_queue,
                        "added": activation_result["added"],
                        "notProcessed": activation_result["notProcessed"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        except Exception as activation_exc:
            activation_result["error"] = str(activation_exc)
            print(f"SRE_BRIDGE ACTIVATION ERROR {activation_exc}", flush=True)

    target = int(config.get("targetDailySendCount") or len(config["prospects"]))
    outcome = "PASS_READY" if not held else "HOLD_WITH_REPLACEMENT_REQUIRED"
    result = {
        "lastRunAt": now_iso(),
        "lastOutcome": outcome,
        "sequenceId": SEQUENCE_ID,
        "processed": processed,
        "ready": ready,
        "held": held,
        "replacementNeeded": max(0, target - ready),
        "templateUpdated": template_updated,
        "activation": activation_result,
        "error": None,
    }
    with _state_lock:
        _state.update(result)
    print(
        "SRE_BRIDGE sync "
        + json.dumps(
            {
                "outcome": outcome,
                "processed": processed,
                "ready": ready,
                "held": len(held),
                "replacementNeeded": result["replacementNeeded"],
                "templateUpdated": template_updated,
                "campaignCopyVersion": _state.get("campaignCopyVersion"),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return result





def probe_first10_domain_health_once():
    """Read-only probe of Reply's V3 email-account filter response.

    The point is to obtain current provider-side domain-validation evidence.
    This never changes DNS, mailbox, sequence, contact, or sending state.
    """
    attempts = [
        {"top": 100, "skip": 0},
        {"limit": 100, "offset": 0},
        {},
    ]
    for payload in attempts:
        try:
            response = requests.post(
                API_BASE + "/email-accounts/filter",
                headers=auth_headers(),
                timeout=30,
                json=payload,
            )
            body = response.text[:12000]
            print(
                "SRE_BRIDGE FIRST10_DOMAIN_HEALTH_PROBE "
                + json.dumps(
                    {
                        "status": response.status_code,
                        "payload": payload,
                        "body": body,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if response.status_code < 400:
                return
        except Exception as exc:
            print(f"SRE_BRIDGE FIRST10_DOMAIN_HEALTH_PROBE ERROR {exc}", flush=True)


def stage_first10_contact_fields_once():
    """Write only the exact profile-bound personalization fields for the bound ten.

    Does not enroll contacts, start a sequence, or send messages.
    """
    try:
        staged = []
        for prospect in FIRST10_CONTACT_ROSTER:
            update_contact(prospect, "READY_EXACT_PROFILE_BOUND_FIRST_TOUCH_ONLY")
            staged.append(int(prospect["contactId"]))
        if len(staged) != 10 or len(set(staged)) != 10:
            raise RuntimeError("FIRST10_STAGE_CONTACT_SET_NOT_EXACTLY_10_UNIQUE")
        print(
            "SRE_BRIDGE FIRST10_FIELDS STAGED "
            + json.dumps(
                {
                    "sequenceId": FIRST10_PILOT_SEQUENCE_ID,
                    "contactIds": staged,
                    "count": len(staged),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return staged
    except Exception as exc:
        print(f"SRE_BRIDGE FIRST10_FIELDS ERROR {exc}", flush=True)
        return None


def provision_first10_sequence_once():
    """Idempotently provision the bounded Franklin first-10, first-touch-only sequence.

    This function only creates or reuses the dedicated one-step sequence.
    It never creates contacts, enrolls contacts, starts/resumes a sequence,
    or sends a message.
    """
    try:
        skip = 0
        existing = None
        while True:
            page = api("GET", f"/sequences?top=100&skip={skip}") or {}
            items = page.get("items") or page.get("Items") or []
            existing = next(
                (
                    item
                    for item in items
                    if str(item.get("name") or item.get("Name") or "")
                    == FIRST10_PILOT_SEQUENCE_NAME
                ),
                None,
            )
            if existing or not (page.get("hasMore") or page.get("HasMore")):
                break
            skip += len(items) or 100

        if existing:
            sequence_id = int(existing.get("id") or existing.get("Id") or 0)
            if sequence_id <= 0:
                raise RuntimeError("FIRST10_EXISTING_SEQUENCE_HAS_NO_VALID_ID")
            print(
                "SRE_BRIDGE FIRST10_SEQUENCE REUSED "
                + json.dumps(
                    {"sequenceId": sequence_id, "name": FIRST10_PILOT_SEQUENCE_NAME},
                    sort_keys=True,
                ),
                flush=True,
            )
            return sequence_id

        payload = {
            "name": FIRST10_PILOT_SEQUENCE_NAME,
            "scheduleId": FIRST10_PILOT_SCHEDULE_ID,
            "emailAccounts": [FIRST10_PILOT_EMAIL_ACCOUNT_ID],
            "linkedInAccounts": [],
            "settings": {
                "emailsCountPerDay": 10,
                "emailSendingDelaySeconds": 300,
                "dailyThrottling": 10,
                "useDailyThrottling": True,
                "disableOpensTracking": True,
                "repliesHandlingType": "markAsFinished",
                "enableLinksTracking": False,
            },
            "steps": [
                {
                    "type": "email",
                    "delayInMinutes": 0,
                    "executionMode": "automatic",
                    "variants": [
                        {
                            "subject": "Your Franklin Navigator community profile",
                            "message": (
                                "Hi {{Outreach_Greeting}},<br><br>"
                                "Franklin Navigator is a local community network connecting Franklin residents with local businesses, professionals, organizations and resources.<br><br>"
                                "<strong>Your community profile:</strong><br>"
                                "{{Profile_URL}}<br><br>"
                                "<strong>You can claim it free</strong> to review and manage your business information.<br><br>"
                                "<strong>Optional Community Membership — $35/year</strong>, renewing annually until canceled:<br>"
                                "• Build a richer profile with services, hours, photos and business details<br>"
                                "• Add website, contact, booking, quote, menu/order and social links where applicable<br>"
                                "• Gain additional local visibility and community-participation tools<br>"
                                "• Help Franklin residents better understand and connect with your business<br><br>"
                                "Factual corrections and profile removal are always free.<br><br>"
                                "Questions? Just reply and I’ll be happy to help."
                            ),
                        }
                    ],
                }
            ],
        }
        created = api("POST", "/sequences", json=payload) or {}
        sequence_id = int(created.get("id") or created.get("Id") or 0)
        if sequence_id <= 0:
            raise RuntimeError(
                "FIRST10_SEQUENCE_CREATE_RETURNED_NO_VALID_ID:" + json.dumps(created)[:800]
            )
        print(
            "SRE_BRIDGE FIRST10_SEQUENCE CREATED "
            + json.dumps(
                {"sequenceId": sequence_id, "name": FIRST10_PILOT_SEQUENCE_NAME},
                sort_keys=True,
            ),
            flush=True,
        )
        return sequence_id
    except Exception as exc:
        print(f"SRE_BRIDGE FIRST10_SEQUENCE ERROR {exc}", flush=True)
        return None


def runner():
    while True:
        try:
            sync_once()
        except Exception as exc:
            error = str(exc)
            with _state_lock:
                _state.update(
                    {
                        "lastRunAt": now_iso(),
                        "lastOutcome": "ERROR",
                        "error": error,
                    }
                )
            print(f"SRE_BRIDGE ERROR {error}", flush=True)
        time.sleep(SYNC_INTERVAL_SECONDS)


@app.on_event("startup")
def startup():
    try:
        startup_config = load_config()
        startup_count = len(startup_config.get("prospects") or [])
    except Exception:
        startup_count = -1
    print(
        f"SRE_BRIDGE startup apiKeyConfigured={bool(REPLY_API_KEY)} replySyncEnabled={REPLY_SYNC_ENABLED} mailshakeApiKeyConfigured={bool(MAILSHAKE_API_KEY)} mailshakeCampaignId={MAILSHAKE_CAMPAIGN_ID} complianceHold={MAILSHAKE_COMPLIANCE_HOLD} sequenceId={SEQUENCE_ID} configPath={CONFIG_PATH} prospectCount={startup_count}",
        flush=True,
    )
    threading.Thread(target=test_mailshake_connection, daemon=True).start()
    if MAILSHAKE_API_KEY and MAILSHAKE_CAMPAIGN_ID > 0:
        threading.Thread(target=mailshake_monitor_runner, daemon=True).start()
        if MAILSHAKE_PUSH_SETUP_ON_STARTUP and MAILSHAKE_PUSH_SECRET:
            threading.Thread(target=setup_mailshake_pushes_once, daemon=True).start()
    if FIRST10_PROVISION_ON_STARTUP:
        threading.Thread(target=provision_first10_sequence_once, daemon=True).start()
    if FIRST10_STAGE_FIELDS_ON_STARTUP:
        threading.Thread(target=stage_first10_contact_fields_once, daemon=True).start()
    if FIRST10_DOMAIN_HEALTH_PROBE_ON_STARTUP:
        threading.Thread(target=probe_first10_domain_health_once, daemon=True).start()
    if REPLY_SYNC_ENABLED:
        threading.Thread(target=runner, daemon=True).start()
    if OWNER_TEST_ON_STARTUP:
        threading.Thread(target=send_owner_test_once, daemon=True).start()


@app.get("/health")
def health():
    return {
        "ok": True,
        "apiKeyConfigured": bool(REPLY_API_KEY),
        "sequenceId": SEQUENCE_ID,
        "lastRunAt": _state["lastRunAt"],
        "lastOutcome": _state["lastOutcome"],
        "mailshakeApiKeyConfigured": bool(MAILSHAKE_API_KEY),
        "mailshakeConnection": _state["mailshake"]["connection"],
        "mailshakeCampaignId": MAILSHAKE_CAMPAIGN_ID or None,
        "mailshakeLastPollAt": _state["mailshake"].get("lastPollAt"),
    }


@app.get("/mailshake/pilot/status")
def mailshake_pilot_status():
    with _state_lock:
        ms = dict(_state["mailshake"])
    return {
        "ok": ms.get("connection") == "PASS" and not ms.get("error"),
        "campaignId": ms.get("campaignId"),
        "campaignTitle": ms.get("campaignTitle"),
        "campaignPaused": ms.get("campaignPaused"),
        "lastPollAt": ms.get("lastPollAt"),
        "rosterExact": ms.get("rosterExact"),
        "recipientCount": ms.get("recipientCount"),
        "sentCount": ms.get("sentCount"),
        "replyCount": ms.get("replyCount"),
        "bounceCount": ms.get("bounceCount"),
        "unsubscribeCount": ms.get("unsubscribeCount"),
        "outOfOfficeCount": ms.get("outOfOfficeCount"),
        "delayNotificationCount": ms.get("delayNotificationCount"),
        "problem": ms.get("problem"),
        "safetyPauseReason": ms.get("safetyPauseReason"),
        "policyVersion": ms.get("policyVersion"),
        "complianceHold": ms.get("complianceHold"),
        "pushSubscriptions": ms.get("pushSubscriptions"),
        "lastPushAt": ms.get("lastPushAt"),
        "lastPushEvent": ms.get("lastPushEvent"),
        "error": ms.get("error"),
    }


@app.post("/mailshake/push/{secret}/{event_name}")
async def mailshake_push(secret: str, event_name: str, request: Request):
    if not MAILSHAKE_PUSH_SECRET or secret != MAILSHAKE_PUSH_SECRET:
        raise HTTPException(status_code=404, detail="Not found")
    body = await request.json()
    resource_url = str(body.get("resource_url") or "").strip()
    event_key = event_name.strip().lower()
    if event_key not in {"messagesent", "replied"}:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        resource = mailshake_fetch_resource(resource_url)
        campaign = resource.get("campaign") or {}
        resource_campaign_id = int(campaign.get("id") or 0)
        if resource_campaign_id and resource_campaign_id != MAILSHAKE_CAMPAIGN_ID:
            print(
                f"SRE_BRIDGE MAILSHAKE_PUSH IGNORED event={event_key} campaign={resource_campaign_id}",
                flush=True,
            )
            return {"ok": True, "ignored": True}
        with _state_lock:
            _state["mailshake"]["lastPushAt"] = now_iso()
            _state["mailshake"]["lastPushEvent"] = event_key
        print(
            "SRE_BRIDGE MAILSHAKE_PUSH RECEIVED "
            + json.dumps(
                {
                    "event": event_key,
                    "campaignId": resource_campaign_id or MAILSHAKE_CAMPAIGN_ID,
                    "replyType": resource.get("type") if event_key == "replied" else None,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        threading.Thread(target=mailshake_monitor_once, daemon=True).start()
        return {"ok": True}
    except Exception as exc:
        print(f"SRE_BRIDGE MAILSHAKE_PUSH ERROR {exc}", flush=True)
        raise HTTPException(status_code=500, detail="Push processing failed")


@app.get("/mailshake/health")
def mailshake_health():
    ok = test_mailshake_connection()
    with _state_lock:
        state = dict(_state["mailshake"])
    return {"ok": ok, **state}


@app.get("/status")
def status():
    with _state_lock:
        return dict(_state)
