# Ledger N3XT Hackathon @ OP3N 2026: tap-to-pay with a Ledger

Two projects share this repo. Both make a Ledger something you pay with by tapping. Both have the Ledger itself sign a USDC `transferWithAuthorization` (EIP-3009) after showing the payment on its screen.

| | **TapCash** | **ledger-cash** |
|---|---|---|
| Tap | Ledger Flex ↔ iPhone (Safari WebAuthn over NFC) | Ledger ↔ Ledger (Flex in NFC reader mode ↔ Ledger or Android in card emulation) |
| Status | **Works on real hardware**; live page | Runs end to end in emulation; hardware gates pending |
| Settles | Immediately, from the iPhone page (Base Sepolia) | Later, by anyone: offline at tap time (anvil, Base Sepolia or Ethereum Sepolia) |
| Code | [`mvp/tapcash/`](mvp/tapcash/) | [`mvp/ledger-cash/`](mvp/ledger-cash/) |

## TapCash: your Ledger as a tap-to-pay wallet

Tap a Ledger Flex to an iPhone, approve on the Flex screen, tap again, and USDC moves on Base Sepolia.
- The receiver needs no app: Safari is enough.
- The payer needs no ETH for gas.
- The key never leaves the secure element, and the Flex shows exactly what it signs.

**Works on real hardware.** Live page: https://tapcash-ruby.vercel.app

### How it works

1. The iPhone page asks for a payment by tapping the Flex. The request travels over NFC through Safari's security-key support (WebAuthn), so no iOS app or paid Apple account is needed.
2. The Flex shows "Send payment? 5 USDC on Base Sepolia to 0x…".
3. On Approve, the Flex itself signs a USDC `transferWithAuthorization` (EIP-3009).
4. On the second tap, the page checks the signature and submits it, paying the gas.

Details, wire format, commands and limits: [`mvp/tapcash/README.md`](mvp/tapcash/README.md).

| Path | What |
| --- | --- |
| `mvp/tapcash/flex-app/` | Ledger Flex app (C, Ledger secure SDK) |
| `mvp/tapcash/web/` | The iPhone page (static, no build) |
| `mvp/tapcash/test.mjs` | End-to-end check on Speculos, including an on-chain simulation |

## ledger-cash: tap-to-pay between two Ledgers

A Ledger Flex becomes a wallet you pay with by tapping it against another Ledger. Setup and payment:

1. **Load:** the owner loads a USDC balance onto the device. The device caps spending at that loaded amount; it does not escrow it.
2. **Read the request:** the payer's Flex runs in NFC **reader** mode and reads the payee's signed payment request.
3. **Review:** it shows "Pay 5 USDC / To 0x… / For coffee" on its Secure Screen.
4. **Sign:** on approval, it signs a USDC `TransferWithAuthorization` (EIP-3009) and hands it back over the same tap.
5. **Settle later:** the payee holds a **signed IOU** that anyone can settle on-chain later. Both devices can be offline at tap time ("staged offline").

On the merchant side, an **AI till agent** turns a typed order into a priced request that the merchant approves on their own Ledger. It then verifies the IOUs, pre-checks payers' on-chain balances, and settles them.

**Who decides what.**
- **The agent**, on each run and without human input: understands the order, prices it in code, drafts the request, reads and verifies IOUs, pre-checks solvency, settles, keeps the books.
- **The humans, on hardware:** the merchant approves every request on their Ledger; the payer approves every payment on their Secure Screen.
- The agent holds no key that can sign a payment.

```bash
cd mvp/ledger-cash
python -u demo.py                # two emulated Ledger Flex devices tap, pay, settle on anvil -> ALL PASS
python -u agent/agent_demo.py    # the AI till agent end to end -> ALL PASS
python live_demo.py up --sepolia && python live_demo.py serve   # hands-on demo, settles on Ethereum Sepolia
```

Status (honest):
- **Emulation only so far.** It runs end to end in emulation: we patched Speculos to emulate the NFC reader mode. The Nano S Plus build and the Android payee also pass in emulation.
- **What hardware has and hasn't shown.**
  - TapCash shows a sideloaded `ENABLE_NFC` app works in card emulation on a retail Flex.
  - Reader mode on hardware is still untested: [HARDWARE.md](mvp/ledger-cash/HARDWARE.md).
- **The payee holds an IOU, not money.** Attested IOUs (BOLOS endorsement) were built, then forged by us, and are reported as a negative result.
- Details: [mvp/ledger-cash/README.md](mvp/ledger-cash/README.md).

## Repository map

| Path | What |
|---|---|
| [mvp/tapcash/](mvp/tapcash/) | TapCash: Flex app + iPhone page + Speculos E2E test |
| [mvp/ledger-cash/](mvp/ledger-cash/) | ledger-cash: device app, Speculos NFC reader patch and relay, settlement, demos, AI till agent, hardware checklists, video |
| [mvp/android/](mvp/android/) | Android payee app (HCE), plus a bridge that makes a phone the NFC antenna for a USB Nano S Plus (APK built in GitHub Actions) |
| [mvp/tangem/](mvp/tangem/) | Tangem card protocol module and mock card (not wired in; licence question open) |
| [mvp/nfc-probe/](mvp/nfc-probe/) | Compile gate for the Flex NFC reader API |
| [PITCH.md](PITCH.md) | Talk track, slide outline, demo plan, jury Q&A, submission drafts |
| [DX-FEEDBACK.md](DX-FEEDBACK.md) | The required developer-experience write-up |
| [HACKATHON.md](HACKATHON.md) | The brief, rubric and submission steps |
| [WORKLOG.md](WORKLOG.md) | Chronological record of the work |
| [research/](research/) | Sourced notes: NFC reader mode, USDC/EIP-3009 on Ledger, source audit, Vanadium, Tangem protocol, prior art, and the wider Ledger stack |
| [prior-art/industry/](prior-art/industry/) | Source texts behind the prior-art note |
| [spikes/](spikes/), [proto/](proto/) | Early hardware-free feasibility tests and an approval-core prototype |

The ideation ranking that preceded the build is kept at the git tag `archive/exploration-2026-10-11` (`IDEAS.md`).

**Pre-existing code:** none of ours existed before Oct 7, 2026. The device apps are built on LedgerHQ's open-source `app-boilerplate` and the Ledger secure SDK. Third-party packages are listed in each component's README.
