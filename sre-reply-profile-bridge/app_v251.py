import app_v250 as base

legacy = base.legacy
SRE_BRIDGE_RELEASE = "FN-SRE-BRIDGE-2.5.1-CANDIDATE"
legacy.SRE_BRIDGE_RELEASE = SRE_BRIDGE_RELEASE


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


legacy.build_franklin_message = build_franklin_message_v251

# Re-export tested candidate helpers for a single review/test surface.
_validate_direct_sequence_v250 = base._validate_direct_sequence_v250
_step_due = base._step_due
_recipient_is_suppressed = base._recipient_is_suppressed
build_franklin_message_v250 = build_franklin_message_v251

app = legacy.app
