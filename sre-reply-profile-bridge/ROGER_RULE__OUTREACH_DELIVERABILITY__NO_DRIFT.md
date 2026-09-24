# ROGER RULE — FRANKLIN NAVIGATOR OUTREACH DELIVERABILITY, ANTI-SPAM, AND LONG-TERM SENDER REPUTATION — NO DRIFT

**Rule ID:** RR-FN-OUTREACH-DELIVERABILITY-2026-09-24-V1  
**Authority:** Roger Rule / Owner directive  
**Effective:** 2026-09-24  
**Scope:** Franklin Navigator SRE Owner Console / Revenue Engine outbound email campaigns, including Mailshake and any successor provider.  
**Status:** DURABLE / FAIL-CLOSED / NO DRIFT

## Core rule

Franklin Navigator outreach must be built and operated to preserve long-term sender reputation, legal compliance, inbox placement, and user trust. No future builder, automation, campaign, migration, or provider change may silently weaken these protections. Safety controls may be tightened automatically when evidence warrants it, but may not be loosened without explicit owner approval.

## Durable controls

1. **Truthful identity and content.** From/Reply-To/routing identity and subject lines must be accurate and non-deceptive. Use a stable Franklin Navigator sender identity. No invented person identity may be used to create false trust.
2. **Commercial-email compliance footer.** Every commercial outreach message must include Franklin Navigator's valid physical postal address, a clear statement that the message is commercial/community outreach, and an easy opt-out path.
3. **Unsubscribe protection.** Reply-based opt-outs remain enabled. A visible unsubscribe link must be present for scalable outreach. Mailshake's visible-link One-click/Two-click setting is not assumed to satisfy Gmail/Yahoo RFC 8058 requirements; the current low-volume pilot may retain Mailshake's recommended two-click visible-link behavior. Before high-volume scale, RFC 8058 one-click header support must be explicitly verified. Opt-outs are durable suppressions across remaps, imports, campaigns, and provider migrations.
4. **Authentication gate.** Before material scale, the sending domain/mailbox must pass SPF, DKIM, DMARC, TLS, and alignment checks appropriate to the provider. Mailshake's green domain-health indicator is not by itself sufficient evidence because its automatic check only verifies presence for some records.
5. **Complaint-rate rule.** Target Gmail user-reported spam rate is below 0.10%. Never knowingly continue at or above 0.30%. Any observable spam complaint in a low-volume pilot causes a fail-closed review before more outreach.
6. **Pilot bounce/unsubscribe rule.** During the first 20 real outreach sends from a mailbox, any hard bounce or unsubscribe pauses further automated outreach for review. At larger volume, a 2% bounce rate is an internal warning threshold and 5% is a hard pause/step-back threshold.
7. **Slow ramp / no spikes.** Do not jump sending volume. Default Mailshake ramp ceiling per mailbox: Week 1 <=20/day; Week 2 <=40/day; Week 3 <=55/day; Week 4 <=75/day; Week 5 <=100/day. Default long-term ceiling is 100/day per mailbox unless fresh evidence and explicit owner approval justify otherwise.
8. **Current pilot remains stricter.** First Franklin Navigator pilot remains <=10/day, one at a time, spaced across Monday-Friday business hours, first-touch only.
9. **No automatic scale-up.** Automation may monitor and pause automatically, but may not silently raise daily caps, add large cohorts, add follow-ups, or activate new sending mailboxes/domains. Scale requires a clean prior cohort and explicit owner authorization.
10. **Recipient-quality rule.** Use relevant, source-backed, profile-bound Franklin recipients. Do not use purchased, guessed, dictionary-generated, scraped-in-violation-of-site-terms, stale, or unverified bulk lists. Exact profile binding and currentness are required.
11. **Suppression durability.** Bounces, opt-outs, spam complaints, invalid addresses, and explicit "do not contact" signals must remain suppressed across future campaigns and provider migrations. Never re-add them through a fresh import.
12. **Tracking restraint.** Open/click tracking is OFF by default for cold outreach. Do not turn it on merely for analytics. Use reply, bounce, unsubscribe, and provider reputation signals instead.
13. **Natural cadence.** Space sends; do not blast multiple messages at once. Default minimum batch size is one message at a time for new/low-volume mailboxes.
14. **One provider per mailbox.** Do not send cold outreach simultaneously from the same mailbox through multiple automation providers. Avoid unexplained volume or cadence changes.
15. **Warm-up requirement.** A new domain or mailbox must not immediately inherit mature sending volume. Warm it gradually before real outreach; Mailshake recommends at least 1-2 weeks of warm-up for a new outreach mailbox and a gradual ramp.
16. **Provider-reputation monitoring.** Before scaling materially, establish Gmail Postmaster Tools or an equivalent reputation monitor when available. If reputation/complaint evidence is unavailable, scaling remains conservative.
17. **Fail closed on automation uncertainty.** Roster mismatch, profile-binding mismatch, provider/API error that prevents suppression/currentness checks, campaign drift, unexpected follow-up, or material configuration mismatch pauses automation rather than guessing.
18. **No hidden regression.** Future campaign/provider migrations must carry this entire rule forward, including suppression state, ramp stage, monitoring thresholds, authentication gate, unsubscribe requirements, and audit receipts.
19. **Research refresh.** Before each material expansion of outreach volume or provider architecture, re-check current Google, Yahoo, FTC, provider, and other relevant sender requirements. Adopt/adapt only changes that materially improve compliance, deliverability, or safety.
20. **Owner-only weakening.** These safeguards can be tightened automatically. They can be weakened only by Roger's explicit instruction after the tradeoff is explained.

## Current source baseline — 2026-09-24

- Google Email Sender Guidelines: https://support.google.com/mail/answer/81126
- Google Sender Guidelines FAQ: https://support.google.com/mail/answer/14229414
- Yahoo Sender Best Practices: https://senders.yahooinc.com/best-practices/
- FTC CAN-SPAM Compliance Guide: https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business
- Mailshake Deliverability Common Questions: https://docs.mailshake.com/article/249-deliverability-common-questions
- Mailshake Sending Cadence / Copywriting Deliverability: https://docs.mailshake.com/article/231-copywriting-deliverability
- Mailshake Sending Calendar Rules: https://docs.mailshake.com/article/140-how-can-i-tweak-sending-schedules
- Mailshake Unsubscribe Management: https://docs.mailshake.com/article/60-how-does-mailshake-manage-unsubscribes
- Mailshake Domain Health Checks: https://docs.mailshake.com/article/415-domain-health-checks-when-connecting-a-sending-account
- Mailshake One-click vs Two-click Unsubscribe: https://docs.mailshake.com/article/201-one-click-vs-two-click-unsubscribe-setting
- Microsoft Outlook High-Volume Sender Requirements: https://techcommunity.microsoft.com/blog/microsoftdefenderforoffice365blog/strengthening-email-ecosystem-outlook%E2%80%99s-new-requirements-for-high%E2%80%90volume-senders/4399730

## Current first-10 enforcement

- Campaign ID: 1553662
- Max intended prospects: 10
- First-touch messages only: 1
- Max daily sends: 10
- One email per time slot
- Open tracking: off
- Click tracking: off
- Exact recipient/profile binding required
- Any roster mismatch: pause
- Completion at 10 sends: lock closed
- Any bounce or unsubscribe during first 10: pause for review
- Old Reply.io sync: disabled
- BCC audit copy: reachrgnow@gmail.com

This document is the durable authority for Franklin Navigator outbound deliverability.