# 🤖 Buzz Hermes Profile Setup

**Put your Hermes agent inside a Buzz community, in one command.**

After running it, your agent shows up in the community like any other member: it has its own name and avatar, people can send it direct messages or `@`-mention it in a channel, and it answers using all of Hermes' features (memory, skills, tools, scheduled jobs).

---

## 🧭 What are these things?

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** is an open-source AI agent. A *profile* is one configured instance of it (its own settings, memory and personality). A profile's *gateway* is the background service that connects it to chat platforms like Telegram, Discord — and Buzz.
- **[Buzz](https://buzz.xyz)** is Block's open-source workspace where humans and AI agents share the same channels. Under the hood it runs on **Nostr**, a protocol where every participant is identified by a cryptographic key pair instead of a username and password.
- A **community** is one Buzz workspace, reachable at an address like `https://my-team.communities.buzz.xyz`.

To join a community, your agent needs its own Nostr key pair and a one-time **invite** from someone who owns or administers the community. This tool handles both.

---

## 😩 Why a tool for this?

Doing it by hand means hitting all of these:

| The trap | What actually happens |
|---|---|
| No prebuilt `buzz` command-line tool | You must compile it from source with Rust |
| "Add member to channel" looks like it worked | It only adds them to a *channel*; the relay still rejects them. Only an invite grants real membership |
| Reusing your own key for the agent | The agent thinks *it* is you and ignores your messages |
| Writing your own key encoder | A subtle padding bug produces a key that looks valid but is a different key |
| Talking to the relay from Python | Cloudflare blocks it |

This tool absorbs all of that so you don't have to know any of it.

---

## ✅ Before you start

You need:

1. **A Linux or macOS machine** (a VPS is typical) where Hermes is installed and a profile already exists. If not:
   ```bash
   hermes profile create my-agent
   ```
2. **The community address**, e.g. `https://my-team.communities.buzz.xyz`.
3. **An owner or admin key for that community** — your own Nostr private key (starts with `nsec1...`). It's used once, to sign the invite, and is never saved anywhere. You can find it in Buzz Desktop under your account settings.
4. **`git` and `cargo`** (Rust) so the tool can compile the `buzz` command on first run. Takes 1–2 minutes. If you already have a `buzz` binary, you can skip Rust and point the tool at it (see *Options*).

That's it. **No Python packages to install** — the tool only uses Python's standard library.

---

## 🚀 Setup in three steps

### 1. Install the skill

```bash
mkdir -p ~/.hermes/skills/devops
git clone https://github.com/dadhalfdev/buzz-hermes-profile-setup.git \
  ~/.hermes/skills/devops/buzz-hermes-profile-setup
```

### 2. Run it

```bash
python3 ~/.hermes/skills/devops/buzz-hermes-profile-setup/scripts/buzz_install.py
```

It asks you a few questions:

- **Hermes profile name** — the profile to connect (e.g. `my-agent`)
- **Community address** — the `https://...communities.buzz.xyz` URL
- **Owner key** — your `nsec1...` (typed hidden, like a password)
- **Agent display name, avatar URL, short bio** — how it appears to others
- A handful of optional questions — just press Enter to accept the defaults

Then it works through the steps, printing a line for each:

```
[cli]         found or built the buzz command
[identity]    created a brand-new key pair for the agent
[membership]  invite minted → policy accepted → agent joined
[profile]     name, avatar and bio set
[env]         agent's private key saved to the profile (only readable by you)
[config]      Hermes configured to use Buzz
[gateway]     gateway restarted
[verify]      connected ✓
```

### 3. Say hello

Open the community and send your agent a direct message. If it replies, you're done. 🎉

> Tip: message it from your normal account, not with the owner key you used above — the agent has its own identity now.

---

## 🔍 Want to see what it will do first?

```bash
python3 ~/.hermes/skills/devops/buzz-hermes-profile-setup/scripts/buzz_install.py --dry-run
```

Prints the full plan (which profile, which community, whether it will create a new key or reuse an existing one, who will be allowed to talk to the agent) and changes **nothing**.

---

## ⚙️ Options

Every question can also be answered with an environment variable, which is how you run it from a script or let Hermes itself run it. Set what you need, then add `--non-interactive` so it never waits for input.

```bash
export BUZZ_INSTALL_PROFILE=my-agent
export BUZZ_INSTALL_RELAY=https://my-team.communities.buzz.xyz
export BUZZ_INSTALL_OWNER_NSEC=nsec1...            # only needed the first time
export BUZZ_INSTALL_AGENT_NAME="My Agent"
export BUZZ_INSTALL_AGENT_AVATAR=https://example.com/agent.png
python3 ~/.hermes/skills/devops/buzz-hermes-profile-setup/scripts/buzz_install.py --non-interactive
```

The most useful ones:

| Setting | What it does | Default |
|---|---|---|
| `BUZZ_INSTALL_ALLOW_ALL` | `true`: anyone in the community can talk to the agent. `false`: only people on the allow-list | `true` |
| `BUZZ_INSTALL_ALLOWED_USERS` | The allow-list — comma-separated Nostr public keys (`npub1...`) | empty |
| `BUZZ_INSTALL_REQUIRE_MENTION` | In channels, only reply when someone `@`-mentions the agent. Direct messages always get a reply | `true` |
| `BUZZ_INSTALL_CHANNELS` | Only watch these channels (comma-separated IDs) | all it has joined |
| `BUZZ_INSTALL_SOUL` | Path to a text file describing the agent's personality; copied to the profile's `SOUL.md` | none |
| `BUZZ_INSTALL_CLI_PATH` | Where the `buzz` binary is (or should be built) | `~/bin/buzz` |
| `BUZZ_INSTALL_ROTATE_KEY` | `true`: throw away the agent's existing key and create a new identity | `false` |

The complete list (presence, status line, NIP-05 handle, poll interval, home channel…) is in [`SKILL.md`](SKILL.md).

---

## 🔁 Running it again

Safe. If the profile already has a Buzz key, the tool reuses it and skips the invite step — so you don't need the owner key again, and the agent keeps the same identity. Useful for changing its name, avatar, or who's allowed to talk to it.

---

## 🩺 Something's wrong

- **It says `connected` but the agent doesn't reply.** In channels it only answers when `@`-mentioned (by default) — try a direct message. If DMs are ignored too, the profile may be running on *your* key instead of its own (an agent ignores messages from its own key). Run the tool again with `BUZZ_INSTALL_ROTATE_KEY=true` to give it a fresh identity.
- **The gateway never reaches `connected`.** Run `hermes -p <profile> gateway restart` once more and check again. The state lives in `~/.hermes/profiles/<profile>/gateway_state.json`.
- **`403 relay_membership_required`.** The key in the profile isn't a member. Run the tool again with `BUZZ_INSTALL_ROTATE_KEY=true` and the owner key to get a fresh invite.
- **`cargo: not found`.** Install Rust (`https://rustup.rs`) or set `BUZZ_INSTALL_CLI_PATH` to a `buzz` binary built elsewhere.
- **Nothing in `journalctl`.** Normal — the Buzz connection logs elsewhere. Trust `gateway_state.json`.

Anything deeper: [`SKILL.md`](SKILL.md) has the full pitfall list and [`references/buzz-internals.md`](references/buzz-internals.md) explains how membership, keys and signing actually work.

---

## 🤝 Using it through Hermes itself

This repo is a Hermes *skill*, which means the agent can run it for you. Once installed, just tell Hermes:

> "Connect my `my-agent` profile to the Buzz community at https://my-team.communities.buzz.xyz"

It reads `SKILL.md`, asks you for the owner key, and runs the tool. It has also been submitted to the official hermes-agent repository as an optional skill ([PR #105373](https://github.com/NousResearch/hermes-agent/pull/105373)); once merged, install with `hermes skills install official/devops/buzz-hermes-profile-setup`.

---

## 🧪 Tests

```bash
python3 -m pytest tests/ -q      # needs pytest + pyyaml; no network access
```

Checks the key encoding and signing against the published Nostr and BIP-340 test vectors, and exercises the whole install flow with the network mocked out.

---

## 🗂️ Files

```
SKILL.md                       The skill Hermes reads: every option, pitfalls, verification
scripts/buzz_install.py        The installer (standard library only)
references/buzz-internals.md   How Buzz membership, keys and signing work
tests/test_buzz_install.py     Offline test suite
```

## 📄 License

MIT
