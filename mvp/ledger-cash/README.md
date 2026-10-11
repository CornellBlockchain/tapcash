# Ledger Cash v0: device-capped USDC cash on a Ledger Flex, paid by tapping two Ledgers together

Ledger Cash makes a Ledger Flex work as a device-capped cash wallet for USDC. The ledger-cash app refuses to sign more
than the loaded balance from a [cash account](#the-cash-account) no stock Ledger chain app can sign for (dedicated derivation path; see The cash account for the remaining hole).
Nothing is escrowed, and the payee still cannot check on-chain solvency offline (see
[Cash ladder](#cash-ladder-device-capped-iou-v0-to-escrowed-cash-v2)). The owner funds the cash account on-chain, then
**loads** a device-capped cash balance into the device and confirms it on screen. Later the owner **pays offline**: they hold
their Flex against the payee's Ledger. The payer's Flex is the NFC **reader**; the payee's Ledger is the NFC **card**
(card emulation). The payer's screen shows exactly who is paid, how much and for what. On approval the payer app signs a
USDC EIP-3009 `TransferWithAuthorization` and hands it to the payee over NFC. The payee app checks it, stores it and
returns a signed receipt. Later, when someone is online, **anyone** can submit the stored authorization on-chain to
settle it.

What the payee holds after a tap is a **signed IOU**, not money: see [Honest limits](#honest-limits) before relying on
it.

Status (2026-10-10): **runs end to end in emulation.** `python demo.py` prints `ALL PASS` (recorded output below).
It uses two Speculos Flex instances joined by an emulated NFC field and settles on anvil. Nothing has been run on a real
device yet; see [What changes on real hardware](#what-changes-on-real-hardware) and the [hardware gates](#hardware-gates).
The real-device checklists are in [HARDWARE.md](HARDWARE.md), and a 1-minute video of the emulated run is
[video/ledger-cash-demo.mp4](video/ledger-cash-demo.mp4).

```
 payer Flex (NFC reader)                         payee Ledger (NFC card emulation)
 ------------------------                        ---------------------------------
 LOAD_CASH 20 (on-screen OK)                     SET_REQUEST 5 "coffee" (on-screen OK)
 "Pay by tap" / TAP_TO_PAY                       home: "Receive 5 USDC to 0xB112...A72DB"
 "Hold near the payee"   ---- field on ---->
   SELECT AID F04C45444745524341534801  ---->    9000
   GET_REQUEST E011                     ---->    request (157 B, signed by the payee)
 checks payee sig, network, balance, replay
 review: Pay / To / For / Cash left after
   (owner matches "To" with the payee's screen)
 Hold to sign -> sign EIP-712 in RAM,
   debit capped cash + record nonce (one NVM write)
   PUT_AUTH E023 + auth (161 B)         ---->    checks the auth (incl. low-s), stores it,
                                        <----    receipt (payee's signature over the auth)
 verifies receipt -> "Paid 5 USDC to 0x..."      "Signed IOU for 5 USDC from 0x... Not settled yet"
                                                 (request consumed: GET_REQUEST now B006)
                                                 ... later, online: GET_AUTHS -> settle.mjs
                                                 -> USDC.transferWithAuthorization on-chain
```

## The cash account

Both the payer key and the payee's request-signing key are `m/44'/1279476051'/0'/0/0`: coin type `0x4C434153`
("LCAS"), which is not registered in [SLIP-44](https://github.com/satoshilabs/slips/blob/master/slip-0044.md) (checked
2026-10-10). The app's Makefile sets `PATH_APP_LOAD_PARAMS = "44'/1279476051'"` and nothing else, so the device OS
lets ledger-cash derive no other key, and no stock Ledger chain app may derive this one: the Ethereum app is locked to
`44'/60'`, `45'` and `12381/3600`, and each chain clone to its own SLIP-44 coin type.

- The **cash account** is a separate address that no stock Ledger chain app can sign for (dedicated derivation path; see the remaining hole below). It is still a normal Ethereum
  address, so EIP-3009 settlement is unchanged. `GET_BALANCE` (`hw.py balance`) returns it.
- The owner **funds it on-chain**: send USDC to that address. `LOAD_CASH` then sets how much of it the device will
  spend offline.
- **Remaining hole:** the OS path lock binds the key to whichever app declares the path, not to this app's code. The
  owner could sideload another app that declares `44'/1279476051'`, or import the recovery phrase into a software
  wallet, and sign with the cash key outside the cap. Closing that for a payee needs attestation (BOLOS endorsement,
  rung v1 of the [Cash ladder](#cash-ladder-device-capped-iou-v0-to-escrowed-cash-v2)) plus escrow (v2). The path lock
  is enforced by the device OS; the emulated runs show the derivation, not the lock.

## Device-capped cash semantics (what the payer's secure element enforces)

These rules protect the **payer's own spending**. They give the payee no assurance at all: nothing in a tap proves
that the other side is a Ledger, runs this app, or has any device-capped cash counter (see
[Honest limits](#honest-limits)).

- **Load before you spend.** `LOAD_CASH` adds to a balance counter in the app's NVM, and only after the owner approves it
  on screen. The payer app refuses any payment above that balance (`B003`, nothing signed).
- **Each payment settles once.** The EIP-3009 nonce is `keccak256(request[0:92])`, so the same request maps to the same
  nonce, and USDC's `authorizationState` rejects a second settlement ("already used", shown in the demo). The payer
  also refuses to sign a request it has already paid (`B004`). It remembers its last 8 nonces in NVM. The request's
  `reqNonce` is 32 random bits, so a payee that is wiped, reinstalled or run on a second device does not repeat old
  requests.
- **Debit before release.** On approval the app signs in RAM, then writes the new balance, the payment counter and the
  nonce in **one** `nvm_write`, and only then sends the signature over NFC. If the payee leaves the field before
  approval, nothing is debited and the screen says "Card removed / Nothing paid". If the payee leaves after signing,
  the debit stands, and the screen says "Signed X / Card left after signing / Cash debited, no receipt". The signed
  auth stays readable over USB with `TAP_STATUS` until the next tap or app exit (it is kept in RAM only). The demo runs
  both cases.
- **What the signatures prove.** The request carries an EIP-191 signature by `payTo` over its first 92 bytes. The payer
  recovers it on the device and refuses the request if it does not recover to `payTo` (`B001`). That gives integrity
  in transit and binds the receipt to `payTo`; it does **not** say who the payee is, because anyone can sign a
  request for their own address. So the payee's home screen shows its address (`Receive 5 USDC to 0xB112...A72DB`),
  and the payer must match it with the "To" on the review. The payee checks the auth's EIP-712 signature (low-s only,
  as USDC requires), `to`, value, `validBefore` and nonce before storing it, and signs a receipt. The payer verifies
  the receipt against `payTo` before it shows "Paid".
- **The payee serves a request only while it is payable.** `GET_REQUEST` answers `B006` once the request is paid, after
  any new `SET_REQUEST` (even one rejected on screen) and after `SET_CONFIG`. A payer who taps a paid payee sees
  "Payee has no request" and nothing is signed or debited.
- **Over NFC the app is only a payee card.** Only SELECT, `GET_REQUEST` and `PUT_AUTH` are accepted over NFC; every
  other INS (balance and address, `PAY`, `LOAD_CASH`, `SET_CONFIG`, `TAP_TO_PAY`, `TAP_STATUS`, `GET_AUTHS`) answers
  `6D00`. A reader in range cannot read the balance or push a payment review onto an idle payer.

## Honest limits

- **Any key can pay the payee in IOUs.** `PUT_AUTH` checks only that the EIP-712 signature recovers to the `from` the
  sender supplied. Any NFC phone or script can create a fresh key with no USDC, read `GET_REQUEST`, sign a matching
  auth and send it; the payee then shows "Signed IOU for 5 USDC", marks the request paid and returns a receipt. No
  Ledger is needed. The screen says "IOU ... Not settled yet" for this reason, not "Received".
- **No offline solvency.** The loaded device-capped cash is **only a counter on the payer's device**. Nothing locks the
  USDC on-chain, so the payee **cannot check offline** that the cash account's on-chain balance still covers the
  authorization. The payer could have loaded more than the account holds, loaded the same seed's cash account on a
  second device, or moved the USDC with the key outside ledger-cash (see [The cash account](#the-cash-account)). Until settlement the payee
  carries the credit risk of a signed IOU. True bearer cash (escrowed, not device-capped) needs on-chain escrow (the
  "load" moves USDC into a contract that only releases it to authorizations from that device key) **and** device
  attestation (so the payee knows the counter lives in a genuine Ledger secure element running this app). Both are
  stretch goals, out of scope for v0; see [Cash ladder](#cash-ladder-device-capped-iou-v0-to-escrowed-cash-v2).
- **The payee's identity is visual.** The payer can only compare the "To" address on its review with the payee's home
  screen. A rogue card shows a review with its own address and any label.
- `validBefore = 2^64-1`: a request never expires, because the device has no trusted clock.
- The domain name is fixed to `"USDC"` (testnets, Arc). Configured with mainnet USDC (`"USD Coin"`), both sides would
  sign and verify under the wrong domain: the payee would accept auths that never settle.
- The payee keeps received auths in a ring of 8. A 9th payment silently overwrites the oldest, so run `GET_AUTHS` and
  settle first.
- Wiping or reinstalling the app resets the balance and the replay ring. The on-chain nonce still stops a double
  settlement. `reqNonce` is 32 random bits: two requests with the same amount and label collide with probability
  2^-32 per pair, and a collision gets an auth that cannot settle.
- A "signed, no receipt" auth lives in the payer's RAM only: readable with `TAP_STATUS` over USB until the next tap or
  app exit. There is no on-device "Resend" yet; the payer stays debited either way.
- "Hold near the payee" has no timeout. Until Cancel, any card that enters the field gets SELECT and GET_REQUEST, and
  a valid request puts a review on screen (which still needs Hold to sign).
- Emulation only: the Speculos payee runs `--transport NFC`, so `speculos-nfc/seproxyhal.py` adds a USB host link to
  it. The demo sends the payee's host commands with a `USB!` prefix over that link; a real device has USB (or BLE)
  next to NFC anyway.

## Cash ladder: device-capped IOU (v0) to escrowed cash (v2)

"Cash" in this project always means one rung of this ladder; this build is v0, device-capped cash.

| Rung | What the payee holds | What makes it hold | Status |
|---|---|---|---|
| **v0: device-capped cash (this build)** | A payer-signed EIP-3009 IOU that settles later | The ledger-cash app refuses to sign more than the loaded balance from a cash account no stock Ledger chain app can sign for (dedicated derivation path), and debits before the signature leaves the chip. No escrow: the payee still cannot check on-chain solvency offline. | Runs end to end in emulation |
| **v1: attested device-capped cash** | The same IOU, plus proof that it came from the genuine ledger-cash app | BOLOS endorsement signs over the running app's code hash, so a payee can check the IOU came from the capped app, not from any key or from another app that declares the same path. Still no escrow. | Speculos-only stretch, not built. Speculos gives every app the same fixed code hash (`src/bolos/endorsement.c:38`), so it shows the mechanism, not the binding; retail provisioning is untested (research/source-audit.md M01) |
| **v2: escrowed cash** | An attested note redeemable from on-chain escrow | "Load" locks USDC in a contract that releases it only to authorizations from that device key, so the note pays out without trusting the payer | Not built |

Q&A, v0 device-capped cash: "What stops a payer spending the same loaded balance to two payees before either settles?
In v0 the ledger-cash app caps what it signs from its cash account; it does not escrow." Each payment is debited from
the device counter before its signature leaves the chip, so the sum of everything one device's ledger-cash app signs
never exceeds what was loaded on it. The cash account's USDC is not locked: the owner can load more than it holds, or
sign with the key outside ledger-cash (see [The cash account](#the-cash-account)), so an IOU can bounce at settlement.
v2 closes that gap.

## Protocol

All APDUs use CLA `E0` and big-endian fixed fields; P1 = P2 = 0 unless stated. Values are USDC base units (6 decimals).
"USB" in the link column means any host link (USB or BLE); over NFC only the three NFC rows are accepted.

| INS | Name | Who / link | Data in | Data out | Screen |
|---|---|---|---|---|---|
| `00 A4 04 00 0C` | SELECT AID | payee, NFC | AID `F04C45444745524341534801` (`F0` + "LEDGERCASH" + `01`) | none (`9000`, `6A82` for another AID) | none |
| `12` | SET_CONFIG | both, USB | chainId u64, token 20 | none | Approve: "Set USDC network". Approval drops a pending request |
| `20` | LOAD_CASH | payer, USB | value u64 | none | Approve: "Load X USDC as cash" |
| `21` | GET_BALANCE | both, USB | none | balance u64, payCounter u32, address 20 | none (also allowed while a screen is up) |
| `10` | SET_REQUEST | payee, USB | value u64, label of up to 24 printable ASCII bytes | none | Approve; home becomes "Receive X to 0xB112...A72DB". Once it reaches the screen it drops the pending request, even if rejected |
| `11` | GET_REQUEST | payee, NFC or USB | none | request (157) while one is payable, else `B006` | none |
| `22` | PAY | payer, USB | request (157) | auth (161) | review, then Hold to sign (USB path, stage B) |
| `23` | PUT_AUTH | payee, NFC or USB | auth (161) | `01`, receipt r32 s32 v1 (66) | "Signed IOU for X from 0x... Not settled yet" |
| `24` | GET_AUTHS | payee, USB | P1 = slot 0..7 | auth (161) | none |
| `30` | TAP_TO_PAY | payer, USB (or the home button "Pay by tap") | none | none; `9000` = reader armed | "Hold near the payee" (Cancel) |
| `31` | TAP_STATUS | payer, USB | none | state u8, sw u16, last tap auth (161 bytes, zeros if none) | none (also allowed while a screen is up) |

Wire formats:
- **request (157):** chainId u64 @0, token 20 @8, payTo 20 @28, value u64 @48, validBefore u64 @56, reqNonce u32 @64
  (random), label 24 @68 (zero padded), payeeSig r32 s32 v1 @92. payeeSig = `personal_sign(keccak256(request[0:92]))`.
- **auth (161):** from 20, to 20, value u64, validAfter u64 (=0), validBefore u64, nonce 32 (= keccak256(request[0:92])),
  v 1, r 32, s 32. Signed as EIP-712 `TransferWithAuthorization` under the domain {name "USDC", version "2", chainId,
  verifyingContract token}. v is 27/28 and s is at most n/2 (the payer produces low-s; the payee refuses high-s).
  Settle it with `transferWithAuthorization(from, to, value, validAfter, validBefore, nonce, v, r, s)`.
- **receipt:** the payee's `personal_sign(keccak256(auth))`, as r||s||v.

TAP_STATUS states: 0 idle, 1 waiting for a card, 2 busy (reading or review on screen), 3 auth sent, 4 **paid** (receipt
verified), 5 **failed, nothing paid**, 6 **signed, no receipt** (debited; the auth is in the reply).

Status words: `9000` ok, `6985` rejected on screen, `6700` wrong length, `6A80` bad data, `6A86` bad P1/P2,
`6A88` no auth in that slot, `6D00` unknown INS or not allowed over NFC, `6E00` wrong CLA.
- `B001` payee signature invalid
- `B002` not configured, or wrong chain or token
- `B003` not enough device-capped cash
- `B004` already paid
- `B005` invalid auth (fields, signature, or high-s)
- `B006` no request (none set, already paid, or dropped)
- `B007` busy (a screen is up)
- `B008` tap: card left the field
- `B009` tap: payee did not answer in time
- `B0FF` crypto failure

NFC size budget: replies over 271 bytes are dropped by the reader stack (research/nfc-reader-mode.md §1.3). The
largest messages fit without splitting:

| Exchange | Size |
|---|---|
| GET_REQUEST reply | 157 + SW = 159 bytes |
| PUT_AUTH command | 5 + 161 = 166 bytes |
| receipt | 66 + SW = 68 bytes |

Both GET_REQUEST and PUT_AUTH cross the 158-byte Ledger-protocol chunk, so the multi-chunk path is exercised in both
directions.

## Run it

Prerequisites:
- Docker Desktop, with these images (pinned by digest: the builder so `app.sha256` is reproducible,
  `speculos-nfc/seproxyhal.py` is a patched copy of that exact Speculos build, and the anvil state dump format follows
  the anvil version):
  ```bash
  docker pull ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools@sha256:8d3da9179dd1b241883c769c521ee9403352b60091c80405b5bef5801a003ba2
  docker pull ghcr.io/ledgerhq/speculos@sha256:028d1e368244631578537e7ca50b6f13ca2932b5f3fd220627289b559c07a886
  docker pull ghcr.io/foundry-rs/foundry@sha256:0c00cb0bda1ab1b91c9a6bf60f4c76c09c1a8870824b6d4718afbabacf6f9a17
  ```
- Node 20+, and Python 3.12 with `requests` and `eth-account` (which brings `eth_utils`).
- Free host ports 127.0.0.1:8545 (a local anvil there would collide) and 16000-16002, 16010-16011.
- Git Bash or PowerShell. The host has little RAM, so the demo never runs more than one container at a time.

```bash
cd mvp/ledger-cash
# 1. build the device app (same ELF for payer and payee; APP_DIR=/app is required)
MSYS_NO_PATHCONV=1 docker run --rm --memory 1g --name lc-i-build -v "$(pwd -W)/app:/app" \
  ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools@sha256:8d3da9179dd1b241883c769c521ee9403352b60091c80405b5bef5801a003ba2 \
  make -C /app TARGET=flex BOLOS_SDK=/opt/flex-secure-sdk APP_DIR=/app -j4
# 2. settlement deps (viem); out/USDC.sol/USDC.json is already compiled
(cd settle && npm i)
# 3. the demo (about 1 minute once the images are pulled)
python demo.py
```

`demo.py` runs in three phases, one container each:

1. **Chain, online, before** (`lc-i-anvil`): deploy the USDC look-alike, mint 100 USDC to the payer, print the
   balances, then save the chain with `anvil_dumpState` and stop anvil.
2. **Devices, offline** (`lc-i-speculos`). One container runs two Speculos Flex instances with the patched
   `speculos-nfc/seproxyhal.py`:
   - The payer is the NFC reader. It keeps its USB link to the host: REST `:16000`, APDU `:16001`, NFC reader port
     `:16002`.
   - The payee runs `--transport NFC` as the card: REST `:16010`, APDU = RF side `:16011`. Its host commands go over
     the patch's USB link (`USB!` prefix on REST `/apdu`), so they arrive as USB, as on a device.

   `speculos-nfc/relay.py` is the RF field between them. The demo calls SET_CONFIG on both, LOAD_CASH 20 on the
   payer and SET_REQUEST 5 "coffee" on the payee. It checks the payee's NFC side as a stranger's reader would see it
   (SELECT and GET_REQUEST answer, GET_BALANCE / PAY / LOAD_CASH / SET_CONFIG / TAP_TO_PAY / TAP_STATUS / GET_AUTHS
   give `6D00`), then runs four taps. It auto-approves the payer's review through the Speculos REST API (`/events`
   and `/finger`):
   1. Tap 1 starts from the home button "Pay by tap" and is paid. The payee's GET_REQUEST is `B006` afterwards.
   2. Tap 2 is the same tap again: the payee no longer serves the paid request, so the payer shows "Payee has no
      request" (`B006`) and nothing is signed. A USB PAY of the same request gets the payer's own `B004`.
   3. Tap 3: the payee is pulled away during the review, so nothing is paid.
   4. Tap 4: the payee is pulled away after signing, so the device-capped cash is debited and the auth is kept.

   Then two payee checks: a high-s copy of tap 4's auth (it still recovers to the payer) is refused with `B005`, and a
   SET_REQUEST rejected on screen drops the pending "tea" request (`GET_REQUEST` -> `B006`). GET_AUTHS on the payee
   writes `auths.json`.
3. **Chain, online, later** (`lc-i-anvil`): `anvil_loadState`, then `settle.mjs auths.json`, with balances before and
   after. A second settle is rejected with "already used".

Screenshots of both screens at every step go to `screens/` (`NN-<payer|payee>-<step>.png`). Key ones:

| Screenshot | Shows |
|---|---|
| `*-payee-ready` | "Receive 5 USDC to 0xB112...A72DB" |
| `*-payer-tap1-hold-near` | "Hold near the payee" |
| `*-payer-tap1` | the review pages: Pay / To / For / Cash left after, then Hold to sign |
| `*-payer-tap1-end` / `*-payee-tap1-end` | "Paid 5 USDC to 0xB112..." / "Signed IOU for 5 USDC from 0x46CE... Not settled yet" |
| `*-payer-tap2-again-end` | "Payee has no request" |
| `*-payer-tap3-pulled-end` | "Card removed / Nothing paid" |
| `*-payer-tap4-cut-end` | "Signed 3 USDC / Card left after signing / Cash debited, no receipt" |

Fixtures: the payer is the spike's Speculos seed, `0x46cE8565DD320e3764aa33cbdA7024F469132354`. The payee is
"abandon x11 about", `0xb1124942BA3CeB48d87Dac9baBc50ca3B50A72db`. Both are the cash key 44'/1279476051'/0'/0/0, on
anvil chainId 31337.

## Recorded demo output

`python demo.py`, 2026-10-10, one run (the hex lines are the APDUs on the emulated field). The reqNonce is random, so
the request, signature, nonce and settlement tx hex differ on every run. The bracketed `[payer]`/`[payee]` screen-text
lines also vary: whether the home-screen text is still in the Speculos event buffer depends on timing. Every assert,
status word, balance and address is the same on every run.

```
== 1. chain (online, before): deploy USDC, fund the payer
  token 0x5FbDB2315678afecb367f032d93F642f64180aa3 chainId 31337 tx 0xfbfa126cb1e320eda35a0e8bf278195e886d79547544826678a8314ff0b113ec
  minted 100 USDC to 0x46cE8565DD320e3764aa33cbdA7024F469132354 tx 0xe0c1ec0433391c5bc165cf873a7618deaa156e3c14daf15e6eb532ccb416d3d0 balance 100.000000 USDC
  0x46cE8565DD320e3764aa33cbdA7024F469132354 100.000000 USDC
  0xb1124942BA3CeB48d87Dac9baBc50ca3B50A72db 0.000000 USDC
== 2. devices (offline): payer Flex = NFC reader, payee Flex = NFC card emulation
  [payer] Set USDC network | Chain ID 31337 | USDC  | 0x5FBDB2315678AFECB367F0 | 32D93F642F64180AA3 | Reject | Approve
  [payee] Set USDC network | Chain ID 31337 | USDC  | 0x5FBDB2315678AFECB367F0 | 32D93F642F64180AA3 | Reject | Approve
  [payer] Load 20 USDC as cash | Cash after: 20 USDC | Reject | Approve
  [payee] Request 5 USDC | For: coffee | Reject | Approve
  payer loaded 20 USDC cash; payee asks 5 USDC for coffee
  NFC side of the payee: SELECT and GET_REQUEST answer; GET_BALANCE, PAY, LOAD_CASH, ... -> 6D00
== tap 1: pay 5 USDC by tap (started from the payer's home button "Pay by tap")
  tap: card 04a1b2c3 in field
    reader > card 00a404000cf04c45444745524341534801
    reader < card 9000
    reader > card e011000000
    reader < card 0000000000007a695fbdb2315678afecb367f032d93f642f64180aa3b1124942ba3ceb48d87dac9babc50ca3b50a72db00000000004c4b40ffffffffffffffffbc1a9d4d636f66666565000000000000000000000000000000000000613adbc3953d62c4cd69223d34b66b243f47f1cbd8ee4e69808711f16c6098cb5c1a2fbae6e94cbf4429b28e4ea67069ddf2c576c9254870f96bcb2c15b750611b9000
  [payer screen] Reading request | Pay with | USDC cash | Swipe to review | Reject | 1 of 4
  [payer screen] Pay | 5 USDC | To | 0xB1124942BA3CEB48 | D87DAC9BABC50CA3B | 50A72DB | For | coffee | Reject | 2 of 4
  [payer screen] Cash left after | 15 USDC | Reject | 3 of 4
  [payer screen] Pay 5 USDC? | Reject | 4 of 4 | Hold to sign
    reader > card e0230000a146ce8565dd320e3764aa33cbda7024f469132354b1124942ba3ceb48d87dac9babc50ca3b50a72db00000000004c4b400000000000000000ffffffffffffffff555d037bbd06edae5804ab22adb24caf51c893a6b55569a2fa7f702739ff9c471bda6c5f5be6b5310dd18064c6d70a1be285f5b5eee38fd087c4f1d771e10a828d3e705c0be98473c088560a8f1151e09b7ba9290d5cc8a24296867c183806feee
    reader < card 014bfff3712a1bc66514f78f78119f68fceefc6b02b68d9b9aa2baa90c841e43bc696a39775b3454adc06780e3fe780b27ca4ee25413e7526de1613ab20a6898221b9000
  tap: card removed after 3 APDU(s)
  TAP_STATUS PAID sw 9000   payer screen: Sending payment | Paid 5 USDC | to  | 0xB1124942BA3CEB48 | D87DAC9BABC50CA3B | 50A72DB
  PAID: payer cash 20 -> 15, payee holds the auth (EIP-712 recovers to payer), receipt verified on the payer
== tap 2: same tap again (the payee no longer serves the paid request)
  tap: card 04a1b2c3 in field
    reader > card 00a404000cf04c45444745524341534801
    reader < card 9000
    reader > card e011000000
    reader < card b006
  tap: card removed after 2 APDU(s)
  TAP_STATUS FAILED sw B006   payer screen: Reading request | Payee has no request
  NOTHING PAID: B006 payee has no request, cash still 15; the same request over USB PAY -> B004
== tap 3: payee pulled away while the review is on screen
  [payee] Request 3 USDC | For: tea | Reject | Approve
  [payer] Pay with | USDC cash | Swipe to review | Reject | 1 of 4
  [payer] Reject transaction? | Go back to transaction | Yes, reject
  tap: card 04a1b2c3 in field
    reader > card 00a404000cf04c45444745524341534801
    reader < card 9000
    reader > card e011000000
    reader < card 0000000000007a695fbdb2315678afecb367f032d93f642f64180aa3b1124942ba3ceb48d87dac9babc50ca3b50a72db00000000002dc6c0ffffffffffffffffa0584283746561000000000000000000000000000000000000000000d878fa9836f01456fe55a522a60121a2aa673abd62f2358c994af60cea7b122125bc714919fd264d4a0575fd0bbe0f1aa614e0f69b90cc73f3577467caa9087f1c9000
  [payer screen] Reading request | Pay with | USDC cash | Swipe to review | Reject | 1 of 4
  (payee pulled away while the review is on screen)
  tap: card removed after 2 APDU(s)
  TAP_STATUS FAILED sw B008   payer screen: Card removed | Nothing paid
  NOTHING PAID: B008 card removed before approval, cash still 15
== tap 4: payee pulled away after the payer signed (PUT_AUTH never arrives)
  tap: card 04a1b2c3 in field
    reader > card 00a404000cf04c45444745524341534801
    reader < card 9000
    reader > card e011000000
    reader < card 0000000000007a695fbdb2315678afecb367f032d93f642f64180aa3b1124942ba3ceb48d87dac9babc50ca3b50a72db00000000002dc6c0ffffffffffffffffa0584283746561000000000000000000000000000000000000000000d878fa9836f01456fe55a522a60121a2aa673abd62f2358c994af60cea7b122125bc714919fd264d4a0575fd0bbe0f1aa614e0f69b90cc73f3577467caa9087f1c9000
  [payer screen] Reading request | Pay with | USDC cash | Swipe to review | Reject | 1 of 4
  [payer screen] Pay | 3 USDC | To | 0xB1124942BA3CEB48 | D87DAC9BABC50CA3B | 50A72DB | For | tea | Reject | 2 of 4
  [payer screen] Cash left after | 12 USDC | Reject | 3 of 4
  [payer screen] Pay 3 USDC? | Reject | 4 of 4 | Hold to sign
    reader > card e0230000a146ce8565dd320e3764aa33cbda7024f469132354b1124942ba3ceb48d87dac9babc50ca3b50a72db00000000002dc6c00000000000000000ffffffffffffffff4ca3f8dae88cfd8146e3a76f788042dd0c6c933c16030de82bde1167de6b84ed1c84c529de672d0b07d1ef2805678598193ab4820878883b1ef95305386e4a8c9f42f169e59cf204672794ec812f673073ee49992468a9ffb17ad72664b9f01d08  (card pulled away, not delivered)
  tap: card removed after 2 APDU(s)
  TAP_STATUS SIGNED_NO_RECEIPT sw B008   payer screen: Sending payment | Signed 3 USDC | Card left after signing | Cash debited, no  | receipt
  SIGNED, NO RECEIPT: cash 15 -> 12 (debit before release), auth kept on the payer (TAP_STATUS)
== payee checks: high-s copy refused, a rejected new request clears the old one
  [payee] Request 7 USDC | For: cake | Reject | Approve
  high-s auth -> B005; SET_REQUEST rejected on screen -> GET_REQUEST B006 (old request gone)
  payee GET_AUTHS -> auths.json (1 auth)
== 3. chain (online, later): anyone settles the payee's auths
  balances before:
  0x46cE8565DD320e3764aa33cbdA7024F469132354 100.000000 USDC
  0xb1124942BA3CeB48d87Dac9baBc50ca3B50A72db 0.000000 USDC
  #0 success tx 0x9b0a092a816060bdbf13d7ee94dd2a2ddca687d70b120b145314b144a80af39d value 5.000000 USDC nonce 0x555d037bbd06edae5804ab22adb24caf51c893a6b55569a2fa7f702739ff9c47
     from 0x46cE8565DD320e3764aa33cbdA7024F469132354 100.000000 USDC -> 95.000000 USDC
     to   0xb1124942BA3CeB48d87Dac9baBc50ca3B50A72db 0.000000 USDC -> 5.000000 USDC
  0x46cE8565DD320e3764aa33cbdA7024F469132354 95.000000 USDC
  0xb1124942BA3CeB48d87Dac9baBc50ca3B50A72db 5.000000 USDC
  #0 REJECTED already used nonce 0x555d037bbd06edae5804ab22adb24caf51c893a6b55569a2fa7f702739ff9c47
ALL PASS
```

Two `[payer]` lines in tap 3 come from an extra check on the stage-B USB PAY path, run before the tap: a review
rejected on screen, which returns 6985. The 3 USDC from tap 4 is debited on the payer but never reached the payee, so
it is not in `auths.json`. That is the "signed, no receipt" case: the payer still holds the auth in RAM (`TAP_STATUS`)
until its next tap.

## What changes on real hardware

- **Sideload both apps.** Build `TARGET=flex` (or `stax` / `apex_p`; both compile) and load the app with `ledgerblue`
  (`loadApp`, or `runScript --scp` with `bin/app.apdu`). See research/custom-device-apps-bolos-speculos.md §4. The
  device warns that the app is not genuine. NFC must be on in Settings, and the app does not check that setting yet.
- **Speculos patch and relay go away.** On a device the MCU does what `speculos-nfc/seproxyhal.py` emulates (the ITC
  echo, NFC power, the RF field, a USB link next to card emulation), and the two antennas replace `relay.py`. The app
  code under the transport is the same. The app keeps `DISABLE_OS_IO_STACK_USE=1`, because the reader callbacks exist
  only in the app-side IO stack. app-security-key, the one NFC app Ledger ships, uses the same flag.
- **The host is optional.** On the payer, "Pay by tap" on the home screen starts the tap without USB. On the payee, a
  host is still needed for SET_CONFIG, SET_REQUEST and GET_AUTHS, because there is no on-device keypad flow for an
  amount yet. For the demo that is Ledger's USB or BLE link from a laptop or phone; over NFC the app refuses them.
- **Counterpart options for the payee side**, all answering the same APDUs (SELECT AID, `E011`, `E023`):
  1. **A teammate's NFC Ledger** (Flex, Stax or Apex P) running this same app.
  2. **The Android HCE payee app** in `mvp/android`. It uses the same AID, GET_REQUEST, PUT_AUTH and receipt, with a
     software key on the phone. It can also bridge to a Nano S Plus over USB OTG.
  3. **Tangem does not apply as a payee.** A Tangem card speaks only its own protocol: it can sign a digest, but it
     cannot hold a request, check an auth or sign a receipt. It can be something the payer *reads* (see `mvp/tangem`),
     never the shop.

## Hardware gates

These are not verified, and each one can break the real-device path. The order follows research/nfc-reader-mode.md §8.

1. **Reader gate.** Does the OS let a sideloaded app power the reader and deliver `CARD_DETECTED`? Nobody outside
   Ledger has shown it. NO-GO means fall back to the Android payee in card mode on the payee side, plus a USB or BLE
   host on the payer.
2. **Framing.** Do raw ISO 7816 APDUs go over the air between two Ledgers as `relay.py` assumes? The emulation passes
   raw bytes, and real ISO-DEP framing by the MCU is unknown. Flex-to-Flex may work even if Flex-to-phone needs
   different framing.
3. **Card-emulation AID routing.** Does the payee's OS route `SELECT F04C45...01` to the open app?
4. **Mode switch.** The payer does `io_nfc_reader_stop` then `os_io_nfc_cmd_start_ce` after every tap. Does that come
   back to card emulation without restarting the app?
5. **Timing.** The emulated field never drops during a 10-20 s review. Does a real field stay up while the payer
   reads the screen and holds to sign? If not, the flow must read the request, drop the field, review, then tap
   again to deliver PUT_AUTH.
6. **Size.** 159 and 166 bytes worked in emulation. The real limit is the 271-byte SEPH buffer, which this flow stays
   under.
7. **Media on a device.** The NFC allowlist keys on `G_io_app.apdu_media == IO_APDU_MEDIA_NFC`, which the SDK sets for
   every received APDU (`io_legacy/src/os_io_legacy.c`). In emulation, card APDUs arrive as NFC and host APDUs as USB;
   on a device the same is expected but not yet seen.

## Files

| Path | What |
|---|---|
| `demo.py` | The one-command end-to-end demo (asserts every step). |
| `app/src/cash.c` | The whole device app (payer and payee, USB and NFC). `app/test.py` is the stage-B USB test. |
| `speculos-nfc/` | Patched `seproxyhal.py` (NFC reader emulation, plus a USB host link on a `--transport NFC` instance), `relay.py` (the field; `tap(stop=, cut_ins=)`, `card_exchange()`), stage-A checks. |
| `settle/` | USDC look-alike (`src/USDC.sol`), `deploy.mjs`, `fund.mjs`, `settle.mjs`, `balances.mjs`, stage-C test. |
| `auths.json` | What the payee handed over in the last demo run (input to `settle.mjs`). |
| `screens/` | Screenshots of both devices from the last demo run. |
| `NOTES.md` | Integration and fix-stage notes: commands, decisions, what passed. |
