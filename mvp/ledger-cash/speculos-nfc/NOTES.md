# Stage A: Speculos NFC reader emulation (emulated Ledger-to-Ledger tap)

Status 2026-10-10: PASS. A reader-mode app in one Speculos instance sent `E003000000` through `relay.py` to a
card-emulation app in a second instance and got the card's `0203029000` back in its `io_nfc_reader_send` callback.
Both tap orders pass (reader on then card arrives; card already in the field when the reader powers on).

> Update (Fix stage, 2026-10-10): `run.sh` now pins `ghcr.io/ledgerhq/speculos@sha256:028d1e368244631578537e7ca50b6f13ca2932b5f3fd220627289b559c07a886`
> (the build `seproxyhal.py` was copied from; `seproxyhal.patch` regenerated against it). The patch also gives a
> `--transport NFC` instance a USB/HID host link: `self.usb` is a second HID transport, `USB_CONFIG` and
> `USB_EP_PREPARE` go to it, and `to_app()` sends packets prefixed `USB!` (REST `/apdu` data `55534221...`) over it.
> On a HID instance `self.usb` is `self.transport`, so the reader side is unchanged. Needed because ledger-cash now
> refuses host commands over NFC. Verified by `../demo.py` (ALL PASS). `check_tap.py` was **not** re-run after this
> change (reader instance unchanged; the card path is covered by demo.py).

> Update (attested IOUs, 2026-10-10): a second, independent Speculos patch lives in `../attest/speculos_codehash.py`:
> it gives each instance its ELF's real code hash for the endorsement syscalls. It does not touch `seproxyhal.py`;
> `../attest_demo.py` and `../app/test_nano.py` use both. See ../README.md "Attested IOUs".

## Files

| File | What |
|------|------|
| `seproxyhal.py` | Patched copy of `/speculos/speculos/mcu/seproxyhal.py` from `ghcr.io/ledgerhq/speculos:latest` (speculos 0.27.x; that build is `@sha256:028d1e368244631578537e7ca50b6f13ca2932b5f3fd220627289b559c07a886`, now pinned). Bind-mounted over the original. No other Speculos file is patched (`transport/nfc.py` is reused as-is). |
| `seproxyhal.patch` | `diff -u` of the original against the patched copy. |
| `run.sh` | Starts both instances in ONE container (`lc-a-speculos`, `--memory 1g`). |
| `relay.py` | The tap. Python 3.12 stdlib. Importable (`tap()`, `card_exchange()`, `send_frame()`, `recv_exact()`). |
| `check_tap.py` | The assert-based check (both tap orders). |
| `probe.patch` | Boilerplate -> reader probe: Makefile flags, INS 0x50/0x51, `src/nfc_probe.c`. |
| `card.patch` | Boilerplate -> card: Makefile flags only. |

Both app patches apply to `LedgerHQ/app-boilerplate` at `b2e8c3f` (the clone at `C:/lgw/app-boilerplate`).

## What the patch does

Stock Speculos dies on reader mode (`unknown tag: 0x5d` -> `sys.exit(0)`) and has no way to inject `NFC_EVENT`.
The patch plays the MCU's part:

1. `SephTag` gains `ITC_EVENT 0x1A`, `NFC_EVENT 0x1E`, `ITC_CMD 0x5D` (also makes `RAW!` injection of 0x1E legal).
2. `ITC_CMD` is echoed back as `ITC_EVENT` with the same payload. The app's own IO stack (`os_io.c process_itc_event`)
   then calls `NFC_LEDGER_start(READER)` for 0x12, `NFC_LEDGER_stop()` for 0x10, `NFC_LEDGER_start(CE)` for 0x11.
3. `NFC_POWER 0x34` is logged and tracked: `nfc_power` 0 off, 1 card emulation, 2 reader.
4. While `nfc_power == 2`, `NFC_RAPDU 0x4A` chunks are reader commands: reassembled with a second `NFC` transport
   object and sent to the NFC reader port. Otherwise 0x4A goes to the normal transport (card-emulation replies).
5. NFC reader port (TCP, only when env `SPECULOS_NFC_READER_PORT` is set), one client at a time, frames both ways
   `len(4, big-endian) + type(1) + body`:
   - client -> speculos `E` + `01 01 <uid 4|7 bytes>`: card enters field (NFC-A; `01 02 <uid>` for NFC-B)
   - client -> speculos `E` + `02`: card leaves field
   - client -> speculos `R` + `<response data + SW>`: reply to the last command (sent as 0x1C chunks, which the app
     reassembles as packet type 0x41 -> `os_io_nfc_reader_rx` -> response callback). Dropped unless reader is on.
   - speculos -> client `C` + `<command APDU>`: what the app passed to `io_nfc_reader_send`
   - client disconnect = card leaves field.
6. Card presence is latched like a real field: `CARD_DETECTED` reaches the app when the card arrives while the reader
   is powered, or when the reader powers on (`NFC_POWER 02`) with the card already present. `CARD_REMOVED` only
   reaches the app while the reader is powered.

The reader instance keeps the default USB/HID transport, so its APDU port and REST `/apdu` stay usable during a tap
(the SDK fixed reader + USB coexistence in PR #987; that fix is verified to exist in source, not tested on hardware). Reader commands never reach `apdu_callbacks`, so a
pending REST `/apdu` on the reader cannot swallow one. The card instance runs `--transport NFC`, so its stock APDU port
is the RF side of the card.

Decision vs. the research sketch (`RAW!` over the APDU port with `--transport NFC` on the reader): not used, because in
reader mode every byte into that port becomes a reader response, so the host could not talk to the payer app during a
tap, and a REST `/apdu` would take a reader command as its reply.

## Build (Git Bash)

```bash
# clean copies, no tests/ (long paths), then git init: Makefile.rules needs `git rev-parse --show-toplevel`
for d in lc-a-probe lc-a-card; do
  mkdir -p /c/lgw/$d
  git -C /c/lgw/app-boilerplate archive HEAD . ':(exclude)tests' ':(exclude)fuzzing' ':(exclude)unit-tests' | tar -x -C /c/lgw/$d
  (cd /c/lgw/$d && git init -q .)
done
# (tar warns about the .github/instructions symlink; harmless)
(cd /c/lgw/lc-a-probe && git apply "<repo>/mvp/ledger-cash/speculos-nfc/probe.patch")
(cd /c/lgw/lc-a-card  && git apply "<repo>/mvp/ledger-cash/speculos-nfc/card.patch")
for d in lc-a-probe lc-a-card; do
  MSYS_NO_PATHCONV=1 docker run --rm --name lc-a-build --memory 1g \
    -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
    -v "C:/lgw/$d:/app" ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools@sha256:8d3da9179dd1b241883c769c521ee9403352b60091c80405b5bef5801a003ba2 \
    make -C /app TARGET=flex BOLOS_SDK=/opt/flex-secure-sdk -j4
done
```

Both builds: exit 0, `build/flex/bin/app.elf`.

Build gotchas hit:
- `[ERROR] You should be inside a git repo (you can use 'git init')` on a plain export; the `safe.directory` env is
  needed because the bind-mounted repo has a different owner inside the container.
- `ld.lld: error: .data section must be empty`: a Ledger app cannot have initialised non-const globals
  (`static size_t x = 1;`). Zero-initialise and set at runtime.

Flags:
- reader (probe): `ENABLE_NFC=1 ENABLE_NFC_READER=1 DISABLE_OS_IO_STACK_USE=1` (from `mvp/nfc-probe`).
- card: `ENABLE_NFC=1 DISABLE_OS_IO_STACK_USE=1`. The own-stack flag deviates from "unmodified boilerplate +
  ENABLE_NFC": with the default OS stack Speculos serves IO from its own SDK copy built without `HAVE_NFC`, so 0x1C
  never becomes an APDU (research/nfc-reader-mode.md section 5). Source is unmodified.

Probe app (reader): INS `0x50` = clear result + `io_nfc_reader_start`; on `CARD_DETECTED` it sends `E003000000` with a
2000 ms timeout; on `CARD_REMOVED` it calls `io_nfc_reader_stop` (ITC 0x10 -> `NFC_POWER 00`). INS `0x51` returns
`[state][response...] 9000`, state 0 none, 1 response, 2 error (card removed mid-command), 3 timeout.

## Run

```bash
cd mvp/ledger-cash/speculos-nfc
sh run.sh                      # PORT_BASE=15000 NAME=lc-a-speculos by default; args: [reader_bin_dir] [card_bin_dir]
python check_tap.py            # same PORT_BASE env
python relay.py --seconds 3    # manual tap; default until Ctrl-C
docker rm -f lc-a-speculos
```

Ports (host 127.0.0.1, same numbers inside the container), base B = 15000:

| Port | Instance | What |
|------|----------|------|
| B+0  = 15000 | reader | REST API (`/apdu`, `/events`, `/finger`, `/screenshot`) |
| B+1  = 15001 | reader | APDU TCP port, USB/HID transport |
| B+2  = 15002 | reader | NFC reader port (patched) |
| B+10 = 15010 | card | REST API |
| B+11 = 15011 | card | APDU TCP port, `--transport NFC` = card emulation |

Port 5000 was taken by another stage's container (`lc-b-payer`), hence the base.

## Verbatim output (2026-10-10)

`python check_tap.py`:
```
card direct GET_VERSION: 0203029000
tap: card 04a1b2c3 in field
  reader > card e003000000
  reader < card 0203029000
tap: card removed after 1 APDU(s)
probe INS 0x51 (card_first=False): 0102030290009000
tap: card 04a1b2c3 in field
  reader > card e003000000
  reader < card 0203029000
tap: card removed after 1 APDU(s)
probe INS 0x51 (card_first=True): 0102030290009000
PASS: reader app -> relay -> card app -> reader app round trip, both tap orders
```

Reader instance log (`docker logs lc-a-speculos | grep seproxyhal`), annotations added:
```
seproxyhal: NFC reader port 15002
seproxyhal: NFC_POWER 01                      <- os_io_start: card emulation by default
seproxyhal: ITC_CMD 12                        <- io_nfc_reader_start
seproxyhal: NFC_POWER 02                      <- NFC_LEDGER_start(READER) after the ITC echo
seproxyhal: nfc-reader > 45010104a1b2c3       <- E 01 01 04a1b2c3 (CARD_DETECTED)
seproxyhal: nfc-reader < e003000000           <- io_nfc_reader_send
seproxyhal: nfc-reader > 520203029000         <- R + card reply
seproxyhal: nfc-reader > 4502                 <- E 02 (CARD_REMOVED)
seproxyhal: ITC_CMD 10                        <- io_nfc_reader_stop
seproxyhal: NFC_POWER 00
seproxyhal: nfc-reader > 45010104a1b2c3       <- card first (latched, reader off)
seproxyhal: ITC_CMD 12
seproxyhal: NFC_POWER 02                      <- latched CARD_DETECTED delivered here
seproxyhal: nfc-reader < e003000000
seproxyhal: nfc-reader > 520203029000
seproxyhal: nfc-reader > 4502
seproxyhal: ITC_CMD 10
seproxyhal: NFC_POWER 00
```

Card instance log (`docker exec lc-a-speculos cat /tmp/card.log`): `seproxyhal: NFC_POWER 01`, `apdu: > e003000000`,
`apdu: < 0203029000`.

## Limits of the emulation (not hardware truth)

- On-air framing is not emulated: the relay passes raw APDU bytes. What the real MCU puts on ISO-DEP is unknown.
- Timing: response timeouts tick at Speculos' 100 ms ticker; real RF latency is not modelled.
- Response size: the app drops replies over 271 bytes (`apdu_rx_max_size`, SEPH buffer 272) and times out; that
  limit is in the app's SDK code, so it applies here too. Not exercised by this check.
- UID passed to the callback: the SDK copies it from `G_io_seproxyhal_spi_buffer + 5`, which may be stale with the
  own IO stack (research note). Not checked here; do not rely on the UID.
- One NFC reader client at a time.
- The settings gate is open in Speculos (`os_setting_get(FEATURES)` = 0xff). On hardware NFC must be enabled.
