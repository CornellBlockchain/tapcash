# TapCash

Tap your Ledger Flex to an iPhone, approve on the Flex, tap again, and USDC moves on Base.

- **Nothing to install on the iPhone.** It runs in Safari.
- **The payer needs no ETH.** The receiver's phone pays the gas.
- **Your key stays on the Ledger.** The Flex shows the amount, the chain and the receiver before it signs.
- **Base mainnet or Base Sepolia,** picked on the page.

Live page: https://tapcash-ruby.vercel.app. It works on a real Flex, and has moved real USDC on Base mainnet.

Built for the Ledger N3XT Hackathon @ OP3N 2026.

## Why

Hardware wallets are the safest place to keep crypto, and the most awkward place to spend it from. Paying someone in person usually means a laptop, a cable, or a phone app paired over Bluetooth, plus copying addresses around.

TapCash makes it feel like tapping a card. The receiver opens a web page, the payer taps their Ledger, checks the screen, and taps again. No app store, no pairing, no address copying, and the signing key never leaves the Ledger's secure chip.

## How a payment works

1. **The receiver asks.** They type an amount on the iPhone page and hold the phone near the Flex.
2. **The payer checks.** The Flex shows "Send payment? 5 USDC on Base to 0x…" and the payer approves.
3. **The payer taps again.** The Flex hands over a signed USDC transfer. The phone checks it really came from that Flex and sends it to the chain.
4. **Done.** The page shows the amount received and a Basescan link, usually within a few seconds.

The receiver can then move the USDC to their own Ledger by tapping it (or connecting Ledger Wallet), or, on testnet, cash it out to a sandbox Visa card.

## How the tap works

Without a paid Apple developer account, an iPhone app can't talk NFC to custom hardware. But Safari already talks to NFC security keys for logins (WebAuthn). So the Flex app acts as a security key:

- The page puts the payment request where a login would put a key ID.
- The Flex puts its signature where a security key would put its login signature.

The Flex builds the transfer itself from the request and signs that. It never signs a hash the page gives it, so the page can't trick it into signing something other than what's on screen.

## Ways to pay

Set on the Flex:

| Mode | What happens | When to use it |
| --- | --- | --- |
| **Manual** (default) | Every payment is reviewed: tap, approve, tap again. | Any amount, full control. |
| **Budget** | Payments within your limits go through on one tap, with no review. You set the per-payment limit, total and number of payments. | Many small payments, like a day at a market. |
| **Card** | The next payment, of any amount, goes through on one tap. Then it turns off, or after a minute. | Paying at a counter, like tapping a card. |

## Testnet and mainnet

Tap the network label in the page header to switch between **Base Sepolia** (test money, the default) and **Base** (real USDC).

- The Flex shows which chain it's signing for, and a signature for one chain doesn't work on the other.
- New iPhone wallets get a little gas automatically on both chains: about 0.0005 test ETH, or about $0.10 of real ETH on mainnet.
- Card cash-out is a sandbox demo, so it only appears on testnet.

## Safety

- **Keys:** the payer's key never leaves the Flex's secure chip, and the Flex shows exactly what it signs.
- **Replay:** each signature is for one amount, one receiver, one chain, and one random nonce, and it expires after an hour.
- **Modes:** budget and card mode trade review for speed. Like a contactless card, someone who taps your unlocked Flex can take what's left of your budget, or anything while card mode is on. Both live only in memory and turn off when the app closes.
- **The iPhone wallet** is a key stored in Safari. It's fine for receiving change; move anything real to a Ledger.

## Try it

**With a Flex and an iPhone:**
1. Sideload the TapCash app onto the Flex ([`SETUP.md`](SETUP.md), section 5).
2. Put some USDC on the Flex's address: free test USDC from https://faucet.circle.com, or real USDC on Base.
3. Open https://tapcash-ruby.vercel.app in Safari, enter an amount, and tap.

**Without hardware:** the tests run the whole flow on the Ledger emulator. See [`SETUP.md`](SETUP.md), section 4.

## Architecture

```
  Payer                               Receiver
┌──────────────┐   NFC tap 1: request   ┌──────────────────┐
│ Ledger Flex  │ ◀───────────────────── │ iPhone, Safari   │
│ TapCash app  │                        │ tapcash page     │
│              │   NFC tap 2: signature │ (burner wallet)  │
│ secure chip  │ ─────────────────────▶ │                  │
└──────────────┘                        └────────┬─────────┘
                                                 │ transferWithAuthorization
                                                 │ (phone pays gas)
                        ┌──────────────┐         ▼
                        │ Vercel APIs  │   ┌───────────┐
                        │ gas top-up   │──▶│ Base USDC │
                        │ card cashout │   └───────────┘
                        └──────────────┘
```

- **The Flex** only ever sees a request and returns a signature. It needs no internet.
- **The phone** checks the signature, sends the transaction, and shows the result.
- **The APIs** are optional. Without them, you fund the phone's gas by hand and the cash-out button stays hidden.

## Demo in two minutes

1. Open TapCash on the Flex. The home screen says "Manual mode: two taps".
2. On the iPhone, open the page, type `1`, and press **Tap Ledger**.
3. Hold the phone to the Flex. It shows "Send payment? 1 USDC on Base Sepolia to 0x…". Touch **Approve**.
4. Tap again. The phone shows "+1 USDC" with a Basescan link.
5. On the Flex, turn on **card mode**, request `2` on the phone, and tap once. It pays straight away, then card mode turns off.
6. Tap the network label on the page to switch to **Base** and repeat with real USDC.

## FAQ

**Does the payer need an app on their phone?**
No. The payer only needs their Ledger Flex. The receiver needs an iPhone with Safari.

**Why two taps?**
iOS ends the NFC session as soon as the Flex says "not yet, waiting for approval". The second tap collects the signature. Budget and card mode sign on the first tap.

**Who pays the gas?**
The receiver's phone, from its burner wallet. On mainnet a payment costs well under a cent, and the gas top-up funds new phones automatically.

**Can the page make the Flex sign something else?**
No. The Flex builds the USDC transfer from the request fields, shows them, and signs that. It only signs USDC transfers on Base or Base Sepolia.

**What if the phone is lost or Safari's data is cleared?**
The burner wallet and anything in it is gone. That's why the page offers "Move to my Ledger" right after you get paid.

**Does it work on Android?**
Not tested. The tap uses standard WebAuthn over NFC, so Chrome on Android may work, but we've only tried iPhone Safari.

## What's next

Work in progress on other branches:
- **Private receiving** (`private-payments`, PR #10): a fresh receiving address for each payment, so payments aren't all linked to one address.
- **Ledger Wallet CLI** (`wallet-cli`, PR #8): check, top up and empty the TapCash address from the command line.
- **DMK setup page** (`dmk-setup`, PR #7): confirm the Flex address over USB with Ledger's Device Management Kit.

Ideas beyond that:
- A real card off-ramp instead of the sandbox, e.g. through a card issuer.
- Paying the gas with USDC so the receiver needs no ETH either.
- More tokens and chains, each built into the Flex app with its own check.

## Built with

- **Flex app:** C on the Ledger secure SDK, with its own minimal U2F responder and EIP-712 signing.
- **iPhone page:** one static HTML file using viem. No build step, hosted on Vercel.
- **APIs:** two Vercel functions, one for the gas top-up and one for the Increase sandbox card cash-out.
- **Chain:** USDC's `transferWithAuthorization` (EIP-3009) on Base, so the payer never needs ETH.

## Where things are

| Path | What |
| --- | --- |
| `mvp/tapcash/flex-app/` | The Ledger Flex app |
| `mvp/tapcash/web/` | The iPhone page and its two small APIs |
| `mvp/tapcash/web/site/` | The product website |
| `mvp/tapcash/test*.mjs` | Tests on the Ledger emulator |

More detail on the internals, request format and limits: [`mvp/tapcash/README.md`](mvp/tapcash/README.md).
Building and running it yourself: [`SETUP.md`](SETUP.md).

## Limits

- **Two taps.** iOS ends the NFC session after the first tap, so approval needs a second one (budget and card mode skip it).
- **Not private.** Every payment comes from the Flex's one address.
- **A signed cheque, not cash.** If the payer empties their balance before the phone sends the transfer, it fails.
- **iPhone and Safari only** so far, and the TapCash app has to be open on the Flex.
