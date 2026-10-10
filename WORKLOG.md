# Worklog

Running record of autonomous exploration for the N3XT hackathon. Newest at bottom.

## 2026-10-10 00:40 — kickoff

- Read hackathon brief (Google Doc "Hackathon Brief" tab) → `HACKATHON.md`.
- Hardware on hand: Ledger Nano S Plus, Ledger Flex. Host: Windows 11.
- Starter ideas from Sahas:
  1. Voice agent ("Siri for your wallet") — speak a transaction, face scan to authorise, Ledger signs.
  2. Ledger-to-Ledger NFC payments — tap one Ledger on another to send; receive on the other, like a physical wallet.
- Mandate: explore widely, not only these two. ~8 h autonomous budget. Keep records.
- Plan: (1) research sweep over the Ledger AI stack, DMK, device capabilities, prior art → `research/`; (2) idea generation + scoring against rubric + adversarial feasibility checks → `IDEAS.md`; (3) feasibility spikes on top candidates (install Ledger CLI, DMK, detect devices) → `spikes/`; (4) recommendation.

## 2026-10-10 01:30 — research sweep complete

- Workflow `ledger-research-sweep`: 13 topic readers + completeness critic + 8 gap-fill readers (22 agents, ~51 min). Output: 21 notes in `research/` (~100k words). Each note marks VERIFIED vs INFERRED and cites sources.
- Host check: Node 24.2, Python 3.12, cargo 1.98, Docker Desktop 29.8, WSL2, gpg 2.4.9. Realtek Bluetooth adapter present. No NFC reader on the PC. Neither Ledger plugged in at time of check.
- Pulled `ghcr.io/ledgerhq/speculos:latest` for hardware-free testing.
- DMK npm packages republished 2026-10-10 (device-management-kit 1.11.0, signer-kit-ethereum 1.18.1, transport node-hid 1.0.1, web-hid 1.2.4, web-ble 1.3.2, speculos 1.2.1).

### Headline findings

1. **Starter idea 2 (Ledger→Ledger NFC) is not buildable with our hardware.** Nano S Plus has no NFC radio. Only the Flex has NFC, and no Ledger SDK (DMK, ledgerjs, wallet-cli) exposes an NFC transport. The C secure SDK has `ENABLE_NFC` (card emulation, used by Security Key app) and an undocumented `ENABLE_NFC_READER`; Flex↔Flex would need two Flex units plus a custom sideloaded C app. Honest reframe: Flex as NFC card tapped by an Android phone (card-emulation mode), or drop NFC.
2. **Starter idea 1 (voice + face + Ledger) has direct prior art**: ITHACA took 3rd in ETHOnline 2026 "AI Agents x Ledger" with Gemini Live voice + Flex DMK + a cosmetic WebAuthn "Face ID". Ledger CHAO Ian Rogers (juror) defines Proof of Human as hardware attestation, and Ledger Academy calls biometrics deepfake-able software. Face as the authority works against the jury. Reframe: "voice drafts, Ledger decides" — put the spoken intent itself on the Secure Screen (EIP-191 personal_sign or clear-signed ETH/CAL-listed USDC transfer); face at most selects whose policy loads.
3. **Clear signing without a partner originToken**: native ETH and CAL-listed ERC-20 transfers (incl. Sepolia / Base Sepolia tUSDC) clear-sign on both devices. Anything via CAL `/dapps` (ERC-7730 calldata, EIP-712 labels, Transaction Check) is 403 without a token. EIP-191 `signMessage` shows full ASCII text on both devices with no CAL at all.
4. **Key Ring** = `wallet-cli ring`; `init` needs USB device + Ledger Sync app; encrypt/decrypt need network to `trustchain.api.live.ledger.com` + OS keychain, no device. Native windows-x64 binary exists (docs say WSL). Ring lifecycle (members/add/remove/rotate/backup) is missing from the CLI — gap.
5. **Agent Intent beta** (`wallet-cli agent-intent`, released 2026-10-05): zero hackathon projects use it; Ethereum mainnet real funds only; works natively on Windows via Credential Manager.
6. **White space**: non-finance (<15% of prior entries), Security Key FIDO2 / OpenPGP as agent primitives, Key Ring lifecycle tooling, headless enrolment, "delegating proof-of-humanity to an agent with revocation" (open question Ledger itself raised), Windows-native DX, custom Rust "attestation signer" device app (sideloadable on both devices without approval).
7. **Jury line**: "Agents propose. Humans approve. Hardware enforces." Rogers/Mathias already built an x402 + intent-queue demo (Feb 2026) — do not rebuild an intent queue. Circle juror wants USDC moving (Arc testnet 5042002 works keyless via Circle facilitator). Venice juror: private inference, DX craft.

## 2026-10-10 02:45 — spikes done (hardware-free)

Workflow `ledger-spikes`, 5 agents, all in `spikes/<name>/README.md`:

- **speculos-dmk-sign: PASS.** `npm run speculos:flex && npm run demo` → DMK 1.11.0 + speculos transport + signer-kit-ethereum 1.18.1 against app-ethereum on emulated Flex and Nano S Plus: `getAddress` → `signMessage` (EIP-191 "Approve: pay 12 USDC to Alice for pizza. nonce 42") → `signTypedData` (EIP-712 Payment struct); auto-approve via Speculos REST `/events` + `/finger` / `/button`; viem `recoverMessageAddress` / `recoverTypedDataAddress` match on both. Screenshots in `screenshots/`. EIP-191 renders in full on both devices with no settings and no CAL. EIP-712: Flex shows every field (after "Blind signing ahead"); Nano S Plus shows only domain + hash unless "Raw messages" is on. This is the core "human reads the agent's intent on the Secure Screen" primitive, proven without hardware and usable in CI.
- **node-hid-windows: PASS.** DMK + node-hid transport install on Node 24 / Windows with prebuilds, no compiler. `discover.mjs` runs clean with no device; `connect-and-get-address.mjs` ready. Gotcha: `@ledgerhq/*` ESM builds break plain Node (`ERR_UNSUPPORTED_DIR_IMPORT`) → use `createRequire` + CJS.
- **wallet-cli-windows: PARTIAL (no device).** `@ledgerhq/wallet-cli@2.9.0` runs natively on Windows (Bun exe, 108 MB). All non-device commands fine. `ring` has only init/encrypt/decrypt/keys/destroy. No-device wait is a hard 60 s regardless of `--device-timeout`. `device-smoke.ps1` ready.
- **host-capabilities: PASS.** No Windows Hello face/IR camera (PIN only) → WebAuthn "face gate" would be a PIN prompt on this laptop. RGB webcam + mic present → webcam face ID via `@vladmandic/human` viable as a *profile selector*. Chrome 153/Edge 154, no policies; Web Bluetooth flags off (need `#enable-web-bluetooth-new-permissions-backend`, optionally `#enable-web-bluetooth-confirm-pairing-support`). RTX 4060, CUDA, torch, openai-agents installed; `faster-whisper-small.en` cached. No Ledger ever enumerated on this PC.
- **ledgerblue-and-app-toolchain: PARTIAL.** `ledgerblue 0.1.58` + `ledgerwallet 0.10.0` install on Windows with wheels only; `ledgerctl` works. `app-boilerplate-rust` cloned, exact Docker build + `ledgerblue.runScript --elfFile ... --apdu --scp` load commands and file pointers for an "Attestation Signer" fork recorded in README. Dev-tools image not pulled (multi-GB).
- `DX-FEEDBACK.md` started from all of the above (10 sections).

## 2026-10-10 03:00 — ideation panel complete → `IDEAS.md`

- Workflow `ledger-ideation-panel`: 10 lens generators (voice-strongest, nfc-strongest, non-finance, key-ring-headless, fido-pgp, custom-device-app, circle-venice, agent-intent-policies, human-agency-delegation, wildcard) → merger (16 candidates I01–I16) → per candidate: rubric scorer + feasibility refuter + originality refuter (48 judges) → synthesizer. 60 agents; hit a usage-limit pause mid-run, resumed from cache.
- Result ranking (synthesis order, not raw score): 1 I11 ledger-sudo (75.7) · 2 I14 Consent Receipts (71.9) · 3 I06 SE-counter Receipt (74.2, gated on sideload) · 4 I10 ringctl (75.0) · 5 I01 Echo = honest voice idea (67.7). Starter idea 2 survives only as I02 Tap-to-Receive (Flex Security Key NFC tap on a phone) or I03 custom NFC C app (78.65 on paper, refuted on feasibility).
- Recommended stack: I11 core on the stock Ethereum app (EIP-191) with I06 as the Sunday-noon sideload upgrade; I14 as the alternative if the pitch should be about a patient instead of a developer.

## 2026-10-10 03:40 — second opinion + build image

- Codex (read-only) reviewed IDEAS.md against research/ and spikes/. Accepted: calendar was wrong (Oct 10 is Saturday; Oct 12–13 are mentor days); hook timeouts do not block by default so the hook cannot be the enforcement point; I06 over-ranked; I15 under-ranked; new candidate I17 Release Seal. Design consequence: the daemon must hold the privileged credential and act only on a valid device signature (nonce + expiry + artifact digest). Recorded as IDEAS.md §7; dates relabelled.
- Pulled `ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest`; building unmodified `app-boilerplate-rust` for flex + nanosplus and running it in Speculos (agent in progress).
- Prototype of the shared approval core (`proto/`: ledgerd + Claude Code hook + verifier on Speculos) in progress; its review phase will be re-run against the §7 punctures.

## 2026-10-10 04:00 — custom device app builds and runs (emulator)

- Unmodified `app-boilerplate-rust` v1.9.1 built in `ledger-app-dev-tools` for flex (35 s, 270 KB ELF) and nanosplus (29 s, 191 KB ELF), no fixes needed. Command needs `MSYS_NO_PATHCONV=1` under Git Bash.
- Speculos flex: GET_VERSION → `0109019000`; GET_APP_NAME → "app-boilerplate-rust"; hand-driven SIGN_TX approved via `/finger` → DER signature, SW 9000. Review screen renders NBGL name/value fields ("Amount / CRAB 777", "Destination / 0xDE0B…"). Repo's ragger tests: 5 passed headless inside the image.
- API_LEVEL 27 (`ledger_device_sdk 1.37.1`, `ledger_secure_sdk_sys 1.16.4`, nightly-2025-12-05). Day-1 check against device OS via `ledgerctl info`; 0x511F = mismatch.
- Sideload command ready: `spikes/ledgerblue-and-app-toolchain/sideload.ps1 -Device flex -Load`.
- Consequence for IDEAS.md: I06's "Sunday-noon gate" is now only the real-device install question; toolchain + review UI + CI are proven.

## 2026-10-10 04:30 — prototype reviewed and fixed

- `proto/` built → adversarially reviewed (9 findings, 4 high) → fixed. `npm test` green on Speculos Flex and Nano S Plus from a clean state.
- High findings fixed: hook failed open on timeout/crash (now `onFailure: "block"`, try/catch → exit 2, 280 s abort); command text was truncated to 160 chars hiding the dangerous tail (now never truncated, refused if >400 or non-ASCII/multiline); hook and verifier trusted whatever answered on :7777 (now `LEDGER_ADDRESS` pinned out of band, signature verified in the hook); regex denylist beaten 37/41 (now an allowlist of read-only verbs per `;`/`&&`/`||`/`|` segment, everything else goes to the device).
- Medium fixed: chain bound into the signed text (`tier <prev8> <cmd> cwd:`), signed CHECKPOINT so truncation is detectable; 0x6980 retry after a bad byte; vacuous test assertion.
- Remaining honest limits (in proto/README): `node script` / `npm test` are tier0 and run whatever the repo contains; only Bash/PowerShell/Edit/Write hooked; no log lock; ledgerd unauthenticated locally; tier2 co-sign TODO; real HID untested.
- Collateral to flag: while killing a hung test the fix agent's PowerShell filter matched `@modelcontextprotocol/server-pdf` and killed ~14 node processes belonging to other Claude sessions' pdf MCP server.
- Added `README.md` index. Untracked `proto/log/session.jsonl`.

## 2026-10-10 05:00 — reconciled ranking after second opinion

- Designed + judged I15 Minute Book (73.9, feasibility passes, originality refuted on Ledger's own multisig CLI but survives on minutes-as-object and two-officer roles) and I17 Release Seal (76.95, both reviewers pass). IDEAS.md §1/§3/§4/§7 updated.
- Reconciled top 3: **I17 Release Seal** (= narrowed I11: ledgerd holds the publish credential, fires only on a Secure Screen signature over repo/version/destination/digest; ~130 lines on the reviewed proto core) · **I15 Minute Book** (two officers, two devices, countersigned minutes) · **I14 Consent Receipts** (patient story, lowest Day-1 risk, upgrade path = decrypt key moves into ledgerd).
- Elapsed autonomous time ≈ 4.5 h. Nothing has touched a real device. Day-1 gate list: IDEAS.md §6.

## 2026-10-10 — correction: docs-first research missed source-only capabilities

Sahas pointed at `LedgerHQ/ledger-secure-sdk/lib_nfc` and at "Ledger VMs". Both were missed because the first sweep read docs and READMEs, not source. Verified inline from source (gh api, master branch, 2026-10-10):

**NFC reader mode exists for third-party apps (Flex, Stax, Apex P).**
- `lib_nfc/src/nfc_ledger.c`: `NFC_LEDGER_start(mode)` powers the front end as card emulation (`SEPROXYHAL_TAG_NFC_POWER_ON_CE`, packets `OS_IO_PACKET_TYPE_NFC_APDU` 0x40) or reader (`SEPROXYHAL_TAG_NFC_POWER_ON_READER`, `OS_IO_PACKET_TYPE_NFC_APDU_RSP` 0x41). Refuses unless NFC is enabled in device settings (`OS_SETTING_FEATURES_NFC_ENABLED`).
- `Makefile.standard_app`: `ENABLE_NFC = 1` → `HAVE_NFC` + `lib_nfc` (+ `HAVE_APPLICATION_FLAG_BOLOS_SETTINGS`); `ENABLE_NFC_READER = 1` → `HAVE_NFC_READER`. Both only for `TARGET_STAX TARGET_FLEX TARGET_APEX_P`.
- App-level reader API in `io_legacy/include/os_io_legacy.h` + `src/os_io_legacy.c` (under `HAVE_NFC_READER`): `io_nfc_reader_start(nfc_evt_callback_t)`, `io_nfc_reader_send(cmd, len, nfc_resp_callback_t, timeout_ms)`, `io_nfc_reader_stop()`, `io_nfc_is_reader()`. Events `CARD_DETECTED` (with `card_info{tech NFC_A|NFC_B, nfcid[7]}`) and `CARD_REMOVED`; response callback `(error, timeout, data, len)`; 100 ms ticker timeouts; card removed mid-APDU → error callback. Routed from `io/src/os_io.c` (`SEPROXYHAL_TAG_NFC_EVENT`, `ITC_IO_NFC_START_READER` 0x12).
- `lib_nfc/include/nfc_ndef.h`: `os_parse_ndef`, `os_ndef_to_string`, `os_get_uri_header`; NDEF TEXT/URI records, text ≤ 215 chars.
- `lib_nfc/doc/mainpage.dox` still says "only available on Stax" and "TO BE COMPLETED" — stale.
- Every LedgerHQ app Makefile checked (boilerplate, ethereum, passwords, aleo, canton, exchange, hyperliquid, ledger-sync, nbgl-tests, nem, ont, openpgp, recovery-check, vechain, xrp) has `#ENABLE_NFC = 1` commented out; `app-security-key` has it on. GitHub code search finds no app using `io_nfc_reader_*` outside the SDK and Speculos's vendored copy.
- Speculos: `speculos/mcu/transport/nfc.py` handles host→device card-emulation APDUs (MTU 140; `NFC_APDU_EVENT` 0x1C, `NFC_EVENT` 0x1E); vendored `os_io.c` compiles `HAVE_NFC_READER`. Reader-mode emulation support: under investigation.
- Consequence: a single Flex running a custom C app can act as an NFC reader (cards, Type 4 tags, Android HCE phones, another NFC Ledger in card mode). The earlier verdict "Ledger-to-Ledger NFC impossible with our hardware" was wrong in its reasoning: the counterparty does not have to be a Ledger. Rust SDK still has no NFC (C app required).

**"Ledger VMs" = `LedgerHQ/vanadium`** (pushed 2026-10-09, 44★): "a Risc-V Virtual Machine that runs in an embedded Secure Element". V-Apps run inside the SE; the untrusted host stores encrypted, authenticated memory pages, so V-Apps are not limited by device memory. Written in Rust (`riscv32imac-unknown-none-elf`), tooling `cargo-vnd`, runs natively, on Speculos, or on device. README: "EXPERIMENTAL ... INSECURE AT THIS STAGE". Earlier answer that "Ledger VMs" meant Speculos was wrong.

**Also never looked at:** `applet-recovery-key` (JavaCard applet of the Ledger Recovery Key — a Ledger-made NFC smartcard counterparty), `ledger-button-public`, `ledger-wallet-dx`, `dale`, `nano-sniffer`, `ledgered`, `lumen` (design system), `ts-libs`, `npm-attest-lab`, `exchange-sdk`, `web3allowlist`. 230 active public LedgerHQ repos total.

**Running now:**
- Workflow `ledger-nfc-reader-deep-dive` → `research/nfc-reader-mode.md`, corrections in NFC notes, NFC ideas in IDEAS.md.
- Workflow `ledger-source-audit` (8 clusters: vanadium, secure-sdk, device-sdk-ts, ledger-live, apps catalog, tooling/misc, docs sitemap diff, products/APIs) → verify → re-ideate → `research/source-audit.md`, `research/vanadium.md`, IDEAS.md §8.

## 2026-10-10: NFC reader-mode deep dive (closes `ledger-nfc-reader-deep-dive`)

Read the SDK reader path end to end, plus Speculos, app-security-key, the Rust SDK, applet-recovery-key and the PR history, then had each headline claim checked by an adversarial pass. Full note with file:line and commit citations: `research/nfc-reader-mode.md`.

- **What the first sweep missed.** The reader API is maintained (PR #777 Dec 2024, fixes #987 and #1044, rename pending in #1243 whose author says no production app uses it). The trap that nobody had written down: its event and response dispatch lives only in the app-side IO stack (`io/src/os_io.c:187-531`, `#ifndef USE_OS_IO_STACK`), which `Makefile.standard_app:194-197` compiles out by default. A reader app needs `ENABLE_NFC=1 ENABLE_NFC_READER=1 DISABLE_OS_IO_STACK_USE=1`, the same own-stack flag `app-security-key` sets. Without it the build passes and no callback fires, so the planned plain-`ENABLE_NFC` Day-1 probe could have produced a false negative.
- **Limits found in source.** ISO 14443-A/B only; replies over 271 bytes silently become timeouts; `io_nfc_reader_start` returns true even when NFC is off in Settings; the CARD_DETECTED UID is probably stale; `io_nfc_is_reader` has no prototype. Stock Speculos exits on the reader start (tag 0x5D); an own-stack build + a small `seproxyhal.py` patch + `--transport NFC` should work (not run). Rust has no NFC; the app is C. Third-party CE already exists (structured-passkeys, 2026-10-04), so the first is reader mode, not NFC as such.
- **Files changed (not committed):** new `research/nfc-reader-mode.md`; dated correction blocks at the top of the NFC sections of `research/device-capabilities-nfc-ble.md` and `research/custom-device-apps-bolos-speculos.md`; IDEAS.md §2 NFC subsection rewritten, N1-N4 added to the §3 table as unscored, N1 deep dive at the end of §4.
- **Top NFC idea: N1 Tap the Request.** The Flex in reader mode reads a payee-signed USDC request from an Android HCE app or Type 4 tag, verifies it on the chip, shows it, and signs EIP-3009. Gate, Sunday 09:00: a sideloaded own-stack reader app gets CARD_DETECTED and an FCI ending 9000 from SELECT PPSE on a bank card. If it fails by noon, N2 (Flex as a Type 4 NDEF tag, card emulation only) on the same data format. N1 does not displace I17 as the main pick unless the team has an NFC Android phone and the gate passes.

## 2026-10-10 — Sahas's steer + NFC compile gate

- Steer from Sahas: Ledger-as-agent-permission is table stakes and unlikely to wow the judges. I03 (Flex as the card / NFC) is the headline to explore and expand; it should absorb all NFC ideas, including his Ledger-to-Ledger one. Sub-feature: stablecoins that behave like cash, moved between wallets by NFC tap. Start implementing MVPs. (I08 noted as encompassing I05 and the other agent-permission ideas.)
- Compile gate PASS (`mvp/nfc-probe/`): C app-boilerplate + `ENABLE_NFC=1 ENABLE_NFC_READER=1 DISABLE_OS_IO_STACK_USE=1` builds for Flex against SDK API_LEVEL 27; reader API and reader event routing are linked. First build without `DISABLE_OS_IO_STACK_USE` also linked but would never fire callbacks — caught by the NFC deep-dive.
- Counterparty options ranked for Sahas (pending his answer): 1 teammate's NFC Ledger, 2 Android HCE phone, 3 Tangem card (ISO-DEP, AID `A000000812010208`, `Read` 0xF2 / `Sign` 0xFB with access-code TLV — from tangem-sdk-android source), 4 NTAG 424 DNA Type 4 tags, 5 USB PC/SC reader, 6 blank JavaCard applet, 7 iPhone (reader only, needs Xcode), 8 emulator only.

## 2026-10-10 — hardware ownership corrected; build branch `ledger-cash`

- Correction: Sahas has a **Ledger Nano S Plus, Tangem cards and an iPhone**. The **Ledger Flex and an Android phone belong to his collaborator**. Earlier notes that say "our Flex" mean the collaborator's Flex. The two meet in Paris for the finals.
- Consequences: the only NFC Ledger is the collaborator's Flex. Live counterparties for the Flex: the collaborator's Android (HCE app) and Sahas's Tangem cards. A Ledger-to-Ledger tap needs either the Android acting as the NFC antenna for Sahas's Nano S Plus (phone bridges NFC ↔ USB OTG to the Nano) or two Speculos instances in emulation. Sahas cannot run Flex hardware gates alone; the collaborator runs them.
- All build work from here is on branch `ledger-cash` (Sahas's request).

## 2026-10-10: source audit of all Ledger capabilities (closes `ledger-source-audit`)

Sahas: "i don't just mean nfc research, i mean ledger research in general". Eight source-first audits (vanadium, secure-sdk, device-sdk-ts, ledger-live, apps catalog, tooling, docs diff, products/APIs), then synthesis, an adversarial verify pass on the 14 top findings, nine new ideas judged on the rubric. NFC skipped (separate workflow). No hardware touched, nothing committed.

- **Verified missed capabilities (13 survive):** BOLOS endorsement (app-attested signatures over the running app's code hash; retail provisioning untested), FIDO2 packed attestation from the retail Security Key app with Ledger roots in FIDO MDS3, Ethereum INS 0x18 tap-gated X25519 (>= 1.22.3, wipe on abort >= 1.22.4), Speculos test-vs-prod PKI root (`-p`), on-device Address Book (Eth 1.23.0 + OS 1.7.0 on Ledger's production catalog since 2026-10-07), NBGL keypad/warnings/QR (~213 B)/piezo, in-app PIN step-up, CAL gating interstitial (Nano S Plus not exempt), the real Multisig CLI package `@ledgerhq/multisig-cli` plus Ledger's public Safe tx-service, Flex lock-screen upload from any host, Manager API provider 4, Passwords HID keyboard, Vanadium. Refuted: app_storage surviving a ledgerblue reinstall and Speculos `--save-nvram` for Rust apps.
- **New ideas (weighted):** X32 Tap to Trust 76.55 (feasibility refuted), **X22 Sealed Records 75.3 (both pass)**, X23 74.5 (both refuted), X31 Echo Named 74.2 (both pass), X13 Mandate on the Glass 73.2 (both pass), X33 72.9, X12 72.6, X21 71.5, X11 Vanadium policy V-App 70.6.
- **Top 3 change:** I14 replaced by X22 (same patient story, decrypt key behind the device via the stock Ethereum app, no sideload). I17 and I15 unchanged. The agent-permission ranking is now explicitly the fallback set; ledger-cash stays the headline per Sahas's steer. IDEAS.md §8.4 lists what the audit adds to ledger-cash (custom app avoids gating, keypad/QR/piezo on the Flex till, OS 1.7.0 check, attested till on the Nano S Plus as a risky stretch).
- **Files:** new `research/source-audit.md`, new `research/vanadium.md`; a one-line "Correction (2026-10-10, source audit)" at the top of 14 research notes; IDEAS.md §1 (context note + X22 replaces I14) and new §8; this entry.
- **Things Sahas can run alone on the Nano S Plus:** the INS 0x18 round-trip for X22, the Vanadium sideload gate (`research/vanadium.md` §12), an endorsement provisioning probe (1-2 h cap, save the C0 response). Every Flex gate is the collaborator's.
- Also wrong in our tree, flagged only: `spikes/speculos-dmk-sign/README.md:25` ("Speculos has no persistent NVRAM") is wrong for C apps.
