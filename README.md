# 🤖 Buzz Hermes Profile Setup

> Connect a self-hosted **Hermes agent** (the kind running on a VPS) to a [Buzz](https://buzz.dev) (Nostr) community as a first-class member — with its own name, avatar, and access rules. One command, end to end. ✨

The manual path is a slog: no prebuilt CLI, a keypair encoding bug, Cloudflare blocking requests, and a "relay vs channel" membership trap that *silently* fails. This skill absorbs all of it so you don't have to think about it.

---

## 🚀 What it does

One command handles the whole pipeline:

1. 🔧 Builds the `buzz` CLI (first run only)
2. 🔑 Mints a fresh keypair + relay membership for your agent
3. 👤 Sets its name, avatar, bio, and NIP-05 handle
4. 🔌 Wires up your Hermes gateway
5. ✅ Restarts and verifies the connection

---

## 📦 Prerequisites

- 🖥️ A **Linux VPS** where Hermes is already running (not for desktop-only setups)
- 🦀 `git` + `cargo` (Rust) — used to build the CLI
- ⚡ `uv` — pulls in the one helper library (`coincurve`)
- 🔑 An **owner key** for the community, to mint the invite (used once, never saved)

> No `uv`? See `requirements.txt` — `coincurve` is the only dependency, install it however you like.

---

## 🖥️ Install

Clone the repo into your Hermes skills folder:

```bash
mkdir -p ~/.hermes/skills/devops
git clone https://github.com/dadhalfdev/buzz-hermes-profile-setup.git \
  ~/.hermes/skills/devops/buzz-hermes-profile-setup
```

---

## ▶️ Run

```bash
uv run --with coincurve python3 \
  ~/.hermes/skills/devops/buzz-hermes-profile-setup/scripts/buzz_install.py
```

That's it. The script prompts for the few things it can't guess — profile name, community URL, an owner key, agent name, avatar — and handles the rest silently.

Prefer to script it? Every input can be set as an env var (`BUZZ_INSTALL_*`), so it runs headless too. The full list lives in `SKILL.md`.

---

## 🧠 What you can control

- 👤 **Identity** — a dedicated keypair (auto-generated, never your own), display name, avatar URL, bio, NIP-05
- 🔐 **Access** — open to everyone vs. an allow-list of specific users; whether the agent replies to everyone in channels or only when `@`-mentioned
- 📢 **Channels** — which ones to watch, and where cron/notify messages land
- 💬 **Presence** — online / away / offline, plus a status line and emoji

---

## ✅ Verify it worked

Send your agent a direct message in the community. If it replies, you're live. 🎉

(Want the nerdy check? Peek at `~/.hermes/profiles/<name>/gateway_state.json` — you're after `"buzz":{"state":"connected"}`. More in `SKILL.md`.)

---

## 🤔 Stuck?

- The agent looks connected but won't reply → make sure you're messaging it from the right account (the owner's key is separate from the agent's).
- `coincurve` import error → you ran the script without `uv run --with coincurve`.
- Anything else → `SKILL.md` has a full troubleshooting section, and `references/buzz-internals.md` has the deep dive.

---

## 🗂️ File layout

```
buzz-hermes-profile-setup/
├── SKILL.md                       # The skill: full options, pitfalls, troubleshooting
├── scripts/buzz_install.py        # The one-shot installer
├── references/buzz-internals.md   # How relay/membership/keys work (for debugging)
├── requirements.txt               # The one dependency (coincurve)
└── README.md                      # You are here ✨
```

---

## 📄 License

MIT.

---

Happy onboarding! 🚀🤖