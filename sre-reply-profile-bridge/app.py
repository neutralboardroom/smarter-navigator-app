"""Production entrypoint for the tested Franklin Navigator SRE outreach v2.5.1 layer.

The preserved pre-v2.5 runtime lives in app_legacy.py. The candidate modules patch
that preserved runtime in place, then this entrypoint exposes the same FastAPI app.
"""

import importlib
import sys

import app_legacy as _legacy

# app_v250 was intentionally written against module name `app`. During activation,
# make that import resolve to the preserved runtime so every monkey-patch lands on
# the real FastAPI runtime rather than on this thin entrypoint.
_entrypoint = sys.modules[__name__]
sys.modules["app"] = _legacy
try:
    _active = importlib.import_module("app_v251")
finally:
    sys.modules["app"] = _entrypoint

app = _legacy.app
SRE_BRIDGE_RELEASE = _legacy.SRE_BRIDGE_RELEASE
legacy = _legacy
_validate_direct_sequence_v250 = _active._validate_direct_sequence_v250
_step_due = _active._step_due
_recipient_is_suppressed = _active._recipient_is_suppressed
build_franklin_message_v250 = _active.build_franklin_message_v250
