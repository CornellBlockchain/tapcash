# Fix stage notes (2026-10-10, after the security and repro reviews)

Status: **PASS.** Clean rebuild (`rm -rf app/build app/bin app/debug auths.json __pycache__`, then the build below:
exit 0, 0 warnings, about 18 s), then `python -u demo.py > demo-run.log 2>&1`: exit 0, `ALL PASS`, 65-66 s. Three runs
after the C fixes all passed; only the last has the final cash.c (the first two still had the payee-home tagline bug
described below, which no assert covers: it was caught from the screenshot). The last run is pasted in README.md and
kept in `demo-run.log`. No lc-* containers were left. Nothing committed. Backups of every pre-fix file:
scratchpad `lc-f-backup/`.

Final ELF: `app/build/flex/bin/app.elf`, built from the final cash.c.

## Findings -> changes

High:
- **Debit trap (payee kept serving a dead request).** `g_req_set` deleted; `GET_REQUEST` serves `g_req` only while
  `g_req_valid`, else `B006`. `g_req_valid` is cleared by payment (as before), by any `SET_REQUEST` (kept at the start
  of `set_request`, so a rejected one also drops the old request) and now by an approved `SET_CONFIG`. Demo tap 2 now
  ends `B006` "Payee has no request" with the cash unchanged; the payer's own `B004` is still shown via a USB PAY of the
  same request. New demo check: a `SET_REQUEST` rejected on screen makes `GET_REQUEST` return `B006`.
- **"Received" proved nothing.** Payee screen now `Signed IOU for X\nfrom 0x...\nNot settled yet`. README has an
  **Honest limits** section stating that any key can produce an auth the payee accepts, and that the cash rules
  protect only the payer's own spending; the "Cash semantics" heading says so too.

Medium:
- **High-s accepted.** `put_auth` refuses `s > n/2` (`SECP_N_HALF`, memcmp) with `B005` before the EIP-712 recovery.
  Demo check: tap 4's auth with `(r, n-s, 55-v)` still recovers to the payer under eth_account (so only the new rule can
  reject it) and `PUT_AUTH` returns `B005`; `GET_AUTHS 1` stays `6A88`.
- **Request repeats after a wipe.** `reqNonce = cx_rng_u32()`; `NV.req_nonce` removed from `storage_t` (NVM layout
  change, fine for v0). Request, payee signature, auth nonce and tx hashes now differ on every run.
- **Every INS worked over NFC.** `dispatch` refuses anything but SELECT, `GET_REQUEST` and `PUT_AUTH` when
  `G_io_app.apdu_media == IO_APDU_MEDIA_NFC` (`6D00`), placed after the CLA check and before the GET_BALANCE /
  TAP_STATUS exemptions. The emulated payee runs `--transport NFC`, so every REST `/apdu` used to arrive as NFC: the
  advisor suggested a compile-time opt-out, but a 10-line addition to `speculos-nfc/seproxyhal.py` was smaller and keeps
  the guard tested. On a `--transport NFC` instance the patch builds a second (HID) transport, routes `USB_CONFIG` /
  `USB_EP_PREPARE` to it, and `to_app()` sends `USB!`-prefixed packets over it. `app/test.py` `Dev` gained
  `prefix = b""`; `demo.py` sets `b"USB!"` on the payee. Demo check over the RF port (`rf()` via `relay.card_exchange`):
  SELECT 9000, GET_REQUEST returns the request, and GET_BALANCE, TAP_STATUS, GET_AUTHS, PAY, LOAD_CASH, SET_CONFIG,
  TAP_TO_PAY all `6D00`.
- **Payee identity.** Payee home: `Receive 5 USDC to\n0x9858...EDA94`. README now says the request signature gives
  integrity and receipt binding only, and the payer must match the address visually. Gotcha hit: the SDK `snprintf`
  silently drops everything from `%.6s` on (first two runs showed only "to"); `%.*s` works.
- **Repro: unpinned images.** demo.py, app/test.py and speculos-nfc/run.sh pin
  `ghcr.io/ledgerhq/speculos@sha256:028d1e368244631578537e7ca50b6f13ca2932b5f3fd220627289b559c07a886` and
  `ghcr.io/foundry-rs/foundry@sha256:0c00cb0bda1ab1b91c9a6bf60f4c76c09c1a8870824b6d4718afbabacf6f9a17` (both equal to
  the local `:latest` RepoDigests). `seproxyhal.patch` regenerated with `diff -u` against that image's original file;
  before my change the old patch matched it exactly.
- **Repro: undocumented prerequisites.** README lists the three `docker pull`s, ports 8545 and 16000-16011, and that
  `eth_utils` comes with `eth-account`.

Low, taken because they were one-liners: SET_CONFIG shows the full u64 chain ID (`format_u64`; was `%u` of a cast);
`config_choice` clears `g_req_valid` (also closes "verifies under NV, not g_req's network"); `put_auth` signs the
receipt before the NVM writes; README runtime "about 1 minute"; README TAP_STATUS wording (RAM only); recording note on
varying lines; root `.gitignore` gained `__pycache__/` and `!mvp/ledger-cash/**/*.log` (checked with
`git check-ignore -v`). Low, documented under README Honest limits instead: no TAP_WAIT timeout, ring of 8 overwrites
silently, domain name fixed to "USDC", no on-device Resend.

`app/test.py` (stage B) was not re-run (it starts two containers at once). Its asserts were kept correct by hand:
`reqNonce == 1` became "differs from the first request", `IMAGE` pinned, `prefix` added (default empty).

---

# Integrate stage notes (2026-10-10)

> Superseded where it conflicts with the fix-stage notes above: GET_REQUEST no longer serves a paid request, the payee
> screen says "Signed IOU", tap 2 is B006, the demo takes about 1 minute.

Status: **PASS.** `python demo.py` printed `ALL PASS` on three runs; the last run used the final demo.py. The full verbatim output of the last run
is in README.md. A local copy is in `demo-run.log`. Nothing is committed. No
containers were left running.

## What changed

`app/src/cash.c` (stage B's file; the original is backed up in the scratchpad as `lc-i/cash.c.stageB`):
- **Payee.**
  - ISO SELECT `00 A4 04 00 0C F04C45444745524341534801` returns 9000; any other AID returns 6A82. It is handled before
    the CLA check.
  - The home tagline reads "Ready to receive X" while a request is pending. After SET_REQUEST the app goes straight
    home instead of showing "Done".
  - PUT_AUTH shows "Received X\nfrom 0x<full address>".
  - GET_REQUEST keeps serving the last request after it is paid (`g_req_set`); PUT_AUTH still needs `g_req_valid`.
    Serving it is what lets a re-tap reach the payer's B004 refusal.
- **Payer: TAP_TO_PAY (INS 0x30, or the home button "Pay by tap").**
  1. `io_nfc_reader_start` puts up `nbgl_useCaseAction` "Hold near the payee" with a Cancel button.
  2. On CARD_DETECTED it sends SELECT, then GET_REQUEST (`E011000000`).
  3. `pay_review()` runs the same `pay_check` and review as PAY; it is factored out of `pay()` and sends nothing.
  4. On approval `tap_choice` calls `pay_sign` (debit persisted), then sends PUT_AUTH (`E0230000A1` + auth) with a 5 s
     timeout.
  5. `tap_on_receipt` recovers the receipt to `payTo`, and the tap ends with "Paid X\nto 0x...".

  Every exit path goes through `tap_end`: `io_nfc_reader_stop` + `os_io_nfc_cmd_start_ce` (back to card emulation),
  then a status screen. The tap never answers over USB, because the USB TAP_TO_PAY reply goes out at once. The host
  polls TAP_STATUS (INS 0x31: state u8, sw u16, auth 161).
- **Removal handling.** The SDK calls a pending `resp_cb(error=true)` before `evt_callback(CARD_REMOVED)`, and
  `tap_end` clears `evt_callback`, so each removal is handled once:
  - Before approval, with no command pending (review on screen): `tap_evt` gives "Card removed\nNothing paid",
    state 5, B008.
  - With a command pending: `tap_reply` gives "Nothing paid" before signing, or "Signed X / Card left after signing /
    Cash debited, no receipt" (state 6) after.
- **Stale review.** `g_pay_src` records who opened the review: PAY_USB, PAY_TAP or none. A review that outlives its tap
  answers nothing.
- **Busy guard.** GET_BALANCE and TAP_STATUS are exempt from the B007 busy guard (read-only, polled during a tap).

`speculos-nfc/relay.py`: `tap()` gained `stop=` (a threading.Event) and `cut_ins=`, which pulls the card away when
the reader sends that INS and does not deliver it. Both are optional; the CLI is unchanged.

New: `demo.py`, `README.md`, this file, `auths.json`, and `screens/` (51 PNGs, both devices).

## Commands (Git Bash)

```bash
cd "C:/Users/sahas/Github Repos/ledger-op3n-n3xt-hackathon-26/mvp/ledger-cash"
MSYS_NO_PATHCONV=1 docker run --rm --memory 1g --name lc-i-build \
  -v "C:/Users/sahas/Github Repos/ledger-op3n-n3xt-hackathon-26/mvp/ledger-cash/app:/app" \
  ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools@sha256:8d3da9179dd1b241883c769c521ee9403352b60091c80405b5bef5801a003ba2 \
  make -C /app TARGET=flex BOLOS_SDK=/opt/flex-secure-sdk APP_DIR=/app -j4      # exit 0, about 20 s, no warnings
# same with TARGET=stax BOLOS_SDK=/opt/stax-secure-sdk -> exit 0 (compiled only, not run)
python -u demo.py 2>&1 | tee demo-run.log                                       # about 1 min, ends ALL PASS
```

Containers, one at a time:
1. `lc-i-anvil` (512m), up, then down.
2. `lc-i-speculos` (1g; both Speculos instances in one container, like stage A's run.sh but with `--seed` per
   instance and port base 16000).
3. `lc-i-anvil` again.

The chain state is carried across with `anvil_dumpState` / `anvil_loadState` over JSON-RPC, so the task's order
(deploy and fund before the tap, settle after) holds without running two containers at once.

## Decisive results

- **Multi-chunk NFC works in both directions** through stage A's patch, which had only moved 5-byte frames: the
  GET_REQUEST reply is 159 B and the PUT_AUTH command is 166 B. That was the main risk the advisor flagged; it passed
  on the first run.
- **REST `/apdu` on the `--transport NFC` payee instance works** for SET_CONFIG, SET_REQUEST, GET_REQUEST and
  GET_AUTHS, including on-screen approval. Stage A had only used its TCP port.
- **Calling NBGL (spinner, review, status) and chaining `io_nfc_reader_send` from inside the reader callbacks** works
  in Speculos. The research note's "do not call NBGL from the callback" was marked INFERRED; it did not hold here.
- Tap 1 is paid:
  - balance 20 -> 15, counter 1;
  - the payee's GET_AUTHS slot 0 equals the payer's TAP_STATUS auth;
  - the EIP-712 signature recovers to the payer (eth_account);
  - nonce = keccak(request[0:92]).
- Tap 2 (the same request again) is refused on the payer with B004, and nothing is signed. A USB PAY of the same
  request is also B004.
- Tap 3 (payee pulled during the review): B008, "Card removed / Nothing paid", balance still 15.
- Tap 4 (PUT_AUTH cut): state 6, B008, balance 15 -> 12, counter 2. The kept auth recovers to the payer, and the payee
  has no slot 1 (6A88).
- Settlement: 100/0 -> 95/5 USDC. The second settle prints `REJECTED already used`.
- Fallback (USB test INS injecting card responses) was **not needed**; the real reader-mode code path ran.

## Not done / caveats

- `app/test.py` (stage B) was **not re-run**: it starts two containers at once, which this stage's rules forbid. The
  USB paths it covers that this stage touched are re-checked inside demo.py:
  - PAY rejected on screen returns 6985 (through the new `pay_review` and `g_pay_src`);
  - PAY of a paid request returns B004;
  - SET_CONFIG, LOAD_CASH and SET_REQUEST approve.

  test.py's assertions still hold by construction: PUT_AUTH twice still gives B006, and nothing it asserts depends on
  the removed "Done" screen.
- Everything is emulated. See README "Hardware gates" (reader permission for sideloaded apps, on-air framing, CE AID
  routing, reader -> CE mode switch, whether the field stays up during a long review).
- The tap has no overall timeout. "Hold near the payee" waits until a card arrives or the user presses Cancel.
- The card UID is ignored (it may be stale with the own IO stack).

## Cash account, honest wording, pinned builder (2026-10-10): PASS

Status: **PASS** in emulation. `python -u demo.py` (Flex) and `python -u app/test_nano.py` (Nano S Plus) both print
`ALL PASS` (`demo-run.log`, `app/test_nano-run.log`); `settle/test.mjs` also passes on a fresh anvil. Nothing touched
hardware. Nothing committed.

### What changed
- **Dedicated cash key.** `app/src/cash.c` `PATH` is `44'/1279476051'/0'/0/0` (`{0x8000002C, 0xCC434153, 0x80000000,
  0, 0}`) for both the payer key and the payee's request/receipt signer. `app/Makefile` declares only
  `PATH_APP_LOAD_PARAMS = "44'/1279476051'"` (44'/60' dropped), so the OS lets ledger-cash derive nothing else, and no
  stock Ledger chain app may derive this path (app-ethereum: `44'/60'`, `45'`, `12381/3600`; clones: their own coin
  type). The built `.apdu` carries `8000002CCC434153` in its install parameters.
  - **Coin type:** the task gave `1279475027` next to `0x4C434153` ("LCAS"); they disagree (`1279475027` =
    `0x4C433D53`, "LC=S"). Used the hex intent, **`0x4C434153` = 1279476051**. Neither value is in the SLIP-44 registry
    (`slip-0044.md` fetched 2026-10-10; no row for 1279476051 or 1279475027).
  - The address is a normal Ethereum address, so EIP-3009 settlement is unchanged.
  - **Remaining hole (documented):** the path lock binds the key to any app that declares the path. The owner can
    sideload another app declaring `44'/1279476051'`, or import the seed into a software wallet, and sign outside the
    cap; closing that for a payee needs attestation (v1) plus escrow (v2). The path lock is an OS check; Speculos runs
    show the derivation, not the lock.
- **Fixtures** (`app/test.py`, derived with `eth_account` `HDPath(...).derive(Mnemonic.to_seed(seed))`, no BIP-39
  checksum check): payer `0x46cE8565DD320e3764aa33cbdA7024F469132354` (was `0x153a5a...61415`), payee
  `0xb1124942BA3CeB48d87Dac9baBc50ca3B50A72db` (was `0x9858Ef...EDA94`). demo.py and test_nano.py read them from
  test.py. `settle/test.mjs` derives the same payer path (`hdKeyToAccount(..., { path })`); `fixture.json`,
  `auths.json`, `auths-bad-domain.json` in `settle/` regenerated.
- `hw.py`: SW names for 6700, 6A80, 6E00, B0FF; `balance` help names the cash account.
- **Wording** (README intro, Honest limits, Cash ladder v0/v1 rows and Q&A, IDEAS.md team decision and the
  primitives line): "the ledger-cash app refuses to sign more than the loaded balance from a cash account only it can
  sign for (dedicated derivation path); the payee still cannot check on-chain solvency offline". New README section
  "The cash account" (fund it on-chain, LOAD_CASH sets the offline spend). README Status links HARDWARE.md and
  video/ledger-cash-demo.mp4; the recorded output block is the new `demo-run.log`.
- **Builder pinned** to `ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools@sha256:8d3da9179dd1b241883c769c521ee9403352b60091c80405b5bef5801a003ba2`
  (the local `:latest` was this digest) in `.github/workflows/device-apps.yml`, README, HARDWARE.md, this file,
  app/NOTES.md, speculos-nfc/NOTES.md. LOAD.txt: "Close Ledger Wallet (formerly Ledger Live)".
- **HARDWARE.md:** new hash table; cash-account paragraph in Shared facts; SW rows 6E00/6700/6A80/6A88/B0FF; A0.1
  invitation check (hrishabhayush, invited 2026-10-10, write); A0.2 fallback (`gh workflow run` only after one run on
  the branch, else push a commit touching `mvp/ledger-cash/app/**`); `hw.py version` cross-check moved after A3; A7
  label note (`coffee-and-croissant-x2` in screens/nano vs `coffee`); "account 1" wording replaced; B-1 Prerequisites
  (invitation link, winget/brew/apt installs); B5 safety note (approve only 31337/anvil token or 84532/Base Sepolia
  USDC); B7.3 "the side of the Flex that worked in B6"; B7.4 exact screenshot names (13, 15, 17, 19, 21, 23); B8 and C
  save shared auths in `mvp/ledger-cash/settle/`.
- **mvp/android/README.md:** Nano bridge no longer blocked (`ledger-cash-nanosplus`; USB path takes GET_REQUEST and
  PUT_AUTH); A7 fixed: a Nano payee also answers `B006` after a paid PUT_AUTH (`put_auth` clears `g_req_valid`), so
  the Flex shows "Payee has no request", not `B004`; B5 Nano screen is "IOU 1 USDC from 0x… Not settled yet".
- **Video:** `video/render.py` STEPS[0] "Payer loads 20 USDC into a device-capped cash account (a spending cap, not
  escrow)", STEPS[4] "Signed offline. Payee holds a signed IOU", end card in the new wording; the caption font shrinks
  to fit the bar. Re-rendered: ffprobe `h264 1920x1080 yuv420p 83.5 s`; frames at steps 1, 4, 6 and the end card
  checked by eye.
- `screens/` and `screens/nano/` regenerated by the two runs (new addresses on the To, Receive and IOU screens).

### Builds (pinned image, clean `build/<target>`)
| target | app.sha256 |
|---|---|
| flex | `9c8cfe79ceb043e3ef728eaa12f117e8a17d92e35cb639be3fb0a0887bfbcd57` |
| nanos2 (Nano S Plus) | `4733ab55e296422951864ea7843e98f723a47004c7295c1f42cd48faa1fa10de` |

CI has not built these yet; the first `device-apps` run on this change should reproduce them.
- Not re-run: `app/test.py` (stage B, starts two containers at once). Its fixture addresses are the new ones and
  demo.py imports them, so it passes by construction; `app/test-run.log` still shows the old addresses.

## Interop: Flex payer (cash.c) taps the Android payee logic (2026-10-10): PASS

Hardware gate 2 is "Flex taps the collaborator's Android phone running the payee APK". This run shows in emulation
that the two sides speak the same protocol byte for byte. `interop/android_payee_tap.py` starts ONE Speculos Flex payer
(`v2i-speculos`, patched seproxyhal, REST :18000, USB APDU :18001, NFC reader :18002) and runs the phone payee as
`ledgercash.InteropMain` (mvp/android/core): `Payee.handle`, the code path `PayeeService` runs in PHONE mode, on
stdin/stdout with a fixed key (anvil test key 2, `0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC`) and a fixed reqNonce.
A TCP shim on :18011 speaks the Speculos APDU-port framing, so `relay.tap()` and `demo.run_tap()` run unchanged
(imported, with `demo.B = 18000`; demo.py's `lc-i-*` containers and :8545 are never touched). Anvil is `v2i-anvil` on
:8546; the settle scripts get `RPC_URL`. `settle/deploy.json` is restored after `deploy.mjs` (only its `rpc` field
differs).

```bash
cd mvp/ledger-cash
python -u interop/android_payee_tap.py     # ~50 s; needs app/build/flex/bin/app.elf, settle/node_modules, a JDK 17+
```
It runs `gradlew installDist` in mvp/android/core first. It drops a stale `JAVA_HOME`, because this host has one that
points at a removed JRE 8. Output goes to `interop/run.log`, payer screenshots to `interop/screens/`, and the phone's
exported auth (`Auth.toJson`, what the app's Share sends) to `interop/auths.json`.

First run, before any fix. The tap itself was already PAID; the stranger-reader and replay checks found 6 mismatches:
```
== b. the phone's NFC side gives cash.c's status words
  e0240100                   -> 6A86  cash.c 6D00  GET_AUTHS P1=1 over NFC (allowlist before the P1/P2 check)
  00a404000cf04c454447455243 -> 9000  cash.c 6700  SELECT with Le (SDK apdu_parser: Lc must match the length)
  e011000001                 -> B006  cash.c 6700  Lc=1 with no data
  00a4000c0cf04c454447455243 -> 6E00  cash.c 6A82  SELECT our AID with P1 != 04
== c. same request re-armed: v 0/1 and high-s forms of the device auth refused, original re-receipted
  v-parity -> 9000, high-s -> B006  cash.c B005 both
```
The v-parity case is a money bug. `Eth.recover` accepted v = 0/1, so the phone accepted an auth that USDC's
`transferWithAuthorization` reverts, receipted it and marked the request paid. cash.c's `ecrecover` takes 27/28 only.
cash.c's length rule comes from the SDK's `lib_standard_app/parser.c` `apdu_parser` (read from the pinned builder
image): 4 bytes (Lc = 0) or exactly 5 + Lc, else 6700, checked before SELECT. The fixes are in mvp/android (see its
NOTES).

After the fixes, `interop/run.log` (abridged; every line is asserted):
```
== a. tap: pay 5 USDC to the phone payee
    reader > card 00a404000cf04c45444745524341534801
    reader < card 9000
    reader > card e011000000
    reader < card 0000000000007a695fbdb2315678afecb367f032d93f642f64180aa33c44cdddb6a900fa2b585dd299e03d12fa4293bc00000000004c4b40ffffffffffffffff1c0ffee0636f66666565000000000000000000000000000000000000310b931967823a63dc9e5b738b37d3d64e3d9b9232ce3bd222f91a32270b9ca1114bbc9b003829f88690f3e2db88e0572bea87fbef803518906cbf57eec9ad5e1c9000
  [payer screen] Pay | 5 USDC | To | 0x3C44CDDDB6A900F | A2B585DD299E03D12F | A4293BC | For | coffee | Reject | 2 of 4
    reader > card e0230000a146ce8565dd320e3764aa33cbda7024f4691323543c44cdddb6a900fa2b585dd299e03d12fa4293bc00000000004c4b400000000000000000ffffffffffffffff4e4482f7d1d3e515379aec8695b0be54b8124ee1e4ac68ada1b48c554079ea0b1c02b00f5f1b296a01085497e06927c561c1f8dd44f471201363127f7c4bba7d9930c145b20ac8224a9a087a4b0ca0f0d9e4f88dc6254bd32d41169564af5a0e15
    reader < card 018a20c651ad9c0e7c2bd7ba158775440a8929b293f309da1616163e1307e7e31840d531b75301a1f68f090e0afcce548f0132e29fae03aff39d6e9c40d7eee7a51c9000
  TAP_STATUS PAID sw 9000   payer screen: Sending payment | Paid 5 USDC | to  | 0x3C44CDDDB6A900F | A2B585DD299E03D12F | A4293BC
== b. the phone's NFC side gives cash.c's status words      (all 10 match: B006 B006 6D00 6D00 6A86 6700 6700 6A82 6A82 6E00)
== c. same request re-armed: v 0/1 and high-s forms of the device auth refused, original re-receipted
  v-parity -> B005, high-s -> B005  cash.c B005 both
  original auth -> the same receipt byte for byte (RFC 6979)
== d. tampered request: the phone's GET_REQUEST reply has payTo rewritten
  TAP_STATUS FAILED sw B001   payer screen: Reading request | Payee signature invalid | Nothing signed
== 3. chain (online, later): settle the auth the phone exported (Auth.toJson)
     from 0x46cE8565DD320e3764aa33cbdA7024F469132354 100.000000 USDC -> 95.000000 USDC
     to   0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC 0.000000 USDC -> 5.000000 USDC
  #0 REJECTED already used nonce 0x4e4482f7d1d3e515379aec8695b0be54b8124ee1e4ac68ada1b48c554079ea0b
  transcript -> mvp/android/core/src/test/kotlin/ledgercash/InteropVectors.kt
ALL PASS
```
The request, the device's auth and the phone's receipt were the same bytes before and after the fixes. Two post-fix
runs wrote the same `InteropVectors.kt` (sha256 `7cc3991c...928e`), so the transcript is deterministic and CI replays it
(mvp/android `InteropTest`, `interop` job in `.github/workflows/android.yml`, pure JVM, no Speculos).

Caveats:
- The expected SWs in section b come from reading cash.c's `dispatch`/`put_auth` and the SDK parser, plus demo.py's
  asserts on the real payee (B006 after paid, 6D00 for host INS over NFC). Only one Speculos runs here, so the Flex
  payee did not answer these exact APDUs in this run.
- Synced against the attestation build (Flex app.sha256 `69873224...2acdb`). Its cash.c changes (IOU-status wording,
  the `PUT_ATTEST` overwrite guard, the till cents keypad) do not touch the NFC dispatch, `put_auth`, `GET_REQUEST`
  or the payer's tap path, so `InteropVectors.kt` is unchanged (sha256 `7cc3991c...928e`). If cash.c's protocol
  changes, rerun the script: it rewrites `InteropVectors.kt`, and the diff there shows what changed.
- Emulation only: real ISO-DEP framing between a Flex and an Android HCE service (gate 2) is still unverified.


## Till UX: on-device request, Waiting/Cancel home, settlement QR (2026-10-10): PASS

Status: **PASS** in emulation. `till_demo.py` (new, Flex), `demo.py` (Flex) and `app/test_nano.py` (Nano S Plus, now
with a till check) all print `ALL PASS`. Both targets rebuilt clean with the pinned builder. Nothing touched hardware.
Nothing committed. Containers used: `v2t-build`, `v2t-sdk` (SDK greps), `v2t-speculos`, `v2t-nano-speculos`,
`v2t-anvil`, one at a time; none left running.

### What changed
- `app/Makefile`: `ENABLE_NBGL_KEYPAD = 1` (QR was already on).
- `app/src/cash.c`:
  - **Till flow** (`till_start` -> `nbgl_useCaseKeypad("Amount in USDC", 1..6 digits)` -> `nbgl_useCaseKeypad("Cents
    (0 if none)", 1..2 digits)` -> `nbgl_useCaseGenericConfiguration("Payment for", BARS_LIST Coffee/Food/Groceries/
    Transport/Gift/Other)` -> `request_review(false)`). `request_review` is `set_request`'s old screen code, shared;
    the signing stays in `request_choice`. **`g_req_usb`**: only a USB SET_REQUEST gets a status word
    (`request_reply`); the till path answers nothing (no APDU is pending). `g_busy` is held from the first keypad to
    Approve/Reject/back, so a USB SET_REQUEST cannot swap `g_value`/`g_label` under it (`B007`, asserted). Starting
    the till drops a pending request, like SET_REQUEST. Amount 0 -> "Amount must be above 0".
  - **Keypad has no decimal key** (`keypadCallback` accepts `0x30..0x3F` only), hence two steps. Validate is disabled
    until `minDigits` are typed, so cents needs at least one digit ("0 if none"); one digit is cents (`5` = 0.05).
  - **Home.** Pending request: tagline `Waiting for tap:\n<amount> <label>\nto 0x1234...abcd` (`s_tagline` 80 -> 112),
    action **Cancel request** (`SOFT_HOME_ACTION`; `till_cancel` clears `g_req_valid`, status "Request cancelled").
    Idle: Flex keeps **Pay by tap**; the Flex/Stax home has exactly one action button (`useCaseHomeExt`:
    `actionButtonText`), so the till is behind the settings wheel: `settingContents` = BARS_LIST "Request payment",
    "Show settlement QR" (`HAVE_SE_TOUCH`). Nano (no NFC): idle action **Request payment**. demo.py's home press
    (240, 434) still hits "Pay by tap".
  - **Tune: no code.** `nbgl_useCaseStatus(msg, true, ...)` (put_auth's "Signed IOU ..." screen) already calls
    `os_io_seph_cmd_piezo_play_tune(TUNE_LEDGER_MOMENT)` under `HAVE_PIEZO_SOUND` (defined for flex and stax in
    `Makefile.defines`), and that function returns early unless `OS_SETTING_PIEZO_SOUND` enables notifications.
    Adding `TUNE_SUCCESS` would play twice. Not observable in Speculos.
  - **Settlement QR** (Flex only): `qr_show` draws `nbgl_layoutAddQRCode` + footer "Close" for the latest
    `NV.auths` slot; text `lcash:` + base64url(from|to|value|nonce|v|r|s) = 6 + 194 = **200 chars**. The full auth
    does not fit the ~213-byte budget (hex 322, base64 216); validAfter=0 and validBefore=2^64-1 are implied because
    `put_auth` only stores those. NBGL picks V10 for this length. `g_busy` is held until Close. "No signed IOU yet"
    when `auth_count == 0`.
- `hw.py`: `qr "<lcash:...>" [file]` -> settle.mjs JSON (decoder `qr_auth`, also used by till_demo.py);
  `selfpay till` = selfpay without SET_REQUEST (pays the request typed on the device's own till); the ledgerblue
  import moved into `x()` so `qr` runs without it.
- `till_demo.py` (new): one container `v2t-speculos` on demo.py's ports 16000-16011, no anvil. Asserts: keypad open ->
  USB SET_REQUEST `B007`; back arrow -> home, `GET_REQUEST B006`; settings wheel -> Request payment -> keypad `4` ->
  keypad `50` -> Coffee -> Approve; home shows `Waiting for tap:` / `4.5 USDC Coffee` / `to 0xB112...A72DB` /
  `Cancel request`; GET_REQUEST = 157 B, chain/token, payTo = payee, value 4 500 000, validBefore max, label
  `Coffee` zero-padded, payeeSig recovers to the payee; payer taps from "Pay by tap" -> PAID, payer 20 -> 15.5, payee
  GET_AUTHS 0 == auth, nonce = keccak(req[:92]), payee status text `Signed IOU for 4.5 USDC from 0x46CE...2354 Not
  settled yet`; settings -> Show settlement QR, the screenshot is decoded with OpenCV and `hw.qr_auth(text) == auth`;
  Close -> home; till again `2` + `05` -> labels page 2 -> Other -> GET_REQUEST value 2 050 000, label `Other`, new
  reqNonce; Cancel request -> "Request cancelled", GET_REQUEST `B006`. Key coordinates: keypad keys at x 80/240/400,
  y 292/380/468/556, validate (400, 556), wheel (404, 76), back (48, 48), labels next page (430, 552).
- `app/test_nano.py`: after PUT_AUTH, the payee Nano runs the till with buttons (row `<del> 0..9 <ok>`, cursor starts
  on 5 and jumps to `<ok>` after a digit): `3`, `0`, Coffee, Approve -> home `Waiting for tap: | 3 USDC Coffee | to
  0xB112...A72DB`, GET_REQUEST 3 USDC `Coffee` recovering to the payee; right -> Cancel request -> `B006`. Screens
  `screens/nano/38-45`.
- Docs: HARDWARE.md hash table + A4/B4 copies, A7 step 4 home text, new A7 step 7 (Nano till), B5 home text, new
  **B5b** (Flex till, `selfpay till`, QR, cancel, put the cash back); README Protocol (SET_REQUEST row, QR format,
  "On-device till" paragraph), flow diagram, Run it step 4, screenshots table, Files; app/NOTES.md update header.
- `screens/` and `screens/nano/` regenerated (payee home now shows "Waiting for tap" and the wheel);
  `screens/till/` new (35 PNGs). `video/ledger-cash-demo.mp4` was **not** re-rendered and still shows the old
  "Receive ..." payee home.

### Builds (pinned image, clean `build/<target>`, exit 0; the cash.c compiles printed no warnings)
```bash
MSYS_NO_PATHCONV=1 docker run --rm --memory 1g --name v2t-build \
  -v "C:/Users/sahas/Github Repos/ledger-op3n-n3xt-hackathon-26/mvp/ledger-cash/app:/app" \
  ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools@sha256:8d3da9179dd1b241883c769c521ee9403352b60091c80405b5bef5801a003ba2 \
  make -C /app TARGET=flex BOLOS_SDK=/opt/flex-secure-sdk APP_DIR=/app -j4      # and TARGET=nanos2 BOLOS_SDK=/opt/nanosplus-secure-sdk
```
| target | app.elf | app.apdu | app.hex | app.sha256 |
|---|---|---|---|---|
| flex | 243828 | 150032 | 202431 | `a601af35321b293728e5618de8b8130632f5142a2aaa5ba612e621b2820a6dbc` |
| nanos2 (Nano S Plus) | 167304 | 90912 | 122650 | `7ffe99e1042909407237e65ed396f96ab15d3a1930ee56ba62ea2e13cc186713` |

Same hashes from the incremental and the clean build. CI has not built these yet.

### Runs (exact commands; the logs in the repo come from these)
demo.py and test_nano.py hardcode `lc-i-*` / `v1-*` container names (test_nano.py also ports 17000-17011), outside this
track's allotment, so they were run with `v2t-*` names and ports 16000-16011 patched in at import (the scripts themselves are unchanged apart from the Nano till check):
```bash
cd mvp/ledger-cash
python -u till_demo.py > till_demo-run.log 2>&1                                    # exit 0
python -u -c "import sys; sys.argv=['demo.py']; sys.path.insert(0,'.'); import demo as D; D.SPEC='v2t-speculos'; D.ANVIL='v2t-anvil'; D.main()" > demo-run.log 2>&1   # exit 0
cd app && python -u -c "import sys; sys.argv=['test_nano.py']; sys.path.insert(0,'.'); import test_nano as N; N.B=16000; N.SPEC='v2t-nano-speculos'; N.D.ANVIL='v2t-anvil'; N.main()" > test_nano-run.log 2>&1   # exit 0
```
Decisive output (verbatim):
```
till_demo-run.log:
  keypad open -> SET_REQUEST B007; back arrow -> home, GET_REQUEST B006
  GET_REQUEST: 4.5 USDC 'Coffee' to the payee, payeeSig recovers to 0xb1124942BA3CeB48d87Dac9baBc50ca3B50A72db
  [payer screen] Pay | 4.5 USDC | To | 0xB1124942BA3CEB48 | D87DAC9BABC50CA3B | 50A72DB | For | Coffee | Reject | 2 of 4
  TAP_STATUS PAID sw 9000   payer screen: Sending payment | Paid 4.5 USDC | to  | 0xB1124942BA3CEB48 | D87DAC9BABC50CA3B | 50A72DB
  PAID: payer 20 -> 15.5, payee screen 'Signed IOU for 4.5 USDC ... Not settled yet'
  QR (200 chars) decodes to the stored auth: lcash:Rs6FZd0yDjdkqjPL2nAk9GkTI1SxEklCuj...
  2.05 USDC 'Other' served, then Cancel request -> GET_REQUEST B006, home back to 'Cash: 0 USDC'
ALL PASS
app/test_nano-run.log:
  Nano till: keypad 3 + 0 cents, Coffee, approved -> GET_REQUEST 3 USDC 'Coffee'; Cancel request -> B006
ALL PASS
demo-run.log: ... ALL PASS
```

### Not exercised
- On hardware: everything (keypad feel, the wheel, the QR scanned by a real phone camera, the tune).
- Stax / Apex P: not compiled this time (`ledger_app.toml` lists them; CI builds flex and nanos+ only).
- The Nano never shows the QR (no `HAVE_SE_TOUCH` branch); `hw.py selfpay till` and `hw.py qr` were run only as far
  as `qr`'s decoder (through till_demo.py); `selfpay till` needs a device or ledgerblue's Speculos proxy.

## Attested IOUs, cash ladder v1 (emulated) (2026-10-10): PASS

The payer can attest an IOU with BOLOS endorsement slot 1, and the payee checks it on the device. `attest_demo.py`,
`demo.py`, `till_demo.py` and `app/test_nano.py` all print ALL PASS on the final builds. Nothing touched hardware;
nothing is committed. Container prefix `v2a-`, ports 16000-16011, no anvil in `attest_demo.py`.

### What the API reading established
- SDK `v27.1.2` (`/opt/flex-secure-sdk`, HEAD `6709cd2b`, tag `v27.1.2`) `include/os_endorsement.h`:
  `sys_endorsement_get_code_hash(hash, len)`, `sys_endorsement_get_public_key(slot, pub, &len)` (65),
  `sys_endorsement_get_public_key_signature(slot, sig, &len)` (len in >= 72), `sys_endorsement_key1_sign_data(data,
  len, sig, &len)`: "Hash input data, update the hash with current calling app code hash, then sign it with keys from
  endorsement slot 1". Errors are returned (`0x4103` no key, `0x5218` not set, `0x5503` PIN not validated), per the
  header; no retail run.
- Speculos (pinned image, 0.27.1) `src/bolos/endorsement.c`: `static char CODE_HASH[] = "12345678abcdef0000fedcba8765432";`
  (32 bytes with the NUL), returned by every get_code_hash; `key1_sign_data` = ECDSA(`USER_PRIVATE_KEY`,
  `sha256(data || CODE_HASH)`), DER. `src/environment.c` `env_init_user_certificate`: cert = ECDSA(`ATTESTATION_PRIVATE_KEY`,
  `sha256(0xFE || pub65)`), DER. Defaults: attestation key `138fb9b9...5d57` (pub `044114d1...964e`), user key
  `e15e01d4...b710` (pub `04b7962a...949c`); both instances share them.
- ledgerblue 0.1.58 (in the builder image): `verifyEndorsement1` checks `sha256(message || codehash)`;
  `endorsementSetup` = `E0 C0` (device returns the new key signed by the device key over `sha256(0xFF || pub)`), then
  `E0 C2` stores the Owner certificate (`0xFE || pub`, signed by the host's private key). The device key and its issuer
  certificate (`E0 52`, batch issuer `0490f5c9...` = Blue batch 1) are seen only by that dashboard flow, never by an
  app. `hashApp` docstring: the app hash is sha256(target_id, api_level, code/data/install lengths, flags, boot
  offset, image) "computed device-side at install time".
- `bin/app.sha256` is `ledgerblue.loadApp --offline`'s "Application full hash" (`Makefile.rules_generic:181`), the
  same computation, so it is the code hash a device should report. Not compared on a device.

### What changed
- `app/src/cash.c`: INS `25` PUT_ATTEST (payee, NFC allowlist), `32` GET_ATTESTATION (USB; a `9000` arms the payer),
  `33` GET_LAST_ATTEST (USB), SW `B00A`. `att_sign` in `pay_sign` after the EIP-712 signature and before the debit
  write, only when armed; the tap sends PUT_ATTEST after a verified receipt and ends PAID whatever the answer
  (`tap_on_attest`). `att_verify`: cert under `CERTIFIER` (Speculos default attestation pub), sig under the sent key over
  `sha256(keccak(last stored auth) || own code hash)`. Payee IOU status gains "Attested: Ledger Cash 0.0.1" / "Not
  attested" (Nano "Attested" / "Not attested", 4 lines). `s_msg` 112 -> 160. A failing PUT_ATTEST does not overwrite a
  verified record. Two bugs found by the runs and fixed: `tap_choice` sent `sizeof(g_tap_cmd)` after the buffer grew
  (PUT_AUTH went out as 248 bytes, zero padded -> `6700`, tap SIGNED_NO_RECEIPT), and `put_auth` formatted its status from the APDU buffer after the reply had
  reused it ("Signed IOU for  USDC from 0x8667..."); it now reads the NVM copy.
- `attest/speculos_codehash.py`: run inside the Speculos image, copies `speculos.main.launcher_path` to
  `/tmp/launcher-<hash16>` with the 32 fake bytes replaced (asserts exactly one occurrence), sets
  `speculos.main.launcher_path` to the copy and calls `main()`. One copy per instance, so two builds share a container.
- `attest/verify_attestation.py`: offline verifier (cryptography + eth_utils). `attest/iou-genuine.json`,
  `attest/iou-cheat.json`: the exported IOUs of the last run.
- `attest_demo.py` (new), `app/test_nano.py` (patched launcher, GET_ATTESTATION before PAY, PUT_ATTEST check),
  `till_demo.py` (IOU screen text now includes "Not attested"), `hw.py` (`attest`; `selfpay` forwards an attestation
  when armed). The cheating payer is built by `attest_demo.py` into `app/build/cheat/flex` (gitignored): a copy of
  `app/` with the line containing `R_VALUE) > NV.wallet.balance) return SW_INSUFFICIENT` deleted by `sed`; its hash is
  whatever that build gives (`5aa3da0d...` this run), not a pinned value.

### Builds (pinned image, clean `build/<target>`, exit 0, no compiler warnings)
```bash
cd mvp/ledger-cash/app && rm -rf build/flex build/nanos2
MSYS_NO_PATHCONV=1 docker run --rm --memory 1g --name v2a-build -v "C:/Users/sahas/Github Repos/ledger-op3n-n3xt-hackathon-26/mvp/ledger-cash/app:/app" ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools@sha256:8d3da9179dd1b241883c769c521ee9403352b60091c80405b5bef5801a003ba2 make -C /app TARGET=flex BOLOS_SDK=/opt/flex-secure-sdk APP_DIR=/app -j4
# same with TARGET=nanos2 BOLOS_SDK=/opt/nanosplus-secure-sdk
```
| target | app.elf bytes | app.sha256 |
|---|---|---|
| flex | 244692 | `69873224e9a205cbff4b5a40ec22846dba9f2a7caded36738c3d781be2a2acdb` |
| nanos2 (Nano S Plus) | 168136 | `63e3c196dfc9b01c8e32747a29e299af903c849790f945fa7a983c5303bf7bb9` |

These supersede the till hashes (`a601af35...`, `7ffe99e1...`) that the interop track pinned.

### Runs (exact commands; the logs in the repo come from these, one container at a time)
```bash
cd mvp/ledger-cash
python -u attest_demo.py > attest_demo-run.log 2>&1                                                    # exit 0
python -u -c "import sys; sys.argv=['demo.py']; sys.path.insert(0,'.'); import demo as D; D.SPEC='v2a-speculos'; D.ANVIL='v2a-anvil'; D.main()" > demo-run.log 2>&1   # exit 0
python -u -c "import sys; sys.argv=['till_demo.py']; sys.path.insert(0,'.'); import till_demo as TD; TD.D.SPEC='v2a-speculos'; TD.main()" > till_demo-run.log 2>&1   # exit 0
cd app && python -u -c "import sys; sys.argv=['test_nano.py']; sys.path.insert(0,'.'); import test_nano as N; N.B=16000; N.SPEC='v2a-nano-speculos'; N.D.ANVIL='v2a-anvil'; N.main()" > test_nano-run.log 2>&1   # exit 0
```
Decisive output (verbatim, `attest_demo-run.log` without the APDU hex lines):
```
  genuine build app.sha256 69873224e9a205cbff4b5a40ec22846dba9f2a7caded36738c3d781be2a2acdb
  cheating build app.sha256 1cbdb79bcc68444e27ecab7d020ec6b55d37a67cc39bac8a369ccaa3aff4bdf0
== 1. genuine payer -> genuine payee (both Speculos instances report their own code hash)
  GET_ATTESTATION on both: endorsement key 04b7962a8e0e4b9ca0..., cert valid, code hash = app.sha256
  genuine payer, 20 USDC loaded, asked for 25 USDC: PAY -> B003 (device cap holds, nothing signed)
  [payee screen] Signed IOU for 5 USDC | from  | 0x46CE8565DD320E37... | Not attested | Not settled yet | ... | Certified device key | Not settled yet
  $ python attest/verify_attestation.py attest/iou-genuine.json --codehash app/build/flex/bin/app.sha256  -> exit 0
    pinned code hash  69873224e9a205cbff4b5a40ec22846dba9f2a7caded36738c3d781be2a2acdb
    claimed code hash 69873224e9a205cbff4b5a40ec22846dba9f2a7caded36738c3d781be2a2acdb
    sig over keccak(auth) || pinned hash: valid
    ATTESTED
  PAID 5 USDC; payee verified the attestation on the device (state 2) and shows 'Certified device key'
  over NFC: a broken PUT_ATTEST -> B00A and the verified record stays; GET_ATTESTATION / GET_LAST_ATTEST -> 6D00
== 2. cheating payer (cap check deleted) -> genuine payee
  [payee screen] Signed IOU for 25 USDC | from  | 0x46CE8565DD320E37... | Not attested | Not settled yet | ...
  the cheat signed 25 USDC over a 20 USDC load (its cash counter wrapped to 18446744073704551616); the payee stored the IOU, verdict state 3 = NOT attested
  $ python attest/verify_attestation.py attest/iou-cheat.json --codehash app/build/flex/bin/app.sha256  -> exit 1
    claimed code hash 1cbdb79bcc68444e27ecab7d020ec6b55d37a67cc39bac8a369ccaa3aff4bdf0   (differs from pinned)
    sig over keccak(auth) || pinned hash: INVALID
    sig verifies with the CLAIMED hash: the IOU was signed inside a different build
    NOT ATTESTED
  replaying round 1's genuine attestation for this IOU: PUT_ATTEST -> B00A (it covers another auth)
== 3. forging payer (cap deleted, key1_sign_without_code_hash over keccak(auth)||genuine hash) -> genuine payee
  forging build app.sha256 73d950658c5447b5bf4ca28cd93b1035ce8dafe577d3098dc4a446558f42b987
  [payee screen] Signed IOU for 25 USDC | from  | 0x46CE8565DD320E37... | Not attested | Not settled yet | ... | Certified device key | Not settled yet
  $ python attest/verify_attestation.py attest/iou-forge.json --codehash app/build/flex/bin/app.sha256  -> exit 0
    pinned code hash  69873224e9a205cbff4b5a40ec22846dba9f2a7caded36738c3d781be2a2acdb
    claimed code hash 69873224e9a205cbff4b5a40ec22846dba9f2a7caded36738c3d781be2a2acdb
    sig over keccak(auth) || pinned hash: valid
    ATTESTED
  the forge signed 25 USDC over a 20 USDC load; the payee shows 'Certified device key' (state 2) and the offline
  verifier says ATTESTED. v1's code-hash binding is forgeable by any app via the real BOLOS syscall
  sys_endorsement_key1_sign_without_code_hash: a negative result, not a guarantee to a shop.
ALL PASS
app/test_nano-run.log:
  PUT_ATTEST: payee Nano verifies the payer's attestation (state 2, 'Certified key'); host verifier agrees
ALL PASS
till_demo-run.log:
  PAID: payer 20 -> 15.5, payee screen 'Signed IOU for 4.5 USDC ... Not attested / Not settled yet'
ALL PASS
demo-run.log: ... ALL PASS   (unarmed payer: taps are the v0 taps, 3 APDUs in tap 1, no E025)
```
Screens: `screens/attest/` (`23-payee-genuine-payee-status.png` Attested, `44-payee-cheat-payee-status.png` Not
attested), `screens/nano/38-payee-put-attest.png`.

### Not exercised / open
- Hardware: everything. Retail endorsement calls, whether slot 1 is provisioned at the factory, whether
  `get_code_hash` equals `app.sha256`, a 246-byte command over a real field. `hw.py attest` and the `selfpay`
  attestation path were not run (no ledgerblue on this host; they need a device or ledgerblue's Speculos proxy).
- `ledgerblue.endorsementSetup` was not run anywhere, and must not be run on the team's devices without the owner's
  decision (README "Attested IOUs").
- Stax / Apex P not compiled; CI has not built `69873224...` / `63e3c196...`; the video still shows the old screens.
- The interop track's recorded Android transcript is unaffected: an unarmed payer sends no E025.
