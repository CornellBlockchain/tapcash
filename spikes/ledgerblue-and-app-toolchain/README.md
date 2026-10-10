# Spike: ledgerblue + Rust app toolchain on Windows (no device)

Question: can we sideload a custom device app onto Nano S Plus / Flex from this Windows 11 host later?
Answer: **yes, the host side is ready.** `ledgerblue` 0.1.58 and `ledgerwallet` 0.10.0 install from prebuilt wheels
(no compiler), the HID backend loads, and the Rust boilerplate's load path is `python -m ledgerblue.runScript --elfFile ... --scp`
run on the host. Building needs the `ledger-app-dev-tools` Docker image (not pulled here).
Nothing was plugged in; `sideload.ps1` is the ready-to-run script.

Date: 2026-10-10. Host: Win11, Python 3.12.10, cargo 1.98.1 (stable only), Docker Desktop (speculos image pulled).

## 1. ledgerblue / ledgerwallet in a venv  -- PASS

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install ledgerblue ledgerwallet     # full log: pip-install.log (gitignored)
```
Decisive lines (verbatim):
```
Downloading hidapi-0.15.0-cp312-cp312-win_amd64.whl (67 kB)
Downloading libusb1-3.4.0-py3-none-win_amd64.whl (141 kB)
Downloading nfcpy-1.0.4-py3-none-any.whl (186 kB)
Using cached cryptography-50.0.2-cp311-abi3-win_amd64.whl (3.8 MB)
Building wheels for collected packages: python-u2flib-host, pydes
Successfully installed bleak-3.0.2 ... hidapi-0.15.0 ... ledgerblue-0.1.58 ledgerwallet-0.10.0 libusb1-3.4.0 ... nfcpy-1.0.4 ...
```
Only `python-u2flib-host` and `pydes` were built from source, both pure Python (no compiler needed).
hidapi, libusb1, nfcpy, cryptography, pillow all resolved as prebuilt wheels. This settles the research note's
"INFERRED OK" for Windows pip install.

```
.venv/Scripts/python.exe -c "import ledgerblue, ledgerwallet, hid, usb1, nfc; print('ok')"   -> ok
.venv/Scripts/ledgerctl.exe --help                                                             -> exit 0
   Commands: delete delete-ca genuine-check info install install-ca list meminfo onboard remote-delete remote-install run send upgrade-firmware
.venv/Scripts/python.exe -m ledgerblue.runScript --help                                        -> exit 0
   options: --fileName --apdu --scp --targetId --elfFile --rootPrivateKey
.venv/Scripts/python.exe -c "import hid; print(len(hid.enumerate(0x2c97)))"                   -> 0   (HID backend loads; no Ledger plugged in)
```
ledgerblue transport switches seen in `.venv/Lib/site-packages/ledgerblue/comm.py`: `LEDGER_PROXY_ADDRESS`+`LEDGER_PROXY_PORT`
(TCP, for Speculos :9999), `LEDGER_BLE_PROXY`, `LEDGER_NFC_PROXY`, `PCSC`, `APDUGEN`, `MCUPROXY`. Default is USB HID.

## 2. cargo-ledger  -- SKIPPED on purpose (not needed on host)

```
ls ~/.cargo/bin | grep -i ledger        -> nothing
cargo search cargo-ledger                -> cargo-ledger = "1.14.0"   # Build and sideload Ledger apps
                                            ledger_device_sdk = "1.41.0"
rustup toolchain list                    -> stable-x86_64-pc-windows-msvc (active, default)   # no nightly
which arm-none-eabi-objcopy arm-none-eabi-gcc clang   -> none found
```
`cargo install cargo-ledger --locked` was not run. Reason: the boilerplate pins `nightly-2025-12-05`
(`rust-toolchain.toml`) and needs `build-std` + `arm-none-eabi-objcopy`, none of which are on this host, so
`cargo ledger build` cannot work here anyway. The Docker image bundles cargo-ledger 1.14.0 and the whole
toolchain; `cargo ledger build --load` only shells out to `ledgerblue.runScript`, which we have in the venv.
Host build is a dead end on Windows; build in Docker, load from the host.

## 3. app-boilerplate-rust  -- cloned (shallow)

```
git clone --depth 1 https://github.com/LedgerHQ/app-boilerplate-rust   -> commit 0f857a78 (2026-10-05), v1.9.1
```
`ledger-app-ai-instructions/` submodule is empty after a shallow clone (`git submodule update --init` if the
CLAUDE.md imports matter). `ledger_app.toml`: `sdk = "Rust"`, devices `nanox, nanos+, stax, flex, apex_p`.
`.cargo/config.toml`: default target is `apex_p`, so always pass the device.

### Exact build commands (Windows PowerShell, from the app directory)
```
docker pull ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest       # NOT run here (multi-GB)

# one-shot builds (artifacts land in host target/)
docker run --rm -v "$(Get-Location):/app" ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest cargo ledger build nanosplus
docker run --rm -v "$(Get-Location):/app" ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest cargo ledger build flex

# interactive shell (extra flags only matter for Speculos; needs VcXsrv with access control disabled)
docker run --rm -ti --privileged -v "$(Get-Location):/app" -e DISPLAY='host.docker.internal:0' --publish 5001:5001 --publish 9999:9999 ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest
```
Outputs: `target/<device>/release/app-boilerplate-rust` (ELF), `.apdu` (install script), `.hex`, `.sha256`.
Speculos inside the container: `speculos --apdu-port 9999 --api-port 5001 --display headless target/nanosplus/release/app-boilerplate-rust`
(Nano UI on localhost:5001; Flex UI goes to the X server). Ragger tests: `pip install -r tests/standalone/requirements.txt`,
`pytest tests/standalone/ --tb=short -v --device nanosp` (Speculos says `nanosp`, manifest says `nanos+`).

### Exact load command (host, outside Docker, device unlocked on dashboard, Ledger Live closed)
```
.venv/Scripts/python.exe -m ledgerblue.runScript --elfFile app-boilerplate-rust/target/nanosplus/release/app-boilerplate-rust --fileName app-boilerplate-rust/target/nanosplus/release/app-boilerplate-rust.apdu --apdu --scp
.venv/Scripts/python.exe -m ledgerblue.runScript --elfFile app-boilerplate-rust/target/flex/release/app-boilerplate-rust      --fileName app-boilerplate-rust/target/flex/release/app-boilerplate-rust.apdu      --apdu --scp
```
`--elfFile` reads the target ID from the ELF `ledger.target_id` section (Nano S+ `0x33100004`, Flex `0x33300004`)
and overrides `--targetId`, whose default is Nano S and is never auto-detected. `cargo ledger build <device> --load`
does the same thing but only works where cargo-ledger can see USB, i.e. not from Docker on Windows.
Wrapped in `sideload.ps1` (`-Build`, `-Load`, `-List`). Uninstall: `ledgerctl delete "Rust Boilerplate"` or
`python -m ledgerblue.deleteApp --appName "Rust Boilerplate" --targetId 0x33100004`.

## 4. File pointers for an "Attestation Signer" fork

| What | Where |
|---|---|
| App name, curve, BIP32 path, flags, per-device icons | `Cargo.toml` `[package.metadata.ledger]`: `name = "Rust Boilerplate"`, `curve = ["secp256k1"]`, `path = ["44'/1'"]`, `nanosplus = { icon = "icons/crab_14x14.gif" }`, `flex = { icon = "icons/crab_40x40.gif" }` |
| NBGL on Nano S+ | `Cargo.toml` `[features] default = ["ledger_device_sdk/nano_nbgl"]`; Flex is NBGL-only. The same `NbglReview` code runs on both. |
| CLA + APDU parsing | `src/main.rs:200` `comm.set_expected_cla(0xe0)`; `src/main.rs:99-137` `enum Instruction` + `impl TryFrom<ApduHeader>`: INS 3 GetVersion, 4 GetAppName, 5 GetPubkey (P1=1 shows address), 6 SignTx (P1 chunk 0..3, P2 0x80 more / 0x00 last). Add a new INS here. |
| Dispatch | `src/main.rs:240-255` `handle_apdu()` match arms -> handler fns. Status words `src/main.rs:64-83` (`Deny 0x6985`, `InsNotSupported 0x6D00`, ...). |
| Sign handler | `src/handlers/sign_tx.rs:102-175` `handler_sign_tx`: chunk 0 = BIP32 path (`ctx.path = data.try_into()?`), later chunks append to `raw_tx` (`MAX_TRANSACTION_LEN = 510`), last chunk JSON-parses `Tx { nonce, coin, value, to: [u8;20], memo }` at line 138, calls `ui_display_tx(comm, &tx)?` at line 164, then `compute_signature_and_append` lines 177-196: `Keccak256` over `raw_tx`, `Secp256k1::derive_from_path(path).deterministic_sign(hash)`, response = `[siglen, sig, parity]`. For an attestation: replace `Tx` with hash + context fields, keep the chunk protocol. |
| Review text (NBGL) | `src/app_ui/sign.rs:35-82` `ui_display_tx`: `Field { name, value }` array (Amount / Destination / Memo), `NbglReview::new().titles("Review transaction\nto send CRAB", "", "Sign transaction\nto send CRAB").glyph(&FERRIS)`, `review.show(comm, &fields)` returns `bool` approve. Glyph per device at lines 58-63 (`icons/crab_14x14.gif` for nanosplus, `glyphs/crab_64x64.gif` for flex). |
| Post-review status screen | `src/main.rs:140-168` `NbglReviewStatus` (`StatusType::Transaction`), then `home.show_and_return()` |
| Home screen / settings | `src/app_ui/menu.rs:24-50` `NbglHomeAndSettings::new().glyph().settings(.., [["Display Memo", "..."]]).infos(title, version, authors)`; title string at lines 37-43 |
| Pubkey handler | `src/handlers/get_public_key.rs`, UI in `src/app_ui/address.rs` |
| Host test client (INS constants to mirror) | `tests/application_client/boilerplate_command_sender.py:10-51` (`CLA = 0xE0`, `InsType`, SW codes) |
| End-user installer | `tools/sideload/` (`ledger_installer.py`, `make_bundle.py`; PyInstaller .exe embedding the .apdu, replayed through ledgerblue SCP) |
| Target ID helper | `tools/get_target_id.py <elf>` (needs `pyelftools`, already in the venv) |

## What passed / failed
- PASS: venv + `pip install ledgerblue ledgerwallet` on Win11/Py3.12 with no compiler; imports; `ledgerctl --help`; `runScript --help`; hidapi backend loads.
- PASS: shallow clone + manifests read; exact Docker build and host load commands recorded; `sideload.ps1` parses.
- SKIPPED: `cargo install cargo-ledger` (useless on host without nightly + arm toolchain; lives in the Docker image); `docker pull ledger-app-dev-tools` (multi-GB, per brief).
- NOT TESTED (needs device): actual USB HID open, SCP handshake, "allow unsafe manager" flow, app install, `ledgerctl list`.

## Next steps when a device is plugged in
1. Close Ledger Live. Unlock the device, stay on the dashboard.
2. `.\sideload.ps1 -List` -> expect installed apps via `ledgerctl list`. If `hid` cannot open the device, that is the Windows HID blocker to record (research-note fallback: WSL2 + usbipd-win).
3. `docker pull ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest`, then `.\sideload.ps1 -Device nanosplus -Build` (and `-Device flex -Build`).
4. `.\sideload.ps1 -Device nanosplus -Load` -> approve "unsafe manager" and the not-genuine warning on the device; compare the printed identifier.
5. Open the app and send `e0030000` (GET_VERSION) with `ledgerctl send -`; expect `01 09 01` + `9000`. `0x511F` means SDK/OS mismatch -> rebuild against the device's OS.
6. Only then fork into the Attestation Signer using the file pointers above.
