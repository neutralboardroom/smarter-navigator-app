import json

import app_v250 as base

legacy = base.legacy
SRE_BRIDGE_RELEASE = "FN-SRE-BRIDGE-2.5.2-CANDIDATE"
legacy.SRE_BRIDGE_RELEASE = SRE_BRIDGE_RELEASE

# Fail closed on real prospect sending until the Main/Local product has explicitly
# qualified the new paid-member benefit claims for outreach use. Even if Render's
# older FN_DIRECT_OUTREACH_ENABLED switch remains true, prospect sending stays off
# unless this second readiness gate is also true.
FN_OUTREACH_COPY_READY = legacy.os.environ.get("FN_OUTREACH_COPY_READY", "false").strip().lower() in {"1", "true", "yes"}
legacy.FN_OUTREACH_COPY_READY = FN_OUTREACH_COPY_READY
legacy.FN_DIRECT_OUTREACH_REQUESTED = bool(legacy.FN_DIRECT_OUTREACH_ENABLED)
legacy.FN_DIRECT_OUTREACH_ENABLED = bool(legacy.FN_DIRECT_OUTREACH_ENABLED and FN_OUTREACH_COPY_READY)
legacy._state.setdefault("directOutreach", {}).update({
    "enabled": legacy.FN_DIRECT_OUTREACH_ENABLED,
    "requestedEnabled": legacy.FN_DIRECT_OUTREACH_REQUESTED,
    "outreachCopyReady": FN_OUTREACH_COPY_READY,
})


def build_franklin_message_v251(to_email: str, subject: str, plain_body: str, html_body: str = ""):
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

    # The body already contains the required commercial-outreach disclosure.
    # Do not repeat it in the signature/footer.
    footer_text = (
        "\n\nFranklin Navigator Community Team\n"
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


def send_owner_sequence_preview_once():
    """Send one idempotent rendered initial-outreach preview to the owner only.

    No outreach key is supplied to SMTP, so the prospect-roster send path is never
    entered. A durable Zoho ledger key prevents a service restart from sending the
    same owner preview twice. A new FN_OUTREACH_OWNER_PREVIEW_ID can be supplied
    later if a deliberate second preview is needed.
    """
    try:
        owner_email = str(legacy.FN_OUTREACH_OWNER_TEST_EMAIL or "").strip().lower()
        if owner_email != "reachrgnow@gmail.com":
            raise RuntimeError("OWNER_PREVIEW_RECIPIENT_DRIFT")
        sequence = legacy.load_direct_sequence()
        step = (sequence.get("steps") or [])[0]
        if str(step.get("id") or "") != "initial":
            raise RuntimeError("OWNER_PREVIEW_INITIAL_STEP_MISSING")
        subject = str(step.get("subject") or "").strip()
        preview_id = legacy.os.environ.get("FN_OUTREACH_OWNER_PREVIEW_ID", "v252-initial-owner-test-1").strip()
        if not preview_id or len(preview_id) > 120:
            raise RuntimeError("OWNER_PREVIEW_ID_INVALID")
        ledger_key = "fn-owner-preview:" + preview_id

        with legacy._imap_connect() as client:
            if not legacy._ledger_reserve(client, ledger_key, owner_email, subject):
                print(
                    "SRE_BRIDGE OWNER_SEQUENCE_PREVIEW SKIPPED "
                    + json.dumps({"to": owner_email, "previewId": preview_id, "reason": "ALREADY_RESERVED_OR_SENT"}, sort_keys=True),
                    flush=True,
                )
                return None

            preview_recipient = dict(legacy.FIRST10_CONTACT_ROSTER[-1])
            plain_body = legacy._render_direct_body(step.get("body") or "", preview_recipient)
            html_body = legacy._render_direct_body(step.get("html_body") or "", preview_recipient)
            message_id = legacy.send_franklin_smtp_message(
                owner_email,
                subject,
                plain_body,
                html_body=html_body,
            )
            legacy._ledger_mark_sent(client, ledger_key, owner_email, subject, message_id)

        print(
            "SRE_BRIDGE OWNER_SEQUENCE_PREVIEW SENT "
            + json.dumps(
                {
                    "to": owner_email,
                    "step": "initial",
                    "previewId": preview_id,
                    "messageId": message_id,
                    "prospectSend": False,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return message_id
    except Exception as exc:
        print(f"SRE_BRIDGE OWNER_SEQUENCE_PREVIEW ERROR {exc}", flush=True)
        return None


legacy.build_franklin_message = build_franklin_message_v251
# Reuse the existing startup-only owner-test switch, but make it send the actual
# current initial outreach email rather than the old generic RFC8058 test body.
legacy.send_owner_rfc8058_test_once = send_owner_sequence_preview_once

# Re-export tested candidate helpers for a single review/test surface.
_validate_direct_sequence_v250 = base._validate_direct_sequence_v250
_step_due = base._step_due
_recipient_is_suppressed = base._recipient_is_suppressed
build_franklin_message_v250 = build_franklin_message_v251

app = legacy.app
