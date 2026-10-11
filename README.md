# TapCash: your Ledger as a tap-to-pay wallet

Tap a Ledger Flex to an iPhone, approve on the Flex screen, tap again, and USDC moves on Base Sepolia.
- The receiver needs no app: Safari is enough.
- The payer needs no ETH for gas.
- The key never leaves the secure element, and the Flex shows exactly what it signs.

**Works on real hardware.** Live page: https://tapcash-ruby.vercel.app

Built for the Ledger N3XT Hackathon @ OP3N 2026.

## How it works

1. The iPhone page asks for a payment by tapping the Flex. The request travels over NFC through Safari's security-key support (WebAuthn), so no iOS app or paid Apple account is needed.
2. The Flex shows "Send payment? 5 USDC on Base Sepolia to 0x…".
3. On Approve, the Flex itself signs a USDC `transferWithAuthorization` (EIP-3009).
4. On the second tap, the page checks the signature and submits it, paying the gas.

Details, wire format, commands and limits: [`mvp/tapcash/README.md`](mvp/tapcash/README.md).

## Repo

| Path | What |
| --- | --- |
| `mvp/tapcash/flex-app/` | Ledger Flex app (C, Ledger secure SDK) |
| `mvp/tapcash/web/` | The iPhone page (static, no build) |
| `mvp/tapcash/test.mjs` | End-to-end check on Speculos, including an on-chain simulation |
