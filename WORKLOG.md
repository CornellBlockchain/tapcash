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
