# Ledger Key Ring / "Ring CLI" — research note

Researched 2026-10-10 for the N3XT hackathon (deadline 2026-10-13 23:59 CEST). Web-only; no hardware touched, nothing installed.
Tags: **VERIFIED** = read in a primary source (Ledger docs, ledger-live source, npm registry, whitepaper PDF). **INFERRED** = my reading between sources.

## TL;DR

- "Ring CLI" is not a product. It is the `ring` command group inside `@ledgerhq/wallet-cli` (`wallet-cli ring init|encrypt|decrypt|keys|destroy`). **VERIFIED** (docs, README, source).
- Keys are **not** derived from the 24-word seed. The whitepaper is explicit: LKRP keys are *random*, generated on the device, and the root is encrypted (ECDHE) to the device's own seed-derived Ledger Sync identity key and stored, encrypted, on Ledger's trustchain backend. "Recoverable from your seed" really means "recoverable with the same seed **plus** Ledger's backend still holding the encrypted tree". The hackathon brief's wording ("keys derived from your Ledger seed") is marketing shorthand. **VERIFIED** (whitepaper) / consequence **INFERRED**.
- Headless = "device once, then never": `ring init` needs a USB Ledger with the **Ledger Sync** app (app id 17 branch, path `m/0'/17'/N'`). `ring encrypt`/`decrypt` need **no device**, but need (a) network to Ledger's trustchain backend, (b) the machine's member private key in the **OS keychain**, (c) the local password (`WALLET_PASS` when no TTY). **VERIFIED**.
- Trust model after init is therefore: OS keychain + local password + Ledger backend reachability/authorisation. Anyone with the machine's keychain entry and password decrypts everything without a Ledger. The device only gates *enrolment* and *revocation/rotation*. **VERIFIED** (source) / framing **INFERRED**.
- Windows: official docs say "Windows (WSL recommended)", but npm ships a native `@ledgerhq/wallet-cli-windows-x64` binary (2.9.0, 2026-10-05) and the source has Windows-specific code paths (Credential Manager hint, CRLF keychain parsing, `%LOCALAPPDATA%` state dir, rename fallback). Native Windows is plausible but not officially blessed; WSL needs `usbipd-win` for the one USB step. **VERIFIED** facts, "plausible" **INFERRED**.
- Devices: the Ledger Sync device app runs on Nano S Plus, Nano X, Stax, Flex, Nano Gen 5; not Nano S. Both the Nano S Plus and Flex we have qualify. **VERIFIED** (Agent Intent doc lists devices; support search snippet for Sync).
- There is **no documented way to enrol a USB-less host** (CI runner, VPS) in the ring today. The SDK underneath (`addMember` with a `SoftwareDevice`) can add a member without hardware, but `wallet-cli` does not expose it. This is exactly the gap Ledger's own ETHOnline brief asked people to fill ("Bring the Key Ring to hosts with no USB port: enroll a VPS, a CI runner, or a hosted agent"). **VERIFIED** gap / opportunity **INFERRED**.

## 1. What it is, where it lives

| Item | Value | Status |
| --- | --- | --- |
| Product name | Ledger Key Ring, a.k.a. LKRP (Ledger Key Ring Protocol); CLI surface is `wallet-cli ring` | VERIFIED |
| npm package | `@ledgerhq/wallet-cli`, latest **2.9.0** (published 2026-10-05). `ring` landed in **2.0.0** (2026-07-10), `skill` in 2.1.0 (2026-07-30), `agent-intent` in 2.9.0 | VERIFIED (registry JSON, CHANGELOG) |
| Platform binaries | optionalDependencies `@ledgerhq/wallet-cli-{darwin-arm64,linux-x64,linux-arm64,windows-x64}`; the Windows one is `bin/wallet-cli.exe`, os `win32`, cpu `x64`, ~108 MB (Bun single-file executable built with `bunli build`) | VERIFIED |
| Engine | `bun >=1.1.0` (only matters if running from source) | VERIFIED |
| Repo | monorepo `LedgerHQ/ledger-live`, directory `apps/wallet-cli`; ring code in `apps/wallet-cli/src/commands/ring/*` and `apps/wallet-cli/src/key-ring/*` | VERIFIED |
| Protocol libs | `@ledgerhq/ledger-key-ring-protocol` (SDK, `libs/ledger-key-ring-protocol`) and `@ledgerhq/hw-ledger-key-ring-protocol` (device/APDU + crypto). Both marked "STABLE, production-ready" | VERIFIED |
| Merge history | #16859 (`secrets` group, Apr 2026) closed; #17743 (`ring`) closed; **#19477 merged 2026-07-10** by Justkant, 90.1% coverage on new code | VERIFIED |
| Agent skill | `LedgerHQ/agent-skills` → `skills/wallet-cli/wallet-cli-usage/SKILL.md`; also embedded: `wallet-cli skill install --agent claude` | VERIFIED |
| Licence | Apache-2.0 | VERIFIED |
| Whitepaper | `LedgerHQ/ledger-key-ring-protocol-whitepaper` (PDF; repo archived 2025-10-01, read-only) | VERIFIED |

Install (docs):

```bash
npm i -g @ledgerhq/wallet-cli      # or pnpm add -g / yarn global add / bun add -g
wallet-cli --version
wallet-cli skill install --agent claude   # also cursor, codex, agents
```

## 2. Command surface

From docs + source. Device/network columns from code, not from the PR description (the PR text wrongly says encrypt/decrypt need a device).

| Command | Device | Network | TTY/password | Notes |
| --- | --- | --- | --- | --- |
| `ring init [--name N] [--unsecure-no-password]` | **yes** (Ledger Sync app open) | yes | prompts password twice unless flag; `WALLET_PASS` if no TTY | creates/recovers trustchain, registers this machine as member. `--name` 1..64 chars, default `hostname-platform` |
| `ring encrypt --key K [-i FILE] [-o FILE] [--output json]` | no | yes | password (or `WALLET_PASS`) only if ring was init'ed with a password | `-i` default stdin, `-o` default stdout (raw bytes) |
| `ring decrypt --key K [-i FILE] [-o FILE]` | no | yes | same | same |
| `ring keys` | no | no | no | lists `session.domains` (local cache) |
| `ring destroy` | no (per source) | yes | types `destroy` to confirm; password prompt "Enter to skip remote destroy" | closes the app-17 stream remotely, deletes whole trustchain only if last open app; wipes keychain + session ring fields |

Key-name rules: `--key` is `1..253` chars, no whitespace (`/^\S+$/`). Free-form. **VERIFIED** (shared.ts).

I/O rules that the skill doc does not state (issue #21910, confirmed in `shared.ts`):
- no `--input` and stdin is a TTY → error `No input: provide --input FILE or pipe data to stdin.`
- `--output json` without `--out` → error (binary can't go to JSON stdout).
- `--out` is an atomic write with mode `0600` (temp file + rename; on win32 falls back to unlink+rename, non-atomic). Spinner/prompts go to stderr, plaintext goes to stdout only.

Docs examples (verbatim):

```bash
wallet-cli ring init
wallet-cli ring encrypt -i secrets.txt -o secrets.enc --key my-key
wallet-cli ring decrypt -i secrets.enc -o secrets.txt --key my-key
wallet-cli ring keys
wallet-cli ring destroy
pbpaste | wallet-cli ring encrypt --key personal-notes | pbcopy
echo "destroy" | wallet-cli ring destroy          # non-interactive confirm (in-repo SKILL.md)
```

## 3. Cryptography, exactly

### 3.1 Ciphertext format (`apps/wallet-cli/src/key-ring/crypto.ts`) — VERIFIED

```
[ 12-byte random IV ][ AES-256-GCM ciphertext || 16-byte tag ]
```

No magic bytes, no version, no key-name, no header. Decrypt only checks length ≥ 12. Consequences (**INFERRED**): you must remember which `--key` you used; a wrong key just fails GCM auth with no hint; nothing stops you feeding a non-ring file in. WebCrypto `subtle.encrypt`, non-extractable keys.

### 3.2 Per-key ("domain") key — VERIFIED

```
domainKey = HKDF-SHA256( IKM  = hex-decode(walletSyncEncryptionKey),
                         salt = "wallet-cli-domain-v1",
                         info = <key name>,
                         L    = 32 bytes )
```

`walletSyncEncryptionKey` is what the LKRP SDK returns from `restoreTrustchain` for the ring's application path: the first 32 bytes (the private-key half) of the xpriv at `m/0'/17'/N'`. Every encrypt/decrypt re-fetches the trustchain over HTTPS, re-derives this, then HKDFs the domain key, and discards both. So all `--key` names share one root secret; key names are scoping labels, not independent secrets. **INFERRED**: rotation of the root rotates every key name at once.

### 3.3 Where the root comes from (LKRP) — VERIFIED (whitepaper, docs/ledger-sync, hw lib source)

- Trustchain = a tree of signed command streams stored on Ledger's trustchain backend. Blocks: `Seed` (0x10), `AddMember` (0x11), `PublishKey` (0x12), `CloseStream` (0x13), `Derive` (0x15). Members are secp256k1 public keys; signatures ECDSA/SHA-256 (DER); key agreement ECDH over secp256k1; symmetric AES-256-GCM.
- Path policy: `m / treeIndex' / applicationId' / rotationIndex'`, all hardened. `treeIndex` is always 0. `applicationId` **16 = Ledger Sync**, **17 = wallet-cli ring**. `rotationIndex` starts at 0 and bumps on each rotation. So ring path = `m/0'/17'/0'`, then `m/0'/17'/1'`, ... (the commit message even denylists `m/0'/17'/0'` as PII in analytics).
- `Seed`: the **device generates a random 64-byte extended private key** (32 priv + 32 chain code). Whitepaper: "LKRP never shares private keys ... derived from the user 24 words seed phrase ... Instead it must share randomly generated encryption keys". The root is encrypted with ECDHE to the block issuer (the device's Ledger Sync identity key) and stored in the Seed block as a backup "for the secure device to retrieve the private key".
- `Derive`: device recovers the root from the Seed block, derives the app branch (BIP32 via the `bip32` npm package in software members; on-device for the hardware).
- `AddMember` + `PublishKey`: the branch xpriv is encrypted for the new member: ephemeral secp256k1 keypair, ECDH → raw x-coordinate → `HMAC-SHA256(key="", msg=x)` → AES-256-GCM with a **16-byte** nonce (noble `gcm`, not WebCrypto). Payload is the 64-byte xpriv.
- Member restore (no device): `SoftwareDevice.readKey` walks the stream for a `PublishKey` addressed to its pubkey, ECDH-decrypts the xpriv, then BIP32-derives down to the requested path. This is what runs on every `ring encrypt/decrypt`.
- Device APDUs (Ledger Sync app, CLA `0xE0`): `INS_GET_PUBLIC_KEY 0x05` (also signs the auth challenge), `INS_INIT 0x06`, `INS_SIGN_BLOCK 0x07`, `INS_PARSE_STREAM 0x08`, `INS_SET_TRUSTED_MEMBER 0x09`. Device parses/validates all prior blocks before signing. "If we have no trusted param we need an explicit approval" (host comment) → the user approves on the trusted display. What exactly the screen says is firmware-side, not in the TS source (**gap**).

**So, precisely:** your 24-word seed never produces the ring key. It produces the device's LKRP identity key, which is the only thing that can decrypt the `Seed` block held by Ledger's backend. Same seed on a new device + backend still has the tree ⇒ recovery. Backend loses/deletes the tree (destroy, or inactivity purge; see §7) ⇒ **unrecoverable even with the seed**. **INFERRED** from the above.

### 3.4 Local member credential protection — VERIFIED (`keychain.ts`, `crypto.ts`, `init.ts`)

- Member keypair: random secp256k1 (`crypto.randomKeypair()`, hex `pubkey`/`privatekey`).
- Stored in the OS keychain via `@napi-rs/keyring` **1.3.0** (wallet-cli pin), service `ledger-wallet-cli`, account `member-private-key-<first 16 hex of SHA-256(stateDir)>`. Entry body: line 1 = `ENC:<hex>` (wrapped) or plaintext hex (if `--unsecure-no-password`); line 2 = pubkey. CRLF-tolerant parse "because entries written on Windows use \r\n".
- Wrapping: `PBKDF2-SHA256(password, salt=16 random bytes, 600 000 iterations)` → AES-256-GCM, same `[iv][ct]` format. Salt stored as 32 hex chars in `session.yaml` `passwordSalt`. Password never stored. Lost password ⇒ not recoverable; re-`init` on a new machine (or `destroy` + `init`).
- Keychain read error ⇒ treated as "no key" (no file fallback, no env fallback).

### 3.5 State on disk — VERIFIED (`session-store.ts`, `@bunli/utils` `xdg.ts`)

- Dir: `stateDir("ledger-wallet-cli")` → Linux/macOS `$XDG_STATE_HOME/ledger-wallet-cli` or `~/.local/state/ledger-wallet-cli`; **Windows `%LOCALAPPDATA%\ledger-wallet-cli\State`**. Created `0700`.
- File `session.yaml` (Bun YAML), written atomically `0600`. Ring fields: `trustchain: {rootId, applicationPath}`, `domains: [{domain, firstUsed}]`, `passwordSalt`. No key material in the file. Lock file `.session.lock` serialises read-modify-write across processes.
- Rotation detection: if the restored `applicationPath` differs from the stored one, a stderr warning says older data may not decrypt; the new path is persisted under lock.

### 3.6 Network — VERIFIED

- Trustchain backend prod `https://trustchain.api.live.ledger.com` (staging `trustchain-backend.api.aws.stg.ldg-tech.com`); wallet-cli takes it from `getEnv("TRUSTCHAIN_API_PROD")`.
- Auth per call: `GET /v1/challenge` → sign challenge hash with member key (software; the device only signs it during `init`) → `POST /v1/authenticate` → JWT with permissions keyed by `rootId` + path; `GET /v1/refresh`. Trustchain fetch, `POST /v1/seed`, add derivation, append commands, delete.
- Membership checks happen server-side (JWT) *and* client-side (`TrustchainEjected` when the app stream is closed or the pubkey is not in the member list).
- Ring analytics go to Segment (`@segment/analytics-node`); events carry only booleans/enums/counts, never key names/paths/root ids. `USER_ID` env defaults to `wallet-cli`; `WALLET_CLI_NO_NUDGE=1` kills the first-run nudge.

## 4. "Headless" — what it really means

VERIFIED from `prompt.ts`, `init.ts`, SKILL.md, docs:

1. `promptHidden` order: if `WALLET_PASS` is **defined** (even empty) → use it, no prompt. Else if stdin is a TTY → raw-mode hidden prompt. Else try `/dev/tty` (so piped payloads aren't eaten as the password). Else throw: `Password required but no TTY available and WALLET_PASS is not set.` with hints:
   - macOS: `WALLET_PASS=$(security find-generic-password -a default -s ledger-wallet-cli -w) wallet-cli ...`
   - Linux: `WALLET_PASS=$(secret-tool lookup service ledger-wallet-cli account default) wallet-cli ...`
   - Windows: `$env:WALLET_PASS=(Get-StoredCredential -Target ledger-wallet-cli).GetNetworkCredential().Password; wallet-cli ...` (`Get-StoredCredential` is from the third-party `CredentialManager` PowerShell module — **INFERRED**, not in the message)
2. `/dev/tty` does not exist on Windows ⇒ on native Windows, *any* piped invocation (`type x | wallet-cli ring encrypt ...`) needs `WALLET_PASS`, whereas macOS/Linux fall back to the controlling terminal. **INFERRED** from the code comment "(Windows, or no controlling terminal in CI)".
3. `ring init --unsecure-no-password` stores the member private key **unencrypted** in the OS keychain; afterwards encrypt/decrypt need no password at all. Docs: don't use for real data. Skill doc: "The ring must be protected by a password." `--help` documents the flag; the skill doesn't (issue #21910, open, no maintainer reply as of 2026-09-13).
4. `ring destroy` with `WALLET_PASS` set-but-empty aborts ("WALLET_PASS is set but empty"); unset + non-TTY aborts.
5. Linux headless: `@napi-rs/keyring` needs a Secret Service (gnome-keyring etc.) with an unlocked collection. SKILL.md: "Headless Linux, containers, and some CI runners fail with a keychain error, and there's no file-based fallback." (Newer `@napi-rs/keyring` 2.x falls back to in-memory kernel keyutils; wallet-cli pins 1.3.0, so assume no fallback — **INFERRED**.)
6. The password lands in the child's environment and is readable by the same user via `ps eww`; hence "inject at call time from the keychain", never `export`.

**Bottom line (INFERRED):** "Headless by design" is true for *decrypting* on a machine that was once enrolled with a human + device. It is not true for *enrolling* a headless machine. There is no `ring export-member`, no `ring add-member`, no `ring init --from-credentials`. A CI runner can be enrolled only by (a) plugging a Ledger into it, (b) copying `session.yaml` + the keychain entry from an enrolled machine (the keychain account name hashes the state dir, so the path must match or the entry must be re-created; the wrapped key stays wrapped under the same password), or (c) writing your own enrolment using the SDK's `addMember` (software device) from an already-enrolled member. Option (c) is the hackathon-shaped hole.

### CI patterns the docs actually give

- GitHub Actions / any runner: store `WALLET_PASS` in the CI secret store, inject per step; the runner still needs the member key in its OS keychain (pre-provisioned) and outbound HTTPS to `trustchain.api.live.ledger.com`. **INFERRED** composition of VERIFIED facts; no first-party Actions example exists.
- Agent startup pattern (issue #21910 reporter, ETHOnline 2026): agent decrypts RPC URL, signing key and LLM API key from the ring at boot and parses stdout in memory, never writing plaintext to disk. Docs: "Pipe it straight to a file, another process, or the clipboard. Don't print or cat it."
- `.env` / sops / age backend: Ledger's ETHOnline brief suggests "using `wallet-cli ring` as the key backend for existing `.env`, sops, or age files".
- `WALLET_CLI_MOCK=1` swaps in the mock LKRP SDK: no device, no network, fixed JWT, deterministic `walletSyncEncryptionKey` (`00..01`, bumps on rotation). wallet-cli's own HKDF + AES-GCM still run on top, so the ring commands round-trip for tests/demos without hardware. **VERIFIED** mock behaviour / round-trip **INFERRED**.
- Claude Code sandbox note (SKILL.md): `ring init` needs `dangerouslyDisableSandbox: true` for USB; `ring encrypt/decrypt/destroy` need it for keychain access; `ring keys` needs nothing.

## 5. Trust model vs a plain Ledger signer

| | Plain signer (DMK / OpenPGP) | Key Ring |
| --- | --- | --- |
| Device per operation | yes, every sign/decrypt, user taps | only `init` and rotation (`removeMember`) |
| What the device attests | this human approved this action, now | this machine was once enrolled as a member |
| Secret location | secure element | OS keychain (member key) + Ledger backend (encrypted root/branch) + RAM during use |
| Offline | works | needs backend for every encrypt/decrypt |
| Compromise of host | can't sign without device | full decrypt capability if keychain entry + password are stolen |
| Revocation | unplug | remove member → owner device rotates path; old ciphertext stays readable to whoever had the old key, so re-encrypt first |
| Recovery | OpenPGP: key backup (OS updates wipe keys) | same seed + backend still holding the tree |
| Ledger as a party | not involved | backend sees encrypted blobs and membership metadata, can deny service, cannot read keys (PublishKey is encrypted to member pubkeys) |

Sources: docs comparison table (VERIFIED), whitepaper ("the protocol is not suitable for securing blockchain assets", "the backend is only responsible for storing encrypted" data) (VERIFIED), rest INFERRED.

Related but distinct: **Ledger Agent Intent** (`wallet-cli agent-intent enroll`, 2.9.0, beta) enrols a *software-only* agent key as a member on the Ledger Sync branch (app 16) via a relay link the human approves on their device; the agent then proposes EVM sends that the human clear-signs. Different trust model (SDK built with `refuseAgentDevice`), but it proves the "enrol a USB-less host via a link + device approval elsewhere" UX exists in the same binary. **VERIFIED**.

## 6. Windows specifics

VERIFIED:
- Docs prerequisite line: "macOS, Linux, or Windows (WSL recommended)".
- npm publishes `@ledgerhq/wallet-cli-windows-x64` 2.9.0 (`bin/wallet-cli.exe`), and the CHANGELOG has Windows WebUSB fixes (0.3.0: reconnect handling, discovery of late-plugged devices) — so a native Windows device path exists and has been exercised.
- Code paths for win32: Credential Manager hint in the no-TTY error; CRLF-tolerant keychain parse; `%LOCALAPPDATA%\ledger-wallet-cli\State`; non-atomic rename fallback in `writeSecureFile`; `chmod 0600` is best-effort (NTFS ignores POSIX mode — **INFERRED**).
- `@napi-rs/keyring` ships `win32-x64-msvc` etc. (Windows Credential Manager backend) — the README documents only the Linux store selection, so the Windows backend is INFERRED from the platform packages and the wallet-cli hint.
- WSL2 has no USB passthrough without `usbipd-win` (`usbipd bind --busid X`, `usbipd attach --wsl --busid X`); needs kernel ≥ 5.10.60.1 and udev rules inside WSL. Only `ring init` (and other device commands) need it; encrypt/decrypt in WSL need only network + a Secret Service inside WSL (gnome-keyring in WSL is its own headache — **INFERRED**).
- `node-hid` is **not** a dependency; device access is the `usb` 2.17.0 (libusb) package + WebUSB types through the DMK. On Windows, Ledger over WebUSB/libusb relies on the WinUSB driver Ledger Live installs — **INFERRED**.

Practical plan for our box (INFERRED): try the native `.exe` first (`npm i -g @ledgerhq/wallet-cli` on Windows should pull `wallet-cli-windows-x64`); pipe with `WALLET_PASS` always set; fall back to WSL + usbipd only if WebUSB fights us.

## 7. Devices, Ledger Sync app, and lifecycle hazards

- Ledger Sync device app: installed automatically by Ledger Wallet (ex-Ledger Live) when you turn on Sync (Settings > General > Ledger Sync), or manually via experimental settings. Agent Intent requires app **≥ 1.3.0**; ring's minimum is undocumented (**gap**). **VERIFIED** (Agent Intent docs, Ledger Sync blog).
- Supported: Nano S Plus, Nano X, Stax, Flex, Nano Gen 5. Not Nano S ("employs AES-256-GCM encryption, which is not compatible" — support-site snippet, page itself is JS-rendered and did not fetch). **VERIFIED** list via Agent Intent docs; Nano S reason INFERRED from snippet.
- One root per seed: Ledger Sync (app 16) and the ring (app 17) are branches of the same trustchain. Bug fixed 2026-06 (ledger-live #17817 + backend #519): `ring init` used to evict the Ledger Sync member. Fixed server-side; not something we control. **VERIFIED**.
- Docs: "Removing a Ledger Sync member rotates the encryption key. Re-encrypt older data before removing a member." The SDK's `removeMember` closes the *current application's* stream (app 16 for Ledger Wallet). Whether removing a Sync member in Ledger Wallet really rotates the app-17 branch, or whether the docs conflate the two, I could not confirm. **CONTRADICTION / open**.
- Ledger Sync data is deleted after one year of inactivity (support search snippet). If that purge takes the whole root, ring ciphertext becomes unrecoverable. **INFERRED, unverified** — ask on Discord.
- `ring destroy` deletes the whole trustchain if the ring was the last open application (i.e. if you never turned on Ledger Sync). **VERIFIED**.
- Where can a user see/remove ring members? Ledger Wallet's Sync "Manage" screen shows Sync instances; whether app-17 members appear there is unknown. **gap**.

## 8. Contradictions and doc gaps to put in the required DX write-up

1. "Keys derived from your Ledger seed" (hackathon brief) vs whitepaper "LKRP encryption keys are always randomly generated". Recovery depends on Ledger's backend, which no doc states plainly.
2. PR #19477 description table says `ring encrypt/decrypt` require a device; the code and the docs say no device. The docs page's own comparison table is correct.
3. Docs say "Windows (WSL recommended)" while npm ships a native Windows binary and the code carries Windows-specific hints. No Windows example for `WALLET_PASS` in the docs page or skill; only in the runtime error string.
4. `--unsecure-no-password` exists in `--help`, is warned about in docs, and is absent from the agent skill (issue #21910, open since 2026-09-13).
5. I/O semantics (stdin default, TTY refusal, JSON+stdout error, 0600 atomic write) only in source.
6. No documented minimum Ledger Sync app version for ring; no statement on what the device screen shows at `ring init`.
7. No enrolment path for USB-less hosts despite "Headless by design" marketing and Ledger's own ETHOnline ask.
8. Ciphertext has no header: no version, no key-name hint, no way to tell a ring file from random bytes.
9. Whitepaper typo: members decrypt "with their public key" (should be private). Whitepaper also omits the ECDH→AES KDF (it is `HMAC-SHA256(key="", x)` in `NobleCrypto.ts`) and uses 16-byte GCM nonces where wallet-cli uses 12.
10. `@ledgerhq/ledger-key-ring-protocol` 1.0.0 on npm has no README text; the real docs are `docs/ledger-sync/01-hardware-lkrp.md` and `02-trustchain-sdk.md` inside ledger-live, which point to an internal Confluence page for the full spec.

## 9. Hackathon angles this enables (all INFERRED)

- **Ring for headless hosts, done properly**: a small tool that uses `@ledgerhq/ledger-key-ring-protocol` `addMember` (software device) from an enrolled laptop to add a CI runner / VPS / container as an app-17 member, with the human approving on the Ledger (reuse the Agent Intent "link + approve on device" UX). Directly answers the brief's "Bring Key Ring to environments without USB". Risk: `addMember` on a branch needs an issuer who holds the branch key, which the laptop member does — plausible, untested.
- **Key Ring as a sops/age-style backend**: `wallet-cli ring` as the KMS behind `.env`/sops/age; Ledger explicitly suggested this.
- **Agent that boots from the ring**: decrypt API keys into process memory at startup (the #21910 pattern), with a Ledger Signer (DMK) for the high-risk actions. Clear autonomous/approved boundary.
- **Scoped-capability broker**: Ledger's ETHOnline wish list, "a broker that issues scoped capabilities so the API key itself is never handed out" — ring holds the long-lived key, broker mints short-lived tokens.
- **Our Idea 1 (voice + face Siri)**: ring can hold the agent's LLM/STT/RPC keys; the Ledger device is the face-scan replacement (the device *is* the second factor). Face scan on top is theatre unless it gates something the device doesn't.
- **Our Idea 2 (NFC ledger-to-ledger)**: unrelated to the ring; the ring doesn't touch NFC or payments.
- **Non-finance**: encrypted shared notes/credentials for a club, where adding/removing a member is a device-approved act and the device never does bulk crypto (the whitepaper's own "note application" example, categories at `m/0'/16'/0'/8'/0'/...`).
- **Pure demo without hardware for CI**: `WALLET_CLI_MOCK=1` lets the pipeline test the ring flow in GitHub Actions.

## 10. Open questions (ask Ledger on Discord)

1. Minimum Ledger Sync app version for `ring init`? What does the device display at enrol time ("Add member <name>"?).
2. Does removing a Ledger Sync member in Ledger Wallet rotate the app-17 (ring) branch, or only app 16?
3. Does the 1-year Sync inactivity purge delete the root (and thus ring data)? Does `ring encrypt/decrypt` activity count as "activity"?
4. Is adding a software member to app 17 via the SDK `addMember` from an enrolled laptop supported/permitted by the backend permissions model? Any plan for a `ring add-member`/`ring export` command?
5. Is native Windows officially supported, or only WSL? Any known WebUSB driver issue on Windows 11 with Flex over USB-C?
6. Does `@napi-rs/keyring` 1.3.0 (wallet-cli pin) fall back to in-memory keyutils on headless Linux, or hard-fail?
7. Rate limits / availability SLO on `trustchain.api.live.ledger.com` for an agent doing many decrypts?
8. Any way to decrypt with a Ledger device *instead of* the backend for an air-gapped host (the whitepaper's "secure device reads the backup" path)?

## Sources

Primary (Ledger / ledger-live / npm):
- https://developers.ledger.com/docs/ai-tools/ledger-cli (and `.md` variant https://developers.ledger.com/docs/ai-tools/ledger-cli.md)
- https://developers.ledger.com/docs/ai-tools/overview
- https://developers.ledger.com/docs/ai-tools/agent-intent
- https://developers.ledger.com/docs/ai-tools/hardware-security/open-pgp
- https://github.com/LedgerHQ/ledger-live/blob/develop/apps/wallet-cli/README.md
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/CHANGELOG.md
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/package.json
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/key-ring/crypto.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/key-ring/constants.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/key-ring/lkrp-sdk.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/key-ring/keychain.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/key-ring/load-key-ring.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/key-ring/prompt.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/commands/ring/init.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/commands/ring/encrypt.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/commands/ring/decrypt.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/commands/ring/shared.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/commands/ring/keys.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/commands/ring/destroy.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/commands/agent-intent/enroll.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/shared/secure-file.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/session/session-store.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/.agents/skills/ledger-wallet-cli/SKILL.md
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/docs/ledger-sync/01-hardware-lkrp.md
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/docs/ledger-sync/02-trustchain-sdk.md
- https://github.com/LedgerHQ/ledger-live/pull/16859 (closed), https://github.com/LedgerHQ/ledger-live/pull/17743 (closed), https://github.com/LedgerHQ/ledger-live/pull/19477 (merged), https://github.com/LedgerHQ/ledger-live/pull/17817
- https://github.com/LedgerHQ/ledger-live/issues/21910
- https://raw.githubusercontent.com/LedgerHQ/agent-skills/main/skills/wallet-cli/wallet-cli-usage/SKILL.md
- https://raw.githubusercontent.com/LedgerHQ/agent-skills/main/skills/wallet-cli/wallet-cli-usage/references/business-logic.md
- https://unpkg.com/@ledgerhq/ledger-key-ring-protocol@1.0.0/README.md , /src/sdk.ts , /src/utils.ts , /src/mockSdk.ts
- https://unpkg.com/@ledgerhq/hw-ledger-key-ring-protocol/README.md , /src/index.ts , /src/StreamTree.ts , /src/Device.ts , /src/ApduDevice.ts , /src/Crypto.ts , /src/NobleCrypto.ts
- https://registry.npmjs.org/@ledgerhq/wallet-cli , https://registry.npmjs.org/@ledgerhq/wallet-cli-windows-x64 , https://registry.npmjs.org/@ledgerhq/ledger-key-ring-protocol , https://registry.npmjs.org/@napi-rs/keyring , https://registry.npmjs.org/@bunli/utils
- https://github.com/Brooooooklyn/keyring-node
- https://raw.githubusercontent.com/AryaLabsHQ/bunli/main/packages/utils/src/xdg.ts
- https://github.com/LedgerHQ/ledger-key-ring-protocol-whitepaper and the PDF https://raw.githubusercontent.com/LedgerHQ/ledger-key-ring-protocol-whitepaper/main/Ledger%20Key%20Ring%20Protocol%20Technical%20White%20Paper.pdf (text extracted locally with pdftotext)
- https://www.ledger.com/blog-ledger-key-ring-protocol-secure-data-sharing
- https://www.ledger.com/blog-ledger-sync-synchronize-your-crypto-accounts-effortless-private-and-secure
- https://ethglobal.com/events/ethonline2026/prizes/ledger
- https://learn.microsoft.com/en-us/windows/wsl/connect-usb

Secondary / could not fetch body (JS-rendered), used only via search snippets:
- https://support.ledger.com/article/Ledger-Sync-FAQs
- https://support.ledger.com/article/How-to-synchronize-your-Ledger-Live-accounts-with-Ledger-Sync
- https://support.ledger.com/article/Ledger-Nano-S-Limitations
- https://siliconangle.com/2026/07/16/ledger-launches-agent-stack-keep-ai-agents-away-crypto-keys/
