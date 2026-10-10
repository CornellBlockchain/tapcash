# Spike: DMK Node USB path on Windows 11 / Node 24 without a compiler

Question: do `@ledgerhq/device-management-kit` + `@ledgerhq/device-transport-kit-node-hid` + `@ledgerhq/device-signer-kit-ethereum` install and load on Windows 11 x64 / Node 24.2 / npm 12.2 with **no** Visual Studio Build Tools, and does a discovery script run and exit cleanly with no device?

**Verdict: YES for install, native-module load and no-device discovery.** Device-connected path is written but untested (no Ledger plugged in during the spike).

Date: 2026-10-10. Host: Windows 11 Enterprise 10.0.26200, Node v24.2.0 (`process.versions.napi=10`, x64, ABI 137), npm 12.2.0. Ledger Wallet/Live not running. No Ledger has ever been enumerated on this Windows install (see section 3).

## 1. Install (sequential, one package per `npm install`)

```
mkdir spikes/node-hid-windows && cd spikes/node-hid-windows
npm init -y                      # then set "type":"module", "private":true
npm install --foreground-scripts --no-fund --no-audit @ledgerhq/device-management-kit          > install-1-dmk.log
npm install --foreground-scripts --no-fund --no-audit @ledgerhq/device-transport-kit-node-hid  > install-2-node-hid.log
npm install --foreground-scripts --no-fund --no-audit @ledgerhq/device-signer-kit-ethereum     > install-3-signer-eth.log
```

Results (all exit 0; 20 s / 5 s / 11 s):

```
added 23 packages in 20s
added 7 packages in 5s
npm warn install-scripts 2 packages had install scripts blocked because they are not covered by allowScripts:
npm warn install-scripts   node-hid@3.4.0 (install: pkg-prebuilds-verify ./binding-options.js || node-gyp rebuild)
npm warn install-scripts   usb@2.19.1 (install: node-gyp-build)
npm warn install-scripts Run `npm install-scripts ls` to review, or `npm install-scripts approve <pkg>` to allow.
npm warn deprecated crypto-js@4.2.0: Active development of CryptoJS has been discontinued. This library is no longer maintained.
added 17 packages in 11s
```

**No node-gyp ran.** `grep -i "gyp ERR|MSBuild|Visual Studio|gyp info" install-*.log` matches nothing; the only "node-gyp" strings are npm quoting the script names inside its warning.

Resolved versions (`npm ls @ledgerhq/device-management-kit @ledgerhq/device-transport-kit-node-hid @ledgerhq/device-signer-kit-ethereum node-hid usb rxjs`):

```
+-- @ledgerhq/device-management-kit@1.11.0
+-- @ledgerhq/device-signer-kit-ethereum@1.18.1
|   (+ @ledgerhq/context-module@2.6.0, device-contacts-kit@0.5.0, signer-utils@1.3.0)
`-- @ledgerhq/device-transport-kit-node-hid@1.0.1
    +-- node-hid@3.4.0
    +-- rxjs@7.8.2
    `-- usb@2.19.1
```

### npm 12 `allowScripts` gate (new pitfall, not in the research notes)

npm 12 blocks native install scripts by default. The prebuilds ship inside the tarballs, so **both modules load even with the scripts blocked**:

```
> node -e "const h=require('node-hid'); console.log('node-hid OK', typeof h.devicesAsync)"
node-hid OK function
> node -e "const u=require('usb'); console.log('usb OK', typeof u.getDeviceList, 'libusb hotplug:', u.usb && typeof u.usb.on)"
usb OK function libusb hotplug: function
```

Prebuild files present: `node_modules/node-hid/prebuilds/HID-win32-x64/node-napi-v4.node`, `node_modules/usb/prebuilds/win32-x64/node.napi.node`.

Approving the scripts and forcing them to run also succeeds without a compiler:

```
> npm install-scripts approve node-hid usb        # writes package.json "allowScripts": {"node-hid@3.4.0": true, "usb@2.19.1": true}
> npm install --foreground-scripts                # "up to date in 2s" (scripts do NOT re-run on an already-installed tree)
> npm rebuild node-hid usb --foreground-scripts
npm notice run node-hid@3.4.0 install
npm notice run pkg-prebuilds-verify ./binding-options.js || node-gyp rebuild
npm notice run usb@2.19.1 install
npm notice run node-gyp-build
rebuilt dependencies successfully
```

`pkg-prebuilds-verify` passed, so the `|| node-gyp rebuild` fallback never fired.

## 2. Scripts

### `discover.mjs` (`node discover.mjs` or `npm run discover`) - works with no device

Creates DMK with `nodeHidTransportFactory`, lists raw `node-hid` Ledger interfaces (VID 0x2c97), calls `startDiscovering()` once, then `listenToAvailableDevices()` for 10 s, then `dmk.close()` and `process.exit(0)`.

Run with no device (exit 0, 12 s wall):

```
node-hid raw: 0 Ledger HID interface(s)
DMK 1.11.0
[NodeHidTransport] Error while getting accessible device {
  error: { _tag: 'NoAccessibleDeviceError', originalError: {}, err: 'No selected device' }
}
startDiscovering -> NoAccessibleDeviceError: No selected device
listenToAvailableDevices: watching 10 s (plug/unplug a Ledger to see it)...
  2026-10-10T05:50:38.131Z none
closed; exiting 0
```

Behaviour learned:
- On node-hid, `startDiscovering()` is a **one-shot** "pick the first device"; with nothing plugged in it errors `NoAccessibleDeviceError` immediately and the transport logs the error at Error level even when discovery is expected to find nothing. Use `listenToAvailableDevices({})` for a CLI or agent that waits for a device.
- `dmk.close()` alone does not end the process (the libusb hotplug thread keeps the event loop alive); call `process.exit()`.

### `connect-and-get-address.mjs` (`node connect-and-get-address.mjs [path]` or `npm run address`) - needs a device; only `node --check` passed

Waits up to 60 s via `listenToAvailableDevices`, `dmk.connect({ device })`, waits out `DeviceStatus.LOCKED`, then `new SignerEthBuilder({ dmk, sessionId }).build().getAddress("44'/60'/0'/0/0", { checkOnDevice: false })`, prints `address` and `publicKey`, then `disconnect`, `close`, exit 0. Errors print `_tag` / `message` / `originalError` and exit 1.

### Plain-Node ESM pitfall (the first run of discover.mjs failed)

```
Error [ERR_UNSUPPORTED_DIR_IMPORT]: Directory import '...\node_modules\@ledgerhq\device-management-kit\lib\esm\src' is not supported resolving ES modules imported from ...\lib\esm\index.js
```

Cause: every `@ledgerhq/*` package's `"import"` export condition points at an ESM build with extensionless specifiers (`lib/esm/index.js` is literally `export*from"./src"`). That resolves only under a bundler or `tsx`, never under `node x.mjs`. `@ledgerhq/device-transport-kit-node-hid` maps `"import"` to its CJS build, so it alone is fine. Fix used here: `const require = createRequire(import.meta.url)` and `require("@ledgerhq/...")`; the CJS builds are correct. Alternatives: write `.cjs` files, or run via `npx tsx`.

## 3. Windows drivers (no device needed)

```
> pnputil /enum-drivers | Select-String '2c97','ledger'          -> 0 hits (1386 lines scanned)
> Get-PnpDevice | ? InstanceId -match 'VID_2C97'                 -> nothing (includes non-present devices: a Ledger has never been enumerated on this install)
> Get-Process | ? ProcessName -match 'Ledger'                    -> nothing (Ledger Wallet/Live not running)
> dir C:\Windows\System32\drivers\hidclass.sys, hidusb.sys, winusb.sys
hidclass.sys 327680   9/8/2026
hidusb.sys    81920   9/8/2026
winusb.sys   143360   9/8/2026
```

No Ledger-specific driver is in the driver store and none is needed: the APDU interface is standard HID (`hidclass.sys`, in-box) and the WebUSB interface auto-binds `winusb.sys` via MS OS 2.0 descriptors (see `research/gap-windows-hid-coexistence-ledger-live.md` section 2). Nothing was installed; no Zadig.

## 4. Pass / fail

| Check | Result |
|---|---|
| `npm install` x3 on Node 24 / npm 12 with no Build Tools | PASS, no node-gyp |
| `require('node-hid')` / `require('usb')` load prebuilt binaries | PASS (node-hid 3.4.0 N-API v4, usb 2.19.1 with libusb hotplug) |
| Install scripts forced via `npm rebuild`, still no compile | PASS |
| `discover.mjs` loads DMK, runs 10 s, prints `none`, exits 0 | PASS |
| `connect-and-get-address.mjs` | WRITTEN, `node --check` ok, **not run** (no device) |
| Plain `import` of `@ledgerhq/*` under Node ESM | FAIL (`ERR_UNSUPPORTED_DIR_IMPORT`), worked around with `createRequire` |
| Ledger drivers pre-installed | none; in-box HID + WinUSB present, which is all that is required |

## 5. Next steps when a device is plugged in

1. Quit Ledger Wallet completely (tray icon too). Plug in, unlock, stay on the dashboard.
2. `cd spikes/node-hid-windows && node discover.mjs`. Expect `node-hid raw: 1 Ledger HID interface(s)` with `usagePage=0xffa0` and model `0x50` (Nano S Plus) or `0x70` (Flex), then `startDiscovering -> <name>` and the same device in the watch list. Unplug and replug during the 10 s to confirm libusb hotplug fires on Windows (usb 2.19.1 = libusb 1.0.30).
3. `node connect-and-get-address.mjs`. getAddress opens the Ethereum app itself (device asks to open it if on the dashboard; the app launch re-enumerates USB and DMK tolerates ~6 s). Expect `address 0x...`. Then flip `checkOnDevice: true` as the first on-device-approval test.
4. Device Manager sanity: HID node should be "HID-compliant vendor-defined device" under HIDClass, WinUSB node under "Universal Serial Bus devices". If the HID node shows as "WinUsb Device", someone ran Zadig: uninstall device + delete driver, replug.
5. Repeat step 3 with Ledger Wallet open to observe the frame-interleaving failure mode from the research note (expected `ReceiverApduError` / timeouts), since a demo may run alongside it.
6. If `connect` fails with `OpeningConnectionError` and two 0x2c97 HID rows appear with different `usagePage`, the device is in a FIDO/Passwords app; return to the dashboard.

## Files

- `discover.mjs`, `connect-and-get-address.mjs`, `package.json` (`npm run discover`, `npm run address`), `package-lock.json`, `.gitignore`
- `install-1..6*.log`, `discover-run.log` - verbatim output
