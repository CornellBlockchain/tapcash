# TapCash

Tap your Ledger Flex to an iPhone, approve on the Flex, tap again, and USDC moves on Base.

- **Nothing to install on the iPhone.** It runs in Safari.
- **The payer needs no ETH.** The receiver's phone pays the gas.
- **Your key stays on the Ledger.** The Flex shows the amount, the chain and the receiver before it signs.
- **Base mainnet or Base Sepolia,** picked on the page.

Live page: https://tapcash-ruby.vercel.app. It works on a real Flex.

Built for the Ledger N3XT Hackathon @ OP3N 2026.

## How a payment works

1. The receiver types an amount on the iPhone and holds it near the Flex.
2. The Flex shows "Send payment? 5 USDC on Base to 0x…". The payer approves.
3. The payer taps again. The Flex hands over a signed USDC transfer, and the phone sends it.

## Where things are

| Path | What |
| --- | --- |
| `mvp/tapcash/flex-app/` | The Ledger Flex app |
| `mvp/tapcash/web/` | The iPhone page and its two small APIs (gas top-up, card cash-out) |
| `mvp/tapcash/web/site/` | The product website |
| `mvp/tapcash/test*.mjs` | Tests on the Ledger emulator |

How it works under the hood, and the payment modes: [`mvp/tapcash/README.md`](mvp/tapcash/README.md).
Building and running it yourself: [`SETUP.md`](SETUP.md).
