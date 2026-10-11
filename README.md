# ledger-cash — tap-to-pay between two Ledgers

Built for the Ledger N3XT Hackathon @ OP3N 2026.

A Ledger Flex becomes a wallet you pay with by tapping it against another Ledger. The owner loads a USDC balance onto the device. The device caps spending at that loaded amount; it does not escrow it. To pay, the payer holds their Flex against the payee's Ledger. The payer's Flex reads the payee's signed payment request over NFC, shows "Pay 5 USDC / To 0x… / For coffee" on its Secure Screen, and on approval signs a USDC `TransferWithAuthorization` (EIP-3009). It hands that signature back over the same tap. The payee now holds a **signed IOU** that anyone can settle on-chain later. Both devices can be offline at tap time.

On the merchant side, an **AI till agent** turns a typed order ("two flat whites and a croissant") into a priced request that the merchant approves on their own Ledger. It then verifies the IOUs, pre-checks payers' on-chain balances, and settles them.

**Who decides what.** The agent, on each run and without human input: understands the order, prices it in code, drafts the request, reads and verifies IOUs, pre-checks solvency, settles, and keeps the books. The humans, on hardware: the merchant approves every request on their Ledger, and the payer approves every payment on their Secure Screen. The agent holds no key that can sign a payment.

## Try it (emulation, one command)

```bash
cd mvp/ledger-cash
python -u demo.py          # two emulated Ledger Flex devices tap, pay, settle on anvil -> ALL PASS
python -u agent/agent_demo.py   # the AI till agent end to end -> ALL PASS
```

Prerequisites, the build command and the recorded output are in [mvp/ledger-cash/README.md](mvp/ledger-cash/README.md). Backup video of the emulated run: [mvp/ledger-cash/video/ledger-cash-demo.mp4](mvp/ledger-cash/video/ledger-cash-demo.mp4).

## Status (honest)

- **Runs end to end in emulation:**
  - Two Speculos Flex instances, joined by an emulated NFC field. We patched Speculos to emulate the Ledger NFC reader mode.
  - Settlement on anvil, against a USDC look-alike token.
  - The Nano S Plus build (USB only) also passes in emulation.
  - The Android payee logic interoperates byte for byte.
- **Not yet run on a real device.** The open question for the whole project is whether a retail Flex lets a sideloaded app power its NFC reader. Step-by-step checklists: [mvp/ledger-cash/HARDWARE.md](mvp/ledger-cash/HARDWARE.md).
- **What the payee holds is an IOU, not money.** The cap is a device counter set by the owner. The payee cannot check offline that the payer can cover it. See the "Cash ladder" and "Honest limits" sections of the [ledger-cash README](mvp/ledger-cash/README.md).
- **Attested IOUs (rung v1) are a negative result, which we report.** We built them with BOLOS endorsement, then forged them ourselves through `sys_endorsement_key1_sign_without_code_hash`. Details are in the ledger-cash README and in [DX-FEEDBACK.md](DX-FEEDBACK.md) §11.

## Ledger primitives actually used

| Primitive | Where |
|---|---|
| Custom device app (C SDK, API level 27), Flex + Nano S Plus | `mvp/ledger-cash/app/` |
| NFC **reader** mode (`io_nfc_reader_*`, `ENABLE_NFC_READER`) on the payer | `cash.c` tap path |
| NFC **card emulation** (`ENABLE_NFC`) on the payee | `cash.c` NFC dispatch |
| Secure Screen review (NBGL), on-device keypad till | `cash.c` |
| Dedicated derivation path that no stock chain app can sign for (`m/44'/1279476051'/…`) | `app/Makefile`, `cash.c` |
| BOLOS endorsement (emulated; forgeable — reported) | `attest_demo.py` |
| Ledger Key Ring (`wallet-cli ring`) holding the agent's gas relayer key (pending hardware provisioning) | `mvp/ledger-cash/agent/keyring.md` |
| Speculos, with our NFC reader patch | `mvp/ledger-cash/speculos-nfc/` |

## Repository map

| Path | What |
|---|---|
| [mvp/ledger-cash/](mvp/ledger-cash/) | The project: device app, Speculos NFC patch and relay, settlement, demos, AI till agent, hardware checklists, video |
| [mvp/android/](mvp/android/) | Android payee app (HCE), plus a bridge mode that makes the phone the NFC antenna for a USB Nano S Plus. The APK is built in GitHub Actions |
| [mvp/tangem/](mvp/tangem/) | Tangem card protocol module and mock card (not wired into the app; licence question open) |
| [PITCH.md](PITCH.md) | Talk track, slide outline, demo plan, jury Q&A, submission drafts |
| [DX-FEEDBACK.md](DX-FEEDBACK.md) | The required developer-experience write-up |
| [HACKATHON.md](HACKATHON.md) | The brief |
| [WORKLOG.md](WORKLOG.md) | Chronological record of everything done |

## How we got here

Before building, we researched the Ledger developer surface:
- [research/](research/) holds 25 sourced notes. The NFC reader-mode note and the source audit live there; both came from reading source, not just docs.
- [IDEAS.md](IDEAS.md) ranked the ideas we considered.
- [spikes/](spikes/) holds early hardware-free feasibility tests.
- [proto/](proto/) is an earlier approval-core prototype.

The team chose ledger-cash over the agent-permission ideas, which are already common in Ledger hackathons. IDEAS.md §1 explains why.

**Pre-existing code:** none of ours existed before Oct 7, 2026. The device app is built on LedgerHQ's open-source `app-boilerplate` and the Ledger secure SDK. Third-party packages are listed in each component's README.
