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
1. Add a visible unsubscribe link to the sending signature; current Mailshake two-click behavior may remain for this low-volume pilot because Mailshake recommends it to reduce scanner-triggered accidental unsubscribes.
2. Add Franklin Navigator's valid physical postal address.
3. Add a clear commercial/community-outreach identification in the footer.
4. Verify the final live signature in Mailshake.
5. Before releasing the promotional campaign at all, send one controlled real message to an owner-controlled mailbox and inspect the raw received headers. Require both a valid HTTPS `List-Unsubscribe` header and `List-Unsubscribe-Post: List-Unsubscribe=One-Click`. Do not infer compliance from Mailshake's visible-link setting. Re-check after any provider/mailbox/SMTP architecture change.

No campaign send may resume until those items are verified.


## Controlled Gmail compliance test — 2026-09-25

Production-path test campaign:
- Mailshake campaign ID: 1554023
- Recipient: owner-controlled Gmail address
- Real Mailshake send: PASS
- SPF: PASS
- DKIM: PASS
- DMARC: PASS
- Visible Mailshake unsubscribe link: PASS
- Mailshake unsubscribe activity registration: PASS (1 unsubscribe recorded)
- RFC 8058 List-Unsubscribe header: FAIL / ABSENT
- RFC 8058 List-Unsubscribe-Post header: FAIL / ABSENT

Disposition:
- Main Franklin Navigator first-10 campaign remains PAUSED / FAIL-CLOSED.
- Compliance hold MUST NOT be released based only on the working body unsubscribe link.
- Public Mailshake documentation reviewed on 2026-09-25 documents body-link unsubscribe behavior and one-click/two-click body-link handling, but no documented control or public API parameter was found for adding RFC 8058 List-Unsubscribe / List-Unsubscribe-Post headers to SMTP-connected sends.
- Technical support inquiry sent to hello@mailshake.com on 2026-09-25 asking whether Mailshake can add RFC 8058 headers for SMTP-connected accounts and, if so, the exact configuration required.
- No provider migration, custom sender replacement, or compliance-gate weakening is authorized by this receipt.

Next gate:
- Obtain authoritative Mailshake answer OR independently qualify another sending path that demonstrably emits both required RFC 8058 headers in an actual received message.
- Re-test with a real owner-controlled Gmail delivery before releasing the first-10 campaign.


## Owner-approved low-volume RFC 8058 disposition — 2026-09-28

Owner explicitly approved proceeding with the existing Franklin Navigator first-10 pilot without RFC 8058 headers because the pilot is capped at 10/day and remains subject to all other verified protections.

Release conditions retained:
- visible unsubscribe link: required and already tested working
- durable suppression: required and already tested working
- SPF: PASS
- DKIM: PASS
- DMARC: PASS
- valid physical postal address: required
- open tracking: OFF
- click tracking: OFF
- first-touch only
- no automatic scale-up
- any bounce/unsubscribe/complaint during the low-volume pilot remains a fail-closed review trigger
- organization/domain suppression and hold rules remain fully active

RFC 8058 remains a mandatory scale gate before any material expansion approaching mailbox-provider bulk-sender thresholds and after any material provider/mailbox/SMTP/delivery-architecture change.

This approval does not authorize follow-ups, volume increases, new mailboxes, or provider changes.


## Qualified RFC 8058 direct-Zoho path — 2026-09-29

A production-path owner-controlled test was sent through the Franklin SRE bridge using the existing Zoho mailbox `community@franklinnavigator.com`.

Received Gmail raw-message verification:
- SPF: PASS
- DKIM: PASS
- DMARC: PASS
- TLS delivery: PASS
- `List-Unsubscribe`: PRESENT with HTTPS Franklin unsubscribe endpoint
- `List-Unsubscribe-Post`: `List-Unsubscribe=One-Click` PRESENT
- visible unsubscribe URL: PRESENT
- physical postal address: PRESENT
- open/click tracking: not added by the SRE direct sender

One-click endpoint verification:
- real HTTPS POST using `List-Unsubscribe=One-Click`: HTTP 200
- durable Mailshake unsubscribe-list handoff: executed
- main campaign safety pause: retained
- self-test was immediately disabled after verification to prevent repeat test actions

Disposition:
- The direct Zoho SMTP path through the Franklin SRE bridge is QUALIFIED for RFC 8058 one-click unsubscribe.
- Mailshake campaign 1553662 remains paused and must not be unpaused for sending because Mailshake itself does not emit the required RFC 8058 headers on the tested SMTP-connected path.
- Any real first-10 sending moved to the qualified direct path must preserve the same exact roster, first-touch-only copy, owner BCC, business-hours pacing, suppression rules, organization/domain safety rules, and fail-closed monitoring.
- No scale-up is authorized by this qualification.


## Follow-up and complaint-monitoring hardening — 2026-09-29

Implemented:
- two conservative direct-path follow-up templates, at +5 business days and +7 additional business days
- no third follow-up enabled for the pilot
- stop-on-reply, unsubscribe, bounce, complaint, correction/removal request, and organization/domain hold/suppression rules
- Zoho IMAP monitoring and sent-mail ledger architecture for duplicate prevention and reply/bounce checks
- Gmail Feedback-ID header for future complaint analysis
- custom DKIM signing layer prepared so RFC 8058 List-Unsubscribe and List-Unsubscribe-Post headers can both be covered by a Franklin-controlled DKIM signature

Important qualification:
- the existing Zoho DKIM signature on the first RFC 8058 test covered List-Unsubscribe but did not list List-Unsubscribe-Post in its DKIM h= field.
- therefore a Franklin-controlled second DKIM signature is being added and must be DNS-verified in a new selector before outreach is released.
- Mailshake remains paused and is not used for actual sends.
