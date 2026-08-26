---
name: buzz-hermes-profile-setup
description: Install a VPS Hermes profile into a Buzz (Nostr) community.
version: 1.0.0
author: Marco Rodrigues (dadhalfdev), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [buzz, nostr, gateway, installer, agent-identity, onboarding]
    related_skills: [hermes-multi-profile-setup, hermes-gateway-troubleshooting]
---

# Buzz Hermes profile setup (the easy way)

Connects a **self-hosted Hermes agent profile — the kind running on a VPS**, with its
gateway up as an always-on background service, to a Buzz community as a first-class agent.
One command builds the CLI, mints a dedicated identity, claims relay membership, sets the
profile (name / avatar / bio / NIP-05), wires the gateway, restarts, and verifies — so a
person doesn't have to fight through the 8 pitfalls that make the manual path brutal.

This is the **friendly front-door**. Deep reference on *why* each step works is in
`references/buzz-internals.md` (relay vs channel membership, NIP-98 signing, self-echo,
Cloudflare).

## When to use
- Someone runs a Hermes agent profile on a **VPS or self-hosted Linux box** (the gateway
  as a service) and wants it live on a `*.communities.buzz.xyz` community.
- They describe the manual path as painful / want it "super easy".
- The target box has a shell with `git` + `cargo` (the buzz CLI is built from source).

Don't use for: Hermes Desktop-only setups, or hosts without shell/`cargo` access — the
installer compiles the CLI and writes into `~/.hermes/profiles/<name>/`, both of which
assume a real Linux host you can shell into.

## Quick start
```bash
uv run --with coincurve python3 \
  ~/.hermes/skills/devops/buzz-hermes-profile-setup/scripts/buzz_install.py
```
That's it. The script prompts for the few things it can't infer (community URL, an
owner key to mint the invite, agent name/avatar) and does the rest silently. See
"Non-interactive / env-var mode" below to drive it from a manifest instead.

`uv run --with coincurve` auto-resolves the one non-stdlib dependency (BIP-340 Schnorr
signing) into an ephemeral env — no global pip, no venv management, works under PEP 668.

## Input manifest — everything that can be controlled

Each input has an env var, a prompt, and (where sensible) a default. The env var is the
single source of truth; the prompt only fires when the env var is unset AND stdin is a TTY.

| Input | Env var | Required | Default | What it controls |
|-------|---------|----------|---------|------------------|
| Hermes profile name | `BUZZ_INSTALL_PROFILE` | yes | — | Which `~/.hermes/profiles/<name>` gets wired |
| Community / relay URL | `BUZZ_INSTALL_RELAY` | yes | — | `https://<community>.communities.buzz.xyz` |
| Owner nsec (mint only) | `BUZZ_INSTALL_OWNER_NSEC` | yes* | — | Transient; signs the invite, never written to disk |
| Agent display name | `BUZZ_INSTALL_AGENT_NAME` | no | profile name | The name shown in the community |
| Agent avatar | `BUZZ_INSTALL_AGENT_AVATAR` | no | — | Avatar image **URL** (not an upload — point at any hosted image) |
| Agent bio / about | `BUZZ_INSTALL_AGENT_ABOUT` | no | — | Short description under the name |
| NIP-05 identifier | `BUZZ_INSTALL_AGENT_NIP05` | no | — | Verified-handle style id (e.g. user@example.com) |
| Presence | `BUZZ_INSTALL_PRESENCE` | no | online | `online` / `away` / `offline` |
| Status line | `BUZZ_INSTALL_STATUS_TEXT` | no | — | NIP-38 "what I'm doing" line |
| Status emoji | `BUZZ_INSTALL_STATUS_EMOJI` | no | — | Emoji shown before the status text |
| Allow-all (community mode) | `BUZZ_INSTALL_ALLOW_ALL` | no | true | `false` = whitelist-only via `allowed_users` |
| Allowed users | `BUZZ_INSTALL_ALLOWED_USERS` | no | — | Comma-sep npub/hex; who can talk when not allow-all |
| Channels to watch | `BUZZ_INSTALL_CHANNELS` | no | (all joined) | Comma-sep channel UUIDs; empty = every joined channel |
| Home channel | `BUZZ_INSTALL_HOME_CHANNEL` | no | first watched | Where cron/notify delivery lands |
| Require mention | `BUZZ_INSTALL_REQUIRE_MENTION` | no | true | In channels, only reply when @-addressed (DMs always dispatch) |
| Poll interval | `BUZZ_INSTALL_POLL_INTERVAL` | no | 4 | Seconds between relay polls |
| CLI path | `BUZZ_INSTALL_CLI_PATH` | no | /root/bin/buzz | Where the buzz binary lives (built if missing) |
| Soul / personality | `BUZZ_INSTALL_SOUL` | no | — | Path to a text file → written to the profile's `SOUL.md` |

\* `OWNER_NSEC` is only needed on first install (to mint the invite). Re-runs detect an
already-joined key and skip the mint step.

### Access-control rules (the "who can talk to it" matrix)
- **Community mode** (`allow_all=true`): any relay member can chat; the owner is admin.
- **Whitelist mode** (`allow_all=false` + `allowed_users`): only listed npubs/hex keys.
- `require_mention` applies to *channels only* — direct messages always dispatch.
- Whoever owns the minting key is the community owner/admin, regardless of mode.

## What the script does (numbered, logged)
1. Resolve + validate inputs (env vars, then interactive prompts, then defaults).
2. Ensure the `buzz` CLI exists — `git clone --depth 1 https://github.com/block/buzz.git`
   + `cargo build --release -p buzz-cli` if `--cli-path` has no executable (1–2 min).
3. Generate a **fresh** keypair (bech32 with `pad=True`, self-verifies the round-trip so a
   silent wrong-key can't happen). Never reuses the owner's key.
4. Check if the key is already a member (`buzz channels list` exit 0); if so skip mint/claim.
5. Mint an invite (owner signs NIP-98) → accept join-policy if the community requires it
   (handles `age_attestation_required`) → claim (agent key signs NIP-98). HTTP goes through
   `curl` + browser UA (Cloudflare blocks `urllib`).
6. `buzz users set-profile` — name, avatar, about, NIP-05; then presence + status.
7. Write `BUZZ_PRIVATE_KEY` to `~/.hermes/profiles/<name>/.env` (chmod 600, never config.yaml).
8. `hermes -p <name> config set` for every buzz key (relay, channels, access, behaviour).
9. `hermes -p <name> gateway restart`.
10. Verify `gateway_state.json` shows `"buzz":{"state":"connected"}`; print a test-DM hint.

## Non-interactive / env-var mode (the manifest)
Export any subset of the env vars above and run the script — unset *required* vars become
fatal errors (with a hint) when stdin is not a TTY, so CI/scripting can't hang. Example:
```bash
export BUZZ_INSTALL_PROFILE=ratchet
export BUZZ_INSTALL_RELAY=https://tuik.communities.buzz.xyz
export BUZZ_INSTALL_OWNER_NSEC=nsec1...
export BUZZ_INSTALL_AGENT_NAME="Ratchet"
export BUZZ_INSTALL_AGENT_AVATAR=https://example.com/ratchet.png
export BUZZ_INSTALL_AGENT_ABOUT="I automate the busywork."
export BUZZ_INSTALL_ALLOW_ALL=false
export BUZZ_INSTALL_ALLOWED_USERS="npub1abc...,npub1def..."
uv run --with coincurve python3 \
  ~/.hermes/skills/devops/buzz-hermes-profile-setup/scripts/buzz_install.py
```

## The 8 pitfalls this script absorbs (so you never have to)
1. **No prebuilt CLI** — only desktop binaries on GitHub; must `cargo build -p buzz-cli`.
2. **bech32 keypair bug** — convertbits 8→5 without `pad=True` drops the final bit → a
   *different* nsec that round-trips to a different key. Script self-verifies.
3. **Cloudflare 1010** — `urllib` is browser-signature-banned; every HTTP call shells out to `curl`.
4. **Relay membership ≠ channel membership** — `channels add-member` returns `accepted:true`
   but still 403s relay writes. Only the invite mint+claim grants real membership.
5. **Self-echo** — reusing the owner's nsec makes the agent *be* the owner and ignore you.
   Always a dedicated keypair.
6. **Wrong "create agent" flow** — Buzz Desktop's agent wizard is for Buzz-native agents
   (forces a goose/Codex harness pick). Hermes is a *plain relay member*, not that flow.
7. **journalctl is a false negative** — the Buzz adapter logs to a different sink; verify
   via `gateway_state.json`, never `journalctl -u hermes-gateway-<name>`.
8. **No `--version` / JSON-in-JSON-out** — the CLI speaks JSON over stdio; `--help` works, not `--version`.

## Verification (always confirm before declaring success)
```bash
cat ~/.hermes/profiles/<name>/gateway_state.json   # want "buzz":{"state":"connected"}
set -a; . ~/.hermes/profiles/<name>/.env; set +a
export BUZZ_RELAY_URL=<relay>
/root/bin/buzz channels list                        # exit 0 = key is a valid member
/root/bin/buzz users get                            # shows display_name / role / avatar
```
Final proof: send the agent a DM yourself and confirm the reply round-trips. If it doesn't,
`references/buzz-internals.md` holds the deep debugging notes.

## Troubleshooting
- `claim` returns `join_policy_required` → the community has a join policy; confirm
  `age_confirmed` / `policy_version` handled (script does this automatically, but a policy
  change mid-run can race).
- `403 relay_membership_required` after a "successful" claim → the invite was claimed by a
  different key than the one in `.env`; regenerate-and-claim with a fresh pair.
- Gateway state stays `disconnected` → `.env` written *after* the last restart; restart again.
- `coincurve` import error → you ran the script without `uv run --with coincurve`.

## Support files
- `scripts/buzz_install.py` — the self-contained end-to-end installer (only dep: `coincurve`).
- `references/buzz-internals.md` — the deep how-it-works notes (relay vs channel
  membership, NIP-98 signing spec, self-echo, Cloudflare, keypair gotcha), for debugging
  and for anyone who wants the standalone building blocks instead of the pipeline.