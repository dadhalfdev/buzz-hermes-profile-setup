# Buzz relay & membership — how it actually works

Condensed under-the-hood notes for anyone who wants to understand (or debug) the
installer's steps. Source of truth: the `block/buzz` OSS repo (relay, desktop, mobile,
CLI, agent harness). The Hermes Buzz adapter lives at `plugins/platforms/buzz/` inside a
Hermes install (adapter.py + plugin.yaml).

## Relay info (NIP-11)

`GET https://<community>.communities.buzz.xyz/` returns NIP-11 JSON: `name`,
`description`, `version`, `supported_nips` (1,2,10,11,16,17,23,25,29,33,38,42,50,56,43),
and `auth_required: true`, `restricted_writes: true`. The `wss://` endpoint returns a
`101 Switching Protocols` handshake for the WS relay protocol. The `https://` base URL is
what `relay_url` / `BUZZ_RELAY_URL` wants.

## Membership: relay vs channel (the distinction that matters)

- Channel membership (`buzz channels add-member --channel <uuid> --pubkey <hex> --role bot`)
  writes a channel-member event and returns `accepted:true` immediately.
- BUT it does **not** grant relay membership. Acting as that key afterwards returns:
  `{"error":"auth_error","message":"relay error 403: relay_membership_required"}`.
- Relay membership for an agent can be granted two ways (pick the right one):
  - **Invite mint+claim (the Hermes path — fully programmatic, no desktop).** The owner
    mints an invite (`POST /api/invites`, NIP-98 signed by the *owner*); the joining key
    claims it (`POST /api/invites/claim`, NIP-98 signed by the *joining* key), optionally
    after accepting the join-policy (`POST /api/invites/accept-policy`, unsigned). Result:
    a plain `member`-role relay member — exactly what the Hermes adapter needs.
  - **Native agent / NIP-OA attestation (the desktop path — for Buzz's OWN agent
    framework, NOT Hermes).** Buzz Desktop → "Add agents" → "Create a new agent" → pick a
    harness (goose/Codex/`buzz-agent`). This generates a key + NIP-OA auth tag for a
    *Buzz-native* agent. Connecting **Hermes** does NOT use this — Hermes is a plain relay
    member, not a Buzz harness, and "create agent" asks you to pick a harness Hermes isn't.
- **Self-echo suppression by pubkey**: the adapter ignores inbound events whose pubkey
  equals its own. If the profile uses the *owner's own* nsec, the agent IS the owner, has
  no separate identity, and will ignore the owner's messages. Always a dedicated keypair.
  Detect via `buzz users get` (display_name / `role: owner` reveal it).

## Invite mint+claim — the exact HTTP contract

Endpoints (relative to the relay's HTTPS base `https://<community>.communities.buzz.xyz`):

| Step | Method + path | Auth | Body | Returns |
|------|---------------|------|------|---------|
| 1. mint | `POST /api/invites` | NIP-98 (owner/admin) | `{}` or `{"ttl_secs":N,"max_uses":N}` | `{code, expires_at, max_uses, url}` (code is `v2.`-prefixed) |
| 2. accept-policy | `POST /api/invites/accept-policy` | **none** (unsigned) | `{code, policy_version, age_confirmed:true}` | `{receipt}` |
| 3. claim | `POST /api/invites/claim` | NIP-98 (joining key) | `{code, policy_receipt}` | `{status:"joined", role:"member", community_id, host}` |

Only mint and claim are signed. Step 2 is only required when the community has a join
policy (`GET /api/join-policy` returns `{"policy":{...}}`); if it returns `{}` (no policy),
skip it. When `age_attestation_required:true`, `age_confirmed` MUST be `true` and
`policy_version` MUST match `policy.version` exactly, or accept-policy returns
`join_policy_not_accepted` and claim returns `join_policy_required`.

### NIP-98 signing (kind 27235)

`Authorization: Nostr <base64(json)>` where the JSON event is:

```json
{"id":"<hex>","pubkey":"<hex>","created_at":<unix>,"kind":27235,
 "tags":[["u","<url>"],["method","POST"],["payload","<sha256hex(body)>"]],
 "content":"","sig":"<64-byte BIP-340 schnorr hex>"}
```

- `id` = sha256 of the canonical serialization `[0, pubkey_hex, created_at, 27235, tags, ""]`
  (compact JSON, `json.dumps(..., separators=(",",":"))`, no spaces, lowercase hex pubkey).
- Signature is **BIP-340 Schnorr** over the 32-byte `id`. Use
  `coincurve.PrivateKey.sign_schnorr(id_bytes, None)`
  (the `cryptography` lib does ECDSA only — it cannot sign Schnorr).
- `u` tag = exact request URL, scheme `https` (the relay serves `wss`, but NIP-98 `u` uses
  the HTTPS base). `method` = `POST`. `payload` = sha256 hex of the exact request body bytes.
- `created_at` must be within ±60s of server time.
- No `nonce` tag required (replay protection is by event `id`, unique per body).

## Cloudflare note (why curl, not urllib)

The relay sits behind Cloudflare. Python `urllib` requests are blocked with error `1010`
(browser-signature ban) while `curl` with a browser `User-Agent` passes. Do relay HTTP
calls via `curl` (or shell out to curl from Python via `subprocess`).

## Keypair / bech32 gotcha

`convertbits` 8→5 MUST use `pad=True` when encoding an nsec. A non-padding conversion
drops the final bit and produces an nsec that decodes to a **different** private key
(silent round-trip breakage). The installer self-verifies the round-trip before use.

## Verification (the truth is in state files, not logs)

- `~/.hermes/profiles/<name>/gateway_state.json` — `"buzz":{"state":"connected"}`.
- `~/.hermes/profiles/<name>/channel_directory.json` — `"buzz": [...]` (empty until
  channels surface).
- The Buzz adapter logs to a different sink than Telegram/Slack, so it never appears in
  `journalctl -u hermes-gateway-<name>` — that's a false negative, not a bug.
