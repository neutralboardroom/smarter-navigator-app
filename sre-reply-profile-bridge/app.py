"""Production entrypoint for the tested Franklin Navigator SRE outreach layer.

The preserved pre-v2.5 runtime lives in app_legacy.py. Candidate modules patch
that preserved runtime in place, then this entrypoint exposes the same FastAPI app.
"""

import importlib
import sys

import app_legacy as _legacy

_entrypoint = sys.modules[__name__]
sys.modules["app"] = _legacy
try:
    _active = importlib.import_module("app_v255")
finally:
    sys.modules["app"] = _entrypoint

# Owner-controlled alternate-email suppression tooling remains imported with all
# action flags defaulting off. It is not part of normal prospect outreach.
_suppression_test = importlib.import_module("suppression_test_tools")

# Keep the scanner-safe visible unsubscribe confirmation/success UI. RFC 8058
# one-click POST remains separate and unchanged.
_unsubscribe_ui = importlib.import_module("unsubscribe_ui")

# Optional one-shot read-only diagnostic. It never sends and is off by default.
_point_of_send_diagnostic = importlib.import_module("point_of_send_diagnostic")

app = _legacy.app
SRE_BRIDGE_RELEASE = _legacy.SRE_BRIDGE_RELEASE
legacy = _legacy

# Current v2.5.5 surfaces.
_validate_direct_sequence_v255 = _active._validate_direct_sequence_v255
_validate_growth_cohort = _active._validate_growth_cohort
_growth_scan_once = _active._growth_scan_once

# Preserve the existing v2.5 regression/test exports so the new growth layer does
# not break already-qualified unsubscribe, copy, timing, and suppression checks.
_validate_direct_sequence_v250 = _active._validate_direct_sequence_v255
_step_due = _active.base._step_due
_recipient_is_suppressed = _active.base._recipient_is_suppressed
build_franklin_message_v250 = _active.base.build_franklin_message_v251
