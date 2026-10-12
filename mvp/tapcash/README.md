# TapCash: how it works

## The idea

An iPhone can't talk NFC to custom hardware without a paid Apple developer account, but Safari can talk to NFC security keys. So the Flex app pretends to be one (a U2F key). The page hides the payment request inside a "credential ID", and the Flex hides its signature inside the reply.

1. **First tap:** the Flex receives the request and shows "Send payment? 5 USDC on Base to 0x…".
2. **Approve** on the Flex. It builds the USDC `transferWithAuthorization` (EIP-3009) itself and signs it. It never signs a hash the page gives it.
3. **Second tap:** the page gets the signature, checks it came from the Flex, and sends the transfer. The phone pays the gas.

## Two chains

Each request carries a chain byte: 0 for Base Sepolia, 1 for Base mainnet. Both USDC contracts are built into the Flex app, the Flex screen names the chain, and a signature for one chain is useless on the other.

On the page, tap the network label in the header to switch. On mainnet:
- payments move real USDC;
- a new iPhone wallet gets about $0.10 of gas automatically from a small funding wallet;
- "Cash out to card" is hidden, because it's a sandbox demo.

## Payment modes on the Flex

- **Manual (default):** every payment is reviewed on the Flex. Tap, approve, tap again.
- **Budget mode:** payments within your limits go through on one tap, with no review. Set the limits in Settings: per payment, total, and number of payments. Like a contactless card, someone who taps your unlocked Flex can take at most what's left.
- **Card mode:** turn it on right before paying, and the next payment of any amount goes through on one tap. It turns off after that payment, or after a minute.

## Cash out to a card (sandbox, testnet only)

"Cash out to card" sends the phone's USDC to a cash-out address. `web/api/cashout.mjs` reads the amount from the chain and issues an [Increase](https://increase.com) sandbox Visa card with that much to spend. "Buy a $3.50 coffee" tests it. It uses test money only.

## Wire format

Shared by `flex-app/src/app_main.c` and `web/tapcash.js`.
- **Request (65 bytes):** `to(20) | value(8, micro-USDC) | validBefore(4) | nonce(32) | chain(1)`
- **Reply:** `UP(1) | counter(4, last byte = v) | DER(r, s) | from(20)`

## Tests

Both run against the Ledger emulator (Speculos). See [`SETUP.md`](../../SETUP.md).
- `test.mjs`: both taps, on both chains, ending with a simulated transfer on the real chain.
- `test-modes.mjs`: budget and card mode.

## Gotchas we hit

- iOS sends a trailing byte that the Ledger SDK's command parser rejects, so the app parses commands itself.
- NFC only answers while the TapCash app is open on the Flex, not on the home screen.
- The SDK's `format_fpu64` doesn't end amounts of 1 or more with a NUL byte, which showed garbage on screen.
- The emulator's default seed has an EIP-7702 delegation on Base Sepolia, which makes USDC reject its signatures. The tests use their own seed.

## Limits

- **Not private.** Every payment comes from the Flex's one address.
- **A signed cheque, not cash.** If the payer empties their balance before the phone sends the transfer, it fails.
- **Two taps.** iOS ends the NFC session after the first tap's "not yet" answer.
- **Small amounts on the phone.** The iPhone wallet's key lives in Safari's storage. Move anything real to your Ledger.
- **The mainnet gas top-up can be drained** by someone requesting it for many new addresses. Keep only a few dollars in its funding wallet.
