# Ledger Device Management Kit (DMK) TypeScript + Signer kits — research note

> **Correction (2026-10-10, source audit).** All in-repo signer kits are on npm (l.15, l.43; Tron is `device-signer-kit-tron`); rn-hid/rn-ble/mockserver versions are known (l.32-33); only GenuineCheck/Install/ListInstalled/Uninstall need the secure channel (l.108); `withAddressBook` exists (l.129); BLE id is `WEB-BLE-RN-STYLE` (l.185); Cardano GET_SERIAL does fingerprint a device, unauthenticated (l.70); the Speculos command needs `-p/--pki-prod` to clear-sign with prod CAL (l.243). See `source-audit.md` §2 (M04, M05) and §5.

Date: 2026-10-10. Scope: `@ledgerhq/device-management-kit` and friends (monorepo `LedgerHQ/device-sdk-ts`, branch `develop`). Target: hackathon build on Windows 11 with a Nano S Plus (USB only) and a Flex (USB + BLE + NFC), 3 days left.

Legend: **VERIFIED** = read in a primary source (Ledger docs page, repo source, npm registry). **INFERRED** = reasoned from sources / general knowledge, not read verbatim.

---

## TL;DR for the hackathon

- DMK is Ledger's current TS SDK; LedgerJS (`hw-transport-*`, `hw-app-*`) is deprecated and will stop working with the Ethereum app in Sept 2026 (EIP-712 change). Use DMK. **VERIFIED** (migration guide).
- Runs in **browser (Chromium only, WebHID / Web Bluetooth)**, **Node.js (node-hid, USB only)**, React Native, and against the **Speculos** emulator over HTTP. **VERIFIED** (transports doc + READMEs).
- **No NFC transport exists in DMK.** Flex NFC is documented only for Ledger Recovery Key and Security Key (FIDO). Idea #2 ("NFC ledger-to-ledger") is not buildable with the public SDK. **VERIFIED** (repo tree has zero "nfc" paths; Ledger shop lists NFC for Recovery Key/Security Key only).
- Both devices are supported: `DeviceModelId` enum = `nanoS, nanoSP, nanoX, stax, flex, apexp`. **VERIFIED** (source). Nano S Plus = USB only, so WebHID or node-hid. Flex adds Web BLE in the browser.
- Signer kits published on npm: **Ethereum 1.18.1, Bitcoin 1.3.3, Solana 1.13.3, Hyperliquid 1.1.0, Zcash 0.7.1, ICP 0.2.0**; in-repo but unverified on npm: aleo, concordium, cosmos, polkadot, trx, xrp. **VERIFIED** (npm registry, 2026-10-10).
- ETH signer ops: `getAddress`, `signTransaction`, `signMessage` (personal_sign), `signTypedData` (EIP-712), `signDelegationAuthorization` (EIP-7702), `verifySafeAddress`. **VERIFIED** (README).
- Every op returns `{ observable, cancel }`; observable emits `DeviceActionState` with status `not-started | pending | stopped | completed | error`; `pending` carries `intermediateValue.requiredUserInteraction` (what the human must do on-device) and, for sign flows, a `step`. **VERIFIED** (source + README).
- Clear Signing metadata flows: context-module (HTTP to Ledger CAL `https://global.api.prd.ledger.com/cal/v1`) -> `ClearSignContext[]` -> `Provide*Command` APDUs to the Ethereum app before `SignTransactionCommand`. Works without `originToken` for basic things (ERC-20 etc.); **Transaction Check and "full" clear signing need an `originToken` from Ledger's partner program**. **VERIFIED** (for-wallets doc, context-module source, migration troubleshooting table).
- Windows-specific: node-hid transport 1.0.1 filters HID interfaces by usage page `0xffa0` on win32/darwin (fix for stalls). node-hid 3.4.0 ships prebuilds (N-API 4) for Windows x64. Speculos on Windows = Docker only. Web Bluetooth works in Chrome/Edge on Windows 10+ (INFERRED).

---

## 1. Package map (npm, latest as of 2026-10-10) — VERIFIED via registry.npmjs.org

| Package | Latest | Published | Peer deps / notes |
|---|---|---|---|
| `@ledgerhq/device-management-kit` | 1.11.0 | 2026-10-06 | peer `rxjs@7.8.2`; deps xstate 5.19.2, inversify 7.5.1, purify-ts, ws/isomorphic-ws, @noble/hashes. Exports ESM + CJS (`lib/esm`, `lib/cjs`). |
| `@ledgerhq/device-transport-kit-web-hid` | 1.2.4 | 2026-06-16 | peer dmk ^1.7.0 |
| `@ledgerhq/device-transport-kit-web-ble` | 1.3.2 | 2026-01-09 | peer dmk ^1.0.0 |
| `@ledgerhq/device-transport-kit-node-hid` | 1.0.1 | 2026-04-14 | deps `node-hid ^3.2.0`, `usb ^2.16.0`; peer dmk ^1.2.0. **CJS only** (`import` and `require` both point to `lib/cjs`). |
| `@ledgerhq/device-transport-kit-speculos` | 1.2.1 | 2026-05-26 | peer dmk ^1.5.1; Node >= 20 or browser |
| `@ledgerhq/device-transport-kit-react-native-hid` / `-react-native-ble` | (not checked) | | RN only |
| `@ledgerhq/device-transport-kit-mockserver` | (not checked) | | testing |
| `@ledgerhq/device-signer-kit-ethereum` | 1.18.1 | 2026-09-21 | peer `@ledgerhq/context-module ^2.6.0`, dmk ^1.9.1; deps ethers 6.14.1, `@ledgerhq/device-contacts-kit`, `@ledgerhq/signer-utils` |
| `@ledgerhq/device-signer-kit-bitcoin` | 1.3.3 | 2026-08-11 | peer `bitcoinjs-lib ^6.1.6`, dmk ^1.7.1; dep crypto-js |
| `@ledgerhq/device-signer-kit-solana` | 1.13.3 | 2026-09-28 | peer dmk ^1.10.0; deps @solana/web3.js, context-module (regular dep) |
| `@ledgerhq/device-signer-kit-hyperliquid` | 1.1.0 | 2026-05-18 | needs provider certificate + signedMetadata; niche |
| `@ledgerhq/device-signer-kit-zcash` | 0.7.1 | 2026-09-07 | |
| `@ledgerhq/device-signer-kit-icp` | 0.2.0 | 2026-08-03 | |
| `@ledgerhq/context-module` | 2.6.0 | 2026-09-21 | peer dmk ^1.9.1; supports Ethereum, Solana, Concordium |
| `@ledgerhq/device-trusted-app-kit-ledger-keyring-protocol` | 0.5.0 | 2026-03-13 | Ledger Keyring Protocol trusted app |

Repo-only (in `packages/signer/` on `develop`, npm not checked): `signer-aleo`, `signer-concordium`, `signer-cosmos`, `signer-polkadot`, `signer-trx`, `signer-xrp`, `signer-utils`. The agent-skill SDK reference also names `@ledgerhq/device-signer-kit-cosmos` and `-aleo` as installable — **INFERRED** they are on npm.

Gotchas (VERIFIED):
- `rxjs` is a **peer dependency**: `npm install rxjs` explicitly (migration guide).
- `@ledgerhq/context-module` is a **peer dep of the ETH signer and is imported internally** — install it even if you do not care about clear signing, else `Module not found: Can't resolve '@ledgerhq/context-module'` (agent-skill SDK reference).
- Vite + BTC/Solana signers need Node polyfills (`vite-plugin-node-polyfills`, `optimizeDeps.include: ["crypto-js"]`) (agent-skill platform patterns).
- The agent-skill says "DMK packages are ESM-only — use `"type": "module"`"; the actual package.json files ship **both** ESM and CJS for dmk/signer-eth, and node-hid transport is CJS-only. **Contradiction** — treat the skill as stale; `tsx` handles either.
- The published DMK agent skills list "known-working versions" dmk 1.2.0 / signer-eth 1.12.0 — far behind npm latest (1.11.0 / 1.18.1). Expect drift; trust installed `.d.ts`.
- All transport READMEs carry a CAUTION: "still under development ... may lead to breaking changes".

## 2. Transports — VERIFIED

Source: https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/transports.md and each package README.

| Transport | Package / factory export | Environment | Our devices |
|---|---|---|---|
| Web HID (USB) | `@ledgerhq/device-transport-kit-web-hid` → `webHidTransportFactory`, `webHidIdentifier === "WEB-HID"` | Chromium browsers only; HTTPS or localhost; `startDiscovering()` must be called from a user gesture (browser shows a picker) | Nano S Plus + Flex |
| Web BLE | `@ledgerhq/device-transport-kit-web-ble` → `webBleTransportFactory` | Browsers with Web Bluetooth (Chrome/Edge; not Firefox/Safari); secure context + transient activation | Flex only |
| Node HID (USB) | `@ledgerhq/device-transport-kit-node-hid` → `nodeHidTransportFactory` | Node.js (README: "tested successfully on Node v20"), Electron | Nano S Plus + Flex |
| Speculos | `@ledgerhq/device-transport-kit-speculos` → `speculosTransportFactory(url = "http://localhost:5000")` | Node >= 20 or browser; talks HTTP to the emulator | emulated Flex / nanos2 |
| RN HID / RN BLE | `-react-native-hid`, `-react-native-ble` (`RNBleTransportFactory`) | React Native | n/a |
| Mock server | `-mockserver` | tests | n/a |

- **Node BLE: does not exist.** There is no Node Bluetooth transport in the repo. For BLE you need a browser (Web Bluetooth) or React Native. **VERIFIED** (repo tree).
- **NFC: does not exist** in DMK (zero matches for "nfc" across 5,222 paths of the monorepo tree). **VERIFIED**.
- Multiple transports can be registered on one builder (Flex/Stax doc shows `.addTransport(webBleTransportFactory).addTransport(webHidTransportFactory)`). `startDiscovering({ transport })` can filter by identifier. **VERIFIED**.
- Known limitation (docs): DMK cannot distinguish two devices of the same model over WebHID/USB and does not prevent connecting the same device twice. **VERIFIED**.
- `DeviceId` is generated at runtime and is not stable across sessions ("privacy feature of Ledger devices") — you cannot fingerprint a device. **VERIFIED** (DeviceModel.ts comment).
- Speculos package README imports from `@ledgerhq/device-transport-speculos` but install says `@ledgerhq/device-transport-kit-speculos` — the README import is a typo; the npm name is `-kit-speculos`. **VERIFIED** (registry).

### Node HID on Windows — what the source actually does (VERIFIED, `NodeHidTransport.ts` + CHANGELOG)
- Uses `node-hid` (`devicesAsync`, `HIDAsync`) for I/O and the `usb` package for hotplug (`usb.on("attach"/"detach")`).
- Filters by `LEDGER_VENDOR_ID = 0x2c97`; on `win32` and `darwin` it additionally requires `usagePage === 0xffa0` (the APDU interface). 1.0.1 changelog: "Filter Ledger HID devices to the APDU interface on macOS and Windows to prevent stalls when multiple HID interfaces are exposed." So use >= 1.0.1 on Windows.
- Dedupes multiple interfaces of the same device by `vendorId:productId`.
- `startDiscovering()` on Node is effectively a wrapper around `listenToAvailableDevices()` (no picker). The agent skill recommends `listenToAvailableDevices({})` for CLI contexts.
- node-hid 3.4.0 (2026-07-18): `engines node >= 10.16`, N-API 4 prebuilds; install script is `pkg-prebuilds-verify ... || node-gyp rebuild`. On Windows x64 with a current Node a prebuild should match (**INFERRED**; if it falls back to node-gyp you need VS Build Tools + Python). The `usb` package also has a native addon and the same risk.
- Fallback documented by Ledger's agent skill if node-hid will not build: write a custom transport on the `usb` package's WebUSB API (`WebUSBDevice`, vendor 0x2c97, endpoint 3, 64-byte frames). That is real work; avoid unless forced.
- Ledger Live / Ledger Wallet desktop holds the HID device open; close it before running your own Node/browser app (**INFERRED** from standard HID exclusivity on Windows; not stated in DMK docs).

### Web Bluetooth on Windows (INFERRED unless noted)
- MDN (VERIFIED): secure context only, `requestDevice()` needs transient activation, not available in workers.
- Chrome/Edge on Windows 10+ support Web Bluetooth; Firefox/Safari do not. (General knowledge; MDN compat table not readable via fetch.)
- WebBleTransport (VERIFIED) calls `navigator.bluetooth.requestDevice({ filters: [{services:[ledgerServiceUuid]}...], optionalServices })` using service UUIDs from the device-model data source, so the Flex should appear in Chrome's picker. Pre-pairing the Flex in Windows Bluetooth settings is not required by Web Bluetooth (the picker pairs) — INFERRED; test early.

## 3. Device support — VERIFIED (source `packages/device-management-kit/src/api/device/DeviceModel.ts`)

```ts
export enum DeviceModelId {
  NANO_S = "nanoS", NANO_SP = "nanoSP", NANO_X = "nanoX",
  STAX = "stax", FLEX = "flex", APEX = "apexp",
}
export const LEDGER_VENDOR_ID = 0x2c97;
```
- Both our devices are first-class. Flex and Stax doc page ("Add BLE and USB support for Flex and Stax") requires DMK >= 0.4.0.
- Transaction Check (Web3 Checks) is described as a touchscreen-signer feature ("On Ledger touchscreen signers, Clear Signing works alongside Transaction Check") — so Flex yes, Nano S Plus likely no. **VERIFIED** statement, **INFERRED** exclusion.
- Speculos emulates Nano X, Nano S+ (`nanos2`), Flex, Stax, Apex+. `app-ethereum` releases attach prebuilt ELFs per device: e.g. v1.22.3 (2026-08-26) has `app-1.22.3-flex.elf` and `app-1.22.3-nanos2.elf`. **VERIFIED** (GitHub releases API). So you can emulate either of our devices without hardware.

## 4. Core DMK API — VERIFIED (DMK README + docs + `DeviceManagementKit.ts`)

Public methods on the built instance: `getVersion`, `startDiscovering({transport?})`, `stopDiscovering`, `listenToAvailableDevices({transport?})`, `connect({device | deviceId, sessionRefresherOptions?: {isRefresherDisabled, pollingInterval}})`, `reconnect({device, sessionRefresherOptions?})`, `disconnect({sessionId})`, `sendApdu({sessionId, apdu})`, `sendCommand({sessionId, command, abortTimeout?})`, `executeDeviceAction({sessionId, deviceAction})`, `getConnectedDevice({sessionId})`, `getDeviceSessionState({sessionId})` (Observable), `listConnectedDevices()`, `listenToConnectedDevice()`, `disableDeviceSessionRefresher`, `setProvider/getProvider`, `setFirmwareDistributionSalt/get...`, `setWebSocketUrl/get...`, `isEnvironmentSupported()`, `close()`.

Session state (`DeviceSessionState`): `deviceStatus` in `DeviceStatus.{CONNECTED, LOCKED, BUSY, NOT_CONNECTED}`, `deviceModelId`, `batteryStatus?`, `currentApp?: {name, version}`, OS info. Dashboard shows `currentApp.name === "BOLOS"`.

Pre-built commands: `OpenAppCommand(name)`, `CloseAppCommand`, `GetOsVersionCommand`, `GetAppAndVersionCommand`, battery status. Most reject when device is locked or status word != `0x9000`.

Pre-built device actions in core (`src/api/device-action/os/`): `OpenAppDeviceAction`, `OpenAppWithDependencies`, `GoToDashboard`, `GetDeviceStatus`, `GetDeviceMetadata`, `ListApps`, `ListAppsWithMetadata`, `InstallOrUpdateApps`, `InstallLanguagePackage`, `WaitForAppAndVersion`, `SendCommandInAppDeviceAction`, `CallTaskInAppDeviceAction`. App install/list/genuine-check need a **Secure Channel** (WebSocket to Ledger HSM, user approves `AllowSecureConnection` on device, internet required) — VERIFIED in the dmk-business-logic skill.

Docs bug (VERIFIED): the how-to page's `executeDeviceAction` example passes `{ sessionId, openAppDeviceAction }`; the real parameter is `deviceAction`.

### Device-action state machine — VERIFIED
- Implemented with **xstate 5** (`XStateDeviceAction.ts`: `createActor`, snapshots mapped into `DeviceActionState`).
- `DeviceActionStatus`: `not-started | pending | stopped | completed | error`.
- `DeviceActionState<Output, Error, IntermediateValue>` union: Pending carries `intermediateValue`, Completed carries `output`, Error carries `error`.
- `UserInteractionRequired` enum (core): `none, unlock-device, allow-secure-connection, confirm-open-app, sign-transaction, sign-typed-data, allow-list-apps, verify-address, sign-personal-message, sign-delegation-authorization, web3-checks-opt-in, verify-safe-address, register-wallet, confirm-load-image, confirm-commit-image, confirm-remove-image, grant-consent, allow-install-firmware`.
- Core `OpenAppDeviceAction` uses `UserActionRequiredType.{None, ConfirmOpenApp, UnlockDevice}` in `intermediateValue.userActionRequired` (older naming) while signers use `intermediateValue.requiredUserInteraction`. Two field names — be careful.
- ETH `SignTransactionDeviceAction` states (from source): `InitialState → OpenAppDeviceAction (skippable via options.skipOpenApp) → GetAppConfig → [Web3ChecksOptIn → Web3ChecksOptInResult] → ParseTransaction → GetAddress → BuildContexts → ProvideContexts → SignTransaction → SignTransactionResultCheck → (BlindSignTransactionFallback | DetectBlindSigning) → Success/Error`. Steps exposed via `SignTransactionDAStep.{OPEN_APP, GET_APP_CONFIG, WEB3_CHECKS_OPT_IN, WEB3_CHECKS_OPT_IN_RESULT, PARSE_TRANSACTION, GET_ADDRESS, BUILD_CONTEXTS, PROVIDE_CONTEXTS, SIGN_TRANSACTION, BLIND_SIGN_TRANSACTION_FALLBACK, DETECT_BLIND_SIGNING}`.

### Error handling — VERIFIED (agent-skill code patterns, consistent with source)
- Errors carry `_tag` and often `errorCode` (hex status word string). User rejection = `_tag === "RefusedByUserDAError"` or codes `5501`, `6985` (`6982` on Solana). Locked: `DeviceLockedError` / `5515`. App not installed: `6807`. Blind signing disabled: `6a80`. Wrong app: `6e00`. Also `DeviceDisconnectedWhileSendingError`, `SendApduTimeoutError`, `NoAccessibleDeviceError`. `UnknownDeviceExchangeError` buries `errorCode` under `originalError`.

## 5. Signer kits — operations

### Ethereum (`SignerEthBuilder`) — VERIFIED (README + migration guide)
```ts
const signerEth = new SignerEthBuilder({ dmk, sessionId, originToken? })
  .withContextModule(customContextModule)?   // optional
  .withAddressBook({...})?                   // optional, shows contact names on device
  .build();

signerEth.getAddress(path, { checkOnDevice?, returnChainCode?, skipOpenApp?, chainId? })
  // → { publicKey, address: `0x…`, chainCode? }
signerEth.signTransaction(path, txBytes: Uint8Array, { skipOpenApp? })      // RLP-encoded unsigned tx → { r, s, v }
signerEth.signMessage(path, message: string | Uint8Array, { skipOpenApp? }) // personal_sign → { r, s, v }
signerEth.signTypedData(path, typedData: { domain, types, primaryType, message }, { skipOpenApp? }) // EIP-712 → { r, s, v }
signerEth.signDelegationAuthorization(path, chainId: number, contractAddress: string, nonce: number) // EIP-7702 → { r, s, v }
signerEth.verifySafeAddress(safeAddress, { chainId, skipOpenApp? })        // → void
```
- Derivation path format: `"44'/60'/0'/0/0"` — **no `m/` prefix** (DMK's `DerivationPathUtils.splitPath` throws on `m`). VERIFIED (business-logic skill). Note the Solana README example uses `"m/44'/501'/0'/0'"` — inconsistent; test both.
- No `signEIP712HashedMessage` equivalent; no `getChallenge`/`getAppConfiguration` (use `sendCommand`). VERIFIED (migration table).
- The signer opens the Ethereum app automatically. VERIFIED.
- README examples write `new SignerEthBuilder({ sdk, sessionId })`; the real arg is `dmk` (docs page and migration guide). Naming drift in README.

### Bitcoin (`SignerBtcBuilder`) — VERIFIED (README headings)
`getExtendedPublicKey`, `getMasterFingerprint`, `signMessage`, `signPsbt`, `signTransaction`, `getWalletAddress`, `registerWallet` (custom/multisig wallet policies). Peer dep `bitcoinjs-lib`.

### Solana (`SignerSolanaBuilder`) — VERIFIED (README)
`getAddress`, `signTransaction(path, bytes, { solanaRPCURL?, delayed?, fetchBlockhash?, transactionResolutionContext?: { mintAddress }, skipOpenApp? })` → 64-byte signature; `signMessage` (off-chain message spec); `getAppConfiguration`. Clear signing only for simple instructions (single transfer, createAccount+transfer); `6808` = unsupported, needs blind signing.

### Others
Hyperliquid `signActions({ derivationPath, certificate, signedMetadata, actions })` requires a perps-provider certificate — not hackathon-friendly. Zcash/ICP exist; READMEs not read.

## 6. How Clear Signing metadata reaches the device — VERIFIED (context-module README/source, ProvideContextTask.ts, for-wallets doc)

1. `SignerEth.signTransaction` parses the tx (`ParseTransactionTask`), derives the address, then `BuildContexts` calls `contextModule.getContexts(input)`.
2. `ContextModuleBuilder({ originToken }).setChain(ContextModuleChainID.Ethereum).build()` wires loaders (tokens, NFTs, trusted names/ENS, plugins such as 1inch/Paraswap, ERC-7730 transaction info/field descriptions, Web3 checks, proxy info, dynamic networks, Safe accounts). Loaders hit Ledger backends in parallel: CAL `https://global.api.prd.ledger.com/cal/v1` (mode prod/test, branch main/next/demo), a web3-checks URL, `https://nft.api.live.ledger.com`, and a blind-signing reporter `https://blind-signing.api.ledger.com/ingest`. `originToken` defaults to `""` when omitted.
3. Each `ClearSignContext` has a `type`, a `payload` (signed by Ledger's trusted authority) and optional `certificate`. `ProvideContextTask` maps type → APDU: `SetPluginCommand`, `SetExternalPluginCommand`, `ProvideNFTInformationCommand`, `ProvideTokenInformationCommand`, `ProvideTransactionInformationCommand`, `ProvideTrustedNameCommand`, `ProvideEnumCommand`, `ProvideTransactionFieldDescriptionCommand`, `ProvideWeb3CheckCommand`, `ProvideProxyInfoCommand`, `ProvideNetworkConfigurationCommand`, `ProvideSafeAccountCommand`, `ProvideGatedSigningCommand`, preceded by `LoadCertificateCommand` when a PKI cert is attached.
4. Then `SignTransactionCommand` (chunked). If the app lacks context it falls back to blind signing; `BlindSigningDetectionTask` reports it.
5. ERC-7730 descriptors live in the Ethereum Foundation registry (`ethereum/clear-signing-erc7730-registry`); stewardship moved from Ledger to the EF on 2026-05-12. Authoring/validation at https://clearsigning.org/build/. A dApp's own contract gets clear-signed only if a descriptor is in the registry **and** the device's Ethereum app receives it via CAL — i.e. **you cannot push your own descriptor to the device without Ledger's signing backend** (payloads "must be signed by a trusted authority"). You could write a custom `ContextLoader`, but the device checks signatures on the payload. INFERRED consequence: a hackathon team cannot clear-sign a freshly deployed custom contract; stick to ERC-20 transfers / native ETH / EIP-712 typed data (which the app renders field-by-field) / personal messages.
6. `originToken`: optional to build; without it "signing remains available and basic Clear Signing may still be supported, but advanced contract context may be unavailable and some transactions may fall back to blind signing"; Transaction Checks unavailable. Legal page: using a token without a written agreement is forbidden. Do not ask for one on a 3-day timeline; design around it.
7. Blind-sign reporter: `setAppSource("my-app-name")` tags reports (default `"third-party"`).

## 7. Node vs browser — how to run

### Browser (VERIFIED, init_dmk.md)
```bash
npm install @ledgerhq/device-management-kit @ledgerhq/device-transport-kit-web-hid @ledgerhq/device-transport-kit-web-ble rxjs
npm install @ledgerhq/device-signer-kit-ethereum @ledgerhq/context-module
```
```ts
// dmk.ts — build once, singleton
import { ConsoleLogger, DeviceManagementKitBuilder } from "@ledgerhq/device-management-kit";
import { webHidTransportFactory } from "@ledgerhq/device-transport-kit-web-hid";
import { webBleTransportFactory } from "@ledgerhq/device-transport-kit-web-ble";
export const dmk = new DeviceManagementKitBuilder()
  .addLogger(new ConsoleLogger())
  .addTransport(webHidTransportFactory)   // Nano S Plus + Flex over USB
  .addTransport(webBleTransportFactory)   // Flex over Bluetooth
  .build();
```
```ts
// in a click handler (user gesture required for the HID/BLE picker)
import { firstValueFrom } from "rxjs";
const device = await firstValueFrom(dmk.startDiscovering({ transport: "WEB-HID" })); // BLE identifier: import from the web-ble package (string not verified)
const sessionId = await dmk.connect({ device });
```
Chromium only, HTTPS or localhost. React: do not mix a module singleton with a Provider (two instances).

### Node.js (VERIFIED: agent-skill platform patterns + ldmk-cli app)
```bash
npm install @ledgerhq/device-management-kit @ledgerhq/device-transport-kit-node-hid rxjs \
            @ledgerhq/device-signer-kit-ethereum @ledgerhq/context-module tsx
```
```ts
// main.ts  — run with: npx tsx main.ts
import { DeviceManagementKitBuilder, DeviceStatus, DeviceActionStatus } from "@ledgerhq/device-management-kit";
import { nodeHidTransportFactory } from "@ledgerhq/device-transport-kit-node-hid";
import { SignerEthBuilder } from "@ledgerhq/device-signer-kit-ethereum";
import { firstValueFrom, filter, take, timeout } from "rxjs";

const dmk = new DeviceManagementKitBuilder().addTransport(nodeHidTransportFactory).build();

function run<T>(a: { observable: any; cancel: () => void }): Promise<T> {
  return new Promise((res, rej) => a.observable.subscribe({
    next: (s: any) => {
      if (s.status === DeviceActionStatus.Pending)
        process.stderr.write(`device: ${s.intermediateValue.requiredUserInteraction}\n`);
      else if (s.status === DeviceActionStatus.Completed) res(s.output as T);
      else if (s.status === DeviceActionStatus.Error) rej(s.error);
      else if (s.status === DeviceActionStatus.Stopped) rej(new Error("cancelled"));
    }, error: rej }));
}

const devices = await firstValueFrom(
  dmk.listenToAvailableDevices({}).pipe(filter(d => d.length > 0), timeout(60_000)));
const sessionId = await dmk.connect({ device: devices[0]! });

const st = await firstValueFrom(dmk.getDeviceSessionState({ sessionId }).pipe(take(1)));
if (st.deviceStatus === DeviceStatus.LOCKED)
  await firstValueFrom(dmk.getDeviceSessionState({ sessionId })
    .pipe(filter(s => s.deviceStatus !== DeviceStatus.LOCKED), take(1), timeout(60_000)));

const eth = new SignerEthBuilder({ dmk, sessionId }).build();
const { address } = await run<{ address: string }>(eth.getAddress("44'/60'/0'/0/0", { checkOnDevice: true }));
console.log(address);

// Sign a tx built with ethers v6 (ethers is already a dep of the signer) — INFERRED glue:
// import { Transaction, getBytes } from "ethers";
// const tx = Transaction.from({ to, value, chainId, nonce, gasLimit, maxFeePerGas, maxPriorityFeePerGas, type: 2 });
// const sig = await run<{ r: string; s: string; v: number }>(eth.signTransaction("44'/60'/0'/0/0", getBytes(tx.unsignedSerialized)));
// tx.signature = sig; provider.broadcastTransaction(tx.serialized)
await dmk.disconnect({ sessionId });
```

Ledger's own Node reference is `apps/ldmk-cli` in the monorepo (interactive menu; uses node-hid transport + ETH signer; run `pnpm cli dev` from a monorepo clone). Its `dev` script uses `&`/`sleep`, i.e. a POSIX shell — run it from Git Bash on Windows (INFERRED).

### Speculos (emulator) — VERIFIED (speculos docs, speculos README)
Windows path is Docker only:
```bash
docker pull ghcr.io/ledgerhq/speculos
# get app-1.22.3-flex.elf (or -nanos2.elf) from https://github.com/LedgerHQ/app-ethereum/releases into ./apps
docker run --rm -it -v "$(pwd)/apps:/speculos/apps" -p 5000:5000 -p 40000:40000 \
  ghcr.io/ledgerhq/speculos --model flex --display headless --api-port 5000 --apdu-port 40000 apps/app-1.22.3-flex.elf
```
```ts
import { speculosTransportFactory } from "@ledgerhq/device-transport-kit-speculos";
const dmk = new DeviceManagementKitBuilder().addTransport(speculosTransportFactory("http://localhost:5000")).build();
```
Screen at http://127.0.0.1:5000. `@ledgerhq/speculos-device-controller` can press buttons / tap the Flex screen by percentage coordinates — useful for a scripted demo/CI. Default seed is "secret" unless `--seed` given. Whether `--model flex` is needed with a flex ELF: the docs say model is auto-detected for ELFs embedding API level — INFERRED it works for the release ELFs.

## 8. Windows caveats (summary)
- Browser: Chrome/Edge only. WebHID + Web Bluetooth both fine on Windows 11 in Chromium (INFERRED). Close Ledger Wallet desktop first (HID exclusivity, INFERRED).
- Node: node-hid 3.x prebuilds for win-x64 exist; `usb` package is also native. If `npm install` tries node-gyp you need VS Build Tools. Use transport >= 1.0.1 (usage-page filter fix). Tested by Ledger on Node v20 only.
- Node BLE: impossible with DMK. For Bluetooth you need the browser (Flex only).
- Speculos: Docker Desktop (WSL2). Path mounts need `$(pwd)` under Git Bash or `${PWD}` in PowerShell.
- No Ledger docs mention Windows at all — every Windows statement above is from node-hid / Chrome knowledge, not Ledger.

## 9. Ledger's AI/agent framing that overlaps DMK — VERIFIED (ai-tools pages, agent-skills repo)
- `npx skills add ledgerhq/agent-skills -s ledger-dmk-implementation dmk-intent-vocabulary dmk-business-logic` installs Markdown skills for Claude Code/Cursor. They encode a 5-gate HITL flow (Init → Session → Device State → App → Operation) with ABORT/ESCALATE rules, timeouts (discovery 15s, app open 30s, signing 60s) and "never bypass an ESCALATE gate". Good vocabulary for the pitch's "what the agent does vs what the human approves" boundary.
- The skills explicitly cover WebAuthn: DMK's only role is `OpenAppCommand("Security Key")`; credentials go through `navigator.credentials` (Ledger = cross-platform roaming authenticator).
- "Ledger Agent Intent" (approval queue) and Wallet CLI are separate products, not DMK.

## 10. Gaps, contradictions, risks
- **NFC**: no SDK surface. Flex NFC = Recovery Key + Security Key only (Ledger shop copy via search; not read on a Ledger developer page). Idea #2 dead as stated; the nearest buildable analogue is Flex-over-BLE to a laptop browser, or two devices on one host passing a signed payload.
- **Face scan (idea #1)**: nothing in DMK; the device confirmation *is* the human factor. A face/voice layer would be host-side UX only and the jury may see it as weakening, not strengthening, the trust model (INFERRED).
- **Origin token**: required for Transaction Check and full clear signing; partner-program only. Plan demos around ERC-20/ETH transfers, EIP-712 typed data, personal messages, Safe address verification, EIP-7702 delegation.
- **Docs drift**: how-to page param typo (`openAppDeviceAction`), README `sdk` vs `dmk`, speculos README import name, skill "ESM-only" vs shipped CJS, skill version table years behind. Budget time for `.d.ts` reading.
- **Node support is thin**: one transport, tested on Node 20, "under development" caution, no Windows notes. If node-hid fights you, fall back to the browser (WebHID) — that is the primary, best-tested path.
- **Nano S Plus specifics**: no battery, no BLE, no Transaction Check; small screen so EIP-712 review is long. Fine for USB demos.
- Not checked: npm presence of cosmos/aleo/trx/xrp/polkadot signers; exact Web Bluetooth transport identifier string; whether `startDiscovering` without `{transport}` on a dual-transport browser build opens two pickers.

## 11. Sources
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/dmk (and `.md`)
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/how_to_use_a_signer (and `.md`)
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/transports.md
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/migrations/ledgerjs-to-dmk.md
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/migrations/signers/eth/hw_app_eth_to_dmk.md
- https://developers.ledger.com/docs/device-interaction/beginner/init_dmk.md
- https://developers.ledger.com/docs/device-interaction/beginner/setup.md
- https://developers.ledger.com/docs/device-interaction/beginner/discover_and_connect.md
- https://developers.ledger.com/docs/device-interaction/beginner/ble_flex_stax.md
- https://developers.ledger.com/docs/device-interaction/getting-started.md
- https://developers.ledger.com/docs/device-interaction/explanation/introduction.md
- https://developers.ledger.com/docs/clear-signing/overview.md
- https://developers.ledger.com/docs/clear-signing/for-wallets.md
- https://developers.ledger.com/docs/ai-tools/overview.md
- https://developers.ledger.com/docs/ai-tools/ledger-dmk-skills (and `.md`)
- https://developers.ledger.com/llms.txt
- https://github.com/LedgerHQ/device-sdk-ts (README; tree via GitHub API)
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/device-management-kit/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/device-management-kit/src/api/device/DeviceModel.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/device-management-kit/src/api/device-action/model/DeviceActionState.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/device-management-kit/src/api/device-action/model/UserInteractionRequired.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/device-management-kit/src/api/device-action/xstate-utils/XStateDeviceAction.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/device-management-kit/src/api/DeviceManagementKit.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/signer/signer-eth/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/signer/signer-eth/src/internal/app-binder/device-action/SignTransaction/SignTransactionDeviceAction.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/signer/signer-eth/src/internal/app-binder/task/ProvideContextTask.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/signer/signer-btc/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/signer/signer-solana/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/signer/signer-hyperliquid/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/signer/context-module/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/signer/context-module/src/ContextModuleBuilder.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/signer/context-module/src/config/model/ContextModuleConfig.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/node-hid/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/node-hid/CHANGELOG.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/node-hid/src/api/transport/NodeHidTransport.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/web-hid/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/web-ble/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/web-ble/src/api/transport/WebBleTransport.ts
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/transport/speculos/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/speculos-device-controller/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/ledger-wallet/README.md
- https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/apps/ldmk-cli/README.md (+ package.json)
- https://registry.npmjs.org/@ledgerhq%2F<package> for every package in the table; https://registry.npmjs.org/node-hid
- https://raw.githubusercontent.com/node-hid/node-hid/master/README.md
- https://github.com/LedgerHQ/agent-skills (README; skills/dmk/ledger-dmk-implementation/{SKILL,dmk-platform-patterns,dmk-sdk-reference,dmk-code-patterns}.md; skills/dmk/dmk-business-logic/SKILL.md)
- https://api.github.com/repos/LedgerHQ/app-ethereum/releases (ELF assets per device)
- https://speculos.ledger.com/_sources/user/quickstart.md.txt, .../docker.md.txt, .../getting_an_app.md.txt
- https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API
- https://shop.ledger.com/products/ledger-flex (NFC = Recovery Key / Security Key; via search snippet)
