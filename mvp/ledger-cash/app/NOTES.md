# ledger-cash device app v0 (stage B): NOTES

> Update (Integrate stage, 2026-10-10): NFC is now wired. TAP_TO_PAY (0x30) / TAP_STATUS (0x31), SELECT AID, the payee screens, and the reader-mode path are in src/cash.c. See ../NOTES.md and ../README.md. Statements below that NFC is not wired are stale.

> Update (Fix stage, 2026-10-10): see ../NOTES.md "Fix stage". What changes below: `reqNonce` is random (`cx_rng_u32`),
> not a counter, so assert 8's "reqNonce now 1" became "differs from the first request"; `PUT_AUTH` also refuses
> high-s (`B005`); over NFC only SELECT / GET_REQUEST / PUT_AUTH are accepted (test.py talks USB, so unaffected); the
> payee screen says "Signed IOU ... Not settled yet"; `IMAGE` is pinned to speculos@sha256:028d1e36...; `Dev.prefix`
> exists for demo.py. test.py was **not re-run** after these changes (it starts two containers at once); the
> `test-run.log` output below is from the pre-fix ELF.

Status: **PASS** on Speculos Flex (two instances, payer + payee). `python test.py` prints `ALL PASS` (`test-run.log`).
stax and apex_p also compile (exit 0), not run.

## Layout

- `src/cash.c`: the whole app (IO loop, dispatcher, handlers, ecrecover, EIP-712 digest, NVM, NBGL screens). The rest of the C boilerplate (swap, token, transaction, ui, helpers) is deleted.
- `Makefile`: boilerplate with `APPNAME "Ledger Cash"`, `PATH_APP_LOAD_PARAMS "44'/60'"`, `ENABLE_NFC=1 ENABLE_NFC_READER=1 DISABLE_OS_IO_STACK_USE=1`, no Bluetooth/TLV/PKI/test-swap. `ledger_app.toml`: flex, stax, apex_p.
- `test.py`: end-to-end test. `screens/`: Flex screenshots from the passing run. Icons are still the boilerplate's.

## Build (Git Bash, from anywhere)

The path with a space works as a bind mount. The SDK runs `git rev-parse --show-toplevel` and compiles **no app sources** when the mount is not a git repo (link fails with `undefined symbol: app_main`), so pass `APP_DIR=/app`:

```bash
MSYS_NO_PATHCONV=1 docker run --rm --memory 1g --name lc-b-build \
  -v "C:/Users/sahas/Github Repos/ledger-op3n-n3xt-hackathon-26/mvp/ledger-cash/app:/app" \
  ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest \
  make -C /app TARGET=flex BOLOS_SDK=/opt/flex-secure-sdk APP_DIR=/app -j4
# stax: TARGET=stax BOLOS_SDK=/opt/stax-secure-sdk     apex_p: TARGET=apex_p BOLOS_SDK=/opt/apex-secure-sdk
```

The "fatal: not a git repository" line still prints and is harmless. Output: `build/flex/bin/app.elf`.

## Test

```bash
cd mvp/ledger-cash/app && python test.py     # Python 3.12, requests, eth-account; ~2 min
```

Starts `lc-b-payer` (:5000, spike seed `glory promote ...` -> `0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415`) and `lc-b-payee` (:5001, `abandon x11 about` -> `0x9858EfFD232B4033E47d90003D41EC34EcaEda94`) from `ghcr.io/ledgerhq/speculos` (now pinned to `@sha256:028d1e36...`), `--memory 1g` each, and removes both at the end. The approver thread reads `/events`: taps `Approve`, swipes on `N of M` pages, holds `Hold to sign`. In reject mode it taps `Reject`, then `Yes, reject`. Every new screen is saved to `screens/`.

Asserts:
1. SET_CONFIG on both, LOAD_CASH 50 -> GET_BALANCE = (50 000 000, counter 0, spike address).
2. Payee SET_REQUEST 5 "coffee" -> GET_REQUEST 157 bytes. The fields are correct, and **payeeSig recovers to the payee with eth_account** (`encode_defunct(primitive=keccak(req[:92]))`). The signature is low-s.
3. Payer PAY with value+1 -> `B001`; with corrupted s -> `B001`. These requests never reach the screen. This exercises the on-device ecrecover.
3b. Both signature parities go through ecrecover. Requests signed by fresh eth_account keys, one with v=27 and one with v=28, must reach the review: they are rejected there with `6985`, not `B001`. Without this check only v=27 was ever exercised (the payeeSig in this run has v=27).
4. PAY, reject on screen -> `6985`, balance still 50 / counter 0.
5. PAY, approve -> 161-byte auth. from = payer, to = payTo, validAfter 0, nonce == keccak(req[:92]). The **EIP-712 TransferWithAuthorization recovers to the payer with eth_account** (domain USDC / "2" / 31337 / token), and s is low. Balance is then 45 / counter 1.
6. The same PAY again -> `B004` (replay), balance unchanged.
7. Payee PUT_AUTH with a flipped s byte -> `B005`. The real auth -> `01 || receipt`, and the receipt recovers to the payee. The same auth again -> `B006`, because the request is consumed. GET_AUTHS P1=0 == auth, P1=1 -> `6A88`.
8. Payee SET_REQUEST 100 "tv" (reqNonce now 1) -> payer PAY -> `B003`, balance unchanged.

Decisive output (verbatim, `test-run.log`; the first two reject rounds are the v=27 and v=28 parity requests):
```
payeeSig v=27
  [lc-b-payer] Pay with | USDC cash | Swipe to review | Reject | 1 of 4
  [lc-b-payer] Reject transaction? | Go back to transaction | Yes, reject
  [lc-b-payer] Pay with | USDC cash | Swipe to review | Reject | 1 of 4
  [lc-b-payer] Reject transaction? | Go back to transaction | Yes, reject
  [lc-b-payer] Pay with | USDC cash | Swipe to review | Reject | 1 of 4
  [lc-b-payer] Reject transaction? | Go back to transaction | Yes, reject
  [lc-b-payer] Pay with | USDC cash | Swipe to review | Reject | 1 of 4
  [lc-b-payer] Pay | 5 USDC | To | 0x9858EFFD232B4033 | E47D90003D41EC34E | CAEDA94 | For | coffee | Reject | 2 of 4
  [lc-b-payer] Cash left after | 45 USDC | Reject | 3 of 4
  [lc-b-payer] Pay 5 USDC? | Reject | 4 of 4 | Hold to sign
pay ok: 50 -> 45, EIP-712 verifies with eth_account, low-s
payee stored auth, receipt verifies, GET_AUTHS returns it
  [lc-b-payee] Request 100 USDC | For: tv | Reject | Approve
AUTH 153a5aa5e15f13c92760b65aae8ccfa7c51614159858effd232b4033e47d90003d41ec34ecaeda9400000000004c4b400000000000000000ffffffffffffffffa709d84808ef99002ecd68dc697a9b0ea0a6453c95391c64cf5f690ce3d9e15a1b8c546f673399894bc276ea2e662e3451679d9145a3ea00b4838af6efff73c2593f2ef028da9fcf8cca6edb46d315460b318a561ff7642ecfdda2502ef695853f
ALL PASS
```

## APDU protocol (CLA E0, big-endian, P1=P2=0 except GET_AUTHS)

| INS | Name | Data in | Out | Screen |
|---|---|---|---|---|
| 12 | SET_CONFIG | chainId u64 \|\| token 20 | - | "Set USDC network / Chain ID / USDC 0x..", Approve |
| 20 | LOAD_CASH | value u64 (6-dec) | - | "Load X USDC as cash / Cash after", Approve |
| 21 | GET_BALANCE | - | balance u64 \|\| payCounter u32 \|\| address 20 (32 B) | - |
| 10 | SET_REQUEST | value u64 \|\| label <=24 printable ASCII | - | "Request X USDC / For: label", Approve |
| 11 | GET_REQUEST | - | request (157 B) | - |
| 22 | PAY | request (157 B) | auth (161 B) | review: Pay / To (full address) / For / Cash left after, Hold to sign |
| 23 | PUT_AUTH | auth (161 B) | 01 \|\| receipt r32 s32 v1 (66 B) | status "Signed IOU for X USDC / from 0x... / Not settled yet" (was "Received X USDC" before the fix stage) |
| 24 | GET_AUTHS | P1 = slot 0..7 | auth (161 B) | - |

- request = chainId u64 @0 | token 20 @8 | payTo 20 @28 | value u64 @48 | validBefore u64 @56 | reqNonce u32 @64 | label 24 @68 (zero padded) | payeeSig r32 @92 s32 @124 v1 @156. payeeSig = personal_sign (EIP-191) of keccak256(request[0:92]): `viem.verifyMessage({address, message:{raw: keccak256(req.slice(0,92))}, signature: req.slice(92)})`.
- auth = from 20 @0 | to 20 @20 | value u64 @40 | validAfter u64 @48 | validBefore u64 @56 | nonce 32 @64 | v1 @96 | r32 @97 | s32 @129. **161 bytes** (the brief said 193: 20+20+8+8+8+32+1+32+32 = 161). The EIP-712 domain is {name "USDC", version "2", chainId, verifyingContract token}, and nonce = keccak256(request[0:92]). On-chain: `transferWithAuthorization(from, to, value, validAfter, validBefore, nonce, v, r, s)`.
- receipt = personal_sign of keccak256(auth[0:161]), r||s||v. Both payee signatures (payeeSig and receipt) use the same verify call.
- v = 27/28 everywhere, low-s: Speculos `cx_ec.c:1648-1654` canonicalises s unless `CX_NO_CANONICAL`, as the device does. test.py asserts it on every signature.
- SW: 9000 ok, 6985 user reject, 6700 length, 6A80 bad data (value 0, bad label, overflow), 6A86 P1/P2, 6A88 no such auth, 6D00 INS, 6E00 CLA, **B001** payeeSig does not recover to payTo, **B002** not configured or request chainId/token differ from config, **B003** value > cash, **B004** request already paid (replay), **B005** auth invalid (to/value/validAfter/validBefore/nonce mismatch or sig not from `from`), **B006** no active request, **B007** busy (a review is on screen), B0FF crypto failure.

## Decisions

- **Replay:** the payer keeps the nonces of its last 8 payments in NVM (`wallet.seen`, ring indexed by payCounter) and refuses a request it has already paid (`B004`). On-chain, USDC's `authorizationState` also makes a second settlement impossible.
- **Atomic debit:** PAY signs into RAM, then writes `{balance, payCounter, seen[8]}` with one `nvm_write`, then sends the auth. If the device loses power between the write and the send, the cash is debited but the auth is never delivered. That loses money; it never double-spends. `pay_sign` re-runs every check (`pay_check`) at approve time.
- **validBefore = 2^64-1:** the device has no trusted clock, so a request never expires, like cash (`ponytail:` comment in `request_choice`). To add expiry later: SET_REQUEST takes a host validBefore and shows it on screen.
- **Payee request in RAM:** one request is active at a time. A successful PUT_AUTH consumes it, so the same auth is not accepted twice. reqNonce is an NVM counter, so requests stay unique across restarts.
- **Auth ring:** 8 slots in NVM. The 9th payment overwrites the oldest (`ponytail:` comment). The host must GET_AUTHS and settle before then.
- **"To" shows the full 42-char address**, not a short one. Paying the right person is the point of the Secure Screen, and it fits on one page (screens/13).
- **Busy guard:** while a review is on screen, every other APDU gets `B007`. Without it, a second PAY could swap `g_pay` under a screen showing a different payee.
- **ecrecover** is built on the device from the `cx_bn_*` and `cx_ecpoint_*` syscalls (decompress R from r with parity v-27, then `double_scalarmul(u1=-z/r on G, u2=s/r on R)`), and checks 0<r,s<n. The negative asserts in test.py prove it works on Speculos. The positive cases are the payee's real signature and the payer's real auth.
- SET_CONFIG may be changed later while a balance exists. The balance is not tied to a chain; that is fine for v0.
- The SET_CONFIG screen prints chainId with `%u` after a 32-bit cast. That is fine for 31337, 84532 and 5042002, but the display would truncate a chainId above 2^32. The stored value is the full u64.
- Implemented but not covered by test.py: `B002` (config mismatch / not configured), `B007` (busy), the label-charset rejection, LOAD_CASH overflow.

## Bugs hit

| Symptom | Cause | Fix |
|---|---|---|
| `ld.lld: error: undefined symbol: app_main`, with no app objects built | the SDK's `APP_DIR := $(shell git rev-parse --show-toplevel)` is empty inside a non-git mount, so it finds no sources | `make ... APP_DIR=/app` |
| Speculos dies on swipe to review page 2: `seproxyhal.py line 407 ... UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb2 in position 8`. The raw text line (patched debug seproxyhal) was `b'5.000000G\xc5A\x13\xc1\x03...'` | SDK `format_fpu64` (lib_standard_app/format.c:128-131) `strncpy`s exactly `decimals` digits and never writes the NUL. `format_fpu64_trimmed` then `strlen`s into stack garbage. LOAD_CASH worked only because its stack happened to be zero | `char tmp[24] = {0};` in `fmt_usdc` |
| `eth_account` refuses the Speculos mnemonic ("Language not detected") | that mnemonic is not a valid BIP-39 phrase for eth_account | hardcode the payer address from the spike run |

## Honest gaps (for the README)

- **The loaded cash is only a device counter.** LOAD_CASH is approved on screen, but nothing locks USDC on-chain. A payee cannot check offline that the payer's on-chain balance still covers the authorization: the payer can spend the USDC elsewhere, or load more "cash" than they hold. True bearer cash needs an on-chain escrow that the device-held key alone can release, plus device attestation so the payee knows the counter lives in a genuine secure element. That is a stretch goal, out of scope for v0.
- Wiping or reinstalling the app resets the balance and the replay ring. The on-chain nonce still prevents a double settle of the same request.
- validBefore never expires (see above).
- NFC is not wired yet. The handlers are transport-agnostic: CE APDUs (payee: GET_REQUEST, PUT_AUTH) arrive through the same `io_recv_command`, and the reader-side payer can call `pay_check` / `pay_sign` with the bytes it got over NFC. Every reply fits the 271-byte NFC reply limit (157, 161 and 66 bytes plus SW).
