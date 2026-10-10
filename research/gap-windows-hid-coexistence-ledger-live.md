# Windows 11 USB/HID reality check: Ledger Live coexistence, drivers, node-hid, Python tooling

Researched 2026-10-10 from primary sources (source code, npm registry, PyPI, Microsoft docs, GitHub issues). No hardware touched, nothing installed. Tarballs for `node-hid` and `usb` were downloaded to the scratchpad to list their contents.

Legend: **VERIFIED** = read in a primary source (quoted or cited below). **INFERRED** = reasoned from verified facts, not directly observed. **SNIPPET** = text seen only in a search-engine snippet of an official page whose body could not be fetched (support.ledger.com is a JS-rendered SPA; both the HTML and the Zendesk JSON endpoint return the 77 KB shell).

---

## TL;DR for Day 1

1. **No driver install, no Zadig, no admin needed for HID on Windows 10/11.** The APDU interface is a standard HID class interface (`bInterfaceClass 0x03`, usage page `0xFFA0`), so `hidclass.sys` binds it in-box. The WebUSB interface ships Microsoft OS 2.0 descriptors with compatible ID `WINUSB`, so `winusb.sys` auto-binds on Windows 8.1+ with no INF. **VERIFIED** (SDK source + Microsoft docs; see §2).
2. **Ledger Live (now "Ledger Wallet") does NOT take an exclusive lock on Windows.** Both hidapi (node-hid, Python `hid`) and Chromium (Electron WebHID, which LLD uses) open the device with `FILE_SHARE_READ | FILE_SHARE_WRITE`. A second process can open the same HID collection. **VERIFIED** (§3). The "cannot open device with path" failure is a **macOS** phenomenon (exclusive seize), not Windows. **VERIFIED** (node-hid maintainer, §3.4).
3. **What actually breaks on Windows is interleaving, not opening.** LLD keeps its WebHID handle open (its `close()` is a no-op) and sends APDUs whenever one of its device flows runs. Windows delivers every input report to every open handle; the DMK receiver does **not** check the channel ID, so a foreign response frame is parsed as yours → `ReceiverApduError`, wrong-length responses, or stalls. **VERIFIED** mechanics / **INFERRED** symptom (§3.3). Rule stays the same as every note assumed: **quit Ledger Live before running your own transport.** Ledger's support site says exactly this for third-party wallets. **SNIPPET** (§4).
4. **`@ledgerhq/device-transport-kit-node-hid@1.0.1` → `node-hid ^3.2.0` + `usb ^2.16.0`.** `node-hid@3.4.0` ships a `win32-x64` N-API v4 prebuild; `usb@2.19.1` ships `win32-x64` prebuild with libusb 1.0.30 (Windows hotplug). No compile on Node 22/24 unless a prebuild loader misfires. **VERIFIED** (§5).
5. **wallet-cli (Agent Stack) on Windows uses node-usb WebUSB bulk, not HID**, pins `usb@2.17.0` (libusb 1.0.29 = **no** Windows hotplug) and polls every 1 s as a fallback. Needs the WinUSB-bound interface → should work out of the box via MS OS 2.0 descriptors. **VERIFIED** code / **INFERRED** behaviour (§5.3).
6. **Python:** `hidapi` 0.15.0 has cp312/cp313/cp314 `win_amd64` wheels; `ledgerblue` 0.1.58 and `ledgerwallet` 0.10.0 (ledgerctl) have pure-Python or wheeled deps. Expect `pip install` to work on Python 3.12/3.13 without a compiler. **VERIFIED** deps / **INFERRED** install success (§6).
7. **Opening/closing a device app re-enumerates USB** (PID changes with the interface mask). Expect a disconnect/connect pair up to ~6 s; DMK's `RECONNECT_DEVICE_TIMEOUT = 6000`. Any script that opens an app must tolerate this. **VERIFIED** (§2.3).
8. **WSL is a trap for USB**: `blue-loader-python#83` "No dongle found" under WSL. Ledger CLI docs say "Windows (WSL recommended)" but ship a native `windows-x64` binary; use native Windows. **VERIFIED** issue / **INFERRED** recommendation (§7).

---

## 1. How Ledger Live / Ledger Wallet desktop talks to the device on Windows

### 1.1 It is Electron WebHID in the renderer, through DMK — not node-hid

- `apps/ledger-live-desktop/package.json` (app version 4.23.0) has **no** `node-hid` or `usb` dependency; it depends on `@ledgerhq/device-management-kit` and `@ledgerhq/hw-transport`. **VERIFIED** [S1]
- `apps/ledger-live-desktop/src/main/window-lifecycle.ts` registers Electron's WebHID chooser hook and auto-picks the first Ledger VID device: **VERIFIED** [S2]

  ```ts
  mainWindow.webContents.session.on("select-hid-device", (event, details, callback) => {
    event.preventDefault();
    const ledgerDevices = details.deviceList.filter(
      device => device.vendorId === ledgerUSBVendorId,
    );
    if (ledgerDevices.length > 0) {
      callback(ledgerDevices[0].deviceId);
    } else {
      console.warn("No Ledger HID devices found.");
    }
  });
  ```
- `libs/live-dmk-desktop/src/hooks/useDeviceManagementKit.tsx` builds the DMK with `.addTransport(webHidTransportFactory)` from `@ledgerhq/device-transport-kit-web-hid` (plus Speculos and mockserver transports). **VERIFIED** [S3]
- Electron version in the monorepo catalog: `electron: 43.1.1`. **VERIFIED** [S4]
- A legacy `@ledgerhq/hw-transport-node-hid-singleton` path could not be found in the current LLD tree (GitHub code search for it returned no LLD files). **VERIFIED absence** [S5]. Older LLD versions did use node-hid in an "internal" process (ledgerjs maintainer comments from 2019–2020 reference `node-hid-singleton`), so third-party write-ups describing LLD as a node-hid app are stale. **INFERRED**

### 1.2 Does LLD hold the handle open, and does it poll?

- `libs/live-dmk-desktop/src/transport/DeviceManagementKitTransport.ts`: **VERIFIED** [S6]
  - `open()` connects with `sessionRefresherOptions: { isRefresherDisabled: true }` — LLD **disables** DMK's 1 s background `GetAppAndVersion`-style refresher.
  - `close: () => Promise<void> = () => Promise.resolve();` — **closing the transport does not close the HID device.** The DMK session (and therefore the Chromium HID handle) stays open until `disconnect()` or device removal.
  - `exchange()` silently reconnects if the session vanished.
- Consequence: while LLD is running with a device plugged in, a Chromium-owned handle to the APDU collection stays open. It is **quiet** (no refresher) until LLD runs a device flow (account add, app install, swap, firmware check, "genuine check", clear-signing flows), each of which sends APDUs through this always-open handle. **INFERRED** from the above; LLD's higher-level live-common polling (e.g. `getAppAndVersion` loops in device actions) was not traced in this pass.
- DMK default refresher (relevant for *your* app, and for any third-party DMK app that leaves defaults on): `DEVICE_SESSION_REFRESHER_POLLING_INTERVAL = 1000` ms, Nano S doubled, skipped while busy. **VERIFIED** [S7]

---

## 2. What USB interfaces a Flex / Nano S Plus expose, and Windows driver binding

### 2.1 Interfaces (from `ledger-secure-sdk/lib_stusb`)

| Class (SDK name) | Interface | Driver Windows binds | Source |
|---|---|---|---|
| `USBD_LEDGER_CLASS_HID` — APDU channel | `bInterfaceClass 0x03`, EP OUT `0x02` / IN `0x82`, 64-byte, `bInterval 1`; report descriptor `06 A0 FF` (usage page **0xFFA0**), usage `0x01`, report count 64 in/out, **no report ID** | `hidclass.sys` (in-box) | **VERIFIED** [S8] |
| `USBD_LEDGER_CLASS_WEBUSB` | `bInterfaceClass 0xFF` (vendor), EP OUT `0x03` / IN `0x83`; BOS with WebUSB platform capability (`3408B638-…`) **and** Microsoft OS 2.0 platform capability (`D8DD60DF-…`), `dwWindowsVersion` "minimum 8.1 (0x06030000)", compatible ID `'W','I','N','U','S','B'`, registry property `DeviceInterfaceGUIDs = {CE809264-4B24-4E81-A8B2-57ED01D580E1}`; legacy MS OS 1.0 `MSFT100` string too, with a *different* GUID `{13d63400-2C97-0004-0000-4c6564676572}` | `winusb.sys` (in-box, auto via compat ID) | **VERIFIED** [S9] |
| `USBD_LEDGER_CLASS_HID_U2F` | second HID interface (FIDO usage page) — only when a FIDO/security-key app enables it | `hidclass.sys` | class referenced in `usbd_ledger.c`; descriptor file not read → **INFERRED** [S10] |
| `USBD_LEDGER_CLASS_HID_KBD` | HID keyboard (Passwords-type apps) | `kbdhid.sys`, OS-exclusive | referenced in `usbd_ledger.c` → **INFERRED** [S10] |
| `USBD_LEDGER_CLASS_CCID_BULK` | CCID (OpenPGP app) | `usbccid.sys` / WUDFUsbccidDriver (in-box) | referenced → **INFERRED** [S10] |
| `USBD_LEDGER_CLASS_CDC*` | CDC serial (debug/dev builds) | `usbser.sys` | referenced → **INFERRED** [S10] |

- Interface numbers are assigned in class order: "the interface descriptor's byte at offset 2 is set to `index`"; `bNumInterfaces` incremented per class. The WebUSB descriptor hardcodes `bFirstInterface 0x01` with a `TODO_IO` comment — i.e., the firmware assumes HID = interface 0, WebUSB = interface 1 in the default (dashboard) configuration. **VERIFIED** [S9][S10]
- Vendor ID `0x2c97`. Product ID is `MMII`: model byte `MM` (Nano S `0x10`, Nano X `0x40`, **Nano S Plus `0x50`**, Stax `0x60`, **Flex/"europa" `0x70`**, Nano Gen5/"apex" `0x80`) and an interface bitfield `II`. `identifyUSBProductId` matches on `usbProductId >> 8`. **VERIFIED** [S11]. The SDK file read (`usbd_ledger.c`) does not itself OR class bits into the PID (`pid = product` fallback), so where the low byte is composed was not located in this pass — **gap**.

### 2.2 Windows auto-binding — no Zadig

- Microsoft: "A WinUSB device is a USB device whose firmware defines certain Microsoft OS feature descriptors that report `WINUSB` as the compatible ID. … enable Windows to load Winusb.sys as the device's function driver without a custom INF file." "In Windows 8, the in-box Winusb.inf file is updated … `%USB\MS_COMP_WINUSB.DeviceDesc%=WINUSB,USB\MS_COMP_WINUSB`." For composite devices "The compatibleID field of each function section must specify `WINUSB`." **VERIFIED** [S12]
- Ledger firmware supplies exactly that (§2.1). Therefore the WebUSB interface appears in Device Manager under **"Universal Serial Bus devices"** as a WinUSB device, and the HID interface under **"Human Interface Devices"** as "HID-compliant vendor-defined device" (the 2017 ledgerjs #4 reporter saw "USB Input Device" + "HID-compliant vendor-defined device" installed automatically). **VERIFIED** [S13] (device-manager names from that issue; current Windows 11 names **INFERRED**)
- **No Ledger source consulted mentions Zadig.** Not the SDK, not ledgerblue, not ledgerctl, not the DMK docs, not the support search results. Zadig is only needed if you want *libusb* to drive an interface that Windows bound to a *different* driver (e.g. force WinUSB onto the HID interface). Don't. node-usb's README: "If `LIBUSB_ERROR_NOT_SUPPORTED` occurs when opening a device, the device may lack a WinUSB driver. Options are installing one with Zadig, or calling `usb.useUsbDkBackend()`." — that error would only appear if you tried to `claim()` the **HID** interface through libusb. **VERIFIED** [S14]
- Ledger support search snippets (official article "Fix USB connection issues with Ledger Wallet (formerly Ledger Live)", id 115005165269): steps are cable/port, close other apps & extensions, run Ledger Wallet as administrator, "update the USB drivers" via Device Manager automatic search, disable AV/VPN, Windows **S mode blocks it**, **Windows 10 64-bit+ only, arm64 unsupported**. No driver download is offered. **SNIPPET** [S15][S16]

### 2.3 App open/close = USB re-enumeration

- ledgerjs maintainer (gre, 2019): "when you enter an app, it's disconnecting and reconnecting a device on the USB stack." **VERIFIED** [S17]
- DMK `NodeHidConfig.ts` / `WebHidConfig.ts`: `RECONNECT_DEVICE_TIMEOUT = 6000; // in some cases, when opening/closing an app, it takes up to 6s between the HID "disconnect" and "connect" events`. **VERIFIED** [S18]
- On Windows the PID low byte changes when the class mask changes (e.g. an app adds U2F/CCID), so Windows sees a *new* device ID and may do a first-time driver bind (a few seconds, "Setting up a device" toast). **INFERRED** from §2.1.
- ledgerjs #430 (open, 2019): on Windows 10 the `hw-transport-node-hid` `listen()` observer missed the re-attach after app open; `list()` saw the device. Historical, usb-detection era. **VERIFIED** [S17]

---

## 3. Two processes on one HID device on Windows: what really happens

### 3.1 hidapi (node-hid, Python `hid`, ledgerblue, ledgerctl) opens **shared**

`hidapi/windows/hid.c` `open_device()` — identical in upstream master and in the copy bundled inside `node-hid@3.4.0` (hidapi `VERSION` = 0.15.0): **VERIFIED** [S19][S20]

```c
DWORD desired_access = (open_rw)? (GENERIC_WRITE | GENERIC_READ): 0;
DWORD share_mode = FILE_SHARE_READ|FILE_SHARE_WRITE;
handle = CreateFileW(path, desired_access, share_mode, NULL, OPEN_EXISTING,
                     FILE_FLAG_OVERLAPPED, /*FILE_ATTRIBUTE_NORMAL,*/ 0);
```

- `hid_enumerate` opens each device with zero access (`open_device(device_interface, FALSE)`) just to read attributes. Enumeration never fails because someone else has the device open. **VERIFIED** [S19]
- `hid_open_path` falls back to zero-access open with the comment "System devices, such as keyboards and mice, cannot be opened in read-write mode, because the system takes exclusive control over them" — that is the **only** exclusivity on Windows, and it is the OS, not another app. **VERIFIED** [S19]
- `hid_write` is synchronous (waits on the overlapped event); `hid_read_timeout` leaves an overlapped read pending; hidapi calls `HidD_SetNumInputBuffers(handle, 64)` ("Set the Input Report buffer size to 64 reports"). **VERIFIED** [S19]
- node-hid `nonExclusive` option: "On MacOs if set to true the `nonExclusive` property allows the device to be opened in non-exclusive mode. … For the other platforms the flag has no impact." DMK's `NodeHidApduSender` passes `nonExclusive: true` — a macOS-only effect. **VERIFIED** [S21][S22]

### 3.2 Chromium / Electron WebHID (what LLD uses) opens **shared** too

`services/device/hid/hid_service_win.cc` `OpenDevice`: tries `GENERIC_WRITE | GENERIC_READ`, then `GENERIC_READ`, then `0`, each with `FILE_SHARE_READ | FILE_SHARE_WRITE, FILE_FLAG_OVERLAPPED`; the loop only continues on `ERROR_ACCESS_DENIED`. One `HidDeviceInfo` per device-interface path (so the APDU collection and a U2F collection are separate `HIDDevice`s). **VERIFIED** [S23]

### 3.3 So both handles open. Then what?

- Windows `hidclass` keeps an input-report ring buffer per open handle ("sets the maximum number of input reports that the HID class driver ring buffer can hold for a specified top-level collection", parameter is "an open handle"; default 32). Every open handle receives every input report the device sends. The per-handle wording is **INFERRED** from the API shape (Microsoft's page does not spell out "per file object"); the practical consequence ("both processes see all responses") is what the 2017 Windows cross-talk report in ledgerjs #4 shows (`=> 0101 05 …` sent, `<= 0105 0000 …` received, "Invalid channel"). **VERIFIED** API text [S24], **VERIFIED** symptom example [S13], causal link **INFERRED**.
- Who filters? 
  - **Old ledgerjs `hid-framing`**: validated channel/tag/sequence and threw "Invalid channel" — that is the historic error string you'd see. **VERIFIED** from the #4 log [S13] (source file not fetched this pass).
  - **ledgerctl `hid.py`**: `assert data_chunk[:2] == b"\x01\x01"`, `assert data_chunk[2] == 5`, `assert data_chunk[3:5] == seq_idx…` → **`AssertionError`** on a foreign frame. Channel is fixed `0x0101`, so two Python tools cross-talk indistinguishably. **VERIFIED** [S25]
  - **ledgerblue `comm.py`**: channel fixed `0x0101`, `wrapCommandAPDU(0x0101, apdu, 64)`, 65-byte reads, `CommException("Timeout")` after `TIMEOUT`. Unwrap behaviour on bad frames not read → **gap**. **VERIFIED** partial [S26]
  - **DMK `DefaultApduReceiverService`**: **no channel check, no tag check**; only "a non-first frame with no pending first frame" → `Left(new ReceiverApduError())`; short header → `ReceiverApduError("Unable to parse header from apdu")`; completion is `totalReceiveLength >= dataSize` from the *first* frame's length field. DMK's channel is random per instance (`Math.floor(Math.random() * 0xffff)`) but it is only used to compute how many bytes to skip. **VERIFIED** [S27][S22]
- Therefore, with LLD open **and active** on Windows, a DMK node-hid app will: (a) receive LLD's response frames and treat them as its own → wrong status/data or `ReceiverApduError`; (b) have its own response consumed by nobody (fine) or interleaved with LLD's multi-frame command → the device sees a corrupted command → `0x6e00/0x6d00/0x6700`-class errors or no reply → `SendApduTimeoutError("Abort timeout")` if you set `abortTimeout`, otherwise a hang. wallet-cli classifies `ReceiverApduError`/`UnknownDeviceExchangeError` as "timeout" with the comment "Transport framing errors (garbled APDU). Surfaced as timeout since root cause is typically lock / busy and the fix is the same: retry." **VERIFIED** classification [S28], scenario **INFERRED**.
- With LLD open but **idle** (no device flow on screen), nothing is sent on its handle, so your process may work fine — which is exactly why "it worked yesterday" bugs appear. **INFERRED** from §1.2.

### 3.4 "cannot open device with path" is macOS, not Windows

- node-hid maintainer Julusian (#552, 2024-11-25): "macos only allows one open handle to a hid device at a time. windows does not have the same limitation. So if you already have the hid device open, or another application has opened the hid device, you will not be able to open it." (#547): "On windows, I am pretty sure that it is always opened in non-exclusive mode and there is no way to change that." **VERIFIED** [S29]
- ledgerjs #439 (gre, 2020): "this issue definitely happen if the usb connection has been acquired by another software / the device has been opened by another app like Ledger Live. … As soon as someone open() and do not close(), that error will happen on a second open() attempt. but that does not prevent to list devices." — reporter was on macOS Catalina. **VERIFIED** [S30]
- On Windows the DMK node-hid sender's only open-time errors are `Error("Missing device path")` / `Error("Error while opening device")` (no retry, no try/catch around `HIDAsync.open`), wrapped as `OpeningConnectionError`. **VERIFIED** [S22]

### 3.5 Does Ledger document "close Ledger Live first"?

- developers.ledger.com: **No.** Checked `ai-tools/ledger-cli` (no "Ledger Live", "close", "busy", "driver", "HID", "WebUSB"; only "Supported platforms: macOS, Linux, Windows (WSL recommended)"), `ai-tools/ledger-dmk-skills` (nothing about Windows/Node/transports beyond "WebHID only runs in Chromium-based browsers, on localhost or HTTPS, and requires a user gesture"), `dmk-ts/integration/how_to/transports` (package table + snippets, no platform notes), `dmk-ts/integration/how_to/dmk` (mentions `isRefresherDisabled`, `pollingInterval`, locked/busy states only), node-hid transport README ("tested successfully on Node v20", nothing else). **VERIFIED absence** [S31][S32][S33][S34][S35]
- support.ledger.com: yes, for third-party wallets. "Using dapps and third-party wallets" (360026472413) tells users to close all other applications including Ledger Wallet; the USB troubleshooting article (115005165269) asks to "fully close all applications and browser extensions" and names MetaMask/Daedalus/MEW as interferers; the Phantom guide says "ensure the Ledger Wallet app is closed". **SNIPPET** [S16]
- Nothing anywhere states *why* (shared vs exclusive handle), and nothing distinguishes Windows from macOS. **Gap worth putting in the DX-feedback write-up.**

---

## 4. Transport packages on Windows (versions as of 2026-10-10)

### 4.1 `@ledgerhq/device-transport-kit-node-hid@1.0.1`

- Published deps: `node-hid ^3.2.0`, `usb ^2.16.0`, `uuid 11.0.3`, `purify-ts 2.1.0`; peers `@ledgerhq/device-management-kit ^1.2.0`, `rxjs 7.8.2`. No `engines`. **VERIFIED** [S36]
- CHANGELOG 1.0.1: "Filter Ledger HID devices to the APDU interface on macOS and Windows to prevent stalls when multiple HID interfaces are exposed" (PR #1399). 1.0.0: "Add Node HID Transport Kit … uses node-hid library (usb)". **VERIFIED** [S37]
- `NodeHidTransport.ts`: discovery via `devicesAsync()`, filter `vendorId === 0x2c97`, and on `darwin`/`win32` **`usagePage === 0xffa0`**; dedup by `vendorId:productId`; model via `productId >> 8`; hotplug via node-usb `usb.on("attach"/"detach")` (no timers); `OpeningConnectionError` on connect failure; `NoAccessibleDeviceError` if `devicesAsync` throws. **VERIFIED** [S38]
- `NodeHidApduSender.ts`: `HIDAsync.open(path, { nonExclusive: true })`, `on("data")` reads, writes `Buffer.from([0x00, ...frame])` (65 bytes), 300 ms `setTimeout` before reopen "make sure the device is opened on the OS level", random channel, optional `abortTimeout` → `SendApduTimeoutError("Abort timeout")`. **VERIFIED** [S22]
- Hotplug on Windows via libusb: `usb@2.16.0` bundles libusb **1.0.27**, `usb@2.17.0` → 1.0.29, `usb@2.18.0`/`2.19.1` → **1.0.30**, whose ChangeLog (2026-05-17) says "Add hotplug support on Microsoft Windows". With `^2.16.0` a fresh install resolves to 2.19.1, so attach/detach events should fire natively; an older lockfile pinning <2.18 means libusb falls back to polling (`usb.pollHotplug` exists "Force polling loop for hotplug events"). **VERIFIED** versions [S39], behaviour on <1.0.30 **INFERRED**.
- Known DMK GitHub issues with "windows": none about HID/transport; #946 is a Windows 11 + Nano S Plus reporter hitting a `signDelegationAuthorization` TypeError (not transport). **VERIFIED** [S40]

### 4.2 `node-hid` 3.x on Windows

- Registry: 3.0.0 2023-11-29, 3.1.0 2024-05-31, 3.1.1 2024-10-21 (**prebuilds missing**, #549), 3.1.2 2024-10-22, 3.2.0 2025-06-03 (adds `nonExclusive`), 3.3.0 2026-02-02, **3.4.0 2026-07-18**. **VERIFIED** [S41][S42]
- 3.4.0 `package.json`: `engines.node >=10.16`, deps `node-addon-api ^8.9.0`, `pkg-prebuilds ^1.1.0`, `binary.napi_versions [4]`, install script `pkg-prebuilds-verify ./binding-options.js || node-gyp rebuild`. **VERIFIED** [S43]
- 3.4.0 tarball ships prebuilds: `HID-win32-x64`, `HID-win32-ia32`, **`HID-win32-arm64`**, darwin x64/arm64, linux x64/arm64/arm (+musl, +hidraw). All `node-napi-v4.node`. **VERIFIED** [S20]
- N-API v4 binaries load on Node 22/24 without rebuild ("Existing add-ons can continue to run without recompilation using an earlier version of Node-API"). The one reported Node 22 failure (#557) was a `prebuild-install`/`napi-build-utils` bug in a *downstream* package that still used node-hid 2.1.2 — fixed by pinning `napi-build-utils@2.0.0`; maintainer: "the current builds do work with node v22.14". **VERIFIED** [S44]
- README is stale: lists "Node v10 to Node v20", "Electron v3 to v24", Windows build toolchain "Python 2.7 … windows-build-tools" with an explicit "slightly stale" note. Ignore; if a rebuild ever triggers you need VS Build Tools C++ workload + Python 3 (node-gyp). **VERIFIED** staleness [S21], toolchain **INFERRED**.
- Windows limitations in README: only OS-owned keyboards/mice/Xbox pad; nothing about exclusivity. **VERIFIED** [S21]
- Legacy stack for reference: `@ledgerhq/hw-transport-node-hid@6.33.5` → `node-hid 2.1.2` + `usb 2.9.0`; `hw-transport-node-hid-noevents@6.36.0` → `node-hid 2.1.2`. These are the versions that hit the Node 22 prebuild bug. Avoid. **VERIFIED** [S45]

### 4.3 wallet-cli (Agent Stack) device layer on Windows

- `apps/wallet-cli/src/device/register-dmk-transport.ts`: registers exactly one module, `MODULE_ID = "wallet-cli-dmk-webusb"`; no platform/env switch; "The session refresher is disabled in wallet-cli: short-lived command sessions otherwise race refresher APDUs against explicit disconnect/reopen cycles. If the initial session state is BUSY we disconnect and ask the user to retry." Comments also warn of a "parked transferIn" after SIGINT that can keep the process alive. **VERIFIED** [S46]
- `NodeWebUsbTransport.ts`: node-usb `getDeviceList()` → `WebUSBDevice`; picks the interface whose alternate has `interfaceClass === 255`; on `win32` starts `setInterval(..., WINDOWS_WEBUSB_DISCOVERY_POLL_INTERVAL_MS)` with the constant's comment "Windows hotplug can miss late WebUSB attach notifications; rescan periodically as a fallback." (1000 ms); `LEDGER_WEBUSB_CONFIGURATION_VALUE = 1`, `LEDGER_WEBUSB_ENDPOINT_NUMBER = 3`, `RECONNECT_DEVICE_TIMEOUT_MS = 6000`. Errors: `NoAccessibleDeviceError("No Ledger WebUSB device found")`, `DeviceNotRecognizedError("Device not recognized: WebUSB productId: 0x…")`, `OpeningConnectionError`. **VERIFIED** [S47][S48]
- `apps/wallet-cli/package.json` pins **`usb: 2.17.0`** (libusb 1.0.29 → no native Windows hotplug; hence the poll). Published `@ledgerhq/wallet-cli` is 2.9.0. **VERIFIED** [S49]
- Because it drives the WinUSB-bound vendor interface, wallet-cli does **not** contend with LLD's HID handle at the OS level — but the *device* still processes one APDU stream; concurrent LLD HID traffic and wallet-cli WebUSB traffic interleave inside the firmware. Same rule: close Ledger Wallet. **INFERRED**
- Failure signature if WinUSB did *not* bind (e.g. S mode, group policy blocking driver install): libusb `LIBUSB_ERROR_NOT_SUPPORTED` on open/claim → surfaces as `OpeningConnectionError`; Device Manager shows the second interface with a yellow bang. **INFERRED** from [S14].

---

## 5. Python tooling on Windows (ledgerblue, ledgerctl)

- **`hidapi` (PyPI) 0.15.0, 2025-12-09**: binary wheels `cp312/cp313/cp314-win_amd64` (+ win32, + cp314t), sdist only as fallback; no `win_arm64` seen (page truncated). hidapi's Windows backend is statically compiled in → no `hidapi.dll` to ship. **VERIFIED** wheels [S50], static-link **INFERRED**.
- **`ledgerblue` 0.1.58 (2026-06-23)**, `requires-python >=3.8`, deps: `pyelftools`, `hidapi>=0.7.99`, `protobuf>=5.28,<6`, `pycryptodomex`, `future`, `ecpy`, `pillow`, `python-u2flib-host`, `websocket_client`, **`nfcpy>=1.0.4`**, **`bleak>=0.20.1`**, `pycryptodome`, `python-gnupg`, `pyserial`. Optional `smartcard` extra → `pyscard`. PyPI page: Windows listed as supported OS, no Windows notes, recommends a venv "to avoid hidapi issues", prerequisites `libudev-dev libusb-1.0-0-dev` are Linux build deps only. **VERIFIED** [S51][S52]
  - `comm.py` imports `hid` **and `nfc`** at module import; `nfc/clf/transport.py` does `import usb1 as libusb` at import time and raises `ImportError("missing usb1 module, try 'pip install libusb1'")` if absent. `libusb1` 3.4.0 Windows wheels bundle `libusb-1.0.dll` 1.0.29 ("installing wheels from pypi also installs the libusb dll within the usb1 python module"), and since 2.0.0 it does "not load the C library on import". So the chain resolves with wheels only. **VERIFIED** chain [S26][S53][S54], end-to-end import success **INFERRED**.
  - `getDongle()`: `hid.enumerate(0, 0)`, `vendor_id == 0x2C97` and (`interface_number == 0` **or** `usage_page == 0xFFA0`), `open_path`, `set_nonblocking(True)`; `LEDGER_PROXY_USB_PORT` env override; `CommException("No dongle found")`. No platform branches. **VERIFIED** [S26]
  - Windows history: #42 (2018, Win10 PowerShell) got as far as device status `6985` → HID path worked; #11 (2017, Win10) a crypto bug; **#83 (2021) WSL → "No dongle found"**. No "pip install fails on Windows" issue found. **VERIFIED** [S55]
- **`ledgerwallet` 0.10.0 (2026-04-08) = `ledgerctl`**, `requires-python >=3.9`, deps `click>=8.0 construct>=2.10 cryptography>=2.5 ecdsa hidapi intelhex Pillow protobuf>=5.28,<6 requests tabulate toml`; no pyusb. Install note: on Debian "HIDAPI compiles from source" — not applicable with Windows wheels. `transport/hid.py`: `hid.enumerate(0x2C97, 0)`, same `interface_number == 0 or usage_page == 0xFFA0` filter, fixed channel `0x0101`, asserts on header. **VERIFIED** [S25][S56]
- `pyscard` (for `PCSC=1` NFC via a PC/SC reader) is optional; Windows has the WinSCard API in-box so pyscard wheels work without pcsclite. **INFERRED** (not researched further; out of scope).

---

## 6. Day-1 Windows checklist (each step: tag + failure signature)

Run native Windows (PowerShell), not WSL.

| # | Step | Tag | Failure signature to look for |
|---|---|---|---|
| 0 | **Quit Ledger Wallet/Live completely** (tray icon too) before any custom transport. Re-open it only to install device apps, then quit again. | SNIPPET (Ledger support) + VERIFIED mechanics §3 | Random `ReceiverApduError`, APDU responses with wrong length/status, `SendApduTimeoutError("Abort timeout")`, device "busy" state, or commands that work only sometimes. Historic string: `Invalid channel`. |
| 1 | Plug the device, unlock, stay on dashboard. Open Device Manager → **Human Interface Devices**: expect a "HID-compliant vendor-defined device" (+ "USB Input Device"); **Universal Serial Bus devices**: expect a WinUSB device for the vendor interface. | VERIFIED descriptors §2 / INFERRED names | Yellow bang on either node, or device under "Other devices" → driver install blocked (S mode, policy, Windows Update driver download disabled). Ledger: S mode is unsupported. |
| 2 | Confirm Node ≥ 20 x64 (`node -p "process.versions.napi + ' ' + process.arch"`). | VERIFIED prebuild matrix §4.2 | `arch = arm64`: node-hid has a win32-arm64 prebuild but Ledger Wallet does not support Windows arm64; wallet-cli has no arm64 binary. |
| 3 | `npm i @ledgerhq/device-management-kit @ledgerhq/device-transport-kit-node-hid` in an empty folder and check **no node-gyp output** scrolls by. | VERIFIED install script §4.2 | Lines containing `node-gyp rebuild`, `MSBuild`, `gyp ERR!`, `Could not find any Visual Studio installation`. Fix: `npm ls node-hid usb` must show `node-hid 3.x` + `usb ≥2.18`; nuke lockfile if it pinned 2.1.2; as a last resort install VS Build Tools (C++ workload). |
| 4 | Smoke test with the snippet below (no Ledger Live running). Expect one device, `usagePage 0xffa0`, model from `productId >> 8` (`0x50` S Plus, `0x70` Flex). | VERIFIED filter §4.1 | `devicesAsync()` lists **two** `0x2c97` entries with different `usagePage` → you're in a FIDO/Passwords app or the U2F interface is on; go back to dashboard. Zero entries → step 1. |
| 5 | Open the Ethereum app on the device *while listening*: expect `detach` then `attach` within ≤6 s and the same `deviceId` reused. | VERIFIED `RECONNECT_DEVICE_TIMEOUT` §2.3 | No `attach` event ever → old `usb` (<2.18, libusb <1.0.30) without Windows hotplug; upgrade `usb` or poll `devicesAsync()` every 1 s like wallet-cli does. |
| 6 | If you use **wallet-cli**: `npm i -g @ledgerhq/wallet-cli`, run a read-only command, with Ledger Wallet closed. | VERIFIED code §4.3 / INFERRED outcome | `No Ledger WebUSB device found` → WinUSB not bound (step 1) or device in bootloader/locked; `Device not recognized: WebUSB productId` → new model byte; hang on Ctrl+C → the documented parked `transferIn`, kill the process. |
| 7 | **Python**: `py -3.12 -m venv .venv; .\.venv\Scripts\pip install ledgerblue ledgerwallet`, then `python -c "import hid,nfc,ledgerblue.comm,ledgerwallet"`. Expect wheels only, no compiler. | VERIFIED wheels §5 / INFERRED success | `error: Microsoft Visual C++ 14.0 or greater is required` → a dep fell back to sdist (check which: `pip download --no-deps`); `ImportError: missing usb1 module` → `pip install libusb1`; `CommException: No dongle found` → Ledger Wallet open? wrong interface? WSL? |
| 8 | Never run two of your own tools at once against the device (DMK app + ledgerctl, two DMK processes, Speculos is exempt). | VERIFIED §3.3 | ledgerctl: `AssertionError` in `transport/hid.py read()`. DMK: as step 0. |
| 9 | Don't install Zadig / libusb-win32 / UsbDk. If someone already did on this PC: Device Manager → the Ledger WinUSB/HID node → Uninstall device + "delete driver", replug. | VERIFIED no Ledger source needs it §2.2 | `LIBUSB_ERROR_NOT_SUPPORTED` / `LIBUSB_ERROR_ACCESS` from node-usb, or HID interface shown as "WinUsb Device" (means the APDU HID interface was hijacked → node-hid sees nothing). |

### Smoke-test snippet (Node, DMK node-hid) — adapted from the DMK transports doc + `NodeHidTransport.ts`

```ts
// smoke.mts  — run with: node smoke.mts   (Node 22+, ESM)
import { DeviceManagementKitBuilder, ConsoleLogger } from "@ledgerhq/device-management-kit";
import { nodeHidTransportFactory } from "@ledgerhq/device-transport-kit-node-hid";
import { devicesAsync } from "node-hid";

const ledgerHid = (await devicesAsync()).filter(d => d.vendorId === 0x2c97);
console.table(ledgerHid.map(d => ({ path: d.path, productId: d.productId.toString(16),
  model: (d.productId >> 8).toString(16), usagePage: d.usagePage?.toString(16), iface: d.interface })));
// Expect exactly one row with usagePage 'ffa0' on the dashboard.

const dmk = new DeviceManagementKitBuilder()
  .addTransport(nodeHidTransportFactory)
  .addLogger(new ConsoleLogger())
  .build();

dmk.listenToAvailableDevices({}).subscribe(async devices => {
  if (!devices.length) return;
  const sessionId = await dmk.connect({ device: devices[0],
    sessionRefresherOptions: { isRefresherDisabled: true } }); // like LLD & wallet-cli
  const res = await dmk.sendApdu({ sessionId,
    apdu: new Uint8Array([0xb0, 0x01, 0x00, 0x00, 0x00]), // GET_APP_AND_VERSION (dashboard: "BOLOS")
    abortTimeout: 10_000 });
  console.log("status", Buffer.from(res.statusCode).toString("hex"), "data", Buffer.from(res.data).toString("hex"));
  await dmk.disconnect({ sessionId }); process.exit(0);
});
```
(`sendApdu`/`connect` option names are as read in the LLD/wallet-cli call sites; the `GET_APP_AND_VERSION` APDU bytes are the long-standing BOLOS command and were **not** re-verified in this pass — INFERRED.)

### PowerShell one-liners for triage (no install)

```powershell
# Which Windows drivers bound to the Ledger (VID 2C97)?
Get-PnpDevice | Where-Object InstanceId -like 'USB\VID_2C97*' | Select Status,Class,FriendlyName,InstanceId
Get-PnpDevice | Where-Object InstanceId -like 'HID\VID_2C97*' | Select Status,Class,FriendlyName,InstanceId
# Is Ledger Wallet/Live still running?
Get-Process | Where-Object { $_.ProcessName -match 'Ledger' } | Select ProcessName,Id,Path
```
(Expected classes: `HIDClass` for the APDU interface, `USBDevice` for the WinUSB interface — INFERRED from §2.2.)

---

## 7. Gaps, contradictions, things to raise in the DX-feedback write-up

- **Contradiction:** `ai-tools/ledger-cli` says "Windows (WSL recommended)" while the package ships a native `windows-x64` Bun binary and the source has Windows-specific WebUSB polling; USB in WSL2 needs usbipd and Ledger's own loader issue #83 shows "No dongle found" under WSL. Recommend native Windows. **VERIFIED** both halves [S31][S47][S55]
- **Gap:** no Ledger developer doc explains that Ledger Wallet must be closed, or that on Windows the failure mode is cross-talk rather than an open error. The DMK receiver's lack of a channel check makes this worse than the legacy `hid-framing` which at least threw "Invalid channel". **VERIFIED** [S27]
- **Gap:** `@ledgerhq/device-transport-kit-node-hid` README says only "tested successfully on Node v20"; no Windows/udev/Electron guidance. **VERIFIED** [S35]
- **Gap:** `node-hid` README version matrix is stale (Node ≤20, Electron ≤24); reality is N-API v4 prebuilds incl. win32-arm64. **VERIFIED** [S21][S20]
- **Unread:** the firmware code that ORs the interface bitfield into the PID low byte; the U2F/CCID/KBD descriptor files; LLD's live-common device polling cadence; ledgerblue's `unwrapResponseAPDU` behaviour on foreign frames; the full text of support article 115005165269 (SPA; only snippets).
- **Not reproducible from sources:** whether Windows 11 24H2/25H2 shows "Setting up a device" delays on each PID change (would add seconds to app-open flows). Test on Day 1 with a stopwatch.
- **Rate-limit note:** GitHub search API was exhausted mid-run; `LedgerHQ/device-sdk-ts` "windows" search covered only the first page (10 of 60, all dependabot/CI noise). **VERIFIED partial** [S40]

---

## Sources

- [S1] https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/ledger-live-desktop/package.json
- [S2] https://github.com/LedgerHQ/ledger-live/blob/develop/apps/ledger-live-desktop/src/main/window-lifecycle.ts (read via GitHub contents API)
- [S3] https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/libs/live-dmk-desktop/src/hooks/useDeviceManagementKit.tsx
- [S4] https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/pnpm-workspace.yaml
- [S5] GitHub code search `repo:LedgerHQ/ledger-live hw-transport-node-hid-singleton` (via `gh search code`) — no hits in apps/ledger-live-desktop
- [S6] https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/libs/live-dmk-desktop/src/transport/DeviceManagementKitTransport.ts
- [S7] https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/device-management-kit/src/internal/device-session/data/DeviceSessionRefresherConst.ts and .../model/DeviceSessionRefresher.ts
- [S8] https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/lib_stusb/src/usbd_ledger_hid.c
- [S9] https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/lib_stusb/src/usbd_ledger_webusb.c
- [S10] https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/lib_stusb/src/usbd_ledger.c
- [S11] https://unpkg.com/@ledgerhq/devices/src/index.ts
- [S12] https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/automatic-installation-of-winusb
- [S13] https://github.com/LedgerHQ/ledgerjs/issues/4
- [S14] https://raw.githubusercontent.com/node-usb/node-usb/master/README.md
- [S15] https://support.ledger.com/article/115005165269-zd (SPA; body unavailable — snippets via web search), https://support.ledger.com/article/4403310017041-zd (system requirements), https://support.ledger.com/article/4405741700881-zd (S mode)
- [S16] https://support.ledger.com/article/360026472413-zd (third-party wallets; snippet), https://support.ledger.com/article/4408131265169-zd (Phantom; snippet)
- [S17] https://github.com/LedgerHQ/ledgerjs/issues/430
- [S18] https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/node-hid/src/api/data/NodeHidConfig.ts ; https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/web-hid/src/api/data/WebHidConfig.ts
- [S19] https://raw.githubusercontent.com/libusb/hidapi/master/windows/hid.c
- [S20] npm tarball of node-hid@3.4.0 (`npm view node-hid@3.4.0 dist.tarball`), listed `package/prebuilds/*`, `package/hidapi/VERSION`, `package/hidapi/windows/hid.c` lines 350–355
- [S21] https://raw.githubusercontent.com/node-hid/node-hid/master/README.md
- [S22] https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/node-hid/src/api/transport/NodeHidApduSender.ts
- [S23] https://raw.githubusercontent.com/chromium/chromium/main/services/device/hid/hid_service_win.cc (and hid_connection_win.cc, which receives already-open handles)
- [S24] https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/hidsdi/nf-hidsdi-hidd_setnuminputbuffers ; https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/obtaining-hid-reports ; https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/opening-hid-collections
- [S25] https://raw.githubusercontent.com/LedgerHQ/ledgerctl/master/ledgerwallet/transport/hid.py
- [S26] https://raw.githubusercontent.com/LedgerHQ/blue-loader-python/master/ledgerblue/comm.py
- [S27] https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/device-management-kit/src/internal/device-session/service/DefaultApduReceiverService.ts
- [S28] https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/device/classify-device-error.ts
- [S29] https://github.com/node-hid/node-hid/issues/552 ; https://github.com/node-hid/node-hid/issues/547
- [S30] https://github.com/LedgerHQ/ledgerjs/issues/439
- [S31] https://developers.ledger.com/docs/ai-tools/ledger-cli
- [S32] https://developers.ledger.com/docs/ai-tools/ledger-dmk-skills
- [S33] https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/transports.md
- [S34] https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/dmk
- [S35] https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/node-hid/README.md
- [S36] `npm view @ledgerhq/device-transport-kit-node-hid@1.0.1 dependencies peerDependencies` ; https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/node-hid/package.json ; device-sdk-ts `pnpm-workspace.yaml` catalog (`node-hid: ^3.2.0`, `usb: ^2.16.0`, `rxjs: 7.8.2`)
- [S37] https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/node-hid/CHANGELOG.md
- [S38] https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/node-hid/src/api/transport/NodeHidTransport.ts
- [S39] `npm view usb time`; npm tarballs usb@2.16.0 / 2.17.0 / 2.18.0 / 2.19.1 → `package/libusb/libusb/version.h`, `package/libusb/ChangeLog` ; https://raw.githubusercontent.com/libusb/libusb/master/ChangeLog
- [S40] https://api.github.com/search/issues?q=repo:LedgerHQ/device-sdk-ts+windows (first 10 of 60) ; https://github.com/LedgerHQ/device-sdk-ts/issues/946 ; `gh search issues --repo LedgerHQ/device-sdk-ts node-hid`
- [S41] `npm view node-hid time` ; https://registry.npmjs.org/node-hid
- [S42] https://github.com/node-hid/node-hid/issues/549 ; https://api.github.com/repos/node-hid/node-hid/releases/latest (v3.4.0, 2026-07-18, "fix: update build for Node.js v21+ compatibility")
- [S43] https://raw.githubusercontent.com/node-hid/node-hid/master/package.json ; https://raw.githubusercontent.com/node-hid/node-hid/master/binding-options.js
- [S44] https://github.com/node-hid/node-hid/issues/557
- [S45] `npm view @ledgerhq/hw-transport-node-hid dependencies` ; `npm view @ledgerhq/hw-transport-node-hid-noevents dependencies` ; https://unpkg.com/@ledgerhq/hw-transport-node-hid/README.md
- [S46] https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/device/register-dmk-transport.ts ; .../wallet-cli-dmk-transport.ts
- [S47] https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/device/node-webusb/NodeWebUsbTransport.ts
- [S48] https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/device/node-webusb/node-webusb-constants.ts
- [S49] https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/package.json ; `npm view @ledgerhq/wallet-cli version`
- [S50] https://pypi.org/project/hidapi/#files
- [S51] https://pypi.org/project/ledgerblue/
- [S52] https://raw.githubusercontent.com/LedgerHQ/blue-loader-python/master/pyproject.toml
- [S53] https://raw.githubusercontent.com/nfcpy/nfcpy/master/src/nfc/clf/transport.py
- [S54] https://pypi.org/project/libusb1/
- [S55] https://api.github.com/search/issues?q=repo:LedgerHQ/blue-loader-python+windows (#83, #42, #11)
- [S56] https://pypi.org/project/ledgerwallet/ ; https://raw.githubusercontent.com/LedgerHQ/ledgerctl/master/pyproject.toml
- Also consulted, no Windows content: https://github.com/LedgerHQ/ledger-live/issues/4964 (WebHID disconnect on openApp/quitApp — confirms re-enumeration on app open/close from a WebHID user's perspective)
