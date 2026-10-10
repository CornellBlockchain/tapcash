# NFC reader mode on the Ledger Flex: what the SDK actually exposes, and what we can build with one Flex

Research note for N3XT @ OP3N 2026, written 2026-10-10 (Saturday). Deadline Tuesday 2026-10-13 23:59 CEST. Hardware on hand: one Ledger Flex (NFC), one Nano S Plus (no radio), a Windows 11 host with no PC/SC reader. Nothing in this note was run on hardware.

This note replaces the NFC conclusions in `device-capabilities-nfc-ble.md` (§1, §5, §6, §8) and `custom-device-apps-bolos-speculos.md` (§0 item 4, §6). Those notes read the docs and the `lib_nfc` header and called reader mode "undocumented beyond a header" with "zero precedent". The full implementation is in the SDK source, Ledger has fixed it three times, and it is the missing piece for any "tap something to your Ledger" idea.

Every claim is marked VERIFIED (primary source read; file:line, commit or URL given) or INFERRED (reasoned, searched or not checked against a primary source). Unless stated otherwise, SDK line numbers refer to `LedgerHQ/ledger-secure-sdk` master at `b03e7d647f9ef99b0327cef8840f35781697f069` (2026-10-08), Speculos line numbers to `LedgerHQ/speculos` at `abc6b7d93639c58e9309c4d05c3966e554ba6a52` (2026-10-09).

## 0. Bottom line

1. **A device app can be an NFC reader.** The SDK ships an app-level reader API: `io_nfc_reader_start`, `io_nfc_reader_send`, `io_nfc_reader_stop`, with `CARD_DETECTED` / `CARD_REMOVED` events and a per-command response callback. It is enabled with `ENABLE_NFC=1` plus `ENABLE_NFC_READER=1` on Flex, Stax and Apex P (Nano Gen5). VERIFIED (`io_legacy/include/os_io_legacy.h:109-118`, `Makefile.standard_app:34-46`).
2. **The trap: the default build compiles the reader dispatch out.** The code that turns NFC events and card responses into those callbacks sits in the app-side IO stack under `#ifndef USE_OS_IO_STACK` (`io/src/os_io.c:187-531`, reader hooks at `:361-379`), and `Makefile.standard_app:194-197` defines `USE_OS_IO_STACK` by default. With the default build, card responses (packet type 0x41) hit the `default:` branch of `io_legacy_apdu_rx` and are dropped (`os_io_legacy.c:497`). The build succeeds and the callbacks never fire. Every NFC build should set `DISABLE_OS_IO_STACK_USE = 1`, as `app-security-key` (the one shipping NFC app) does. VERIFIED from source; behaviour on a real Flex INFERRED.
3. **Ledger built it on purpose and nobody uses it.** PR #777 "Add NFC reader mode support" (merged 2024-12-12), fixed by #987 (2025-06-10) and #1044 (2025-07-16). Open PR #1243 renames the functions and says "Since no app in production uses this API, it should not impact anybody." Public code search finds no consumer. A working third-party reader app would be the first we can find. VERIFIED.
4. **One Flex is enough for a tap demo.** The counterparty does not have to be a Ledger. A Flex reader can talk to ISO 14443-A/B targets: an Android phone running HCE, an NFC Forum Type 4 tag, a JavaCard, a contactless bank card, a YubiKey, or another NFC Ledger in card mode. That ISO-DEP APDUs go over the air unchanged is INFERRED; the API is APDU-shaped and the MCU firmware is closed.
5. **Ledger-to-Ledger still needs a second NFC Ledger for the final demo.** The Nano S Plus has no radio. Development does not need one: an Android HCE stub can play the other Ledger, and two Speculos instances can be bridged once a small Speculos patch is applied (INFERRED, not run).
6. **Speculos cannot run reader mode as shipped.** It exits on the first `io_nfc_reader_start` call. A three-part recipe (own-stack build, a patched `seproxyhal.py` bind-mounted into the image, `--transport NFC`) should make it work. INFERRED, not run.
7. **The app is C.** The Rust SDK has no `lib_nfc` and no reader bindings. VERIFIED.

## 1. The SDK API

### 1.1 Build flags

| Flag | Effect | Source |
|------|--------|--------|
| `ENABLE_NFC = 1` | `HAVE_NFC`, adds `lib_nfc`, sets `HAVE_APPLICATION_FLAG_BOLOS_SETTINGS` (0x200). Only for `TARGET_STAX TARGET_FLEX TARGET_APEX_P`. | VERIFIED `Makefile.standard_app:34-40` |
| `ENABLE_NFC_READER = 1` | Adds `HAVE_NFC_READER` only. Same three targets. Does nothing without `ENABLE_NFC`, because the reader routing in `os_io.c:362-379` is nested inside `#ifdef HAVE_NFC` and `os_io_legacy.c:40-42` includes `lib_nfc`'s `nfc_ledger.h`. | VERIFIED `Makefile.standard_app:42-46` |
| `DISABLE_OS_IO_STACK_USE = 1` | Stops `Makefile.standard_app:194-197` from defining `USE_OS_IO_STACK`, so the app compiles and runs its own `os_io_init` / `os_io_rx_evt` / `os_io_tx_cmd`. `USE_OS_IO_STACK` is also skipped under `HAVE_LEGACY_PID`, and `DEBUG_OVER_USB` forces the flag on (`:138`). | VERIFIED |

`io_legacy` itself is compiled into every app with no flag (`Makefile.rules:48`, `SDK_SOURCE_PATH += io io_legacy protocol lib_u2f_legacy`). VERIFIED.

`app-security-key` sets `DISABLE_OS_IO_STACK_USE = 1` (Makefile line 163) and `ENABLE_NFC = 1` (line 175) at `d6f57fb11fba8611cb59531be98c5b2c0280d37f`. It is a card-emulation app, does not set `ENABLE_NFC_READER`, and gives no reason for the own-stack flag. VERIFIED. https://github.com/LedgerHQ/app-security-key/blob/d6f57fb11fba8611cb59531be98c5b2c0280d37f/Makefile#L163-L175

### 1.2 Why the own IO stack matters (the part both earlier notes missed)

- `io/include/os_io.h:149-164` declares `os_io_init`, `os_io_start`, `os_io_rx_evt`, `os_io_tx_cmd` as `SYSCALL`. With `USE_OS_IO_STACK` the app's copies in `os_io.c:187-531` are compiled out and the calls go to weak syscall stubs (`src/syscalls.c:1625-1649`) that enter the closed OS IO stack. VERIFIED.
- The reader dispatch lives only in that app-side copy: on `SEPROXYHAL_TAG_NFC_APDU_EVENT` with `dst[0] == OS_IO_PACKET_TYPE_NFC_APDU_RSP` it calls `os_io_nfc_reader_rx()`, and on `SEPROXYHAL_TAG_NFC_EVENT` or a ticker it calls `os_io_nfc_evt()` (`os_io.c:361-379`). The app's copy of `process_itc_event` that turns `ITC_IO_NFC_START_READER` into `NFC_LEDGER_start(READER)` is at `os_io.c:75-183` (case at `:160-162`), under the same guard. Code search finds no other caller of `os_io_nfc_evt` / `os_io_nfc_reader_rx`. VERIFIED.
- In the default build, `io_legacy_apdu_rx` has no case for packet type 0x41 (it lands in `default:` at `os_io_legacy.c:497` and is dropped), and SEPH events including `NFC_EVENT` go to `io_event(CHANNEL_APDU)` (`:365-382`), never to the reader context. VERIFIED.
- Card emulation is different. `io_legacy_apdu_rx` accepts `OS_IO_PACKET_TYPE_NFC_APDU` (0x40) in both modes (`os_io_legacy.c:157` and `:396`). So a CE app with the default OS stack would receive NFC APDUs if the closed OS stack delivers them. That is INFERRED and untested; in Speculos it cannot work (see §5). The practical recipe is still to set `DISABLE_OS_IO_STACK_USE = 1` on every NFC build, CE or reader, so the behaviour matches `app-security-key` and Speculos.
- It is INFERRED, not shown, that the OS ignores the reader start in the default build. The ITC command still reaches the OS through the syscall and the OS's own `process_itc_event` may power the reader. What is VERIFIED is that the app would never see the events or responses.

### 1.3 Functions, types, events

Declared in `io_legacy/include/os_io_legacy.h:109-118` under `HAVE_NFC_READER`. Types in `io_legacy/include/os_io_legacy_types.h:57-88`. VERIFIED.

```c
enum card_tech { NFC_A, NFC_B };
enum nfc_event { CARD_DETECTED, CARD_REMOVED };
struct card_info { enum card_tech tech; uint8_t nfcid[7]; size_t nfcid_len; };

typedef void (*nfc_evt_callback_t)(enum nfc_event event, struct card_info *info);
typedef void (*nfc_resp_callback_t)(bool error, bool timeout, uint8_t *resp_data, size_t resp_len);

bool io_nfc_reader_start(nfc_evt_callback_t callback);
bool io_nfc_reader_send(const uint8_t *cmd_data, size_t cmd_len,
                        nfc_resp_callback_t callback, int timeout_ms);
void io_nfc_reader_stop(void);
/* defined in os_io_legacy.c:678 but NOT declared in the public header */
bool io_nfc_is_reader(void);
```

Behaviour, read from `os_io_legacy.c:533-680` (VERIFIED unless marked):

- `io_nfc_reader_start` stores the callback, sets `reader_mode = true`, sends `os_io_nfc_cmd_start_reader()` and returns `true` unconditionally (`:657-666`), although the header comment says it can return false. The switch is asynchronous: the command goes out as `SEPROXYHAL_TAG_ITC_CMD` (0x5D) `[0x5D,0,1,0x12]` (`os_io_seph_cmd.c:461-469`), and when the MCU returns it as an `ITC_EVENT` (0x1A) the app-side `process_itc_event` calls `NFC_LEDGER_start(NFC_LEDGER_MODE_READER)` (`os_io.c:151-163`). That the MCU echoes the command back is INFERRED from that code path.
- `io_nfc_reader_send` stores the response callback, sends the bytes with `os_io_tx_cmd(APDU_TYPE_NFC, cmd, len, 0)` and arms `remaining_ms = timeout_ms` (`:643-655`). It ignores the send status and always returns true.
- `CARD_DETECTED`: `tech` is `NFC_A` if the SEPH sub-type is 0x01, otherwise `NFC_B`; `nfcid_len = MIN(size-2, 7)`, so a 10-byte UID is truncated (`:545-553`). There is no SAK, ATQA, ATS or ATQB.
- INFERRED likely bug: `io_nfc_event` copies `nfcid` from `G_io_seproxyhal_spi_buffer + 5` (`:551-553`), but with the app's own stack that buffer is refreshed only after `os_io_rx_evt` returns (`:147`, `:367`). The UID passed to the callback probably holds bytes from the previous SEPH packet. `tech` and `nfcid_len` are correct. Do not rely on the UID until checked on hardware.
- `CARD_REMOVED` while a command is pending calls `resp_cb(error=true, ...)`. VERIFIED (`:576-623`).
- Timeouts count down 100 ms per ticker event (`io_nfc_ticker`, `:613-623`); expiry calls `resp_cb(false, true, NULL, 0)` (`:587-591`). Use timeouts in multiples of 100 ms.
- The response pointer points into `G_io_seproxyhal_spi_buffer`, the shared SEPH/UX buffer. Copy the bytes inside the callback. `resp_callback` is cleared before the call, so each send gets one callback. VERIFIED (`:576-623`).
- `io_nfc_reader_stop` clears the context and sends `os_io_nfc_cmd_stop()` (ITC 0x10), which powers NFC off. It does not restore card emulation; call `os_io_nfc_cmd_start_ce()` (ITC 0x11) yourself, there is no `io_legacy` wrapper (`:668-676`, `os_io_seph_cmd.c:441-469`).

### 1.4 Settings gate and permissions

- `NFC_LEDGER_start` powers the front end only if `os_setting_get(OS_SETTING_FEATURES, NULL, 0) & OS_SETTING_FEATURES_NFC_ENABLED`. Otherwise it returns silently with no event (`lib_nfc/src/nfc_ledger.c:103-104`). `io_nfc_reader_start` and `io_nfc_is_reader` still report true. The app must check the setting itself and tell the user. VERIFIED.
- The SDK's factory default for the NFC feature bit is on (`include/os_settings.h:164`, `FEATURES_DEFAULT_NFC_ENABLED 1`). VERIFIED. The earlier note's "NFC disabled by default" came from a search snippet of a support article and may describe the Security Key setting or older firmware. INFERRED. Check the Flex's Settings either way.
- `os_setting_get` needs `APPLICATION_FLAG_BOLOS_SETTINGS` (0x200). `ENABLE_NFC` sets it, and so does `ENABLE_BLUETOOTH`, which the C boilerplate already has (Makefile line 99). There is no NFC-specific app flag in `include/appflags.h` and no NFC field in `ledger_app.toml`. VERIFIED. Whether the OS or MCU filters reader power-on for a sideloaded, unreviewed app cannot be seen from the open source. INFERRED, Day-1 gate.
- `include/os_settings.h:159-161` defines `OS_SETTING_FEATURES_CHARON_BACKUP 0x80` ("Charon" is the Recovery Key card's internal codename in the Synacktiv report). VERIFIED that the flag exists; its meaning is INFERRED.
- `io_legacy` refuses to pass an incoming APDU to the app while a PIN is set and not validated (`SWO_SEC_PIN_15`, `os_io_legacy.c:136-137,412-418`). Both devices must be unlocked with the app open. VERIFIED.

### 1.5 Wire path and size limits

- Command path: `io_nfc_reader_send` → `os_io_tx_cmd(0x40)` → `NFC_LEDGER_send` (`os_io.c:471-474`) → `LEDGER_PROTOCOL_tx` chunks of up to 158 bytes (channel id, tag 0x05, seq, total length on the first chunk) → `SEPROXYHAL_TAG_NFC_RAPDU` (0x4A) to the MCU (`nfc_ledger.c:61-77,185-230`). VERIFIED.
- Response path: MCU → `SEPROXYHAL_TAG_NFC_APDU_EVENT` (0x1C) chunks → reassembly writes packet type 0x41 at `buffer[0]` (`protocol/src/ledger_protocol.c:89`) → `os_io.c:366-367` → `os_io_nfc_reader_rx` → response callback. VERIFIED.
- The SDK never builds ISO 7816 or ISO-DEP framing. What the closed MCU puts on the air is not in any public source. INFERRED that it sends the bytes as an ISO-DEP (ISO 14443-4) APDU: every name says APDU, PR #665 calls the transport "NFC APDUs", and Ledger's known reader target is a JavaCard. INFERRED that Type 2 tags (NTAG213/215/216, `READ 0x30`) cannot be read.
- Response size: with the default `OS_IO_SEPH_BUFFER_SIZE=272` (`Makefile.defines:218-223`), responses of up to 271 bytes reach the callback. 272 bytes or more are dropped with no error callback and the request ends in a timeout. Raising `CUSTOM_IO_APDU_BUFFER_SIZE` does not help, because `apdu_rx_max_size` is tied to the SEPH buffer (`os_io_legacy.c:318-321,566-574`); `ENABLE_ADDRESS_BOOK=1` raises it to 447. VERIFIED by tracing the source; not run.
- Command size: chunked by the SDK, so limited by what the MCU accepts in reader mode, which is undocumented. Keep commands short APDUs. INFERRED.

### 1.6 Card emulation (CE) in the same app

- `os_io_start` calls `NFC_LEDGER_start(NFC_LEDGER_MODE_CARD_EMULATION)` (`os_io.c:264-266`), so an `ENABLE_NFC` app is a card as soon as it opens. CE APDUs arrive as packet type 0x40 through the normal `io_recv_command` path. VERIFIED.
- One mode at a time: `nfc_ledger_data` holds a single mode and `NFC_LEDGER_start` resets protocol state on a mode change (`nfc_ledger.c:93-123`). The app switches with `os_io_nfc_cmd_start_reader / start_ce / stop`. VERIFIED in the SDK; whether the RF front end ever does both is INFERRED.
- In CE the app sees every ISO 7816 SELECT. `app-security-key` answers `SW_FILE_NOT_FOUND` for unknown AIDs with the comment "Readers probe other applications before ours (Android selects the NDEF Tag Application first)" and chunks responses with 61xx / GET RESPONSE (`src/u2f_processing.c:368-380`, `src/nfc_io.c`). So a CE app can answer its own AID or emulate a Type 4 NDEF tag. VERIFIED for the FIDO AID; INFERRED for the NDEF AID.
- USB and NFC coexist. PR #987 fixed "Using the reader mode while exchanging apdus over USB did not work properly" by sending reader commands through `os_io_tx_cmd(APDU_TYPE_NFC, ...)` instead of switching the global legacy APDU type. A laptop can drive the app over USB while the Flex reads a card. VERIFIED that the fix exists; not tested on hardware.

### 1.7 NDEF helpers

`lib_nfc/include/nfc_ndef.h`: `os_parse_ndef`, `os_ndef_to_string`, `os_get_uri_header`, TEXT and URI records, `NFC_TEXT_MAX_LEN 215`. VERIFIED. There is a fuzz harness for it (`fuzzing/sdk-fuzz/harness/fuzz_nfc_ndef.c`). The SDK does not implement the Type 4 read sequence; the app sends the SELECT / READ BINARY APDUs itself. The old Stax "publish an NDEF tag" path (`io_seproxyhal_nfc_init`) became opt-in under `HAVE_NDEF_SUPPORT` in PR #412 (2023-09-05). VERIFIED.

### 1.8 Which SDK branch, which OS

- The reader API exists on SDK branches `API_LEVEL_23` (as `include/os_io_nfc.h` + `src/os_io_nfc.c`, commit `51d0719f7e`, 2024-09-09) and `API_LEVEL_24` through `27` plus master (in `io_legacy/`). It is absent on `API_LEVEL_22` and older. VERIFIED (git trees per branch).
- API 23 is in no released OS. The first Flex OS with the reader in its SDK is `flex_1.4.1` (API 24); then `flex_1.5.0` (25), `flex_1.6.x` (26), `flex_1.7.0` (27, the only active level). Stax 1.8.1+, Apex P 1.0.4+. VERIFIED (`README.md:54-75`, `api_levels.json`).
- Build against the `API_LEVEL_<N>` branch matching the Flex's OS, not master (`API_LEVEL=0`). The `ledger-app-builder` image ships v27.1.2, which contains #777, #835 (which carried #987 to master) and #1044. VERIFIED.
- PR #1243 (open since 2025-09-29, merge conflicts, no activity since 2025-10-28) would rename everything to `os_io_nfc_*` and move it to `io/src/os_io_nfc.c`. Pinning the API_LEVEL branch protects against it. VERIFIED.
- No CHANGELOG entry mentions the reader, and `lib_nfc/doc/mainpage.dox` still says "only available on Stax" and "TO BE COMPLETED". VERIFIED.

### 1.9 History

| When | What | Source |
|------|------|--------|
| 2024-09-09 | Commit `51d0719f7e` "Add support to start NFC in CE and reader mode" (Yves Richard) | VERIFIED |
| 2024-09-11 | `LedgerHQ/applet-recovery-key` (the Recovery Key JavaCard) created | VERIFIED `gh api repos/LedgerHQ/applet-recovery-key` |
| 2024-12-12 | PR #777 "Add NFC reader mode support", "Add application support for NFC in reader mode", merged to master (`e5a295a`) | VERIFIED |
| 2025-02-19 | IO revamp moves the reader into `io_legacy` (`7968333824`) | VERIFIED |
| 2025 | `9eb2842108` "Fix for NFC reader mode" (two threads report different dates, 2025-04-01 and 2025-06-05) | VERIFIED commit; date unresolved |
| 2025-06-10 | PR #987 "Fix NFC reader support for apps" merged into `pr-io-revamp` (`a8f47fe`); reached master the same day through PR #835 "IO revamping" (`1fc96d8`). Fixes: power notifications reported as bogus APDUs, responses delayed to the next ticker, reader broken during USB APDU exchange | VERIFIED |
| 2025-06-24 | Ledger Recovery Key announced for Stax and Flex | VERIFIED https://www.ledger.com/blog-ledger-recovery-key |
| 2025-07-16 | PR #1044 (master, `252231f`) and #1045 (API_LEVEL_24) "Call NFC reader functions directly from os_io_rx_evt()" | VERIFIED |
| 2025-09-29 | PR #1243 opened: rename, "no app in production uses this API" | VERIFIED https://github.com/LedgerHQ/ledger-secure-sdk/pull/1243 |

The link between the SDK reader and the Recovery Key is not stated anywhere. It rests on the timing and on the `!defined(HAVE_BOLOS)` guards in `os_io.c:26`, which suggest the OS build defines `HAVE_NFC_READER` too. INFERRED.

## 2. Minimal C sketch

A probe for a fork of `LedgerHQ/app-boilerplate` (C). INFERRED to compile; untested. It shows the shape, not a finished app.

Makefile additions:

```make
ENABLE_NFC = 1
ENABLE_NFC_READER = 1
DISABLE_OS_IO_STACK_USE = 1   # without this the reader callbacks never fire
```

```c
#include "os.h"
#include "os_settings.h"
#include "os_io_legacy.h"

extern bool io_nfc_is_reader(void);           /* no prototype in the header */

static const uint8_t SELECT_PPSE[] = {         /* 00 A4 04 00 0E "2PAY.SYS.DDF01" 00 */
    0x00, 0xA4, 0x04, 0x00, 0x0E, '2', 'P', 'A', 'Y', '.', 'S', 'Y', 'S',
    '.', 'D', 'D', 'F', '0', '1', 0x00};

static uint8_t g_resp[271];                    /* replies over 271 B are dropped */
static size_t  g_resp_len;
static volatile int g_state;                   /* 0 idle, 1 got reply, 2 timeout, 3 error */

static void on_resp(bool error, bool timeout, uint8_t *data, size_t len) {
    if (error)   { g_state = 3; return; }       /* card removed mid-command */
    if (timeout) { g_state = 2; return; }       /* also what an oversize reply looks like */
    g_resp_len = MIN(len, sizeof(g_resp));
    memcpy(g_resp, data, g_resp_len);          /* data lives in the shared SEPH buffer */
    g_state = 1;                               /* expect ... 90 00 at the end */
}

static void on_card(enum nfc_event evt, struct card_info *info) {
    if (evt == CARD_DETECTED) {
        /* info->tech is NFC_A or NFC_B; info->nfcid may be stale, see §1.3 */
        io_nfc_reader_send(SELECT_PPSE, sizeof(SELECT_PPSE), on_resp, 1000);
    }
}

bool nfc_probe_start(void) {
    if (!(os_setting_get(OS_SETTING_FEATURES, NULL, 0) & OS_SETTING_FEATURES_NFC_ENABLED)) {
        return false;                          /* show "turn NFC on in Settings" */
    }
    return io_nfc_reader_start(on_card);       /* always true; failure shows up as silence */
}

void nfc_probe_stop(void) {
    io_nfc_reader_stop();                      /* radio off */
    os_io_nfc_cmd_start_ce();                  /* only if the app should be a card again */
}
```

Callbacks run from the IO event path, so the UI loop (NBGL) reads `g_state` and draws the result; do not call NBGL from inside the callback. INFERRED from how `io_event` dispatch works in the boilerplate.

## 3. What the reader can talk to

- ISO 14443-A and -B only. The SEPH event has sub-types `CARD_DETECTED_A=0x01` and `_B=0x02` (`include/seproxyhal_protocol.h:163-176`); there is no NFC-F (FeliCa) and no NFC-V (ISO 15693). VERIFIED at the protocol level; the radio's own capabilities are closed.
- ISO-DEP APDU targets: INFERRED to work. That includes Android HCE, Type 4 tags (NTAG 424 DNA, NTAG 413), JavaCards, EMV cards, YubiKey 5 NFC, the Ledger Recovery Key, and another NFC Ledger in CE.
- Type 2 tags (NTAG21x, MIFARE Ultralight): probably only `CARD_DETECTED` with a UID, no data. INFERRED.
- A tag that carries a payment request should be a Type 4 tag: `00A4040007D276000085010100` (SELECT NDEF app), `00A4000C02E103` (CC), `00B000000F`, `00A4000C02E104` (NDEF file), `00B0000002` (NLEN), then `00B00002<NLEN>`. INFERRED (NFC Forum T4T procedure, not fetched); the parser for the payload is `os_parse_ndef` (VERIFIED).

## 4. Counterparties we could tap

| Target | What a Flex reader gets without secrets | Cost / availability by Tue 13 Oct | Status |
|--------|------------------------------------------|-----------------------------------|--------|
| Contactless bank card or unlocked phone wallet | `SELECT PPSE` lists AIDs (Visa `A0000000031010`, Mastercard `A0000000041010`); SELECT AID, GPO with PDOL, READ RECORD per AFL give PAN and expiry. Copyable, no verifiable signature. Show last 4 digits only; never send GPO cryptograms anywhere. | Everyone has one. | INFERRED (EMV Book 3, not fetched) |
| Android phone running our HCE app | Anything we program. HCE emulates ISO-DEP over NFC-A, routes on the first SELECT AID (no partial match), needs the screen on, one logical channel, random UID, about 1 KB per 300 ms. | Needs an NFC Android owner and about 100 lines of Kotlin (`HostApduService`). | VERIFIED https://developer.android.com/develop/connectivity/nfc/hce |
| Android phone, stock NDEF-emulator app | e.g. "NFC NDEF Tag Emulator" (`com.maxsoft.ndeftagemulator`). Whether it answers the T4T sequence on `D2760000850101` is unconfirmed. | Free, Play Store. | VERIFIED listing; behaviour INFERRED |
| NTAG 424 DNA | Type 4, ISO 14443-A, 416 B (CC 32, NDEF 256, protected 128), AES-128 mutual auth, SUN/SDM CMAC mirrored into the NDEF read. A Flex holding the SDM key can verify it offline with `cx_cmac` (`lib_cxng/include/lcx_cmac.h:16-26`, behind `HAVE_CMAC`). Ships with zero keys and SDM off; provision with NXP TagWriter or from the Flex. | About €1-3 each, mail order; next-day at best. | VERIFIED https://www.nxp.com/products/NTAG424DNA ; provisioning INFERRED |
| Ledger Recovery Key | SELECT `A0000000624C45444745523031`, `GET_STATUS 08 F2 00 00` (TLVs: target id `33400004`, 4-byte serial, 3-byte applet version, lifecycle and transient FSM state), and GP `INITIALIZE UPDATE 80 50` (handshake output returned to anyone). Every other `CLA 08` INS fails `checkSecurityLevel()` without an SCP03 session using Ledger's keys, and then needs a Ledger-signed host certificate (`VALIDATE_HOST_CERTIFICATE 0x51`) and the PIN. No genuineness or liveness proof is available to us. | In the box only for Flex units sold after the bundle started (announced 2025-06-24; start date not published). $39 spare. | VERIFIED `applet-recovery-key` @ `3088fa3d73` `AppletRecoveryKey.java` process() and `checkSecurityLevel()` ~`:328-338`, `CommandProcessor.java:90-109`, `Constants.java:24-40`; bundling date INFERRED |
| YubiKey 5 NFC | AIDs: FIDO `A0000006472F0001`, OpenPGP `D27600012401`, PIV `A000000308`, OATH `A0000005272101`, MGMT `A000000527471117`. U2F/CTAP assertion with challenge = action hash returns a P-256 ECDSA signature the Flex can check with `cx_ecdsa_verify_no_throw`. | About €55-60; only if someone owns one. | AIDs VERIFIED (`Yubico/yubikey-manager yubikit/core/smartcard/__init__.py:95-105`); flow INFERRED |
| Coinkite SATSCARD / TAPSIGNER | SELECT `f0436f696e6b697465434152447631`, one APDU with CBOR; `read` returns a pubkey and a signature over our nonce. | Mail order only; out. | VERIFIED `coinkite/coinkite-tap-proto docs/protocol.md:73-94,231-245` |
| Arx HaLo (Kong, event badges) | SELECT `A0000009490148614C6F00`; secp256k1 sign of a digest, returns an ETH address. | Only if someone owns one. | VERIFIED `arx-research/libhalo core/src.ts/aid.ts` |
| Blank JavaCard (J3R180) | Anything, once our applet is loaded with GlobalPlatformPro. | Needs a PC/SC reader we lack, Java toolchain and mail order. Out. | INFERRED |
| ICAO passport | Only EF.CardAccess without BAC/PACE. BAC needs 3DES and SHA-1, and `lib_cxng` has neither header. | Drop. | VERIFIED (`lib_cxng/include` listing) |
| iPhone as card | EEA HCE entitlement needs an EEA-established organisation and agreements; the non-EEA NFC & SE Platform needs a commercial agreement and lab review. | Out. An iPhone can still be the reader for Security Key flows. | VERIFIED https://developer.apple.com/support/hce-transactions-in-apps/ , https://developer.apple.com/support/nfc-se-platform/ |
| Second NFC Ledger (Flex / Stax / Nano Gen5) | Anything our CE app answers. Its stock Security Key app already answers SELECT `A0000006472F0001`. | Only a teammate's. Nano Gen5 about $179. | INFERRED |

## 5. Speculos

- Stock Speculos cannot run reader mode. VERIFIED:
  - `seproxyhal.py:439-440` ignores `TAG_NFC_POWER` (0x34) with `pass`.
  - Nothing sends `NFC_EVENT` 0x1E; it is an unused enum member in `speculos/mcu/transport/nfc.py:13`.
  - `SephTag` (`seproxyhal.py:24-71`) has no 0x1A, 0x1E or 0x5D, and the unknown-tag branch calls `sys.exit(0)` (`:556-558`). `io_nfc_reader_start` sends 0x5D, so Speculos exits.
  - There is no NFC REST endpoint, and the `RAW!` escape in `to_app` calls `SephTag(tag)`, which raises for 0x1E (`:617-619`).
- Default-stack apps get no NFC APDUs in Speculos even in CE. Speculos serves the IO syscalls from its own copy of the SDK IO code, built with `HAVE_BOLOS`, `HAVE_NBGL`, `HAVE_IO_USB` only (`src/CMakeLists.txt:90-96`), so its `nfc_ledger.c` compiles to nothing and 0x1C reaches the app as a generic SEPH event. VERIFIED. Own-stack apps work: `app-security-key`'s CI job "Ragger NFC tests" runs `--transport NFC` on stax, flex and apex_p (`.github/workflows/build_and_functional_tests.yml:80-88`). VERIFIED.
- The vendored SDK copy in Speculos is a stale snapshot (`983b999055`, 2025-06-30) with pre-#1044 calls, so rebuilding Speculos with `HAVE_NFC` is not a viable route. VERIFIED.
- `sys_os_setting_get(OS_SETTING_FEATURES)` returns 0xff for Stax, Flex and Apex P (`src/bolos/os.c:49-60`), so the settings gate passes ("Flex and Stax OSes emulation always consider NFC to be up", CHANGELOG 0.12.0; `--transport NFC` from PR #519, 2024-11-25). VERIFIED.

**Recipe for reader development in Docker (INFERRED, not run). All three parts are needed:**

1. Build the app with `ENABLE_NFC=1 ENABLE_NFC_READER=1 DISABLE_OS_IO_STACK_USE=1` for Flex.
2. Patch `speculos/mcu/seproxyhal.py`: add `ITC_EVENT = 0x1A`, `NFC_EVENT = 0x1E`, `ITC_CMD = 0x5D` to `SephTag`, and in `SeProxyHal.can_read` add `elif tag == SephTag.ITC_CMD: self.socket_helper.queue_packet(SephTag.ITC_EVENT, data)`. Bind-mount it over `/speculos/speculos/mcu/seproxyhal.py` (the image runs `python ./speculos.py` from `/speculos` after `pip install -e .`, VERIFIED). Inject a card over the APDU TCP port as a frame: 4-byte big-endian length + `b'RAW!'` + `bytes([0x1E, 0x01, 0x01])` + a 4- or 7-byte UID (`0x02` instead of the second `0x01` for NFC-B). Removal: `bytes([0x1E, 0x02])`.
3. Run with `--transport NFC`. Reader commands leave as 0x4A, which the default USB transport drops ("Ignored", `transport/usb.py:155-157`) and the NFC transport forwards to the APDU client. Whatever the client sends back arrives as 0x1C and, in reader mode, becomes the card's reply.

Use the APDU TCP port, not REST `/apdu`, for the reader instance: REST waits for the next SE output as the reply and blocks on a `RAW!` injection. The TCP server prefixes outgoing frames with `len(packet)-2`, so read size+2 bytes; one client per instance (`speculos/mcu/apdu.py:42-45,75-112`). VERIFIED.

Docker command from Git Bash (flags VERIFIED from `--help` of `ghcr.io/ledgerhq/speculos:latest`, speculos 0.27.1):

```sh
MSYS_NO_PATHCONV=1 docker run --rm -it \
  -v "$PWD/build/flex/bin:/app" \
  -v "$PWD/seproxyhal.py:/speculos/speculos/mcu/seproxyhal.py:ro" \
  -p 5000:5000 -p 9999:9999 ghcr.io/ledgerhq/speculos:latest \
  --model flex --transport NFC --display headless --api-port 5000 --apdu-port 9999 /app/app.elf
```

Two-instance Ledger-to-Ledger (INFERRED): instance A runs the CE app with `--transport NFC`, instance B the reader app with the patch, both own-stack builds, on different host ports (`-p 5001:5000 -p 9998:9999`). A relay injects `CARD_DETECTED` into B, then loops: read B's command, send it to A, read A's reply, send it to B.

No-patch fallback (INFERRED): in a dev build, skip `io_nfc_reader_start`, call `NFC_LEDGER_start(NFC_LEDGER_MODE_READER)` directly, set the global `G_io_reader_ctx.reader_mode = true` (`os_io_legacy.c:71`), and call `io_nfc_reader_send` without waiting for `CARD_DETECTED`. That avoids both the 0x5D exit and the 0x1E injection.

## 6. Ledger products and prior art

- The Flex already reads a JavaCard in production: the Ledger Recovery Key, an NXP P71D600 on JCOP 4.5, CC EAL6+, talking only to a Ledger over NFC with GP SCP03 plus a Ledger secp256k1 certificate channel. The reader code is in BOLOS, not in an app. VERIFIED (https://www.ledger.com/ledger-recovery-key-white-paper ; Ledger Academy; Synacktiv report `doc/Synacktiv-Ledger-Security_Assessment_Report_v1.2_public.pdf`, which audited "the BOLOS code handling Charon card communication" on 2 Flex units).
- The applet licence is Ledger's "Source Code Accessibility License v1.0": audit and personal compilation on Ledger hardware, no commercial use; the white paper reserves patents. Fine as a probe target, not a platform. VERIFIED.
- No public repo exists for the wallet-side Recovery Key flow or the "Recovery Key Updater" app named in the white paper (several guessed repo names return 404). VERIFIED.
- No host SDK has an NFC transport: `LedgerHQ/device-sdk-ts` (develop, 5222 paths) and `LedgerHQ/ledger-live` (develop, 30714 paths) have no path matching `/nfc/i`. VERIFIED.
- Ledger's support article "Ledger devices and NFC" (18934878523037) reportedly says developers "will be able to create Ledger apps using the NFC transport". JS-rendered, read from search extracts only. INFERRED.
- Third-party NFC CE already exists: `structured-world/structured-passkeys` PR #20 "feat(nfc): CTAP over NFC on Stax, Flex and Nano Gen5" (merged 2026-10-04, `57a6cc2`), on a forked Rust SDK (`structured-world/ledger-device-rust-sdk` @ `bebc9af`) whose `nfc` feature compiles `lib_nfc` for CE only. The author reports Speculos NFC tests passing on stax, flex and apex_p and a hardware probe passing on a Nano Gen5 only. VERIFIED that the claims are made; Flex hardware INFERRED. So "first third-party NFC app" is false for CE. Reader mode would still be a first.
- No third-party reader use: code search for `io_nfc_reader_send`, `io_nfc_reader_start`, `HAVE_NFC_READER`, `NFC_LEDGER_MODE_READER`, `SEPROXYHAL_TAG_NFC_POWER_ON_READER`, `ITC_IO_NFC_START_READER` finds only the SDK, Speculos's vendored copy (event hooks only, no calls to the reader functions) and our repo. Default branches only; private apps cannot be ruled out. VERIFIED.
- Rust: upstream `ledger-device-rust-sdk` (master `4123d2d`) compiles neither `lib_nfc` nor `os_io_legacy.c`, binds no NFC header and never defines `HAVE_NFC`. Its only NFC mention is the comment on the `app_io_stack` feature (added `6934e01379`, 2026-10-07; `ledger_secure_sdk_sys/Cargo.toml:36-38`, `build.rs:268-273`). A Rust reader app would need a forked sys crate or `LEDGER_SDK_EXTRA_DEFINES` plus a hand-built `os_io_legacy.c` and FFI (INFERRED, untested). For this deadline the reader app is C. VERIFIED.
- Market: COLDCARD (ST25DV64KC dynamic tag, `Coldcard/firmware shared/nfc.py:5`), Tangem, Status Keycard, Arx HaLo and Ledger Unplugged (2013 JavaCard emulating a Type 4 tag, `LedgerHQ/ledger-javacard`) all have the hardware as the passive tag and the phone as the reader. Devices with screens that read cards (Cypherock X1, OneKey Pro with OneKey Lite, Ledger with the Recovery Key) read only their vendor's own paired cards. A screened hardware wallet that reads an arbitrary third-party card or tag and signs what it read was not found in the researched corpus. COLDCARD and Ledger Unplugged VERIFIED; the rest INFERRED from vendor pages and search extracts.
- Op3n 2026 is on 2026-10-15, two days after our deadline; no source found links it to NFC. INFERRED.

## 7. Architectures

Shared protocol for all of them (INFERRED design): a payment request of about 150 bytes `{ver, chainId u32, token addr20, value u64, payTo addr20, validBefore u64, reqNonce 16, label <= 24}`, optionally followed by a 65-byte payee signature and 65-byte pubkey, which keeps the whole record under the 271-byte reply limit. The payer's Flex verifies the payee signature with `cx_ecdsa_verify_no_throw` and checks `keccak(pubkey)[12:] == payTo`, shows the request on NBGL, and signs EIP-3009 `TransferWithAuthorization` with `nonce = keccak(request)` using `bip32_derive_ecdsa_sign_rs_hash_256` on `44'/60'/0'/0/0`. The helpers are VERIFIED in the SDK (`lib_standard_app/crypto_helpers.h:291-352`, `lib_cxng/include/lcx_ecdsa.h`) and in app-ethereum (`src/features/sign_message_eip712_common/common_712.c:25-62` @ `e5b6dbff3a`). Anyone holding the signature can call `transferWithAuthorization` (VERIFIED, https://eips.ethereum.org/EIPS/eip-3009). A replayed request maps to the same nonce and settles once. Not stopped: offline double-spend; the payee carries credit risk until settlement. The device has no trusted clock, so `validBefore` is displayed, and enforced only on-chain.

| | Who reads, who is the card | Hardware | Feasibility (3 days) |
|-|----------------------------|----------|----------------------|
| **B / N1: Flex reads the request** | Flex reader; payee's Android HCE app or a Type 4 tag is the card. Flex returns the authorization by a second APDU (UPDATE BINARY on a tag) or over USB. | Our Flex + an NFC Android or a Type 4 tag. | About 0.35, about 0.5 if the Day-1 gate passes by Sunday noon. INFERRED |
| **A / N2: Flex is a Type 4 tag** | Phone reader (Chrome Android Web NFC `NDEFReader.write` then `scan`); Flex in CE serves the signed authorization as an NDEF URI. Web NFC is NDEF-only (VERIFIED, https://w3c-cg.github.io/web-nfc/). An iPhone can read the URI by background tag reading but cannot write (INFERRED). | Our Flex + an NFC Android with Chrome. | About 0.6. Testable in stock Speculos `--transport NFC` with an own-stack build. INFERRED |
| **C / N3: Ledger-to-Ledger** | Payee Ledger in CE (default after `os_io_start`), payer Flex switches to reader, reads and verifies the payee-signed request, writes the authorization back. Same app on both. | Needs a second NFC Ledger for the demo; develop against an HCE stub or two Speculos instances. | About 0.25. INFERRED |
| **D: stock Security Key (I02)** | Phone reader, Flex Security Key app attests the receive address; Nano S Plus signs EIP-3009 over USB. | Our kit + iPhone or Android 14+. | About 0.7; the tap attests and does not carry the payment. INFERRED |

The Nano S Plus cannot take part in any tap. Its honest role in A to C is the payee's cold key, signing the request once over USB with the stock Ethereum app.

## 8. Day-1 gates (hardware, in this order)

0. Read the Flex OS version (Settings > About). It needs `flex_1.4.1` or later; pick the matching `API_LEVEL_<N>` branch. Check that NFC is on in Settings.
1. **Reader gate (decides N1, N3, N4).** Sideload a C boilerplate fork with `ENABLE_NFC=1 ENABLE_NFC_READER=1 DISABLE_OS_IO_STACK_USE=1` that runs the sketch in §2. Hold a contactless bank card to the Flex. GO if `CARD_DETECTED` fires and the response callback gets an FCI ending `90 00`. That one result shows a sideloaded app may drive the reader, that events reach the app, and that plain ISO-DEP goes over the air. NO-GO on no event, a timeout or an exit.
2. **Framing.** If gate 1 gives a timeout but `CARD_DETECTED` fires, retry with a short APDU; a consistent timeout points at Ledger framing on the air (only Flex-to-Flex would work) or at the reply exceeding 271 bytes (PPSE FCIs are usually well under).
3. **Type 2.** Tap an NTAG213 if one is around: does `CARD_DETECTED` fire, and does `30 04` return anything?
4. **CE gate (decides N2).** With the own-stack CE app open, does Android NFC Tools or a Chrome `NDEFReader.scan` page see a hard-coded NDEF record? NO-GO means the OS does not route the NDEF AID to the app.
5. **Mode switch.** Reader, then `io_nfc_reader_stop` + `os_io_nfc_cmd_start_ce`, then CE again, without restarting the app.
6. **UID.** Does `info->nfcid` match the card's UID on two consecutive taps (the stale-buffer suspicion in §1.3)?

## 9. Open questions

- Does the OS or MCU allow a sideloaded, unreviewed app to power the reader? Nothing in the open source forbids it; nobody outside Ledger has shown it.
- Does the MCU do ISO-DEP activation (RATS/ATS), chaining and WTX itself? What is the maximum command length in reader mode?
- How reliably does `CARD_REMOVED` arrive, and what is the polling interval?
- Does Android route our custom AID SELECT to an HCE service when the reader is a Flex rather than a POS terminal?
- In CE, does the MCU forward the NDEF AID SELECT to the app or answer it itself?
- Does our Flex box contain a Recovery Key?
- Does anyone on the team own an NFC Android phone, a YubiKey 5 NFC, or a second Flex / Stax / Nano Gen5? Can NTAG 424 DNA arrive by Monday?
- What exactly does support article 18934878523037 say? Someone with a browser should read it.

## 10. Sources

- SDK @ `b03e7d647f9ef99b0327cef8840f35781697f069`: `io/src/os_io.c`, `io/src/os_io_seph_cmd.c`, `io/include/os_io.h`, `io_legacy/src/os_io_legacy.c`, `io_legacy/include/os_io_legacy.h`, `io_legacy/include/os_io_legacy_types.h`, `lib_nfc/src/nfc_ledger.c`, `lib_nfc/include/nfc_ndef.h`, `lib_nfc/doc/mainpage.dox`, `protocol/src/ledger_protocol.c`, `include/seproxyhal_protocol.h`, `include/os_settings.h`, `include/appflags.h`, `Makefile.standard_app`, `Makefile.defines`, `Makefile.rules`, `src/syscalls.c`, `api_levels.json`, `README.md`. https://github.com/LedgerHQ/ledger-secure-sdk
- SDK PRs: https://github.com/LedgerHQ/ledger-secure-sdk/pull/777 , /pull/835 , /pull/987 , /pull/1044 , /pull/1045 , /pull/1243 , /pull/665 , /pull/412
- https://github.com/LedgerHQ/app-security-key (Makefile @ `d6f57fb11f`, `src/nfc_io.c`, `src/u2f_processing.c`, CI workflow)
- https://github.com/LedgerHQ/speculos @ `abc6b7d936` (`speculos/mcu/seproxyhal.py`, `speculos/mcu/transport/nfc.py`, `speculos/mcu/transport/usb.py`, `speculos/mcu/apdu.py`, `src/CMakeLists.txt`, `src/bolos/os.c`, `src/bolos/io/io.c`, CHANGELOG), PR #519
- https://github.com/LedgerHQ/ledger-device-rust-sdk @ `4123d2dc85`
- https://github.com/structured-world/structured-passkeys/pull/20
- https://github.com/LedgerHQ/applet-recovery-key @ `3088fa3d73`
- https://www.ledger.com/ledger-recovery-key-white-paper , https://www.ledger.com/blog-ledger-recovery-key , https://shop.ledger.com/products/ledger-recovery-key
- https://github.com/LedgerHQ/app-ethereum @ `e5b6dbff3a`
- https://developer.android.com/develop/connectivity/nfc/hce , https://w3c-cg.github.io/web-nfc/
- https://www.nxp.com/products/NTAG424DNA , https://www.nxp.com/products/NTAG213_215_216
- https://github.com/Yubico/yubikey-manager , https://github.com/coinkite/coinkite-tap-proto , https://github.com/arx-research/libhalo
- https://eips.ethereum.org/EIPS/eip-3009
