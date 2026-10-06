"""Owner-controlled end-to-end unsubscribe/suppression test harness.

Restricted to reachrgnow1@gmail.com. This module never changes Franklin Navigator's
normal owner-alert recipient and does not provide a general unsuppress action.
"""

import json

import app_legacy as legacy
import app_v250 as candidate

EXPECTED_SUPPRESSION_TEST_EMAIL = "reachrgnow1@gmail.com"
SUPPRESSION_TEST_EMAIL = legacy.os.environ.get(
    "FN_SUPPRESSION_TEST_EMAIL", EXPECTED_SUPPRESSION_TEST_EMAIL
).strip().lower()
SUPPRESSION_TEST_ID = legacy.os.environ.get(
    "FN_SUPPRESSION_TEST_ID", "v253-alt-email-unsubscribe-1"
).strip()
SUPPRESSION_TEST_SEND_ON_STARTUP = legacy.os.environ.get(
    "FN_SUPPRESSION_TEST_SEND_ON_STARTUP", "false"
).strip().lower() in {"1", "true", "yes"}
SUPPRESSION_TEST_CHECK_ON_STARTUP = legacy.os.environ.get(
    "FN_SUPPRESSION_TEST_CHECK_ON_STARTUP", "false"
).strip().lower() in {"1", "true", "yes"}


def _test_email() -> str:
    if SUPPRESSION_TEST_EMAIL != EXPECTED_SUPPRESSION_TEST_EMAIL:
        raise RuntimeError("SUPPRESSION_TEST_EMAIL_NOT_ALLOWLISTED")
    return EXPECTED_SUPPRESSION_TEST_EMAIL


def _test_state() -> dict:
    email_addr = _test_email()
    suppressed_set = legacy._zoho_suppression_set()
    safety_state = legacy.load_org_safety_state()
    domain = legacy.email_domain(email_addr)
    domain_suppressed = domain in legacy._zoho_domain_suppression_set()
    blocked = candidate._recipient_is_suppressed(
        email_addr,
        domain,
        suppressed_set,
        {domain} if domain_suppressed else set(),
        safety_state,
    )
    return {
        "email": email_addr,
        "suppressed": email_addr in suppressed_set,
        "domainSuppressed": domain_suppressed,
        "senderWouldBlock": bool(blocked),
    }


def send_suppression_test_preview_once():
    try:
        email_addr = _test_email()
        before = _test_state()
        if before["senderWouldBlock"]:
            raise RuntimeError("SUPPRESSION_TEST_ADDRESS_ALREADY_BLOCKED")

        sequence = legacy.load_direct_sequence()
        step = (sequence.get("steps") or [])[0]
        if str(step.get("id") or "") != "initial":
            raise RuntimeError("SUPPRESSION_TEST_INITIAL_STEP_MISSING")
        if not SUPPRESSION_TEST_ID or len(SUPPRESSION_TEST_ID) > 120:
            raise RuntimeError("SUPPRESSION_TEST_ID_INVALID")

        subject = str(step.get("subject") or "").strip()
        ledger_key = "fn-suppression-test-preview:" + SUPPRESSION_TEST_ID
        with legacy._imap_connect() as client:
            if not legacy._ledger_reserve(client, ledger_key, email_addr, subject):
                print(
                    "SRE_BRIDGE SUPPRESSION_TEST_SEND SKIPPED "
                    + json.dumps(
                        {"to": email_addr, "testId": SUPPRESSION_TEST_ID, "reason": "ALREADY_RESERVED_OR_SENT"},
                        sort_keys=True,
                    ),
                    flush=True,
                )
                return None

            # Keep a valid public Franklin profile URL for the exact email template,
            # but make the greeting unmistakably owner-directed during testing.
            preview_recipient = dict(legacy.FIRST10_CONTACT_ROSTER[-1])
            preview_recipient["outreachGreeting"] = "Roger"
            plain_body = legacy._render_direct_body(step.get("body") or "", preview_recipient)
            html_body = legacy._render_direct_body(step.get("html_body") or "", preview_recipient)
            message_id = legacy.send_franklin_smtp_message(
                email_addr,
                subject,
                plain_body,
                html_body=html_body,
            )
            legacy._ledger_mark_sent(client, ledger_key, email_addr, subject, message_id)

        print(
            "SRE_BRIDGE SUPPRESSION_TEST_SEND SENT "
            + json.dumps(
                {"to": email_addr, "testId": SUPPRESSION_TEST_ID, "messageId": message_id, "prospectSend": False},
                sort_keys=True,
            ),
            flush=True,
        )
        return message_id
    except Exception as exc:
        print(f"SRE_BRIDGE SUPPRESSION_TEST_SEND ERROR {exc}", flush=True)
        return None


def check_suppression_test_once():
    try:
        state = _test_state()
        print(
            "SRE_BRIDGE SUPPRESSION_TEST_CHECK " + json.dumps(state, sort_keys=True),
            flush=True,
        )
        return state
    except Exception as exc:
        print(f"SRE_BRIDGE SUPPRESSION_TEST_CHECK ERROR {exc}", flush=True)
        return None


@legacy.app.on_event("startup")
def suppression_test_startup():
    if SUPPRESSION_TEST_SEND_ON_STARTUP and SUPPRESSION_TEST_CHECK_ON_STARTUP:
        print("SRE_BRIDGE SUPPRESSION_TEST HOLD MULTIPLE_ACTIONS_REQUESTED", flush=True)
        return
    if SUPPRESSION_TEST_SEND_ON_STARTUP:
        legacy.threading.Thread(target=send_suppression_test_preview_once, daemon=True).start()
    elif SUPPRESSION_TEST_CHECK_ON_STARTUP:
        legacy.threading.Thread(target=check_suppression_test_once, daemon=True).start()
