# Source audit: Ledger capabilities the docs-first sweep missed

Written 2026-10-10 (Saturday) for N3XT @ OP3N 2026 (deadline Tue 2026-10-13 23:59 CEST). No hardware touched. Companion notes: `vanadium.md` (Vanadium deep dive) and `nfc-reader-mode.md` (NFC, covered by a separate workflow and skipped here).

Tags: **VERIFIED** = read in source (repo path:line, commit, npm tarball) or a live API response on 2026-10-10. **INFERRED** = a reading across sources, not run. `known` = whether `research/` or `IDEAS.md` already had it before this audit (no / partial / yes).

## 0. Why and how

The first sweep read docs and READMEs. It missed two things that only exist in source: the SDK's app-level NFC reader API (`io_nfc_reader_*`, `ENABLE_NFC_READER`) and `LedgerHQ/vanadium`, a RISC-V VM inside the secure element. This audit went back to source for all of Ledger, not only NFC.

Method:
1. Eight clusters, one auditor each: vanadium, secure-sdk, device-sdk-ts, ledger-live, apps-catalog, tooling-misc, docs-sitemap-diff, products-apis.
2. Source first: `gh api` (contents, `git/trees?recursive=1`, commits, PRs, releases, code search), shallow clones into the session scratchpad (read with grep/sed, never executed), npm tarballs unpacked, live GETs against Ledger's public APIs (Manager API, CAL, Safe tx-service, FIDO MDS3). Docs and web only to date or confirm.
3. Every capability was grepped against `research/` and `IDEAS.md` to set `known`.
4. A synthesis pass picked 14 missed capabilities (M01-M14) and ranked them by hackathon impact.
5. An adversarial verifier re-checked each of the 14 against source and gave a verdict plus `usable_by_tue` (yes / risky / no). One was refuted (M08). Where the verifier corrected a claim, §2 uses the corrected version.
6. Nine new ideas were designed on the survivors and judged on the rubric; see `IDEAS.md` §8.

Process notes: the tooling cluster ran `rm -rf scratchpad/src/*` mid-run and may have deleted other clusters' clones (findings unaffected). GitHub API rate limits cut the org-wide Address Book code search and some FORCE_PROVIDER tracing short.

## 1. Where sources disagreed, and which one wins

| Topic | Disagreement | Resolution |
|---|---|---|
| M03 Ethereum INS 0x18 confirm gate | docs cluster said 1.22.4+; synthesis said 1.22.3 | **1.22.3** has the gate (`cmd_perform_privacy_operation.c:54-55` at tag `stax_1.10.1_1.22.3_sdk_v26.6.1`); 1.22.1 and 1.22.2 do not (silent ECDH oracle). The secret is wiped on abort only from **1.22.4** (CHANGELOG). Gate on >= 1.22.4. |
| M05 Address Book on retail | device-sdk-ts cluster and the X32 judge said Eth 1.23.0 is unreleased (GitHub tags stop at 1.22.5, CHANGELOG `1.23.0 - xxxx-xx-xx`); ledger-live and apps clusters said it shipped | **Manager API wins**: provider 1 serves Ethereum 1.23.0 for OS 1.7.0 on Flex (versionId 76797) and Nano S Plus (76799), dateModified 2026-10-07, built from the private `app-ethereum-dev`. GitHub lags. Still INFERRED: that the shipped binary has `ENABLE_ADDRESS_BOOK` (develop `Makefile:185-186` does), and whether a given retail device is offered OS 1.7.0. |
| M09 gating on Nano S Plus | synthesis: "Nano S Plus exemption unknown" | **Not exempt.** `HAVE_GATING_SUPPORT` is unconditional (`makefile_conf/features.mk:51`), nanosp snapshots exist, DMK excludes only the original Nano S. Nano text is "A safer way exists:" plus the URL. |
| M09 testnets | synthesis: Base Sepolia / Arc testnet "have no Circle entries" | True for Circle, but not empty: Base Sepolia gates Morpho and Uniswap Permit2; Arc testnet gates Kiln and LI.FI. |
| M06 QR capacity | Ledger header says 1500 chars; synthesis said ~271 B | QR is drawn by closed OS firmware; the V4->V10 switch at 62 chars implies ECC-M, so **~213 B** (INFERRED). Text only, NUL-terminated. |
| M07 DelayLock | synthesis grouped it with locking the device | `BOLOS_UX_DELAY_LOCK` postpones auto-lock by 10 s. It is not a lock. |
| M11 image helpers | M11 verdict: helpers are browser-only | Only the canvas helpers (`processImage`, crop/resize, `loadImage`) need a browser; `encodeImageForDevice` and `getScreenSpecs` run in Node (X13 judge, `doc/CustomLockScreen.md`). |
| M13 Passwords | "the host never reads them" | Wrong: the focused app receives plaintext keystrokes. Correct claim: no host app can *pull* a password over APDU without a press on the device. |
| M14 Vanadium `known` | vanadium cluster said `no` | **partial**: WORKLOG logged it from the README earlier on 2026-10-10. |
| M01 endorsement details | synthesis: SCP needed, Owner cert optional | In the only public dashboard source (Nano X 2.2.3, 2023) `E0 C0` / `E0 C2` sit in the non-secure dispatcher (no SCP); the key is persisted only by C2, so an Owner cert is mandatory; `get_public_key_signature` returns the Owner cert, not a device signature. Stock `endorsementSetup.py` checks a Blue-era issuer key and will likely crash on Flex / Nano S Plus. |

## 2. Verified missed capabilities (M01-M14)

Ranked by the synthesis' hackathon impact. Verdict column is the adversarial verifier's.

| id | Capability | Verdict | Usable by Tue | Key source | One-line use |
|---|---|---|---|---|---|
| M01 | BOLOS endorsement: `sys_endorsement_key1_sign_data` signs SHA256(data \|\| running app code hash) with a slot-1 attestation key | holds, corrected | risky | ledger-secure-sdk@b03e7d6 `include/os_endorsement.h:57-207` (same names on `API_LEVEL_27`); speculos `src/emulate.c:914-950`, `src/bolos/endorsement.c:38` | A custom app proves *which build* signed. Works in Speculos today, but every app there gets one fixed fake code hash. |
| M02 | FIDO2 packed attestation from the retail Security Key app, roots in FIDO MDS3 | holds | yes | app-security-key@d6f57fb `make_credential_utils.c:229-258`, `aaguid.c`, `crypto_data.h:218,524`; MDS3 blob no 290 | Standards-only "made inside a genuine Ledger Flex / Nano S Plus" proof (batch-level). |
| M03 | Ethereum app INS 0x18: silent X25519 encryption key, tap-gated shared secret | holds | yes | app-ethereum tag `stax_1.10.1_1.22.3_sdk_v26.6.1` `cmd_perform_privacy_operation.c:8-9,42-125`; `ui_display_privacy.c:21-46` | Device-gated decryption on the stock app, no sideload. |
| M04 | Speculos trusts Ledger's TEST PKI root unless `-p/--pki-prod` | holds | yes | speculos `src/bolos/os_signature.c:5-27,167-182`, `os_pki.c:307`; device-sdk-ts `apps/sample/api/index.py:45-47,452-480` | Add `-p` to clear-sign with prod CAL; omit it to clear-sign your own descriptor with the release ELF. |
| M05 | On-device Address Book (device-HMAC contact names) | holds; one link INFERRED | yes | secure-sdk `app_features/address_book/doc/address_book_spec.md:92-111,313-326,618-660`; contacts-kit 0.5.0; signer-kit-eth 1.18.1 `SignerEthBuilder.d.ts:42`; Manager API | Device-verified "To: Alice". Matches only `tx.to` + chainId; a rejection is silent. |
| M06 | NBGL beyond reviews: Keypad, Keyboard (C only), Choice, streaming review, `nbgl_warning_t` threat screens, long-press, QR (Flex), piezo (Flex) | holds, corrected | yes | secure-sdk `API_LEVEL_27` `nbgl_use_case.h:274-326,635-645`, `nbgl_content.h:400`, `Makefile.standard_app:176-189`, `io/src/os_io_seph_cmd.c:248-287` | UX points; QR receipts on the Flex; native "Threat detected" screen. |
| M07 | In-app PIN step-up (`UxEvent::ValidatePIN`), `os_global_pin_check` + `sys_identity_log_out` with flag 0x40 | holds (API) | risky | rust-sdk `ledger_device_sdk/src/uxapp.rs`; secure-sdk `os_pin.h:19-38`, `os_identity.h:28-33`, `appflags.h:18` | Tiered approval. Untestable in Speculos (`os_ux` stub returns OK). Wrong PINs count against the real counter. |
| M08 | app_storage kept across updates + Speculos `--save-nvram` | **refuted** | risky | see §3 | |
| M09 | CAL gated-signing interstitial ("There is a safer way to sign") | holds, corrected | yes | app-ethereum `apdu_constants.h:39`, `cmd_get_gating.c:678-686`; context-module 2.6.0; live `/cal/v1/gated_dapps` | Fires only on blind/BASIC paths with a device-wide 1-in-10 counter; affects any stock-Eth EIP-3009 / Permit / CCTP demo on mainnet. |
| M10 | Ledger Multisig: `@ledgerhq/multisig-cli` 1.0.0 + public Safe tx-service / RPC | holds | yes | npm tarball `dist/index.mjs:9497-9531,190604,233235`; live `/v1/about/` (v5.42.1) | Real Ledger product for N-of-M; writes are signature-gated, not key-gated (empty POST gave 422, not 401). |
| M11 | Custom lock screen upload from any host (`@ledgerhq/dmk-ledger-wallet` 0.7.0, APDUs E0 60-66) | holds | yes | device-sdk-ts `packages/ledger-wallet/src/api/command/*`, `UploadCustomLockScreenDeviceAction.ts:243,335` | E Ink receipt that stays without power. Flex only, not in Speculos, closes any open app. |
| M12 | Manager API catalog + provider 4 | holds | risky | ledger-live `HttpManagerApiRepository.ts:215-245`, desktop `experimental.tsx:57`; live queries | Day-1 check without hardware; Ledger Sync >= 1.3.0 only on provider 4. |
| M13 | Passwords app types seed-derived passwords over USB HID keyboard | holds, corrected | yes | app-passwords@f481c6f `Makefile:54,63,80-81,113-119`, `password_typing.c:45-54,133-180`, `dispatcher.c:51-65` | "The agent cannot fetch the credential" beat, USB only. |
| M14 | Vanadium RISC-V VM in the SE | holds | risky | vanadium@342010bc; see `vanadium.md` | Run large Rust policy code in the SE; experimental, USB only, ~44x slower on device. |

### M01 BOLOS endorsement (risky)

VERIFIED: names and syscall IDs are the same on `API_LEVEL_27` (the team's v27.1.2 SDK) and master (`include/syscalls.h:153-159,225`). Functions: `get_code_hash`, `get_public_key(slot)`, `get_public_key_signature(slot)`, `key1_get_app_secret` (64 B), `key1_sign_data`, `key1_sign_without_code_hash`, `key2_derive_and_sign_data`, `get_metadata`. No LedgerHQ app calls them.

Speculos emulates five calls (get_pub_key, key1_sign_data, key1_sign_without_code_hash, get_code_hash, get_pub_key_sig), not app_secret, key2 or metadata. Keys come from env `USER_PRIVATE_KEY` / `ATTESTATION_PRIVATE_KEY`. `CODE_HASH` is one constant for every app (`endorsement.c:38`), so the emulator cannot show binary binding without a patch. Verifier: `ledgerblue.verifyEndorsement1` over sha256(message || codehash) (order from Speculos `endorsement.c:128-143`). `ledgerblue.hashApp` computes the expected hash independently; equality with the on-device value is untested.

Provisioning (VERIFIED for Nano X 2.2.3 only, `ledger-secure-os` dashboard, 2023): C0 generates a keypair and returns it signed by the factory Device key over sha256(0xFF||pub); C2 stores a host-supplied Owner cert (signature over 0xFE||pub) and persists the key. Non-secure dispatcher, no reset instruction, so one write per slot. Save the C0 response: it is the only link to genuine hardware. Rust: the bindgen of `os.h` includes it (`build.rs:543`); unsafe FFI should link (INFERRED). Unknown: retail Flex / NS+ 1.7.0 behaviour, factory-provisioned slots, whether a wipe clears them. Prior art: `rsksmart/rsk-powhsm` uses endorsement in production (original Nano S); Ledger's "attestation redux" blog post.

### M02 FIDO2 packed attestation (yes)

VERIFIED: always fmt `packed`, ES256, single-cert x5c (no `none` path in `src/`). Leaf subjects `CN=Ledger Flex FIDO 2 Attestation Batch 1` / `CN=Ledger Nano-SP FIDO 2 Attestation Batch 1`, issuer `CN=Ledger FIDO Attestation CA`, valid 2024-05-30 to 2034-05-28, with the AAGUID extension. MDS3 blob 290 (nextUpdate 2026-11-01): Flex `1d8cac46-47a1-3386-af50-e88ae46fe802`, Nano S Plus `58b44d0b-0a7c-f33a-fd48-f7153c871352`, `basic_full`, `NOT_FIDO_CERTIFIED`; `openssl verify` OK for both leaves. SimpleWebAuthn and python-fido2 do not reject NOT_FIDO_CERTIFIED by default.

Limits: the attestation key is a compile-time constant (`PROD_FIDO2_<MODEL>_PRIVATE_KEY`, `Makefile:53-85`) shared by every unit of a model, so this is batch-level and weaker than Rogers' per-chip genuine check. Self-built and Speculos builds use the public `TEST_FIDO2_*` cert and do not chain. Windows: USB HID only on both devices; Chrome may show a make/model consent prompt and return `none` if declined (INFERRED), so fail closed. It does not prove that any BIP32 key lives on the same unit. Prior art: Automata Proof of Machinehood (same mechanic with Yubico's root), Entra ID / Okta AAGUID allowlists.

### M03 Ethereum INS 0x18 (yes)

VERIFIED: P2=00 returns the Curve25519 key for the secp256k1 account at a BIP32 path (scalar byte-reversed and clamped); with P1=00 it is silent. P2=01 with a 32-byte peer key returns X25519(sk, peer) only with P1=01, after a "Provide derived shared secret" review that shows Address and Key (the secret hex) and no purpose text. Gate present at 1.22.3, 1.22.4, 1.22.5; absent at 1.22.1, 1.22.2. Dispatch has no `#ifdef` (`main.c:201-202`). The spec is `doc/ethapp.adoc:577-600` (stale on the gate), not `doc/apdu.md`. Host: `hw-app-eth` `getEIP1024SharedSecret(path, peer, true)` still works (the LedgerJS deprecation is about hashed EIP-712), or a raw APDU via DMK `sendApdu`.

INFERRED: byte order (send the peer key RFC 7748 little-endian, expect the secret reversed; run a round-trip test) and Speculos support (it has had `cx_x25519` since 2023, but Ledger's own ragger test skips the privacy op on Speculos). After release the secret is in host RAM.

### M04 Speculos PKI root (yes)

VERIFIED: `pki_prod = false` by default (`os_signature.c:27`); `-p` switches ROOT_CA_V3 to the production key (flag since b604b735, 2024-12-10; prod key updated 1471cc8e, 2025-02-24; the pulled image is from 2026-10-01). The test root's private key is public (`TEST_SIGNING_KEY_CERTIFICATE`, `index.py:47`; derivation checked). `https://app.devicesdk.ledger-test.com/api/certificates` returned 200 on 2026-10-10 with flex/nanosp certs whose signatures verify under the test root. The release app-ethereum checks the OS-loaded PKI cert before its compiled-in keys (`src/ledger_pki.c:5-61`), so **no test-key app build is needed** to clear-sign your own ERC-7730 descriptor in Speculos.

Limits: emulator only; ENS/metadata and tx-simulation keys are not re-signed; prod CAL needs `-p` and test-signed data needs no `-p`, never both in one session; `@ledgerhq/cal-interceptor` is private (vendor it). The 5720 -> 6a80 -> blind-sign chain comes from PR #1938 and was not re-run.

### M05 Address Book (yes, one INFERRED link)

VERIFIED: CLA B0 INS 10; P1 0x01 register identity, 0x02-0x04 edits, 0x11/0x12 Ledger account, 0x20/0x21 provide contact; P2 00/80 chunking. Register returns group_handle(64) + hmac_proof(32) + hmac_rest(32). The keys come from `sys_address_book_hmac`, which is OS-level: Speculos derives at a fixed path with no app id (`address_book.c:74-110`), and fix 647fe6aa removed the app-path restriction. The device stores nothing.

Host: `@ledgerhq/device-contacts-kit` 0.5.0 (`MIN_OS` 1.7.0 on Flex and NS+, `MIN_ETHEREUM_APP_VERSION` 1.23.0). `SignerEthBuilder.withAddressBook()` works with no originToken because the contact step runs before the CAL contexts. Matching is `tx.to` + chainId only, so ERC-20 recipients never get a name. A rejected contact logs "Contact rejected, signing without it" and signing continues. Speculos >= 0.27.1 has all three address-book commits (the pulled image does). Ledger's own fixture: `device-sdk-ts/apps/clear-signing-tester/ressources/contacts/sign-with-contact.json`. Ledger Wallet's Contacts UI is behind flags `lwdContacts` / `lwmContacts` (off by default).

### M06 NBGL (yes)

VERIFIED at `API_LEVEL_27`: Keypad (opt-in `ENABLE_NBGL_KEYPAD`, shuffled/hidden), Keyboard (C only; the Rust Flex defines omit `NBGL_KEYBOARD`), Choice / ChoiceWithDetails / AdvancedChoice, Spinner, Action, NavigableContent, ReviewStreaming*, AdvancedReview with `nbgl_warning_t` (W3C issue/risk/threat/no-threat, blind and gated warnings, custom `dAppProvider` / `reportProvider` / `providerMessage`), `INFO_LONG_PRESS`. QR via `nbgl_layoutAddQRCode`, Flex/Stax/Apex only (~213 B, see §1). Piezo: `HAVE_PIEZO_SOUND` on Flex/Stax; `io_seproxyhal_play_tune(TUNE_LOOK_AT_ME|SUCCESS|ERROR|...)` respects the user's sound settings, so it may be silent.

Nano S Plus: AdvancedReview, Spinner, Choice, Keypad, Keyboard in the step UI; no QR, no piezo, no long-press. Rust wraps warnings, keypad, streaming review, spinner, choice, and long-press plus `tune_id` in generic review; no standalone play_tune or keyboard wrapper.

### M07 PIN step-up (risky)

VERIFIED (API): (a) no flag: `UxEvent::ValidatePIN.request()` = WAKE_UP + `os_ux(BOLOS_UX_VALIDATE_PIN)` + block; `os_global_pin_is_validated()`. (b) flag 0x40 (`HAVE_APPLICATION_FLAG_GLOBAL_PIN=1`): `os_global_pin_check`, `os_global_pin_retries`, `sys_identity_log_out` (seed logout until the PIN is entered again). Ledger-signed app-passwords and app-exchange set the flag (no code use found).

Unknown: whether an unsigned sideload with 0x40 installs; whether ValidatePIN draws over a running app or simply returns OK when the PIN is already validated. Speculos: `sys_os_ux` returns OK immediately and the flag-gated calls are unimplemented. A passphrase-bound PIN switches identity. `DelayLock` only delays auto-lock.

### M09 CAL gating (yes)

VERIFIED: INS 0x38 `PROVIDE_GATING`, TLV signed under `CERTIFICATE_PUBLIC_KEY_USAGE_GATED_SIGNING`, matched on chain/address/selector or EIP-712 schema hash. One persistent `gating_counter` covers all gated contracts and the screen shows when `counter % 10 == 1`. Hooks exist only on blind calldata and EIP-712 BASIC paths (not ERC-7730 clear signing), and blind signing must already be on.

DMK always fetches `/gated_dapps` (open, 358 apps) and sends INS 0x38, token or not; the token's real effect is that `/dapps` returns 403 without it, which pushes Circle/USDC typed data onto the blind path. Base 8453 gated: CCTP TokenMessenger `779b432d` / `8e0250ee`, two USDC schema hashes (INFERRED EIP-3009), USDC permit; `transfer()` is not gated. Text and URL are Ledger-signed and fixed. **A custom app (for example `mvp/ledger-cash`) never shows it**; only flows through the stock Ethereum app do.

### M10 Ledger Multisig (yes)

VERIFIED: install with `npm i -g @ledgerhq/multisig-cli` (bin `ledger-multisig-cli`; `lem` is only the internal CLI_NAME). Ledger's docs name `les-multisig-cli`, which is 404, and the source repo is private. Commands: connect, config, safe scan|info|balances|nonce, tx list|show|propose|sign|execute (`execute` exists, the README omits it); no Safe creation, no delegate command. USB node-hid only. Bundled DMK origin token with `setDatasourceConfig({proxy:'safe'})`.

Endpoints `app.multisig.ledger.com/api/{safe-transaction-service|rpc}/<chainId>` for 1, 10, 137, 8453, 42161, 11155111. Reads are unauthenticated; writes need an owner or delegate signature (registering a delegate needs an owner EIP-712 signature). One config file, `~/.config/les-multisig/config.json`. Hidden `--seed` software signer.

### M11 Custom lock screen (yes, hardware only)

VERIFIED: npm `@ledgerhq/dmk-ledger-wallet` 0.7.0 (2026-10-06, Apache-2.0, peer DMK ^1.11). Actions Upload / Download / GetInfo / Remove; APDUs E0 60 create, 61 chunk, 62 commit, 63 delete, 64 size, 65 fetch, 66 hash; no secure channel, no backend. Flex 480x600 at 4 bpp; Nano S Plus unsupported. Upload exits to the dashboard (closing the open app), needs the device unlocked and two confirmations. The README usage example imports the wrong package name (`@ledgerhq/ledger-wallet`). Ledger's sample app drives it from a browser. Speculos has no lock-screen handling. Whether INS 66 answers while the device is locked: unknown.

### M12 Manager API (risky, only because the device OS is unknown)

VERIFIED 2026-10-10: `GET https://manager.api.live.ledger.com/api/v2/apps/by-target?provider=<1|4>&target_id=<858783748 Flex|856686596 NS+>&firmware_version_name=1.7.0`, no auth. Provider 1: 193 (Flex) / 232 (NS+) apps; Ledger Sync 1.2.2; OpenPGP 2.7.4, Passwords, Bitcoin Test and Bitcoin Test Legacy are `isDevTools=true`; Security Key is public. Provider 4: 51 / 53 apps, Ledger Sync 1.4.2 (private `app-ledger-sync-dev`), "Ledger Demo" 1.1.8 (app-nbgl-tests, Ledger-signed), no Bitcoin. Desktop: Settings > Experimental > "My Ledger provider" (`FORCE_PROVIDER`), with Ledger's warning that it may break install/uninstall. All numbers assume the device runs OS 1.7.0.

### M13 Passwords app (yes, USB only)

VERIFIED: path 5265220', variant pwmgr; v1.3.6 on Flex OS 1.7.0, v1.3.0 on NS+ OS 1.4.x/1.5.0; Developer mode only. Password = SHA256(nickname) -> BIP32 path -> derived key -> SHA256 -> CTR-DRBG; shown on screen or typed via `USBD_LEDGER_CLASS_HID_KBD` (QWERTY / QWERTY-Intl / AZERTY, optional Enter). Typing starts only from the device menu. APDUs are GET_APP_CONFIG 0x03 and the approval-gated DUMP/LOAD_METADATAS 0x04/0x05 (nicknames only). BLE and NFC are commented out. A custom C app gets the same with `DEFINES += HAVE_USB_HIDKBD`; the TESTING build stubs typing out, so Speculos probably cannot demo it. INFERRED: Windows `kbdhid.sys` delivers the keystrokes while Ledger Wallet or a DMK session holds the vendor interface.

### M14 Vanadium (risky)

See `vanadium.md`.

## 3. Refuted

**M08: "app_storage is kept across app updates" and "Speculos `--save-nvram` keeps our app's state".** Partly refuted on two counts.

- `app_storage` is real (rust-sdk `ledger_device_sdk/src/app_storage.rs:1-30`, crates.io `ledger_device_sdk` 1.41.0 published 2026-10-06; C `ENABLE_APP_STORAGE`, 480 B, CRC, unencrypted). But it lives in the app's own flash and survives an update only when the host runs the OS backup/restore APDUs E0 6A-6E (device-encrypted; restore needs consent and a PIN). Ledger Wallet and DMK `ledger-wallet` send them; **ledgerblue does not**, so a delete-then-install sideload wipes it. Untested whether those APDUs work for unsigned apps.
- Speculos `--load-nvram` / `--save-nvram` exits with "not yet implemented for Rust apps" for any ELF with a `.nvm_data` section (`speculos/main.py:124-129`), which every Rust app has. It works for C apps only. `--deterministic-rng` works for both.
- What stands: `nvm::AtomicStorage` (already used in our Rust boilerplate) is tear-safe and survives power cycles, not reinstalls.
- Also wrong in our tree: `spikes/speculos-dmk-sign/README.md:25` says "Speculos has no persistent NVRAM". That is wrong for C apps such as the Ethereum app (the flags exist since 0.17.0). It is a spike, not a research note, so it is only flagged here.

## 4. Per-cluster capability tables

One line per capability the auditors reported. Items covered by M01-M14 point there.

### 4.1 vanadium

All VERIFIED unless marked; detail in `vanadium.md`.

| Capability | Status | known | Use |
|---|---|---|---|
| Vanadium VM app (rv32imac in the SE); prebuilt `latest/vanadium_binaries.zip` at api_level 27 / SDK v27.1.2 | VERIFIED | partial | M14 |
| Sideload with `ledgerblue.runScript --targetId 0x33300004/0x33100004 --apdu --scp`; not Nano X | VERIFIED | partial | M14 |
| V-App registration: on-device review of name, version, 64-hex hash; 32-app registry | VERIFIED | no | trust ceremony |
| Host-paged memory: 256 B pages, Merkle proofs, AES-CTR, stack up to 128 MiB; access pattern leaks | VERIFIED | no | big code in the SE |
| V-App crypto: secp256k1 BIP32 at any path, ECDSA (DER, low-S, no v), BIP340, Keccak/SHA, bignum, RSA PKCS#1 v1.5, RNG; no P-256, no ed25519 | VERIFIED | no | EVM signing after policy logic |
| V-Apps receive the raw private key at any path (DERIVE_MASTER) | VERIFIED | no | test seed only |
| UX: pages (Flex) / steps (NS+), tag-value review, long-press, spinner; no custom icons, keyboard or QR | VERIFIED | no | |
| Storage: 4 x 32 B slots per V-App; re-registering the same name wipes them | VERIFIED | no | counters, policy hash |
| Async executor and spinner tasks | VERIFIED | no | |
| Rust client SDK over HID/TCP; `cargo vnd serve` length-prefixed TCP bridge | VERIFIED | no | Node agent talks to a V-App |
| Native dev mode and `cargo test` with auto-approve | VERIFIED | no | fast iteration |
| Speculos support (CI-tested) | VERIFIED | no | backup demo |
| ~44x slower on device than in Speculos | VERIFIED ratio | no | sizing |
| Example V-Apps: template, rps, bitcoin (miniscript, MuSig2, cleartext policies), sadik, async | VERIFIED | no | prior art |
| cargo-vnd builds on Windows | INFERRED | no | |
| app-streaming (Donjon 2023, archived) is the predecessor | VERIFIED | no | pitch framing |
| Very active, last merge 2026-10-09; pin the rev | VERIFIED | no | |

### 4.2 secure-sdk

| Capability | Status | known | Use / note |
|---|---|---|---|
| Endorsement / app attestation syscalls | VERIFIED API, INFERRED retail | no | M01 |
| Address Book feature and syscalls | VERIFIED | partial | M05 |
| App storage (`ENABLE_APP_STORAGE`, Rust `app_storage`) | VERIFIED | partial | M08 (refuted part) |
| PIN step-up, lock delay, identity logout | VERIFIED API | no | M07 |
| NBGL catalog (keypad, keyboard, choice, streaming, warnings, long-press, spinner) | VERIFIED | partial | M06 |
| On-device QR (Flex); ticker callbacks for multi-frame QR | VERIFIED; multi-frame INFERRED | partial | M06 |
| Native warning/threat screens with custom provider text | VERIFIED | no | M06 |
| USB HID keyboard class (`HAVE_USB_HIDKBD`) | VERIFIED | partial | M13 |
| USB CCID smartcard, CDC serial (`DEBUG_OVER_USB` / Rust `debug_over_usb`), WebUSB landing URL | VERIFIED; WebUSB Chrome behaviour INFERRED | partial | CDC printf for real-device debugging |
| Custom FIDO/U2F/CTAP transport (USB, BLE U2F profile) | VERIFIED; BLE-U2F use INFERRED | partial | too big for 3 days |
| lib_cxng: P-256, BIP340, ECDH, AES-GCM, ML-DSA/ML-KEM, BLS12-381 and VSS behind defines, SLIP-21, EIP-2333 | VERIFIED; BLS/VSS firmware availability INFERRED | partial | P-256 receipts, ECDH channel |
| `os_perso_get_master_key_identifier`: seed fingerprint without DERIVE_MASTER | VERIFIED | no | bind receipts to a seed |
| `os_flags`, `os_version`, `os_serial`, registry tag: device posture | VERIFIED | no | posture in receipts |
| `os_setting_get/set` (with BOLOS_SETTINGS flag) | VERIFIED API; allowed IDs INFERRED | partial | probe only |
| Piezo tunes on Flex | VERIFIED SDK; physical buzzer INFERRED | no | M06 |
| No real-time clock, only tickers | VERIFIED | partial | expiry must be host-asserted |
| Ledger PKI verification (`os_pki_*`, lib_tlv) | VERIFIED | partial | only to consume CAL data |
| `os_lib_call` / swap library mode | INFERRED for unsigned callers | no | risky probe |
| Full ENABLE_/DISABLE_ flag list; `LEDGER_SDK_EXTRA_DEFINES` for Rust | VERIFIED; Rust extra-defines compile INFERRED | partial | reference |
| `api_levels.json`: API 27 = flex_1.7.0 / nanos+_1.7.0 (nanos+_1.4.1 is API 24) | VERIFIED | partial | sideload gate |

### 4.3 device-sdk-ts

| Capability | Status | known | Use / note |
|---|---|---|---|
| Speculos `--pki-prod` trap | VERIFIED | no | M04 |
| Clear-sign your own ERC-7730 descriptor in Speculos via the test root | chain VERIFIED, end to end INFERRED | partial | M04 |
| CAL gated-signing interstitial | VERIFIED | partial | M09 |
| Ethereum INS 0x18 privacy operation (no DMK wrapper) | VERIFIED | no | M03 |
| Tron signer `getECDHSecret` (device-approved secp256k1 ECDH) | VERIFIED | no | typed alternative to M03, needs the Tron app |
| Custom lock screen actions | VERIFIED | no | M11 |
| `GetOsVersion` secure-element flags (PIN validated, onboarded, recovery, custom CA, endorsement slots) | VERIFIED | no | unauthenticated preflight posture |
| Secure-channel actions (genuine check, install) need no API key; `dmk.setWebSocketUrl` | VERIFIED | partial | genuine check at enrolment |
| Browser sideload over WebHID (TS port of ledgerblue SCP, in the sample app) | VERIFIED | no | fallback installer |
| Host onboarding `E0 D0` (destructive, dev only) | VERIFIED | no | avoid |
| device-contacts-kit and `withAddressBook` | VERIFIED | partial | M05 |
| App-storage backup/restore E0 6A-6F, master consent | VERIFIED | no | explains M08 |
| ListApps / GetDeviceMetadata without the secure channel | VERIFIED | partial | pre-demo check |
| Get/Set device name E0 D2 / D4 | INFERRED | no | name devices by role |
| npm `@develop` snapshot tags | VERIFIED | no | pin released versions |
| All in-repo signer kits are on npm (Tron is `device-signer-kit-tron`) | VERIFIED | partial | |
| Device Mock Server (offline genuine check, install) | VERIFIED | no | hardware-free paths |
| DMK DevTools live APDU inspector | VERIFIED | no | optional on-stage trace |

### 4.4 ledger-live

| Capability | Status | known | Use / note |
|---|---|---|---|
| On-device Contacts shipped to provider 1 on 2026-10-05/07 | VERIFIED (catalog) | partial | M05 |
| LKRP QR-code pairing (`createQRCodeHostInstance` / `createQRCodeCandidateInstance`, ECDH over `wss://<trustchain-api>/v1/qr`, digit code) | VERIFIED; use on app 17 INFERRED | no | device-less member enrolment UX |
| Ledger Sync (Cloud Sync) blob: accounts, names, contacts, recent addresses | VERIFIED; reading contacts from an agent INFERRED | partial | read-only; never push to slug `live` |
| Custom lock screen | VERIFIED | no | M11 |
| Monorepo map; libs moved to `LedgerHQ/ts-libs` and `coin-modules`; npm `@ledgerhq/live-common` and `cryptoassets` are stale | VERIFIED | partial | import only published, current packages |
| Manager API and live.ledger.tools (catalog matrix, browser APDU REPL) | VERIFIED | partial | M12 |
| wallet-cli 2.9 env vars; telemetry always on, no opt-out (`SEGMENT_WRITE_KEY` redirects it) | VERIFIED | partial | `DEBUG=wallet-cli`, `WALLET_CLI_NO_NUDGE=1` |
| Feature-flag registry: Contacts, Pay tab, gas sponsorship, stablecoin savings; zero code for x402, passkey, proof of human, MCP | VERIFIED | no | positioning |
| Ledger Wallet desktop copies process env into live-env (`MOCK`, `DISABLE_TRANSACTION_BROADCAST`, `PLATFORM_LOCAL_MANIFEST_JSON`) | VERIFIED code; packaged build INFERRED | no | sign-without-broadcast demos |
| wallet-cli APDU proxy (HTTP/WS on 8435, no auth), source-only | VERIFIED | no | pattern for LAN access to a USB-only Nano |

### 4.5 apps-catalog

| Capability | Status | known | Use / note |
|---|---|---|---|
| Ethereum EIP-1024 privacy op | VERIFIED | no | M03 |
| Passwords app | VERIFIED | partial | M13 |
| Manager catalog and provider 4 | VERIFIED | partial | M12 |
| NBGL Tests app ("Ledger Demo", provider 4): APDU-triggered screens including sound | VERIFIED | no | UX gallery |
| Flex piezo API | VERIFIED | no | M06 |
| Ethereum Address Book | INFERRED (binary) | partial | M05 |
| Bitcoin app: miniscript, MuSig2 (2.4.0), clear-text policy registration (2.5.0); BIP-322 on develop only | VERIFIED | partial | agent co-signer vault on testnet |
| Seed Tool (SSKR; BIP85 not implemented) | VERIFIED | no | narrative prop only |
| Recovery Check | VERIFIED | no | none |
| Ledger Sync `GET_SEED_ID` as seed identity plus app attestation; legacy path accepts a self-signed challenge | VERIFIED source; retail INFERRED | partial | "Sign in with Ledger" with an offline-verifiable attestation, Ledger Sync branded screen |
| Solana off-chain message signing | VERIFIED | partial | ed25519 consent signature |
| Cardano `GET_SERIAL` (7-byte serial, no prompt) and CIP-8 | VERIFIED | no | unauthenticated device id |
| Exchange app partner-signed protocol | VERIFIED | partial | no-go without Ledger onboarding |
| btcext boilerplate / Core app (custom Bitcoin review on top of the Bitcoin app) | VERIFIED | no | 2-day firmware path |
| OpenPGP, Passwords, testnet apps are Developer-mode only; Security Key is public | VERIFIED | partial | setup |
| ledger-app-database (CI metadata) | VERIFIED | no | only for store submission |
| Archived age, KeePass, Windows Hello apps | VERIFIED | no | reference only |
| Hyperliquid app | VERIFIED | partial | low |

### 4.6 tooling-misc

| Capability | Status | known | Use / note |
|---|---|---|---|
| Ledger Wallet Provider ships a built-in origin token and Ledger's demo identity (`dAppIdentifier 'ledger'`) | VERIFIED presence; third-party acceptance untested | no | ask mentors before relying on it |
| Wallet Provider `devConfig` stubs, mock transport, `environment: 'staging'` | VERIFIED | no | hardware-free UI walkthrough; no Speculos transport |
| Speculos `--deterministic-rng`, `--user-private-key`, `--attestation-key`, `--save/load-nvram` (C apps), `-t`, `-d`, `-l` | VERIFIED | partial | reproducible recordings |
| Speculos REST `/ticker/` pause/step, `/events?currentscreenonly=true`, automation port, button/finger ports (not deprecated) | VERIFIED | partial | clean screenshots, agent-driven emulator |
| Speculos "Driving Speculos from code or an agent" doc and quickstart | VERIFIED | partial | DX write-up |
| Speculos PKI root switch | VERIFIED | partial | M04 |
| Address Book in Speculos and the Ragger helper | VERIFIED | partial | M05 |
| Endorsement | INFERRED (retail) | no | M01 |
| `applet-recovery-key` JavaCard source is public (CLA 0x08, full protocol, Synacktiv audit) | VERIFIED | no | talking point; only pre-auth GET_STATUS / GET_CARD_CERTIFICATE reachable |
| `ledger-app-workflows`, including the Guideline Enforcer and a Claude security-review workflow | VERIFIED | no | green CI badge on a custom app |
| `ledger-app-ai-instructions` SECURITY.REVIEW.md skill | VERIFIED | partial | run locally, quote the result |
| VS Code extension (build, test, Enforcer Checks); never run Quick Device Setup | VERIFIED | partial | |
| Lumen design system (React / RN, Tailwind preset) | VERIFIED | partial | host UI that looks like Ledger Wallet |
| `dale` APDU log explainer (web, Pyodide) | VERIFIED | no | readable traces |
| `erc7730-analyzer` LLM descriptor auditor | VERIFIED | no | cite on our own descriptor |
| `internal-erc7730-registry` Cursor rules | VERIFIED | partial | descriptor generation prompts |
| `clear-signing-erc7730-builder` (self-hostable, Flex bezel previews) | VERIFIED | no | |
| sRFC 39 Meta Intents Extension (Solana intent reduction spec) | VERIFIED | no | Solana intent reducer |
| iframe-provider viem/wagmi templates with a local manifest | VERIFIED | partial | fastest "inside Ledger Wallet" demo |
| device-management-kit-ts-workshop (old pins) | VERIFIED | no | copy patterns |
| web3allowlist | VERIFIED | partial | low |
| Ledger-Donjon: age-plugin-ledger, cargo-checkct, public-findings | VERIFIED | partial | cargo-checkct for rigour |
| `ledger-secure-os` public dashboard source (2023, Nano X) | VERIFIED | no | APDU reference |
| embedded-application-tools (icon resize), ledgered, ledgercomm, nano-sniffer (Linux only) | VERIFIED | partial | icon polish |

### 4.7 docs-sitemap-diff

| Capability | Status | known | Use / note |
|---|---|---|---|
| Endorsement in docs ("Endorsement & application attestation") | VERIFIED docs | no | M01 |
| Speculos endorsement emulation | VERIFIED | no | M01 |
| `ledgerblue.endorsementSetup` provisioning | INFERRED (retail) | no | M01 |
| In-app PIN (`os_global_pin_check` + `nbgl_useCaseKeypad`) | VERIFIED API | no | M07 |
| Ethereum INS 0x18 | VERIFIED | no | M03 |
| On-device QR, NBGL use-case catalog, design guidelines ("Hold to sign" only for state or fund changes) | VERIFIED | partial | M06 |
| App permissions: path/curve allowlists (including bls12381g1), LIBRARY flag | VERIFIED | partial | own hardened path for an approval app |
| N_ NVRAM vars, 64-byte pages, wear | VERIFIED | partial | |
| Custom USB protocols / ECS event model | VERIFIED | partial | do not attempt |
| Native mobile DMK (Kotlin Multiplatform) 0.0.4 alpha | VERIFIED | no | skip |
| Travel Rule SIWX via Reown AppKit | VERIFIED | no | low |
| ExchangeSDK card/sell flows (partner-gated) | VERIFIED | no | blocked |
| Ethereum plugins need Ledger pre-approval | VERIFIED | no | use ERC-7730 instead |
| LedgerJS / hashed EIP-712 deprecation (Sep 2026) | VERIFIED | partial | guardrail |
| `llms-full.txt`, per-page `.md`, `changelog.json`; the sitemap is stale | VERIFIED | partial | use llms-full.txt for doc sweeps |
| Rogers' "Don't give the agent the keys" five-layer stack, `ai-agent@ledger.com` early access | VERIFIED | partial | pitch vocabulary |
| Donjon "Cerberus" six-agent security harness | VERIFIED | no | I17 pitch framing |
| DMK rollout: multi-signer, adopters including MoonPay Agents | VERIFIED | partial | I15 prior art |
| N3XT research papers (authorization boundaries, key lifecycle, "signed not sound") | VERIFIED | partial | cite as the problem statement |

### 4.8 products-apis

| Capability | Status | known | Use / note |
|---|---|---|---|
| FIDO2 packed attestation and MDS3 | VERIFIED | partial | M02 |
| Ledger Sync `GetSeedId` attestation with a public PROD pubkey (`app-ledger-sync/src/crypto_data.h`) | VERIFIED source; legacy path on retail INFERRED | partial | offline-verifiable "official Ledger Sync app on a real device" |
| BOLOS endorsement | INFERRED (retail) | no | M01 |
| Remote genuine check over `wss://scriptrunner.api.live.ledger.com/update/genuine`, no token | INFERRED (server relay) | partial | weak alone; pair with a key-bound proof |
| Ledger Multisig tx-service and RPC | VERIFIED reads | no | M10 |
| `@ledgerhq/multisig-cli` is the real `lem` | VERIFIED | partial | M10 |
| `@ledgerhq/ledger-enterprise-cli` 0.2.3 (needs a paid workspace) | VERIFIED | partial | prior art only |
| LKRP caller-chosen applicationId and a staging backend | INFERRED | partial | own key-ring namespace, untested |

## 5. Corrections to earlier notes

Each affected note now carries a one-line "Correction (2026-10-10, source audit)" pointer at the top. Line numbers are as of before those pointers were inserted (each note gained two lines at the top).

| Note | What was wrong | Correct |
|---|---|---|
| `custom-device-apps-bolos-speculos.md` §0.6/§4.2 (l.32, l.176) | pairs API_LEVEL 27 with `nanos+_1.4.1` | API 27 = flex_1.7.0 and nanos+_1.7.0; nanos+_1.4.1 is API 24 and gets 0x511F |
| same, §7 takeaway | a custom app adds only UI/NFC because personal_sign already attests messages | misses endorsement (M01): personal_sign cannot say which app binary signed |
| same, §1.3 | Rust feature list omits `debug_over_usb` | PRINTF over a USB CDC COM port on a real device |
| same, l.193 | Speculos `--automation` / `--button-port` deprecated | only `-u/--usb` is deprecated (`main.py:400-404,481-501`) |
| same, l.184-186, l.249-250 | Developer mode is a red herring; OpenPGP public; Bitcoin = BIP-137 only | Developer mode is needed for OpenPGP, Passwords and testnet apps; Bitcoin 2.5.x has miniscript, MuSig2, clear-text policies (BIP-322 on develop only) |
| `gap-windows-hid-coexistence-ledger-live.md` | HID_KBD, CCID, CDC rows INFERRED | VERIFIED: `HAVE_USB_HIDKBD` (`os_io_legacy.c:305`), `ENABLE_USB_CCID`, `DEBUG_OVER_USB` |
| `dmk-ts-signer.md` l.15/43, 32-33, 70, 108, 129, 185, 243 | signers "unverified on npm"; rn/mockserver versions unchecked; cannot fingerprint a device; ListApps grouped with secure channel; `withAddressBook?`; BLE id unverified; Speculos command lacks `-p` | all signers on npm (Tron = `device-signer-kit-tron`); rn-hid 1.0.4, rn-ble 1.3.2, mockserver 1.1.2; Cardano GET_SERIAL returns a serial (unauthenticated); only GenuineCheck / Install / ListInstalled / Uninstall use the WebSocket; `withAddressBook` exists (M05); id is `"WEB-BLE-RN-STYLE"`; add `-p` for prod CAL (M04) |
| `dmk-skills.md` l.120 | secure-channel host `wss://manager.live.ledger.com` | `wss://scriptrunner.api.live.ledger.com/update` + `/genuine`, `/install`, `/apps/list`; no API key |
| `clear-signing-erc7730.md` §3.3, l.129/136 | self-signed descriptors need a test-key app build; hosted backend `app.devicesdk.ledger.com`; contacts need "a recent app" | release ELF plus default Speculos accepts test-root certs (M04; end to end INFERRED); host is `app.devicesdk.ledger-test.com`; contacts need Eth >= 1.23.0 and OS >= 1.7.0 (M05) |
| `gap-clear-signing-without-origin-token.md` l.104, l.238 | `/gated_dapps` not probed | open, 358 entries; interstitial behaviour in M09 |
| `hardware-security-fido-pgp-ssh.md` l.219, l.347, §3-5 | MDS listing unknown, use `attestation:none`; tap-to-decrypt only via OpenPGP or Key Ring | Ledger AAGUIDs are in MDS3 (M02); Ethereum INS 0x18 gives a tap-gated X25519 secret (M03) |
| `ledger-cli-agent-stack.md` l.30, §8 items 8 and 12 | `les-multisig-cli` / `ledger-enterprise-cli` names; EXPLORER may retarget wallet-cli; analytics opt-out unknown | `@ledgerhq/multisig-cli` (bin `ledger-multisig-cli`), `@ledgerhq/ledger-enterprise-cli`; wallet-cli never copies env into live-env; no analytics opt-out |
| `jury-and-ledger-strategy.md` l.148 | all four Agent Stack blocks are open-source | the Enterprise and Multisig CLIs are bundled npm tarballs with private source |
| `gap-agent-intent-beta-onboarding.md` | Ledger Sync >= 1.3.0 installs automatically | provider 1 serves 1.2.2 on OS 1.7.0; 1.4.2 only on provider 4 (M12) |
| `key-ring.md` l.14, l.25 | no documented USB-less enrolment; LKRP lives in ledger-live `libs/` | LKRP QR-code pairing is the shipped device-less path; the package moved to `LedgerHQ/ts-libs` (commit 1117c9041) |
| `gap-key-ring-recovery-and-rotation-semantics.md` | m/99'/99' only as the auth identity | `GetSeedId` also returns an app attestation verifiable offline (public PROD key) |
| `wallet-provider-live-apis.md` l.48-51 | no demo key; useless without a key; no `environment` option | built-in fallback origin token; `devConfig.stub.dAppConfig`; `environment: 'staging'\|'production'` |
| `device-capabilities-nfc-ble.md` l.75, l.258 | Recovery Key source not found | the card applet is public at `LedgerHQ/applet-recovery-key` |
| `IDEAS.md` l.130 (I06 risk) | Rust storage API verified only by feature names | `app_storage.rs` is source-verified, but it does not survive a ledgerblue reinstall (§3) |
| `IDEAS.md` I14 and the §7 fix | the decrypt key needs a custom app | the stock Ethereum INS 0x18 already does it (M03) |
| Ledger's `lib_nbgl/include/nbgl_types.h:243` | V10 QR holds 1500 chars | ~213 B (§1) |

## 6. Open questions (hardware or mentors)

Who runs a check matters: per WORKLOG, Sahas owns the Nano S Plus, Tangem cards and an iPhone; the Flex and the Android phone are the collaborator's.

1. Which OS are the two units on? API 27 needs flex_1.7.0 / nanos+_1.7.0; Contacts needs 1.7.0 plus Eth 1.23.0. (Each owner, Sunday morning, Ledger Wallet > My Ledger.)
2. Does the shipped Ethereum 1.23.0 answer CLA B0 INS 10 P1 01 (6D00/6E00 means no Address Book)?
3. Endorsement: do retail OS 1.7.0 units accept `E0 C0 01` / `E0 C2`, or is slot 1 already set? Probe on the Nano S Plus only, after saving the C0 response; ask mentors which issuer key signs Flex / NS+ device certs.
4. Does `sys_endorsement_get_code_hash` on a sideloaded app equal `ledgerblue.hashApp`?
5. Does Chrome / `webauthn.dll` on Win11 pass the full x5c for `attestation:'direct'` on a Ledger key, or downgrade to `none`?
6. Byte order and Speculos support for Ethereum INS 0x18 (30-minute round-trip test); is the key MetaMask-compatible?
7. Does `withAddressBook` behave on hardware as it does in source with no originToken?
8. Does an unsigned sideload with flag 0x40 (GLOBAL_PIN) install? Does `ValidatePIN` draw a PIN pad over a running app?
9. Does custom-lock-screen INS 66 answer while the device is locked? Does upload from a non-Ledger-Wallet host work on current firmware?
10. Does the Nano S Plus show the gating interstitial for a gated contract (source says yes)?
11. Does Ledger's Multisig tx-service accept unauthenticated propose POSTs carrying valid owner signatures (an empty POST gave 422, not 401)?
12. Does Ledger Sync `GetSeedId` take the legacy path for a self-signed third-party challenge on retail?
13. Does the built-in Wallet Provider origin token work from a non-Ledger origin, and may we use it? (mentors)
14. Vanadium: does the prebuilt VM sideload on the Nano S Plus (Sahas can run this alone)? Does `cargo-vnd` build on Windows?
15. LKRP: do QR pairing and arbitrary applicationIds work on app 17 / staging?
