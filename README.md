# Ledger N3XT Hackathon @ OP3N 2026 — exploration repo

Prep work for the 1-week remote build (deadline Tue 2026-10-13 23:59 CEST, finals Fri 2026-10-16 at Ledger HQ Paris). Hardware on hand: Ledger Nano S Plus, Ledger Flex. Host: Windows 11.

| File / dir | What |
| --- | --- |
| `HACKATHON.md` | The brief: challenge, tools, rubric, jury, dates, submission steps. |
| `IDEAS.md` | 16 candidate projects (+ I17 from the second-opinion review), scored against the rubric with feasibility and originality refutations; honest verdicts on the two starter ideas; top-5 deep dives with day-by-day plans; Day-1 hardware questions. Start here. |
| `research/` | 21 deep-read notes on the Ledger AI stack, DMK, Key Ring, Agent Intent, clear signing, device apps, NFC/BLE, FIDO/OpenPGP, prior art, jury. Facts marked VERIFIED vs INFERRED with sources. |
| `spikes/` | Hardware-free feasibility spikes, each with a README of exact commands and output: `speculos-dmk-sign` (DMK → emulated Flex/Nano S Plus EIP-191 + EIP-712 signing, auto-approved, verified), `node-hid-windows` (DMK USB path loads on Node 24, scripts ready for a device), `wallet-cli-windows` (Ledger CLI runs natively), `host-capabilities` (no IR camera; webcam, BLE, GPU inventory), `ledgerblue-and-app-toolchain` (custom Rust device app builds for both devices and runs in Speculos; sideload script ready). |
| `proto/` | Working prototype of the shared approval core: `ledgerd` (owns the device via DMK, HTTP `/approve` → EIP-191 on the Secure Screen), a Claude Code PreToolUse hook (`ledger-sudo`), `approve.mjs` CLI, hash-chained log + signed checkpoint, `verify.mjs`. `npm test` runs end to end on Speculos with no hardware. Adversarially reviewed; honest limits in its README. |
| `mvp/tapcash/` | **TapCash, working on hardware:** tap a Ledger Flex to an iPhone, approve, and USDC moves on Base Sepolia. Custom Flex app (U2F over NFC, signs EIP-3009) + a Safari page (no iOS app or paid Apple account). Live at https://tapcash-ruby.vercel.app. `node test.mjs` runs end to end on Speculos. |
| `DX-FEEDBACK.md` | The mandatory developer-experience write-up, built from real reproduction (10 sections). |
| `WORKLOG.md` | Chronological record of everything done, with the headline findings. |

Nothing here has touched a real device yet. `IDEAS.md` §6 lists the Day-1 hardware questions that gate every top pick.
