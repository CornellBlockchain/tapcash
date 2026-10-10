# Gap check: Ledger Flex over Web Bluetooth from Chrome/Edge on Windows 11

Research note for the N3XT hackathon (deadline 2026-10-13 23:59 CEST). Written 2026-10-10. No hardware touched, nothing installed; the only local actions were read-only version/driver queries on this PC.

Legend: **VERIFIED** = read in a primary source (LedgerHQ GitHub source/PRs, npm registry, Chromium source, Ledger docs). **INFERRED** = derived from verified facts, or from a search-engine snippet of a page I could not load. **UNVERIFIED** = nobody has shown it working.

---

## 0. Verdict

**Go, but only with a 15-minute smoke test on Day 1 and USB-C as the committed fallback.** Nothing I found says "Flex + Chrome + Windows is broken"; nothing I found shows it working either. The code path is real and used by Ledger's own sample app, but three Windows-specific facts raise the risk from "should work" to "must test first":

1. **The Flex demands an authenticated (MITM, bonded) link before it will accept or emit a single APDU** (firmware source, VERIFIED, section 3.1). Pairing is not optional.
2. **Chrome/Edge on Windows refuse to perform the Flex's pairing kind (numeric comparison) unless a flag is on.** `kWebBluetoothConfirmPairingSupport` is `FEATURE_DISABLED_BY_DEFAULT` on Win/Linux in current Chromium `main`, and the WinRT pairing code returns `ERROR_AUTH_FAILED` for `ConfirmPinMatch` when that feature is off (VERIFIED, section 3.2). Consequence: **either pre-pair the Flex in Windows Settings > Bluetooth, or enable `chrome://flags/#enable-web-bluetooth-confirm-pairing-support`.** Expect the chooser alone to fail with "GATT Error: Not paired" / "Connection failed for unknown reason" (INFERRED from Chromium source + three independent Windows reports).
3. **DMK's automatic reconnect depends on `navigator.bluetooth.getDevices()` and `watchAdvertisements()`, which are still behind `#enable-web-bluetooth-new-permissions-backend` on Chrome** (VERIFIED, section 4). Without the flag the transport throws `Device not found` in its reconnect loop and the session dies on any link drop (e.g. opening an app reboots the BLE link). Enable the flag or plan for a manual re-select.

The host itself is fine: Windows 11 build 26200, Chrome 153.0.8010.53, Edge 154.0.4258.62, Realtek USB Bluetooth adapter present and `OK` (VERIFIED locally, section 8). Known local caveat: this adapter has a history of losing its link-key store after selective suspend (memory note); a BLE bond that silently vanishes would reproduce exactly the "device not found" symptom.

If the smoke test fails for more than 30 minutes, drop BLE. USB-C WebHID/node-hid on the Flex is the verified path from the other notes, the touchscreen reads the same on video, and nobody on the jury will miss the cable.

---

## 1. The package: `@ledgerhq/device-transport-kit-web-ble`

VERIFIED (npm registry `time` field, `package.json`, `src/api/index.ts`, `WebBleTransport.ts` on `develop`):

| Item | Value |
|---|---|
| Latest | **1.3.2**, published 2026-01-09. Earlier: 1.0.0 (2025-01-27), 1.1.0 (2025-03-11), 1.2.0 (2025-09-11), 1.3.0 (2025-11-12), 1.3.1 (2025-12-12). |
| Peer deps (1.3.2) | `@ledgerhq/device-management-kit ^1.0.0`, `rxjs 7.8.2` (exact) |
| Deps | `uuid 11.0.3`, `purify-ts 2.1.0`, `@sentry/minimal 6.19.7` |
| Description | `> [!CAUTION] This is still under development and we are free to make new interfaces which may lead to breaking changes.` |
| Exports | `webBleIdentifier`, `WebBleTransport`, `webBleTransportFactory`, plus `./model/Errors` |
| **Transport identifier** | **`export const webBleIdentifier: TransportIdentifier = "WEB-BLE-RN-STYLE";`** (line 37 of `WebBleTransport.ts`). Not `"WEB-BLE"`. Import it, never hardcode it. |
| `isSupported()` | `typeof navigator !== "undefined" && !!navigator.bluetooth` |

The changelog (no dates in the file; dates above are from npm) says, verbatim: 1.0.0 "Fix Chrome windows ble connect"; 1.2.0 "Implement DeviceConnectionStateMachine in webBLE"; 1.3.0 "Use BLE advertised name as connected device name"; 1.3.1 "Breaking change: Replace TransportDeviceModel.blockSize by dynamic getBlockSize"; 1.3.2 "Add second set of Bluetooth identifiers for Nano Gen5". Nothing mentions Flex, Stax, pairing, GATT caching or "device not found".

The "Fix Chrome windows ble connect" (PR #637, merged 2025-01-27, a rebase of #537/#535 "Fix ble connection on windows") is smaller than it sounds. The whole transport change is:

```diff
-            await bleDevice.forget();
+            this._logger.error("Error while discovering device", { data: { error, bleDevice } });
+            if (bleDevice.forget) {
+              await bleDevice.forget();
+            }
```

(twice: in the discovery error path and the connect error path). The #537 description says the Windows connection "threw an error" and "calling the BLE device forget method resolves it". So the only Windows-specific bug Ledger ever recorded for this transport was a crash in an error handler, fixed before 1.0.0. VERIFIED (PR diff + PR bodies via GitHub API).

### Ledger GATT service UUIDs (VERIFIED, `packages/device-management-kit/src/api/device-model/data/StaticDeviceModelDataSource.ts`)

| Device | serviceUuid | notify (`-0001-`) | write (`-0002-`) | writeCmd (`-0003-`) |
|---|---|---|---|---|
| Nano X | `13d63400-2c97-0004-0000-4c6564676572` | `...-0004-0001-...` | `...-0004-0002-...` | `...-0004-0003-...` |
| Stax | `13d63400-2c97-6004-0000-4c6564676572` | `...-6004-0001-...` | `...-6004-0002-...` | `...-6004-0003-...` |
| **Flex** | **`13d63400-2c97-3004-0000-4c6564676572`** | `13d63400-2c97-3004-0001-4c6564676572` | `13d63400-2c97-3004-0002-4c6564676572` | `13d63400-2c97-3004-0003-4c6564676572` |
| Nano Gen5 (`APEX`, productName "Ledger Nano Gen5") | `13d63400-2c97-8004-0000-...` and a second set `13d63400-2c97-9004-0000-...` (bootloader quirk, PR #1212) | | | |

The suffix `4c6564676572` is ASCII "Ledger". Flex USB product id is `0x70`, bootloader `0x0007`. The transport builds `requestDevice({ filters: [{services:[uuid]}, ...one per UUID], optionalServices: [all UUIDs] })` from this table, so the Chrome chooser shows only Ledger devices and identifies the model from the service UUID that answers `getPrimaryService`.

---

## 2. What the transport does, step by step (VERIFIED from `WebBleTransport.ts`, 642 lines, `develop`)

**Discovery** (`startDiscovering()`): must be called from a user gesture (Web Bluetooth rule). Calls `navigator.bluetooth.requestDevice(...)` as above, then `_identifyLedgerGattService`: `gatt.connect()` with a 6000 ms timeout, sleep 150 ms, `getPrimaryService(uuid)` trying the last-successful UUID first and falling back to `getPrimaryServices()` with case-insensitive matching, then `gatt.disconnect()` and sleep 200 ms. Emits one `TransportDiscoveredDevice { id, deviceModel, transport: "WEB-BLE-RN-STYLE", name }`. `stopDiscovering()` is a no-op. **Service discovery does not require pairing**, so this step is expected to pass on an unpaired Windows PC.

**Connect** (`connect({deviceId, onDisconnect, onReconnect})`): `gatt.connect()` (6 s timeout), `_getPrimaryLedgerGattService`, `_resolveLedgerServiceCharacteristics` (notify = `notifyUuid`; write = `writeCmdUuid` if it has `writeWithoutResponse`/`write`, else `writeUuid`), builds a `WebBleApduSender`, wraps it in `DeviceConnectionStateMachine` with `RECONNECT_DEVICE_TIMEOUT = 15000`, registers a `gattserverdisconnected` listener, then `setupConnection()` (starts notifications and sends the MTU/handshake frames). **This is the first operation that touches an authenticated characteristic**, so this is where an unpaired Windows host fails (section 3).

**Reconnect** (`_tryToReconnect`): loop: `_rediscoverPermittedDevice` (returns `null` immediately if `navigator.bluetooth.getDevices` is not a function; otherwise matches by `device.id`, then `_waitForAdvertisementInRange` using `watchAdvertisements` with `ADVERTISING_DELAY = 400`, `ADVERTISING_TIMEOUT = 1200`), wrapped in `REDISCOVER_TIMEOUT = 3000`; `if (!rediscoveredDevice) throw new Error("Device not found")`; on success `gatt.connect()`, re-resolve service and characteristics, `setDependencies`, `setupConnection`, `eventDeviceConnected`, call `onReconnect`. On any failure: disconnect, sleep `RECONNECTION_LOOP_BACKOFF = 500`, retry until the state machine's 15 s timer fires and `onTerminated` -> `onDisconnect`.

Error classes you will see: `UnknownDeviceError`, `DeviceAlreadyConnectedError`, `OpeningConnectionError` (GATT timeouts, missing service/characteristic, `SecurityError` with the hint `Add it to optionalServices in requestDevice()`), `GeneralDmkError`; and plain `Error("Device not found")` / `Error("No GATT on device")` inside the reconnect loop (logged, not surfaced).

A detail from PR #853 (web-ble "Fix connection and reconnection and implemented DeviceConnectionStateMachine", DSDK-715) that matters for a demo: "when we launch the requested app, it drops the BLE link immediately, no status-word is delivered"; Web Bluetooth surfaces `DeviceDisconnectedWhileSendingError`, which the transport converts into a synthetic `9000` when the caller flagged `triggersDisconnection=true`. In other words **opening the Ethereum app over BLE always goes through the reconnect path**, so section 4 is not an edge case, it is the main flow. VERIFIED (PR body).

---

## 3. Does the Flex need to be paired in Windows first?

### 3.1 The firmware side: yes, pairing is mandatory and it is numeric comparison (VERIFIED, `LedgerHQ/ledger-secure-sdk` `lib_blewbxx/src/ble_ledger.c` and `ble_ledger_profile_apdu.c`, `master`)

```c
// ble_ledger.c
case BLE_INIT_STEP_SET_IO_CAPABILITIES:
    ble_aci_gap_forge_cmd_set_io_capability(&ble_ledger_data.cmd_data, BLE_GAP_IO_CAP_DISPLAY_YES_NO);
...
case BLE_INIT_STEP_SET_AUTH_REQUIREMENTS: {
    data.bonding_mode = BLE_GAP_BONDING_ENABLED;
    data.mitm_mode    = BLE_GAP_MITM_PROTECTION_REQUIRED;
    data.sc_support   = 1;
    data.use_fixed_pin = BLE_GAP_USE_FIXED_PIN_FOR_PAIRING_FORBIDDEN;
```

```c
// ble_ledger_profile_apdu.c: notify, write and write-cmd characteristics all carry
data.security_permissions = BLE_GATT_ATTR_PERMISSION_AUTHEN_WRITE;
data.enc_key_size         = BLE_GAP_MAX_ENCRYPTION_KEY_SIZE;
// and APDU traffic is gated on
&& (handle->notifications_enabled) && (handle->link_is_encrypted)
```

Pairing UX is `ask_user_pairing_numeric_comparison(code)` showing a `"%06d"` code on the device (under `HAVE_INAPP_BLE_PAIRING`). This matches the Ledger support flow ("compare the code shown on your phone with the one on the Flex ... tap Yes, they match"; "The pairing persists in your global smartphone settings", support article 360019138694 "Set up Bluetooth connection", via search snippet, INFERRED for exact wording). So: **DisplayYesNo + MITM required + bonding** = LE Secure Connections numeric comparison. On Windows this surfaces as `DevicePairingKinds_ConfirmPinMatch`.

Side effect for the demo: Ledger OS updates reset the pairing table ("the pairing with Ledger Wallet mobile will be reset by this OS update", Flex OS release notes via search snippet, INFERRED). If you update the Flex firmware mid-week, re-pair.

### 3.2 The Chromium side on Windows: the chooser does not pair by itself (VERIFIED, Chromium `main`)

- `content/browser/bluetooth/README.md`, "Secure Characteristics": "pairing will be initiated during a read/write operation. Some operating system Bluetooth implementations (like macOS and Android) do this transparently for the application. Other OS's (like Windows and Linux/BlueZ) need to explicitly pair when a read/write fails due to an authentication error."
- `web_bluetooth_service_impl.cc`: under `#if PAIR_BLUETOOTH_ON_DEMAND()`, a failed `startNotifications` triggers `pairing_manager_->PairForCharacteristicStartNotifications` only when `error_code == GattErrorCode::kNotAuthorized && !device->IsPaired()`; the read path also accepts `kNotPaired`. (INFERRED consequence: if WinRT reports the CCCD write as "not paired" rather than "not authorized", the notification path returns the error without even attempting pairing. This would explain the raw "GATT Error: Not paired" reports below.)
- `device/base/features.cc`: `kWebBluetoothConfirmPairingSupport` ("Controls whether Web Bluetooth should support confirm-only and confirm-PIN pairing mode on Win/Linux") is `base::FEATURE_DISABLED_BY_DEFAULT`.
- `device/bluetooth/bluetooth_pairing_winrt.cc`, `OnPairingRequested`: for `DevicePairingKinds_ConfirmPinMatch`, if the feature is off it logs `"is not enabled by enable-web-bluetooth-confirm-pairing-support"` and runs the callback with `ConnectErrorCode::ERROR_AUTH_FAILED`. Only `ProvidePin` works unconditionally.
- `chrome/browser/about_flags.cc`: `enable-web-bluetooth-confirm-pairing-support` exists for `kOsDesktop` on Win/Linux; `chrome/browser/flag-metadata.json` gives it `expiry_milestone: 166`, i.e. it is still a flag in the Chrome 153 era, not launched.
- Electron issue #33111 (closed 2022-09-26) is the clearest end-to-end account: errors "GATT error: Not paired." and "NetworkError: Connection failed for unknown reason."; Chromium bug 1309715 "added confirm-only pairing support, which reached Chrome 105.0.5195.68 behind the #enable-web-bluetooth-confirm-pairing-support flag"; working fix `--enable-features=WebBluetoothConfirmPairingSupport`; and "Electron initially failed unless the device was first paired through the OS." Electron's `session` docs: "When a handler is not defined, any pairing on Linux or Windows that requires additional validation will be automatically cancelled." VERIFIED (issue page + docs page).
- Nimiq `@nimiq/ledger-api` `transport-comparison.md` (Nano X, Web Bluetooth): Windows "Works pretty well", but "Pairing through the browser device selector did not work. Pairing had to be done upfront through the OS", "needs to be done only once", and the Web Bluetooth permission "lasts only until the device disconnects or the page reloads". VERIFIED (document read). Date of that test unknown; it predates the confirm-pairing flag.
- chromium.org web-bluetooth group, Apr 2022 (Jack Hsieh, Chromium): `startNotifications()` -> "NetworkError: Connection failed for unknown reason", suspected bug 1271239 which "requires a certain pairing mode that our web bluetooth on Windows might not properly support yet"; workaround "Pair the device in Windows settings before using Web Bluetooth". VERIFIED (thread read).
- W3C implementation-status.md: "On-demand device pairing" is checked only for Android and Mac, blank for Windows. Windows GATT support since Chrome 70 on Windows 10 1703+; Edge "Supported as of version 79". VERIFIED.

### 3.3 Practical answer

Two routes, both INFERRED to work for the Flex (each is verified for *some* BLE device on Windows, neither has a Flex report):

**Route A (no browser flags): pair in Windows first.** Flex: Settings > Bluetooth, enabled. Windows: Settings > Bluetooth & devices > Add device > Bluetooth > pick "Ledger Flex" (the advertised name; renameable on the device). Windows shows a 6-digit code, the Flex shows the same, confirm on both. Then in Chrome click Connect: the chooser lists the (now bonded) Flex, GATT operations go through on the encrypted link. This is the Nimiq and Debian-blog flow ("I simply selected the wallet's name in Debian's Bluetooth settings, and confirmed the code on the Ledger and the laptop"). Bond is stored in Windows; the Ledger support text for phones ("does not have to be confirmed again until you forget the device") INFERRED to apply.

**Route B: flags.** `chrome://flags/#enable-web-bluetooth-confirm-pairing-support` = Enabled (Edge: `edge://flags/...` same name, INFERRED since Edge inherits Chromium flags). Then Chrome's chooser pick -> DMK `connect()` -> first authenticated op fails with not-authorized -> Chrome shows its own "confirm PIN" prompt -> confirm on the Flex. Route B is less tested (flag off by default for four years for a reason) and the pairing prompt is Chrome UI, not OS UI. Use Route A for the demo; try Route B only out of curiosity.

Either way: **also enable `chrome://flags/#enable-web-bluetooth-new-permissions-backend`** (section 4), and do the whole thing with Ledger Wallet desktop closed and the Flex unlocked.

If the Flex ever gets into a half-paired state: Flex Settings > Bluetooth > remove pairings (the firmware has `BLE_INIT_STEP_CLEAR_PAIRING` -> `aci_gap_clear_security_db`), and Windows "Remove device". That is also the fix Ledger gave for the 2019 Nano X web-ble `NotSupportedError: GATT operation failed for unknown reason` (ledgerjs #352: "Reset Pairings on the NanoX and forget on the phone/computer side").

---

## 4. `getDevices()` / `watchAdvertisements()` are flag-gated, so auto-reconnect is degraded by default (VERIFIED)

- `content/public/common/content_features.cc`: `kWebBluetoothNewPermissionsBackend` is `FEATURE_DISABLED_BY_DEFAULT`; comment: "When enabled, WebBluetoothWatchAdvertisements and WebBluetoothGetDevices blink features are also enabled."
- `about_flags.cc`: `enable-web-bluetooth-new-permissions-backend` for `kOsAndroid | kOsDesktop`; `flag-metadata.json` expiry 166.
- MDN BCD `api/Bluetooth.json`: `getDevices` Chrome `version_added: "85"` behind a flag; Edge mirrors Chrome.

Effect on DMK: `_rediscoverPermittedDevice` returns `null` -> `Error("Device not found")` every 500 ms until the 15 s `RECONNECT_DEVICE_TIMEOUT` -> `onDisconnect`. Since opening an app drops the link (section 2), **without this flag every `OpenAppDeviceAction` over BLE ends the session**. With the flag, Chrome also remembers the permission across reloads (persistent device permissions), which is what makes `listenToAvailableDevices()` useful on a second page load. The transport's `_publishDiscoveredDevices` only knows devices picked in this page session otherwise (the Nimiq note "permission lasts only until ... the page reloads" is the pre-flag behaviour).

Demo implication: enable the flag on the demo machine, or structure the demo so the Ethereum app is already open before you connect (`skipOpenApp: true` on signer calls, as Orchestra does) so no app-switch reboot happens mid-session.

---

## 5. Issue tracker sweep

Searches run via GitHub API (authenticated `gh`) on 2026-10-10. VERIFIED.

- `repo:LedgerHQ/device-sdk-ts bluetooth` -> 18 results, all PRs or unrelated issues. Relevant PRs: #221 "Connect to Ledger Ble Device" (2024-08), #637 Windows fix (2025-01), #853 web-ble reconnection + state machine (2025-05), #1005 "Web ble device connection io revamp" (merged 2025-09-10), #966 definitive BLE ids for Apex (2025-08), #1212 second Gen5 id set (2026-01). **Zero open or closed issues about web-ble, Windows, pairing, GATT caching, reconnect or "device not found".** `repo:LedgerHQ/device-sdk-ts ble is:issue` -> 2 results, neither about BLE transport (#1773 is status word 0x6901 on Nano X via any transport; #1067 is a peer-dep conflict).
- `repo:LedgerHQ/ledger-live bluetooth windows is:issue` -> 0. `"web bluetooth"` -> 11, all Renovate/tsconfig PRs plus #6746/#6465 (below). `hw-transport-web-ble is:issue` -> 6: #6746 and #6465 "`@ledgerhq/hw-transport-web-ble` throws error on Transport.create()" (Chrome 122, Nano X, `Failed to execute 'stopNotifications' ... GATT Server is disconnected`, OS not stated, never fixed, closed by stale bot 2025-03-14); #4958 BLE disconnect throws without calling listeners (2023). These are the legacy ledgerjs transport, which ledger-live **deleted** in PR #19124 "Sunset unused legacy transports" (merged 2026-06-30; removed `hw-transport-web-ble`, `hw-transport-webhid`, `hw-transport-webusb`, `hw-transport-node-hid*`, `react-native-hw-transport-ble`, ...; "Their last published versions remain on npm"). Do not start from `@ledgerhq/hw-transport-web-ble`.
- `repo:LedgerHQ/ledgerjs web-ble` -> 15 (2018-2021): #352 Android `NotSupportedError` (Ledger: firmware bug, reset pairings, "<50 apps"); a bystander in that thread: "It worked well in Win 10 chrome"; #648 same `stopNotifications` after disconnect; #293 "Create a Bluetooth transport that works in Electron" (open since 2019: no Node/Electron BLE, consistent with the other notes); #368 "Document current web ble support & tradeoffs" (closed, pointed at implementation-status.md and caniuse).
- Global `hw-transport-web-ble windows chrome is:issue` -> 0.

Chromium side (not Ledger-specific): bug 960258 (Windows PIN pairing, fixed by Chromium 96), 1309715 (confirm pairing, flag, Chrome 105), 1271239 (pairing mode unsupported on Windows, 2022), 1120338 (why `kNewBLEGattSessionHandling` on Windows is disabled). `kUncachedGattDiscoveryForGattConnection` is `ENABLED_BY_DEFAULT` on Windows, so stale GATT caches on connect are already mitigated. VERIFIED (features.cc).

---

## 6. Does Ledger Wallet desktop on Windows do Bluetooth? No.

- Support article 360019138694 "Set up Bluetooth connection" (last updated 2025-03-10 per snippet): "Bluetooth pairing with a desktop is currently not available." The same article is what Ledger's site returns for Flex pairing searches; the page is JS-rendered and could not be fetched, so wording is from search snippets. INFERRED that it covers Flex/Stax/Gen5 as well as Nano X; VERIFIED that Ledger's shop copy says "Bluetooth (BLE 5.2) for any smartphone (iOS or Android)" and lists USB-C "for desktop use".
- `apps/ledger-live-desktop/package.json` (develop) depends on `@ledgerhq/device-transport-kit-speculos` and `@ledgerhq/hw-transport` only; no `web-ble`, no `node-hid` BLE. GitHub code search `repo:LedgerHQ/ledger-live device-transport-kit-web-ble filename:package.json` -> 0 files. The 2026 desktop connect-device work (#19055 "add connect device flow": "WebHID discovery"; #22599 marks Bluetooth error screens "(mobile)") is HID-only. VERIFIED.
- Also: ledgerjs #293 (open since 2019) asks for an Electron BLE transport; none exists in DMK either (no Node BLE transport in `packages/transport/`). VERIFIED.

So Ledger's own desktop app will not interfere with or help a BLE demo; it only matters for USB (close it so it does not hold the HID interface).

---

## 7. Community and hackathon evidence for Flex/Nano X BLE from a Windows browser

| Project | What they actually did | OS/browser evidence | Verdict |
|---|---|---|---|
| **Orchestra** (Cannes 2026, youssef-jeddi/Orchestra) | `frontend/package.json` and root `package.json`: `@ledgerhq/device-transport-kit-web-ble ^1.3.2`, DMK ^1.2.0, signer-eth ^1.13.0. `frontend/src/lib/ledger.js` and `src/integrations/ledger/dmk.ts` register **only** `webBleTransportFactory`; signer calls use `skipOpenApp: true`. README: "Ledger Device Management Kit (DMK) for browser-based BLE connection", prerequisite "A Ledger hardware wallet (Nano S/X) with Bluetooth" (sic; Nano S has none). | No OS or browser named. The author is on Ledger's Agent Stack shop page as an early tester. | Browser BLE via DMK **works somewhere** (most likely macOS/Nano X). Not Windows evidence. VERIFIED (source), OS INFERRED. |
| **ITHACA** (ETHOnline 2026 3rd, chrsnikhil/ithaca) | `guardian/package.json` lists both `web-ble ^1.3.2` and `web-hid ^1.2.4`; README "USB and Bluetooth signing through the Ledger Device Management Kit (WebHID and Web-BLE)" and "Open ... in desktop Chrome or Edge, arm on your Ledger over USB or Bluetooth". **But** `guardian/app/lib/useLedgerMandate.ts` only imports and registers `webHidTransportFactory`. | "desktop Chrome or Edge", OS not stated. | BLE claimed in README, **not wired in the code I read**. Treat as USB-only evidence. VERIFIED. |
| **Chapter 2** (ETHOnline 2026, maxiggle/ethonline-2026) | "connect a Ledger (Nano X / Flex) over Bluetooth in Approvals" in the **Android app**; web console is WebHID. | Mobile BLE only. | Not browser BLE. VERIFIED (README). |
| **Amulet** (ETHOnline 2026) | ESP32-S3 pendant talks to a **Nano X over BLE** directly. | No browser, no Windows. | Irrelevant to Web Bluetooth. VERIFIED (prior-art note). |
| **Nimiq ledger-api** transport-comparison (Nano X, Web Bluetooth) | Windows: works after OS pairing; chooser pairing fails; Linux experimental; Android Chrome pairing failed. | Windows, Chrome. | **Only Windows + Nano X + Web Bluetooth report found.** Positive, with OS pre-pairing. VERIFIED. |
| neilzone.co.uk (Nano X, Debian 11) | Paired via OS Bluetooth settings with code confirmation; "I've not yet used it over Bluetooth." | Linux. | Pairing flow confirmation only. VERIFIED. |
| Ledger's own `apps/sample` (device-sdk-ts) | `transportConfig.ts` default factories `[webHidTransportFactory, webBleTransportFactory]`, UI label "Select a BLE device". | Ledger QA presumably runs it on macOS; no Windows statement anywhere in the repo. | Ledger ships and dogfoods browser BLE. OS coverage unknown. VERIFIED (source). |
| Ledger legacy tutorial (ledgerjs web-bluetooth) | "works only with a Ledger Nano X", "select your Nano X in the browser popup, and confirm the pairing request", defers browser support to caniuse. No OS named. | None. | Ledger has never published a Windows statement for BLE. VERIFIED. |

**Net: zero reports of a Flex (or Stax) over Web Bluetooth from any desktop browser, on any OS, from anyone other than Ledger's unspecified internal testing.** The closest is Orchestra (Nano X?, unknown OS) and Nimiq (Nano X, Windows, pre-paired). Flex-specific BLE differences from Nano X in DMK are only the UUID row; the firmware BLE stack (`lib_blewbxx`) is shared. INFERRED: what works for Nano X on Windows works for Flex.

---

## 8. This host (read-only checks, 2026-10-10, VERIFIED locally)

- OS: Windows 11 Enterprise 10.0.26200 (well past the 1703 minimum).
- Chrome 153.0.8010.53 (`C:\Program Files\Google\Chrome\Application`), Edge 154.0.4258.62. Both far above Chrome 70/Edge 79.
- Bluetooth: "Realtek Bluetooth Adapter", status OK, `USB\VID_0BDA&PID_5852`. No Ledger devices currently in the Bluetooth PnP tree (never paired here).
- Known quirk of this exact adapter (memory note `project_bluetooth_audio_wedge.md`): BTHUSB event 18 "cannot store link keys on the local adapter" after selective-suspend resume; power-management registry fix applied 2026-09-01. BLE/GATT "keeps working" in that failure mode, but a lost link key would make the Flex look unpaired to Windows while the Flex still thinks it is bonded -> re-pair both sides if the Chrome chooser suddenly cannot connect after a sleep/resume.
- Not installed/checked: nothing. Do not install anything to test this; a static HTML page served over `localhost` is enough (section 9).

---

## 9. Day-1 smoke test (15 minutes, no project code)

Serve the DMK sample app or a 40-line page over `http://localhost` (secure-context rule: localhost counts). Minimal page:

```ts
import { DeviceManagementKitBuilder, ConsoleLogger } from "@ledgerhq/device-management-kit";
import { webBleTransportFactory, webBleIdentifier } from "@ledgerhq/device-transport-kit-web-ble";
import { webHidTransportFactory } from "@ledgerhq/device-transport-kit-web-hid";
import { firstValueFrom } from "rxjs";

const dmk = new DeviceManagementKitBuilder()
  .addLogger(new ConsoleLogger())
  .addTransport(webHidTransportFactory)
  .addTransport(webBleTransportFactory)
  .build();

document.getElementById("ble")!.onclick = async () => {          // user gesture required
  const device = await firstValueFrom(dmk.startDiscovering({ transport: webBleIdentifier })); // "WEB-BLE-RN-STYLE"
  const sessionId = await dmk.connect({ device });                // first authenticated GATT op happens here
  console.log("connected", sessionId, device.deviceModel.id);     // expect "flex"
};
```

Order of operations:
1. Flex: Settings > Bluetooth on; device unlocked; Ethereum app already open (avoids the app-switch link drop).
2. Ledger Wallet desktop closed.
3. **Route A**: Windows Settings > Add device > "Ledger Flex" > confirm matching 6-digit code on both. Then click the page button.
4. Chrome flags to set regardless: `#enable-web-bluetooth-new-permissions-backend` Enabled (reconnect + persistent permission). Optional Route B: `#enable-web-bluetooth-confirm-pairing-support`.
5. Diagnostics if it fails: `chrome://device-log` with only "Bluetooth" ticked at Debug level (Reilly Grant's standard ask); `chrome://bluetooth-internals`. Look for `ERROR_AUTH_FAILED`, "not enabled by enable-web-bluetooth-confirm-pairing-support", `GATT_NOT_PAIRED`.
6. Success criteria: `connect()` resolves, `getDeviceSessionState` reports Ethereum app, a `getAddress` round-trips. Then pull the USB cable mid-session and confirm nothing else changes. Then test a `signTypedData` end-to-end over BLE.
7. Time-box: 30 min. Failure -> switch to `webHidTransportFactory` (same code, `transport: webHidIdentifier`) and never look back. Pitch line unchanged ("Ledger confirms; the agent proposes"), hardware story unchanged (Flex touchscreen on camera).

---

## 10. Gaps and contradictions

- **No primary source anywhere states Flex + Web Bluetooth + Windows works.** Everything above is an argument from code, not a report.
- Ledger's BLE guide for Flex/Stax says LedgerJS needs "transport libraries v8.3.0 or later" while npm `hw-transport-web-ble` tops out at 6.35.0 and the package was deleted from the monorepo in June 2026. Stale doc; ignore LedgerJS entirely.
- Whether Windows reports an unauthenticated CCCD write as `kNotAuthorized` (pairing attempted) or `kNotPaired` (pairing not attempted on the notifications path) is not verified. Route A sidesteps it.
- Whether the Flex re-advertises when bonded to a PC that is out of range, and whether Windows auto-reconnects a bonded BLE peripheral behind Chrome's back (interfering with DMK's own `gatt.connect()`), is untested.
- Ledger support article wording is from search snippets (JS-rendered site; Zendesk API path returned HTML). Flex OS release notes likewise.
- Edge is assumed identical to Chrome (same Chromium flags); implementation-status only says Edge "Supported as of version 79".
- `@sentry/minimal` dependency in the transport conflicts with `tslib` in some bundlers (device-sdk-ts #919, open) - not Windows-specific, but a Day-1 install hazard.

---

## 11. Sources

Ledger / DMK
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/web-ble/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/web-ble/CHANGELOG.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/web-ble/package.json
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/web-ble/src/api/index.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/web-ble/src/api/transport/WebBleTransport.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/web-ble/src/api/data/WebBleConfig.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/device-management-kit/src/api/device-model/data/StaticDeviceModelDataSource.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/device-management-kit/src/api/device-model/model/BleDeviceInfos.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/device-management-kit/src/api/device-model/data/DeviceModelDataSource.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/apps/sample/src/providers/DeviceManagementKitProvider/transportConfig.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/apps/sample/package.json
- https://github.com/LedgerHQ/device-sdk-ts/pull/637 (+ .diff), https://github.com/LedgerHQ/device-sdk-ts/pull/537, /535, /641
- https://github.com/LedgerHQ/device-sdk-ts/pull/853, /1005, /1212, /966, /221
- https://github.com/LedgerHQ/device-sdk-ts/issues/1773, /1067, /919
- https://registry.npmjs.org/@ledgerhq/device-transport-kit-web-ble and /1.3.2
- https://developers.ledger.com/docs/device-interaction/beginner/ble_flex_stax.md
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/transports.md
- https://developers.ledger.com/docs/device-interaction/dmk-ts/ledgerjs/integration/web-application/web-bluetooth.md
- https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/lib_blewbxx/src/ble_ledger.c
- https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/lib_blewbxx/src/ble_ledger_profile_apdu.c
- https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/lib_blewbxx/src/ble_cmd.c
- https://github.com/LedgerHQ/ledger-live/pull/19124 (+ files), /19055, /22599, /22765
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/ledger-live-desktop/package.json
- https://github.com/LedgerHQ/ledger-live/issues/6746, /6465, /4958
- https://github.com/LedgerHQ/ledgerjs/issues/352, /368, /648, /293
- https://support.ledger.com/article/360019138694-zd (snippet only), https://support.ledger.com/article/Ledger-Flex-OS-release (snippet only), https://support.ledger.com/article/360021488913-zd (snippet only)
- https://shop.ledger.com/products/ledger-flex (snippet)

Chromium / Web Bluetooth
- https://raw.githubusercontent.com/chromium/chromium/main/content/browser/bluetooth/README.md
- https://raw.githubusercontent.com/chromium/chromium/main/content/browser/bluetooth/web_bluetooth_service_impl.cc
- https://raw.githubusercontent.com/chromium/chromium/main/content/browser/bluetooth/web_bluetooth_pairing_manager_impl.cc
- https://raw.githubusercontent.com/chromium/chromium/main/device/bluetooth/bluetooth_pairing_winrt.cc
- https://raw.githubusercontent.com/chromium/chromium/main/device/bluetooth/bluetooth_device_winrt.cc
- https://raw.githubusercontent.com/chromium/chromium/main/device/bluetooth/bluetooth_remote_gatt_characteristic_winrt.cc
- https://chromium.googlesource.com/chromium/src/+/main/device/base/features.cc
- https://raw.githubusercontent.com/chromium/chromium/main/content/public/common/content_features.cc
- https://chromium.googlesource.com/chromium/src/+/main/chrome/browser/about_flags.cc
- https://raw.githubusercontent.com/chromium/chromium/main/chrome/browser/flag-metadata.json
- https://developer.chrome.com/docs/capabilities/bluetooth
- https://raw.githubusercontent.com/WebBluetoothCG/web-bluetooth/main/implementation-status.md
- https://raw.githubusercontent.com/mdn/browser-compat-data/main/api/Bluetooth.json
- https://github.com/electron/electron/issues/33111
- https://www.electronjs.org/docs/latest/api/session (setBluetoothPairingHandler)
- https://groups.google.com/a/chromium.org/g/web-bluetooth/c/1mXfl3q3Wws
- https://issues.chromium.org/issues/1309715 (sign-in wall; number cited via Electron thread)

Community / hackathon
- https://github.com/youssef-jeddi/Orchestra (README, package.json, frontend/package.json, frontend/src/lib/ledger.js, src/integrations/ledger/dmk.ts, src/integrations/ledger/safeswarm-ledger.md)
- https://github.com/chrsnikhil/ithaca (README, guardian/package.json, guardian/app/lib/useLedgerMandate.ts, ledger-broker/SUBMISSION.md)
- https://github.com/maxiggle/ethonline-2026 (README)
- https://cdn.jsdelivr.net/npm/@nimiq/ledger-api@4.0.0/transport-comparison.md
- https://neilzone.co.uk/2021/12/setting-up-a-ledger-nano-x-with-debian-11/
- Local: research/prior-art-hackathon-projects.md, research/device-capabilities-nfc-ble.md, research/dmk-ts-signer.md, research/dmk-skills.md; ~/.claude/projects/C--Users-sahas/memory/project_bluetooth_audio_wedge.md
