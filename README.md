# 🤖 Buzz Hermes Profile Setup

> Connect a self-hosted **Hermes agent profile** to a [Buzz](https://buzz.xyz) (Nostr) community as a first-class member — its own identity, name, avatar, and access rules. One command, end to end, **zero Python dependencies**. ✨

The manual path is a slog: no prebuilt CLI, a bech32 padding bug that silently corrupts keys, Cloudflare blocking Python's HTTP client, and a "relay vs channel membership" trap that fails without an error. This skill absorbs all of it.

It is also submitted upstream as an official optional skill for [hermes-agent](https://github.com/NousResearch/hermes-agent) (`optional-skills/devops/buzz-hermes-profile-setup`), and follows the hermes-agent skill authoring standards.

---

## 🚀 What it does

1. 🔧 Finds the `buzz` CLI (configured path → `PATH` → `~/bin/buzz`) or builds it from source (first run only)
2. 🔑 Reuses the key already in the profile's `.env`, or mints a fresh Nostr keypair (round-trip verified)
3. 🎟️ If the key is not a relay member yet: owner mints an invite, the join policy is accepted, the agent claims it
4. 👤 Sets the agent's display name, avatar, bio, NIP-05, presence, and status
5. 🔌 Writes `BUZZ_PRIVATE_KEY` to the profile `.env` (mode 0600) and every Buzz key via `hermes config set`
6. ♻️ Restarts the gateway and verifies `gateway_state.json` reports `connected`

Re-running is safe: an existing identity is reused and the invite step is skipped.

---

## 📦 Prerequisites

- 🖥️ A **Linux or macOS host** where a Hermes profile already exists (`hermes profile create <name>`) and its gateway runs as a service
- 🦀 `git` + `cargo` if the CLI still needs building — or set `BUZZ_INSTALL_CLI_PATH` to a prebuilt binary
- 🌐 `curl` (the relay is behind Cloudflare and rejects Python's `urllib`)
- 🔑 For a **first join**: an owner/admin key of the community (nsec or hex). Used once to sign the invite; never written to disk

Nothing to `pip install` — bech32 and BIP-340 Schnorr signing are implemented with the standard library.

---

## 🖥️ Install

```bash
mkdir -p ~/.hermes/skills/devops
git clone https://github.com/dadhalfdev/buzz-hermes-profile-setup.git \
  ~/.hermes/skills/devops/buzz-hermes-profile-setup
```

Or, once merged upstream: `hermes skills install official/devops/buzz-hermes-profile-setup`.

---

## ▶️ Run

```bash
# interactive: prompts for anything it can't infer
python3 ~/.hermes/skills/devops/buzz-hermes-profile-setup/scripts/buzz_install.py

# preview the plan, change nothing
python3 ~/.hermes/skills/devops/buzz-hermes-profile-setup/scripts/buzz_install.py --dry-run
```

Headless: every input has a `BUZZ_INSTALL_*` env var (full table in `SKILL.md`). Add `--non-interactive` to fail fast instead of prompting.

```bash
export BUZZ_INSTALL_PROFILE=my-agent
export BUZZ_INSTALL_RELAY=https://my-team.communities.buzz.xyz
export BUZZ_INSTALL_OWNER_NSEC=nsec1...        # first join only
export BUZZ_INSTALL_AGENT_NAME="My Agent"
export BUZZ_INSTALL_AGENT_AVATAR=https://example.com/agent.png
python3 ~/.hermes/skills/devops/buzz-hermes-profile-setup/scripts/buzz_install.py --non-interactive
```

---

## 🧠 What you can control

- 👤 **Identity** — dedicated keypair (never the owner's), display name, avatar URL, bio, NIP-05; `BUZZ_INSTALL_ROTATE_KEY=true` to mint a new one
- 🔐 **Access** — community mode (any member) or a whitelist of npubs; reply to everyone in channels or only when `@`-mentioned (DMs always answer)
- 📢 **Channels** — which to watch and where cron/notify deliveries land
- 💬 **Presence** — online / away / offline, plus a status line and emoji
- 🧬 **Personality** — a text file copied to the profile's `SOUL.md`

---

## ✅ Verify it worked

Send your agent a DM from an account other than the owner key. If it replies, you're live. 🎉

The technical check is `~/.hermes/profiles/<name>/gateway_state.json` containing `"platforms": {"buzz": {"state": "connected"}}`.

---

## 🧪 Tests

```bash
python3 -m pytest tests/ -q      # needs pytest + pyyaml; no network
```

Covers bech32 against NIP-19 vectors, BIP-340 against the official test vector, NIP-98 header construction, input resolution, `.env` handling, the invite flow with mocked HTTP, gateway verification, and `--dry-run`.

---

## 🗂️ File layout

```
buzz-hermes-profile-setup/
├── SKILL.md                       # The skill: inputs, procedure, pitfalls, verification
├── scripts/buzz_install.py        # The one-shot installer (stdlib only)
├── references/buzz-internals.md   # Relay/membership/NIP-98/bech32 notes for debugging
├── tests/test_buzz_install.py     # Offline test suite
└── README.md                      # You are here ✨
```

---

## 📄 License

MIT.
