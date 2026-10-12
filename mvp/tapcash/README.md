# TapCash: tap a Ledger Flex to an iPhone to pay USDC

Hold an iPhone near a Ledger Flex, approve on the Flex screen, tap again: USDC moves on Base Sepolia. The iPhone needs no app and no paid Apple account (just Safari), and the payer needs no ETH.

**Status: works on real hardware.** A real payment from the Flex to an iPhone settled on Base Sepolia, 2026-10-11. Live page: https://tapcash-ruby.vercel.app

## How it works

- **Transport: Safari WebAuthn over NFC.** Free Apple accounts can't use Core NFC, but Safari can talk to NFC security keys. TapCash answers the FIDO AID as a U2F authenticator:
  - The payment request rides in the credential ID (U2F key handle).
  - The signed result rides back in the signature field.
- **Two taps.**
  - Tap 1 delivers the request and the Flex shows "Send payment? 5 USDC on Base Sepolia to 0x…".
  - Tap 2, after Approve, returns the signature. Each approval yields exactly one signature.
- **Signing on the Flex.** `flex-app/src/app_main.c` builds the EIP-712 digest of USDC `transferWithAuthorization` (EIP-3009) itself and signs it with `m/44'/60'/0'/0/0`. It never signs a hash supplied by the page. The domain separator is pinned to USDC on Base Sepolia, so signatures can't be replayed on another chain.
- **iPhone side** (`web/`):
  - It is the receiver's wallet: a burner key kept in localStorage that also pays the gas.
  - It verifies the signature (recovers the signer and checks it is the Flex), normalises it to low-s, and submits `transferWithAuthorization`.

Wire format (shared by `app_main.c` and `web/tapcash.js`):
- **Request (key handle, 64 B):** `to(20) | value(8, micro-USDC) | validBefore(4) | nonce(32)`
- **Response:** `UP(1) | counter(4, last byte = v) | DER(r, s) | from(20)`

## Run it

All commands run from the repo root unless noted.

```sh
# Build (the SDK silently skips app sources outside a git repo, so mount the repo root)
docker run --rm -v "$PWD":/app -w /app/mvp/tapcash/flex-app ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest \
  bash -c 'git config --global --add safe.directory "*"; make BOLOS_SDK=$FLEX_SDK'

# End-to-end check: emulated Flex, both taps, page parsing, on-chain simulation (see header of test.mjs)
cd mvp/tapcash && npm i && node test.mjs

# Sideload (Flex on USB, unlocked, on the home screen, Ledger Wallet closed)
python3 -m venv /tmp/lv && /tmp/lv/bin/pip install ledgerblue
cd mvp/tapcash/flex-app && /tmp/lv/bin/python -m ledgerblue.runScript --scp --fileName build/flex/bin/app.apdu --elfFile build/flex/bin/app.elf

# Deploy the page (Vercel project "tapcash")
cd mvp/tapcash/web && npx vercel deploy --prod --yes
```

Before the first payment:
- Fund the Flex address with Base Sepolia USDC from faucet.circle.com.
- Send about 0.001 Base Sepolia ETH to the iPhone wallet shown on the page.

## Payment modes

- **Manual mode (two taps)** is the default. Every payment is reviewed on the Flex: tap, approve, tap again.
- **Budget mode (spending limits)** signs payments within your limits on one tap.
- **Card mode (one uncapped transaction)** signs the next payment, of any amount, on one tap, then turns off.

## Budget mode (spending limits)

Budget mode is optional, and off by default. With it off, the Flex is in manual mode.
- Turn it on with the "Budget mode" switch on the first Settings page (the gear on the home screen).
- After that, payments up to the per-payment limit are signed on the first tap, with no review. The second tap isn't needed, and the page needs no change.
- Budget mode stops when the total budget or the number of payments is used up, or when the app closes, since it lives only in the app's memory.
- The next three Settings pages set its limits:
  - per payment: 1, 5, 10 or 50 USDC (default 5);
  - total: 10, 20, 100 or 500 USDC (default 20);
  - number of payments: 1, 5, 10 or 25 (default 10).
- Bigger payments, or payments past a limit, fall back to manual mode: a review and two taps.
- The home screen shows what's left, and the same switch ends it at once.
- The risk is like a contactless card's no-PIN limit: someone who taps your open, unlocked Flex can take at most what's left of the budget.

## Card mode (one uncapped transaction)

Card mode is for paying like a card: you turn it on right before paying, and the payment terminal (the iPhone) sets the amount.
- On the Flex home screen, touch "Turn on card mode" and confirm.
- The next payment, of any amount, is signed on the first tap with no review. Then card mode turns off by itself.
- It also turns off after one minute if no payment comes, with "Turn off card mode", or when the app closes. It doesn't spend budget mode's budget. Afterwards the Flex is back in manual mode, or in budget mode if that is on.
- The Flex shows what it paid, and to whom, right after.
- The risk: while it's on, whoever taps the Flex sets the amount, and on-chain payments can't be charged back. Turn it on only at the moment you pay.

`node test-modes.mjs` checks card mode and budget mode on Speculos, starting from a fresh home screen.

## Cash out to a card (sandbox)

After a payment, "Cash out to card" sends the iPhone wallet's USDC to a cash-out address. Then `web/api/cashout.mjs`:
1. reads the amount from the on-chain receipt;
2. issues an [Increase](https://increase.com) sandbox virtual Visa card with that spend limit;
3. funds it with a simulated ACH deposit, standing in for the USDC-to-USD off-ramp.

"Buy a $3.50 coffee" then runs a simulated card authorization, which comes back approved or with a decline reason such as `breaches_limit`.
- This is test money in Increase's sandbox, not a real card. In production the same step would go to a card issuer such as Baanx (Ledger CL Card) or Mercuryo Spend.
- A sandbox key needs no signup: `curl -X POST -H 'Content-Length: 0' https://sandbox.increase.com/groups` returns one.
- It needs two Vercel environment variables: `INCREASE_API_KEY` and `CASHOUT_ADDRESS` (where the USDC goes). Without them the button stays hidden.
- A replayed transaction hash returns the same card, because Increase's `Idempotency-Key` is set from the hash.
- `node test-cashout.mjs` checks the receipt parsing against real Base Sepolia transfers, with no key. `LIVE=1 node --env-file=.env.local test-cashout.mjs` also runs the sandbox flow.
- Deployed at https://tapcash-cashout.vercel.app (Vercel project `tapcash-cashout`).

## Findings worth knowing

- **Plain commands work over NFC.** The Flex forwards SELECT AID to the app, and iOS sends plain ISO 7816 APDUs with a trailing Le. The SDK's `apdu_parser` rejects that trailing Le, so the app parses its own APDUs.
- **NFC is off on the home screen.** Card emulation only runs while an NFC-enabled app is open, so nothing answers a phone tapped against the home screen.
- **`format_fpu64` bug.** In the SDK it doesn't NUL-terminate amounts of 1 or more. That put stack garbage on the review screen until the buffer was zero-initialised.
- **Public Speculos seed.** The default Speculos seed's first address has an EIP-7702 delegation on Base Sepolia, so USDC verifies its signatures via ERC-1271 and rejects them. `test.mjs` uses its own seed.

## Honest limits

- **Not private yet.** Every payment comes from the Flex's fixed address and is linkable on-chain.
- **A signed cheque, not cash.** If the payer spends the balance before the receiver submits, the transfer fails.
- **Two taps.** iOS ends the NFC session on the first tap's "not yet" reply.
- **Small amounts only.** The iPhone burner key lives in browser storage, which is fine for change, not for savings.
