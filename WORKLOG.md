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
