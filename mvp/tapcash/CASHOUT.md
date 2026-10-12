# Cash-out experiments

Goal: after a TapCash payment, turn the received testnet USDC into something you can spend, in a provider's sandbox, by the Tue 13 Oct deadline. Each provider has its own branch. All of them read the amount from the real Base Sepolia receipt, so the on-chain part is real and only the card side is simulated.

Checked on 2026-10-11.

| Provider | Branch | Signup | Result |
| --- | --- | --- | --- |
| Increase | `cashout-increase` | None: one unauthenticated call returns a sandbox key | **Working.** Virtual Visa card issued, funded and charged in the sandbox. Live at https://tapcash-ruby.vercel.app |
| Lithic | `cashout-lithic` | Email and password, and you must accept their terms and E-SIGN | Code is written and checked offline. It needs a sandbox key, which needs Sahas to sign up |
| Immersve | `cashout-immersve` | None: public sandbox credentials are in their docs | **Blocked at KYC.** Sign-in with the wallet, funding source and simulated deposit all work; issuing a card needs KYC |
| Bridge, Baanx, Mercuryo | — | Sales contact | Sandbox access emailed for; no reply yet |

## Increase (working)

- **How:** `curl -X POST -H 'Content-Length: 0' https://sandbox.increase.com/groups` returns a sandbox key, with no account.
- **Flow in `web/api/cashout.mjs`:**
  1. Read the USDC amount from the receipt.
  2. Create a card with an all-time spending limit equal to that amount.
  3. Fund the cash-out account with a simulated inbound ACH, standing in for the USDC-to-USD off-ramp.
  4. Simulate purchases with `/simulations/card_authorizations`.
- **Test results:**
  - a $5 card approved a $3.50 coffee;
  - a second $3.50 was declined with `insufficient_funds`;
  - on a $1 card, $1.01 was declined with `breaches_limit`.
- **Good DX:**
  - instant sandbox;
  - `Idempotency-Key` on every POST, which made replaying a transaction hash safe;
  - clear decline reasons;
  - a real-time authorization webhook, which could let a card swipe pull USDC at that moment.
- **Friction:**
  - Creating an account needs an "entity" (a person or company) even in the sandbox, so we send obvious test data.
  - `POST /groups` with no body fails with HTTP 411 unless you send `Content-Length: 0`.
- **Limits:** fiat only. The USDC-to-USD step is ours, simulated by the ACH deposit.

## Lithic

- `web/api/cashout.mjs` on `cashout-lithic` creates a virtual card with a spend limit, then simulates authorizations.
- Lithic's API checks out against its SDK: the raw key goes in `Authorization`, `account_token` is optional, and the outcome is in `result`.
- **Blocker:** a sandbox key needs a dashboard signup that accepts Lithic's terms and E-SIGN. That's for Sahas to do, not an agent.

## Immersve

- **Good fit on paper:** cards spend USDC from the user's own wallet, and Base Sepolia USDC is a supported funding type.
- **What worked with the public sandbox credentials:**
  - SIWE sign-in with a throwaway wallet (`/auth/login-init`, then `/auth/login-complete`);
  - `POST /api/funding-sources`;
  - `POST /api/simulator/execute-deposit`, which confirmed a 5 USDC deposit.
- **Blocker:** `POST /api/cards` returns `KYC_REQUIRED`.
  - Partner-conducted KYC needs the public Card Issuer key, which returns `API_KEY_DISABLED`.
  - Immersve-conducted KYC is a hosted flow that needs a live face scan.
  - The public account is also set up for Polygon Amoy, not Base Sepolia.
- **Friction:** the API reference pages don't render request schemas without JavaScript, so we read the field names from validation errors.
- **Probe script:** `probes/immersve.mjs`.

## Not tried, with the reason

- **Marqeta:** email signup with terms, and possibly phone 2FA. Fiat only, like Increase.
- **Transak staging:** it is an off-ramp and has Base Sepolia, but signup wants a company email and the test token is TRNSK, not USDC.
- **MoonPay sandbox:** needs phone verification, and supports Sepolia only.
- **Stripe Issuing:** its docs contradict each other on sandbox support.
- **Ramp, Banxa, Alchemy Pay, Sardine, Rain, Reap:** gated behind sales or KYB.
