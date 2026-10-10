# Gap: what clear-signs on a retail Flex / Nano S Plus WITHOUT a Ledger `originToken`

> **Correction (2026-10-10, source audit).** `/gated_dapps` is open (358 entries, probed 2026-10-10), and without an origin token gated contracts show a 'There is a safer way to sign' interstitial on blind paths, Nano S Plus included (l.104, l.238). See `source-audit.md` §1 and §2 (M09).

Date: 2026-10-10. Scope: `@ledgerhq/device-signer-kit-ethereum` 1.18.1 + `@ledgerhq/context-module` 2.6.0 (what npm `latest` resolves to today), `LedgerHQ/device-sdk-ts` `develop` @ `1a3f860` (2026-10-09), `LedgerHQ/app-ethereum` `develop` @ `5a48940` (2026-09-22). No hardware touched; nothing installed. Evidence = source read in a sparse clone + published npm tarballs + live HTTP probes against Ledger's production CAL from this machine.

Legend: **VERIFIED** = read in primary source or observed on the wire. **INFERRED** = follows from verified facts but not observed on a device.

---

## 0. Verdict (what the demo can put on the device screen with no partner token)

| Payload | Without `originToken`, retail device, stock Ethereum app | Confidence |
|---|---|---|
| Native ETH transfer (empty `data`) on mainnet / Sepolia / Base Sepolia | **Clear-signed.** App shows Amount, To, Max fees, network from its own tx parser; no CAL data needed. Network name/ticker for Base Sepolia and Sepolia comes from CAL `/networks`, which is **open** (200, no token). | VERIFIED (app source + CAL probe); on-screen rendering INFERRED |
| ERC-20 `transfer(address,uint256)` / `approve` of a token **in Ledger's CAL** (USDC mainnet, Sepolia `tUSDC` `0x1c7D…7238`, Base Sepolia `tUSDC` `0x036C…CF7e`) | **Clear-signed.** Signer fetches the signed token descriptor from CAL `/tokens` (**open**, 200 no token), sends `PROVIDE ERC 20 TOKEN INFORMATION`, the app's built-in ERC-20 plugin renders `Send <amount> <ticker>` + `To`. Blind-signing setting not required. | VERIFIED chain to the APDU; on-screen text INFERRED (matches Ledger's own tester fixture `raw-erc20.json` expecting `["USDC","5000"]`) |
| ERC-20 transfer of a token **not** in CAL (a token you deployed) | **Blind-signed, and refused unless "Blind signing" is enabled** (app: plugin `FALLBACK` -> generic review -> `dataPresent && !dataAllowed` -> error screen). Amount shows as `0 ETH`, To = token contract. | VERIFIED (app source) |
| Any other contract call (ERC-7730 calldata descriptors, 1inch/Uniswap plugins, Safe, proxies) | **Blind-signed.** All of these come from CAL `/dapps`, which returns **HTTP 403 with no token** and **401 with a wrong token**. Requires "Blind signing" enabled on the app, shows the blind-signing warning. | VERIFIED (probe + source) |
| EIP-712 `signTypedData` with an ERC-7730 EIP-712 descriptor (e.g. USDC `TransferWithAuthorization`, Permit2) | **No ERC-7730 labels** (filters come from `/dapps` -> 403). Falls to **BASIC mode** = raw field-by-field review; the app **refuses** BASIC mode unless *either* "Blind signing" *or* "Raw messages" (`verbose_eip712`) is enabled, and shows the blind-signing warning. Readable, but not "clear signing". | VERIFIED (app source + probe) |
| EIP-712 legacy fallback (old app, or device rejected context) | Hash-only (`domainHash`+`messageHash`) via `SignEIP712Command` v0; **requires "Blind signing" enabled.** | VERIFIED (signer + app source) |
| `personal_sign` / `signMessage` (EIP-191) | **Not a clear-signing feature at all**; app displays the message text (hex if non-printable). No CAL, no token, no setting. | VERIFIED (prior note clear-signing-erc7730.md §5; signer path `SendSignPersonalMessageTask` never touches the context module) |
| Transaction Check (Web3 Checks) on Flex | **Unavailable.** `transaction-checks/v3` returns **403** without a token. Signer drops the error context; the app signs without a simulation result (no threat/risk screen). Nano S Plus has no Transaction Check anyway. | VERIFIED (probe + signer source); "no extra screen" INFERRED |
| Trusted names (ENS/CAL names for `to`) | Metadata service `nft.api.live.ledger.com/v2/names/...` answered **200 without a token** in a probe. The migration doc claims the token is needed for trusted names. Treat as **probably works**. | VERIFIED 200 on the wire; device acceptance INFERRED |

**One sentence:** the only things the partner token unlocks are the `/dapps` family (ERC-7730 calldata + EIP-712 descriptors + legacy dApp plugin bindings) and Transaction Check; token metadata, PKI certificates, dynamic networks, NFT metadata and trusted names are served without it. So native ETH and CAL-listed ERC-20 transfers are safe demo payloads; arbitrary contract calls and ERC-7730-labelled EIP-712 are not.

---

## 1. How `originToken` is actually sent — VERIFIED (source)

There is exactly **one** HTTP client for the whole context module, and the token is just a header on it. No loader "requires" the token in code; what differs is what Ledger's gateway does per endpoint.

`packages/signer/context-module/src/shared/constant/HttpHeaders.ts`:
```ts
export const LEDGER_CLIENT_VERSION_HEADER = "X-Ledger-Client-Version";
export const LEDGER_ORIGIN_TOKEN_HEADER = "X-Ledger-Client-Origin";
```

`packages/signer/context-module/src/shared/network/networkClientFactory.ts`:
```ts
export const networkClientFactory = (config: ContextModuleServiceConfig) =>
  new DmkNetworkClient({
    headers: {
      [LEDGER_CLIENT_VERSION_HEADER]: `context-module/${PACKAGE.version}`,
      ...(config.originToken && {
        [LEDGER_ORIGIN_TOKEN_HEADER]: config.originToken,
      }),
    },
  });
```
Empty string => header omitted. All `Http*DataSource` classes inject this single `networkTypes.NetworkClient` (grep: every `this.http.get/post` in `modules/ethereum/**` and `modules/multichain/**`). Same code is in the published 2.6.0 tarball (`lib/cjs/src/shared/network/networkClientFactory.js`).

`ContextModuleBuilder.ts` (develop and 2.6.0): `originToken: originToken ?? ""`. **It does not throw.** `build()` only checks `setChain()` was called. `SignerEthBuilder` passes `originToken` straight through; type is `originToken?: string`.

### Version history of "required" — VERIFIED (npm tarballs)
| context-module | behaviour |
|---|---|
| 1.4.0 (2025-05-13) .. 1.14.1 (2026-02-13) | `build()` throws `"Origin token is required"` when missing (confirmed in 1.9.0 tarball; introduced by PR #807 "Add origin token for transaction checks call", merged 2025-04-18) |
| 1.17.1 (2026-04-29) onward, incl. 2.0.0 .. 2.6.0 | `originToken ?? ""`, no throw (npm dist-tag `no-issue-avoid-breaking-change-context-module` dated 2026-04-29 is the change) |

signer-eth peer ranges: 1.15.x -> context-module ^1.17.x; 1.16.0 -> ^2.0.0; 1.18.0 -> ^2.5.0; **1.18.1 -> ^2.6.0**. So with 1.18.x you never hit the throw. The developer-portal migration page 1.3.3->1.4.0 ("originToken is now required", troubleshooting "Origin token is required" error) describes the 2025 behaviour and is **stale** for current versions.

---

## 2. Live probe of Ledger's production CAL (2026-10-10, from this machine, plain `curl`) — VERIFIED on the wire

Base URL `https://global.api.prd.ledger.com/cal/v1` (the `DEFAULT_CAL_URL` in `ContextModuleBuilder.ts`). "bogus" = `-H 'X-Ledger-Client-Origin: hackathon-bogus-token'`.

| Endpoint (as the data source builds it) | no header | bogus header |
|---|---|---|
| `/tokens?chain_id=1&contract_address=0xA0b8…eB48&output=descriptor` (USDC) | **200**, `{"ticker":"USDC","decimals":6,"descriptor":{"data":"55534443a0b8…","signatures":{"prod":"3045…"}}}` | **401** `{"message":"Unauthorized"}` |
| `/tokens?chain_id=11155111&contract_address=0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238` (Sepolia USDC) | **200**, `id: ethereum_sepolia/erc20/usdc`, ticker `tUSDC`, has `prod` signature | 401 |
| `/tokens?chain_id=84532&contract_address=0x036CbD53842c5426634e7929541eC2318f3dCF7e` (Base Sepolia USDC) | **200**, `id: base_sepolia/erc20/usd_coin`, ticker `tUSDC`, has `prod` signature | 401 |
| `/tokens?chain_id=1&contract_address=0xdAC1…1ec7` (USDT) | 200 | – |
| `/tokens?chain_id=11155111&contract_address=0x…1234` (random) | 200 `[]` (empty => loader returns ERROR context "no token metadata") | – |
| `/dapps?output=descriptors_calldata&chain_id=1&contracts=0xC02a…6Cc2&ref=branch:main` (WETH ERC-7730 calldata) | **403**, empty body | **401** |
| `/dapps?output=descriptors_eip712_v2&chain_id=8453&contracts=0x8335…2913` (USDC Base EIP-712) | **403** | 401 |
| `/dapps?output=b2c,b2c_signatures,abis&chain_id=1&contracts=0x1111…0582` (1inch plugin binding) | **403** | – |
| `/dapps?…&ref=branch:next` | **403** (so `branch: "next"` is not a back door) | – |
| `/certificates?output=descriptor&target_device=flex&public_key_usage=token_meta&latest=true` | 200 `[]` | 401 |
| `/certificates?output=id,target_device,…&latest=true` | **200**, 11.9 KB list (e.g. `calldata/cal_calldata_key/flex/0.0.1`) | 401 |
| `/networks?output=descriptors&chain_id=84532` / `11155111` / `8453` | **200**, signed `network` descriptors per device (`stax`, …), `prod` signatures, names "Base Sepolia", "Ethereum Sepolia", "Base" | – |
| `https://global.api.prd.ledger.com/transaction-checks/v3/ethereum/scan/transaction` (POST) | **403** | – |
| `https://nft.api.live.ledger.com/v1/ethereum/1/contracts/0xBC4C…f13D` (NFT metadata) | **200** signed payload | – |
| `https://nft.api.live.ledger.com/v2/names/ethereum/1/forward/vitalik.eth?types=eoa&sources=ens&challenge=0x00000000` (trusted name) | **200** signed descriptor | – |

403 responses carry `x-gravitee-*` headers: the gate is Ledger's API gateway, per-route. 401 on a *bad* token everywhere (even on the open routes) means: **never send a made-up token; an empty string is strictly better than a wrong one.**

Reproduce:
```sh
CAL=https://global.api.prd.ledger.com/cal/v1
curl -s -o /dev/null -w '%{http_code}\n' "$CAL/tokens?chain_id=84532&contract_address=0x036CbD53842c5426634e7929541eC2318f3dCF7e&output=descriptor"   # 200
curl -s -o /dev/null -w '%{http_code}\n' "$CAL/dapps?output=descriptors_calldata&chain_id=1&contracts=0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2&ref=branch:main"  # 403
```

---

## 3. Loader-by-loader matrix (Ethereum chain, default loaders) — VERIFIED source + probe

| Loader / data source | Endpoint | Token needed? | What the device gets | If missing |
|---|---|---|---|---|
| `TokenContextLoader` -> `HttpTokenDataSource` (selectors `transfer 0xa9059cbb`, `approve 0x095ea7b3`) | CAL `/tokens` | **No** | `ETHEREUM_TOKEN` payload = `tickerLen‖data‖signatures[mode]` -> `ProvideTokenInformationCommand` | ERROR context dropped; app plugin falls back -> blind sign |
| `CalldataContextLoader` -> `HttpCalldataDescriptorDataSource` (ERC-7730 generic parser; skipped on Nano S) | CAL `/dapps?output=descriptors_calldata` | **Yes (403)** | `ETHEREUM_TRANSACTION_INFO` + `FIELD_DESCRIPTION` + `ENUM`, plus PKI cert | blind sign |
| `HttpTypedDataDataSource.getTypedDataFilters` (EIP-712 ERC-7730) | CAL `/dapps?output=descriptors_eip712_v2` | **Yes (403)** | `SendEIP712FilteringCommand` Activation + MessageInfo + per-field filters | BASIC mode (raw fields) with blind-signing warning |
| `HttpExternalPluginDataSource` (legacy dApp plugins: 1inch, Paraswap…) | CAL `/dapps?output=b2c,b2c_signatures,abis` | **Yes (403)** | `SetExternalPluginCommand` | blind sign |
| `HttpGatedDescriptorDataSource` (gated signing) | CAL `/gated_dapps` | not probed; same `/dapps` family -> INFERRED yes | `ProvideGatedSigningCommand` | n/a |
| `HttpDynamicNetworkDataSource` | CAL `/networks?output=id,descriptors,icons` | **No** | `ProvideNetworkConfigurationCommand` (name, ticker, icon for chains not in app's built-in table) | app shows chain ID + `???` ticker (`g_unknown_ticker`) |
| `HttpPkiCertificateDataSource` | CAL `/certificates` | **No** | `LoadCertificateCommand` | contexts that need a cert fail |
| `HttpNftDataSource` | `nft.api.live.ledger.com/v1/ethereum/{chain}/contracts/…` | **No** | `ProvideNFTInformationCommand` / `SetPluginCommand` | blind sign for ERC-721/1155 |
| `HttpTrustedNameDataSource` | `nft.api.live.ledger.com/v2/names/ethereum/{chain}/{forward|reverse}/…` | **No at HTTP layer** (doc says yes) | `ProvideTrustedNameCommand` | address shown raw |
| `HttpProxyDataSource` / `HttpSafeProxyDataSource` / `HttpSafeAccountDataSource` | metadata service `/v2/ethereum/{chain}/contract/proxy/delegate`, … | not probed | proxy/safe info | n/a |
| `HttpTransactionCheckDataSource` (only when app reports `web3ChecksEnabled`) | `transaction-checks/v3…` | **Yes (403)** | `ProvideWeb3CheckCommand` | no simulation result |
| `HttpBlindSigningReporterDatasource` / `HttpSignReporterDatasource` | `blind-signing.api.ledger.com/ingest` (POST) | n/a (telemetry) | nothing | nothing |

How the signer treats a failed loader (`BuildBaseContexts.ts`): `clearSignContexts.filter(type !== ERROR)`; the count goes into `contextErrorCount`, the success list is sent via `ProvideTransactionContextsTask`, then `SendSignTransactionTask`. **No exception, no observable error** — that is the "silently degrades" the dmk-business-logic skill describes. The only runtime signals you get are (a) the app's `6a80` status when blind signing is disabled, and (b) `BlindSigningDetectionTask` (`isBlindSign = usedFallback || !hasContext || only metadata-type contexts`) which feeds the reporter and is **not** exposed in `SignTransactionDAOutput` (that is just `Signature`).

---

## 4. Why native ETH and CAL-listed ERC-20 clear-sign with no token — VERIFIED source

### Native transfer
`app-ethereum/src/features/sign_tx/logic_sign_tx.c`: when `pluginType == PLUGIN_TYPE_NONE` the app itself formats `destination` and `value` ("Prepare destination address and amount to display"). The `dataPresent && !N_storage.dataAllowed` blind-signing gate only fires if there is calldata. For an empty `data` field nothing is gated and nothing is fetched except (optionally) trusted name + network descriptor. Network name/ticker: `src/network.c` has a built-in table (chain 1 "Ethereum/ETH", 10, 56, 137 "POL", …; Sepolia 11155111, Base 8453 and Base Sepolia 84532 are not in the first ~60 rows) and `const char g_unknown_ticker[] = "???"`. The signer's dynamic-network loader fills the gap from CAL `/networks` (open) via `provide_network_info`. So on Base Sepolia the Flex should show "Base Sepolia" / "ETH" (INFERRED: descriptor exists and the route is open; not seen on a device).

### ERC-20
1. `TokenContextLoader.canHandle` needs `to`, `selector in {transfer, approve}`, `chainId`. Loads `HttpTokenDataSource.getTokenInfosPayload` -> CAL `/tokens?contract_address&chain_id&output=descriptor&ref=branch:main`.
2. Payload = `tickerLength ‖ descriptor.data ‖ signatures["prod"]` (comment in source cites `ethapp.adoc#provide-erc-20-token-information`).
3. App `PROVIDE ERC 20 TOKEN INFORMATION` (INS `0x0A`): "signature is computed on `ticker || address || number of decimals (uint4be) || chainId (uint4be)` signed by the following secp256k1 public key `045e6c1020c14dc46442fe89f97c0b68cdb15976dc24f24c316e7b30fe4e8cc76b1489150c21514ebf440ff5dea5393d83de5358cd098fce8fd0f81daa94979183`" (`doc/ethapp.adoc` §PROVIDE ERC 20 TOKEN INFORMATION). Verified in `cmd_provide_token_info.c` against `LEDGER_SIGNATURE_PUBLIC_KEY` (`src/public_keys.h`, prod key unless `HAVE_CAL_TEST_KEY`).
4. **The app has no built-in token list.** Every ticker/decimals comes from this APDU. Without it `erc20_plugin.c` `ETH_PLUGIN_PROVIDE_INFO` returns `ETH_PLUGIN_RESULT_FALLBACK` (`msg->item1 == NULL`), `logic_sign_tx.c` then logs "Plugin fell back, reverting to the generic transaction review", sets `pluginType = PLUGIN_TYPE_NONE`, and the `dataPresent && !dataAllowed` check shows `ui_error_blind_signing()` ("Enable blind signing in the settings to sign this transaction.").
5. With the APDU accepted the plugin renders `name "ERC20 token"`, `version "Send"|"Approve"`, items `Send <amount> <ticker>` (or `Unlimited <ticker>`), `To` / `Approve to`.

Consequence for the hackathon: **a token you deploy yourself will never clear-sign on a retail device** (CAL addition is "one to two weeks", support-ticket driven, per the for-dapps token-support page). Use USDC on Sepolia/Base Sepolia (both in CAL today) or any mainnet stablecoin.

---

## 5. EIP-712 and personal_sign without a token — VERIFIED source

Signer flow (`SignTypedDataDeviceAction.ts`, `BuildEIP712ContextTask.ts`, `ProvideEIP712ContextTask.ts`):
- `getTypedDataFilters` -> CAL `/dapps` -> 403 -> `filters.type !== "success"` -> `clearSignContext = Nothing`. The task still sends struct definitions + implementations but **no** `SendEIP712FilteringCommand(Activation)`.
- App side: no Activation => `filtering_mode` stays `EIP712_FILTERING_BASIC`. `ui_logic.c:300`: `if (BASIC && !N_storage.dataAllowed && !N_storage.verbose_eip712) { ui_error_blind_signing(); ... }`. With either setting on, `ui_712_start(BASIC)` sets `BLIND_SIGNING_WARN` (and `GATED_SIGNING_WARN`) and then shows every field raw. Setting label on Flex/Stax: **"Raw messages — Displays raw content of EIP712 messages"** (`src/nbgl/ui_home.c`).
- If the app rejects the context (`ProvideContextResultCheck` -> `notRefusedByUser` -> `SignTypedDataLegacy`), `SignTypedDataLegacyTask` computes `domainHash`/`messageHash` client-side and sends `SignEIP712Command` with `legacyArgs` ("Blind sign the hash" in source). App v0 handler: `if (!N_storage.dataAllowed) { ui_error_blind_signing(); return SWO_INCORRECT_DATA; }`.
- Mandate's observation that `DETECT_BLIND_SIGNING` is emitted even after a successful clear sign is consistent with the state machine (`SignTypedDataResultCheck` -> `DetectBlindSigning` always).

`signMessage` (EIP-191) goes through `SendSignPersonalMessageTask` and never calls the context module. Nothing to gate.

---

## 6. Transaction Check on the Flex without a token — VERIFIED source + probe

- Signer: `BuildBaseContexts` only forwards the raw transaction (`needTransaction = appConfig.web3ChecksEnabled`) and the transaction-check loader POSTs to `transaction-checks/v3` -> 403 -> ERROR context -> dropped. The DA may first show `Web3ChecksOptIn` (`UserInteractionRequired.Web3ChecksOptIn`) if the app supports checks and the user has not opted in; that is an on-device "Enable Transaction Check?" dialog (`ui_tx_simulation.c`: "Get real-time warnings about risky Ethereum transactions. Powered by service providers.").
- App: with no `PROVIDE TX SIMULATION` received the review proceeds; footer is plain "Sign" (`ui_tx_simulation_finish_str` returns "Sign" when no W3C/blind warning bit is set). No "check unavailable" string exists in `ui_tx_simulation.c`. INFERRED: the user just does not see a threat/risk card.
- Nano S Plus: no Transaction Check at all (ledger-live issue #21912: "Transaction Check (simulation) runs only on touchscreen devices (Stax, Flex, Nano Gen5)").
- Advice: tell the user to answer "Maybe later" to the opt-in prompt, or pre-disable Transaction Check in app settings, so the demo flow has one fewer screen and no silent dependency on a 403ing backend.

---

## 7. What Mandate's DX.md says, exactly — VERIFIED (raw file read)

Source: https://raw.githubusercontent.com/Satianurag/mandate/main/DX.md (ETHOnline 2026; stack `@ledgerhq/device-management-kit 1.9.0`, `device-signer-kit-ethereum 1.18.0`, `context-module 2.5.0`, `device-transport-kit-node-hid 1.0.1`, `wallet-cli 2.1.0`).

Quotes:
- "Clear-signing on a hackathon device without a partner origin token: `npm run ledger:test-cal` / `MANDATE_LEDGER_TEST_CAL_URL=http://127.0.0.1:8427 npm start`. Open the **ledger-dev Ethereum app** (`CAL_TEST_KEY=1`) before funding."
- "### 1. Production CAL returns 403 without `LEDGER_ORIGIN_TOKEN` — Without a partner token, production CAL 403s and the stock Ethereum app falls back to legacy or clear-basic. A connected device is easy to misread as 'we are clear-signing.' Partner tokens are not self-serve. The working hackathon path is a loopback CAL plus the ledger-dev Ethereum app (`CAL_TEST_KEY=1`). That fork is not on the public 'start here' page."
- "Mandate fail-closes funding unless a partner token **or** `MANDATE_LEDGER_TEST_CAL_URL` is set."
- "### 2. `DETECT_BLIND_SIGNING` is a reporter, not the screen … Legacy fallback is `SIGN_TYPED_DATA_LEGACY` / `usedFallback: true`. We classify traces into `erc7730 | clear-basic | legacy-eip712 | blind | unknown`, and we only call it ERC-7730 when CAL filters actually succeeded."
- "### 3. ERC-7730 lookup hashes the caller's `types` — CAL can succeed in a unit test and still miss on device if `EIP712Domain` is omitted from `types`."
- Improvement #1 to Ledger: "Document CAL **403** as a first-class error: partner `originToken`, or ledger-dev CAL-test, or you are not ERC-7730."

How to read it against the probe: Mandate's payload was an **EIP-712** `TransferWithAuthorization` with a **custom ERC-7730 descriptor** (`docs/erc7730/eip712-USDC-base-mainnet.json`). That path hits `/dapps` -> 403. Their statement is correct **for `/dapps`**; it is **not** a statement about `/tokens`, which their own bridge proxies to production CAL *without* a token (`/tokens` handler: `jsonFetch(upstream)` to `https://global.api.prd.ledger.com/cal/v1/tokens`, then re-signs rows with the test key). The `origin-token.ts` header comment "Without this, CAL returns 403 and the Ethereum app falls back to legacy EIP-712 / blind signing" over-generalises.

What `ledger:test-cal` (`scripts/ledger-test-cal.mjs`) really does — VERIFIED:
1. POSTs the ERC-7730 JSON to `https://app.devicesdk.ledger-test.com/api/process-erc7730-descriptor` (Ledger's hosted processor), gets TLV instructions.
2. Re-signs every instruction and every `/tokens` row with `app-ethereum/client/src/ledger_app_clients/ethereum/keychain/cal.pem` (the **test key** shipped in the app-ethereum repo; fingerprint check `a1609ceb…e386` — I recomputed it from the repo's `cal.pem` with `openssl` and it matches). Serves `/dapps`, `/tokens`, `/certificates` (empty) on `127.0.0.1:8427`; signer is pointed at it with `setCalConfig({ url, mode: "test", branch: "main" })`.
3. Requires an Ethereum app **built with `HAVE_CAL_TEST_KEY`** (`src/public_keys.h`: `#if defined(HAVE_CAL_TEST_KEY)` selects the test key for `LEDGER_SIGNATURE_PUBLIC_KEY`). That is a side-loaded developer build ("ledger-dev Ethereum app"); the Makefile flag spelled `CAL_TEST_KEY=1` in DX.md is not present in today's `Makefile`/`ledger_app.toml` (which only has `use_test_keys = "EIP7702_TEST_WHITELIST=1"`), so the exact build incantation is **unverified** and may have drifted. Side-loading onto a Nano S Plus needs `ledgerctl` with developer mode; a retail Flex cannot take an unsigned app build via the normal path (INFERRED from Ledger's app-loading model; not tested).
4. Net: this is a **Speculos/dev-device** trick. It does not make a retail Flex accept custom descriptors, and it is not needed for ERC-20/native transfers.

---

## 8. Ledger's own clear-signing tester (`apps/clear-signing-tester`) — VERIFIED source

- README: env `GATING_TOKEN` — "Required: For CAL origin-gated features — Description: Origin token". CLI default: `originToken: process.env["GATING_TOKEN"] || "test-origin-token"`. Scenario option `skipOriginToken`: "Send no origin token, so the device shows the gating screen." Their `HttpCalAdapter` sets `"X-Ledger-Client-Origin": this.signerConfig.originToken`.
- Fixtures: `ressources/core/raw-erc20.json` (USDT/USDC `transfer` on `stax`,`nanox`, `expectedTexts: ["USDC","5000"]`) vs `raw-erc20-blind.json` (Uniswap Universal Router call, `expectBlindSigned: true`, `stax`,`flex`). Ledger's own naming: ERC-20 transfer = clear; unsupported calldata = blind.
- Ledger internally calls the token a **gating** token, i.e. it gates access to origin-gated CAL features; it is not a general API key.

---

## 9. Reconciling the five earlier notes

| Note / claim | Status after this research |
|---|---|
| dmk-ts-signer.md: "Works without `originToken` for basic things (ERC-20 etc.); Transaction Check and 'full' clear signing need an `originToken`" | **Correct.** "Full" = ERC-7730 descriptors (`/dapps`), plugins, EIP-712 filters, Transaction Check. |
| dmk-skills.md (dmk-business-logic skill): "without the token the experience silently degrades to blind signing with no runtime error" | **Correct for contract calls and ERC-7730 EIP-712; wrong as a blanket statement.** Native ETH and CAL-listed ERC-20 do not degrade. "Silently" is accurate: loader errors are filtered, not thrown. |
| prior-art-hackathon-projects.md: "production CAL returns HTTP 403 without `LEDGER_ORIGIN_TOKEN`" | **Correct only for `/dapps` (and transaction-checks).** `/tokens`, `/certificates`, `/networks` return 200. Mandate needed test-cal because they were loading a *custom EIP-712 descriptor*, not because signing or ERC-20 is gated. |
| clear-signing-erc7730.md: "descriptors still fetch without it — INFERRED" | **Wrong for descriptors.** `/dapps` descriptor routes 403. Right for token/certificate/network metadata. |
| voice-face-agent-feasibility.md: "native ETH and known-token ERC-20 transfers are always clear-signed — INFERRED" | **Now VERIFIED to the APDU layer** (on-screen text INFERRED). Add: "known token" means "in Ledger's CAL", not "well-known on Etherscan". |
| migration doc 1.3.3->1.4.0: token needed for "trusted names" | Contradicted by a 200 on `nft.api.live.ledger.com/v2/names` with no header. Treat trusted names as "probably works"; verify on device. |

---

## 10. Demo recipe and runtime detection

Do:
```ts
import { SignerEthBuilder } from "@ledgerhq/device-signer-kit-ethereum";
import { ContextModuleBuilder, ContextModuleChainID, ClearSignContextType } from "@ledgerhq/context-module";

// Wrap the default module so the UI can say "clear" vs "blind" BEFORE the device prompt.
const inner = new ContextModuleBuilder({ originToken: process.env.LEDGER_ORIGIN_TOKEN ?? "" })
  .setChain(ContextModuleChainID.Ethereum)
  .build();
const contextModule = {
  ...inner,
  async getContexts(input: unknown, types: ClearSignContextType[]) {
    const ctx = await inner.getContexts(input, types);
    const ok = ctx.filter(c => c.type !== ClearSignContextType.ERROR);
    const errs = ctx.filter(c => c.type === ClearSignContextType.ERROR);
    console.log("[cal] ok:", ok.map(c => c.type), "errors:", errs.map((c: any) => c.error?.message));
    return ctx;
  },
};
const signer = new SignerEthBuilder({ dmk, sessionId }).withContextModule(contextModule).build();
```
(Mandate does the same wrapping for `getTypedDataFilters`; see `packages/gateway/src/dmksigner.ts`.) Never pass a placeholder token — the gateway answers **401 on every route**, including the open ones, for a wrong `X-Ledger-Client-Origin`.

Safe payloads for the pitch (both devices, no token, stock app, no blind-signing toggle):
1. Native ETH transfer on Sepolia / Base Sepolia (Base Sepolia gets its name/ticker from the open `/networks` route).
2. `tUSDC.transfer(to, amount)` on Sepolia (`0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238`) or Base Sepolia (`0x036CbD53842c5426634e7929541eC2318f3dCF7e`): device shows `Send 12.5 tUSDC` + `To`.
3. `signMessage` for non-financial "approve this action" text.

Not safe without a token or a toggle: any custom contract, ERC-7730 EIP-712 (USDC `TransferWithAuthorization`, Permit2 — they fall to raw mode behind "Raw messages"/"Blind signing"), your own ERC-20.

Device prep for a fallback demo: Flex settings -> Ethereum app -> enable "Raw messages" if you want to show raw EIP-712; leave "Blind signing" off so the audience sees the app refuse an undecoded call (good narrative for "device-backed trust"). Decline the "Enable Transaction Check?" opt-in.

Status words to map: `6a80` = blind signing not enabled (incorrect data); `6985` = user refused.

---

## 11. Gaps / open questions

- Not observed on real hardware: the exact strings on Flex/Nano S Plus for a `tUSDC` transfer and for Base Sepolia network naming. Highest-value 10-minute test on day 1.
- `/gated_dapps` and the Safe/proxy metadata routes were not probed.
- Whether Ledger's gateway rate-limits or fingerprints anonymous `/tokens` traffic (the 403s came with Cloudflare `__cf_bm` cookies; all 200s were immediate).
- The trusted-name route was probed with a dummy challenge; a device challenge is `GetChallengeCommand` output. Server accepted the dummy, so the gate is not there, but the device-side signature check over the challenge was not exercised.
- Exact build flag for the test-key Ethereum app today (`HAVE_CAL_TEST_KEY` define exists; Makefile/`ledger_app.toml` plumbing for it not found in the sparse checkout).
- Whether a mentor can hand out a `GATING_TOKEN` for the week — ask on Discord day 1; it would unlock USDC EIP-712 labels and Transaction Check on the Flex, nothing else the demo needs.

---

## Sources

Ledger docs
- https://developers.ledger.com/docs/clear-signing/for-wallets.md (raw read; quotes in §9)
- https://developers.ledger.com/docs/clear-signing/for-dapps/get-started.md
- https://developers.ledger.com/docs/clear-signing/for-dapps/token-support.md
- https://developers.ledger.com/docs/device-interaction/dmk-ts/references/signers/eth
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/migrations/signers/eth/1_3_3_to_1_4_0 (also `apps/docs/content/docs/integration/migrations/signers/eth/1_3_3_to_1_4_0.mdx` in the repo)

device-sdk-ts (sparse clone of `develop` @ 1a3f860f94db64de3eb45f7912d8fab66c7f63ed, 2026-10-09)
- `packages/signer/context-module/src/ContextModuleBuilder.ts` (also https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/signer/context-module/src/ContextModuleBuilder.ts)
- `packages/signer/context-module/src/shared/constant/HttpHeaders.ts`, `shared/network/networkClientFactory.ts`, `config/model/ContextModuleConfig.ts`, `config/model/ContextModuleBuildArgs.ts`
- `packages/signer/context-module/src/modules/ethereum/{token,calldata,trusted-name,typed-data,external-plugin,nft,proxy,dynamic-network}/data/Http*DataSource.ts`, `modules/ethereum/token/domain/TokenContextLoader.ts`, `modules/multichain/{pki,transaction-check}/data/*`
- `packages/signer/signer-eth/src/api/SignerEthBuilder.ts`, `api/model/ClearSigningType.ts`, `internal/app-binder/task/{BuildBaseContexts,BuildEIP712ContextTask,ProvideEIP712ContextTask,ProvideTransactionContextsTask,BlindSigningDetectionTask,SignTypedDataLegacyTask}.ts`, `internal/app-binder/device-action/SignTypedData/SignTypedDataDeviceAction.ts`, `.../SignTransaction/SignTransactionDeviceAction.ts`
- `apps/clear-signing-tester/README.md`, `src/cli/index.ts`, `src/domain/models/Scenario.ts`, `src/infrastructure/adapters/external/HttpCalAdapter.ts`, `ressources/core/raw-erc20.json`, `ressources/core/raw-erc20-blind.json`
- https://github.com/LedgerHQ/device-sdk-ts/pull/807 (origin token header, 2025-04-18)
- https://github.com/LedgerHQ/device-sdk-ts/pull/1471 (Context Module 2.0)
- https://github.com/LedgerHQ/device-sdk-ts/pull/1333 (`--skip-origin-token`)
- https://api.github.com/search/issues?q=repo:LedgerHQ/device-sdk-ts+originToken ; https://api.github.com/search/issues?q=repo:LedgerHQ/device-sdk-ts+403

npm registry (tarballs downloaded and grepped, nothing installed)
- https://registry.npmjs.org/@ledgerhq/context-module (1.5.0, 1.9.0, 1.14.1, 1.17.1, 2.0.0, 2.4.0, 2.6.0)
- https://registry.npmjs.org/@ledgerhq/device-signer-kit-ethereum (1.18.1 peer deps)

app-ethereum (sparse clone of `develop` @ 5a489407c3f6a143bed40aa517edd185a4c1850c, 2026-09-22)
- `doc/ethapp.adoc` (§PROVIDE ERC 20 TOKEN INFORMATION, §PROVIDE TX SIMULATION), `src/public_keys.h`, `src/network.c`, `src/features/sign_tx/logic_sign_tx.c`, `src/plugins/erc20/erc20_plugin.c`, `src/plugins/eth_plugin_handler.c`, `src/features/provide_erc20_token_information/cmd_provide_token_info.c`, `src/features/sign_message_eip712/{ui_logic.c,commands_712.c}`, `src/features/sign_message_eip712_v0/cmd_sign_message_eip712.c`, `src/features/sign_message_eip712_common/common_712.c`, `src/nbgl/{ui_home.c,ui_tx_simulation.c,ui_approve_tx.c,ui_blind_signing.c}`, `client/src/ledger_app_clients/ethereum/keychain/cal.pem`, `ledger_app.toml`, `Makefile`

Mandate (ETHOnline 2026)
- https://github.com/Satianurag/mandate ; raw `DX.md`, `package.json`, `scripts/ledger-test-cal.mjs`, `packages/gateway/src/origin-token.ts`, `packages/gateway/src/dmksigner.ts`, `scripts/dev/probe-ledger-preflight.mjs`

Issues
- https://github.com/LedgerHQ/ledger-live/issues/21912 (wallet-cli skill vs blind signing; TX Check device list)

Live probes (2026-10-10, curl from Windows 11 host)
- https://global.api.prd.ledger.com/cal/v1/{tokens,dapps,certificates,networks}
- https://global.api.prd.ledger.com/transaction-checks/v3/ethereum/scan/transaction
- https://nft.api.live.ledger.com/v1/ethereum/1/contracts/… ; /v2/names/ethereum/1/forward/vitalik.eth
