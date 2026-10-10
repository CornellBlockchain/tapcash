# Developer-experience feedback (running draft)

Required by the brief. Kept from minute one. Every item below was hit on a real Windows 11 host (Node 24.2, Python 3.12, Chrome 153) during prep on 2026-10-10, or verified in source. Sections: what lost us, what was confusing, what context was missing, concrete fixes. Items marked SPIKE were reproduced by running the tool; items marked SOURCE were read in LedgerHQ repos / npm tarballs; items marked DOCS are documentation contradictions.

## 1. Windows is supported but the docs say it isn't

- DOCS/SPIKE: `developers.ledger.com/docs/ai-tools/ledger-cli` says "Windows (WSL recommended)". npm ships `@ledgerhq/wallet-cli-windows-x64@2.9.0`, a native Bun 1.4.2 exe (108,226,560 bytes) with Windows WebUSB polling and Credential Manager support. Every non-device command works natively; WSL2 is the worse path (no USB without usbipd-win, no Secret Service for the keychain, so `agent-intent enroll` fails there). Fix: state native Windows as supported, note the Node shim requirement, add a Windows `WALLET_PASS` recipe (Credential Manager) beside the macOS/Linux ones.
- SPIKE: no Ledger developer doc says to quit Ledger Wallet/Live before using any custom transport, and nothing explains that on Windows the failure is silent cross-talk (both processes open the HID collection shared; the DMK receiver validates no channel/tag bytes), not an "open" error. Fix: one paragraph in the DMK and wallet-cli docs, and a channel/tag check in the DMK receiver that drops foreign frames with a logged warning.
- SPIKE: no host preflight exists. Fix: `wallet-cli doctor` / `dmk doctor` printing: resolved exe path, state dir, keychain backend, USB backend, VID 0x2C97 enumeration, running Ledger Wallet processes, Web Bluetooth prerequisites.

## 2. wallet-cli (Agent Stack) rough edges

- SPIKE: `--device-timeout 10000` is ignored during discovery; with no device every device command waits a hard-coded 60 s then exits 1. Agents and CI need to fail fast. Fix: honour `--device-timeout` for discovery or add `--discovery-timeout`.
- SPIKE: "No Ledger device found" exits 1 with `code:"unknown"`; the embedded skill documents exit 3 = Ledger not detected. Fix: stable machine-readable error codes so an agent can branch without regexing message text.
- SPIKE: `--output` is per-command only; `wallet-cli --output json --help` returns `command-not-found`. `--help`/`--version` print JSON when piped, but `skill list`, `skill doctor`, `session view`, `agent-intent list` print plain text. Fix: one global `--output` honoured everywhere.
- SPIKE: the first-run nudge ("Tip: install the Ledger wallet-cli skill ...") goes to stdout, so the first `wallet-cli ... | jq` on a fresh machine breaks. `WALLET_CLI_NO_NUDGE=1` exists but is undocumented. Fix: stderr, and document the env var.
- SPIKE: `skill doctor` exits 1 for "not installed in this cwd", same as real drift. Fix: distinguish the two.
- DOCS: docs page shows v2.1.0; npm is at 2.9.0 (2026-10-05) and versions 2.2–2.8 were never published. Agent Intent, the newest primitive, is documented only inside the embedded skill.
- SOURCE: `send` always broadcasts via Ledger's backend to mainnet; no `--sign-only`, no custom RPC, no testnet (issues #22443, #22444). A hackathon cannot show device-signed EVM sends without spending real funds, unless it drops to DMK. Fix: `--sign-only` and `--rpc`.
- SOURCE: `--data` calls blind-sign on Nano-class devices; Transaction Check runs only on Stax/Flex/Gen5 (issue #21912). The skill should say this up front.

## 3. Key Ring

- SPIKE: `wallet-cli ring --help` = `init encrypt decrypt keys destroy`. No members, add-member, remove-member, rotate, backup. The SDK (`@ledgerhq/ledger-key-ring-protocol`) has `addMember`/`removeMember`, so a USB-less host cannot be enrolled from the CLI even though the brief invites "Key Ring without USB". Fix: expose the lifecycle.
- DOCS/SOURCE: the docs sentence "Removing a Ledger Sync member rotates the Key Ring encryption key" is misleading: Ledger Wallet manages app-16 members, the ring lives on app 17, and `removeMember` rotates only its own applicationId. Ring members are not visible anywhere in Ledger Wallet. Fix: document where ring members live and how to evict one.
- DOCS/SOURCE: "recoverable from your seed" is true only while Ledger's backend holds the trustchain root; the LKRP whitepaper says ring keys are random, not seed-derived. The docs should say "recoverable with your seed plus Ledger's server", and say whether the one-year Ledger Sync inactivity purge deletes ring data.
- SOURCE: ciphertext format is `[12-byte IV][AES-256-GCM]` with no header, no key-name, no version. Rotation is all-or-nothing. Fix: a small header.
- SOURCE: on native Windows, piped invocations have no `/dev/tty`, so `WALLET_PASS` is mandatory and undocumented for Windows.

## 4. DMK (device-management-kit) in Node

- SPIKE: every `@ledgerhq/*` ESM build is `export*from"./src"` (extensionless directory import); `node script.mjs` dies with `ERR_UNSUPPORTED_DIR_IMPORT` on the first import even though the package.json `import` condition advertises ESM. Workaround: `createRequire` and the CJS build. Fix: emit fully-specified ESM.
- SPIKE: `@ledgerhq/device-transport-kit-node-hid` README says "tested on Node v20". It works on Node 24 with prebuilds (node-hid 3.4.0, usb 2.19.1), no compiler needed on Windows. Say so, and note that npm 12 blocks the install scripts harmlessly.
- SPIKE: `startDiscovering()` on node-hid is a one-shot that logs an Error and errors the observable when no device is present; "no device yet" is the normal state for an agent. `listenToAvailableDevices()` is the right call and is not the headline example. Fix: docs, or make Node discovery long-lived like the web transports.
- SPIKE: `dmk.close()` does not let the process exit (libusb hotplug thread keeps the loop alive); every script needs `process.exit()`. Fix: unref the hotplug listener in `close()`.
- SPIKE: `DeviceModel.name` vs docs' `productName`; `GetAddress` returns `{address, publicKey, chainCode?}`. A one-page Node quickstart with exact field names and the CJS caveat would have saved every trial step.
- SOURCE: `device-signer-kit-ethereum` pulls deprecated `crypto-js@4.2.0`. Replace with `node:crypto` / `@noble/hashes`.
- DOCS: agent-skills `ledger-dmk-implementation` version table is ~9 DMK minors stale; README points at the wrong repo for the wallet-cli skill; no LICENSE file.

## 5. Clear signing and the origin token

- SOURCE (live probes): `cal/v1/tokens`, `/certificates`, `/networks` answer 200 with no token; every `/dapps` route and `transaction-checks/v3` answer 403. Docs say the origin token is "optional" in one place and "required" in another, and "CAL 403" is explained nowhere. A wrong placeholder token yields 401 on every route, including the open ones. Fix: a table of which routes are gated, and a hackathon/test token path.
- SOURCE: the DMK context module filters loader errors, so a missing descriptor produces no runtime error; the app just blind-signs or refuses with 6a80. Fix: surface a "will blind-sign" signal before the device prompt (the for-wallets doc asks wallets to warn, but the SDK gives them nothing to warn with).
- DOCS: ERC-7730 registry PRs take weeks; the only dev-loading path (`@ledgerhq/cal-interceptor` + Flask) is a private package and targets Speculos test keys only. Nothing says "you cannot clear-sign your own contract on a retail device in a hackathon week".

## 6. Web Bluetooth (Flex) on Windows

- SPIKE/SOURCE: Flex BLE needs MITM bonding before any APDU; Chrome on Windows does not pair from the chooser unless `chrome://flags/#enable-web-bluetooth-confirm-pairing-support` is on, and DMK reconnect after every app-open link drop needs `#enable-web-bluetooth-new-permissions-backend`. Neither flag is mentioned anywhere in Ledger docs. Transport identifier is `WEB-BLE-RN-STYLE`, not `WEB-BLE`. The Stax/Flex BLE guide still cites LedgerJS `v8.3.0` for a package deleted in June 2026. Fix: a Windows section and an `isSupported()` that checks the flags.

## 7. Device app toolchain

- SPIKE: `ledgerblue --targetId` defaults to Nano S and is never auto-detected; `cargo ledger build --load` cannot run on a Windows host (needs nightly + arm-none-eabi tools), so the real Windows flow is build in Docker, load with `ledgerblue.runScript --elfFile ... --apdu --scp`, which no doc states.
- SOURCE: three device spellings (`nanos+` in ledger_app.toml, `nanosplus` in cargo-ledger, `nanosp` in Speculos/Ragger); `.cargo/config.toml` defaults to `apex_p`; recent cargo-ledger dropped the JSON manifest that the ledgerctl README still documents; `lib_nfc` doc is "TO BE COMPLETED"; Rust is mandated for new apps but NFC exists only in the C SDK.
- SPIKE: `pip install ledgerblue` on Windows pulls bleak plus nine winrt packages and nfcpy/libusb1 for a USB-only developer. Fix: extras.

## 8. Hardware security apps

- DOCS: the OpenPGP user guide's Windows section is literally "TODO"; the Security Key page has no setup content; the fact that FIDO credentials are seed-derived (restore 24 words = restore every credential) is undocumented and is a selling point.

## 9. Proof of Human and biometrics

- DOCS: Ledger's "Proof of Human" wording and the ETHGlobal prize text invite teams to add face/biometric gates, while Ledger Academy calls biometrics deepfake-able and the CHAO defines Proof of Human as hardware attestation. No developer doc says "a browser face check is not attestation; face may select a policy, only the Secure Screen approves". One paragraph would stop every team repeating the mistake.

## 10. Speculos + DMK (hardware-free path)

- SPIKE: `speculosTransportFactory(url, isE2E, deviceModelId)`: the 2nd and 3rd parameters are undocumented; without `deviceModelId` the discovered model is generic. Fix: document, and default it from Speculos `/model`.
- SPIKE: Speculos does not persist app NVRAM, so "Blind signing" (required for any EIP-712 without CAL descriptors) has to be toggled through the emulated UI on every container start with hand-found tap coordinates (Flex gear 440,50; toggle 415,353). Fix: a Speculos flag / REST call to preset app settings.
- SPIKE: Nano S Plus EIP-712 review shows only domain fields + "Message hash" by default; struct fields need the "Raw messages" app setting, which the DMK signer docs never mention. Flex shows every field after a "Blind signing ahead" warning. Fix: a per-device table in the `signTypedData` docs.
- SPIKE: the "Enable Transaction Check?" opt-in interrupts the first Flex sign flow (`web3ChecksOptIn` step) with no SDK option to pre-answer. Fix: a `SignerEthBuilder` option.
- SPIKE: status words are nested inconsistently (`error.originalError.errorCode` on `UnknownDeviceExchangeError`, `error.errorCode` on `EthAppCommandError`), and 0x6980 arrives as "UnknownError" with no hint that the app is mid-review from a previous flow. Fix: flat `errorCode` everywhere and a mapping for 0x6980.
- SPIKE: `--model nanosp` (Speculos) vs `nanos2` (release ELF) vs `nanoSP` (DMK `DeviceModelId`). Fix: accept all spellings.
- SPIKE: Speculos OCR `/events` splits sentences across events and emits no event for settings toggles on Nano; `speculos-device-controller` is not on npm. Fix: joined page text in `/events`, publish the controller.

## One concrete suggestion

Ship `wallet-cli doctor` (binary path, state dir, keychain backend, USB enumeration, Ledger Wallet running, BLE flags) and make `--device-timeout` apply to discovery. Those two changes remove the first hour of every Windows hackathon team.
