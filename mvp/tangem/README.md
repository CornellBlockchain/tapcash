# Tangem track: let the payer Flex talk to a Tangem card

The ledger-cash Flex app runs in NFC reader mode. This folder holds the code that lets that app read a Tangem card (Sahas owns several), get the card's Ethereum address, have the card sign a 32-byte digest, and challenge the card's attestation key. The protocol facts and their sources are in `research/tangem-protocol.md`.

> **Licence decision pending (Sahas).** Tangem changed its SDK licence in July 2025. The new terms forbid "attempting to recreate the Protocol for use in unauthorized applications". Everything here was built from the earlier MIT-licensed SDK (`cdf62aacbe`), and no SDK code was copied. Whether a public hackathon repo counts as "distributed" is unresolved. See `research/tangem-protocol.md` §0 before this goes into the submission.

## Files

| File | What |
|---|---|
| `src/tangem.h`, `src/tangem.c` | Pure C, no SDK calls, about 3.3 KB of Thumb code. Builds the APDUs, classifies status words, parses TLV replies (the card is treated as untrusted input), normalises signatures to low-s, picks `v`, derives the address through a keccak hook. `tg_next()` steps through SELECT → Read card → Read wallet (HD path) → Sign → AttestCardKey, driven from the reader callback. **All Tangem constants are in `tangem.h`.** |
| `test_tangem.c` | Host unit tests (SDK vectors plus constructed ones) and a `--flow` stdin/stdout driver. |
| `mock_tangem.py` | Fake Tangem card, stdlib only (pure-Python secp256k1 + BIP32). `--harness` drives `test_tangem --flow` and checks the result cryptographically. `--port` speaks the Speculos APDU-port framing, so `mvp/ledger-cash/speculos-nfc/relay.py --card` can tap it to a reader app. |
| `test.sh` | Runs all of the above in the `ledger-app-dev-tools` image, plus an ARM cross-compile. |
| `check_relay_framing.py` | Checks the mock against `relay.card_exchange` on the host. |

Run: `sh test.sh` (Docker), and `python check_relay_framing.py` (host Python 3.10+).

## What is supported

| | Status |
|---|---|
| SELECT, plaintext Read (card mode, then wallet mode with path `44'/60'/0'/0/0`), skipping wallet indexes that are not secp256k1 | built, tested against the mock |
| Firmware below 4 (single wallet, key comes with Read) | built, tested on a recorded 2019 reply |
| Address from a 65-byte or 33-byte key | built; for 33 bytes the app passes a `cx_ecpoint_decompress` wrapper |
| Sign of a 32-byte digest, security delay `9789` resend loop, low-s, `v` by ecrecover trial | built, tested against the mock |
| AttestCardKey (live possession of the card key) | built; the app verifies the signature over `sha256(challenge‖salt)` with `cx_ecdsa_verify` |
| Access code entered by the user | the app sets `s.pin = sha256(code)` and restarts. `TG_NEED_ACCESS_CODE` tells it when. |
| Encryption (`6982`): OpenSession fast/strong, AES-CBC | **not built.** `TG_NEED_ENCRYPTION` reports it. The recipe is in the research note §4.5. |
| Pay-to-Tangem inside the app (unsigned pay-to-address path + signed-auth export) | **not built.** Needs a `cash.c` change owned by the ledger-cash workflow; see Wiring step 4. |
| WalletsList mode, backup cards, CVC, linked terminal | not built (not needed) |
| Proof the card is a genuine Tangem | partial. See the research note §7(c): offline the Flex can check a Tangem-signed card ID, but the certificate for the card key is online only. |

## Wiring into the ledger-cash app (handoff; this track does not edit `mvp/ledger-cash/`)

1. Makefile: `APP_SOURCE_PATH += ../../tangem/src`, or copy `src/` in. Optional: `ENABLE_ADDRESS_BOOK = 1` raises the 271-byte reader reply limit to 447 (`research/nfc-reader-mode.md` §1.5). Turn it on if card-mode Read times out.
2. Hooks: `keccak` (`cx_keccak_256_hash`, already in `cash.c`); `decompress` (`cx_ecpoint_alloc` + `cx_ecpoint_decompress` + `cx_ecpoint_export`, inside `cx_bn_lock`); `recover` (the existing static `ecrecover` in `cash.c`, signature `(z, v, r, s, addr)`, matches `tg_recover_fn`).
3. Reader loop:

```c
static tg_session_t g_tg;
static uint8_t g_tg_apdu[160];

static void tg_on_resp(bool error, bool timeout, uint8_t *data, size_t len) {
    if (error || timeout) { g_tg.state = TG_ST_FAILED; g_tg.why = TG_ERR; return; }  /* card moved, or reply > 271 B */
    size_t n = tg_next(&g_tg, data, len, g_tg_apdu, sizeof g_tg_apdu);              /* copies what it keeps */
    if (n) io_nfc_reader_send(g_tg_apdu, n, tg_on_resp, 3000);  /* 3 s covers one security-delay tick (INFERRED) */
    /* else: DONE or FAILED -> the UI loop reads g_tg (never call NBGL from this callback) */
}
/* on CARD_DETECTED: */
tg_session_init(&g_tg);                    /* default access code, ETH path */
/* role (b) only: g_tg.want_sign = true; memcpy(g_tg.digest, eip712_digest, 32); */
size_t n = tg_next(&g_tg, NULL, 0, g_tg_apdu, sizeof g_tg_apdu);
io_nfc_reader_send(g_tg_apdu, n, tg_on_resp, 1000);
/* DONE: tg_eth_address(g_tg.card.wallet_pubkey, g_tg.card.wallet_pubkey_len, keccak, decompress, addr);
 *       show "Pay X USDC to Tangem card <card_id last 4> 0x<addr>" */
```

4. **Pay-to-Tangem needs a `cash.c` change; a Read alone is not enough.** Today `pay_check` refuses any request whose `payeeSig` does not ecrecover to `payTo` (`SW_BAD_PAYEE_SIG`), and the signed auth is handed to the payee device over `PUT_AUTH`. A Tangem card can do neither. Chosen route (option 1, no card signing needed):
   - a pay-to-address entry in `cash.c`: `payTo` = `tg_eth_address(...)` from the finished `tg_next` session, value typed on the Flex, chainId/token from the app config. The `payeeSig` check is skipped on this path only, because the address came straight from the card over the reader, not from a relayed request. Balance and replay checks stay.
   - an outbox for the signed auth (the same `from‖to‖value‖validAfter‖validBefore‖nonce‖v‖r‖s` as `PUT_AUTH`), read over USB with a new APDU, so a laptop can submit `transferWithAuthorization`.
   - Option 2, later: once plaintext Sign works on hardware, the card signs `eip191(keccak(body))` as a real `payeeSig` and `pay_check` runs unchanged. The auth export is still needed, since there is no payee device to receive `PUT_AUTH`.
5. Debug hook for the hardware run: a USB APDU (for example INS `0x60`) that returns `state, why, last SW, card_id, fw, settings, wallet_index, address`. With it, Paris can be debugged from a laptop over USB while the card sits on the Flex. USB and the reader coexist since SDK PR #987.

## Hardware test steps

### Sahas alone, any time (iPhone + Tangem app)
1. Open the Tangem app and scan each card. For each one, write down the **card ID** (card settings), the **Ethereum address** of the main wallet, whether an **access code** is set, and whether the card is part of a backup set. Do not reset or purge anything.
2. Pick the demo card. Note: a card with no access code (default `000000`) is a bearer note, so anyone holding it can spend from it. Keep only demo funds on it.
3. Send a little Sepolia/Base-Sepolia USDC to that ETH address (or whatever chain ledger-cash settles on) so step 8 below has something to show.

### Paris, collaborator's Flex + Sahas's card (after tangem.c is wired into the app)
0. Flex Settings: confirm NFC is **on** and note the OS version (needs flex 1.4.1 or later; build against the matching `API_LEVEL_<N>` branch).
1. Install the app (`sideload.ps1 -Device flex -Load`), open it, and start the Tangem read. Hold the card flat against the back of the Flex and move it around slowly until the reader fires.
2. **SELECT.** Expect `9000`. If it times out, nothing else will work: the problem is framing or AID routing. Record what the debug APDU shows.
3. **Read card.** Expect the card ID from step 1 of the iPhone checks.
   - Timeout here with SELECT OK most likely means the reply is over 271 bytes. Rebuild with `ENABLE_ADDRESS_BOOK = 1`, then try the LegacyMode TLV (research note §2).
   - `6982` (WHY 4): the card requires encryption. Stop; this is the case for building fast encryption (research note §4.5).
   - `6AF1`/`6A86` (WHY 2): an access code is set. Type it on the Flex (or set it in a debug build) and retry.
4. **Read wallet.** Expect `secp256k1` at some index. **The address on the Flex must equal the address in the Tangem app.** This is the pass/fail line for PAY-TO-TANGEM. If it differs, the path or the wallet index is wrong.
5. PAY-TO-TANGEM (needs the Wiring step 4 `cash.c` path): type the amount on the Flex, approve; the Flex signs EIP-3009 from its own key to the card's address and puts the auth in its outbox. Read it over USB from a laptop, submit `transferWithAuthorization`, and check that the Tangem app shows the USDC.
6. (Stretch, role b) Sign: digest = the EIP-712 digest of a 0.01 USDC transfer from the Tangem address. Watch for `9789` ticks (security delay) and keep the card still. Check that the app finds `v` (27 or 28) and that settlement accepts it.
7. (Optional) AttestCardKey: the signature verifies under the card public key. Optionally check the `86` card-ID signature against Tangem's key (research note §7c).
8. Write every SW, reply length and timing into `WORKLOG.md`.

## Risks
- **Licence** (above).
- **271-byte reply cap** on the Flex reader against card-mode Read size. The mock replies in about 200 bytes; a real card is unknown.
- **Extended-length Lc** (`00 hi lo`): the Tangem SDK always sends it. Whether the Flex MCU forwards it in reader mode is unknown.
- **Encryption required** on production cards. If so, plaintext fails at the first Read.
- **Access code UX**: the payee typing a secret on the payer's device is awkward. A default-code card avoids it but is a bearer instrument.
- **Wallet index / key format** on Wallet 2.0 cards (the mock puts secp256k1 at index 1 on purpose to exercise the loop).
- The `9789` resend loop has no limit, and the snippet re-arms `io_nfc_reader_send` from the callback, so taking the card away is how the user cancels.
- Nothing here has touched a real Tangem card or a Flex.
