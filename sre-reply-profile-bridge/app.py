import json
import os
import re
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI

API_BASE = "https://api.reply.io/v3"
REPLY_API_KEY = os.environ.get("REPLY_API_KEY", "").strip()
SEQUENCE_ID = int(os.environ.get("REPLY_SEQUENCE_ID", "1768444"))
SYNC_INTERVAL_SECONDS = int(os.environ.get("SYNC_INTERVAL_SECONDS", "900"))
CONFIG_PATH = os.environ.get(
    "PROSPECT_CONFIG_PATH",
    os.path.join(os.path.dirname(__file__), "prospects.json"),
)

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

app = FastAPI(title="SRE Reply Profile Bridge", version="1.0.0")
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
    "error": None,
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


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("sequenceId") and int(data["sequenceId"]) != SEQUENCE_ID:
        raise RuntimeError("Configured sequenceId does not match REPLY_SEQUENCE_ID")
    return data


def normalize_text(value):
    return re.sub(r"\s+", " ", (value or "")).strip().lower()


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
    if expected_business not in h1 and h1 not in expected_business:
        return False, f"PROFILE_NAME_MISMATCH:{h1}"

    claim_href = f"/claim-profile/?profile={profile_id}"
    if not soup.find("a", href=claim_href):
        return False, "PROFILE_CLAIM_ACTION_MISSING"

    return True, "PASS"


def contact_get(contact_id):
    return api("GET", f"/contacts/{contact_id}")


def merge_custom_fields(contact, values):
    current = {}
    for item in contact.get("customFields") or []:
        key = item.get("key")
        if key:
            current[key] = str(item.get("value") or "")
    current.update(values)
    return [{"key": key, "value": value} for key, value in current.items()]


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

    custom_fields = merge_custom_fields(
        contact,
        {
            PROFILE_FIELD: prospect["profileUrl"],
            PROFILE_ID_FIELD: prospect["profileId"],
            GREETING_FIELD: greeting,
            LINK_STATE_FIELD: state_value,
        },
    )

    payload = {
        "firstName": contact.get("firstName") or prospect["business"],
        "customFields": custom_fields,
    }
    return api("PATCH", f"/contacts/{prospect['contactId']}", json=payload)


def exact_profile_only_body(body):
    text = body or ""

    # Always use the verified SRE greeting field rather than Reply's raw First Name.
    text = re.sub(
        r"(?im)^\s*(hi|hello|hey)\s+(?:\{\{[^}\n]+\}\}|[^,\n]{1,100}),\s*$",
        r"Hi {{Outreach_Greeting}},",
        text,
        count=1,
    )
    if not re.search(r"(?im)^\s*Hi \{\{Outreach_Greeting\}\},\s*$", text):
        text = "Hi {{Outreach_Greeting}},\n\n" + text.lstrip()

    # A prospecting email may have only one Franklin commercial/action destination:
    # that prospect's exact live profile URL. Never fall back to a generic member page.
    franklin_url = re.compile(
        r"https://franklinnavigator\.com(?P<path>/[^\s<>\"]*)?", re.I
    )

    def replace_franklin_url(match):
        raw_path = match.group("path") or "/"
        path_only = raw_path.split("?", 1)[0].split("#", 1)[0]
        if path_only.startswith("/profiles/"):
            return "{{Profile_URL}}"
        if (
            path_only in GENERIC_FRANKLIN_PATHS
            or path_only.startswith("/membership-")
            or path_only.startswith("/business-membership")
        ):
            return "{{Profile_URL}}"
        return "__FRANKLIN_LINK_BLOCKED__"

    text = franklin_url.sub(replace_franklin_url, text)
    if "__FRANKLIN_LINK_BLOCKED__" in text:
        raise RuntimeError("TEMPLATE_CONTAINS_NON_PROFILE_FRANKLIN_LINK")

    if "{{Profile_URL}}" not in text:
        text = (
            text.rstrip()
            + "\n\nView your Franklin Navigator profile:\n{{Profile_URL}}\n"
        )

    # Keep exactly one profile destination in a shared template.
    seen = False
    output = []
    for line in text.splitlines():
        if "{{Profile_URL}}" in line:
            if seen:
                continue
            seen = True
        output.append(line)
    return "\n".join(output)


def get_sequence():
    return api("GET", f"/sequences/{SEQUENCE_ID}")


def update_email_steps():
    sequence = get_sequence()
    steps = sequence.get("steps") or []
    changed = False

    for step in steps:
        if step.get("type") != "Email":
            continue
        step_id = step["id"]
        email_template = ((step.get("template") or {}).get("emailTemplate") or {})
        execution_mode = email_template.get("executionMode") or "Automatic"
        templates = email_template.get("templates") or step.get("templates") or []
        if not templates:
            raise RuntimeError(f"EMAIL_STEP_{step_id}_HAS_NO_TEMPLATES")

        new_templates = []
        step_changed = False
        for template in templates:
            updated = deepcopy(template)
            body_key = "body" if "body" in updated else "message"
            if body_key not in updated:
                raise RuntimeError(f"EMAIL_STEP_{step_id}_TEMPLATE_HAS_NO_BODY")
            new_body = exact_profile_only_body(updated.get(body_key) or "")
            if new_body != updated.get(body_key):
                updated[body_key] = new_body
                step_changed = True
            new_templates.append(updated)

        if step_changed:
            payload_templates = []
            for template in new_templates:
                payload_templates.append(
                    {
                        key: value
                        for key, value in template.items()
                        if key
                        in {
                            "id",
                            "variantId",
                            "subject",
                            "body",
                            "message",
                            "templateId",
                            "emailTemplateId",
                            "isEnabled",
                        }
                    }
                )
            api(
                "PATCH",
                f"/sequences/{SEQUENCE_ID}/steps/{step_id}",
                json={
                    "type": "Email",
                    "executionMode": execution_mode,
                    "templates": payload_templates,
                },
            )
            changed = True

    return changed


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
            except Exception:
                pass
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

    # Never alter templates while a configured send candidate has an unresolved exact-profile issue.
    template_updated = False
    if not held:
        template_updated = update_email_steps()

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
        "error": None,
    }
    with _state_lock:
        _state.update(result)
    return result


def runner():
    while True:
        try:
            sync_once()
        except Exception as exc:
            with _state_lock:
                _state.update(
                    {
                        "lastRunAt": now_iso(),
                        "lastOutcome": "ERROR",
                        "error": str(exc),
                    }
                )
        time.sleep(SYNC_INTERVAL_SECONDS)


@app.on_event("startup")
def startup():
    threading.Thread(target=runner, daemon=True).start()


@app.get("/health")
def health():
    return {
        "ok": True,
        "apiKeyConfigured": bool(REPLY_API_KEY),
        "sequenceId": SEQUENCE_ID,
        "lastRunAt": _state["lastRunAt"],
        "lastOutcome": _state["lastOutcome"],
    }


@app.get("/status")
def status():
    with _state_lock:
        return dict(_state)
