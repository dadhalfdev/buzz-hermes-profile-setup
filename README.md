# buzz-hermes-profile-setup

One command connects a **Hermes agent profile running on a VPS** (self-hosted Linux server,
gateway up as an always-on background service) to a [Buzz](https://buzz.dev) (Nostr)
community — as a first-class agent with its own identity, avatar, and access rules. It
builds the CLI, mints a dedicated keypair, claims relay membership, sets the profile, wires
the gateway, restarts, and verifies.

**Scope:** this is for VPS / self-hosted Hermes profiles. It compiles the `buzz` CLI from
source (`git` + `cargo`) and writes into `~/.hermes/profiles/<name>/` — both of which
assume a real Linux host you can shell into. It is not for Hermes Desktop-only setups.

This exists because the manual path is brutal: no prebuilt CLI, a bech32 keypair encoding
bug, Cloudflare blocking `urllib`, a relay-vs-channel membership distinction that silently
403s, self-echo suppression that hides the agent from you, and a desktop "create agent" flow
that's the wrong one for Hermes. The installer absorbs all of it.

## Install

Clone this repo into your Hermes skills directory (the full structure matters — the
installer script and the deep-reference notes live in subfolders):

```bash
mkdir -p ~/.hermes/skills/devops
git clone https://github.com/dadhalfdev/buzz-hermes-profile-setup.git \
  ~/.hermes/skills/devops/buzz-hermes-profile-setup
```

## Run

```bash
uv run --with coincurve python3 \
  ~/.hermes/skills/devops/buzz-hermes-profile-setup/scripts/buzz_install.py
```

`uv run --with coincurve` auto-resolves the one non-stdlib dependency (BIP-340 Schnorr
signing) into an ephemeral env — no global pip, works under PEP 668. (No `uv`? See
`requirements.txt` — `coincurve` is the only dep, install it however you normally would.)

The script prompts for the few things it can't infer — profile name, community relay URL,
an owner key to mint the invite, agent name, avatar URL — and does the rest silently.
Every input can also be set via `BUZZ_INSTALL_*` env vars for headless/manifest-driven runs.

## Prerequisites

- `git` + `cargo` (Rust) — used to build the `buzz` CLI from source on first run (there are
  no prebuilt CLI releases; only desktop app binaries).
- `uv` (recommended) — pulls in `coincurve`.
- An owner/reference key for the community (to mint an invite) — needed once, never stored.

## What you can control

The full input manifest is in `SKILL.md`. Highlights:

- **Identity** — dedicated keypair (auto-generated, never your own), display name, avatar
  URL, bio, NIP-05.
- **Access** — community mode (any member) vs. a whitelist of npubs; whether the agent only
  replies when `@`-mentioned in channels.
- **Channels** — which to watch, and the home channel for cron/notify delivery.
- **Behaviour** — presence, status line, poll interval.

## Files

- `SKILL.md` — the skill itself (input manifest, pitfalls, verification).
- `scripts/buzz_install.py` — the self-contained end-to-end installer.
- `references/buzz-internals.md` — how the relay/membership/NIP-98 pieces actually work, for
  debugging or for building your own tooling.

## License

MIT.
