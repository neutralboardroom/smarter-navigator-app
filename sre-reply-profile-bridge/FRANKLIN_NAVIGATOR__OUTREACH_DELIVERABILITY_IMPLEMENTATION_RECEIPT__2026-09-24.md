# Franklin Navigator Outreach Deliverability Implementation Receipt

**Date:** 2026-09-24  
**Rule:** RR-FN-OUTREACH-DELIVERABILITY-2026-09-24-V1  
**Campaign:** Mailshake 1553662 — Franklin Navigator — First 10 Pilot — First Touch Only  
**Status:** FAIL-CLOSED PENDING COMPLIANCE FOOTER / VISIBLE UNSUBSCRIBE VERIFICATION

## Research disposition

Adopted:
- Google sender authentication, low-spam-rate, alignment, and unsubscribe requirements.
- Yahoo SPF/DKIM/DMARC, complaint-rate, unsubscribe, and list-hygiene requirements.
- Microsoft Outlook high-volume SPF/DKIM/DMARC and hygiene recommendations.
- FTC CAN-SPAM accurate identity/subject, physical postal address, commercial identification, and opt-out requirements.
- Mailshake slow ramp, spaced sends, one-at-a-time early cadence, bounce monitoring, physical-address footer, reply-based unsubscribe, visible unsubscribe link, and domain-authentication guidance.

Adapted:
- Mailshake's suggested ramp is capped more conservatively by Roger Rule: current pilot 10/day; future staged ceilings 20/40/55/75/100/day with no automatic scale-up.
- Mailshake says two-click unsubscribe is operationally useful against scanner-triggered unsubscribes; Franklin Navigator will prefer one-click/easy unsubscribe for long-term mailbox-provider compliance where supported.

Rejected:
- High-volume blasting, simultaneous multi-provider sending from one mailbox, open/click tracking by default, automatic cohort expansion, and automatic follow-up escalation.

## Deployed automation controls

- Exact 10-recipient roster/profile binding gate.
- Any roster/profile mismatch -> pause.
- Sequence drift beyond one first-touch message -> pause.
- Unexpected sender mailbox -> pause.
- Any bounce during current pilot -> pause.
- Any unsubscribe during current pilot -> pause.
- Completion at 10 total sends -> lock closed.
- Old Reply.io sync disabled.
- 15-minute reconciliation plus Mailshake push events.
- Current compliance hold -> campaign paused until footer/unsubscribe confirmation.
- No automatic scale-up.

## Current state at deployment

- Recipients: 10
- Sent: 0
- Bounces: 0
- Unsubscribes: 0
- Roster exact: true
- Campaign: paused by compliance hold

## Manual UI-only correction still required

Before the compliance hold is released:
1. Set team unsubscribe behavior to one-click where supported.
2. Add a visible unsubscribe link to the sending signature.
3. Add Franklin Navigator's valid physical postal address.
4. Add a clear commercial/community-outreach identification in the footer.
5. Verify the final live signature in Mailshake.

No campaign send may resume until those items are verified.
