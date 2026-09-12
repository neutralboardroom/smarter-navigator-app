# SRE Reply Exact-Profile Personalization Bridge

This branch is an isolated SMARTER Revenue Engine automation lane. It does not change Smarter Navigator production code and must not be merged into Navigator product authority merely to operate the bridge.

## Purpose

Automatically prepare Franklin Navigator prospect records and sequence emails so every outbound prospect receives:

1. a verified person greeting when first-party evidence supports a named contact, otherwise an intentional `<Business> team` greeting;
2. that prospect's exact live canonical Franklin Navigator profile URL;
3. the same exact profile ID in Reply;
4. an exact-profile claim/manage path from the live profile page;
5. no generic Franklin membership/business-membership/directory/homepage fallback link.

If identity, contact route, live profile, canonical URL, or exact claim path is ambiguous, the record is held. The campaign must preserve authorized volume by sourcing the next qualified Franklin prospect one-for-one rather than weakening the verification standard.

## Reply fields

The bridge uses these existing workspace text fields:

- `Profile URL`
- `Franklin Profile ID`
- `Outreach Greeting`
- `Franklin Profile Link State`

## Reply template variables

Shared sequence email bodies are normalized to:

- `{{Outreach_Greeting}}`
- `{{Profile_URL}}`

Reply automatically converts spaces in custom field labels to underscores in custom-variable names.

## Secure authorization

Set `REPLY_API_KEY` only as a secret environment variable on the Render service. Never commit it to GitHub and never paste it into a public chat.

Create/copy a dedicated Reply API key at Reply.io -> Settings -> API Key. Minimum useful scopes should cover contact read/write and sequence read/write/operate. The bridge validates the live profile before writing personalization.

## Runtime

Render service: `sre-reply-profile-bridge`

Environment:

- `REPLY_API_KEY` — secret, required
- `REPLY_SEQUENCE_ID=1768444`
- `SYNC_INTERVAL_SECONDS=900`

Endpoints:

- `/health` — non-secret readiness summary
- `/status` — last sync outcome and exception counts

## Safety invariants

- no generic Franklin commercial/action destination in prospecting emails;
- no guessed person name;
- no wrong-profile fallback;
- no send-volume reduction hidden as success;
- no send-limit increase by the bridge;
- no SMS/voice automation;
- no payment mutation;
- no membership inference from profile existence;
- no sequence start/resume by this bridge (SRE launch gate remains the authority).
