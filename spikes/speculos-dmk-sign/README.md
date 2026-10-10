# Spike: Speculos + DMK + ETH signer, end to end, no hardware

**Status: PASS on both emulated devices.** `getAddress` -> `signMessage` (EIP-191) -> `signTypedData` (EIP-712) all complete against Speculos running app-ethereum 1.22.3 for **Flex** and **Nano S Plus (nanos2)**, every signature recovers to the device address with viem, and the on-device review is driven automatically over the Speculos REST API. No Ledger device was plugged in at any point.

Both devices produce byte-identical signatures (same seed, deterministic ECDSA): EIP-191 `0xccdf1529...bbb11b`, EIP-712 `0x468e6b26...15091c`.

## Run it

```bash
npm install                 # exact versions pinned in package.json (DMK 1.11.0, signer-eth 1.18.1, transport-speculos 1.2.1, viem 2.57.4)
npm run speculos:flex       # docker run ghcr.io/ledgerhq/speculos:latest app-1.22.3-flex.elf (restarts the container; ~5 s)
npm run demo                # node sign.mjs            -> ALL PASS
npm run speculos:nanos2
npm run demo:nanos2         # node sign.mjs --model nanos2 -> ALL PASS
npm run stop                # docker rm -f speculos
```

`sign.mjs` flags: `--model flex|nanos2`, `--url http://127.0.0.1:5000`, `--skip-typed`, `--no-settings` (skip the blind-signing toggle; only when the container already has it ON).

Prereqs: Docker Desktop running; the ELFs in `untrusted-downloads/` (gitignored). Re-download with
`gh release download v1.22.3 -R LedgerHQ/app-ethereum -p 'app-1.22.3-flex.elf' -p 'app-1.22.3-nanos2.elf' -D untrusted-downloads` (1.22.3 was the latest release on 2026-10-10).

## What the script does

1. Screenshot, then **enable Blind signing** in the app settings (Speculos has no persistent NVRAM, so every fresh container starts with it OFF; EIP-712 without CAL descriptors needs it ON, otherwise `0x6a80 Invalid data`). Flex: tap gear (440,50) -> toggle (415,353) -> back arrow (50,47). Nano: right, both, both (toggle), 6x right to "Back", both.
2. `DeviceManagementKitBuilder().addTransport(speculosTransportFactory(url, false, DeviceModelId.FLEX|NANO_SP)).build()`, `listenToAvailableDevices({})`, `connect({device})`.
3. `SignerEthBuilder({dmk, sessionId}).build()` then `getAddress("44'/60'/0'/0/0", {checkOnDevice:false, skipOpenApp:true})`.
4. `signMessage(path, "Approve: pay 12 USDC to Alice for pizza. nonce 42", {skipOpenApp:true})` while an **auto-approver** polls `GET /events` (Speculos OCR of the screen), screenshots each new screen to `screenshots/<model>-NN-<step>.png`, and drives the UI: Flex = `POST /finger` swipe / tap / 3 s hold on "Hold to sign"; Nano = `POST /button/right|both`.
5. `recoverMessageAddress` (viem) must equal the device address.
6. `signTypedData(path, TYPED, {skipOpenApp:true})` with a 4-field `Payment{to,amount,memo,nonce}` struct under a `PizzaPay` domain; `recoverTypedDataAddress` must match.

## Decisive output (verbatim)

Flex, fresh container (`run13-flex.log`):
```
blind signing toggled ON (flex); screen now: ... Blind signing | Enable transaction blind  | signing ...
discovered: {"id":"SpeculosID","deviceModel":{"id":"SpeculosID","model":"flex",...},"transport":"SPECULOS_HTTP_TRANSPORT",...}
sessionId: 467d383d-... connected: Speculos - Ethereum - 1.22.3
getAddress(44'/60'/0'/0/0) = 0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415  (125 ms)
  [flex screen] Message | Approve: pay 12 USDC  | to Alice for pizza.  | nonce 42 | Reject | 2 of 3
  [flex screen] Sign message? | Reject | 3 of 3 | Hold to sign
signMessage sig: 0xccdf152902a7ab19666eda8bc8d1ff92957f58f601448e8e0d7f1969de4e587a4b3e1f57af23ac3253fb0c3f45fe754a0d71d8a23418180a15335d91939ebbb11b
recoverMessageAddress -> 0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415  match=true
  [signTypedData] pending: {"requiredUserInteraction":"web3-checks-opt-in","step":"signer.eth.steps.web3ChecksOptIn"}
  [flex screen] Enable | Transaction Check? ... | Maybe later | Yes, enable      -> tap Maybe later
  [flex screen] Blind signing ahead | ... | Accept risk and continue | Back to safety
  [flex screen] Skip | Review struct | EIP712Domain | name | PizzaPay | version | 1 | chainId | 1 | Reject | 2 of 6
  [flex screen] Skip | to | 0x70997970C51812dc3 | A010C7d01b50e0d17dc | 79C8 | amount | 12000000 | memo | pizza for Alice | Reject | 4 of 6
  [flex screen] Skip | nonce | 42 | Reject | 5 of 6
  [flex screen] Accept risk and sign  | typed message? | Reject | 6 of 6 | Hold to sign
signTypedData sig: 0x468e6b261622b9cfd2c9c0832dc491f7493482869707732bd971d254ac2c1fab1592ddb4c7b5ceba17198391f06d42d655a1ff753964f2d25edfe5f3fc9515091c
recoverTypedDataAddress -> 0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415  match=true
ALL PASS
```

Nano S Plus, fresh container (`run14-nanos2.log`):
```
getAddress(44'/60'/0'/0/0) = 0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415  (139 ms)
  [nanos2 screen] Message | Approve: pay 12  | USDC to Alice for  | pizza. nonce 42
  [nanos2 screen] Sign message                                   -> both
signMessage sig: 0xccdf1529...bbb11b   recoverMessageAddress -> 0x153a5a...1415  match=true
  [nanos2 screen] Ethereum | app is ready | Blind signing ahead | To accept risk, press  | both buttons   -> both
  [nanos2 screen] Review typed  | message
  [nanos2 screen] name | PizzaPay     [nanos2 screen] version | 1     [nanos2 screen] chainId | 1
  [nanos2 screen] verifyingContract | 0xCcCCccccCCCCcCCC | CCCCcCcCccCcCCCcCcc | cccccC
  [nanos2 screen] Message hash (1/2) | 0xB9CA7F05C7202AF2 | D5E59AD1CA4D66585 | 77F7B5C9B27AD9F7B
  [nanos2 screen] Message hash (2/2) | 9C8D882D3B81F6
  [nanos2 screen] Sign message                                   -> both
signTypedData sig: 0x468e6b26...15091c   recoverTypedDataAddress -> 0x153a5a...1415  match=true
ALL PASS
```

### What the emulator actually shows for EIP-712 (no CAL descriptor, blind signing ON)
- **Flex shows every named field** of both the domain and the `Payment` struct (`to`, `amount`, `memo`, `nonce`), see `screenshots/flex-08..12-signTypedData.png`. Preceded by a "Blind signing ahead" warning and ending in "Accept risk and sign typed message?".
- **Nano S Plus shows only the EIP712Domain fields then the message hash** (`screenshots/nanos2-08..14-signTypedData.png`); the `Payment` fields are NOT displayed. The app has a separate "Raw messages: Displays raw content of EIP712 messages" setting (default Disabled, 3rd item in App settings) that should surface them; not yet tested.
- EIP-191 `signMessage` shows the full sentence on both devices with no settings and no CAL (`flex-03-signMessage.png`, `nanos2-03-signMessage.png`). This is the cleanest "spoken intent on the Secure Screen" primitive.
- Flex only: the first sign flow after boot triggers a one-time "Enable Transaction Check?" opt-in (DMK step `web3ChecksOptIn`, `requiredUserInteraction: "web3-checks-opt-in"`); the script taps "Maybe later".

## Errors hit on the way (verbatim) and fixes

| Error | Cause | Fix |
|---|---|---|
| `Error [ERR_UNSUPPORTED_DIR_IMPORT]: Directory import ... @ledgerhq/device-management-kit/lib/esm/src is not supported` | `lib/esm/index.js` is literally `export*from"./src";` with no `"type":"module"` in package.json; Node ESM rejects it | `createRequire(import.meta.url)` and load the CJS builds (`sign.mjs` top) |
| `getAddress failed: UnknownDeviceExchangeError {"originalError":{"errorCode":"6980"}}` (run1, run3, run7, run9, run12) | the app was still mid-review from a previous aborted run; the first APDU is refused and the app drops to home | script retries `getAddress` once on `errorCode === "6980"` |
| `signTypedData failed: EthAppCommandError {"errorCode":"6a80","message":"Invalid data"}` with screen "Blind signing must be enabled in settings" (run5, run10) | EIP-712 without CAL descriptors is blind-signing; default OFF | `enableBlindSigning()` step; `--no-settings` to skip |
| Nano approver pressed `right` on "Blind signing ahead / To accept risk, press / both buttons" and landed on "Reject transaction" (run11, run12) | OCR splits "press" and "both buttons" into two events; `find(/press\s+both/)` tested each event alone | match on the joined screen text (`/both buttons/i.test(txt)`) |
| run2: `getAddress = 0xDad77910DbDFdE764fC21FCD4E74D71bBACA6D8D` | container started without `--seed` | always pass the Speculos test mnemonic (`speculos.sh`) -> `0x153a5a...1415` |
| Pressing `both` on "Quit app" exits the app and **the container dies** (curl exit 7) | Speculos exits when the app exits | restart via `npm run speculos:<model>`; the approver never presses both on an unmatched page |
| Git Bash rewrote `/apps/app.elf` to `C:/Program Files/Git/apps/...` | MSYS path conversion | `MSYS_NO_PATHCONV=1` in `speculos.sh` |

## DMK API shapes discovered from `.d.ts`, not docs

- `speculosTransportFactory(speculosUrl?: string, isE2E?: boolean, deviceModelId?: DeviceModelId): TransportFactory` (`device-transport-kit-speculos/lib/types/src/api/SpeculosTransport.d.ts`). Docs show only the URL; the 3rd arg is what makes `discovered.deviceModel.model` read `flex` / `nanoSP`.
- `listenToAvailableDevices({})` emits `DiscoveredDevice[]`; wait for the first non-empty array, then `dmk.connect({ device })` returns a `sessionId` string. `dmk.getConnectedDevice({ sessionId }).name` = `"Speculos - Ethereum - 1.22.3"`.
- `SignerEthBuilder({ dmk, sessionId, originToken? }).build()` -> `SignerEth` with `getAddress(derivationPath, { checkOnDevice?, returnChainCode?, skipOpenApp?, chainId? })`, `signMessage(derivationPath, string | Uint8Array, { skipOpenApp? })`, `signTypedData(derivationPath, TypedData, { skipOpenApp? })`, `signTransaction(derivationPath, Uint8Array, TransactionOptions)` (`lib/types/api/SignerEth.d.ts`, `api/model/*Options.d.ts`).
- Every call returns `{ observable, cancel }`; states are `DeviceActionStatus.{NotStarted,Pending,Completed,Error,Stopped}`; `Pending` carries `intermediateValue.{requiredUserInteraction, step}`. Step strings seen: `signer.eth.steps.web3ChecksOptIn`, `web3ChecksOptInResult`, `getAddress`, `buildContext`, `provideContext`, `signTypedData` (or `signTypedDataLegacy` when blind signing is off), `detectBlindSigning`.
- `Signature = { r: HexaString, s: HexaString, v: number }`; `v` came back as 27/28 here, `toSig()` normalises `v < 27` anyway. Concatenate to the 65-byte hex viem expects.
- `skipOpenApp: true` is required on Speculos: there is no dashboard to open the app from, so the default `OpenAppDeviceAction` fails.
- Errors are tagged objects: `error._tag` (`EthAppCommandError`, `UnknownDeviceExchangeError`) with `errorCode` (`"6a80"`, `"6980"`) nested one or two levels down.

## Speculos REST shapes used (all verified live)

- `GET /events` -> `{events:[{text,x,y,w,h,clear}]}` (OCR of drawn text, accumulated); `DELETE /events` clears.
- `GET /screenshot` -> PNG. Flex 480x600, Nano 128x64.
- `POST /finger {"action":"press-and-release"|"press"|"release","x","y"}`; swipe = press at (400,300) then release at (80,300); "Hold to sign" = press, wait 3 s, release.
- `POST /button/{left|right|both} {"action":"press-and-release"}`.
- CLI: `/apps/<elf> --model flex|nanosp --display headless --api-port 5000 --apdu-port 9999 --seed "<mnemonic>"`. Note `--model nanosp` (ELF name says `nanos2`).

## Next steps when a device is plugged in

1. Replace the transport: `npm i @ledgerhq/device-transport-kit-node-hid@1.0.1` and `.addTransport(nodeHidTransportFactory)`; drop the Speculos approver (a human presses the buttons), drop `skipOpenApp` (or open the Ethereum app by hand first). Close Ledger Wallet/Live first (HID exclusivity).
2. Expect the same screens as the screenshots here: EIP-191 shows the full sentence on both devices; EIP-712 shows the fields on Flex and only the hash on Nano S Plus unless "Raw messages" is on.
3. Test the Nano "Raw messages" setting in Speculos first (`App settings` 3rd item) to see whether `Payment` fields appear on the small screen.
4. Verify `v` handling against the real device (27/28 vs 0/1) by recovering with viem exactly as in `sign.mjs`.
5. Re-run with the real seed's address and confirm `recoverMessageAddress` still matches (the script asserts it and exits non-zero otherwise).

## Files

- `sign.mjs` -- the demo (ESM; ~130 lines incl. approver). `speculos.sh` -- container start. `package.json` -- `speculos:flex|nanos2`, `demo`, `demo:nanos2`, `stop`.
- `run1..12.log` -- earlier iterations (failures listed above). `run13-flex.log`, `run14-nanos2.log` -- the passing runs from fresh containers.
- `screenshots/` -- `flex-*`, `nanos2-*` from the passing runs; `manual-*` are hand-driven settings screens (blind-signing toggle ON on both devices).
- `untrusted-downloads/` (gitignored) -- `app-1.22.3-flex.elf`, `app-1.22.3-nanos2.elf` from the app-ethereum v1.22.3 GitHub release.
