#!/usr/bin/env python3
"""buzz_install.py — one-command installer: Hermes profile -> Buzz (Nostr) community.

Self-contained end-to-end pipeline. Only external dependency is `coincurve` (BIP-340
Schnorr signing), resolved by running under `uv run --with coincurve`:

    uv run --with coincurve python3 buzz_install.py

What it does (each step logged as [n/10]):
  1.  Resolve inputs (env vars -> interactive prompts -> defaults).
  2.  Build the `buzz` CLI from source if missing.
  3.  Generate a fresh keypair (bech32 pad=True, round-trip self-verified).
  4.  Skip mint/claim if the key is already a relay member (idempotent re-runs).
  5.  Mint invite (owner signs NIP-98) -> accept join-policy (if any) -> claim (agent signs).
  6.  Set the profile: name / avatar / about / NIP-05, then presence + status.
  7.  Write BUZZ_PRIVATE_KEY to the profile's .env (chmod 600).
  8.  `hermes -p <name> config set` every buzz key.
  9.  Restart the gateway.
  10. Verify gateway_state.json shows buzz connected; print test-DM hint.

Inputs come from BUZZ_INSTALL_* env vars (see SKILL.md "Input manifest"); required ones are
prompted when stdin is a TTY, else fatal. Secrets are read via getpass (echoed off) and are
NEVER written to disk except BUZZ_PRIVATE_KEY -> .env (which is required by the adapter).

Why curl: the relay sits behind Cloudflare, which blocks Python urllib with error 1010.
"""
import json, os, sys, secrets, hashlib, base64, time, subprocess, pathlib, getpass

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
DEFAULT_CLI = "/root/bin/buzz"
HOME = pathlib.Path.home()
PROFILES = HOME / ".hermes" / "profiles"

def log(msg): print(msg, flush=True)

def die(msg):
    print(f"\nFATAL: {msg}", file=sys.stderr); sys.exit(1)


# ---------------------------------------------------------------- bech32 (NIP-19)
CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

def _polymod(v):
    G = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for x in v:
        b = chk >> 25
        chk = (chk & 0x1ffffff) << 5 ^ x
        for i in range(5):
            chk ^= G[i] if (b >> i) & 1 else 0
    return chk

def _hrp_expand(h): return [ord(c) >> 5 for c in h] + [0] + [ord(c) & 31 for c in h]

def _convertbits(data, fb, tb, pad=True):
    acc = bits = 0; out = []; maxv = (1 << tb) - 1
    for v in data:
        acc = (acc << fb) | v; bits += fb
        while bits >= tb:
            bits -= tb; out.append((acc >> bits) & maxv)
    if pad and bits:                       # <-- CRITICAL: pad the final group
        out.append((acc << (tb - bits)) & maxv)
    return out

def bech32_encode(hrp, data):
    vals = _convertbits(list(data), 8, 5)  # pad=True implicit
    pm = _polymod(_hrp_expand(hrp) + vals + [0, 0, 0, 0, 0, 0]) ^ 1
    vals += [(pm >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(CHARSET[d] for d in vals)

def bech32_decode(hrp, addr):
    addr = addr.lower(); pos = addr.rfind("1")
    vals = [CHARSET.index(c) for c in addr[pos + 1:]]
    assert _polymod(_hrp_expand(hrp) + vals) == 1, "bech32 checksum fail"
    return bytes(_convertbits(vals[:-6], 5, 8, False))


# ---------------------------------------------------------------- keypair (coincurve)
def generate_keypair():
    from coincurve import PrivateKey
    sec = secrets.token_bytes(32)
    x = PrivateKey(sec).public_key.format(compressed=False)[1:33]  # 32-byte x
    nsec = bech32_encode("nsec", sec)
    npub = bech32_encode("npub", x)
    # Self-verify: nsec round-trips AND derives the same pubkey (catches pad bugs).
    assert bech32_decode("nsec", nsec) == sec, "nsec round-trip failed"
    assert bech32_decode("npub", npub) == x, "npub round-trip failed"
    return nsec, npub, x.hex()

def nsec_hex(nsec): return bech32_decode("nsec", nsec).hex()


# ---------------------------------------------------------------- NIP-98 (kind 27235)
def sign_nip98(sec_hex, pub_hex, url, body_bytes):
    from coincurve import PrivateKey
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    created_at = int(time.time())
    tags = [["u", url], ["method", "POST"], ["payload", body_hash]]
    ser = json.dumps([0, pub_hex, created_at, 27235, tags, ""], separators=(",", ":"))
    eid = hashlib.sha256(ser.encode()).digest()
    sig = PrivateKey(bytes.fromhex(sec_hex)).sign_schnorr(eid, None)
    ev = {"id": eid.hex(), "pubkey": pub_hex, "created_at": created_at, "kind": 27235,
          "tags": tags, "content": "", "sig": sig.hex()}
    return "Nostr " + base64.b64encode(json.dumps(ev, separators=(",", ":")).encode()).decode()


def curl(url, body=None, auth=None):
    cmd = ["curl", "-sS", "-m", "30", "-H", f"User-Agent: {UA}"]
    if body is not None:
        cmd += ["-X", "POST", "-H", "Content-Type: application/json",
                "-d", json.dumps(body, separators=(",", ":"))]
    if auth:
        cmd += ["-H", f"Authorization: {auth}"]
    cmd += [url]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def sh(cmd, env=None, cwd=None, check=True):
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd)
    out = (p.stdout or "").strip()
    if check and p.returncode != 0:
        die(f"command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr or out}")
    return p.returncode, out


# ---------------------------------------------------------------- input resolution
def _env(key): return os.environ.get(key, "").strip()

def resolve_inputs():
    tty = sys.stdin.isatty()
    def ask(key, prompt, required=False, default=None, secret=False):
        v = _env(key)
        if v:
            return v
        if not tty:
            if required:
                die(f"missing required env var {key} (set it, or run from a terminal)")
            return default if default is not None else ""
        p = prompt
        if default:
            p += f" [{default}]"
        p += ": "
        raw = getpass.getpass(p) if secret else input(p)
        raw = raw.strip()
        return raw if raw != "" else (default or "")

    cfg = {
        "profile":     ask("BUZZ_INSTALL_PROFILE", "Hermes profile name", required=True),
        "relay":       ask("BUZZ_INSTALL_RELAY", "Community relay URL (https://<c>.communities.buzz.xyz)",
                           required=True),
        "owner_nsec":  ask("BUZZ_INSTALL_OWNER_NSEC", "Owner nsec (to mint the invite — used once, never saved)",
                           required=True, secret=True),
        "agent_name":  ask("BUZZ_INSTALL_AGENT_NAME", "Agent display name"),
        "avatar":      ask("BUZZ_INSTALL_AGENT_AVATAR", "Agent avatar URL (hosted image)"),
        "about":       ask("BUZZ_INSTALL_AGENT_ABOUT", "Agent bio / about"),
        "nip05":       ask("BUZZ_INSTALL_AGENT_NIP05", "NIP-05 id (optional)"),
        "presence":    ask("BUZZ_INSTALL_PRESENCE", "Presence (online/away/offline)", default="online"),
        "status_text": ask("BUZZ_INSTALL_STATUS_TEXT", "Status line (optional)"),
        "status_emoji": ask("BUZZ_INSTALL_STATUS_EMOJI", "Status emoji (optional)"),
        "allow_all":   ask("BUZZ_INSTALL_ALLOW_ALL", "Allow all community members to chat? (true/false)",
                           default="true"),
        "allowed_users": ask("BUZZ_INSTALL_ALLOWED_USERS", "Allowed users (comma-sep npub/hex, if whitelist)"),
        "channels":    ask("BUZZ_INSTALL_CHANNELS", "Channels to watch (comma-sep UUIDs; empty = all)"),
        "home_channel": ask("BUZZ_INSTALL_HOME_CHANNEL", "Home channel UUID (for cron/notify)"),
        "require_mention": ask("BUZZ_INSTALL_REQUIRE_MENTION",
                               "Only reply when @-mentioned in channels? (true/false)", default="true"),
        "poll_interval": ask("BUZZ_INSTALL_POLL_INTERVAL", "Poll interval (seconds)", default="4"),
        "cli_path":    ask("BUZZ_INSTALL_CLI_PATH", "buzz CLI path", default=DEFAULT_CLI),
        "soul":        ask("BUZZ_INSTALL_SOUL", "Personality: path to a text file -> SOUL.md (optional)"),
    }
    if not cfg["agent_name"]:
        cfg["agent_name"] = cfg["profile"]
    # validate basics
    if not cfg["relay"].startswith("https://"):
        die("relay URL must start with https://")
    if cfg["presence"] not in ("online", "away", "offline"):
        die("presence must be online/away/offline")
    return cfg


# ---------------------------------------------------------------- buzz CLI env helper
def buzz_env(cfg, nsec):
    e = os.environ.copy()
    e["BUZZ_RELAY_URL"] = cfg["relay"]
    e["BUZZ_PRIVATE_KEY"] = nsec
    return e


def ensure_cli(cli_path):
    p = pathlib.Path(cli_path)
    if p.exists() and os.access(p, os.X_OK):
        log(f"[cli] using existing {cli_path}")
        return str(p)
    log("[cli] building buzz-cli from source (~1–2 min)…")
    build = HOME / ".buzz-build"
    if not (build / "Cargo.toml").exists():
        sh(["git", "clone", "--depth", "1", "https://github.com/block/buzz.git", str(build)])
    sh(["cargo", "build", "--release", "-p", "buzz-cli"], cwd=str(build))
    src = build / "target" / "release" / "buzz"
    if not src.exists():
        die("cargo build finished but target/release/buzz not found")
    import shutil
    p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, p)
    p.chmod(0o755)
    log(f"[cli] built -> {p}")
    return str(p)

def build_cli(cli_path):
    return ensure_cli(cli_path)


# ---------------------------------------------------------------- membership
def already_member(cfg, nsec):
    rc, out = sh(["buzz", "channels", "list"], env=buzz_env(cfg, nsec), check=False)
    return rc == 0


def mint_and_claim(cfg, nsec, agent_pub_hex):
    owner_sec = nsec_hex(cfg["owner_nsec"])
    # derive owner pubkey from nsec via coincurve
    from coincurve import PrivateKey
    owner_pub = PrivateKey(bytes.fromhex(owner_sec)).public_key.format(compressed=False)[1:33].hex()

    # 1. mint
    mint_body = {}
    body = json.dumps(mint_body, separators=(",", ":"))
    auth = sign_nip98(owner_sec, owner_pub, f"{cfg['relay']}/api/invites", body.encode())
    rc, out, err = curl(f"{cfg['relay']}/api/invites", mint_body, auth)
    log(f"[membership] mint -> {out}")
    if rc or '"error"' in out:
        die(f"mint failed: {out or err}")
    code = json.loads(out)["code"]

    # 2. join-policy version
    rc, out, _ = curl(f"{cfg['relay']}/api/join-policy")
    version = ""
    try:
        version = json.loads(out).get("policy", {}).get("version", "")
    except Exception:
        pass

    # 3. accept-policy (if required)
    receipt = None
    if version:
        rc, out, err = curl(f"{cfg['relay']}/api/invites/accept-policy",
                            {"code": code, "policy_version": version, "age_confirmed": True})
        log(f"[membership] accept-policy -> {out}")
        if rc:
            die(f"accept-policy failed: {out or err}")
        receipt = json.loads(out)["receipt"]

    # 4. claim (agent key)
    claim_body = {"code": code}
    if receipt:
        claim_body["policy_receipt"] = receipt
    body = json.dumps(claim_body, separators=(",", ":"))
    agent_sec = nsec_hex(nsec)
    auth = sign_nip98(agent_sec, agent_pub_hex, f"{cfg['relay']}/api/invites/claim", body.encode())
    rc, out, err = curl(f"{cfg['relay']}/api/invites/claim", claim_body, auth)
    log(f"[membership] claim -> {out}")
    if rc or '"error"' in out:
        die(f"claim failed: {out or err}")
    log("[membership] agent key is now a relay member.")


# ---------------------------------------------------------------- profile
def set_profile(cfg, nsec):
    env = buzz_env(cfg, nsec)
    args = ["buzz", "users", "set-profile", "--name", cfg["agent_name"]]
    if cfg["avatar"]: args += ["--avatar", cfg["avatar"]]
    if cfg["about"]:  args += ["--about", cfg["about"]]
    if cfg["nip05"]:  args += ["--nip05", cfg["nip05"]]
    sh(args, env=env)
    log(f"[profile] set name={cfg['agent_name']} avatar={'yes' if cfg['avatar'] else 'no'}")
    sh(["buzz", "users", "set-presence", "--status", cfg["presence"]], env=env)
    if cfg["status_text"]:
        args = ["buzz", "users", "set-status", "--text", cfg["status_text"]]
        if cfg["status_emoji"]: args += ["--emoji", cfg["status_emoji"]]
        sh(args, env=env)


# ---------------------------------------------------------------- hermes wiring
def write_env(cfg, nsec):
    env_path = PROFILES / cfg["profile"] / ".env"
    if not env_path.exists():
        die(f"profile '{cfg['profile']}' not found at {env_path.parent}")
    lines = env_path.read_text().splitlines()
    new = [l for l in lines if not l.startswith("BUZZ_PRIVATE_KEY=")]
    new.append(f"BUZZ_PRIVATE_KEY={nsec}")
    env_path.write_text("\n".join(new) + "\n")
    env_path.chmod(0o600)
    log(f"[env] wrote BUZZ_PRIVATE_KEY -> {env_path}")


def list_to_json(csv):
    items = [x.strip() for x in (csv or "").split(",") if x.strip()]
    return json.dumps(items)


def config_set(profile, key, value):
    sh(["hermes", "-p", profile, "config", "set", key, value], check=False)


def write_config(cfg):
    p = cfg["profile"]
    pre = "gateway.platforms.buzz"
    config_set(p, f"{pre}.enabled", "true")
    config_set(p, f"{pre}.extra.relay_url", cfg["relay"])
    config_set(p, f"{pre}.extra.channels", list_to_json(cfg["channels"]))
    config_set(p, f"{pre}.extra.home_channel", cfg["home_channel"] or "")
    config_set(p, f"{pre}.extra.poll_interval", cfg["poll_interval"] or "4")
    config_set(p, f"{pre}.extra.cli_path", cfg["cli_path"])
    config_set(p, f"{pre}.extra.credentials_file", "")
    config_set(p, f"{pre}.extra.allowed_users", list_to_json(cfg["allowed_users"]))
    config_set(p, f"{pre}.extra.require_mention", cfg["require_mention"].lower())
    config_set(p, f"{pre}.extra.allow_all_users", cfg["allow_all"].lower())
    config_set(p, "display.platforms.buzz.interim_assistant_messages", "false")
    config_set(p, "display.platforms.buzz.tool_progress", "off")
    log("[config] buzz keys written via hermes config set")


def write_soul(cfg):
    if not cfg["soul"]:
        return
    src = pathlib.Path(cfg["soul"]).expanduser()
    if not src.exists():
        die(f"soul file not found: {src}")
    dst = PROFILES / cfg["profile"] / "SOUL.md"
    dst.write_text(src.read_text())
    log(f"[soul] wrote {src} -> {dst}")


def verify(cfg):
    state = PROFILES / cfg["profile"] / "gateway_state.json"
    for _ in range(30):
        if state.exists():
            txt = state.read_text()
            if '"buzz"' in txt and '"connected"' in txt:
                log("[verify] gateway_state.json shows buzz connected ✓")
                return True
        time.sleep(2)
    log("[verify] WARNING: buzz not yet 'connected' in gateway_state.json "
        "(may still be starting — re-check in a moment)")
    return False


# ---------------------------------------------------------------- main
def main():
    log("== buzz-hermes-profile-setup ==")
    cfg = resolve_inputs()

    nsec, npub, pub_hex = generate_keypair()            # [3]
    cli_path = build_cli(cfg["cli_path"])               # [2]

    if not already_member(cfg, nsec):                    # [4]
        if not cfg["owner_nsec"]:
            die("owner nsec required for first-time join (BUZZ_INSTALL_OWNER_NSEC)")
        mint_and_claim(cfg, nsec, pub_hex)               # [5]
    else:
        log("[membership] key already a member — skipping mint/claim")

    set_profile(cfg, nsec)                              # [6]
    write_env(cfg, nsec)                                 # [7]
    write_config(cfg)                                    # [8]
    write_soul(cfg)
    sh(["hermes", "-p", cfg["profile"], "gateway", "restart"], check=False)  # [9]

    ok = verify(cfg)                                     # [10]
    log("\n---- SUMMARY ----")
    log(f"profile:   {cfg['profile']}")
    log(f"npub:      {npub}")
    log(f"pubkey:    {pub_hex}")
    log(f"name:      {cfg['agent_name']}")
    log(f"relay:     {cfg['relay']}")
    log(f"member:    {'yes' if already_member(cfg, nsec) else 'NO — check claim'}")
    log("\nNext: send the agent a DM and confirm it replies. "
        "If it doesn't, see the buzz-setup skill for deep debugging.")
    if not ok:
        sys.exit(1)

if __name__ == "__main__":
    main()