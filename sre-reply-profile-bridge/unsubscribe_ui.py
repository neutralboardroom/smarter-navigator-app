"""Scanner-safe human unsubscribe UI for Franklin Navigator outreach.

The visible GET remains confirmation-only and never suppresses a recipient. Durable
suppression still occurs only after the explicit POST confirmation, while the RFC
8058 one-click POST endpoint in the legacy bridge remains unchanged.
"""

import html
import re

import app_legacy as legacy


def _page(title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin:0; background:#f6f7f8; color:#17202a; font-family:Arial,Helvetica,sans-serif; }}
    .wrap {{ max-width:620px; margin:64px auto; padding:0 20px; }}
    .card {{ background:#fff; border:1px solid #e3e6e8; border-radius:12px; padding:32px; box-shadow:0 2px 8px rgba(0,0,0,.04); }}
    h1 {{ font-size:26px; line-height:1.2; margin:0 0 16px; }}
    p {{ font-size:16px; line-height:1.55; margin:0 0 18px; }}
    .notice {{ background:#f4f7fa; border-left:4px solid #4b6b88; padding:14px 16px; margin:20px 0; }}
    button {{ appearance:none; border:0; border-radius:7px; background:#17202a; color:#fff; font-size:16px; font-weight:700; padding:12px 18px; cursor:pointer; }}
    .small {{ color:#5f6b76; font-size:14px; margin-top:22px; }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="card">
      {body_html}
    </section>
  </main>
</body>
</html>"""


def visible_unsubscribe_v253(token: str):
    # Validate the signed address token, but deliberately do NOT persist suppression
    # on this GET. Link scanners and security systems frequently visit GET links.
    legacy.parse_unsubscribe_token(token)
    safe_token = re.sub(r"[^A-Za-z0-9_.-]", "", token)
    body = f"""
      <h1>Unsubscribe from Franklin Navigator outreach</h1>
      <div class="notice"><strong>You have not been unsubscribed yet.</strong></div>
      <p>Click the button below to confirm that you want to stop future Franklin Navigator outreach at this email address.</p>
      <form method="post" action="/unsubscribe/confirm/{safe_token}">
        <input type="hidden" name="confirm" value="1">
        <button type="submit">Confirm unsubscribe</button>
      </form>
      <p class="small">This extra confirmation helps prevent email-security scanners from unsubscribing you by accident.</p>
    """
    return legacy.HTMLResponse(_page("Unsubscribe from Franklin Navigator outreach", body))


async def confirm_visible_unsubscribe_v253(token: str, request: legacy.Request):
    email_addr = legacy.parse_unsubscribe_token(token)
    raw_body = (await request.body()).decode("utf-8", "ignore")
    values = legacy.parse_qs(raw_body)
    if values.get("confirm", [""])[0] != "1":
        raise legacy.HTTPException(status_code=400, detail="Confirmation required")

    legacy.persist_unsubscribe(email_addr)
    body = """
      <h1>You have been unsubscribed</h1>
      <p>You will not receive future Franklin Navigator outreach at this email address.</p>
      <p class="small">Your request has been recorded. No further action is needed.</p>
    """
    return legacy.HTMLResponse(_page("You have been unsubscribed", body))


def install_unsubscribe_ui():
    """Replace only the two human-facing visible unsubscribe routes."""
    keep = []
    for route in legacy.app.router.routes:
        path = getattr(route, "path", "")
        methods = set(getattr(route, "methods", set()) or set())
        if path == "/unsubscribe/{token}" and "GET" in methods:
            continue
        if path == "/unsubscribe/confirm/{token}" and "POST" in methods:
            continue
        keep.append(route)
    legacy.app.router.routes = keep

    legacy.app.add_api_route(
        "/unsubscribe/{token}",
        visible_unsubscribe_v253,
        methods=["GET"],
        response_class=legacy.HTMLResponse,
    )
    legacy.app.add_api_route(
        "/unsubscribe/confirm/{token}",
        confirm_visible_unsubscribe_v253,
        methods=["POST"],
        response_class=legacy.HTMLResponse,
    )


install_unsubscribe_ui()
