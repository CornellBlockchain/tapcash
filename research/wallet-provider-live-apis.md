# Ledger Wallet Provider / Wallet API / Ledger Live integration — research note

Date: 2026-10-10. Scope: what a dapp (or an AI agent) can do *through Ledger's own software* (Ledger Wallet, formerly Ledger Live; Ledger Wallet Provider SDK; Wallet API), versus talking to the device directly with DMK. Includes mobile (iOS/Android), Bluetooth and NFC facts for the Flex.

Legend: **VERIFIED** = read in a primary source (Ledger docs, npm registry, GitHub source). **INFERRED** = reasoned from verified facts or secondary sources. Everything here was gathered with WebFetch/WebSearch only; nothing was installed or run.

Naming: Ledger is mid-rename. "Ledger Live" → "Ledger Wallet"; the hardware "wallet" → "signer". Every doc page carries a banner saying the rename is in progress and legacy names remain. VERIFIED (banner on all `developers.ledger.com/docs/ledger-live/...` pages).

---

## 0. TL;DR for the hackathon

1. There are **three** distinct "Ledger software" integration surfaces, and they are not interchangeable:

   | Surface | What it is | Who runs the device transport | Needs Ledger approval? | Works from Node / headless? |
   |---|---|---|---|---|
   | **Ledger Wallet Provider** (`@ledgerhq/ledger-wallet-provider`, v2.0.0) | Browser Web-Component SDK that embeds Ledger's connect modal in *your* web page; exposes EIP-1193 (EVM) via EIP-6963 and a Solana Wallet Standard wallet. Built on DMK under the hood. | Your page, via Web HID / Web Bluetooth | **Yes**: `apiKey` + `dAppIdentifier` from Ledger partner program | **No** (browser only, no SSR, no mobile browsers) |
   | **Wallet API** (`@ledgerhq/wallet-api-client`, v1.16.0) | JSON-RPC-over-postMessage API for a **Live App**: your web page loaded *inside* Ledger Wallet (desktop or mobile) as an iframe/webview | Ledger Wallet (USB on desktop, BLE on mobile) | For public listing yes (invitation-only Discover). For local dev **no**: Developer mode + local manifest | No (needs Ledger Wallet running and a human in front of it). A **simulator** exists for browser-only dev. |
   | **dApp Browser** (manifest with `dapp` block) | Ledger Wallet hosts an *unmodified* EVM dapp and injects an EIP-1193 provider that signs via the device | Ledger Wallet | Same as above | No |

2. **For an AI-agent project, none of these is the right primary spine.** They all assume a human-driven web UI and (for Wallet Provider) a partner API key you probably cannot obtain before Oct 13. **DMK direct** (`@ledgerhq/device-management-kit` + `device-transport-kit-node-hid` + `device-signer-kit-*`) or Ledger's own **Wallet CLI** (`@ledgerhq/wallet-cli`, has `--output json` and an agent skill) are the agent-friendly paths. Ledger even ships a beta product for exactly the agent case: **Ledger Agent Intent** (see §7).
3. Where Wallet API / Wallet Provider *do* help: a polished **human-facing confirmation UI** in the demo (Ledger's own modal, Clear Signing + Transaction Check for free), or making your Live App appear *inside Ledger Wallet mobile* so the Flex is driven over **Bluetooth** by Ledger's app rather than your code.
4. **NFC**: no developer surface exists. The Flex's NFC is listed by Ledger only for "Ledger Recovery Key & Security Key" (FIDO2 tap). Neither DMK, Wallet API, nor Wallet Provider has an NFC transport. Ledger-to-Ledger NFC payments are not buildable with any public SDK in 3 days. VERIFIED (spec sheet) + VERIFIED (DMK transport list has no NFC).

---

## 1. Ledger Wallet Provider (`@ledgerhq/ledger-wallet-provider`)

Start page: https://developers.ledger.com/docs/ledger-wallet-provider/overview (the `.md`-suffixed variant of every docs page also serves and is easier to scrape).

### 1.1 What it is — VERIFIED
- "A web component SDK that embeds Ledger's official connect flow in your application." Direct signer connections (no Ledger Wallet app needed), Clear Signing and Transaction Check enabled automatically. Ledger maintains the USB (Web HID) and Bluetooth (Web BLE) transport layers.
- After `initializeLedgerProvider(...)` it announces, per chain family enabled in your partner config:
  - **Ethereum/EVM**: an EIP-1193 provider announced via EIP-6963 (`eip6963:announceProvider`).
  - **Solana (v2+)**: a Wallet Standard wallet (`@wallet-standard/app` `getWallets()`).
- Lit-based Web Components; "framework-agnostic". Repo: https://github.com/LedgerHQ/ledger-button-public (README title "Ledger Wallet Provider"; internal name "ledger-button"). Apache-2.0.

### 1.2 Hard limits — VERIFIED
- **Browser only.** "Cannot run in Node.js or any server-side environment." No SSR: load with dynamic import inside `useEffect`.
- **Mobile browsers not supported** ("Web HID and Web Bluetooth are unavailable on iOS and Android").
- Desktop browsers listed: Chrome 89+, Firefox 89+, Safari 14.1+, Edge 89+. Contradiction: Firefox and Safari do not ship Web HID / Web Bluetooth, and the DMK Skills page separately says WebHID "only runs in Chromium-based browsers". Treat **Chromium on desktop** as the real requirement. INFERRED.
- If the browser lacks Web HID/Web Bluetooth, `initializeLedgerProvider` returns a no-op and mounts nothing (API reference).
- Requires ES2020+, modern bundler (Vite, Webpack 5+).

### 1.3 Partner gating — VERIFIED, with a contradiction to flag
- Get-started v2: "Ledger's partner program enrollment is required for API keys." Configuration page: `apiKey` (string, **required**) "Your Ledger API key. You get it by enrolling in Ledger's partner program." `dAppIdentifier` (string, **required**) "so Ledger can validate the integration and enable remote services. Your partner configuration determines which blockchain families your dApp can use."
- A registration for a family not enabled for your `dAppIdentifier` is **silently skipped** at init (no throw). With a bogus identifier you may get no provider at all and no error.
- A search-engine summary of an older page claimed the key is "required for production use" and mentioned an `environment: 'staging' | 'production'` option; I could not load that page (`/build/configuration`, `/build/overview`, `/get-started` all 404 now). The current configuration page lists **no** `environment` option. Treat "works without a key in dev" as **UNVERIFIED, probably false** for v2.
- `LedgerButtonCore`'s constructor calls `initializeContext()` which "fetches the dApp config" via `GetDAppConfigUseCase`, i.e. a remote lookup keyed by your identifier. INFERRED: no key → no config → no providers.
- The public test-dapp `.env.example` has only `NEXT_PUBLIC_DISABLE_EVENT_TRACKING` and `NEXT_PUBLIC_ETHERSCAN_API_KEY`; no demo `apiKey`/`dAppIdentifier` is published. VERIFIED.
- **Action:** if you want this SDK, ask the Ledger mentors on Discord on Day 1 for a hackathon `dAppIdentifier` + `apiKey`. Without it the SDK is dead weight.

### 1.4 Versions — VERIFIED (npm registry, 2026-10-10)
- `@ledgerhq/ledger-wallet-provider` latest **2.0.0** (published 2026-10-02). Prior: 1.4.3 (2026-09-16), 1.4.2 and 1.4.1 (Aug 18), 1.4.0 (Jul 31), 1.3.2 (Jul 22), 1.3.1 (Jul 2), 1.3.0 (Jun 1). Dist-tags: `latest`, `develop`, `rc`, plus odd ones (`velora`, `jfrog`, `test`).
- 2.0.0 deps: `lit 3.3.3`, `motion ^12.23.6`, `lottie-web ^5.12.2`, `@lit/context 1.1.6`, `@floating-ui/dom ^1.8.0`, `class-variance-authority ^0.7.1`, `@ledgerhq/lumen-design-core ^0.1.28`, `@ledgerhq/ledger-wallet-provider-core 2.0.0`. Peer: `rxjs 7.8.2`.
- `@ledgerhq/ledger-wallet-provider-evm` latest **1.0.0**: deps `ethers ^6.17.0`, `inversify ^7.5.1`, `@ledgerhq/context-module 2.6.0`, `@ledgerhq/device-signer-kit-ethereum 1.18.1`; peers `rxjs 7.8.2`, `xstate 5.19.2`, `purify-ts 2.1.0`, `@ledgerhq/device-management-kit 1.10.0`, `@ledgerhq/ledger-wallet-provider-core 2.0.0`.
- `@ledgerhq/ledger-wallet-provider-solana` exists (docs); version not checked.
- v2 is **eight days old**. Expect rough edges; the GitHub repo README still says 1.0.0-rc.5; repo shows 0 stars / 5 open issues and is a public mirror of an internal `LedgerHQ/ledger-button` repo.
- Yarn 1 does not auto-install peers; use npm 7+ or pnpm.
- Publish attestation (Sigstore) is enabled; verify with `npm audit signatures` or pnpm `trustPolicy: no-downgrade`. VERIFIED (package-attestation page).

### 1.5 Install + init — VERIFIED (get-started/v2, configuration)
```bash
npm install @ledgerhq/ledger-wallet-provider
npm install @ledgerhq/ledger-wallet-provider-evm      # only if you support EVM
npm install @ledgerhq/ledger-wallet-provider-solana   # only if you support Solana
```
```ts
// client-side only (dynamic import in SSR frameworks)
import { initializeLedgerProvider } from "@ledgerhq/ledger-wallet-provider";
import { evmBlockchainProviderFactory } from "@ledgerhq/ledger-wallet-provider-evm";
// the docs say to import the stylesheet; exact path not shown (INFERRED)

const cleanup = initializeLedgerProvider({
  dAppIdentifier: "<from Ledger>",
  apiKey: "<from Ledger>",
  loggerLevel: "info",                            // fatal|error|warn|info|debug
  blockchainProviderFactories: [evmBlockchainProviderFactory],
  // UI options:
  target: document.body,                          // default
  hideButton: false,                              // true -> no floating button; providers still announced
  floatingButtonPosition: "bottom-right",         // bottom-left|bottom-center|top-*|middle-right
  // floatingButtonTarget: "#my-slot",
  walletTransactionFeatures: ["send", "receive", "swap", "buy", "earn", "sell"], // side-panel actions
  transactionConfirmationNotification: "tooltip", // or "toast"
});
// on unmount:
cleanup();
```
Note: the TS type marks `apiKey`/`dAppIdentifier`/`blockchainProviderFactories` optional, so the compiler won't catch omissions. VERIFIED (API reference).

### 1.6 EVM usage — VERIFIED (blockchains/evm, api-reference)
```ts
let ledger: any;
window.addEventListener("eip6963:announceProvider", (e: any) => {
  if (e.detail.info.name.toLowerCase().includes("ledger")) ledger = e.detail.provider; // LedgerEIP1193Provider
});
window.dispatchEvent(new Event("eip6963:requestProvider"));

const [addr] = await ledger.request({ method: "eth_requestAccounts" }); // opens Ledger modal
const sig  = await ledger.request({ method: "personal_sign", params: ["0x...", addr] });
const hash = await ledger.request({ method: "eth_sendTransaction", params: [{ from: addr, to, value }] });
```
- Handled locally (device): `eth_requestAccounts`, `eth_accounts`, `eth_chainId`, `eth_sendTransaction` (sign+broadcast), `eth_signTransaction` (sign only), `eth_signRawTransaction`, `eth_sendRawTransaction`, `eth_sign`, `personal_sign`, `eth_signTypedData`, `eth_signTypedData_v4`, `wallet_switchEthereumChain`.
- Forwarded to Ledger's node RPC: `eth_blockNumber`, `eth_getBalance`, `eth_getCode`, `eth_estimateGas`, `eth_call`, `eth_getTransactionReceipt`.
- Events: `accountsChanged`, `chainChanged`, `connect`, `disconnect`, `message`. Methods: `request`, `on`, `removeListener`, `isConnected()`, `disconnect(code=1000, message?, data?)`.
- Errors (`ProviderRpcError`): 4001 user rejected / closed modal; 4100 unauthorized (no connection, no account, address mismatch); 4200 unsupported method; 4900 disconnected; 4901 unsupported chain; -32602 invalid params; -32603 internal (provider busy, broadcast failed, blind signing disabled).
- Signing calls are **queued** while the modal is open; a second call while busy rejects with -32603 "Ledger Provider is busy".
- wagmi/viem/ethers: no official examples. Because it is standard EIP-6963, wagmi's injected discovery or viem `custom(ledger)` should just work. INFERRED.

### 1.7 Solana usage — VERIFIED (blockchains/solana)
- No discovery event; the wallet registers at init. Use `getWallets()` from `@wallet-standard/app`, pick the wallet whose name includes "ledger" and supports a `solana:` chain. Do **not** dispatch `wallet-standard:app-ready` yourself (can throw in listening wallets).
- Features: `standard:connect`, `solana:signMessage` (ed25519 sig), `solana:signTransaction` (you broadcast), `solana:signAndSendTransaction` (Ledger broadcasts).
- **Two-step signing quirk**: device reviews the tx, then the provider fetches a *fresh blockhash* and signs that version. Broadcast the returned bytes as-is; confirm by signature status, not by your original blockhash/`lastValidBlockHeight`. Blockhash unchanged for co-signed and durable-nonce txs.

### 1.8 Core package internals — VERIFIED (source skim)
`@ledgerhq/ledger-wallet-provider-core` exports `LedgerButtonCore` (inversify DI container). Public surface includes `connectToDevice(type)`, `disconnectFromDevice()`, `listAvailableDevices()`, `observeAccounts()`, `fetchAccountsFromCloudSync()` (Ledger Sync), `connectToLedgerSync()`, `jsonRpcRequest()`, `getChainId()/setChainId()`, consent / feature-flag / analytics methods, `isMobile()`, `isSupportedPlatform()`. It constructs a `ModalService`, so it is not designed to be headless. No signing methods on the core class itself (signing lives in the blockchain-provider layer). Undocumented; not a supported public API. INFERRED: don't build on it.

---

## 2. Wallet API (Live Apps inside Ledger Wallet)

Docs: https://developers.ledger.com/docs/ledger-live/discover/integration/wallet-api/introduction ; repo https://github.com/LedgerHQ/wallet-api (78 stars, Apache-2.0, monorepo with `packages/{client,client-react,core,server,simulator,manifest-validator,manifest-validator-cli}`). VERIFIED.

### 2.1 Model — VERIFIED
- A **Live App** is a web app that Ledger Wallet (desktop or mobile) loads inside a webview/iframe. It talks to the host over `window.postMessage` JSON-RPC using `WindowMessageTransport`. The host (Ledger Wallet) owns the accounts and the device connection; the Live App never touches USB/BLE itself.
- The library "is exclusively designed" for Live Apps inside Ledger Wallet; it does **not** support "web apps connected to Ledger signers through the Ledger Extension" or standalone use.
- Two integration flavours (same manifest system):
  1. **dApp Browser**: EVM-only. Manifest has a `dapp` block (`nanoApp`, `networks[]`); Ledger Wallet injects an EIP-1193 provider into your unmodified dapp. Networks limited to Ethereum mainnet, BSC, Arbitrum, Optimism, Base, Fantom, Polygon (per docs; the example lists a subset).
  2. **Wallet API**: any supported family; you call `client.account.list()`, `client.transaction.signAndBroadcast()` etc.
- **Discover listing is invitation-only** (partner intake form / discover@ledger.fr). **Local dev needs no approval**: Developer mode + load your own manifest.

### 2.2 Packages/versions — VERIFIED (npm registry)
- `@ledgerhq/wallet-api-client` latest **1.16.0**; deps `bignumber.js ^9.1.2`, `@ledgerhq/hw-transport ^6.36.0`, `@ledgerhq/wallet-api-core 2.1.0`.
- `@ledgerhq/wallet-api-client-react` (hooks + `WalletAPIProvider`).
- `@ledgerhq/wallet-api-simulator` (dev only). The React usage page says it "works only in server-side environments because it depends on `process`", which contradicts the simulator page ("develop and test from any browser"). Likely means it needs a bundler `process` polyfill. INFERRED.
- `@ledgerhq/wallet-api-server` exists (reference *wallet-side* implementation). Its README 404s on jsDelivr and raw GitHub; not documented for third parties.

### 2.3 Full RPC surface — VERIFIED from `packages/core/src/spec/methods.ts` and `spec/types/*.ts`
Methods in the current schema enum (16): `account.getMaxSpendable`, `account.getPublicKey`, `account.list`, `account.receive`, `account.request`, `currency.list`, `device.close`, `device.exchange`, `device.transport`, `message.sign`, `transaction.sign`, `transaction.signRaw`, `transaction.signAndBroadcast`, `wallet.capabilities`, `wallet.info`, `wallet.userId`.

Type files also exist for `bitcoin.getAddress/getAddresses/getPublicKey/getXPub/signPsbt`, `device.open`, `device.select`, `exchange.start/complete`, `storage.get/set`, `custom.request`. They are present as types/client modules but not all are in the `methods.ts` enum, so availability depends on host version. PARTIALLY VERIFIED.

Permission strings used in a manifest (Live App creation example): `account.list`, `account.receive`, `account.request`, `currency.list`, `message.sign`, `transaction.sign`, `transaction.signAndBroadcast`, `wallet.capabilities`, `wallet.info`, `wallet.userId`. VERIFIED.

Client module signatures (VERIFIED from source):
```ts
client.account.list({ currencyIds?: string[] }): Promise<Account[]>
client.account.request({ currencyIds?, showAccountFilter?, drawerConfiguration?, useCase?, uiUseCase? }): Promise<Account>  // opens host account picker
client.account.receive(accountId): Promise<string>                  // host verifies address on device
client.account.getPublicKey(accountId, derivationPath?): Promise<string>
client.account.getMaxSpendable(accountId): Promise<BigNumber>
client.transaction.sign(accountId, tx: Transaction, options?, meta?): Promise<Buffer>
client.transaction.signRaw(accountId, rawTxHex: string, broadcast?: boolean, options?, meta?): Promise<{ signedTransactionHex; transactionHash? }>
client.transaction.signAndBroadcast(accountId, tx, options?, meta?): Promise<string /* txHash */>
client.message.sign(accountId, message: Buffer, options?, meta?): Promise<Buffer>
client.wallet.userId(): Promise<string>; client.wallet.info(); client.wallet.capabilities(): Promise<string[]> // @beta
client.device.transport({ appName?, allowManager?, appVersionRange?, firmwareVersionRange?, seeded?, devices? }): Promise<HWTransport> // @ledgerhq/hw-transport-compatible raw APDU channel
client.device.open(...), client.device.select(...)
```
`device.transport` is notable: a Live App can get a **raw `@ledgerhq/hw-transport`-compatible channel to the device through Ledger Wallet**, with the host handling USB/BLE. That is the only Ledger-sanctioned way to send custom APDUs to a Flex over Bluetooth on iOS without writing a native app. Method VERIFIED; the consequence is INFERRED and untested.

`EthereumTransaction` (VERIFIED from `families/ethereum/types.ts`): `TransactionCommon & { family: "ethereum"; nonce?; data?: Buffer; gasPrice?; gasLimit?; maxPriorityFeePerGas?; maxFeePerGas?; sponsored?: boolean }`. `TransactionCommon` (amount, recipient, …) not read.

Families in core (27 dirs, VERIFIED): aleo, algorand, aptos, bitcoin, cardano, casper, celo, cosmos, crypto_org, elrond, ethereum, filecoin, hedera, internet_computer, kaspa, near, neo, polkadot, ripple, solana, stacks, stellar, sui, tezos, ton, tron, vechain. The docs page lists only 18 (stale). "Availability depends on the wallet and the app's permissions."

### 2.4 Minimal code — VERIFIED (core/usage, react/usage)
```bash
npm install @ledgerhq/wallet-api-client            # + @ledgerhq/wallet-api-client-react for hooks
```
```ts
import { WalletAPIClient, WindowMessageTransport } from "@ledgerhq/wallet-api-client";
const transport = new WindowMessageTransport();
transport.connect();
const client = new WalletAPIClient(transport);
const accounts = await client.account.list({ currencyIds: ["ethereum"] });
const hash = await client.transaction.signAndBroadcast(accounts[0].id, {
  family: "ethereum", amount: new BigNumber("1000000000000000"), recipient: "0x…",
});
transport.disconnect();
```
React: wrap the app in `<WalletAPIProvider transport={transport}>`; in dev swap in `getSimulatorTransport(profiles.STANDARD)` from `@ledgerhq/wallet-api-simulator`.

### 2.5 Manifest + loading — VERIFIED (manifest page, developer-mode page, live-app-creation/manifest)
```json
{
  "$schema": "https://live-app-catalog.ledger.com/schema.json",
  "id": "myapp", "name": "My App",
  "url": "http://localhost:3000/", "homepageUrl": "http://localhost:3000/",
  "platform": ["ios", "android", "desktop"],
  "apiVersion": "^2.0.0", "manifestVersion": "2", "branch": "stable",
  "categories": ["tools"], "currencies": "*",
  "content": { "shortDescription": { "en": "…" }, "description": { "en": "…" } },
  "permissions": ["account.list","account.request","account.receive","currency.list","message.sign","transaction.sign","transaction.signAndBroadcast","wallet.capabilities","wallet.info","wallet.userId"],
  "domains": ["http://", "https://"],
  "visibility": "complete"
}
```
- **Desktop**: Ledger Wallet ≥ 2.32. Settings → About → click version number 10× → Developer tab appears → enable "platform dev tools" → "Add a local app" → Browse → pick manifest. App appears in Discover. Disabling dev mode = reinstall.
- **Mobile**: local manifest loading documented for **Android only** (Settings → Developer → "Load Platform Manifest" → paste JSON). Replace `localhost` with your LAN IP (same Wi-Fi band) or an ngrok/localtunnel URL; `domains` must include `http://`. **No documented iOS local-load path.** VERIFIED (dapp-browser manifest page + developer-mode page). INFERRED: on iPhone you can only run Live Apps Ledger has published.
- `branch: "soon"` renders "Coming soon" and is unusable; `debug`/`experimental` need the matching Developer toggles.
- `dapp.networks[].nodeURL` is overridden by Ledger in production; for local testing supply your own RPC.

### 2.6 Mobile + Flex over Bluetooth via Wallet API — INFERRED
Ledger Wallet mobile pairs the Flex over BLE 5.2 (iOS 14+ / Android 10+; iPhones have no USB path). A Live App loaded in Ledger Wallet mobile therefore signs on the Flex **over Bluetooth with zero BLE code on your side**. On Android you can load your own manifest; on iOS you cannot. Support articles (`support.ledger.com/article/360021488913-zd`, `360019138694-zd`) render client-side and returned empty bodies to WebFetch; BLE facts come from the shop spec sheet (VERIFIED) and search snippets of those articles (INFERRED).

---

## 3. NFC on the Flex — VERIFIED gap
- Ledger's spec sheet (shop.ledger.com/products/ledger-flex): "NFC — Ledger Recovery Key & Security Key". Nothing else. The Security Key app is FIDO2/WebAuthn: tap phone to log in; USB on desktop.
- DMK transports (https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/transports): Web HID, Web BLE, RN HID, RN BLE (`react-native-ble-plx`), Node HID (`node-hid`), Speculos. **No NFC transport.** Wallet Provider: USB + Bluetooth only. Wallet API: host-mediated.
- Ledger Wallet mobile pairing is BLE, not NFC.
- Conclusion: "swipe Ledger-to-Ledger over NFC" (starter idea #2) has no public SDK path. Devices also cannot talk to each other; both need a phone/computer host. The nearest buildable analogue is a **tap-to-approve UX where the Flex is the FIDO2 security key** (NFC tap = human approval) and the money moves over a normal chain tx signed via BLE or USB. INFERRED.

---

## 4. Ledger Wallet (Live) as an automation surface — VERIFIED gaps
- No public local HTTP/IPC API on Ledger Wallet desktop for third parties. Searched; nothing.
- Deep links exist (`ledgerlive://discover/<liveAppId>?…`, `ledgerlive://swap?status=…`) but are documented only for the swap/sell provider flows. Routes like `send`/`receive`/`account` are undocumented (the desktop `useDeeplink.ts` path I tried 404'd). INFERRED: an agent could open Ledger Wallet to *your Live App* via `ledgerlive://discover/<id>` once the manifest is loaded; untested.
- `ledger-live` npm CLI (v21.32.1, from the ledger-live monorepo): `deviceInfo`, `getAddress`, `sync`, `send --recipient --amount [--disable-broadcast]`, `signMessage`, `broadcast`, `receive`, `app install/open`, `--device <hidPath>`, `-c <currency>`. Experimental, "as is". Talks to the device directly (not through Ledger Wallet). Ledger's newer **`@ledgerhq/wallet-cli`** supersedes it for agents (§7).

---

## 5. Decision: Wallet Provider / Wallet API vs DMK direct for an AI-agent project

| Need | Wallet Provider | Wallet API (Live App) | DMK direct | `@ledgerhq/wallet-cli` |
|---|---|---|---|---|
| Run from a Node/Python agent process | No | No | **Yes** (`node-hid`) | **Yes** (`--output json`) |
| Windows 11 host | Browser only (Chromium) | Ledger Wallet desktop | Yes (node-hid) | Docs: Windows "WSL recommended" |
| Nano S Plus (USB) | Yes (Web HID) | Yes | Yes | Yes |
| Flex over Bluetooth from PC | Web BLE in Chromium | No (desktop LW is USB) | Web BLE only (no Node BLE transport) | No |
| Flex over Bluetooth on phone | No (mobile browsers unsupported) | **Yes**, via Ledger Wallet mobile (Android loadable, iOS published-only) | RN BLE transport → you write a React Native app | No |
| Needs Ledger-issued credentials | **apiKey + dAppIdentifier** | Only for public listing | `originToken` optional (only for Transaction Check) | No |
| Clear Signing / Tx Check UI | Built in | Built in (host) | Clear Signing via context-module; Tx Check needs originToken | Built in |
| Multi-chain | EVM + Solana | 27 families | eth, btc, solana signer kits (+ others) | btc, eth, solana |
| Build-time risk (3 days) | High (8-day-old v2, key gating) | Medium (dev mode works; iOS blocked) | Low–Medium (well-trodden, Skills available) | Low |

**Recommendation:** agent core = **DMK direct** (or `wallet-cli` for speed) with the device as the human-in-the-loop gate. Optionally add a **Live App** (Wallet API) as the "approve on your phone over Bluetooth" surface for the Flex demo on Android. Skip Wallet Provider unless a mentor hands you a key on Day 1; even then it only adds a nicer connect modal to a web dapp, which is not the agent story the judges asked for.

---

## 6. DMK direct — what you'd use instead (brief, VERIFIED)
```bash
npm i @ledgerhq/device-management-kit @ledgerhq/device-transport-kit-node-hid @ledgerhq/device-signer-kit-ethereum
```
```ts
const dmk = new DeviceManagementKitBuilder().addTransport(nodeHidTransportFactory).build();
// discover -> connect -> sessionId
const signerEth = new SignerEthBuilder({ dmk, sessionId, originToken: "…" }).build(); // originToken optional
const { observable, cancel } = signerEth.signTransaction("44'/60'/0'/0/0", serializedTx);
observable.subscribe((state) => {
  // state.status: NotStarted | Pending (intermediateValue.requiredUserInteraction) | Stopped | Completed (output {r,s,v}) | Error
});
```
Signer-eth also has `getAddress(path, { checkOnDevice })`, `signMessage`, `signTypedData` (EIP-712), `signDelegationAuthorization` (EIP-7702), `verifySafeAddress`. `requiredUserInteraction` values: `SignTransaction`, `SignPersonalMessage`, `SignTypedData`, `SignDelegationAuthorization`, `VerifyAddress`, `VerifySafeAddress`, `UnlockDevice`, `ConfirmOpenApp`, `Web3ChecksOptIn`, `None`. These are exactly the hooks a voice agent needs to say "please confirm on your Ledger". DMK Skills install: `npx skills add ledgerhq/agent-skills -s ledger-dmk-implementation dmk-intent-vocabulary dmk-business-logic`.

---

## 7. Ledger's own agent products (context for "usefulness for Ledger" scoring) — VERIFIED
- **Ledger Wallet CLI** `@ledgerhq/wallet-cli`: `genuine-check`, `account discover <bitcoin|ethereum|solana>`, `balances`, `operations`, `receive`, `send <label> --to <addr> --amount '0.1 ETH' [--dry-run] [--data] [--memo] [--fee-per-byte --rbf]`, `swap quote/execute/status`, `earn yields/positions/deposit/withdraw`, `ring init/encrypt/decrypt/keys/destroy`; every command `--output json`; `wallet-cli skill install --agent claude|cursor|codex`. USB only. Platforms: macOS, Linux, Windows ("WSL recommended").
- **Ledger Agent Intent** (beta, https://agent-intent.ledger-test.com/): a remote agent registers an identity key in your Trustchain (Ledger Sync device app ≥ 1.3.0), proposes "intents" (send only today; swap + Solana in development), you approve on the signer via a web queue (Chromium WebHID/WebBLE; Safari/Firefox unsupported). Supports Nano Gen 5, Flex, Stax, Nano X, Nano S Plus. Enroll: `wallet-cli agent-intent enroll --app-url https://agent-intent.ledger-test.com/`. Lists Claude Code / Cursor / Codex as "supported, less benefit" local agents; recommends remote autonomous agents. This is the closest Ledger product to starter idea #1; a hackathon project should differentiate (voice + face gate on the *proposal* side, Ledger on the *approval* side) rather than rebuild it.

---

## 8. Open questions / things to ask mentors
1. Can hackathon teams get a Wallet Provider `dAppIdentifier` + `apiKey` (and an `originToken` for Transaction Check) during build week?
2. Is there any iOS path to load a local Live App manifest, or staging-catalog access?
3. Does Ledger Wallet desktop on Windows expose any BLE path to the Flex, or is desktop strictly USB? (Spec sheet implies USB-C "for desktop use".)
4. Is `device.transport` (raw APDU via Wallet API) permitted for third-party Live Apps in Developer mode, and does it work on Ledger Wallet mobile?
5. Is NFC on Flex ever going to be exposed to developers (even read-only presence detection)?
6. Developer mode docs say Ledger Wallet ≥ 2.32; does it still work identically in current builds?
7. Where is the Wallet Provider `environment: staging|production` option the search index remembers? Was it removed in v2?

---

## 9. Sources (all fetched 2026-10-10)
Ledger Wallet Provider:
- https://developers.ledger.com/docs/ledger-wallet-provider/overview (and `.md`)
- https://developers.ledger.com/docs/ledger-wallet-provider/introduction
- https://developers.ledger.com/docs/ledger-wallet-provider/requirements.md
- https://developers.ledger.com/docs/ledger-wallet-provider/get-started/v2.md
- https://developers.ledger.com/docs/ledger-wallet-provider/blockchains/evm.md
- https://developers.ledger.com/docs/ledger-wallet-provider/blockchains/solana.md
- https://developers.ledger.com/docs/ledger-wallet-provider/configuration.md
- https://developers.ledger.com/docs/ledger-wallet-provider/api-reference.md
- https://developers.ledger.com/docs/ledger-wallet-provider/package-attestation.md
- https://registry.npmjs.org/@ledgerhq/ledger-wallet-provider
- https://registry.npmjs.org/@ledgerhq/ledger-wallet-provider-evm/latest
- https://github.com/LedgerHQ/ledger-button-public
- https://raw.githubusercontent.com/LedgerHQ/ledger-button-public/develop/apps/test-dapp/.env.example
- https://raw.githubusercontent.com/LedgerHQ/ledger-button-public/develop/packages/ledger-button-core/src/api/LedgerButtonCore.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-button-public/develop/packages/ledger-button-core/README.md
- 404 at time of writing: `/ledger-wallet-provider/get-started(.md)`, `/intro`, `/getting-started`, `/build/overview`, `/build/configuration`

Wallet API / Ledger Wallet (Live):
- https://developers.ledger.com/docs/ledger-live/discover/integration/wallet-api/introduction.md
- https://developers.ledger.com/docs/ledger-live/discover/integration/wallet-api/core/usage.md
- https://developers.ledger.com/docs/ledger-live/discover/integration/wallet-api/react/usage.md
- https://developers.ledger.com/docs/ledger-live/discover/integration/wallet-api/simulator/usage.md
- https://developers.ledger.com/docs/ledger-live/discover/integration/wallet-api/appendix/families.md
- https://developers.ledger.com/docs/ledger-live/discover/integration/wallet-api/examples/live-app-creation/manifest.md
- https://developers.ledger.com/docs/ledger-live/discover/integration/dapp-browser/manifest.md
- https://developers.ledger.com/docs/ledger-live/discover/references/developer-mode.md
- https://developers.ledger.com/docs/ledger-live/discover/beginner/live-app.md
- https://developers.ledger.com/APIs/wallet-api/introduction
- https://developers.ledger.com/APIs/wallet-api/appendix/working-with-ledger-live
- https://github.com/LedgerHQ/wallet-api
- https://raw.githubusercontent.com/LedgerHQ/wallet-api/main/spec/README.md ; …/spec/rpc/README.md
- https://api.github.com/repos/LedgerHQ/wallet-api/contents/packages ; …/packages/client/src ; …/packages/client/src/modules ; …/packages/core/src/families ; …/packages/core/src/spec ; …/packages/core/src/spec/types
- https://raw.githubusercontent.com/LedgerHQ/wallet-api/main/packages/client/src/WalletAPIClient.ts ; …/modules/{Account,Transaction,Message,Wallet,Device}.ts
- https://raw.githubusercontent.com/LedgerHQ/wallet-api/main/packages/core/src/spec/methods.ts
- https://raw.githubusercontent.com/LedgerHQ/wallet-api/main/packages/core/src/spec/types/DeviceTransport.ts
- https://raw.githubusercontent.com/LedgerHQ/wallet-api/main/packages/core/src/families/ethereum/types.ts
- https://registry.npmjs.org/@ledgerhq/wallet-api-client ; …/latest
- https://developers.ledger.com/docs/exchange/swap/flow/detailed-technical-flows (deep links; via search snippet)

DMK / AI tools / CLI:
- https://developers.ledger.com/llms.txt
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/transports.md
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/how_to_use_a_signer.md
- https://cdn.jsdelivr.net/npm/@ledgerhq/device-signer-kit-ethereum/README.md
- https://developers.ledger.com/docs/ai-tools/overview.md
- https://developers.ledger.com/docs/ai-tools/ledger-cli.md
- https://developers.ledger.com/docs/ai-tools/ledger-dmk-skills.md
- https://developers.ledger.com/docs/ai-tools/agent-intent.md
- https://cdn.jsdelivr.net/npm/ledger-live@21.32.1/README.md ; https://registry.npmjs.org/ledger-live

Hardware / mobile:
- https://shop.ledger.com/products/ledger-flex (spec sheet: BLE 5.2, NFC for Recovery Key & Security Key, OS compat)
- https://support.ledger.com/article/360021488913-zd ; …/360019138694-zd ; …/12350325732893-zd (bodies not retrievable via WebFetch; cited via search snippets only)
