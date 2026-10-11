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
  ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest \
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
