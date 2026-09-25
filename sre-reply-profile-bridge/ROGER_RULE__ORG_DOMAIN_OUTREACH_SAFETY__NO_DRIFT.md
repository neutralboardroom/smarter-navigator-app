# ROGER RULE — FRANKLIN NAVIGATOR ORGANIZATION / DOMAIN OUTREACH SAFETY + OWNER ALERTS

**Rule ID:** RR-FN-ORG-OUTREACH-001  
**Authority:** Roger Rule / Owner directive  
**Status:** DURABLE · NO-DRIFT · FAIL-CLOSED · CROSS-BUILDER  
**Adopted:** 2026-09-25  
**Scope:** Franklin Navigator SRE Owner Console / Revenue Engine and every applicable Franklin Navigator contact/profile/outreach component.

This rule supplements all existing Franklin Navigator anti-spam, deliverability, suppression, sender-identity, privacy, and no-fabrication rules. Where another rule is stricter, preserve the stricter rule.

## Durable requirements

1. Never use a company/general inbox as a forwarding hub for multiple employee-targeted messages and never ask generic-inbox staff to mass-distribute outreach internally.
2. A generic/role inbox may receive one legitimate organization-level message when it is the best route. Prefer asking for the appropriate contact over asking for broad forwarding.
3. Prefer verified direct professional/work email for clearly relevant people when lawfully available. Keep identity, role, employer, and route source-backed. Never guess or dictionary-generate addresses.
4. Apply address-, organization-, and domain-level deduplication, throttling, negative-signal checks, HOLD checks, and suppression checks before every send.
5. Conservative new-initial default: no more than 1 new initial outreach message to the same organization/domain in any rolling 24 hours; generally no more than 3 distinct people at the same organization in any rolling 14 days unless there is a documented reply, referral, permission, invitation, or distinct-function reason.
6. Never shotgun many employees at one company. No response does not authorize rapid fan-out.
7. Any spam complaint triggers an immediate company/domain HOLD, blocks queued/new outreach, preserves evidence, and requires owner alerting. Automation may place a HOLD automatically; it may not automatically clear it.
8. Explicit organization-wide do-not-contact language triggers durable company/domain SUPPRESSION across current and future contacts, imports, migrations, provider changes, builder changes, database replacements, and later releases.
9. Individual unsubscribe remains individual by default unless the wording clearly applies organization-wide or other reliable evidence establishes broader scope.
10. Suppression and negative signals outrank growth. Imports, enrichment, refreshes, and discovery may never overwrite unsubscribe, complaint, HOLD, organization suppression, owner suppression, or a higher-priority negative signal.
11. Organization-wide incidents require both an immediate owner email alert when operationally available and a high-priority persistent Owner Console/coordination alert that remains until acknowledged.
12. Owner alerts should contain organization/domain, trigger, time, scope, source/evidence reference, automatic action, HOLD/SUPPRESSED state, pending-send action, and whether an owner decision is required; do not expose unnecessary sensitive information.
13. SMS is not required unless Roger separately activates it.
14. No future builder, provider, import, migration, cleanup, optimization, automation, or version may weaken, omit, reset, bypass, or reinterpret this rule into something less protective. Every applicable material release records it as ADOPTED unless Roger explicitly supersedes it.
15. This rule does not itself authorize sending, volume increases, new campaigns, mailbox activation, hold removal, suppression removal, or contact with a suppressed organization.
16. Franklin Navigator profile/contact source builders remain authoritative for their own data; implementing this rule must not mutate profile facts merely for outreach.

## Current Franklin Navigator pilot enforcement

- Mailshake campaign: 1553662
- First touch only.
- Exact profile binding required.
- Current campaign must contain no duplicate recipient domains because all ten first touches are eligible to send within one business-day window.
- Generic role inboxes are allowed only as one organization-level message for that organization.
- Any detected complaint, organization-wide DNC, domain HOLD, domain SUPPRESSION, roster/profile mismatch, or other fail-closed condition pauses the campaign.
- Existing deliverability compliance hold remains independently active until its own gates are satisfied.

## Persistence rule

The canonical durable ledger is `org_domain_safety_state.json`. Runtime detection must be reflected into that ledger through the approved owner/SRE automation path. A runtime condition must never be treated as cleared merely because a service restarted.

## Required adoption receipt

Every material applicable release must preserve an `RR_ORG_OUTREACH_001_ADOPTION_RECEIPT` showing rule status, implementation points, tests, blocked items, owner-alert status, and confirmation that existing rules were not weakened.
