# nfc-probe — compile/link gate for Flex NFC reader mode

Smallest possible proof that a standard C Ledger app can reach the SDK's app-level NFC reader API. Not a product.

- Base: `LedgerHQ/app-boilerplate` (C) at `b2e8c3f`, SDK `/opt/flex-secure-sdk` in `ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest` (`6709cd2b`, 2026-10-01, API_LEVEL 27).
- `boilerplate.patch`: Makefile flags + a test INS `0x50` in `src/apdu/dispatcher.c` that calls `nfc_probe_start()`.
- `nfc_probe.c`: `io_nfc_reader_start(on_evt)`; on `CARD_DETECTED` sends `SELECT` of the NFC Forum NDEF application (`D2760000850101`) with a 2 s timeout and logs the reply.

## Required flags (all three)

```make
ENABLE_NFC = 1
ENABLE_NFC_READER = 1
DISABLE_OS_IO_STACK_USE = 1
```

Without `DISABLE_OS_IO_STACK_USE = 1` the app still compiles and links `io_nfc_reader_*`, but the reader event routing in `io/src/os_io.c` (`os_io_nfc_reader_rx`, `os_io_nfc_evt`, `ITC_IO_NFC_START_READER`) is compiled out (`#ifndef USE_OS_IO_STACK`), so callbacks never fire. `app-security-key` uses the same setting. See `research/nfc-reader-mode.md`.

## Build (Windows, Git Bash)

The repo needs `core.longpaths` (test snapshot paths exceed MAX_PATH) and a short checkout path:

```bash
git -c core.longpaths=true clone --depth 1 https://github.com/LedgerHQ/app-boilerplate.git C:/lgw/app-boilerplate
cd C:/lgw/app-boilerplate && git apply <repo>/mvp/nfc-probe/boilerplate.patch && cp <repo>/mvp/nfc-probe/nfc_probe.c src/
MSYS_NO_PATHCONV=1 docker run --rm -v "C:/lgw/app-boilerplate:/app" ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest \
  make -C /app TARGET=flex BOLOS_SDK=/opt/flex-secure-sdk -j4
```

Result 2026-10-10: exit 0; `debug/app.map` contains `io_nfc_reader_start`, `io_nfc_reader_send`, `os_io_nfc_reader_rx`, `os_io_nfc_evt`.

## Hardware gate (first thing to run on the real Flex)

1. Flex: Settings → enable NFC. Quit Ledger Wallet.
2. Sideload: `python -m ledgerblue.runScript --elfFile build/flex/bin/app.elf --fileName build/flex/bin/app.apdu --apdu --scp` (see `spikes/ledgerblue-and-app-toolchain/sideload.ps1`).
3. Open the app, send `E050000000` over USB, hold a contactless bank card or an Android phone to the back of the Flex.
4. Pass = a response callback fires (needs a debug build with `DEBUG=1` to see PRINTF, or swap the PRINTF for an on-screen NBGL status). Fail modes: OS refuses to power the reader for a sideloaded app; NFC disabled in settings (`NFC_LEDGER_start` silently refuses while `io_nfc_reader_start` still returns true).

Speculos cannot run reader mode as shipped (ignores `NFC_POWER` 0x34, never emits `NFC_EVENT` 0x1E, exits on `ITC_CMD` 0x5D). A small `seproxyhal.py` patch is sketched in `research/nfc-reader-mode.md`.
