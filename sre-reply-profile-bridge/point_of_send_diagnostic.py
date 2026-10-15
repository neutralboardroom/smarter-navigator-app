import json
import threading
import time

import app_legacy as legacy

FN_POINT_OF_SEND_DIAGNOSTIC_ON_STARTUP = legacy.os.environ.get(
    "FN_POINT_OF_SEND_DIAGNOSTIC_ON_STARTUP", "false"
).strip().lower() in {"1", "true", "yes"}


def _safe_summary(summary):
    summary = dict(summary or {})
    keys = (
        "release",
        "imapConnection",
        "initialSent",
        "followup1Sent",
        "followup2Sent",
        "reengagement90dSent",
        "stoppedForReply",
        "suppressed",
        "bounceHolds",
        "complaintHolds",
        "globalHold",
        "growthCohortStatus",
        "growthCertified",
        "growthRosterCount",
        "newInitialSentToday",
        "growthSuppressed",
        "growthHeld",
        "targetNewInitialsPerBusinessDay",
        "growthFollowupsEnabled",
        "enabled",
        "requestedEnabled",
        "outreachCopyReady",
    )
    return {key: summary.get(key) for key in keys}


def run_point_of_send_diagnostic_once():
    try:
        time.sleep(2)
        summary = legacy._direct_scan_once(send_if_due=False)
        print(
            "SRE_BRIDGE POINT_OF_SEND_DIAGNOSTIC "
            + json.dumps(_safe_summary(summary), sort_keys=True),
            flush=True,
        )
    except Exception as exc:
        print(f"SRE_BRIDGE POINT_OF_SEND_DIAGNOSTIC ERROR {exc}", flush=True)


if FN_POINT_OF_SEND_DIAGNOSTIC_ON_STARTUP:
    @legacy.app.on_event("startup")
    def _start_point_of_send_diagnostic():
        threading.Thread(target=run_point_of_send_diagnostic_once, daemon=True).start()
