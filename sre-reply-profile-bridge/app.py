import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

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

app = FastAPI(title="SRE Reply Profile Bridge", version="1.1.2")
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
    changed = False

    for step in steps:
        if str(step.get("type") or "").lower() != "email":
            continue

        step_id = step["id"]
        execution_mode, templates = extract_email_step(step)
        if not templates:
            raise RuntimeError(f"EMAIL_STEP_{step_id}_HAS_NO_TEMPLATES")

        updated_templates = []
        step_changed = False
        for template in templates:
            variant_id = template.get("variantId") or template.get("id")
            if not variant_id:
                raise RuntimeError(f"EMAIL_STEP_{step_id}_VARIANT_HAS_NO_ID")
            old_body = template.get("body") or template.get("message") or ""
            new_body = exact_profile_only_body(old_body)
            if new_body != old_body:
                step_changed = True

            item = {
                "id": variant_id,
                "subject": template.get("subject") or "",
                "body": new_body,
            }
            if template.get("templateId") is not None:
                item["templateId"] = template.get("templateId")
            updated_templates.append(item)

        if not step_changed:
            continue

        api(
            "PUT",
            f"/sequences/{SEQUENCE_ID}/steps/{step_id}",
            json={
                "type": "Email",
                "executionMode": execution_mode,
                "templates": updated_templates,
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
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return result


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
    print(
        f"SRE_BRIDGE startup apiKeyConfigured={bool(REPLY_API_KEY)} sequenceId={SEQUENCE_ID}",
        flush=True,
    )
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
