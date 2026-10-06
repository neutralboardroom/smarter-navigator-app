"""Production entrypoint for the tested Franklin Navigator SRE outreach v2.5 layer.

The preserved pre-v2.5 runtime lives in app_legacy.py. The candidate modules patch
that preserved runtime in place, then this entrypoint exposes the same FastAPI app.
"""

import importlib
import sys

import app_legacy as _legacy

_entrypoint = sys.modules[__name__]
sys.modules["app"] = _legacy
try:
    _active = importlib.import_module("app_v252")
finally:
    sys.modules["app"] = _entrypoint

# Owner-controlled alternate-email suppression tooling remains imported with all
# action flags defaulting off. It is not part of normal prospect outreach.
_suppression_test = importlib.import_module("suppression_test_tools")

# Keep the scanner-safe visible unsubscribe confirmation/success UI. RFC 8058
# one-click POST remains separate and unchanged.
_unsubscribe_ui = importlib.import_module("unsubscribe_ui")

app = _legacy.app
SRE_BRIDGE_RELEASE = _legacy.SRE_BRIDGE_RELEASE
legacy = _legacy
_validate_direct_sequence_v250 = _active._validate_direct_sequence_v250
_step_due = _active._step_due
_recipient_is_suppressed = _active._recipient_is_suppressed
build_franklin_message_v250 = _active.build_franklin_message_v250
