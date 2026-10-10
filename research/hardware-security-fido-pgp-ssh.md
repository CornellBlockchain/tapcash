# Ledger hardware-security primitives: Security Key (FIDO2/U2F), OpenPGP, SSH

Research note for the N3XT hackathon (deadline 2026-10-13). Written 2026-10-10. Nothing was installed or plugged in; everything below comes from reading docs and source. Each claim is tagged **VERIFIED** (read in a primary source) or **INFERRED** (my deduction). Gaps are called out, not papered over.

Hardware on hand: Ledger Nano S Plus (USB only) and Ledger Flex (USB, BLE, NFC). Host: Windows 11.

---

## 0. TL;DR

| Primitive | Device app | Nano S Plus | Flex | Works on Windows 11 | Headless? | Good "human approval" primitive? |
| --- | --- | --- | --- | --- | --- | --- |
| FIDO2 / U2F security key | **Security Key** app v1.7.7 | yes (USB HID) | yes (USB HID + NFC; BLE built but abandoned) | yes via browser / webauthn.dll; raw CTAP needs admin | no (tap required; `-O no-touch-required` possible for SSH only) | **Yes, best option.** Tap-per-assertion, challenge is signed, verifiable server-side in ~20 lines with `@simplewebauthn/server` or `python-fido2`. |
| OpenPGP smartcard | **OpenPGP** app v2.7.4 | yes | yes | **unknown**: official Windows section literally says "TODO"; 2018 issue reports PIN modes broken on Windows | partly ("Trust" PIN mode removes prompts; "Confirm only"/UIF requires tap) | Yes, but GnuPG plumbing is heavy; and keys die on app/OS update unless SEED mode + backup. |
| SSH via FIDO (`ed25519-sk`) | Security Key app | yes | yes | OpenSSH-for-Windows supports `-sk` keys through Windows Hello/webauthn (PR merged 2021); reports of enrollment failures | tap per auth/sign | Yes: git commit signing with a tap per commit is a 10-minute demo. |
| SSH via gpg-agent | OpenPGP app | yes | yes | same Windows uncertainty as OpenPGP | yes-ish | Secondary. |
| **SSH/PGP Agent** app + `ledger-agent` | deprecated | - | - | - | - | **Dead. Do not use.** |
| `hmac-secret` (FIDO2 extension) | Security Key app | yes | yes | via python-fido2 WindowsClient (`allow_hmac_secret=True`) or admin raw HID; PRF in Chrome/Edge 116+ on Win11 | tap | Yes: derive a per-action symmetric secret only when a human taps; LUKS use-case is the official demo. |

Headline facts worth building on:

1. **Security Key credentials are deterministically derived from the 24-word seed** (BIP32 path `PKS'/0x80000000/resetGeneration`, resetGeneration pinned to 0). Non-resident credentials therefore survive app reinstall, OS update and device replacement. Ledger's docs do not say this anywhere; the source does. (VERIFIED, source.) Resident keys are disabled in production (VERIFIED).
2. The device-unlock PIN counts as FIDO2 **user verification** (`uv: true`) until a CTAP2 client PIN is set. So Windows Hello / `userVerification: "required"` flows work without a separate FIDO PIN. (VERIFIED, source.)
3. The Security Key app's own README markets Git SSH auth, Git commit signing and LUKS2 unlock as "other use cases" and documents each with copy-paste commands. (VERIFIED.)
4. Ledger's own AI-tools page frames FIDO2 as the agent gate: agents "can use a session a human already opened, but they can't start a new authenticated session to a hardware-gated service on their own." (VERIFIED.)
5. OpenPGP on Windows is a documentation hole. Key Ring is what Ledger recommends instead for secrets; OpenPGP is for "developers already proficient with OpenPGP and GnuPG." (VERIFIED.)

---

## 1. Primary Ledger docs (the two hackathon links)

### 1.1 `developers.ledger.com/docs/ai-tools/hardware-security/security-key`

VERIFIED content (the page is a one-screen conceptual overview, no setup steps):

- "Your Ledger can act as a FIDO2 hardware security key" for services such as GitHub, npm, 1Password, Discord.
- Security Key app supports **FIDO2 and U2F**.
- Private key is generated on the device and never exposed.
- Agent framing: agents can reuse a session a human opened; they cannot open a hardware-gated session themselves. "Gating services this way is a direct method for keeping a human in the loop."
- Links out to: Help Center article `https://support.ledger.com/article/12350325732893-zd` and the Ledger Wallet CLI page.

What it does NOT say: supported devices, install steps, OS notes, PIN, resident keys, any code. **GAP.**

### 1.2 `developers.ledger.com/docs/ai-tools/hardware-security/open-pgp`

VERIFIED content:

- Lets a Ledger hold an OpenPGP private key that gates access to encrypted secrets (files, env vars, API tokens).
- "Intended for developers already proficient with OpenPGP and GnuPG."
- Key pair generated on device; private key never leaves it. Decryption needs the device connected; "a stricter mode requires a manual tap on the device for each decryption" so "a process already running on your machine can't read a secret without your confirmation."
- **Warning:** app updates, OS updates and reinstalls wipe keys unless backed up. Losing them loses everything encrypted to them.
- Comparison with Key Ring: Key Ring needs device only once (`ring init`), needs network for encrypt/decrypt, recovers from seed on a new machine. OpenPGP needs the device every time, no network, recovery via backup only. Ledger recommends Key Ring for most users.
- Links: `github.com/LedgerHQ/app-openpgp` (backup/restore), Help Center `https://support.ledger.com/article/115005200649-zd`.

What it does NOT say: devices, install, gpg config, SSH. **GAP.**

### 1.3 The two Help Center articles

Both `support.ledger.com/article/12350325732893-zd` (Security Key) and `.../115005200649-zd` (OpenPGP) failed to fetch (empty body / CAPTCHA, Salesforce "Knowledge Detail" shell). Archive.org is blocked from this tool. **GAP: I never read them.** Indirect evidence of their content:

- app-security-key issue #104 quotes the Security Key article: "The Security Key app currently doesn't support resident keys." (VERIFIED quote-of-quote.)
- app-openpgp issue #146 (2026-04-04) complained the OpenPGP article still called seeded generation "experimental", had a dead developer-doc PDF link and an obsolete "Windows Agent for PuTTY" section pointing at a deprecated app-ssh-agent fork. Ledger's cedelavergne-ledger replied 2026-04-21: "the documentation is updated (at least the English version)". So the article was revised in April 2026; what the Windows section says now is unknown. (VERIFIED thread; article content INFERRED.)

Action for the team: open both articles in a real browser on day 1 and paste the Windows sections into this note.

### 1.4 `developers.ledger.com/docs/ai-tools/ledger-cli` (for cross-reference)

VERIFIED: the Ledger CLI page never mentions Security Key, FIDO or SSH. It mentions OpenPGP only in the Key Ring comparison table ("Intended for advanced OpenPGP/GnuPG users; private keys do not persist through app reinstalls"). Platform list: "macOS, Linux, Windows (WSL recommended)". Key Ring commands: `wallet-cli ring init`, `wallet-cli ring encrypt -i secrets.txt -o secrets.enc --key my-key`, `wallet-cli ring decrypt -i secrets.enc -o secrets.txt --key my-key`; password via `WALLET_PASS`.

---

## 2. Security Key app (FIDO2 / U2F) — `github.com/LedgerHQ/app-security-key`

### 2.1 Devices, version, standards

- `ledger_app.toml`: `devices = ["nanox", "nanos+", "stax", "flex", "apex_p"]`. **Both our devices are supported.** (VERIFIED)
- Makefile restricts to `TARGET_NANOX TARGET_NANOS2 TARGET_STAX TARGET_FLEX TARGET_APEX_P`; `APPNAME = "Security Key"`; version fields give **1.7.7**. (VERIFIED) CHANGELOG top entry is 1.7.6 (2026-08-14) and issue #138 (2026-09-11) mentions a Flex on 1.7.7, so the changelog lags one release. (VERIFIED, minor contradiction.)
- Ledger's 2023 blog post listed Nano S (original) as supported; the current Makefile does not build for it. Irrelevant to us but shows docs drift. (VERIFIED)
- README standards checklist: FIDO U2F 1.2 and CTAP 2.0 implemented; CTAP 2.1/2.2/2.3 listed unchecked; WebAuthn L2 and L3 referenced. (VERIFIED)
- `get_info.c` advertises versions `U2F_V2` and `FIDO_2_0` only (`FIDO_2_1_PRE`/`FIDO_2_1` commented out); extensions: **`hmac-secret` only** (no credProtect, no largeBlob); pinProtocols: v1 only; options: see 2.3. (VERIFIED)
- Install path: Ledger blog says via Ledger Wallet (ex-Ledger Live) → My Ledger → Security Key app. Developer mode is not mentioned anywhere I read; INFERRED not required (the app is a public catalog app since 2023).

### 2.2 Transports

- Makefile: `HAVE_U2F HAVE_IO_U2F`, `HAVE_FIDO2`, `ENABLE_NFC = 1`. No BLE flag. (VERIFIED)
- CHANGELOG 1.7.0 (2025-06-09): "On Stax and Flex, over NFC, MAKE_CREDENTIAL and GET_ASSERTION functions displays RP and user information"; "Resident Keys: GET_NEXT_ASSERTION function implemented on Stax and Flex, available only over NFC". (VERIFIED)
- Issue #74 "Add bluetooth support", closed completed 2026-07-30; Ledger's iartemov-ledger: "FIDO2 BLE transport has been indeed implemented in both the SDK and the app, and tested on the Ledger Flex" but major platforms "have deprecated or removed support for direct BLE security keys" (hybrid/caBLE won) so "we will not be pursuing this development any further." (VERIFIED) → **BLE FIDO is not a usable path.** Windows 11 only supports BLE for cross-device (phone-as-passkey) flows, which is a different protocol. (INFERRED from MS passkeys doc, which discusses BT only for cross-device auth.)
- Issue #138 (2026-09-11, open): Flex + Security Key 1.7.7 over NFC to iPhone: works with Yubico's webauthn.io demo, fails with Google specifically. (VERIFIED) So **Flex NFC → phone works for generic WebAuthn.** Flex NFC → Windows needs a PC/SC NFC reader on the laptop; neither Ledger doc nor Microsoft doc I read confirms Ledger-over-NFC-to-Windows. (INFERRED; untested.)
- Ledger Academy Stax-vs-Flex page: the Security Key app "transforms your Ledger Stax and Ledger Flex into a Passkey"; login "is a single contactless tap on the device's NFC". Marketing, but consistent. (VERIFIED)

### 2.3 PIN, user verification, resident keys

From `get_info.c` (VERIFIED, verbatim comment):

> "The device unlock PIN is our built-in UV, but it can only be advertised while no client PIN is set: once one is, CTAP2.0 requires pinAuth on every request."

- `uv: !N_u2f.pinSet`, `clientPin: N_u2f.pinSet`, `up: true`, `plat: false`.
- `rk`: `config_get_rk_enabled()` under `ENABLE_RK_CONFIG` (always defined in Makefile), default **0 = disabled**; `ENABLE_RK_CONFIG_UI_SETTING` (the on-device toggle) is only compiled when the build sets it, which production does not. Makefile comment: with `ENABLE_RK_CONFIG` alone, "RK is disabled by default and the user cannot enable it." (VERIFIED)
- CHANGELOG: 1.6.3 "Resident Keys: disabled for production version"; 1.6.4 "enabling option was removed". (VERIFIED)
- README: discoverable credentials "stored on a part of the device flash that gets wiped upon app deletion (on uninstall, app update, or OS update)"; proper support "requires a full backup and restore infrastructure ... Work is ongoing." (VERIFIED)
- Consequences: **no passwordless/username-less login** (Microsoft account, Entra, Windows Hello sign-in, Bitwarden unlock all need RK; issues #73, #111, #139 are labelled "Blocked on RK"). Second-factor and allow-list (`allowCredentials`) flows work fine. For a hackathon RP we control, we always pass `allowCredentials`, so RK is irrelevant. (VERIFIED issues; INFERRED consequence.)
- Setting a CTAP2 client PIN is possible (config.c stores `pin[16]`, `pinRetries` = 8) via Windows Settings → Sign-in options → Security Key, but it then forces pinAuth on every request and drops built-in `uv`. **Recommendation: do not set a client PIN; rely on device-unlock-as-UV.** (VERIFIED storage; INFERRED recommendation.)
- Revocation counter disabled (`HAVE_NO_RESET_GENERATION_INCREMENT`), so `resetGeneration` stays 0 forever. (VERIFIED)
- Issue #79 (open): registration fails when the RP sets `enforceCredentialProtectionPolicy: true` (credProtect not implemented). Don't set that in our RP. (VERIFIED)

### 2.4 Key derivation: credentials come from the seed (undocumented, source-verified)

`config.c` `derive_and_store_keys(resetGeneration)`:

- Path = `[PRIVATE_KEY_SEED_PATH, 0x80000000, resetGeneration]` via `os_derive_bip32_no_throw(CX_CURVE_SECP256R1, ...)`; 64-byte output → `N_u2f.privateKeySeed`. Same for `WRAPPING_KEY_PATH`.
- `config.h`: `#define WRAPPING_KEY_PATH 0x80575241 // "WRA"`, `#define PRIVATE_KEY_SEED_PATH 0x80504b53 // "PKS"`.
- `wrappingKeyU2F / wrappingKeyCTAP2 = SHA256(VERSION || wrappingKey)`.
- On every launch when already initialised, the code re-derives and "Check[s] that the seed did not change - if it did, overwrite the keys".
- `crypto.c`: credential private key = `SHA256((0 <<128 | nonce) || privateKeySeed)`; `credRandom` (hmac-secret) key = `SHA256((1 or 2 <<128 | nonce) || privateKeySeed)` (UV vs no-UV variants).
- `credential.c`: credential ID = version byte || AES-SIV tag || nonce || (CTAP2 only) AES-SIV-encrypted CBOR {handle version, flags, alg, user id, user name}; AAD = rpIdHash; key = wrapping key.

All VERIFIED from source. Therefore (INFERRED but tight): a non-resident credential ID embeds everything needed, and the keys to unwrap/re-derive it are a pure function of the 24-word seed. Reinstalling the Security Key app, updating the OS, or restoring the same seed onto a different Ledger (e.g. Nano S Plus → Flex) keeps every registered FIDO credential working. The authentication counter does not survive (`authentificationCounter` reset to 1 and incremented by random 1–5 each use), so an RP that strictly enforces monotonic counters could flag a restored device once. Issue #113 (SLIP-0022, closed 2026-10-06) had community commenter My1 noting "non-resident keys already exist in a custom format also based on the seed" — consistent.

This is a real differentiator over YubiKey and worth a slide: **"a seed-recoverable FIDO2 authenticator"**.

### 2.5 Official use-cases with commands (from `doc/`)

Git/SSH auth (`doc/usecase-git-auth.md`, VERIFIED):

```sh
ssh-keygen -t ed25519-sk -f ~/.ssh/id_ledger_sk      # or -t ecdsa-sk if the server lacks Ed25519
# device must be unlocked, Security Key app open and showing "Ready"; tap to confirm
ssh-keygen -t ed25519-sk -O no-touch-required -f ~/.ssh/id_ledger_sk   # GitHub rejects these
```
Requires OpenSSH ≥ 8.2. `id_ledger_sk` is a key handle, not a secret. Register `.pub` as a GitHub "Authentication Key" or in `authorized_keys`.

Git commit signing (`doc/usecase-git-signing.md`, VERIFIED). Requires Git ≥ 2.34, OpenSSH ≥ 8.2:

```sh
ssh-keygen -t ed25519-sk -f ~/.ssh/id_ledger_sk_signing
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ledger_sk_signing.pub
git config --global commit.gpgsign true
echo "$(git config user.email) $(cat ~/.ssh/id_ledger_sk_signing.pub)" >> ~/.ssh/allowed_signers
git config --global gpg.ssh.allowedSignersFile ~/.ssh/allowed_signers
git commit -S -m "msg"          # tap per commit
git log --show-signature
```
Register the `.pub` on GitHub as a **Signing Key**.

LUKS2 via `hmac-secret` (`doc/usecase-luks.md`, VERIFIED; Linux only: cryptsetup 2.4+, systemd 251+):

```sh
fallocate -l 8G vault.img
sudo cryptsetup luksFormat --type luks2 --cipher aes-xts-plain64 --key-size 512 --hash sha512 --pbkdf argon2id vault.img
sudo systemd-cryptenroll --fido2-device=auto vault.img
sudo /lib/systemd/systemd-cryptsetup attach my_vault vault.img none fido2-device=auto
sudo mkfs.ext4 /dev/mapper/my_vault
```
Enrollment asks for the fallback passphrase, then a tap. Proves the app's `hmac-secret` works end-to-end.

### 2.6 Windows 11 specifics

- Browser WebAuthn (Chrome/Edge/Firefox) → `webauthn.dll` → Ledger over USB HID: standard; no admin. Windows 11 24H2+ shows a passkey privacy-consent prompt for native apps (Settings → Privacy & security → Passkey access). (VERIFIED, MS docs)
- **Raw CTAP2 HID from your own process requires Administrator on Windows ≥ 1903.** python-fido2 README: "access to FIDO devices is restricted and requires running as Administrator"; non-admin processes must use `fido2.client.windows.WindowsClient`, which calls the platform API and pops the Windows security dialog. (VERIFIED) libfido2 has `USE_WINHELLO` ON by default ("Abstract Windows Hello as a FIDO device"). (VERIFIED) A background service/agent therefore cannot silently poke the Ledger; it either runs elevated or triggers a UI prompt. That is the right property for an approval primitive but kills "headless".
- OpenSSH for Windows: PowerShell/openssh-portable PR #541 (merged 2021-12-18) "enables client-side support for FIDO2/U2F security keys, allowing the generation and use of ecdsa-sk and ed25519-sk on cross-platform and platform authenticators, from PowerShell and WSL." (VERIFIED) Win32-OpenSSH issue #2040 (2023, open): `ssh-keygen -t ecdsa-sk` with **Windows Hello** fails "Key enrollment failed: invalid format" on 9.2p1 while a YubiKey works — so cross-platform keys work, platform authenticator does not. (VERIFIED) solo2 discussion #108: resident `-sk` enrollment failed on Windows 11 via `C:\Program Files\OpenSSH\ssh-sk-helper.exe`. (VERIFIED) Ledger has no RK anyway, so use non-resident keys. Git for Windows ships its own MSYS2 OpenSSH; whether it is built with the security-key helper is **unverified**. Safer: `git config --global core.sshCommand "C:/Windows/System32/OpenSSH/ssh.exe"` and `ssh -V` to confirm ≥ 8.2. (INFERRED from guides.)
- NFC to Windows: needs a PC/SC NFC reader; untested. (INFERRED)
- Windows Hello / Microsoft account enrollment of the Ledger as a passkey: blocked on RK (issues #73, #111). (VERIFIED)

### 2.7 Headless CTAP from Python (works on Windows non-admin via WindowsClient)

From `python-fido2/examples/hmac_secret.py` (VERIFIED; `pip install fido2`, Python ≥ 3.10, v2.x):

```python
import ctypes, os
from fido2.client import DefaultClientDataCollector, Fido2Client
from fido2.client.windows import WindowsClient
from fido2.ctap2.extensions import HmacSecretExtension
from fido2.server import Fido2Server

cdc = DefaultClientDataCollector("https://example.com")
if WindowsClient.is_available() and not ctypes.windll.shell32.IsUserAnAdmin():
    client = WindowsClient(cdc, allow_hmac_secret=True)        # Windows dialog, no admin
else:
    dev = next(iter(enumerate_devices()))                       # raw HID, admin on Windows
    client = Fido2Client(dev, client_data_collector=cdc,
                         extensions=[HmacSecretExtension(allow_hmac_secret=True)])

server = Fido2Server({"id": "example.com", "name": "Example RP"}, attestation="none")
create_options, state = server.register_begin({"id": b"user_id", "name": "A. User"},
    resident_key_requirement="discouraged", user_verification="discouraged",
    authenticator_attachment="cross-platform")
result = client.make_credential({**create_options["publicKey"], "extensions": {"hmacCreateSecret": True}})
auth_data = server.register_complete(state, result)

salt = os.urandom(32)
request_options, state = server.authenticate_begin([auth_data.credential_data])
res = client.get_assertion({**request_options["publicKey"],
                            "extensions": {"hmacGetSecret": {"salt1": salt}}}).get_response(0)
secret = res.client_extension_results.hmac_get_secret.output1   # deterministic per (credential, salt)
```
Comment in that example: `hmacCreateSecret` "fails on Windows, but we might still be able to use hmac-secret even if the credential wasn't made with it". (VERIFIED)

libfido2 CLI equivalent (VERIFIED man page): `fido2-assert -G [-h] [-t up=true|false] [-t uv=...] [-t pin=...] device`, input lines = client data hash, RP ID, credential ID, (salt if `-h`); output = client data hash, RP ID, CBOR authData, signature, (hmac secret). `-w` for Windows Hello which hashes client data itself. Windows binaries only from Yubico's release page.

### 2.8 WebAuthn in a web app to gate agent actions

Mechanics (VERIFIED, MDN + W3C RP-ops step 8):
- `challenge` "originating from the relying party's server ... will be signed by the authenticator".
- `signature` = authenticator signature over `authenticatorData || SHA-256(clientDataJSON)`; `clientDataJSON` carries the challenge and origin.
- RP must "Verify that the value of C.challenge equals the base64url encoding of pkOptions.challenge" (WebAuthn L3 §7.1 step 8; same shape in §7.2).
- `userVerification`: `"required" | "preferred" (default) | "discouraged"`.
- Secure context required; `http://localhost` is allowed by Chromium with RP ID `localhost`; `127.0.0.1` is not; a LAN IP needs an HTTPS tunnel for phone testing. (VERIFIED Chromium origins.md via search summary; INFERRED details.)

Pattern for "approve this agent action" (INFERRED design, standard practice):

1. Agent proposes action → server stores `{action_json, nonce}` and sets `challenge = SHA256(canonical(action_json) || nonce)` (≥16 random bytes satisfied by the nonce).
2. Browser page shows the action, calls `navigator.credentials.get({publicKey:{challenge, rpId, allowCredentials:[ledgerCredId], userVerification:"preferred"}})`. Ledger shows the RP on screen (Flex: RP + user over NFC; USB: generic prompt) and the human taps.
3. Server verifies with `@simplewebauthn/server` v14 (Node ≥ 22): `verifyAuthenticationResponse({response, expectedChallenge, expectedOrigin, expectedRPID, credential:{id, publicKey, counter, transports}})`. (VERIFIED API shape.) Store `{authenticatorData, clientDataJSON, signature}` as the **attestation receipt**: anyone with the registered public key can re-verify offline that this exact action hash was approved by that hardware.
4. Only after step 3 does the server release the agent's capability (API token from Key Ring, signed tx, etc.).

Caveats (honest):
- The Ledger screen does not display the challenge, so the human is trusting the browser page to show the right action ("what you see is what you sign" is not provided by FIDO; it is by the Signer/clear-signing path). Pitch it as *presence + intent* evidence, not as clear signing. (INFERRED)
- Attestation on Ledger: `get_info.c` uses a `FIDO2_ATTESTATION_KEY`; whether the AAGUID is in FIDO MDS is unknown. Use `attestation: "none"`. (INFERRED)
- PRF extension in browsers maps to `hmac-secret`: Chrome/Edge 116+ on Windows 11 support PRF with security keys ("security keys require hmac-secret & discoverable creds" per Corbado's table). Ledger has hmac-secret but no discoverable creds, so **PRF via browser may fail on Ledger; use the python-fido2 / libfido2 route for hmac-secret instead.** (VERIFIED table; INFERRED consequence; issue #139 "Support for PRF WebAuthn" is labelled Blocked on RK, consistent.)

---

## 3. OpenPGP app — `github.com/LedgerHQ/app-openpgp`

### 3.1 Facts

- `ledger_app.toml`: devices `["nanox", "nanos+", "stax", "flex", "apex_p"]`. (VERIFIED)
- Makefile: `APPNAME = OpenPGP`, version **2.7.4**, `SPEC_VERSION "3.3.1"`, `ENABLE_USB_CCID = 1`, `DISABLE_STANDARD_U2F = 1`, `DISABLE_STANDARD_WEBUSB = 1`, `HAVE_RSA`, `CURVE_APP_LOAD_PARAMS = secp256k1`, `PATH_APP_LOAD_PARAMS = "2152157255'"`. (VERIFIED) → the app exposes a **USB CCID smart-card interface**; GnuPG talks to it through pcsc / scdaemon, not HID.
- Algorithms: RSA 2048/3072/4096, ECDSA secp256r1/secp256k1, EdDSA Ed25519, ECDH secp256r1/secp256k1/cv25519. (VERIFIED)
- 3 key slots, each with Sig/Dec/Aut keys. Default template RSA 2048; change via gpg `key-attr` or on-device. Changing template erases the key. (VERIFIED)
- **SEED mode** (default ON at app start per user guide): keys derived from the Ledger seed so "the same keys and fingerprints can be reproduced on a new token"; also required for private-key restore. Known gap: no APDU to toggle seed mode. (VERIFIED)
- **Data loss:** "All on-device data is erased when the OpenPGP App is reinstalled, which happens on an App update and on a device OS update." Backup script in `pytools/` "not guaranteed to work in every scenario." (VERIFIED)
- PIN modes (on-device setting): **On Screen** (PIN typed on device), **Confirm only** (default; tap, no PIN value), **Trust** (PIN always considered valid; "only for highly secure environments", cannot be default). **UIF mode**: force a tap for sign / decrypt / auth. Default PINs: user `123456`, admin `12345678`. (VERIFIED)
- Device USB IDs for CCID config: Nano S Plus `0x2C97:0x5000`, Flex `0x2C97:0x7000`. (VERIFIED)
- GnuPG ≥ 2.1.19 for ECC; ≥ 2.4.0 recommended. (VERIFIED)

### 3.2 GnuPG configuration (Linux/macOS, from the user guide; VERIFIED)

`~/.gnupg/scdaemon.conf`:
```
reader-port "Ledger Token"
allow-admin
enable-pinpad-varlen
disable-ccid
pcsc-shared
```
`enable-pinpad-varlen` is mandatory "or gpg may request the PIN on the host, which the App does not support". Find reader name with `pcsc_scan`; test with `gpg --card-status`.

Generate on device:
```
gpg --edit-card
gpg/card> admin
gpg/card> key-attr        # pick ECC / Curve 25519 for all three keys
gpg/card> generate        # answer 'n' to off-card backup
gpg --list-secret-keys john.doe@foo.com
```
Seeded restore without backup:
```
python3 -m gpgcard.gpgcli --pinpad --set-templates ed25519:cv25519:ed25519 \
  --set-fingerprints '<SC_FP>:<E_FP>:<A_FP>' --serial 'FD6C11BE' --seed-key
gpg --faked-system-time "20240118T100841!" --full-generate-key   # option 14 "Existing key from card"
```
Backup/restore (SEED mode must be on):
```
./backup.py --adm-pin 12345678 --user-pin 123456
./backup.py --restore --adm-pin 12345678 --user-pin 123456 --seed-key
```

SSH via gpg-agent:
```
# ~/.gnupg/gpg-agent.conf
enable-ssh-support
allow-loopback-pinentry
# ~/.gnupg/gpg.conf
pinentry-mode loopback
# shell
export SSH_AUTH_SOCK=$(gpgconf --list-dirs agent-ssh-socket); export GPG_TTY=$(tty); gpgconf --launch gpg-agent
gpg -k --with-subkey-fingerprint --with-keygrip john.doe@foo.com
echo <AUTH_KEYGRIP> > ~/.gnupg/sshcontrol
gpg --export-ssh-key <AUTH_SUBKEY_FINGERPRINT>   # → authorized_keys
ssh-add -l
```
Troubleshooting one-liners: `gpgconf --reload scdaemon`, `gpg-connect-agent updatestartuptty /bye` (fixes "agent refused operation" with no pinpad prompt), `killall scdaemon gpg-agent`.

### 3.3 Windows status: a hole

- User guide §3.1.3 "Windows": **`TODO...`** (VERIFIED, both the rst and the hosted HTML, (c) 2025). Gpg4win, Kleopatra, Windows reader names: not mentioned anywhere.
- Issue #31 (2018): "On Screen" and "Confirm Only" PIN modes not working on Windows; scdaemon.conf had `reader-port "Ledger Nano S 0"` and `enable-pinpad-varlen`; Windows still popped a host PIN box. Last comment 2020-01: "works in last version" with no detail. (VERIFIED) → the Windows PC/SC reader name is probably `"Ledger Nano S Plus 0"` / `"Ledger Flex 0"` (INFERRED from the pattern), and Windows' built-in CCID driver means no `Info.plist` step (INFERRED from the guide saying manual CCID config is only needed for Linux/macOS).
- Issue #146 (2026): the support article's Windows guidance was an obsolete PuTTY/app-ssh-agent section; now "updated" in English. Unknown content. (VERIFIED thread)
- Ledger Wallet desktop holds the HID interface; CCID is a separate interface so they may coexist, but the guide's troubleshooting ("multiple agents", "Mac not seeing the device") suggests fragility. (INFERRED)

Bottom line: OpenPGP on Windows is plausible via Gpg4win + the config above, but nobody at Ledger has written it down and the only Windows bug report is from 2018. **Budget a half day or do OpenPGP in WSL2 with usbipd, or skip it.**

### 3.4 Agent angle for OpenPGP

- "Confirm only" + UIF on the Decrypt key = a tap per decryption: the agent's secrets file (`gpg -d secrets.gpg`) cannot be read without a human present. Ledger's own page describes exactly this. (VERIFIED)
- "Trust" PIN mode = fully headless decryption/signing while plugged in (device presence is the only gate). (VERIFIED mode; INFERRED usage.)
- Sign with `gpg --detach-sign`; verifiable receipt with the public key; git `gpg.format openpgp` commit signing also works but the SSH-sk route is far less plumbing.
- Compared with Key Ring (recommended by Ledger): Key Ring = device once, network required, seed-recoverable. OpenPGP = device every time, offline, update-fragile. Pick OpenPGP only if "offline + tap per decrypt" is the demo point.

---

## 4. SSH/PGP Agent app and `ledger-agent`

- `github.com/LedgerHQ/app-ssh-agent` README: "⚠️ DEPRECATED", points to app-openpgp and app-security-key. Python 2 scripts (`python getPublicKey.py`, `python agent.py --key AAAA...`), prime256v1 and ed25519 only. (VERIFIED)
- PyPI `ledger-agent` 0.9.0, uploaded **2017-04-29**, empty description; romanz/trezor-agent README now lists only Trezor, Jade and OnlyKey. (VERIFIED) README-Windows.md 404s. (VERIFIED)
- **Do not build on this.** The two living paths are FIDO `-sk` SSH keys (Security Key app) and gpg-agent SSH (OpenPGP app).

---

## 5. What is possible headlessly (no human at the keyboard)

| Want | Reality |
| --- | --- |
| FIDO assertion with no tap | Only via `ssh-keygen -O no-touch-required` for SSH keys (GitHub rejects such keys). Browser WebAuthn always requires `up`. Ledger's `getInfo` says `up: true`; no "silent" mode. **Not headless.** (VERIFIED/INFERRED) |
| FIDO from a Windows service | Needs admin for raw HID, else `WindowsClient` shows a dialog. Linux/WSL with udev rules: raw HID fine as user. (VERIFIED python-fido2) |
| OpenPGP decrypt/sign with no tap | "Trust" PIN mode + UIF off: yes, gated only by device plugged in and unlocked. Device auto-locks after inactivity timeout (INFERRED), so a long-running agent will stall. |
| Seed-recoverable secrets without the device | Key Ring (`wallet-cli ring`), not OpenPGP or FIDO. (VERIFIED) |
| CI / cloud | Neither FIDO nor OpenPGP; use Key Ring per the hackathon brief. (VERIFIED brief) |

---

## 6. How an AI agent can use these as "human approval" / "attestation" primitives

Ranked by build cost on Windows in 3 days:

1. **WebAuthn approval gate (Security Key app, USB, browser).** Agent → server proposes action → page → tap on Ledger → `verifyAuthenticationResponse` → release capability. Deliverables: approval receipt JSON (`authenticatorData`, `clientDataJSON`, `signature`, credential public key) that anyone can re-verify. Fits the brief's "clear boundary between autonomous and human-approved." Works on Nano S Plus (USB) and Flex (USB; NFC to a phone page for the mobile demo). Risk: low. Novelty: medium; the seed-recoverability point (2.4) is the interesting slide.
2. **Tap-signed git commits for agent-written code.** `ed25519-sk` signing key; agent writes code, human taps to sign each commit; GitHub shows "Verified". 15-minute setup on Linux/WSL; Windows OpenSSH path probably works for non-resident keys (PR #541) but untested. Combine with (1): same device, same app.
3. **hmac-secret-derived per-action secret.** Agent needs a symmetric key to open a vault / decrypt a config: ask the authenticator for `hmacGetSecret(salt = action_hash)`; human taps; secret exists in RAM only for that action. Python via `WindowsClient(allow_hmac_secret=True)` (no admin) or raw HID in WSL. Novelty: high (this is how Windows offline unlock and systemd LUKS work, almost nobody does it for agents). Risk: `hmacCreateSecret` "fails on Windows" at creation but assertion-time hmac may still work (python-fido2 comment); verify on day 1.
4. **OpenPGP "tap to decrypt" secret store.** Strong story (offline, no network, device every time) but Windows setup undocumented. Only if someone has WSL2+usbipd or Linux.
5. **gpg-agent SSH.** Redundant with (2). Skip.

Attestation semantics to state honestly in the pitch: FIDO proves *a specific registered authenticator, with its owner physically present (and PIN-unlocked = UV), signed this server-chosen challenge at this origin*. It does not prove the human read the action; that is what the Ledger Signer / clear-signing path adds. The two compose: FIDO for cheap, fast approvals of low-risk actions; DMK Signer for clear-signed high-risk ones.

---

## 7. Contradictions and gaps (blunt)

- Security Key README says "resident credentials are currently disabled"; CHANGELOG 1.7.0 says GET_NEXT_ASSERTION for RKs implemented "only over NFC" on Stax/Flex; issue #129 shows a Stax displaying "Register Resident Key" then failing. Reading: RK code paths exist and may be reachable over NFC, but the production config flag is off. Treat RK as unavailable.
- Security Key version: Makefile 1.7.7 vs CHANGELOG top 1.7.6.
- Ledger 2023 blog lists Nano S; current build targets exclude it.
- OpenPGP seeded mode: docs page implies keys are only recoverable via backup; the app README says SEED mode reproduces keys on a new token and is on by default. The support article was fixed only in April 2026.
- OpenPGP Windows section is literally "TODO" in the current user guide.
- Both Help Center articles unread (blocked). Content inferred from GitHub issues only.
- Flex NFC → Windows PC: unverified; Flex NFC → iPhone: verified working for generic WebAuthn (issue #138), failing for Google.
- Ledger Security Key AAGUID / FIDO MDS listing: not checked; use `attestation: "none"`.
- WebAuthn L3 §13.4.3 (challenge randomness) not read directly (page too long); relied on MDN and §7.1 step 8.
- Git for Windows OpenSSH `-sk` support: unverified.
- Whether the Security Key app's `uv=true`-via-device-PIN is accepted by Windows' `webauthn.dll` as satisfying `userVerification: "required"`: INFERRED yes from the CTAP semantics; test on day 1.

---

## 8. Day-1 checklist (no installs were done for this note)

1. Ledger Wallet → My Ledger → install **Security Key** on both devices; open it; go to https://webauthn.io, register and authenticate (Chrome, USB). Try `userVerification: required` on https://webauthn.me/debugger.
2. Flex: tap to phone on webauthn.io over NFC.
3. `ssh -V` in PowerShell (≥ 8.2) → `ssh-keygen -t ed25519-sk` → tap → add to GitHub as Signing Key → one signed commit.
4. `pip install fido2` → run `hmac_secret.py` adapted as above, non-admin; confirm `hmacGetSecret` returns bytes from the Ledger.
5. Open both Help Center articles in a browser; paste Windows sections here.
6. Only if time: Gpg4win + OpenPGP app, `gpg --card-status`, `reader-port "Ledger Nano S Plus 0"` guess.

---

## 9. Sources

Ledger docs
- https://developers.ledger.com/docs/ai-tools/hardware-security/security-key (and `.md`)
- https://developers.ledger.com/docs/ai-tools/hardware-security/open-pgp (and `.md`)
- https://developers.ledger.com/docs/ai-tools/ledger-cli
- https://support.ledger.com/article/12350325732893-zd (fetch failed)
- https://support.ledger.com/article/115005200649-zd (fetch failed)
- https://www.ledger.com/blog/strengthen-the-security-of-your-accounts-with-webauthn
- https://www.ledger.com/academy/topics/ledgersolutions/ledgers-next-generation-devices-ledger-stax-vs-ledger-flex
- https://openpgp.apps.ledger.com/app-openpgp.html

app-security-key
- https://github.com/LedgerHQ/app-security-key (README)
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/README.md
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/Makefile
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/ledger_app.toml
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/CHANGELOG.md
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/doc/usecase-git-auth.md
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/doc/usecase-git-signing.md
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/doc/usecase-luks.md
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/src/ctap2/get_info.c
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/src/config.c
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/src/crypto.c
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/src/credential.c
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/src/app_main.c
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/src/globals.c
- https://raw.githubusercontent.com/LedgerHQ/app-security-key/main/include/config.h
- https://api.github.com/repos/LedgerHQ/app-security-key/contents/src ; .../src/ctap2
- Issues: https://github.com/LedgerHQ/app-security-key/issues/74 (+comments), /113 (+comments), /138, /111, /129, /139, /104, /73, /79, /7
- https://api.github.com/search/issues?q=repo:LedgerHQ/app-security-key+windows ; ...+resident

app-openpgp
- https://github.com/LedgerHQ/app-openpgp (README)
- https://raw.githubusercontent.com/LedgerHQ/app-openpgp/master/doc/user/app-openpgp.rst
- https://raw.githubusercontent.com/LedgerHQ/app-openpgp/master/Makefile
- https://raw.githubusercontent.com/LedgerHQ/app-openpgp/master/ledger_app.toml
- https://raw.githubusercontent.com/LedgerHQ/app-openpgp/master/CHANGELOG.md (404)
- https://api.github.com/repos/LedgerHQ/app-openpgp/releases (empty)
- Issues: https://github.com/LedgerHQ/app-openpgp/issues/146 (+comments), /31 (+comments), /121, /81, /57, PR /134
- https://api.github.com/search/issues?q=repo:LedgerHQ/app-openpgp+windows

SSH agent (deprecated)
- https://github.com/LedgerHQ/app-ssh-agent
- https://github.com/romanz/trezor-agent
- https://pypi.org/pypi/ledger-agent/json
- https://raw.githubusercontent.com/romanz/trezor-agent/master/README-Windows.md (404)

FIDO / WebAuthn tooling and platform
- https://github.com/Yubico/python-fido2
- https://raw.githubusercontent.com/Yubico/python-fido2/main/examples/hmac_secret.py
- https://raw.githubusercontent.com/Yubico/python-fido2/main/examples/credential.py
- https://raw.githubusercontent.com/Yubico/libfido2/main/README.adoc
- https://developers.yubico.com/libfido2/Manuals/fido2-assert.html
- https://simplewebauthn.dev/docs/packages/server
- https://developer.mozilla.org/en-US/docs/Web/API/PublicKeyCredentialRequestOptions
- https://developer.mozilla.org/en-US/docs/Web/API/AuthenticatorAssertionResponse/signature
- https://www.w3.org/TR/webauthn-3/ (§7.1 read; §13.4.3 not reached)
- https://learn.microsoft.com/en-us/windows/security/identity-protection/passkeys/
- https://learn.microsoft.com/en-us/entra/identity/authentication/concept-fido2-hardware-vendor
- https://www.corbado.com/blog/passkeys-prf-webauthn
- https://chromium.googlesource.com/chromium/src/+/main/content/browser/webauth/origins.md (via search summary)
- https://github.com/PowerShell/openssh-portable/pull/541
- https://github.com/PowerShell/Win32-OpenSSH/issues/2040
- https://github.com/solokeys/solo2/discussions/108 (via search summary)
- https://github.com/tavrez/openssh-sk-winhello (via search summary)

Search queries run (WebSearch): Ledger Security Key Windows Hello / resident keys; Flex NFC Security Key; OpenPGP Windows gpg4win; webauthn.dll admin requirement; Win32-OpenSSH sk support; Git for Windows ed25519-sk; SSH/PGP Agent app deprecation; PRF Windows support; WebAuthn localhost RP ID; site:ledger.com Security Key.
