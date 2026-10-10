# Custom Ledger device apps: SDKs, Speculos, sideloading, NFC

> **Correction (2026-10-10, source audit).** API_LEVEL 27 = flex_1.7.0 and nanos+_1.7.0, not nanos+_1.4.1 (API 24) (l.32, l.176); the §7 takeaway misses BOLOS endorsement, which personal_sign cannot replace; §1.3 omits Rust `debug_over_usb`; only `-u/--usb` is deprecated in Speculos (l.193); Developer mode is required for OpenPGP/Passwords/testnet apps and Bitcoin 2.5.x has miniscript/MuSig2/clear-text policies (l.184-186, l.249-250). See `source-audit.md` §1, §2 (M01, M06, M12) and §5.

Research note for the N3XT hackathon (deadline 2026-10-13 23:59 CEST). Written 2026-10-10 from web sources only; nothing was installed or plugged in. Hardware on hand: Nano S Plus (USB only), Flex (USB + BLE + NFC). Host: Windows 11.

Tags: **VERIFIED** = read in a primary source (Ledger docs, LedgerHQ GitHub source, PyPI). **INFERRED** = my reading between the lines; treat as a hypothesis to test on Day 1.

---

## 0. Bottom line (read this if nothing else)

1. **You can build and sideload an unsigned custom app onto both the Nano S Plus and the Flex.** Only the Nano X blocks sideloading. VERIFIED: ledger-app-builder README ("Only Nano S, Nano S+, Stax, and Flex support sideloading"), VS Code quickstart ("sideloading is not available on Nano X"), app-boilerplate-rust `tools/sideload/README.md` (ships Flex/Stax/Nano S+/Apex P installers; "Nano X does not allow installing apps outside Ledger Live").
2. **No custom CA, no "developer mode", no Ledger approval is needed to sideload.** You run `ledgerblue.runScript --scp` from the host; the device asks you to allow an "unsafe manager", warns the app is not genuine, and you confirm. A custom CA is optional and only saves retyping the PIN; it also makes the device fail Ledger's Genuine Check until removed. VERIFIED (developers.ledger.com/docs/device-app/deliver; sideload README).
3. **Rust is the mandated language for new apps; C still builds fine and has the only official NFC library.** VERIFIED (getting-started page: "Rust is mandatory for all new device app projects"; `lib_nfc` is C; Rust `build.rs` has no NFC).
4. **NFC on Flex is real and reachable from a C app with one Makefile line (`ENABLE_NFC = 1`)**, card-emulation mode by default (phone taps the Flex), plus an undocumented reader mode (`ENABLE_NFC_READER = 1`). The Nano S Plus has no NFC. VERIFIED (`Makefile.standard_app`, `lib_nfc/`, `io/src/os_io.c`). **Ledger-to-Ledger NFC with our two devices is impossible** (Nano S+ has no radio); it would need two Flex/Stax units, and even then one must be in reader mode, which nothing public demonstrates. INFERRED.
5. **Speculos emulates Flex and Nano S+ (and even an NFC transport), but not BLE**, and needs Linux/macOS/WSL2/Docker. On Windows the sane route is Docker Desktop + the `ledger-app-dev-tools` image + VcXsrv, driven by Ledger's VS Code extension. VERIFIED.
6. **Firmware/API_LEVEL coupling is the #1 "Day 1 lost to install issues" risk.** The Docker SDK is `v27.1.2` (API_LEVEL 27). The app only installs if the device OS exposes that API level (status word `0x511F` = OS too old). Update both devices in Ledger Live before anything else. VERIFIED (lite Dockerfile, structured-passkeys README) / INFERRED (that current Flex/Nano S+ OS == API_LEVEL 27; check with `ledger-binary` + device).
7. **For "sign this hash / attest this message" you don't need a custom app at all**: the Ethereum app signs arbitrary EIP-191 personal messages, the OpenPGP app signs arbitrary data, the Security Key app attests FIDO challenges (over NFC on Flex). A custom app is only justified if you need a bespoke APDU/UI or NFC payloads. VERIFIED.

Realistic 3-day plan is in section 9.

---

## 1. Languages, SDKs, policy

### 1.1 Policy
- "Rust is mandatory for all new device app projects." C "remains supported as a reference for teams that maintain existing C apps." VERIFIED: https://developers.ledger.com/docs/device-app/getting-started
- Every published app needs a paid third-party security audit (Coinspect / Quarkslab) before appearing in My Ledger. Irrelevant for a hackathon sideload, relevant for the "usefulness for Ledger" pitch. VERIFIED (same page).
- Ledger OS (BOLOS) is in C; apps are isolated and get key material only for derivation paths/curves declared at install (`PATH_APP_LOAD_PARAMS` / `CURVE_APP_LOAD_PARAMS` in C, `[package.metadata.ledger] path/curve` in Rust). VERIFIED: https://developers.ledger.com/docs/device-app/explanation/ledger-os/introduction , boilerplate Makefile/Cargo.toml.

### 1.2 C SDK: `LedgerHQ/ledger-secure-sdk`
- "This directory contains the SDK for Nano X, Nano S+, Stax, Apex+ and Flex applications development." Targets: `nanox`, `nanos2` (= Nano S+), `stax`, `flex`, `apex_p`. VERIFIED: https://github.com/LedgerHQ/ledger-secure-sdk
- Versioning: `master` has `API_LEVEL 0` (reserved); release branches `API_LEVEL_1 … API_LEVEL_27` (highest today: 27), tags `v<N>.<minor>.<patch>` (latest `v27.1.2`); per-OS tags `<device>_<os_version>` e.g. `flex_1.7.0`, `nanos+_1.4.1`, `stax_1.11.0`, `nanox_2.8.0`, `nanos_2.1.0`. VERIFIED via GitHub API tags/branches listing.
- `API_LEVEL_27/Makefile.defines` -> `API_LEVEL := 27`. VERIFIED.
- Build: `make BOLOS_SDK=<path> TARGET=<target>`; inside Docker just `BOLOS_SDK=$FLEX_SDK make`. VERIFIED.
- Directory layout includes `lib_nbgl`, `lib_bagl`, `lib_cxng` (crypto), `lib_stusb` (USB), `lib_blewbxx` (BLE), `lib_nfc`, `lib_u2f`, `lib_standard_app`, `io/`. VERIFIED (repo tree).
- Flex/Stax/Apex force NBGL (`USE_NBGL = 1`); Nano X/S+ default to BAGL with optional NBGL (`ENABLE_NBGL_FOR_NANO_DEVICES`). VERIFIED (`Makefile.defines`, `Makefile.standard_app`).

### 1.3 Rust SDK: `LedgerHQ/ledger-device-rust-sdk`
- Crates: `ledger_device_sdk` 1.41.0 (high-level), `ledger_secure_sdk_sys` 1.17.0 (FFI to the C SDK), `include_gif`, `testmacro`. Devices: Nano X, Nano S Plus, Stax, Flex, Apex P. VERIFIED: https://github.com/LedgerHQ/ledger-device-rust-sdk , `ledger_device_sdk/Cargo.toml`.
- Toolchain: nightly Rust (Docker pins `nightly-2025-12-05`), `arm-none-eabi-gcc`, clang 21, `cargo-ledger` 1.14.0. VERIFIED (`full/Dockerfile`, `lite/Dockerfile`).
- Features of note: `io_new` (new IO module; the boilerplate requires it), `nano_nbgl` (NBGL UI on Nano), `debug`/`log_*`, `heap` (default; "Heap is 8192 bytes by default. Override via `HEAP_SIZE` env var; allowed values: 2048, 4096, 8192, 16384, 24576"), `app_storage*`, `mldsa`/`mlkem` (post-quantum). **No `nfc` or `ble` feature.** VERIFIED (Cargo.toml; RUST.instructions.md).
- The sys crate's `build.rs` compiles `lib_blewbxx` when the C SDK defines `HAVE_BLE`, and has zero references to NFC/`lib_nfc`. VERIFIED.
- Packet types visible to Rust (`seph::PacketTypes`): RawApdu, UsbHidApdu, UsbWebusbApdu, BleApdu. **No NFC packet type.** VERIFIED (`seph.rs`, `io_legacy.rs`).
- A third-party fork `structured-world/ledger-device-rust-sdk` adds `nfc` and `app_io_stack` features (`nfc = ["ledger_secure_sdk_sys/nfc"]`), used by the Rust FIDO2 app `structured-world/structured-passkeys` (CTAP over NFC on Stax/Flex/Nano Gen5). Only hardware claim: an Android NFC probe "passes on a Nano Gen5". Status "implementation in progress". VERIFIED that the fork/feature exists; **INFERRED that it is unstable and untested on Flex**.
- Entry point is still C: `_start` calls `c_main()` ("Main is in C until the try_context can be set properly from Rust"). `cargo build` on the host produces nothing runnable ("there is no host target"). VERIFIED (`lib.rs`, RUST.instructions.md).
- Rust SDK docs on docs.rs do not build ("docs.rs failed to build ledger_device_sdk-1.41.0"); read the source. VERIFIED.

### 1.4 AI coding rules
`LedgerHQ/ledger-app-ai-instructions` is a submodule in both boilerplates; `CLAUDE.md` imports `instructions/{EMBEDDED,C,RUST,TEST,REVIEW}.instructions.md`. Rules worth knowing: no `unwrap()`/`expect()`; justify every `unsafe`; `cargo ledger build <TARGET>` only; `cargo fmt --check` + `cargo clippy` clean; debug build `cargo ledger build nanosplus -- --features debug`; "Run `docker images | grep ledger` before any `docker run`". VERIFIED: https://github.com/LedgerHQ/ledger-app-ai-instructions , raw `instructions/RUST.instructions.md`.

---

## 2. Boilerplates

### 2.1 `LedgerHQ/app-boilerplate-rust` (recommended by Ledger)
- Version 1.9.1; devices `nanox`, `nanos+`, `stax`, `flex`, `apex_p`. **`.cargo/config.toml` defaults to `apex_p`: always pass the device.** VERIFIED: https://github.com/LedgerHQ/app-boilerplate-rust
- `Cargo.toml`: `ledger_device_sdk = {version = "*", features = ["io_new"]}`, `default = ["ledger_device_sdk/nano_nbgl"]`, plus `serde`, `serde-json-core`, `hex`, `numtoa`, `arrayvec`.
  ```toml
  [package.metadata.ledger]
  curve = ["secp256k1"]
  path  = ["44'/1'"]
  flags = "0"
  name  = "Rust Boilerplate"
  nanosplus = { icon = "icons/crab_14x14.gif" }
  nanox     = { icon = "icons/crab_14x14.gif" }
  stax      = { icon = "icons/crab_32x32.gif" }
  flex      = { icon = "icons/crab_40x40.gif" }
  apex_p    = { icon = "icons/crab_32x32.png" }
  ```
  VERIFIED. (Icon sizes: Nano 14x14, Stax 32x32, Flex 40x40.)
- `ledger_app.toml`:
  ```toml
  [app]
  build_directory = "./"
  sdk = "Rust"
  devices = ["nanox", "nanos+", "stax", "flex", "apex_p"]
  [pytest.standalone]
  directory = "./tests/standalone/"
  ```
  VERIFIED.
- APDU surface (`src/main.rs`): INS 3 GetVersion, 4 GetAppName, 5 GetPubkey{display: p1}, 6 SignTx{chunk: p1, more: p2}. Main loop:
  ```rust
  loop {
      let command = comm.next_command();
      let decoded = command.decode::<Instruction>();
      let Ok(ins) = decoded else { let _ = comm.send(&[], decoded.unwrap_err()); continue; };
      let _status = match handle_apdu(command, &ins, &mut tx_ctx) { ... };
      show_status_and_home_if_needed(comm, &ins, &mut tx_ctx, &_status);
  }
  ```
  VERIFIED.
- Signing (`src/handlers/sign_tx.rs`): chunk 0 = BIP32 path; later chunks append to `raw_tx` (max 510 bytes); when `more == false` it JSON-parses a `Tx`, shows an NBGL review (`ui_display_tx`), then:
  ```rust
  let mut keccak256 = Keccak256::new();
  let _ = keccak256.hash(&ctx.raw_tx, &mut message_hash);
  let (sig, siglen, parity) = Secp256k1::derive_from_path(ctx.path.as_ref())
      .deterministic_sign(&message_hash).map_err(|_| AppSW::TxSignFail)?;
  // response: [siglen][sig...][parity]
  ```
  VERIFIED. **This is already a "sign arbitrary bytes under a BIP32 path" app**; delete the JSON parsing and you have "sign this hash".
- Tests: `pip install -r tests/standalone/requirements.txt`; `pytest tests/standalone/ --tb=short -v --device {nanosp | nanox | stax | flex | apex_p}` (note `nanosp` for Speculos vs `nanos+` in the manifest). VERIFIED.
- Standalone sideload installers (`tools/sideload/`): PyInstaller one-file executables (Windows `.exe`, macOS, Linux) embedding the `.apdu` scripts for Nano S+/Stax/Flex/Apex P and replaying them "through the ledgerblue secure channel"; not code-signed (SmartScreen warning). Device flow: close Ledger Live, unlock on dashboard, allow the manager, "the device warns that it is not genuine, which is expected for an app installed outside Ledger Live", confirm, compare the printed identifier. "An installer only works with the device OS versions its SDK targets." Uninstall via `--uninstall` or Ledger Live. VERIFIED: https://github.com/LedgerHQ/app-boilerplate-rust/blob/main/tools/sideload/README.md . **This is the demo-day distribution story if judges want to install our app.**

### 2.2 `LedgerHQ/app-boilerplate` (C, "kept as reference")
- README: "For any new application, use the Rust boilerplate." Targets via `BOLOS_SDK=$NANOX_SDK|$NANOSP_SDK|$STAX_SDK|$FLEX_SDK|$APEX_SDK`; default Nano S+. VERIFIED: https://github.com/LedgerHQ/app-boilerplate
- Makefile knobs (VERIFIED, raw `Makefile`):
  ```make
  APPNAME = "Boilerplate"
  CURVE_APP_LOAD_PARAMS = secp256k1
  PATH_APP_LOAD_PARAMS = "44'/1'"
  ICON_NANOX = icons/app_boilerplate_14px.gif   # etc per device
  ENABLE_BLUETOOTH = 1
  #ENABLE_NFC = 1          # <-- the one line that turns NFC on (Stax/Flex/Apex P)
  ENABLE_NBGL_QRCODE = 1
  #DEBUG = 1               # PRINTF for Speculos
  include $(BOLOS_SDK)/Makefile.standard_app
  ```
- `app_main.c` loop: `io_init(); for(;;){ input_len = io_recv_command(); apdu_parser(&cmd, G_io_apdu_buffer, input_len); apdu_dispatcher(&cmd); }`. VERIFIED.
- Build/load: `make DEBUG=1`; Linux `make load`; macOS/Windows: `python3 -m ledgerblue.runScript --scp --fileName bin/app.apdu --elfFile bin/app.elf`. VERIFIED.
- Docs on the APDU envelope (`doc/APDU.md`): Lc always 1 byte, no Le, max 255 data bytes in, 258 out, SW 0x9000 success. VERIFIED.

---

## 3. Toolchain on Windows: Docker image + VS Code extension

### 3.1 Images (`LedgerHQ/ledger-app-builder`)  VERIFIED
| Image | Contents |
|---|---|
| `ghcr.io/ledgerhq/ledger-app-builder/ledger-app-builder-lite:latest` | debian-trixie-slim, C SDKs for all devices (worktrees at `v27.1.2`; Nano S at `lns-2.1.0-v24.0`), `gcc-arm-none-eabi`, clang 21, `ledgerblue==0.1.58`, `ledgered` |
| `.../ledger-app-builder:latest` | + Rust `nightly-2025-12-05`, `cargo-ledger` 1.14.0, custom targets |
| `.../ledger-app-dev-tools:latest` | + Speculos + Ragger (**use this one**) |

Env vars inside: `$NANOSP_SDK`, `$FLEX_SDK`, `$STAX_SDK`, `$NANOX_SDK`, `$APEX_P_SDK`, `$NANOS_SDK`.

### 3.2 Windows invocation (from the Rust boilerplate README, VERIFIED)
```powershell
docker pull ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest
docker run --rm -ti --privileged -v "$(Get-Location):/app" -e DISPLAY='host.docker.internal:0' `
  --publish 5001:5001 --publish 9999:9999 `
  ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest
# inside:
cargo ledger build flex
cargo ledger build nanosplus
speculos --apdu-port 9999 --api-port 5001 target/flex/release/app-boilerplate-rust        # Flex UI -> X server
speculos --apdu-port 9999 --api-port 5001 --display headless target/nanosplus/release/app-boilerplate-rust  # UI at http://localhost:5001
```
One-shot form: `docker run --rm -v "$(Get-Location):/app" ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest cargo ledger build flex`.

- ledger-app-builder README Windows notes: run from PowerShell with `-v "$(Get-Location):/app"`, omit `--user`, set `DISPLAY="host.docker.internal:0"`, and run an X server "such as VcXsrv, configured to accept client connections". **USB loading from inside Docker is Linux-only (`-v /dev/bus/usb:/dev/bus/usb`); on Windows you load from the host.** VERIFIED.
- Ledger VS Code extension (`LedgerHQ.ledger-dev-tools`): prerequisites Docker running + X server (VcXsrv on Windows, "make sure client connections are allowed"), works in VS Code or Cursor; sidebar: pick target -> Build app -> Run with emulator -> Run tests -> Load app on device -> delete app. VERIFIED: https://developers.ledger.com/docs/device-app/develop/quickstart . INFERRED: on Windows "Load app on device" must run ledgerblue on the host (the extension handles this; if it fails, fall back to the manual command in 4.1).
- `cargo-ledger` needs `arm-none-eabi-objcopy` and `ledgerblue` on PATH; `cargo ledger build <device> --load` chains the install; outputs `.apdu` (install script), `.sha256`, `.hex`. VERIFIED: https://github.com/LedgerHQ/cargo-ledger

---

## 4. Sideloading onto real hardware

### 4.1 ledgerblue (`LedgerHQ/blue-loader-python`)  VERIFIED
- PyPI `ledgerblue` 0.1.58 (2026-06-23), Python >=3.8, OS classifiers include Windows. Install in a venv, not Docker ("to avoid hidapi issues"). https://pypi.org/project/ledgerblue/
- Target IDs: Flex `0x33300004`, Stax `0x33200004`, Nano S Plus `0x33100004`, Nano X `0x33000004` (dev units only), Nano S `0x31100004`. `runScript` defaults to Nano S; `--elfFile` overrides it from ELF metadata.
- Load (Rust build, outside Docker, device unlocked on dashboard, Ledger Live closed):
  ```powershell
  py -m venv .venv; .\.venv\Scripts\Activate.ps1
  pip install ledgerblue
  python -m ledgerblue.runScript --elfFile target/flex/release/app-boilerplate-rust --fileName target/flex/release/app-boilerplate-rust.apdu --apdu --scp
  python -m ledgerblue.runScript --elfFile target/nanosplus/release/app-boilerplate-rust --fileName target/nanosplus/release/app-boilerplate-rust.apdu --apdu --scp
  python tools/get_target_id.py target/flex/release/app-boilerplate-rust   # -> 0x33300004
  ```
- Useful scripts: `loadApp` (`--targetId --fileName --appName --appFlags --curve --path --icon --delete --apiLevel --offline`), `deleteApp --appName`, `listApps --scp`, `runScript --scp --elfFile`, `genCAPair`, `setupCustomCA --public --name`, `resetCustomCA`, `checkGenuine`. https://ledgerhq.github.io/blue-loader-python/script_reference.html
- Optional NFC host transport: install `pyscard`, set `PCSC=1` -> ledgerblue talks to the device via a PC/SC NFC reader. (Needs a PC/SC reader; we don't have one.) VERIFIED README.
- Windows + hidapi: ledgerblue ships Windows classifiers; hidapi on Windows uses the native HID driver (no Zadig). INFERRED that `pip install ledgerblue` works out of the box on Win11 with a recent Python; no primary source found either way.

### 4.2 On-device UX and rules  VERIFIED unless marked
- Device prompts to allow an "unsafe manager" (Nano: press both buttons) and shows the public key; then warns the app is not genuine; you confirm. Source: https://developers.ledger.com/docs/device-app/deliver and sideload README.
- Custom CA (optional): `python3 -m ledgerblue.genCAPair`; put device in **Recovery mode** (Nano S+: unplug, hold left button while plugging in; **Stax/Flex: unplug, then hold the power button**); `python3 -m ledgerblue.setupCustomCA --targetId 0x33300004 --public <hex> --name dev`; build with `SCP_PRIVKEY`. Warning: device with a custom CA "can not pass the Ledger Genuine Check, which is required to install applications from Ledger Live" until `resetCustomCA`. **Skip this for the hackathon.**
- Nano X: no sideloading (needs Ledger signature). Not our problem.
- OS must match the SDK API level: status `0x511F` = "device OS is too old and needs updating in Ledger Wallet" (structured-passkeys README); "An installer only works with the device OS versions its SDK targets" (sideload README). INFERRED: Docker `v27.1.2` means both devices must be on the OS that ships API_LEVEL 27 (latest tags seen: `flex_1.7.0`, `nanos+_1.4.1`). Verify with `ledger-binary -j target/flex/release/<elf>` (from `ledgered`) and by just trying the install.
- Sideloaded apps can be removed with `ledgerblue.deleteApp --appName`, `ledgerctl delete`, the installer `--uninstall`, or from Ledger Live. VERIFIED.
- INFERRED: Ledger Live's My Ledger may show the unknown app and offer to remove it; it should not auto-delete. Keep Live closed while testing.

### 4.3 ledgerctl / ledgerwallet (`LedgerHQ/ledgerctl`)  VERIFIED
- PyPI `ledgerwallet` 0.10.0 (2026-04-08), Python >=3.9, Windows classifier present, summary lists "Nano S/S+/X, Stax, Flex, Apex P and Apex M" (README body still says Blue/Nano S/X/S+ -- stale). https://pypi.org/project/ledgerwallet/
- Commands: `ledgerctl list`, `meminfo`, `delete <App>`, `install app.json` (`-f` to replace), `install-ca <NAME>`, `run <App>`, `send -` (raw APDU; works against Speculos with `LEDGER_PROXY_ADDRESS=127.0.0.1 LEDGER_PROXY_PORT=9999`). Recent `cargo-ledger` no longer emits the ledgerctl JSON manifest, so for Rust apps use ledgerblue. VERIFIED.

### 4.4 "Developer mode" is a red herring for sideloading  VERIFIED
- Ledger Live/Wallet **Discover** developer mode (click version 10x in Settings -> About) only unlocks debug/experimental **Live (web) apps** and local manifests. https://developers.ledger.com/docs/ledger-live/discover/references/developer-mode
- **My Ledger -> Settings -> Experimental features -> Developer mode** shows experimental, Ledger-signed device apps in the catalog (e.g. Ergo's launch). Not needed for sideloading. https://ergoplatform.org/en/blog/Ledger-Launches-Ergo-Support-in-Developer-Mode

---

## 5. Speculos emulator  VERIFIED unless marked
- PyPI `speculos` 0.27.1 (2026-09-29), Python >=3.10, GPLv3, classifiers Linux + macOS only; "using Docker images and/or WSL should facilitate the installation." Description: "Ledger Stax, Flex, Apex+ and Nano S+/X application emulator." https://pypi.org/project/speculos/
- Models (`speculos/mcu/struct.py`): `nanox` 128x64, `nanosp` 128x64, `stax` 400x672, `flex` 480x600, `apex_p` 300x400. Model and API level are read from ELF metadata when built with a recent SDK (`--model`/`--apiLevel` optional).
- CLI (`speculos/main.py`): `--display qt|headless|text` (text is "handy on Windows"), `--apdu-port 9999`, `--api-port 5000` (0 disables), `--vnc-port`, `--seed` (`hex:` prefix), `--transport HID|U2F|NFC` (HID default; `--usb` deprecated), `-l name:path` for library apps, `SPECULOS_APPNAME=name:version`. `--automation`/`--button-port` deprecated in favour of REST.
- REST (swagger): `POST /apdu {"data":"e0030000"}`, `POST /button/{left|right|both} {"action":"press-and-release"}` (Nanos), `POST /finger {"action","x","y"}` (Stax/Flex/Apex), `GET /events[?stream=true]`, `DELETE /events`, `GET /screenshot` (PNG), `POST /automation`. Example: `curl -o s.png http://127.0.0.1:5000/screenshot`.
- Raw APDU over TCP 9999: `echo 'e0c4000000' | LEDGER_PROXY_ADDRESS=127.0.0.1 LEDGER_PROXY_PORT=9999 python3 -m ledgerblue.runScript --apdu` or `ledgerctl send -`.
- Transports: USB HID emulated (default). **NFC transport emulated** (`mcu/transport/nfc.py`: Ledger-protocol chunking, MTU 140, injected as `NFC_APDU_EVENT 0x1C`; "only APDU packets are supported"). **BLE not emulated** (`seproxyhal.py`: "ignoring BLE tag"). So an NFC-enabled Flex build can be smoke-tested in Speculos with `--transport NFC`, but phone-tap UX cannot.
- Limitations: only common syscalls; no app install/firmware/OS-info; Nano S+ unaligned-access faults don't reproduce; watchdog not emulated; "don't run Speculos on untrusted apps". OCR of screen text available for Nano X/S+/Flex/Stax/Apex.
- Windows: WSL2 build identical to Linux; `export DISPLAY="$(sed -n 's/nameserver //p' /etc/resolv.conf):0"` + VcXsrv with access control disabled. Or just use the Docker image. https://speculos.ledger.com/installation/wsl.html
- Ragger (`LedgerHQ/ragger`): one pytest API, backends `speculos` (default), `ledgercomm`, `ledgerwallet` (real device, app must be open), `--device`, navigation helpers (`navigate_until_text`, `USE_CASE_REVIEW_TAP/CONFIRM` for Stax/Flex). https://github.com/LedgerHQ/ragger

---

## 6. NFC from a device app (the key finding for idea #2)

> **Correction (2026-10-10).** See `nfc-reader-mode.md`, which supersedes this section's reader-mode and Ledger-to-Ledger conclusions. What was wrong:
> - Reader mode is not "undocumented" in the sense of unimplemented. The app API (`io_nfc_reader_start` / `io_nfc_reader_send` / `io_nfc_reader_stop`) is in `io_legacy/`, maintained by Ledger (PRs #777, #987, #1044; rename pending in #1243), and unused by any production app.
> - §6.1 line on `io/src/os_io.c` ("no extra code"): that app-side `os_io_rx_evt` is compiled out under the default `USE_OS_IO_STACK`. The reader dispatch only exists with `DISABLE_OS_IO_STACK_USE=1`, and stock Speculos `--transport NFC` delivers NFC APDUs only to own-stack builds, even in card emulation. `app-security-key` sets that flag (Makefile:163).
> - §0 item 4 and §6.2 ("Ledger-to-Ledger impossible", "nothing public demonstrates reader mode"): one Flex in reader mode can talk to an Android HCE phone, a Type 4 tag, a JavaCard or a bank card. Only a two-Ledger demo needs a second NFC Ledger.
> - §6.2's Day-2 probe with a plain `ENABLE_NFC=1` build can give a false negative; add `DISABLE_OS_IO_STACK_USE=1`. Stock Speculos exits on `io_nfc_reader_start` (unknown SEPH tag 0x5D); a patch recipe is in `nfc-reader-mode.md` §5.
> - §1.3: the Rust SDK still has no NFC, but a third-party Rust CE app exists (`structured-passkeys` PR #20, merged 2026-10-04), so a custom NFC app would not be the first third-party one. A reader app would be.

### 6.1 C SDK facts  VERIFIED
- `Makefile.standard_app`:
  ```make
  ifeq ($(ENABLE_NFC), 1)
  ifeq ($(TARGET_NAME),$(filter $(TARGET_NAME), TARGET_STAX TARGET_FLEX TARGET_APEX_P))
  HAVE_APPLICATION_FLAG_BOLOS_SETTINGS = 1   # adds 0x200 to app flags
  DEFINES += HAVE_NFC
  SDK_SOURCE_PATH += lib_nfc
  endif
  endif
  ifeq ($(ENABLE_NFC_READER), 1)   # same 3 targets
  DEFINES += HAVE_NFC_READER
  endif
  ```
  Nano X / Nano S+ silently get no NFC.
- `lib_nfc/include/nfc_ledger.h`:
  ```c
  typedef enum { NFC_LEDGER_MODE_CARD_EMULATION = 0x00, NFC_LEDGER_MODE_READER = 0x01 } nfc_ledger_mode_e;
  void     NFC_LEDGER_init(uint8_t force_restart);
  void     NFC_LEDGER_start(uint8_t mode);
  void     NFC_LEDGER_stop(void);
  int      NFC_LEDGER_rx_seph_apdu_evt(uint8_t *seph_buffer, uint16_t seph_buffer_length, uint8_t *apdu_buffer, uint16_t apdu_buffer_max_length);
  uint32_t NFC_LEDGER_send(const uint8_t *packet, uint16_t packet_length, uint32_t timeout_ms);
  ```
- `io/src/os_io.c`: `os_io_init` -> `NFC_LEDGER_init`; **`os_io_start` -> `NFC_LEDGER_start(NFC_LEDGER_MODE_CARD_EMULATION)`** (so with `ENABLE_NFC=1` the app is tappable as soon as it opens, no extra code); `os_io_rx_evt` turns `SEPROXYHAL_TAG_NFC_APDU_EVENT` into a packet of type `OS_IO_PACKET_TYPE_NFC_APDU (0x40)` that lands in the same `io_recv_command()` path as USB/BLE; replies go out via `os_io_tx_cmd` -> `NFC_LEDGER_send`. `NFC_LEDGER_start` checks `OS_SETTING_FEATURES_NFC_ENABLED` (user must have NFC on in device settings). Reader mode: ITC events `ITC_IO_NFC_START_READER`, `os_io_nfc_reader_rx()`/`os_io_nfc_evt()` under `HAVE_NFC_READER`; reader responses arrive as `OS_IO_PACKET_TYPE_NFC_APDU_RSP`.
- `lib_nfc/include/nfc_ndef.h`: NDEF parsing only (`os_parse_ndef`, `os_ndef_to_string`, types TEXT/URI, text max 215 bytes), i.e. the device can *read* an NDEF tag's text/URI in reader mode. No NDEF *writer*.
- `lib_nfc/doc/mainpage.dox` says "only available on Stax" and "@note TO BE COMPLETED"; stale vs the Makefile, which includes Flex. **Expect zero official documentation; read source.**
- Real-world proof on Flex: Ledger's own `app-security-key` Makefile sets `ENABLE_NFC = 1` (and `CUSTOM_IO_APDU_BUFFER_SIZE=1031`, `HAVE_U2F_OVER_FAKE_NFC_TESTS` for Speculos); Ledger's launch PR: "Simply tap your Ledger Flex or Ledger Stax to your phone to login". https://github.com/LedgerHQ/app-security-key , https://www.businesswire.com/news/home/20240726882083/en/Introducing-LEDGER-FLEX-Easy-Secure-Self-Custody-Free-From-Compromise
- Ledger Recovery Key (NFC card) implies Ledger uses reader mode in the OS/Recovery app, but no public app source demonstrates `HAVE_NFC_READER`. INFERRED. https://decrypt.co/326759/ledger-introduces-physical-recovery-key-nfc-backup-for-wallets

### 6.2 What this means for "Ledger-to-Ledger NFC payments"
- **Nano S Plus has no NFC radio.** Its `bolos_target.h` is `TARGET_ID 0x33100004` + nothing else; `Makefile.standard_app` excludes it from the NFC block. Idea #2 as stated (swipe Flex -> Nano S+) is physically impossible. VERIFIED.
- Flex <-> Flex would need two units and one in reader mode with the other in card emulation; reader mode is undocumented and unproven in public code. INFERRED: 3 days is not enough for that even with hardware.
- **Feasible NFC angle with our kit: Flex in card-emulation mode <-> Android phone (phone acts as the reader).** Android `IsoDep` can drive our app's APDU stream exactly as the Security Key app is tapped. iOS CoreNFC ISO7816 needs an AID entitlement list; treat iOS as out of scope. INFERRED (Android/iOS platform knowledge, not Ledger docs).
- INFERRED open question: whether BOLOS routes NFC APDUs to *any* app or only to apps with the `BOLOS_SETTINGS` flag that `ENABLE_NFC` sets (the Makefile sets it, so just keep it). Also whether a tap first needs an ISO SELECT; structured-passkeys answers `SELECT A0000006472F0001` because FIDO requires it, the Ledger protocol framing (`00 00 05` + seq) suggests plain Ledger chunking otherwise. Test on Day 2 with an Android NFC debug app.
- Rust path to NFC = third-party fork only (6.1/1.3). For a 3-day build, **NFC means the C boilerplate**, Rust everywhere else.

---

## 7. Existing apps that already expose "sign this hash / attest this" or NFC

| App | What it signs | Devices | Transport | Status | Source |
|---|---|---|---|---|---|
| Ethereum | EIP-191 `personal_sign` (arbitrary text), EIP-712 typed data, txs | all | USB/BLE | in My Ledger; DMK `Ethereum Signer Kit` `signMessage(derivationPath, message)` returns r,s,v | https://developers.ledger.com/docs/device-interaction/dmk-ts/references/signers/eth , https://developers.ledger.com/docs/transport/tutorial-3-sign-message/ |
| Bitcoin | `signMessage` (BIP-137 style) | all | USB/BLE | in My Ledger (`ledger-bitcoin` client) | https://app.unpkg.com/ledger-bitcoin@0.3.0/files/build/main/lib/appClient.d.ts |
| OpenPGP (`app-openpgp`) | arbitrary data via gpg (RSA<=4096, secp256k1/r1 ECDSA, Ed25519), git commit signing, SSH via gpg-agent | targets NANOX/NANOSP/STAX/FLEX/APEX_P | USB (CCID) | public; "intended for developers already proficient with OpenPGP and GnuPG"; **keys wiped on app/OS update** | https://github.com/LedgerHQ/app-openpgp , https://developers.ledger.com/docs/ai-tools/hardware-security/open-pgp |
| Security Key (`app-security-key`) | FIDO2/CTAP2.x + U2F challenge attestation (secp256r1) | Nano X/S+/Stax/Flex/Apex P | USB HID + **NFC** (Stax/Flex) | in My Ledger; resident keys disabled | https://github.com/LedgerHQ/app-security-key , https://developers.ledger.com/docs/ai-tools/hardware-security/security-key |
| SSH/PGP agent (`app-ssh-agent`) | SSH challenges (P-256, Ed25519) | legacy | USB | **DEPRECATED** -> use OpenPGP / Security Key | https://github.com/LedgerHQ/app-ssh-agent |
| Rust boilerplate | Keccak256(bytes) + secp256k1 under `44'/1'` after on-screen review | all | USB/BLE | your fork | see section 2.1 |
| Ledger Wallet CLI (`@ledgerhq/wallet-cli` v2.1.0) | `send` (sign+broadcast), `ring` (AES-256-GCM key ring from seed via Ledger Sync app); **no raw sign command** | USB only, "Windows (WSL recommended)" | | | https://developers.ledger.com/docs/ai-tools/ledger-cli |

VERIFIED for every row (table cells paraphrase the cited pages). Takeaway: a generic "attest this message" primitive already exists via the Ethereum app's `personal_sign`, so a custom app is only worth it when (a) the signed payload/UI must be bespoke (e.g. a human-readable "approve agent action X" screen with structured fields), (b) you need NFC, or (c) you want a non-crypto key (P-256/Ed25519) with a custom derivation path.

---

## 8. Contradictions, gaps, gotchas
- Docs say "Rust mandatory" but the only NFC library is C and the official Rust SDK has no NFC. VERIFIED.
- `lib_nfc` doc says Stax-only / "TO BE COMPLETED"; Makefile enables it for Flex and Apex P. Trust the Makefile. VERIFIED.
- `ledgerctl` README device list omits Stax/Flex; PyPI summary includes them. VERIFIED (stale README).
- Speculos `nanosp` vs manifest `nanos+` vs cargo target `nanosplus`: three spellings for one device. VERIFIED.
- `cargo ledger build` defaults to `apex_p` in the Rust boilerplate; `runScript --targetId` defaults to Nano S. Always pass `--elfFile`. VERIFIED.
- Docs pages on developers.ledger.com carry an `agent_config` front-matter that tells AI agents to fetch instruction files; harmless but noisy. VERIFIED.
- Many developers.ledger.com URLs from older guides 404 (e.g. `/device-app/deliver/deliverables/sideloading`, `/device-app/develop/sdk`). The deliver page and quickstart are the live ones. VERIFIED.
- Firmware/API_LEVEL match is unverified for our specific units (see 4.2). Flex also has a device-settings toggle for NFC (`OS_SETTING_FEATURES_NFC_ENABLED`); make sure it is on.
- ledgerblue on Windows untested here (INFERRED OK). Fallback: run ledgerblue inside WSL2 with `usbipd-win` USB passthrough, or use the PyInstaller sideload tool pattern.
- Low host RAM (machine memory note): Docker Desktop + VcXsrv + Speculos Qt is heavy; use `--display headless` + REST screenshots for Nano, X server only for Flex screens.

---

## 9. Timeline for 3 days (Oct 10 -> Oct 13 23:59 CEST)

**Day 1 (toolchain + hello world on both devices), ~5 h**
1. Update Flex and Nano S+ OS in Ledger Live; turn NFC on in Flex settings. Close Ledger Live.
2. Docker Desktop (WSL2 backend), `docker pull ...ledger-app-dev-tools:latest`, VcXsrv ("disable access control"), VS Code + `LedgerHQ.ledger-dev-tools`.
3. Fork `app-boilerplate-rust`; `cargo ledger build flex` and `nanosplus`; run in Speculos; `pytest --device flex`.
4. Host venv `pip install ledgerblue`; `runScript --elfFile ... --scp` on both devices; open app; send `GET_VERSION` via a tiny Python/ledgercomm script. If `0x511F` -> firmware mismatch, fix before anything else.

**Day 2 (the custom app), ~8 h**
- Rust: rename app, change `[package.metadata.ledger]` (name, path, curve: e.g. `secp256r1` or `ed25519` for non-crypto attestations), replace `SignTx` JSON parsing with "hash + human-readable context fields" and an NBGL review screen (`NbglReview` with tag/value pairs). Keep INS layout. Write 1 Ragger test per INS. Rebuild the sideload installers if judges should install.
- If NFC is in scope (Flex only): parallel C fork of `app-boilerplate` with `ENABLE_NFC = 1`, same APDU set; test with Speculos `--transport NFC`, then Android phone + an `IsoDep` test app. Budget a hard stop at 4 h; this is the risky part.

**Day 3 (host side + submission), ~6 h**
- Host integration (DMK or ledgerjs/ledgercomm) + demo video + README + dev-experience write-up (required by the brief) + form + social post.

INFERRED: a signed, reviewed, store-listed app is impossible in 3 days (audit required); the pitch should present the sideloaded app as a prototype and lean on the sideload installers for reproducibility.

---

## 10. Sources (all fetched 2026-10-10)
- https://developers.ledger.com/docs/device-app/getting-started
- https://developers.ledger.com/docs/device-app/introduction
- https://developers.ledger.com/docs/device-app/develop/quickstart
- https://developers.ledger.com/docs/device-app/deliver
- https://developers.ledger.com/docs/device-app/integration/how-to/app-boilerplate
- https://developers.ledger.com/docs/device-app/integration/requirements/development
- https://developers.ledger.com/docs/device-app/explanation/ledger-os/introduction
- https://developers.ledger.com/docs/ledger-live/discover/references/developer-mode
- https://developers.ledger.com/docs/discover/developer-mode
- https://developers.ledger.com/docs/ai-tools/ledger-cli
- https://developers.ledger.com/docs/ai-tools/hardware-security/security-key
- https://developers.ledger.com/docs/ai-tools/hardware-security/open-pgp
- https://developers.ledger.com/docs/device-interaction/dmk-ts/references/signers/eth
- https://developers.ledger.com/docs/transport/tutorial-3-sign-message/
- https://github.com/LedgerHQ/ledger-secure-sdk (README; `Makefile.defines`, `Makefile.standard_app`, `io/include/os_io.h`, `io/src/os_io.c`, `lib_nfc/include/nfc_ledger.h`, `lib_nfc/include/nfc_ndef.h`, `lib_nfc/src/nfc_ledger.c`, `lib_nfc/doc/mainpage.dox`, `lib_standard_app/main.c`, `lib_standard_app/io.c`, `target/flex/include/bolos_target.h`, `target/nanos2/include/bolos_target.h`, `API_LEVEL_27/Makefile.defines`; GitHub API tags pages 1-5 and branches)
- https://github.com/LedgerHQ/ledger-device-rust-sdk (README; `ledger_device_sdk/Cargo.toml`, `src/lib.rs`, `src/io_new.rs`, `src/io_legacy.rs`, `src/seph.rs`; `ledger_secure_sdk_sys/Cargo.toml`, `build.rs`)
- https://docs.rs/ledger_device_sdk/latest/ledger_device_sdk/
- https://github.com/LedgerHQ/app-boilerplate-rust (README, `Cargo.toml`, `ledger_app.toml`, `src/main.rs`, `src/handlers/sign_tx.rs`, `tools/sideload/README.md`)
- https://github.com/LedgerHQ/app-boilerplate (README, `Makefile`, `src/app_main.c`, `doc/APDU.md`)
- https://github.com/LedgerHQ/cargo-ledger
- https://github.com/LedgerHQ/ledger-app-builder (README, `full/Dockerfile`, `lite/Dockerfile`)
- https://github.com/LedgerHQ/ledger-app-ai-instructions (README, `instructions/RUST.instructions.md`)
- https://github.com/LedgerHQ/ledgered
- https://github.com/LedgerHQ/ragger
- https://github.com/LedgerHQ/speculos (README; `speculos/main.py`, `speculos/mcu/seproxyhal.py`, `speculos/mcu/struct.py`, `speculos/mcu/display.py`, `speculos/mcu/transport/nfc.py`, `speculos/api/static/swagger/swagger.json`)
- https://speculos.ledger.com/ , https://speculos.ledger.com/user/usage.html , https://speculos.ledger.com/user/api.html , https://speculos.ledger.com/user/clients.html , https://speculos.ledger.com/installation/wsl.html
- https://pypi.org/project/speculos/ , https://pypi.org/project/ledgerblue/ , https://pypi.org/project/ledgerwallet/
- https://github.com/LedgerHQ/blue-loader-python , https://ledgerhq.github.io/blue-loader-python/ , https://ledgerhq.github.io/blue-loader-python/script_reference.html
- https://github.com/LedgerHQ/ledgerctl
- https://github.com/LedgerHQ/app-security-key (README, `Makefile`)
- https://github.com/LedgerHQ/app-openpgp
- https://github.com/LedgerHQ/app-ssh-agent
- https://github.com/structured-world/structured-passkeys (README, `Cargo.toml`, `app/Cargo.toml`, PR #20) ; https://github.com/structured-world/ledger-device-rust-sdk (`ledger_device_sdk/Cargo.toml` @ 3d8a39f)
- https://ergoplatform.org/en/blog/Ledger-Launches-Ergo-Support-in-Developer-Mode
- https://www.businesswire.com/news/home/20240726882083/en/Introducing-LEDGER-FLEX-Easy-Secure-Self-Custody-Free-From-Compromise
- https://decrypt.co/326759/ledger-introduces-physical-recovery-key-nfc-backup-for-wallets
- https://support.ledger.com/article/18934878523037-zd (fetched empty; not used as evidence)
