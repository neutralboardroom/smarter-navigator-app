import json
import hmac
import hashlib
import base64
import smtplib
import ssl
import dkim
import imaplib
import csv
import io
import os
import re
import threading
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from email import policy as email_policy
from email.parser import BytesParser
from zoneinfo import ZoneInfo
from email.utils import formatdate, make_msgid
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

SRE_BRIDGE_RELEASE = "FN-SRE-BRIDGE-2.3.0"
API_BASE = "https://api.reply.io/v3"
REPLY_API_KEY = os.environ.get("REPLY_API_KEY", "").strip()
MAILSHAKE_API_BASE = "https://api.mailshake.com/2017-04-01"
MAILSHAKE_API_KEY = os.environ.get("MAILSHAKE_API_KEY", "").strip()
MAILSHAKE_RUNTIME_ENABLED = os.environ.get("MAILSHAKE_RUNTIME_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
MAILSHAKE_CAMPAIGN_ID = int(os.environ.get("MAILSHAKE_CAMPAIGN_ID", "0") or 0)
MAILSHAKE_COMPLIANCE_TEST_CAMPAIGN_ID = int(os.environ.get("MAILSHAKE_COMPLIANCE_TEST_CAMPAIGN_ID", "1554023") or 1554023)
MAILSHAKE_MONITOR_INTERVAL_SECONDS = int(os.environ.get("MAILSHAKE_MONITOR_INTERVAL_SECONDS", "900"))
REPLY_SYNC_ENABLED = os.environ.get("REPLY_SYNC_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
MAILSHAKE_PUSH_SECRET = os.environ.get("MAILSHAKE_PUSH_SECRET", "").strip()
MAILSHAKE_PUBLIC_BASE_URL = os.environ.get("MAILSHAKE_PUBLIC_BASE_URL", "https://sre-reply-profile-bridge.onrender.com").rstrip("/")
MAILSHAKE_PUSH_SETUP_ON_STARTUP = os.environ.get("MAILSHAKE_PUSH_SETUP_ON_STARTUP", "false").strip().lower() in {"1", "true", "yes"}
MAILSHAKE_COMPLIANCE_HOLD = os.environ.get("MAILSHAKE_COMPLIANCE_HOLD", "true").strip().lower() in {"1", "true", "yes"}
FN_OUTREACH_SMTP_HOST = os.environ.get("FN_OUTREACH_SMTP_HOST", "smtp.zoho.com").strip()
FN_OUTREACH_SMTP_PORT = int(os.environ.get("FN_OUTREACH_SMTP_PORT", "465") or 465)
FN_OUTREACH_SMTP_USER = os.environ.get("FN_OUTREACH_SMTP_USER", "community@franklinnavigator.com").strip()
FN_OUTREACH_SMTP_PASSWORD = os.environ.get("FN_OUTREACH_SMTP_PASSWORD", "").strip()
FN_OUTREACH_PUBLIC_BASE_URL = os.environ.get("FN_OUTREACH_PUBLIC_BASE_URL", MAILSHAKE_PUBLIC_BASE_URL).rstrip("/")
FN_OUTREACH_OWNER_TEST_EMAIL = os.environ.get("FN_OUTREACH_OWNER_TEST_EMAIL", "reachrgnow@gmail.com").strip()
FN_OWNER_ALERT_BRIDGE_SECRET = os.environ.get("FN_OWNER_ALERT_BRIDGE_SECRET", "").strip()
FN_TRANSACTIONAL_BRIDGE_SECRET = os.environ.get("FN_TRANSACTIONAL_BRIDGE_SECRET", "").strip()
FN_OUTREACH_OWNER_TEST_ON_STARTUP = os.environ.get("FN_OUTREACH_OWNER_TEST_ON_STARTUP", "false").strip().lower() in {"1", "true", "yes"}
FN_ONE_CLICK_SELF_TEST_ON_STARTUP = os.environ.get("FN_ONE_CLICK_SELF_TEST_ON_STARTUP", "false").strip().lower() in {"1", "true", "yes"}
FN_OUTREACH_LIST_ID = "franklin-navigator-community-outreach.franklinnavigator.com"
FN_UNSUBSCRIBE_SIGNING_SECRET = os.environ.get("FN_UNSUBSCRIBE_SIGNING_SECRET", "").strip()
FN_OUTREACH_DKIM_PRIVATE_KEY_B64 = os.environ.get("FN_OUTREACH_DKIM_PRIVATE_KEY_B64", "").strip()
FN_OUTREACH_DKIM_SELECTOR = os.environ.get("FN_OUTREACH_DKIM_SELECTOR", "fnmail1").strip()
FN_OUTREACH_DKIM_DOMAIN = os.environ.get("FN_OUTREACH_DKIM_DOMAIN", "franklinnavigator.com").strip()
FN_FEEDBACK_SENDER_ID = os.environ.get("FN_FEEDBACK_SENDER_ID", "FRNAVGTR").strip()
FN_OUTREACH_IMAP_HOST = os.environ.get("FN_OUTREACH_IMAP_HOST", "imap.zoho.com").strip()
FN_OUTREACH_IMAP_PORT = int(os.environ.get("FN_OUTREACH_IMAP_PORT", "993") or 993)
FN_SUPPRESSION_MAILBOX = os.environ.get("FN_SUPPRESSION_MAILBOX", "Franklin Navigator Suppressions").strip()
FN_SEND_LEDGER_MAILBOX = os.environ.get("FN_SEND_LEDGER_MAILBOX", "Franklin Navigator Outreach Ledger").strip()
FN_SUPPRESSION_SEED_ON_STARTUP = os.environ.get("FN_SUPPRESSION_SEED_ON_STARTUP", "false").strip().lower() in {"1", "true", "yes"}
FN_DIRECT_OUTREACH_ENABLED = os.environ.get("FN_DIRECT_OUTREACH_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
FN_INITIAL_SEND_OVERRIDE = os.environ.get("FN_INITIAL_SEND_OVERRIDE", "false").strip().lower() in {"1", "true", "yes"}
FN_INITIAL_COHORT_CLOSED = os.environ.get("FN_INITIAL_COHORT_CLOSED", "false").strip().lower() in {"1", "true", "yes"}
FN_DIRECT_SEQUENCE_PATH = os.environ.get("FN_DIRECT_SEQUENCE_PATH", os.path.join(os.path.dirname(__file__), "direct_outreach_sequence.json")).strip()
FN_PROFILE_PREFLIGHT_ON_STARTUP = os.environ.get("FN_PROFILE_PREFLIGHT_ON_STARTUP", "false").strip().lower() in {"1", "true", "yes"}
RFC8058_SCALE_PROOF = os.environ.get("RFC8058_SCALE_PROOF", "false").strip().lower() in {"1", "true", "yes"}
DELIVERABILITY_POLICY_PATH = os.path.join(os.path.dirname(__file__), "roger_deliverability_policy.json")
ORG_SAFETY_POLICY_PATH = os.path.join(os.path.dirname(__file__), "org_domain_safety_policy.json")
ORG_SAFETY_STATE_PATH = os.path.join(os.path.dirname(__file__), "org_domain_safety_state.json")
SEQUENCE_ID = int(os.environ.get("REPLY_SEQUENCE_ID", "1768444"))
SYNC_INTERVAL_SECONDS = int(os.environ.get("SYNC_INTERVAL_SECONDS", "900"))
FIRST10_PROVISION_ON_STARTUP = os.environ.get("FIRST10_PROVISION_ON_STARTUP", "").strip().lower() in {"1", "true", "yes"}
FIRST10_PILOT_SEQUENCE_NAME = "Franklin Navigator — First 10 Pilot — First Touch Only — 2026-09-20"
FIRST10_PILOT_SCHEDULE_ID = 563862
FIRST10_PILOT_EMAIL_ACCOUNT_ID = 954440
FIRST10_STAGE_FIELDS_ON_STARTUP = os.environ.get("FIRST10_STAGE_FIELDS_ON_STARTUP", "").strip().lower() in {"1", "true", "yes"}
FIRST10_DOMAIN_HEALTH_PROBE_ON_STARTUP = os.environ.get("FIRST10_DOMAIN_HEALTH_PROBE_ON_STARTUP", "").strip().lower() in {"1", "true", "yes"}
FIRST10_PILOT_SEQUENCE_ID = 1776919
FIRST10_INCIDENT_NO_FOLLOWUP_EMAILS = {"catering@littlehatsmarket.com"}
FIRST10_INCIDENT_SEEDED_SENT_AT = {"catering@littlehatsmarket.com": "2026-09-29T06:35:58+00:00"}
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

app = FastAPI(title="SRE Outreach Provider Bridge", version="2.3.0")
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
        "genericInboxCount": 0,
        "duplicateDomains": [],
        "domainHolds": [],
        "domainSuppressions": [],
        "ownerAlerts": [],
    },
    "ownerTest": {
        "enabled": OWNER_TEST_ON_STARTUP,
        "status": "NOT_REQUESTED" if not OWNER_TEST_ON_STARTUP else "PENDING",
        "sentAt": None,
        "messageId": None,
        "error": None,
    },
    "directOutreach": {
        "enabled": FN_DIRECT_OUTREACH_ENABLED,
        "lastCheckedAt": None,
        "sentMailbox": None,
        "imapConnection": "NOT_TESTED",
        "campaignId": "FN-FIRST10-2026-09",
        "initialSent": 0,
        "followup1Sent": 0,
        "followup2Sent": 0,
        "stoppedForReply": [],
        "suppressed": [],
        "bounceHolds": [],
        "complaintHolds": [],
        "ownerAlerts": [],
        "globalHold": None,
        "nextEligible": [],
        "lastSendAt": None,
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





def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def make_unsubscribe_token(email: str) -> str:
    if not FN_UNSUBSCRIBE_SIGNING_SECRET:
        raise RuntimeError("FN_UNSUBSCRIBE_SIGNING_SECRET is not configured")
    email_value = str(email or "").strip().lower()
    if "@" not in email_value:
        raise RuntimeError("invalid unsubscribe email")
    encoded = _urlsafe_b64encode(email_value.encode("utf-8"))
    signature = hmac.new(
        FN_UNSUBSCRIBE_SIGNING_SECRET.encode("utf-8"),
        ("v2:" + encoded).encode("ascii"),
        hashlib.sha256,
    ).digest()[:16]
    return "v2." + encoded + "." + _urlsafe_b64encode(signature)


def parse_unsubscribe_token(token: str) -> str:
    try:
        if not FN_UNSUBSCRIBE_SIGNING_SECRET:
            raise ValueError("signing secret missing")
        version, encoded, supplied_sig = token.split(".", 2)
        if version != "v2":
            raise ValueError("unsupported token version")
        expected_sig = _urlsafe_b64encode(
            hmac.new(
                FN_UNSUBSCRIBE_SIGNING_SECRET.encode("utf-8"),
                ("v2:" + encoded).encode("ascii"),
                hashlib.sha256,
            ).digest()[:16]
        )
        if not hmac.compare_digest(supplied_sig, expected_sig):
            raise ValueError("signature mismatch")
        email = _urlsafe_b64decode(encoded).decode("utf-8").strip().lower()
        if "@" not in email:
            raise ValueError("invalid email")
        return email
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid unsubscribe token") from exc


def _ensure_suppression_mailbox(client):
    status, _ = client.select(f'"{FN_SUPPRESSION_MAILBOX}"', readonly=True)
    if status == "OK":
        return
    client.create(f'"{FN_SUPPRESSION_MAILBOX}"')
    status2, _ = client.select(f'"{FN_SUPPRESSION_MAILBOX}"', readonly=True)
    if status2 != "OK":
        raise RuntimeError("Unable to create suppression mailbox")


def _persist_zoho_suppression(email: str, reason: str):
    email_value = str(email or "").strip().lower()
    if "@" not in email_value:
        raise RuntimeError("invalid suppression email")
    with _imap_connect() as client:
        _ensure_suppression_mailbox(client)
        marker = EmailMessage(policy=email_policy.SMTP)
        marker["From"] = FN_OUTREACH_SMTP_USER
        marker["To"] = FN_OUTREACH_SMTP_USER
        marker["Subject"] = f"Franklin Navigator suppression: {email_value}"
        marker["Date"] = formatdate(localtime=True)
        marker["Message-ID"] = make_msgid(domain="franklinnavigator.com")
        marker["X-Franklin-Suppression-Email"] = email_value
        marker["X-Franklin-Suppression-Reason"] = str(reason or "unspecified")[:120]
        marker.set_content("Durable Franklin Navigator outreach suppression marker.")
        client.append(
            f'"{FN_SUPPRESSION_MAILBOX}"',
            "\\Seen",
            imaplib.Time2Internaldate(time.time()),
            marker.as_bytes(policy=email_policy.SMTP),
        )


def _persist_zoho_domain_suppression(domain: str, reason: str):
    domain_value = str(domain or "").strip().lower().rstrip(".")
    if "." not in domain_value:
        raise RuntimeError("invalid suppression domain")
    with _imap_connect() as client:
        _ensure_suppression_mailbox(client)
        marker = EmailMessage(policy=email_policy.SMTP)
        marker["From"] = FN_OUTREACH_SMTP_USER
        marker["To"] = FN_OUTREACH_SMTP_USER
        marker["Subject"] = f"Franklin Navigator domain suppression: {domain_value}"
        marker["Date"] = formatdate(localtime=True)
        marker["Message-ID"] = make_msgid(domain="franklinnavigator.com")
        marker["X-Franklin-Suppression-Domain"] = domain_value
        marker["X-Franklin-Suppression-Reason"] = str(reason or "unspecified")[:120]
        marker.set_content("Durable Franklin Navigator outreach domain suppression marker.")
        client.append(
            f'"{FN_SUPPRESSION_MAILBOX}"',
            "\\Seen",
            imaplib.Time2Internaldate(time.time()),
            marker.as_bytes(policy=email_policy.SMTP),
        )


def _zoho_domain_suppression_set():
    domains = set()
    with _imap_connect() as client:
        _ensure_suppression_mailbox(client)
        status, data = client.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("domain suppression mailbox search failed")
        ids = [x for x in (data[0] or b"").split() if x]
        for msg_id in ids[-5000:]:
            status2, msg_data = client.fetch(
                msg_id,
                '(BODY.PEEK[HEADER.FIELDS (X-FRANKLIN-SUPPRESSION-DOMAIN)])',
            )
            if status2 != "OK":
                continue
            raw = b"".join(
                part[1] for part in msg_data
                if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray))
            )
            if not raw:
                continue
            msg = BytesParser(policy=email_policy.default).parsebytes(raw)
            value = str(msg.get("X-Franklin-Suppression-Domain") or "").strip().lower().rstrip(".")
            if "." in value:
                domains.add(value)
    return domains


def _zoho_suppression_set():
    emails = set()
    with _imap_connect() as client:
        _ensure_suppression_mailbox(client)
        status, data = client.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("suppression mailbox search failed")
        ids = [x for x in (data[0] or b"").split() if x]
        for msg_id in ids[-5000:]:
            status2, msg_data = client.fetch(
                msg_id,
                '(BODY.PEEK[HEADER.FIELDS (X-FRANKLIN-SUPPRESSION-EMAIL)])',
            )
            if status2 != "OK":
                continue
            raw = b"".join(
                part[1] for part in msg_data
                if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray))
            )
            if not raw:
                continue
            msg = BytesParser(policy=email_policy.default).parsebytes(raw)
            value = str(msg.get("X-Franklin-Suppression-Email") or "").strip().lower()
            if "@" in value:
                emails.add(value)
    return emails


def persist_unsubscribe(email: str):
    _persist_zoho_suppression(email, "unsubscribe")
    # Best-effort compatibility sync while Mailshake still exists. This is not
    # a runtime dependency and may be removed/canceled without affecting safety.
    if MAILSHAKE_RUNTIME_ENABLED and MAILSHAKE_API_KEY:
        try:
            mailshake_api(
                "POST",
                "/recipients/unsubscribe",
                data={"emailAddresses": email},
            )
        except Exception as exc:
            print(f"SRE_BRIDGE MAILSHAKE_UNSUB_SYNC_SKIPPED {exc}", flush=True)
    print(
        "SRE_BRIDGE ONE_CLICK_UNSUBSCRIBE "
        + json.dumps(
            {"email": email, "store": "ZOHO_IMAP", "at": now_iso()},
            sort_keys=True,
        ),
        flush=True,
    )


def build_franklin_message(to_email: str, subject: str, plain_body: str, html_body: str = "") -> EmailMessage:
    token = make_unsubscribe_token(to_email)
    one_click_url = f"{FN_OUTREACH_PUBLIC_BASE_URL}/unsubscribe/one-click/{token}"
    visible_url = f"{FN_OUTREACH_PUBLIC_BASE_URL}/unsubscribe/{token}"
    msg = EmailMessage(policy=email_policy.SMTP.clone(max_line_length=998))
    msg["From"] = f"Franklin Navigator Community Team <{FN_OUTREACH_SMTP_USER}>"
    msg["To"] = to_email
    msg["Reply-To"] = FN_OUTREACH_SMTP_USER
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="franklinnavigator.com")
    msg["List-ID"] = f"<{FN_OUTREACH_LIST_ID}>"
    msg["List-Unsubscribe"] = f"<{one_click_url}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg["Feedback-ID"] = f"first10:profile:outreach:{FN_FEEDBACK_SENDER_ID}"
    footer_text = (
        "\n\nThis is a Franklin Navigator community outreach email.\n\n"
        "Franklin Navigator Community Team\n"
        "Franklin Navigator\n"
        "community@franklinnavigator.com\n"
        "(615) 656-7020\n"
        "franklinnavigator.com\n\n"
        f"Unsubscribe: {visible_url}\n"
        "2020 Fieldstone Pkwy, Ste 900, Franklin, TN 37069"
    )
    msg.set_content(plain_body.rstrip() + footer_text)
    if html_body:
        footer_html = (
            '<br><br>This is a Franklin Navigator community outreach email.<br><br>'
            'Franklin Navigator Community Team<br>'
            'Franklin Navigator<br>'
            'community@franklinnavigator.com<br>'
            '(615) 656-7020<br>'
            'franklinnavigator.com<br><br>'
            f'<a href="{visible_url}">Unsubscribe</a><br>'
            '2020 Fieldstone Pkwy, Ste 900, Franklin, TN 37069'
        )
        msg.add_alternative(html_body.rstrip() + footer_html, subtype="html")
    return msg


def _direct_dkim_private_key():
    if not FN_OUTREACH_DKIM_PRIVATE_KEY_B64:
        raise RuntimeError("FN_OUTREACH_DKIM_PRIVATE_KEY_B64 is not configured")
    try:
        return base64.b64decode(FN_OUTREACH_DKIM_PRIVATE_KEY_B64)
    except Exception as exc:
        raise RuntimeError("FN_OUTREACH_DKIM_PRIVATE_KEY_B64 is invalid") from exc


def send_franklin_transactional_smtp(to_email: str, subject: str, plain_body: str, html_body: str = ""):
    if not FN_OUTREACH_SMTP_PASSWORD:
        raise RuntimeError("FN_OUTREACH_SMTP_PASSWORD is not configured")
    if not re.match(r"^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$", str(to_email or "").strip()):
        raise RuntimeError("invalid transactional recipient")
    msg = EmailMessage(policy=email_policy.SMTP)
    msg["From"] = f"Franklin Navigator <{FN_OUTREACH_SMTP_USER}>"
    msg["To"] = str(to_email).strip()
    msg["Reply-To"] = FN_OUTREACH_SMTP_USER
    msg["Subject"] = str(subject or "").strip()[:240]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="franklinnavigator.com")
    msg["X-Franklin-Message-Type"] = "transactional"
    msg.set_content(str(plain_body or "").rstrip())
    if html_body:
        msg.add_alternative(str(html_body).rstrip(), subtype="html")
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        FN_OUTREACH_SMTP_HOST,
        FN_OUTREACH_SMTP_PORT,
        context=context,
        timeout=30,
    ) as smtp:
        smtp.login(FN_OUTREACH_SMTP_USER, FN_OUTREACH_SMTP_PASSWORD)
        smtp.send_message(msg, to_addrs=[str(to_email).strip()])
    return msg["Message-ID"]


def send_owner_alert_smtp(subject: str, plain_body: str):
    if not FN_OUTREACH_SMTP_PASSWORD:
        raise RuntimeError("FN_OUTREACH_SMTP_PASSWORD is not configured")
    msg = EmailMessage(policy=email_policy.SMTP)
    msg["From"] = f"Franklin Navigator Owner Alerts <{FN_OUTREACH_SMTP_USER}>"
    msg["To"] = FN_OUTREACH_OWNER_TEST_EMAIL
    msg["Reply-To"] = FN_OUTREACH_SMTP_USER
    msg["Subject"] = str(subject or "").strip()[:240]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="franklinnavigator.com")
    msg["X-Franklin-Message-Type"] = "owner-incident-alert"
    msg.set_content(str(plain_body or "").rstrip())
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        FN_OUTREACH_SMTP_HOST,
        FN_OUTREACH_SMTP_PORT,
        context=context,
        timeout=30,
    ) as smtp:
        smtp.login(FN_OUTREACH_SMTP_USER, FN_OUTREACH_SMTP_PASSWORD)
        smtp.send_message(msg, to_addrs=[FN_OUTREACH_OWNER_TEST_EMAIL])
    return msg["Message-ID"]


def send_franklin_smtp_message(to_email: str, subject: str, plain_body: str, html_body: str = "", bcc_email: str = "", outreach_key: str = ""):
    if not FN_OUTREACH_SMTP_PASSWORD:
        raise RuntimeError("FN_OUTREACH_SMTP_PASSWORD is not configured")
    msg = build_franklin_message(to_email, subject, plain_body, html_body)
    if outreach_key:
        msg["X-Franklin-Outreach-Key"] = outreach_key
        msg["X-Franklin-Campaign"] = "FN-FIRST10-2026-09"
    raw = msg.as_bytes(policy=msg.policy)
    include_headers = [
        b"from", b"to", b"reply-to", b"subject", b"date", b"message-id",
        b"list-id", b"list-unsubscribe", b"list-unsubscribe-post", b"feedback-id"
    ]
    if outreach_key:
        include_headers.extend([b"x-franklin-outreach-key", b"x-franklin-campaign"])
    signature = dkim.sign(
        raw,
        selector=FN_OUTREACH_DKIM_SELECTOR.encode("ascii"),
        domain=FN_OUTREACH_DKIM_DOMAIN.encode("ascii"),
        privkey=_direct_dkim_private_key(),
        include_headers=include_headers,
        canonicalize=(b"relaxed", b"relaxed"),
    )
    signed = signature + raw
    recipients = [to_email]
    if bcc_email and bcc_email.lower() != to_email.lower():
        recipients.append(bcc_email)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        FN_OUTREACH_SMTP_HOST,
        FN_OUTREACH_SMTP_PORT,
        context=context,
        timeout=30,
    ) as smtp:
        smtp.login(FN_OUTREACH_SMTP_USER, FN_OUTREACH_SMTP_PASSWORD)
        smtp.sendmail(FN_OUTREACH_SMTP_USER, recipients, signed)
    return msg["Message-ID"]



def _resolved_direct_sequence_path():
    value = FN_DIRECT_SEQUENCE_PATH
    if os.path.isabs(value):
        return value
    if os.path.exists(value):
        return value
    return os.path.join(os.path.dirname(__file__), os.path.basename(value))


def _direct_config_fingerprint(sequence: dict) -> str:
    payload = {
        "release": SRE_BRIDGE_RELEASE,
        "roster": [
            {
                "email": str(x.get("email") or "").strip().lower(),
                "profileId": str(x.get("profileId") or "").strip(),
                "profileUrl": str(x.get("profileUrl") or "").strip(),
            }
            for x in FIRST10_CONTACT_ROSTER
        ],
        "sequence": sequence,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _validate_direct_sequence(sequence: dict):
    if not isinstance(sequence, dict):
        raise RuntimeError("DIRECT_SEQUENCE_INVALID")
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
    steps = sequence.get("steps") or []
    step_ids = [str(x.get("id") or "") for x in steps]
    if step_ids != ["initial", "followup_1", "followup_2"]:
        raise RuntimeError("DIRECT_SEQUENCE_STEP_DRIFT")
    waits = [int(x.get("wait_business_days_after_previous") or 0) for x in steps]
    if waits != [0, 5, 7]:
        raise RuntimeError("DIRECT_SEQUENCE_WAIT_DRIFT")
    for step in steps:
        subject = str(step.get("subject") or "").strip()
        body = str(step.get("body") or "")
        html_body = str(step.get("html_body") or "")
        if not subject or not body or not html_body:
            raise RuntimeError("DIRECT_SEQUENCE_CONTENT_MISSING")
        if "{{Outreach_Greeting}}" not in body or "{{Profile_URL}}" not in body:
            raise RuntimeError("DIRECT_SEQUENCE_PLAIN_TEMPLATE_DRIFT")
        if "{{Outreach_Greeting}}" not in html_body or "{{Profile_URL}}" not in html_body:
            raise RuntimeError("DIRECT_SEQUENCE_HTML_TEMPLATE_DRIFT")
    return sequence


def load_direct_sequence():
    with open(_resolved_direct_sequence_path(), "r", encoding="utf-8") as f:
        sequence = json.load(f)
    return _validate_direct_sequence(sequence)


def _imap_connect():
    if not FN_OUTREACH_SMTP_PASSWORD:
        raise RuntimeError("FN_OUTREACH_SMTP_PASSWORD is not configured")
    client = imaplib.IMAP4_SSL(FN_OUTREACH_IMAP_HOST, FN_OUTREACH_IMAP_PORT)
    client.login(FN_OUTREACH_SMTP_USER, FN_OUTREACH_SMTP_PASSWORD)
    return client


def _imap_select_sent(client):
    candidates = ["Sent", "Sent Messages", "Sent Mail", "INBOX.Sent"]
    for candidate in candidates:
        status, _ = client.select(f'"{candidate}"', readonly=True)
        if status == "OK":
            return candidate
    status, data = client.list()
    if status == "OK":
        for raw in data or []:
            text_value = raw.decode("utf-8", "ignore")
            if "\\Sent" in text_value or re.search(r'(?i)(^|[ "/])sent([ "/]|$)', text_value):
                mailbox = text_value.split(' "/" ')[-1].strip().strip('"')
                status2, _ = client.select(f'"{mailbox}"', readonly=True)
                if status2 == "OK":
                    return mailbox
    raise RuntimeError("Zoho Sent mailbox could not be selected")


def _imap_search_sent_records(client):
    mailbox = _imap_select_sent(client)
    status, data = client.search(None, "HEADER", "X-Franklin-Campaign", "FN-FIRST10-2026-09")
    if status != "OK":
        raise RuntimeError("IMAP sent search failed")
    ids = [x for x in (data[0] or b"").split() if x]
    records = []
    for msg_id in ids[-100:]:
        status2, msg_data = client.fetch(
            msg_id,
            '(BODY.PEEK[HEADER.FIELDS (DATE TO SUBJECT MESSAGE-ID X-FRANKLIN-OUTREACH-KEY X-FRANKLIN-CAMPAIGN)])',
        )
        if status2 != "OK":
            continue
        raw = b"".join(
            part[1] for part in msg_data
            if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray))
        )
        if not raw:
            continue
        msg = BytesParser(policy=email_policy.default).parsebytes(raw)
        dt = None
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(msg.get("Date"))
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = None
        records.append({
            "key": str(msg.get("X-Franklin-Outreach-Key") or "").strip(),
            "to": str(msg.get("To") or "").strip().lower(),
            "subject": str(msg.get("Subject") or "").strip(),
            "messageId": str(msg.get("Message-ID") or "").strip(),
            "date": dt,
        })
    return mailbox, records


def _ensure_send_ledger_mailbox(client):
    status, _ = client.select(f'"{FN_SEND_LEDGER_MAILBOX}"', readonly=True)
    if status == "OK":
        return
    client.create(f'"{FN_SEND_LEDGER_MAILBOX}"')
    status2, _ = client.select(f'"{FN_SEND_LEDGER_MAILBOX}"', readonly=True)
    if status2 != "OK":
        raise RuntimeError("Unable to create outreach ledger mailbox")


def _ledger_records(client):
    _ensure_send_ledger_mailbox(client)
    status, data = client.search(None, "ALL")
    if status != "OK":
        raise RuntimeError("outreach ledger search failed")
    ids = [x for x in (data[0] or b"").split() if x]
    records = []
    for msg_id in ids[-1000:]:
        status2, msg_data = client.fetch(
            msg_id,
            '(BODY.PEEK[HEADER.FIELDS (DATE TO SUBJECT MESSAGE-ID X-FRANKLIN-OUTREACH-KEY X-FRANKLIN-LEDGER-STATUS)])',
        )
        if status2 != "OK":
            continue
        raw = b"".join(
            part[1] for part in msg_data
            if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray))
        )
        if not raw:
            continue
        msg = BytesParser(policy=email_policy.default).parsebytes(raw)
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(msg.get("Date"))
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = None
        records.append({
            "key": str(msg.get("X-Franklin-Outreach-Key") or "").strip(),
            "status": str(msg.get("X-Franklin-Ledger-Status") or "").strip().upper(),
            "to": str(msg.get("To") or "").strip().lower(),
            "subject": str(msg.get("Subject") or "").strip(),
            "messageId": str(msg.get("Message-ID") or "").strip(),
            "date": dt,
        })
    return FN_SEND_LEDGER_MAILBOX, records


def _ledger_has_key(client, key: str):
    _ensure_send_ledger_mailbox(client)
    status, data = client.search(None, "HEADER", "X-Franklin-Outreach-Key", key)
    if status != "OK":
        raise RuntimeError("outreach ledger key search failed")
    return bool((data[0] or b"").strip())


def _append_ledger_marker(client, key: str, email_addr: str, subject: str, status_value: str, message_id: str = ""):
    _ensure_send_ledger_mailbox(client)
    marker = EmailMessage(policy=email_policy.SMTP)
    marker["From"] = FN_OUTREACH_SMTP_USER
    marker["To"] = email_addr
    marker["Subject"] = subject
    marker["Date"] = formatdate(localtime=True)
    marker["Message-ID"] = message_id or make_msgid(domain="franklinnavigator.com")
    marker["X-Franklin-Outreach-Key"] = key
    marker["X-Franklin-Ledger-Status"] = status_value
    marker.set_content("Franklin Navigator outreach send ledger marker.")
    result, _ = client.append(
        f'"{FN_SEND_LEDGER_MAILBOX}"',
        "\\Seen",
        imaplib.Time2Internaldate(time.time()),
        marker.as_bytes(policy=email_policy.SMTP),
    )
    if result != "OK":
        raise RuntimeError("outreach ledger append failed")


def _ledger_reserve(client, key: str, email_addr: str, subject: str):
    if _ledger_has_key(client, key):
        return False
    _append_ledger_marker(client, key, email_addr, subject, "RESERVED")
    return True


def _ledger_mark_sent(client, key: str, email_addr: str, subject: str, message_id: str):
    _append_ledger_marker(client, key, email_addr, subject, "SENT", message_id)


def _imap_has_reply_since(client, sender_email: str, since_dt):
    status, _ = client.select("INBOX", readonly=True)
    if status != "OK":
        raise RuntimeError("IMAP inbox select failed")
    date_text = since_dt.astimezone(timezone.utc).strftime("%d-%b-%Y")
    status, data = client.search(None, "SINCE", date_text, "FROM", sender_email)
    return status == "OK" and bool((data[0] or b"").strip())


def _imap_reply_signal_since(client, sender_email: str, since_dt):
    status, _ = client.select("INBOX", readonly=True)
    if status != "OK":
        raise RuntimeError("IMAP inbox select failed")
    date_text = since_dt.astimezone(timezone.utc).strftime("%d-%b-%Y")
    status, data = client.search(None, "SINCE", date_text, "FROM", sender_email)
    if status != "OK":
        return None
    ids = [x for x in (data[0] or b"").split() if x][-20:]
    if not ids:
        return None
    org_phrases = (
        "do not contact our company",
        "do not contact our organization",
        "remove our organization",
        "remove our company",
        "stop emailing anyone here",
        "stop emailing our company",
        "stop emailing our organization",
        "do not contact this domain",
        "do not email anyone at",
        "do not contact anyone at",
    )
    for msg_id in ids:
        status2, msg_data = client.fetch(
            msg_id,
            "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)] BODY.PEEK[TEXT]<0.8192>)",
        )
        if status2 != "OK":
            continue
        raw = b"".join(
            part[1] for part in msg_data
            if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray))
        )
        blob = raw.decode("utf-8", "ignore").lower()
        if any(phrase in blob for phrase in org_phrases):
            return "org_dnc"
    return "reply"


def _imap_detect_delivery_problem(client, target_email: str, since_dt):
    status, _ = client.select("INBOX", readonly=True)
    if status != "OK":
        raise RuntimeError("IMAP inbox select failed")
    date_text = since_dt.astimezone(timezone.utc).strftime("%d-%b-%Y")
    status, data = client.search(None, "SINCE", date_text, "TEXT", target_email)
    if status != "OK":
        return None
    ids = [x for x in (data[0] or b"").split() if x][-30:]
    for msg_id in ids:
        status2, msg_data = client.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT CONTENT-TYPE)] BODY.PEEK[TEXT]<0.4096>)")
        if status2 != "OK":
            continue
        raw = b"".join(
            part[1] for part in msg_data
            if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray))
        )
        blob = raw.decode("utf-8", "ignore").lower()
        if any(x in blob for x in ("feedback-report", "abuse report", "spam complaint", "complaint feedback")):
            return "complaint"
        if any(x in blob for x in (
            "delivery status notification", "undeliverable", "mail delivery subsystem",
            "delivery failed", "returned mail", "failure notice", "message not delivered"
        )):
            return "bounce"
    return None


_unsubscribe_cache = {"checkedAt": 0.0, "emails": set()}


def _mailshake_unsubscribe_set(force=False):
    now_ts = time.time()
    if not force and now_ts - float(_unsubscribe_cache.get("checkedAt") or 0) < 900:
        return set(_unsubscribe_cache.get("emails") or set())
    request_result = mailshake_api(
        "POST",
        "/campaigns/export",
        json={"exportType": "unsubscribes", "timezone": "UTC"},
    ) or {}
    status_id = request_result.get("checkStatusID")
    if not status_id:
        raise RuntimeError("Mailshake unsubscribe export did not return status ID")
    export_result = None
    for _ in range(10):
        export_result = mailshake_api(
            "GET",
            "/campaigns/export-status",
            params={"statusID": status_id},
        ) or {}
        if export_result.get("isFinished"):
            break
        time.sleep(1)
    url = (export_result or {}).get("csvDownloadUrl")
    if not url:
        raise RuntimeError("Mailshake unsubscribe export did not finish")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    emails = set()
    reader = csv.reader(io.StringIO(response.text))
    for row in reader:
        for cell in row:
            value = str(cell or "").strip().lower()
            if "@" in value and " " not in value:
                emails.add(value.strip('"<> '))
    _unsubscribe_cache["checkedAt"] = now_ts
    _unsubscribe_cache["emails"] = emails
    return set(emails)


def _business_days_between(start_dt, end_dt, tz):
    start_date = start_dt.astimezone(tz).date()
    end_date = end_dt.astimezone(tz).date()
    count = 0
    current = start_date
    while current < end_date:
        current = current.fromordinal(current.toordinal() + 1)
        if current.weekday() < 5:
            count += 1
    return count


def _within_direct_send_window(now_local, sequence):
    window = sequence.get("send_window") or {}
    if now_local.weekday() >= 5:
        return False
    start_h, start_m = [int(x) for x in str(window.get("start") or "09:00").split(":")]
    end_h, end_m = [int(x) for x in str(window.get("end") or "16:00").split(":")]
    minutes = now_local.hour * 60 + now_local.minute
    return start_h * 60 + start_m <= minutes < end_h * 60 + end_m


def _profile_url_preflight(recipient: dict):
    profile_url = str(recipient.get("profileUrl") or "").strip()
    profile_id = str(recipient.get("profileId") or "").strip()
    parsed = urlparse(profile_url)
    if parsed.scheme != "https" or parsed.hostname not in {"franklinnavigator.com", "www.franklinnavigator.com"}:
        raise RuntimeError("PROFILE_URL_INVALID_HOST")
    if not profile_id or profile_id not in parsed.path:
        raise RuntimeError("PROFILE_URL_ID_MISMATCH")
    response = requests.get(
        profile_url,
        timeout=20,
        allow_redirects=True,
        headers={"User-Agent": "FranklinNavigator-Profile-Preflight/1.0"},
    )
    if response.status_code < 200 or response.status_code >= 400:
        raise RuntimeError(f"PROFILE_URL_HTTP_{response.status_code}")
    final = urlparse(response.url)
    if final.hostname not in {"franklinnavigator.com", "www.franklinnavigator.com"}:
        raise RuntimeError("PROFILE_URL_REDIRECTED_OFF_DOMAIN")
    return response.status_code


def profile_preflight_once():
    failures = []
    passed = 0
    for recipient in FIRST10_CONTACT_ROSTER:
        try:
            status = _profile_url_preflight(recipient)
            passed += 1
            print(
                "SRE_BRIDGE PROFILE_PREFLIGHT PASS "
                + json.dumps({"email": recipient.get("email"), "profileId": recipient.get("profileId"), "status": status}, sort_keys=True),
                flush=True,
            )
        except Exception as exc:
            failures.append({"email": recipient.get("email"), "profileId": recipient.get("profileId"), "error": str(exc)})
            print(
                "SRE_BRIDGE PROFILE_PREFLIGHT FAIL "
                + json.dumps(failures[-1], sort_keys=True),
                flush=True,
            )
    print(
        "SRE_BRIDGE PROFILE_PREFLIGHT SUMMARY "
        + json.dumps({"passed": passed, "failed": len(failures)}, sort_keys=True),
        flush=True,
    )


def _render_direct_body(template: str, recipient: dict):
    return (
        str(template or "")
        .replace("{{Outreach_Greeting}}", str(recipient.get("outreachGreeting") or recipient.get("business") or "there"))
        .replace("{{Profile_URL}}", str(recipient.get("profileUrl") or ""))
    )


def _direct_record_map(records):
    mapped = {}
    for item in records:
        key = item.get("key") or ""
        if key:
            mapped[key] = item
    return mapped


def _direct_key(email: str, step_id: str):
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"fn-first10:{digest}:{step_id}"


def _direct_scan_once(send_if_due=False):
    checked_at = now_iso()
    sequence = load_direct_sequence()
    tz = ZoneInfo(sequence.get("timezone") or "America/Chicago")
    now_local = datetime.now(tz)
    alerts = []
    with _imap_connect() as client:
        sent_mailbox, records = _ledger_records(client)
        for seed_email, seed_iso in FIRST10_INCIDENT_SEEDED_SENT_AT.items():
            seed_key = _direct_key(seed_email, "initial")
            if not any(r.get("key") == seed_key and r.get("status") == "SENT" for r in records):
                records.append({"key": seed_key, "status": "SENT", "to": seed_email, "subject": "Your Franklin Navigator community profile", "messageId": "INCIDENT-SEED", "date": datetime.fromisoformat(seed_iso)})
        sent_records = [r for r in records if r.get("status") == "SENT"]
        record_map = _direct_record_map(sent_records)
        sent_keys = {str(r.get("key") or "") for r in sent_records if r.get("key")}
        reserved_without_sent = sorted({
            str(r.get("key") or "")
            for r in records
            if r.get("status") == "RESERVED"
            and r.get("key")
            and str(r.get("key") or "") not in sent_keys
        })
        unsubscribed = _zoho_suppression_set()
        zoho_domain_suppressions = _zoho_domain_suppression_set()
        suppressed = []
        bounce_holds = []
        complaint_holds = []
        stopped_replies = []
        next_eligible = []
        initial_sent = followup1_sent = followup2_sent = 0
        roster_emails = {str(x.get("email") or "").strip().lower() for x in FIRST10_CONTACT_ROSTER}
        pilot_unsubs = sorted(roster_emails & unsubscribed)
        global_hold = f"PILOT_UNSUBSCRIBE:{pilot_unsubs[0]}" if pilot_unsubs else None
        if reserved_without_sent:
            global_hold = global_hold or f"AMBIGUOUS_SEND_RESERVATION:{reserved_without_sent[0]}"
            alerts.append({
                "priority": "HIGH",
                "triggerType": "AMBIGUOUS_SEND_RESERVATION",
                "outreachKey": reserved_without_sent[0],
                "automaticAction": "DIRECT_OUTREACH_HOLD",
            })

        expected_initial_keys = {
            _direct_key(str(x.get("email") or "").strip().lower(), "initial")
            for x in FIRST10_CONTACT_ROSTER
        }
        missing_closed_initial_keys = sorted(expected_initial_keys - set(record_map.keys()))
        if FN_INITIAL_COHORT_CLOSED and missing_closed_initial_keys:
            global_hold = global_hold or "INITIAL_COHORT_CLOSED_LEDGER_MISMATCH"
            alerts.append({
                "priority": "HIGH",
                "triggerType": "INITIAL_COHORT_CLOSED_LEDGER_MISMATCH",
                "missingCount": len(missing_closed_initial_keys),
                "automaticAction": "DIRECT_OUTREACH_HOLD",
            })

        dated_records = [r for r in sent_records if r.get("date")]
        last_send_dt = max([r["date"] for r in dated_records], default=None)
        today = now_local.date()
        sends_today = sum(
            1 for r in dated_records
            if r["date"].astimezone(tz).date() == today
        )

        for recipient in FIRST10_CONTACT_ROSTER:
            email_addr = str(recipient.get("email") or "").strip().lower()
            domain = email_domain(email_addr)
            if email_addr in unsubscribed:
                suppressed.append(email_addr)
                continue
            safety_state = load_org_safety_state()
            if domain in zoho_domain_suppressions or domain in (safety_state.get("domain_holds") or {}) or domain in (safety_state.get("domain_suppressions") or {}):
                suppressed.append(email_addr)
                continue

            previous_record = None
            for index, step in enumerate(sequence.get("steps") or []):
                step_id = str(step.get("id") or "")
                key = _direct_key(email_addr, step_id)
                if email_addr in FIRST10_INCIDENT_NO_FOLLOWUP_EMAILS and step_id != "initial":
                    break
                sent_record = record_map.get(key)
                if sent_record:
                    if step_id == "initial":
                        initial_sent += 1
                    elif step_id == "followup_1":
                        followup1_sent += 1
                    elif step_id == "followup_2":
                        followup2_sent += 1
                    previous_record = sent_record
                    continue

                if index == 0:
                    eligible = not FN_INITIAL_COHORT_CLOSED
                else:
                    if not previous_record or not previous_record.get("date"):
                        eligible = False
                    else:
                        reply_signal = _imap_reply_signal_since(client, email_addr, previous_record["date"])
                        if reply_signal:
                            stopped_replies.append(email_addr)
                            if reply_signal == "org_dnc":
                                _persist_zoho_domain_suppression(domain, "organization_wide_do_not_contact")
                                global_hold = global_hold or f"ORGANIZATION_WIDE_DNC:{domain}"
                                alerts.append({
                                    "priority": "HIGH",
                                    "triggerType": "ORGANIZATION_WIDE_DO_NOT_CONTACT",
                                    "domain": domain,
                                    "email": email_addr,
                                    "automaticAction": "DOMAIN_SUPPRESSION_AND_DIRECT_OUTREACH_HOLD",
                                })
                            eligible = False
                            break
                        problem = _imap_detect_delivery_problem(client, email_addr, previous_record["date"])
                        if problem == "bounce":
                            bounce_holds.append(email_addr)
                            try:
                                _persist_zoho_suppression(email_addr, "bounce")
                            except Exception:
                                pass
                            global_hold = global_hold or f"PILOT_BOUNCE:{email_addr}"
                            alerts.append({"priority":"HIGH","triggerType":"BOUNCE","email":email_addr,"automaticAction":"RECIPIENT_SUPPRESSION_AND_DIRECT_OUTREACH_HOLD"})
                            eligible = False
                            break
                        if problem == "complaint":
                            complaint_holds.append(email_addr)
                            try:
                                _persist_zoho_suppression(email_addr, "complaint")
                            except Exception:
                                pass
                            global_hold = global_hold or f"PILOT_COMPLAINT:{email_addr}"
                            alerts.append({"priority":"HIGH","triggerType":"SPAM_COMPLAINT","email":email_addr,"domain":domain,"automaticAction":"RECIPIENT_SUPPRESSION_AND_DIRECT_OUTREACH_HOLD"})
                            eligible = False
                            break
                        wait_days = int(step.get("wait_business_days_after_previous") or 0)
                        eligible = _business_days_between(previous_record["date"], datetime.now(timezone.utc), tz) >= wait_days

                if eligible:
                    next_eligible.append({"email": email_addr, "step": step_id})
                    initial_override = FN_INITIAL_SEND_OVERRIDE and step_id == "initial"
                    if send_if_due and not global_hold and (_within_direct_send_window(now_local, sequence) or initial_override):
                        min_gap = int((sequence.get("send_window") or {}).get("minimum_minutes_between_sends") or 12)
                        if last_send_dt and (datetime.now(timezone.utc) - last_send_dt.astimezone(timezone.utc)).total_seconds() < min_gap * 60:
                            break
                        max_daily = int((sequence.get("send_window") or {}).get("max_daily_initial_sends") or 10)
                        if sends_today >= max_daily:
                            break
                        subject = str(step.get("subject") or "").strip()
                        body = _render_direct_body(step.get("body") or "", recipient)
                        html_body = _render_direct_body(step.get("html_body") or "", recipient)
                        profile_url = str(recipient.get("profileUrl") or "").strip()
                        if "{{" in body or "{{" in html_body:
                            global_hold = global_hold or f"RENDER_PLACEHOLDER_ERROR:{email_addr}"
                            alerts.append({"priority":"HIGH","triggerType":"MESSAGE_RENDER_ERROR","email":email_addr})
                            break
                        if profile_url not in body or profile_url not in html_body:
                            global_hold = global_hold or f"PROFILE_LINK_RENDER_ERROR:{email_addr}"
                            alerts.append({"priority":"HIGH","triggerType":"PROFILE_LINK_RENDER_ERROR","email":email_addr})
                            break
                        try:
                            _profile_url_preflight(recipient)
                        except Exception as exc:
                            global_hold = global_hold or f"PROFILE_URL_PREFLIGHT_FAIL:{email_addr}"
                            alerts.append({"priority":"HIGH","triggerType":"PROFILE_URL_PREFLIGHT_FAIL","email":email_addr,"error":str(exc)})
                            break
                        if not _ledger_reserve(client, key, email_addr, subject):
                            break
                        message_id = send_franklin_smtp_message(
                            email_addr,
                            subject,
                            body,
                            html_body=html_body,
                            bcc_email=str(sequence.get("owner_bcc") or ""),
                            outreach_key=key,
                        )
                        _ledger_mark_sent(client, key, email_addr, subject, message_id)
                        print(
                            "SRE_BRIDGE DIRECT_OUTREACH_SENT "
                            + json.dumps(
                                {"email": email_addr, "step": step_id, "messageId": message_id, "at": now_iso()},
                                sort_keys=True,
                            ),
                            flush=True,
                        )
                        last_send_dt = datetime.now(timezone.utc)
                        sends_today += 1
                    break

        summary = {
            "enabled": FN_DIRECT_OUTREACH_ENABLED,
            "lastCheckedAt": checked_at,
            "sentMailbox": sent_mailbox,
            "imapConnection": "PASS",
            "campaignId": sequence.get("campaign_id"),
            "release": SRE_BRIDGE_RELEASE,
            "configurationFingerprint": _direct_config_fingerprint(sequence),
            "rosterCount": len(FIRST10_CONTACT_ROSTER),
            "ownerBcc": str(sequence.get("owner_bcc") or ""),
            "initialCohortClosed": FN_INITIAL_COHORT_CLOSED,
            "pilotInitialComplete": initial_sent == len(FIRST10_CONTACT_ROSTER),
            "reservedWithoutSent": reserved_without_sent,
            "initialSent": initial_sent,
            "followup1Sent": followup1_sent,
            "followup2Sent": followup2_sent,
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
        with _state_lock:
            _state["directOutreach"].update(summary)
        print(
            "SRE_BRIDGE DIRECT_OUTREACH_STATUS "
            + json.dumps(
                {
                    "enabled": summary["enabled"],
                    "initialSent": summary["initialSent"],
                    "followup1Sent": summary["followup1Sent"],
                    "followup2Sent": summary["followup2Sent"],
                    "suppressedCount": len(summary["suppressed"]),
                    "stoppedForReplyCount": len(summary["stoppedForReply"]),
                    "globalHold": summary["globalHold"],
                    "nextEligibleCount": len(summary["nextEligible"]),
                    "imapConnection": summary["imapConnection"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return summary


def seed_suppression_store_once():
    try:
        _persist_zoho_suppression(FN_OUTREACH_OWNER_TEST_EMAIL, "owner_controlled_compliance_test_unsubscribe_migration")
        print("SRE_BRIDGE SUPPRESSION_SEED PASS", flush=True)
    except Exception as exc:
        print(f"SRE_BRIDGE SUPPRESSION_SEED FAIL {exc}", flush=True)


def direct_outreach_runner():
    while True:
        try:
            _direct_scan_once(send_if_due=FN_DIRECT_OUTREACH_ENABLED)
        except Exception as exc:
            with _state_lock:
                _state["directOutreach"].update({
                    "lastCheckedAt": now_iso(),
                    "imapConnection": "FAIL",
                    "error": str(exc),
                    "globalHold": "DIRECT_OUTREACH_MONITOR_ERROR",
                })
            print(f"SRE_BRIDGE DIRECT_OUTREACH ERROR {exc}", flush=True)
        time.sleep(60)


def send_owner_rfc8058_test_once():
    try:
        message_id = send_franklin_smtp_message(
            FN_OUTREACH_OWNER_TEST_EMAIL,
            "Franklin Navigator RFC 8058 compliance test",
            "This is a controlled Franklin Navigator RFC 8058 compliance test. No action is required.",
        )
        print(
            "SRE_BRIDGE RFC8058_OWNER_TEST SENT "
            + json.dumps({"to": FN_OUTREACH_OWNER_TEST_EMAIL, "messageId": message_id}, sort_keys=True),
            flush=True,
        )
    except Exception as exc:
        print(f"SRE_BRIDGE RFC8058_OWNER_TEST ERROR {exc}", flush=True)

def run_one_click_self_test_once():
    try:
        time.sleep(3)
        token = make_unsubscribe_token(FN_OUTREACH_OWNER_TEST_EMAIL)
        url = f"{FN_OUTREACH_PUBLIC_BASE_URL}/unsubscribe/one-click/{token}"
        response = requests.post(
            url,
            data="List-Unsubscribe=One-Click",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"HTTP_{response.status_code}:{response.text[:200]}")
        print(
            "SRE_BRIDGE ONE_CLICK_SELF_TEST PASS "
            + json.dumps({"status": response.status_code, "at": now_iso()}, sort_keys=True),
            flush=True,
        )
    except Exception as exc:
        print(f"SRE_BRIDGE ONE_CLICK_SELF_TEST FAIL {exc}", flush=True)




@app.post("/unsubscribe/one-click/{token}", response_class=PlainTextResponse)
async def one_click_unsubscribe(token: str, request: Request):
    email = parse_unsubscribe_token(token)
    body = (await request.body()).decode("utf-8", "ignore")
    if "List-Unsubscribe=One-Click" not in body:
        raise HTTPException(status_code=400, detail="Invalid one-click unsubscribe request")
    persist_unsubscribe(email)
    return "Unsubscribed"


@app.post("/unsubscribe/confirm/{token}", response_class=HTMLResponse)
async def confirm_visible_unsubscribe(token: str, request: Request):
    email = parse_unsubscribe_token(token)
    body = (await request.body()).decode("utf-8", "ignore")
    values = parse_qs(body)
    if values.get("confirm", [""])[0] != "1":
        raise HTTPException(status_code=400, detail="Confirmation required")
    persist_unsubscribe(email)
    return HTMLResponse(
        "<html><body><h1>Unsubscribed</h1><p>You will not receive further Franklin Navigator outreach at this address.</p></body></html>"
    )


@app.get("/unsubscribe/{token}", response_class=HTMLResponse)
def visible_unsubscribe(token: str):
    parse_unsubscribe_token(token)
    safe_token = re.sub(r"[^A-Za-z0-9_.-]", "", token)
    return HTMLResponse(
        "<html><body><h1>Unsubscribe from Franklin Navigator outreach</h1>"
        "<p>Click the button below to stop future Franklin Navigator outreach at this email address.</p>"
        f'<form method="post" action="/unsubscribe/confirm/{safe_token}">'
        '<input type="hidden" name="confirm" value="1">'
        '<button type="submit">Unsubscribe</button></form></body></html>'
    )



def load_org_safety_policy():
    with open(ORG_SAFETY_POLICY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_org_safety_state():
    with open(ORG_SAFETY_STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def email_domain(email):
    value = str(email or "").strip().lower()
    if "@" not in value:
        return ""
    return value.rsplit("@", 1)[1].strip().rstrip(".")


def is_generic_or_role_inbox(email):
    value = str(email or "").strip().lower()
    local = value.split("@", 1)[0] if "@" in value else value
    role_names = {
        "info", "contact", "office", "admin", "hello", "support", "team",
        "general", "sales", "events", "catering", "firm", "mail", "inquiries",
        "reception", "community", "marketing"
    }
    return local in role_names


def reply_recipient_email(item):
    recipient = item.get("recipient") or {}
    candidates = [
        recipient.get("emailAddress"),
        recipient.get("email"),
        item.get("emailAddress"),
        item.get("email"),
        item.get("recipientEmailAddress"),
    ]
    for candidate in candidates:
        if candidate and "@" in str(candidate):
            return str(candidate).strip().lower()
    return ""


def explicit_org_wide_dnc(item):
    # Intentionally narrow: individual unsubscribe must remain individual by default.
    text_blob = json.dumps(item, sort_keys=True).lower()
    phrases = (
        "do not contact our company",
        "do not contact our organization",
        "remove our organization",
        "remove our company",
        "stop emailing anyone here",
        "stop emailing our company",
        "stop emailing our organization",
        "do not contact this domain",
        "do not email anyone at",
        "do not contact anyone at",
    )
    return any(phrase in text_blob for phrase in phrases)


def detect_org_negative_signals(replies):
    complaint_domains = set()
    org_dnc_domains = set()
    for item in replies:
        reply_type = str(item.get("type") or "").strip().lower()
        email = reply_recipient_email(item)
        domain = email_domain(email)
        if not domain:
            continue
        if reply_type in {"spam", "spam-complaint", "spam_complaint", "complaint", "abuse"}:
            complaint_domains.add(domain)
        if explicit_org_wide_dnc(item):
            org_dnc_domains.add(domain)
    return sorted(complaint_domains), sorted(org_dnc_domains)


def organizations_for_domain(domain):
    names = []
    for item in FIRST10_CONTACT_ROSTER:
        if email_domain(item.get("email")) == domain:
            name = str(item.get("business") or "").strip()
            if name and name not in names:
                names.append(name)
    return names


def build_owner_alerts(complaint_domains, org_dnc_domains):
    now = now_iso()
    alerts = []
    for domain in complaint_domains:
        organizations = organizations_for_domain(domain)
        alerts.append({
            "id": f"spam-complaint:{domain}",
            "priority": "HIGH",
            "triggerType": "SPAM_COMPLAINT",
            "organizationNames": organizations,
            "domain": domain,
            "affectedScope": "COMPANY_DOMAIN",
            "sourceEvidence": "MAILSHAKE_REPLY_ACTIVITY",
            "automaticAction": "DOMAIN_HOLD_AND_CAMPAIGN_PAUSE",
            "pendingMessagesAction": "CAMPAIGN_PAUSED_PENDING_OWNER_REVIEW",
            "state": "HOLD",
            "ownerDecisionRequired": True,
            "acknowledgmentRequired": True,
            "detectedAt": now,
            "persistenceReconciliationRequired": True,
        })
    for domain in org_dnc_domains:
        organizations = organizations_for_domain(domain)
        alerts.append({
            "id": f"org-dnc:{domain}",
            "priority": "HIGH",
            "triggerType": "ORGANIZATION_WIDE_DO_NOT_CONTACT",
            "organizationNames": organizations,
            "domain": domain,
            "affectedScope": "COMPANY_DOMAIN",
            "sourceEvidence": "MAILSHAKE_REPLY_ACTIVITY_EXPLICIT_ORG_WIDE_LANGUAGE",
            "automaticAction": "DOMAIN_SUPPRESSION_AND_CAMPAIGN_PAUSE",
            "pendingMessagesAction": "CAMPAIGN_PAUSED_AND_DOMAIN_BLOCKED_PENDING_PERSISTENCE_RECONCILIATION",
            "state": "SUPPRESSED",
            "ownerDecisionRequired": True,
            "acknowledgmentRequired": True,
            "detectedAt": now,
            "persistenceReconciliationRequired": True,
        })
    return alerts


def load_deliverability_policy():
    with open(DELIVERABILITY_POLICY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def policy_pause_reason(sent_count, bounce_count, unsubscribe_count, roster_exact, campaign, duplicate_domains, held_domains, suppressed_domains, complaint_domains, org_dnc_domains):
    policy = load_deliverability_policy()
    current = policy.get("current_pilot") or {}
    compliance = policy.get("compliance") or {}
    current_campaign_id = int(current.get("campaign_id") or 0)
    current_daily_cap = int(current.get("max_daily_sends") or 0)
    low_volume_exception = compliance.get("rfc8058_low_volume_pilot_exception") or {}
    approved_exception = (
        bool(low_volume_exception.get("approved_by_owner"))
        and int(low_volume_exception.get("applies_only_to_current_pilot_campaign_id") or 0) == current_campaign_id
        and current_campaign_id == MAILSHAKE_CAMPAIGN_ID
        and current_daily_cap <= int(low_volume_exception.get("max_daily_sends") or 10)
    )
    if MAILSHAKE_COMPLIANCE_HOLD and not approved_exception:
        return "COMPLIANCE_FOOTER_AND_UNSUBSCRIBE_CONFIRMATION_REQUIRED"
    if current_daily_cap > 10 and not RFC8058_SCALE_PROOF:
        return "RFC8058_SCALE_PROOF_REQUIRED"
    if complaint_domains:
        return "SPAM_COMPLAINT_DOMAIN_HOLD"
    if org_dnc_domains:
        return "ORGANIZATION_WIDE_DNC_DOMAIN_SUPPRESSION"
    if held_domains:
        return "DURABLE_DOMAIN_HOLD_PRESENT"
    if suppressed_domains:
        return "DURABLE_DOMAIN_SUPPRESSION_PRESENT"
    if duplicate_domains:
        return "CURRENT_PILOT_DOMAIN_24H_THROTTLE_RISK"
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

    recipient_domains = [
        email_domain(item.get("emailAddress"))
        for item in recipients
        if email_domain(item.get("emailAddress"))
    ]
    domain_counts = {}
    for domain in recipient_domains:
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
    duplicate_domains = sorted(
        domain for domain, count in domain_counts.items() if count > 1
    )
    generic_inbox_count = sum(
        1 for item in recipients if is_generic_or_role_inbox(item.get("emailAddress"))
    )

    org_state = load_org_safety_state()
    durable_holds = set((org_state.get("domain_holds") or {}).keys())
    durable_suppressions = set((org_state.get("domain_suppressions") or {}).keys())
    held_domains = sorted(set(recipient_domains) & durable_holds)
    suppressed_domains = sorted(set(recipient_domains) & durable_suppressions)
    complaint_domains, org_dnc_domains = detect_org_negative_signals(replies)
    runtime_owner_alerts = build_owner_alerts(complaint_domains, org_dnc_domains)

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
        duplicate_domains,
        held_domains,
        suppressed_domains,
        complaint_domains,
        org_dnc_domains,
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
        "genericInboxCount": generic_inbox_count,
        "duplicateDomains": duplicate_domains,
        "domainHolds": sorted(set(held_domains) | set(complaint_domains)),
        "domainSuppressions": sorted(set(suppressed_domains) | set(org_dnc_domains)),
        "ownerAlerts": runtime_owner_alerts,
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
                "genericInboxes": summary["genericInboxCount"],
                "duplicateDomains": summary["duplicateDomains"],
                "domainHolds": summary["domainHolds"],
                "domainSuppressions": summary["domainSuppressions"],
                "ownerAlerts": len(summary["ownerAlerts"]),
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
        f"SRE_BRIDGE startup release={SRE_BRIDGE_RELEASE} apiKeyConfigured={bool(REPLY_API_KEY)} replySyncEnabled={REPLY_SYNC_ENABLED} mailshakeApiKeyConfigured={bool(MAILSHAKE_API_KEY)} mailshakeCampaignId={MAILSHAKE_CAMPAIGN_ID} complianceHold={MAILSHAKE_COMPLIANCE_HOLD} sequenceId={SEQUENCE_ID} configPath={CONFIG_PATH} prospectCount={startup_count}",
        flush=True,
    )
    if MAILSHAKE_RUNTIME_ENABLED and MAILSHAKE_API_KEY:
        threading.Thread(target=test_mailshake_connection, daemon=True).start()
        if MAILSHAKE_COMPLIANCE_TEST_CAMPAIGN_ID > 0:
            threading.Thread(target=log_compliance_test_status_once, daemon=True).start()
    if MAILSHAKE_RUNTIME_ENABLED and MAILSHAKE_API_KEY and MAILSHAKE_CAMPAIGN_ID > 0:
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
    if FN_OUTREACH_OWNER_TEST_ON_STARTUP:
        threading.Thread(target=send_owner_rfc8058_test_once, daemon=True).start()
    if FN_ONE_CLICK_SELF_TEST_ON_STARTUP:
        threading.Thread(target=run_one_click_self_test_once, daemon=True).start()
    threading.Thread(target=direct_outreach_runner, daemon=True).start()
    threading.Thread(target=profile_preflight_once, daemon=True).start()
    if FN_SUPPRESSION_SEED_ON_STARTUP:
        threading.Thread(target=seed_suppression_store_once, daemon=True).start()


@app.post("/transactional/send")
async def transactional_send(request: Request):
    if not FN_TRANSACTIONAL_BRIDGE_SECRET:
        raise HTTPException(status_code=503, detail="Transactional bridge is not configured")
    supplied = str(request.headers.get("X-Franklin-Transactional-Secret") or "")
    if not hmac.compare_digest(supplied, FN_TRANSACTIONAL_BRIDGE_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    to_email = str(payload.get("to") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    text_body = str(payload.get("text") or "").strip()
    html_body = str(payload.get("html") or "").strip()
    allowed_subjects = (
        "Reset your Franklin Navigator password",
        "Your Franklin Navigator profile access was approved",
        "More information is needed for your Franklin Navigator profile request",
        "Update on your Franklin Navigator profile-access request",
        "Your Franklin Navigator profile access changed",
    )
    if subject not in allowed_subjects:
        raise HTTPException(status_code=400, detail="Unsupported transactional subject")
    if not text_body or len(text_body) > 30000 or len(html_body) > 60000:
        raise HTTPException(status_code=400, detail="Invalid body")
    message_id = send_franklin_transactional_smtp(to_email, subject, text_body, html_body)
    print(
        "SRE_BRIDGE TRANSACTIONAL_SENT "
        + json.dumps({"messageId": message_id, "subject": subject, "at": now_iso()}, sort_keys=True),
        flush=True,
    )
    return {"ok": True, "messageId": message_id}


@app.post("/owner-alert/send")
async def owner_alert_send(request: Request):
    if not FN_OWNER_ALERT_BRIDGE_SECRET:
        raise HTTPException(status_code=503, detail="Owner alert bridge is not configured")
    supplied = str(request.headers.get("X-Franklin-Owner-Alert-Secret") or "")
    if not hmac.compare_digest(supplied, FN_OWNER_ALERT_BRIDGE_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    subject = str(payload.get("subject") or "").strip()
    body = str(payload.get("text") or "").strip()
    if not subject.startswith("[Franklin Navigator] "):
        raise HTTPException(status_code=400, detail="Invalid subject")
    if not body or len(body) > 20000:
        raise HTTPException(status_code=400, detail="Invalid body")
    message_id = send_owner_alert_smtp(subject, body)
    print(
        "SRE_BRIDGE OWNER_ALERT_SENT "
        + json.dumps({"messageId": message_id, "at": now_iso()}, sort_keys=True),
        flush=True,
    )
    return {"ok": True, "messageId": message_id}


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
        "rfc8058ScaleProof": RFC8058_SCALE_PROOF,
        "fnSmtpConfigured": bool(FN_OUTREACH_SMTP_PASSWORD),
        "ownerAlertBridgeConfigured": bool(FN_OWNER_ALERT_BRIDGE_SECRET),
        "transactionalBridgeConfigured": bool(FN_TRANSACTIONAL_BRIDGE_SECRET),
        "fnUnsubscribeSigningConfigured": bool(FN_UNSUBSCRIBE_SIGNING_SECRET),
        "fnDirectDkimConfigured": bool(FN_OUTREACH_DKIM_PRIVATE_KEY_B64),
        "fnDirectOutreachEnabled": FN_DIRECT_OUTREACH_ENABLED,
        "fnInitialSendOverride": FN_INITIAL_SEND_OVERRIDE,
        "fnInitialCohortClosed": FN_INITIAL_COHORT_CLOSED,
        "mailshakeRequiredForDirectOutreach": False,
        "mailshakeRuntimeEnabled": MAILSHAKE_RUNTIME_ENABLED,
        "directSuppressionStore": "ZOHO_IMAP",
        "directSendLedger": "ZOHO_IMAP_OUTREACH_LEDGER",
    }


def log_compliance_test_status_once():
    try:
        status = mailshake_compliance_test_status()
        print(
            "SRE_BRIDGE COMPLIANCE_TEST_STATUS " + json.dumps(status, sort_keys=True),
            flush=True,
        )
    except Exception as exc:
        print(f"SRE_BRIDGE COMPLIANCE_TEST_STATUS ERROR {exc}", flush=True)


@app.get("/mailshake/compliance-test/status")
def mailshake_compliance_test_status():
    campaign_id = MAILSHAKE_COMPLIANCE_TEST_CAMPAIGN_ID
    campaign = mailshake_api(
        "GET",
        "/campaigns/get",
        params={"campaignID": campaign_id},
    ) or {}
    recipients = mailshake_paginated(
        "/recipients/list",
        {"campaignID": campaign_id},
        per_page=100,
    )
    replies = mailshake_paginated(
        "/activity/replies",
        {"campaignID": campaign_id},
        per_page=100,
    )
    sent = mailshake_paginated(
        "/activity/sent",
        {"campaignID": campaign_id, "excludeBody": "true"},
        per_page=100,
    )
    recipient_summaries = []
    for item in recipients:
        recipient_summaries.append({
            "emailAddress": item.get("emailAddress"),
            "status": item.get("status"),
            "isUnsubscribed": item.get("isUnsubscribed"),
            "unsubscribed": item.get("unsubscribed"),
            "unsubscribeDate": item.get("unsubscribeDate"),
            "isPaused": item.get("isPaused"),
            "paused": item.get("paused"),
            "state": item.get("state"),
        })
    reply_types = [str(item.get("type") or "").strip().lower() for item in replies]
    return {
        "campaignId": campaign_id,
        "campaignTitle": campaign.get("title"),
        "campaignPaused": campaign.get("isPaused"),
        "recipientCount": len(recipients),
        "sentCount": len(sent),
        "unsubscribeActivityCount": sum(1 for value in reply_types if value == "unsubscribe"),
        "replyTypes": reply_types,
        "recipients": recipient_summaries,
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
        "genericInboxCount": ms.get("genericInboxCount"),
        "duplicateDomains": ms.get("duplicateDomains"),
        "domainHolds": ms.get("domainHolds"),
        "domainSuppressions": ms.get("domainSuppressions"),
        "ownerAlertCount": len(ms.get("ownerAlerts") or []),
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


@app.get("/direct-outreach/status")
def direct_outreach_status():
    with _state_lock:
        return dict(_state["directOutreach"])


@app.get("/owner/alerts")
def owner_alerts():
    with _state_lock:
        alerts = list(_state["mailshake"].get("ownerAlerts") or [])
    return {
        "ok": True,
        "ruleId": load_org_safety_policy().get("rule_id"),
        "count": len(alerts),
        "alerts": alerts,
    }


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
