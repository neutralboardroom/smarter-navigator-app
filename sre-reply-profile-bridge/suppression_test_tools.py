"""Owner-controlled end-to-end unsubscribe/suppression test harness.

Restricted to reachrgnow1@gmail.com. This module never changes Franklin Navigator's
normal owner-alert recipient. It supports a one-shot test-address-only restoration
so the owner can repeat unsubscribe/deliverability tests without creating a general
unsuppress mechanism for real prospects.
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
SUPPRESSION_TEST_RESTORE_ON_STARTUP = legacy.os.environ.get(
    "FN_SUPPRESSION_TEST_RESTORE_ON_STARTUP", "false"
).strip().lower() in {"1", "true", "yes"}
SUPPRESSION_TEST_LEAN_COPY = legacy.os.environ.get(
    "FN_SUPPRESSION_TEST_LEAN_COPY", "false"
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
    domain_holds = safety_state.get("domain_holds") or {}
    domain_suppressions = safety_state.get("domain_suppressions") or {}
    org_domain_hold = domain in domain_holds
    org_domain_suppression = domain in domain_suppressions
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
        "orgDomainHold": org_domain_hold,
        "orgDomainSuppression": org_domain_suppression,
        "senderWouldBlock": bool(blocked),
    }


def _lean_first_touch(profile_url: str):
    """Owner-only A/B copy for testing Gmail placement; not production sequence copy."""
    profile_url = str(profile_url or "").strip()
    plain = (
        "Hi Roger,\n\n"
        "Franklin Navigator helps Franklin residents find and connect with local businesses and community resources.\n\n"
        "We have a Franklin Navigator business profile available for you to review:\n"
        f"View or claim your Franklin Navigator profile: {profile_url}\n\n"
        "Claiming and managing your basic profile is free. No purchase is required. "
        "If anything is wrong, factual corrections and profile-removal requests are free.\n\n"
        "Optional Community Membership is designed to help increase your visibility in the Franklin community by giving your business a stronger Franklin Navigator presence and more ways for local residents to connect with you.\n\n"
        "Questions? Reply to this email and we’ll be happy to help.\n\n"
        "This is a commercial community-outreach email from Franklin Navigator."
    )
    html = (
        "<p>Hi Roger,</p>"
        "<p>Franklin Navigator helps Franklin residents find and connect with local businesses and community resources.</p>"
        "<p>We have a Franklin Navigator business profile available for you to review:<br>"
        f"<a href=\"{profile_url}\">View or claim your Franklin Navigator profile</a></p>"
        "<p>Claiming and managing your basic profile is free. No purchase is required. "
        "If anything is wrong, factual corrections and profile-removal requests are free.</p>"
        "<p><strong>Optional Community Membership is designed to help increase your visibility in the Franklin community</strong> by giving your business a stronger Franklin Navigator presence and more ways for local residents to connect with you.</p>"
        "<p>Questions? Reply to this email and we’ll be happy to help.</p>"
        "<p>This is a commercial community-outreach email from Franklin Navigator.</p>"
    )
    return plain, html


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

            preview_recipient = dict(legacy.FIRST10_CONTACT_ROSTER[-1])
            preview_recipient["outreachGreeting"] = "Roger"
            if SUPPRESSION_TEST_LEAN_COPY:
                plain_body, html_body = _lean_first_touch(preview_recipient.get("profileUrl") or "")
                copy_variant = "LEAN_FIRST_TOUCH"
            else:
                plain_body = legacy._render_direct_body(step.get("body") or "", preview_recipient)
                html_body = legacy._render_direct_body(step.get("html_body") or "", preview_recipient)
                copy_variant = "CURRENT_INITIAL"
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
                {
                    "to": email_addr,
                    "testId": SUPPRESSION_TEST_ID,
                    "messageId": message_id,
                    "prospectSend": False,
                    "copyVariant": copy_variant,
                },
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


def restore_suppression_test_address_once():
    """Remove suppression markers for the single allowlisted owner test address only."""
    try:
        email_addr = _test_email()
        before = _test_state()
        if before.get("domainSuppressed") or before.get("orgDomainHold") or before.get("orgDomainSuppression"):
            raise RuntimeError("SUPPRESSION_TEST_DOMAIN_BLOCKED_RESTORE_REFUSED")
        deleted = 0
        remaining_marker_ids = []
        with legacy._imap_connect() as client:
            legacy._ensure_suppression_mailbox(client)
            status, _ = client.select(f'"{legacy.FN_SUPPRESSION_MAILBOX}"', readonly=False)
            if status != "OK":
                raise RuntimeError("SUPPRESSION_TEST_SUPPRESSION_MAILBOX_SELECT_FAILED")
            status, data = client.search(None, "HEADER", "X-Franklin-Suppression-Email", email_addr)
            if status != "OK":
                raise RuntimeError("SUPPRESSION_TEST_RESTORE_SEARCH_FAILED")
            ids = [x for x in (data[0] or b"").split() if x]
            for msg_id in ids:
                status2, msg_data = client.fetch(
                    msg_id,
                    '(BODY.PEEK[HEADER.FIELDS (X-FRANKLIN-SUPPRESSION-EMAIL)])',
                )
                if status2 != "OK":
                    continue
                raw = b"".join(
                    part[1]
                    for part in msg_data
                    if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray))
                )
                if not raw:
                    continue
                msg = legacy.BytesParser(policy=legacy.email_policy.default).parsebytes(raw)
                marker_email = str(msg.get("X-Franklin-Suppression-Email") or "").strip().lower()
                if marker_email != email_addr:
                    continue
                store_status, _ = client.store(msg_id, "+FLAGS.SILENT", "(\\Deleted)")
                if store_status == "OK":
                    deleted += 1
            if deleted:
                expunge_status, _ = client.expunge()
                if expunge_status != "OK":
                    raise RuntimeError("SUPPRESSION_TEST_RESTORE_EXPUNGE_FAILED")

            status3, data3 = client.search(None, "HEADER", "X-Franklin-Suppression-Email", email_addr)
            if status3 != "OK":
                raise RuntimeError("SUPPRESSION_TEST_RESTORE_VERIFY_SEARCH_FAILED")
            remaining_marker_ids = [x.decode("ascii", "ignore") for x in (data3[0] or b"").split() if x]

        after = _test_state()
        diagnostics = {
            "email": email_addr,
            "deletedMarkers": deleted,
            "remainingMarkerIds": remaining_marker_ids,
            "before": before,
            "after": after,
            "testOnlyRestore": True,
        }
        if remaining_marker_ids or after.get("suppressed") or after.get("senderWouldBlock"):
            raise RuntimeError("SUPPRESSION_TEST_RESTORE_DID_NOT_CLEAR_BLOCK " + json.dumps(diagnostics, sort_keys=True))
        print("SRE_BRIDGE SUPPRESSION_TEST_RESTORE " + json.dumps(diagnostics, sort_keys=True), flush=True)
        return diagnostics
    except Exception as exc:
        print(f"SRE_BRIDGE SUPPRESSION_TEST_RESTORE ERROR {exc}", flush=True)
        return None


@legacy.app.on_event("startup")
def suppression_test_startup():
    actions_requested = sum(
        1
        for enabled in (
            SUPPRESSION_TEST_SEND_ON_STARTUP,
            SUPPRESSION_TEST_CHECK_ON_STARTUP,
            SUPPRESSION_TEST_RESTORE_ON_STARTUP,
        )
        if enabled
    )
    if actions_requested > 1:
        print("SRE_BRIDGE SUPPRESSION_TEST HOLD MULTIPLE_ACTIONS_REQUESTED", flush=True)
        return
    if SUPPRESSION_TEST_SEND_ON_STARTUP:
        legacy.threading.Thread(target=send_suppression_test_preview_once, daemon=True).start()
    elif SUPPRESSION_TEST_CHECK_ON_STARTUP:
        legacy.threading.Thread(target=check_suppression_test_once, daemon=True).start()
    elif SUPPRESSION_TEST_RESTORE_ON_STARTUP:
        legacy.threading.Thread(target=restore_suppression_test_address_once, daemon=True).start()
