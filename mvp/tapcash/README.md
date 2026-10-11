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

## Cash out to a card (sandbox)

After a payment, "Cash out to card" sends the iPhone wallet's USDC to a cash-out address. `web/api/cashout.mjs` then reads the amount from the on-chain receipt and issues a [Lithic](https://lithic.com) sandbox virtual card with that spend limit. "Buy a $3.50 coffee" runs a simulated card authorization against it.
- This is test money in Lithic's sandbox, not a real card. In production the same step would go to a card issuer such as Baanx (Ledger CL Card) or Mercuryo Spend.
- It needs two Vercel environment variables: `LITHIC_API_KEY` (a sandbox key) and `CASHOUT_ADDRESS` (where the USDC goes). Without them the button stays hidden.
- `node test-cashout.mjs` checks the receipt parsing against real Base Sepolia transfers. It needs no key.

## Findings worth knowing

- **Plain commands work over NFC.** The Flex forwards SELECT AID to the app, and iOS sends plain ISO 7816 APDUs with a trailing Le. The SDK's `apdu_parser` rejects that trailing Le, so the app parses its own APDUs.
- **NFC is off on the home screen.** Card emulation only runs while an NFC-enabled app is open, so nothing answers a phone tapped against the home screen.
- **`format_fpu64` bug.** In the SDK it doesn't NUL-terminate amounts of 1 or more. That put stack garbage on the review screen until the buffer was zero-initialised.
- **Public Speculos seed.** The default Speculos seed's first address has an EIP-7702 delegation on Base Sepolia, so USDC verifies its signatures via ERC-1271 and rejects them. `test.mjs` uses its own seed.

## Honest limits

- **Not private yet.** Every payment comes from the Flex's fixed address and is linkable on-chain.
- **A signed cheque, not cash.** If the payer spends the balance before the receiver submits, the transfer fails.
- **Two taps.** iOS ends the NFC session on the first tap's "not yet" reply.
- **Pocket-cash only.** The iPhone burner key lives in browser storage, which is fine for change, not for savings.
