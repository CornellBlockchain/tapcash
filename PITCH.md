# Ledger Cash: pitch, demo plan, Q&A and submission drafts

Written 2026-10-10 (Saturday), before any hardware gate has run. Every claim below is limited to what the repo shows
today: `python -u demo.py` prints `ALL PASS` (two emulated Flex devices, emulated NFC field, settlement on a local
anvil chain) and `app/test_nano.py` prints `ALL PASS` (two emulated Nano S Plus over USB). Nothing has run on a real
device. Lines marked **[fill in after Gate N]** must be updated from `mvp/ledger-cash/HARDWARE.md` results before
they are said on stage or posted.

Wording rule for everything here: "cash" always means v0 of the [Cash ladder](mvp/ledger-cash/README.md#cash-ladder-device-capped-iou-v0-to-escrowed-cash-v2),
a device-capped spending limit. The shop receives a signed IOU, nothing is escrowed, and the shop cannot check
offline that the payer's USDC is still there.

Assumption to confirm: both presenters are in Paris. Presenter A is Sahas (narrates, runs the laptop). Presenter B is
the collaborator who owns the Flex (does the tap). If that changes, swap the names; the script does not depend on who
holds the device as long as it is someone who has rehearsed the tap.

---

## 1. The pitch

**One sentence.** Ledger Cash lets you pay in USDC by holding your Ledger Flex against the shop's device, with no
internet: the chip caps what it will spend, you approve the amount on the Secure Screen, and the shop gets a signed
IOU that anyone settles on-chain later.

**30 seconds, for someone who has never owned a wallet.**
> Your Ledger keeps your money safe, but it can't pay the person in front of you. You need a laptop or a phone, an
> app and a connection. We wrote a Ledger app that pays by touch. At home you set a spending limit on the device, say
> 20 dollars of USDC. At the market stall the seller's device shows "5 USDC, coffee". You hold your Ledger against it,
> read the amount on your Ledger's own screen, and hold to sign. The seller now has your signed promise to pay, and
> the next time anyone is online it turns into a real USDC transfer. The limit lives in the chip, so your Ledger will
> never sign more than you loaded. It works end to end in Ledger's emulator today; this week we find out what the real
> radio does.

---

## 2. Five-minute talk track (two presenters)

Target 270 s of talk, leaving 30 s of slack inside the 5 minutes. Slide numbers refer to section 3.

| # | Time | Who | Slide | What is said (close to verbatim) |
|---|---|---|---|---|
| 1 | 0:00-0:20 (20 s) | A | 1 | "A Ledger is the safest place to keep money, and it can't pay the person standing in front of you. Today paying from a Ledger means a laptop or a phone, a wallet app and a network. We made the Ledger Flex pay by tap, with no network on either side." |
| 2 | 0:20-0:45 (25 s) | A | 2, 3 | "Three steps. At home you fund a cash account and load a spending cap into the device: the Ledger confirms it on screen. At the till, the shop's device holds a signed request: 5 USDC, coffee. You tap, the request appears on your Secure Screen, you hold to sign. What the shop holds is a signed USDC authorization, an IOU. Later anyone online submits it and the USDC moves." |
| 3 | 0:45-1:55 (70 s) | B does the tap, A narrates | 4 | **Live path (Gate 2 passed):** B arms the phone ("1 USDC, coffee"); A runs `hw.py tap` so the terminal shows each state; B holds the USB-tethered Flex to the phone. A, on the camera feed: "The Flex is now an NFC reader. It reads the shop's request and checks the shop's signature inside the chip. Pay 1 USDC, To this address, which matches the phone, For coffee, Cash left after 9. B holds to sign. The chip debits the cap before the signature leaves the device, then hands it over. The phone checks it and sends back a signed receipt: Paid." Then A settles `tap-auth.json`, which `hw.py` wrote on PAID: "Back online: one call, and 1 USDC moves. The phone can export the same authorization; anyone can submit it." **Fallback (no Gate 2):** play the video from 0:13 to 1:13 with sound off, A narrates the same lines and says first: "This is Ledger's own emulator, two Flex devices, with the NFC field emulated by our patch." |
| 4 | 1:55-2:25 (30 s) | A | 5 | "What it refuses matters more. Tap the same shop again: Payee has no request, nothing signed. Pull the phone away before you approve: Card removed, nothing paid. Pull it away after signing: the cap was already debited, so you can't sign the same money twice, and the signed authorization can still be read off the payer over USB until its next tap. Settle the same authorization twice: USDC itself rejects it. And a stranger's reader in range can't read your balance or push a payment onto your screen." |
| 5 | 2:25-3:00 (35 s) | B | 6 | "Who decides what. The chip, on its own: checks the shop's signature, the network, your cap and replays, and debits before release. No host can override that. The human, on the Secure Screen: approves loading the cap, and reads Pay, To, For, Cash left after, then holds to sign. Settlement is the only step software does alone, and it holds no key: it can only submit what you signed. Shops propose, humans approve, the chip enforces the cap. There is no AI agent in this build. If we add one, it goes on the shop's side: a clerk that settles and reconciles IOUs and never signs." |
| 6 | 3:00-3:35 (35 s) | B | 8 | "Why this is new for Ledger. The Flex SDK has had an NFC reader API since December 2024. Ledger's own engineer wrote that no production app uses it, and we found no third-party app that does. Third-party card emulation exists; reader mode we did not find. Speculos couldn't emulate it, so we patched it: two emulated Flex devices tap each other with real multi-chunk APDUs. Our DX write-up has 15 findings on this path and one ask: a reader example app." |
| 7 | 3:35-4:15 (40 s) | A | 7 | "Honest limits. This is rung one of three. The cap protects the payer from overspending; it gives the shop no guarantee. The shop can't check offline that the USDC is still there, and the owner could sign with the same key outside our app. Rung two, attestation, is built in emulation, and we found that BOLOS lets any app on the device forge it; it needs an OS-level fix before it can protect a shop. Rung three is escrow, so the note pays out without trusting the payer. To ship this, Ledger would need attestation for third-party apps and a documented NFC permission for apps." |
| 8 | 4:15-4:30 (15 s) | B | 9 | "Hardware so far: **[fill in after Gates 1-3, one sentence]**. Everything else, the code, the emulator patch, the checklists and the video, is in the repo. Thank you." |

Sum: 20 + 25 + 70 + 30 + 35 + 35 + 40 + 15 = 270 s.

Beat 8 variants, pick one on Monday night:
- Gate 2 passed: "A real Flex paid a real Android phone over NFC this week, and that authorization settled on-chain."
- Gate 1 passed, Gate 2 not: "The Flex reader powers on and reads a bank card from a sideloaded app; the phone side isn't solid yet, so the full tap you saw is emulated."
- Gate 1 failed: "On the real Flex, the OS did not deliver card events to our sideloaded app. That is a finding for Ledger, and it's in our DX write-up. The full tap you saw is emulated."

---

## 3. Slides (9)

Flex screenshots are 480x600; show them at least 40% of slide height or nobody past row three can read them. All
paths are under `mvp/ledger-cash/`. Video timestamps refer to `video/ledger-cash-demo.mp4` (83.5 s):
0:00 title card, 0:06 load, 0:13 request, 0:20 tap reads, 0:29 Secure Screen review and hold to sign, 0:43 signed
IOU, 0:50 tap again refused, 0:58 settle, 1:06 settle twice rejected, 1:13 honest-limits card.

**Slide 1: title**
- Title: `Ledger Cash`
- Subtitle: `Tap your Ledger to pay in USDC. No signal needed.`
- Small: `A device-capped USDC spending limit on the Ledger Flex. Signed on the Secure Screen, settled on-chain later.`
- Footer: `[Team name] · [Club name] · N3XT @ OP3N 2026 · #LedgerN3XTCollab`
- Image: `screens/13-payer-tap1-hold-near.png` ("Hold near the payee").

**Slide 2: the gap**
- Title: `A Ledger can't pay the person in front of you`
- Left column, `Today`: `Ledger + laptop or phone + wallet app + network`
- Right column, `Ledger Cash`: `Hold your Flex near the shop's device. Read. Hold to sign.`
- Bottom line: `Works with no network on either side. Settles when anyone is back online.`

**Slide 3: how it works**
Four boxes left to right, each with its image:
1. `Load` / `Fund the cash account on-chain. The device confirms a spending cap.` / `screens/07-payer-load-cash.png`
2. `Request` / `The shop signs "5 USDC, coffee".` / `screens/12-payee-ready.png`
3. `Tap and approve` / `Pay, To, For, Cash left after, then Hold to sign` / `screens/17-payer-tap1.png`
4. `Settle later` / `Anyone submits the signed authorization. USDC moves.` / terminal excerpt from `demo-run.log`:
   `#0 success ... value 5.000000 USDC` and `to 0xb112... 0.000000 USDC -> 5.000000 USDC`
- Footer, small but present: `After the tap the shop holds a signed IOU (USDC EIP-3009 authorization), not money.`

**Slide 4: demo**
- Live: full-screen camera feed of the Flex and the phone. Corner label: `Live: Ledger Flex pays an Android phone over NFC`.
- Fallback: the video, 0:13 to 1:13. Corner label: `Recorded in Speculos: two emulated Ledger Flex, NFC field emulated by our patch`.
- No other text on this slide.

**Slide 5: what the chip refuses**
- Title: `What it refuses`
- Four images in a row with a caption under each:
  - `screens/27-payer-tap2-again-end.png`: `Same request again: "Payee has no request". Nothing signed.`
  - `screens/38-payer-tap3-pulled-end.png`: `Pulled away before approval: "Card removed / Nothing paid".`
  - `screens/50-payer-tap4-cut-end.png`: `Pulled away after signing: debited before release, authorization kept.`
  - Terminal line: `#0 REJECTED already used`: `Same authorization settled twice: rejected by USDC.`
- Bottom: `Over NFC the app only answers as a payee. Balance, pay and load commands from a stranger's reader: 6D00.`

**Slide 6: who decides what**
- Title: `Shops propose. Humans approve. The chip enforces the cap.`
- Three columns:
  - `The chip, on its own`: `Checks the shop's signature, network, cap and replays` / `Debits before the signature leaves` / `Refuses host commands over NFC`
  - `The human, on the Secure Screen`: `Approves the network and the cap` / `Reads Pay, To, For, Cash left after` / `Matches To with the shop's screen, holds to sign`
  - `Anyone online, holding no key`: `Submits the signed authorization` / `Can't change amount, payee or nonce` / `Can't settle it twice`
- Bottom, smaller: `AI: none in this build. Proposal: a shop-side settlement clerk that settles and reconciles IOUs and never signs.`

**Slide 7: the cash ladder**
- Title: `Three rungs. This build is the first.`
- Table:

  | Rung | The shop holds | What makes it hold | Status |
  |---|---|---|---|
  | v0 device-capped cash | A signed IOU | The app caps and debits what it signs | Runs in emulation |
  | v1 attested | The same IOU + a slot-1 endorsement signature | BOLOS endorsement over the app code hash | Emulated; forgeable by any app on the device (see README) |
  | v2 escrowed | A note redeemable from on-chain escrow | USDC locked to the device key | Not built |
- Bottom: `v0 is a spending cap, not escrow. Until settlement the shop carries the credit risk.`

**Slide 8: new for Ledger**
- Title: `No third-party NFC reader app found before this one (our search)`
- Bullets:
  - `Ledger's SDK has had an NFC reader API since Dec 2024 (PR #777). No production app uses it (Ledger engineer, PR #1243). We found no third-party app that does.`
  - `Third-party card emulation already exists (structured-passkeys, Oct 2026). Reader mode we did not find.`
  - `Speculos had no reader mode. Our 168-line patch lets two emulated Flex devices tap each other.`
  - `DX feedback: 15 findings on this path. One ask: an NFC reader example app.`
- Image: the reader/card ASCII diagram from `mvp/ledger-cash/README.md`, redrawn as two device outlines with the four APDUs (SELECT, GET_REQUEST, PUT_AUTH, receipt).

**Slide 9: status and asks**
- Title: `What it would take to ship`
- Left, `Hardware status`: **[fill in after Gates 1-3, max three lines]**
- Right, `What Ledger would need`: `Attestation provisioning for third-party apps on retail devices` / `Reader API docs and an NFC permission for apps` / `Reader mode in Speculos (our patch is a start)`
- Footer: `github.com/Sahas266/ledger-op3n-n3xt-hackathon-26 · demo video [link] · DX-FEEDBACK.md`

---

## 4. Demo plan

### Decide by Monday 12 October, 22:00 CEST
| Result of `HARDWARE.md` | Stage plan |
|---|---|
| Gate 2 PAID (Flex paid the Android phone) and Gate 3 settled | Live tap, with the video ready on a second tab |
| Gate 1 GO, Gate 2 not solid | Video for the tap; real Flex on USB (`hw.py selfpay`) only if it has been run and rehearsed |
| Gate 1 NO-GO | Video only, plus the gate result stated as a finding |
| Paris-only bridge (section C: Flex pays the Nano through the phone) | Use live only if it worked in a rehearsal in Paris before the finals. It has never run on hardware |

### Live path (Flex + Android on stage)
Set up before the slot, on the laptop that will be on stage:
1. anvil running locally (`lc-anvil`, see `HARDWARE.md` B8 Option A), token deployed, Flex cash account funded with
   10 USDC. Local anvil, not Base Sepolia: venue Wi-Fi is not a dependency. If Gate 3 Option B ran, put its Basescan
   link on slide 9 instead of settling live on testnet.
2. Flex: Ledger Cash open, configured for anvil, cap loaded (`hw.py setup anvil 10`), NFC on, battery charged,
   Ledger Wallet quit on the laptop.
3. Phone: Ledger Cash Payee in front, screen on and unlocked, NFC on, case off, auto-lock disabled for the session.
   Mark its NFC spot with a small sticker so B does not search for it on stage.
4. A camera on the Flex screen and the phone (a document camera, or a phone on a stand fed to the projector). The Flex
   E Ink screen is unreadable from the jury table otherwise. Test the feed in the room.
5. A terminal ready to run `hw.py tap` (the Flex stays on USB), and a second one with `node settle.mjs ../tap-auth.json`
   typed in `settle/` and not run. `hw.py` writes `tap-auth.json` on PAID, so the phone-to-laptop transfer is off the
   critical path.
6. The video open in a second tab, cued to 0:13.

On stage: B arms 1 USDC "coffee". A runs `hw.py tap`. B places the tethered Flex on the sticker and keeps it still
until "Paid". A narrates beat 3, then runs the settle.

### If NFC fails mid-demo
One retry at most. The second failure goes to the video, with no apology beyond one sentence.

| What the Flex shows | Say | Do |
|---|---|---|
| Stuck at "Hold near the payee" for 10 s | "The radio didn't see the phone. Here is the same flow recorded." | Cancel, switch to the video at 0:13 |
| "Card removed / Nothing paid" | "That's the safety path: the field dropped before I approved, so nothing was signed and nothing was debited." | Re-arm is not needed (the request is still payable); retry once |
| "Signed 1 USDC / Card left after signing / Cash debited, no receipt" | "This is debit before release. The chip took the 1 USDC off the cap before the signature left, so it can never be spent twice. The signed authorization is still in the payer's memory." | Run `hw.py status` before anything else (the auth is in RAM until the next tap or app exit); it writes `tap-auth.json`; settle that file. This turns the failure into beat 4 |
| "Payee did not answer" (B009) | "The phone was too slow to answer. Here is the recorded flow." | Switch to the video |
| "Payee has no request" (B006) | "The phone isn't armed; that's the refusal you'll see in a moment anyway." | Re-arm once and retry |
| Anything else, or USB stops answering | "Recorded flow." | Video |

### Fallback (video and USB-only devices)
- Video: `mvp/ledger-cash/video/ledger-cash-demo.mp4`, 83.5 s, 1080p. Play 0:13 to 1:13 with sound off (there is no
  audio track) and narrate beat 3. Skip the title card and the end card; slide 7 covers the limits. The video's own
  footer says it is emulated, and A says so before pressing play.
- USB on real devices, only what has actually run (from `HARDWARE.md` A7 and the fallback section): `hw.py selfpay`
  on the Nano S Plus or the Flex shows the real Secure Screen review, the debit, `B004` on replay and the IOU screen.
  If shown, say "over USB" every time; it is not a tap.
- Rehearse the fallback on the stage laptop. `demo.py` takes about a minute and runs containers one at a time for
  RAM, so do not run it live; the video is its record.

---

## 5. Q&A prep (15 questions)

Juror in brackets is who is most likely to ask. Answers are written to be said in under 30 seconds.

**1. What stops me paying two shops with the same money before either settles? [Mathias, Breeding]**
On one device, the app does: every payment is debited from the cap before its signature leaves the chip, so
everything one device's app signs adds up to at most what was loaded. What it doesn't stop: loading more than the
account holds, loading the same seed on a second device, reinstalling the app to reset the counter, or signing with
the key outside our app. So the shop holds an IOU that can bounce at settlement. That is rung v0. Escrow (v2) is what
closes it, and we haven't built it.

**2. What stops the owner sideloading another app that declares the same derivation path? [Mathias]**
Nothing in v0, and we say so in the README. The cash key is on a dedicated path, `m/44'/1279476051'/0'/0/0`, which the
stock Ethereum app and the other chain apps can't derive. But the OS binds a path to whichever app declares it, not to
our code, and the seed could also be imported into a software wallet. Closing that needs attestation: BOLOS endorsement
signs over the running app's code hash, so the shop could check the IOU came from our app. That's rung v1.

**3. Why not just a phone wallet? [Rogers, Mathias]**
A phone wallet could sign the same authorization offline. The difference is where the limit and the approval live. On
a phone, the cap is app code on an OS that can be updated remotely, and the screen is drawn by that OS. Here the cap,
the debit and the review run in the secure element and the Secure Screen, and the payer needs no phone or laptop at
the till. Attestation (v1) only means something if the counter runs in a secure element.

**4. Why NFC on a hardware wallet? [Rogers, Mo]**
Because a tap carries intent: a few centimetres of range, no pairing, no cable. Bluetooth on the Flex needs bonding
first. The Flex already has the radio, and Ledger ships both halves in its own products: the Security Key app does
card emulation, and the Recovery Key is read by the Flex in reader mode. Only Ledger's own firmware uses the reader
today; we're asking for third-party apps to be able to.

**5. Isn't offline settlement risky for the shop? [Breeding]**
Yes, and the shop's screen says so: "Signed IOU ... Not settled yet", never "Received". The risks are an unfunded or
double-spent payer, the shop's device keeping only its last 8 authorizations, and no expiry (the device has no trusted
clock). Mitigations in v0: settle as soon as anyone is online, and settlement needs no key, so a relayer or the shop's
phone can do it. Payer and shop both pay no gas to sign.

**6. Why USDC, and what about Arc? [Breeding]**
USDC has EIP-3009 built in: a signed `TransferWithAuthorization` that anyone can submit, which is exactly what an
offline payment needs, and it's the same authorization x402 payments carry. The app hardcodes the domain name "USDC",
version "2". Our research read those values on Base Sepolia, Arc testnet and Arc mainnet, and the EIP-3009 value is
6-decimal on Arc too. We verified the Base Sepolia domain separator against the live contract, and a dry-run settle
reached it. We have not run on Arc yet: it needs a SET_CONFIG approved on the device and Arc's RPC and token for the settle script. With sub-second finality, Arc shortens
the window where the shop carries the IOU.

**7. What about privacy? [Mo, Rogers]**
The tap itself touches no server: no Ledger backend, no RPC. Over NFC, the payer's app answers nothing but payee
commands, so a stranger's reader can't read the balance. What leaks: while a request is armed, any reader in range can
read it (address, amount, label); the shop learns the payer's cash-account address; and settlement is a normal public
USDC transfer linking the two addresses. Offline it behaves like paper money. On-chain it's as public as any USDC
transfer.

**8. What would Ledger need to ship this for real? [Mathias, Rogers]**
Three things. Attestation for third-party apps: endorsement provisioning on retail Flex and Nano S Plus, which our
source audit thinks the stock tool can't do on those devices (inferred, not tried). A documented reader API and an NFC
permission model: today `io_nfc_reader_start` returns true even if NFC is off, and we don't know if the OS lets a
sideloaded app power the reader at all (that's our Gate 1). And app signing or listing, so the payer doesn't see the
"not genuine" warning. Then escrow on the Circle side for v2.

**9. Tangem, the digital euro and Coldcard do NFC already. What's new? [Rogers, Breeding]**
In Tangem and Coldcard the hardware is the passive tag and the phone is the reader that shows and sends. Here the
hardware wallet is the reader: it reads the request, shows it on its own screen and signs. The digital euro's offline
mode, as the ECB has described it (verify before Paris), is issuer-provisioned secure hardware holding real offline value with holding
limits; ours is a signed IOU on a public chain with no issuer, which is why we call it rung v0. See the table in
section 6.

**10. Your app shows a "not genuine" warning. Doesn't that undercut the trust story? [Mathias, Rogers]**
It does, for the shop. Genuine Check proves the device and OS are Ledger's; it says nothing about a sideloaded app.
The payer installed the app themselves and sees the warning, so they know what they're running. The shop has no way
to tell what the payer runs, which is why the shop's screen says IOU. Three things stand between us and fixing it:
the sideload warning, endorsement provisioning on retail devices (source audit M01), and whether a sideloaded app
may use the reader at all (Gate 1).

**11. The brief asks for AI. Where is it? [Mo, Rogers]**
There's no AI agent in this build, and we won't pretend there is. We spent the week on the signer: a Ledger Signer use
case where the human approves every payment on the Secure Screen. Our proposal, not built: a shop-side settlement
clerk. It pulls the authorizations, checks each one and the payer's on-chain balance, settles through a relayer,
reconciles receipts, flags IOUs at risk, and answers "who still owes me". It holds no signing key, and it can't change
an authorization, because the payer's signature covers every field. The cap mechanism also generalises: a spending cap
enforced inside the chip is a building block for the per-period caps in your Agent Policies roadmap, enforced in a device app.

**12. Why a custom app instead of the stock Ethereum app? [Mo]**
Three reasons. The stock app can't use NFC reader mode. It has no cap, so nothing would stop it signing past the
loaded amount. And it can sign for `44'/60'`, so a cap kept outside it would be meaningless. Our app may derive only
the cash path, and the Ethereum app can't derive that one. Side benefit: we sign EIP-3009 ourselves, so the stock app's
gating interstitial on mainnet USDC authorizations never appears.

**13. I lose my Flex with a cap loaded. What happens? [Mathias]**
The finder needs the PIN. The USDC stays on the cash account, which the seed controls, so restoring the seed on
another device gets it back; the cap counter lives in the app and restarts at zero. Authorizations already handed to
shops still settle, because they're signed. Revoking one before it settles means moving the USDC out first, which
makes it bounce; that's the same IOU risk as question 1.

**14. Four review pages on the payer and a laptop on the shop side. Is that the UX you'd ship? [Mathias]**
No. The payer review is the standard Ledger review: Pay with USDC cash, then Pay, To and For, then Cash left after,
then Hold to sign. It could collapse to two pages. The shop side needs a host today only because the app has no amount
entry; the SDK has an opt-in keypad (`ENABLE_NBGL_KEYPAD`) and QR on the Flex, which make the shop's Ledger a
standalone till. Built and emulated: the on-device till (keypad, label list, Approve) and a settlement QR on the
Flex (`till_demo.py`); untested on hardware.

**15. What has actually run on hardware? [all]**
**[fill in after Gates 1-3.]** As of Saturday: nothing. The full tap runs in Speculos on two Flex devices with our NFC
patch, the Nano S Plus build passes its own emulated test, CI reproduces the Flex and Nano S Plus builds from the pinned image (re-check the run after the push), and
`HARDWARE.md` has the gate checklists we ran this week. Any gate that failed is in DX-FEEDBACK as a finding.

Other short answers to have ready:
- *Which Ledger tool did you actually use? [Mathias, Mo]* The Ledger Secure SDK, one layer below DMK: the Signer is
  the primitive, implemented in C on the secure element, with its own Secure Screen review. DMK, wallet-cli and Key
  Ring were not options for the tap, because no host SDK has an NFC transport (we checked device-sdk-ts and
  ledger-live). Ledger tooling we did use: the app builder image, Speculos and ledgerblue.
- *Why C, when Rust is the default for new apps?* The Rust SDK has no `lib_nfc` and no reader bindings.
- *Size limits?* Reader replies over 271 bytes are dropped by the SDK; our largest message is 166 bytes.
- *How does the payer know the shop is who it says?* Visually: the payer matches the "To" address with the address on
  the shop's screen. The request signature proves integrity, not identity.
- *Is the Speculos patch upstreamable?* It's 168 lines against a pinned Speculos build; we can open the PR.

---

## 6. Prior art

Searches: about 70 Ledger hackathon projects (ETHOnline 2026, ETHGlobal NYC and Cannes 2026, Ledger's June 2026 Build
& Show) and public code search for the SDK's reader symbols (`research/prior-art-hackathon-projects.md`,
`research/nfc-reader-mode.md` §6). Private apps cannot be ruled out.

| Prior art | What it does | How Ledger Cash differs |
|---|---|---|
| Tangem cards | The card holds a key and signs; the phone is the NFC reader, shows the transaction and broadcasts | Here the hardware wallet is the reader and has its own screen and cap. Tangem stays out of our app (licence question pending) |
| COLDCARD NFC | The device is a dynamic NFC tag (ST25DV); a phone reads a PSBT or address from it | Same split: the device is passive, the phone reads. No device-to-device payment |
| Ledger Security Key app | Card emulation for FIDO2 over NFC (the only NFC app Ledger ships) | We use card emulation for the payee and reader mode for the payer |
| Ledger Recovery Key | The Flex reads Ledger's own JavaCard, in BOLOS firmware, not an app | We use the app-level reader API to read a third-party device |
| structured-passkeys (PR #20, 2026-10-04) | Third-party CTAP over NFC on Stax, Flex and Nano Gen5, card emulation only, on a forked Rust SDK | Reader mode, in C; "first third-party NFC app" would be false, "first third-party reader app" is not found in our search |
| Cypherock X1, OneKey Pro | Screened devices that read only their vendor's own paired cards | We read any device that answers our AID: another Ledger or an Android phone |
| Digital euro offline mode (ECB proposal; general knowledge, **not in our research notes, verify before it goes on a slide**) | Offline person-to-person payments on secure hardware, with holding limits and cash-like privacy, issued and provisioned by the central bank | Ours is a signed IOU on a public chain with no issuer. Their model is close to our v1 + v2 rungs |
| Hackathon projects: Tap Pay (two Android phones over NFC), Blee (BLE mesh, EIP-3009 pre-signed), MelodyPay (ESP32 over audio), Tappy (NFC sticker plus Flipper Zero) | Offline or proximity USDC payments without a Ledger | Zero of the ~70 Ledger hackathon projects we found used Ledger NFC |

Claim to make: **Ledger Cash is the first third-party app using the Flex NFC reader API that we found in our search.**
Also, carefully: our Speculos patch is the first emulation of Ledger reader mode we found; stock Speculos exits on the
first reader call.

---

## 7. Submission checklist

### Blockers (do these before the form)
- [ ] **Tangem licence decision** (`research/tangem-protocol.md` §0). `mvp/tangem/` is tracked. If the repo goes
      public, either decide it may stay, or remove it from the branch being submitted. Decide before going public.
- [ ] **Repo access.** The repo is private. Make it public, or confirm the form accepts a private repo with jury
      access. Merge `ledger-cash` into `main`, or link the branch directly:
      `https://github.com/Sahas266/ledger-op3n-n3xt-hackathon-26/tree/ledger-cash`.
- [ ] **Root README.** It still describes the exploration repo and says "Nothing here has touched a real device yet".
      Lead it with Ledger Cash and link `mvp/ledger-cash/README.md`, `HARDWARE.md`, `DX-FEEDBACK.md` and the video.
- [ ] **Demo video hosted.** Upload `mvp/ledger-cash/video/ledger-cash-demo.mp4` (YouTube unlisted or similar). If
      Gate 2 passes, record a phone video of the real tap and add it; keep the emulated one, labelled.
- [ ] **Open the form on Monday** (`https://forms.gle/TcmwuFQMGfyEcuNd6`) and map the drafts below to its real fields.
- [ ] **Hardware lines.** Replace every **[fill in after Gate N]** in this file and in the README status line.
- [ ] **Club name and team members** (not found in the repo).
- [ ] **No AI attribution** anywhere that gets pushed or posted: commits, README, form, posts.
- [ ] **Eligibility.** Ask a mentor on Monday whether a custom device app with no DMK, wallet-cli or Key Ring call
      counts as "an AI-powered use case built around a Ledger Signer", and whether the missing AI part costs points.
- [ ] **Re-check quoted output.** `app/Makefile` and `app/src/cash.c` are being changed by another track. After it
      lands, re-verify every screen string, `demo-run.log` excerpt, screenshot filename and video timestamp quoted in
      sections 2, 3 and 4 against the final `demo-run.log`, `screens/` and video.
- [ ] **Verify the digital-euro row** in section 6 against an ECB source before it goes on a slide, or drop it.
- [ ] **Name.** "Ledger Cash" uses Ledger's trademark. Fine for a Ledger hackathon, but ask a mentor whether they
      prefer a different name for anything published beyond it.
- [ ] Submit by Tuesday 13 October 20:00 CEST (deadline 23:59). One submission; edit the response, don't resubmit.

### Form drafts

**Project name:** Ledger Cash

**One-liner:** Pay in USDC by tapping your Ledger Flex on the shop's device, offline: the chip enforces a spending
cap, you approve on the Secure Screen, and the shop gets a signed IOU anyone settles on-chain later.

**Description:**
> Ledger Cash is a C device app for the Ledger Flex (with a USB-only build for the Nano S Plus) that pays in USDC by
> NFC tap, with no network on either side. The owner funds a dedicated cash account and loads a device-capped
> spending limit, confirmed on screen. At the till, the payer's Flex switches to NFC reader mode, reads a payment
> request signed by the payee's device (another Ledger in card emulation, or our Android payee app), verifies it in the
> chip and shows Pay, To, For and Cash left after on the Secure Screen. On hold to sign, the app debits the cap first,
> then signs a USDC EIP-3009 TransferWithAuthorization and hands it over NFC; the payee checks it and returns a signed
> receipt. Later anyone online settles it on-chain.
>
> What the payee holds is a signed IOU, not escrowed money (v0 of a three-rung ladder; attestation and escrow are the
> next rungs). It runs end to end in Speculos, with our patch adding NFC reader emulation, and settles on a local
> chain; `python demo.py` prints ALL PASS. Hardware status: [fill in after Gates 1-3]. As far as our search found, it
> is the first third-party app to use the Flex NFC reader API, which has been in Ledger's SDK since December 2024.
>
> Human and automatic, named: the chip on its own checks the request, enforces the cap and debits before release; the
> human approves the cap and every payment on the Secure Screen; settlement is the only step software does alone, and
> it holds no key. There is no AI agent in this build; a shop-side settlement assistant that never signs is our
> proposed next step.

**Pre-existing code disclosure:**
> Nothing of ours existed before the kickoff (7 October, 15:00 CEST); the repository's first commit is 10 October.
> We build on open-source code we did not write: the LedgerHQ app-boilerplate (Apache-2.0) as the device app skeleton,
> ledger-secure-sdk, Speculos (we ship a patched copy of its `seproxyhal.py` and the diff), ledgerblue, viem,
> eth-account, Foundry (anvil) and the standard Android/Kotlin toolchain. The USDC test token is our own minimal
> contract written to match Circle's FiatTokenV2_2 `transferWithAuthorization` behaviour.

**GitHub:** `https://github.com/Sahas266/ledger-op3n-n3xt-hackathon-26/tree/ledger-cash` (or `main` after the merge;
start at `mvp/ledger-cash/README.md`)

**Demo video:** `[hosted link]`

**DX feedback:** `https://github.com/Sahas266/ledger-op3n-n3xt-hackathon-26/blob/ledger-cash/DX-FEEDBACK.md`
(section 11 and "One concrete suggestion" are this project's).

### Social posts (from the club account)

**X (under 280 characters; X counts any link as 23):**
> We built Ledger Cash: tap your @Ledger Flex on a shop's device to pay in USDC, no signal needed. The chip caps
> spending, you approve on the Secure Screen, the shop gets a signed IOU that settles on-chain later. #LedgerN3XTCollab
> [repo link]

If Gate 2 passed, replace the second sentence's ending with: "First real tap: a Flex paid an Android phone." Recount
before posting.

**LinkedIn:**
> For the N3XT hackathon with @Ledger, [club name] built Ledger Cash: a way to pay in USDC by tapping your Ledger
> Flex on the shop's device, with no internet on either side.
>
> You load a spending cap into the device at home. At the till, your Flex reads the shop's signed request over NFC,
> shows the amount and the payee on its own Secure Screen, and signs only after you hold to confirm. The chip debits
> the cap before the signature leaves, so it can never sign more than you loaded. The shop receives a signed USDC
> authorization, an IOU, and anyone can settle it on-chain once they are back online.
>
> We are upfront about what this is: a device-enforced spending cap, not escrow. The shop carries the risk until
> settlement, and the next steps are device attestation and on-chain escrow.
>
> The Flex SDK has had an NFC reader API since December 2024, and we found no third-party app using it. We also
> patched Ledger's emulator so two Flex devices can tap each other, and wrote up what was hard about building on it.
> Hardware status: [fill in after Gates 1-3].
>
> Code, demo video and developer feedback: [repo link] [video link]
>
> #LedgerN3XTCollab
