# USDC x402 payments clear-signed on a Ledger: EIP-3009 `TransferWithAuthorization` end to end

Research note for the N3XT Hackathon @ OP3N 2026. Written 2026-10-10 from web sources, GitHub source, public RPC `eth_call`s and unauthenticated GETs against public APIs only. No hardware touched, nothing installed. Every fact is tagged **VERIFIED** (read in a primary source: spec, contract source, SDK source, live API response, on-chain read) or **INFERRED** (my reading across sources, or a secondary source). Gaps and contradictions are called out in §9.

Scope: the gap left by `research/jury-and-ledger-strategy.md` (Venice + Circle + Ledger intersection). Six questions from the task brief, answered in §1 to §6, recommendation in §8.

---

## 0. TL;DR

1. **The payload is tiny and identical on every chain.** One EIP-712 struct, six fields, domain `{name, version, chainId, verifyingContract}`. Only two things vary per chain: `name` ("USD Coin" on Ethereum/Base/Polygon/Arbitrum/Avalanche/OP mainnets, **"USDC"** on Sepolia, Base Sepolia, Arc testnet **and Arc mainnet**) and `verifyingContract`. `version` is `"2"` everywhere I checked. VERIFIED by `eth_call name()/version()` on 6 chains (§1.3).
2. **A Circle ERC-7730 descriptor exists** (`registry/circle/eip712-TransferWithAuthorization.json`, merged 2026-02-06 by a Ledger employee) with intent "Authorize USDC transfer" and labelled From / To / Amount (as `0.01 USDC`) / Valid after / Valid before, nonce hidden. **It only lists mainnet deployments: chains 1, 10, 137, 8453, 42161, 43114.** No Base Sepolia, no Sepolia, no Arc (5042 or 5042002). VERIFIED (§2).
3. **Whether Ledger's CAL actually serves that descriptor to devices is unverifiable from outside:** `GET /cal/v1/dapps?...descriptors_eip712` returns `403 Not Authorized` without an `X-Ledger-Client-Origin` token; the token comes from Ledger's partner program, not self-serve. Without it, DMK gets an error context and the device falls to **raw ("basic") mode** on every chain, including Base mainnet. VERIFIED (403) + INFERRED (consequence) (§2.3, §9).
4. **Raw mode on the Flex is acceptable but requires a device setting.** Unfiltered EIP-712 shows every domain and message field as `key: value` under "Review typed message" with a skip button, *but only if* "Blind signing" **or** "Raw messages" is enabled in the Ethereum app settings; otherwise the app returns a blind-signing error. On Nano S Plus, "Raw messages" is the only way to see message fields at all. VERIFIED in `app-ethereum` source (§2.4).
5. **Arc is known to the Ledger stack.** CAL `/networks` (no auth needed) returns signed dynamic-network descriptors for `arc` (chainId 5042, with icons) and `arc_testnet` (5042002, ticker USDC), and CAL `/tokens` knows USDC at `0x3600…0000` on both (6 decimals). DMK's `BuildEIP712ContextTask` pushes that network config to the device before any EIP-712 flow. But in raw mode the domain's `chainId` is displayed as the number `5042002`; the network *name* is only rendered in the filtered path. VERIFIED (§3).
6. **Arc USDC is 6 decimals at the ERC-20 interface** (`0x3600…0000`), 18 decimals only for the native gas balance. The task brief's "18-decimal USDC" is true for `msg.value`/native balance, **wrong for the EIP-3009 `value` field** (it is 6-decimal atomic units; Circle's facilitator advertises `decimals: 6`). VERIFIED (§3.1).
7. **Facilitators, all live today:** x402.org (`https://x402.org/facilitator`, Base Sepolia, no key); Circle Facilitator Service (`https://api.circle.com/v1/facilitator/x402/{verify,settle,status}`, Arc testnet + Arc mainnet + Base + Base Sepolia + Polygon + Amoy, **keyless trial** with an EIP-712 "seller proof"); CDP (`api.cdp.coinbase.com/platform/v2/x402`, needs CDP key, no Arc). VERIFIED by live `GET /supported` (§4).
8. **Rogers/Mathias' `ledger-agent-intents`** calls `signerEth.signTypedData(path, typedData, {skipOpenApp:true})`, concatenates `r||s||v` into a 65-byte hex, base64-encodes an x402 v2 `PaymentPayload` into `PAYMENT-SIGNATURE`, and restricts itself to `eip155:8453` and `eip155:84532`. Its DMK deps are `0.0.0-develop-20260206…` snapshots. It never names a facilitator; its live test hits their own demo server. VERIFIED (§5).
9. **Venice x402 is Base mainnet only, $5 minimum, no testnet.** Their `venice-x402-client` hardcodes `new Wallet(privateKey)`, so you cannot inject a Ledger; but the protocol is just SIWE (`personal_sign`, readable on device) + x402 v2 `PAYMENT-SIGNATURE`, so ~60 lines with a viem `toAccount({signMessage, signTypedData})` shim over DMK does it. VERIFIED (§6).
10. **Recommendation (§8):** build on **Arc testnet (`eip155:5042002`) with Circle Facilitator Service keyless trial**; pay nothing, settle in <1 s, show the Circle juror his chain. Accept raw-mode screens (6 readable fields) and make them readable by construction (`validAfter: 0`, round amounts). Keep a **Base mainnet (`eip155:8453`) path as the "clear-signed" stretch goal**: it is the only chain where a labelled "Authorize USDC transfer" screen is even possible, and only if Ledger hands the team an origin token during build week. Ask the mentors for one on day 1.

---

## 1. The EIP-712 payload (question 1)

### 1.1 Spec and contract

- **VERIFIED** (EIP-3009, https://eips.ethereum.org/EIPS/eip-3009): primary type string is exactly
  `TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)`, typehash `0x7c7c6cdb67a18743f49ec6fa9b35f50d52ed05cbed4cc592e13b44501c1a2267`. `ReceiveWithAuthorization` has the same fields, typehash `0xd099cc98…413de8`. The spec recommends the domain include `verifyingContract` and `chainId`. `nonce` is **random 32 bytes** (not sequential), tracked per authorizer in `authorizationState(authorizer, nonce)`. Signature is passed as `v, r, s` (or, in Circle's V2 code, also as `bytes signature`).
- **VERIFIED** (circlefin/stablecoin-evm `contracts/v2/EIP3009.sol`): `_requireValidAuthorization` enforces `now > validAfter` ("authorization is not yet valid"), `now < validBefore` ("authorization is expired"), and unused nonce. Both strict. Emits `AuthorizationUsed(authorizer, nonce)`.
- **VERIFIED** (`contracts/v2/FiatTokenV2_2.sol`): `_domainSeparator()` = `EIP712.makeDomainSeparator(name, "2", _chainId())`, where `name` is the token's `name` storage variable and `_chainId()` reads `chainid()` at call time (so the separator is recomputed after a fork). **The domain `version` is the string `"2"`**; "2.2" is only the contract's title.
- **VERIFIED** (on-chain `eth_call`): the `TRANSFER_WITH_AUTHORIZATION_TYPEHASH()` getter returns `0x7c7c6cdb…a2267` on Sepolia, Base, Base Sepolia, Arc testnet. Arc mainnet and Ethereum mainnet return a `DOMAIN_SEPARATOR()`; I did not re-read the typehash there (the deployments are the same FiatToken code).

### 1.2 Canonical typed data (what the device signs)

```json
{
  "types": {
    "EIP712Domain": [
      { "name": "name", "type": "string" },
      { "name": "version", "type": "string" },
      { "name": "chainId", "type": "uint256" },
      { "name": "verifyingContract", "type": "address" }
    ],
    "TransferWithAuthorization": [
      { "name": "from", "type": "address" },
      { "name": "to", "type": "address" },
      { "name": "value", "type": "uint256" },
      { "name": "validAfter", "type": "uint256" },
      { "name": "validBefore", "type": "uint256" },
      { "name": "nonce", "type": "bytes32" }
    ]
  },
  "primaryType": "TransferWithAuthorization",
  "domain": {
    "name": "USDC",
    "version": "2",
    "chainId": 5042002,
    "verifyingContract": "0x3600000000000000000000000000000000000000"
  },
  "message": {
    "from": "0x<ledger address>",
    "to": "0x<payTo from the 402>",
    "value": "10000",
    "validAfter": "0",
    "validBefore": "1760200000",
    "nonce": "0x<32 random bytes>"
  }
}
```

The `TransferWithAuthorization` type array above is byte-for-byte what `@x402/evm` exports as `authorizationTypes` (VERIFIED, `typescript/packages/mechanisms/evm/src/constants.ts`) and what the ERC-7730 registry test vector uses (VERIFIED, `registry/circle/testsv2/eip712-TransferWithAuthorization.tests.json`, a CoinGecko x402 v2 vector on Base).

### 1.3 Per-chain domain values (VERIFIED by public RPC `eth_call` on 2026-10-10)

| Chain | CAIP-2 | USDC contract | `name()` | `version()` | `decimals()` | RPC used |
| --- | --- | --- | --- | --- | --- | --- |
| Ethereum | `eip155:1` | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` | **USD Coin** | 2 | 6 | ethereum-rpc.publicnode.com |
| Sepolia | `eip155:11155111` | `0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238` | **USDC** | 2 | 6 | ethereum-sepolia-rpc.publicnode.com |
| Base | `eip155:8453` | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` | **USD Coin** | 2 | 6 | mainnet.base.org |
| Base Sepolia | `eip155:84532` | `0x036CbD53842c5426634e7929541eC2318f3dCF7e` | **USDC** | 2 | 6 | sepolia.base.org |
| Arc testnet | `eip155:5042002` | `0x3600000000000000000000000000000000000000` | **USDC** | 2 | **6** | rpc.testnet.arc.io |
| Arc mainnet | **`eip155:5042`** | `0x3600000000000000000000000000000000000000` | **USDC** | 2 | **6** | rpc.mainnet.arc.io |

Addresses cross-checked against https://developers.circle.com/stablecoins/usdc-contract-addresses (VERIFIED). The `name` split matters: a wrong `name` produces a valid-looking signature that `transferWithAuthorization` rejects. **Always take `name`/`version` from the 402's `accepts[].extra`, never hardcode.** x402's own `defaultAssets.ts` encodes the same split (`"USD Coin"` for 8453, `"USDC"` for 84532) (VERIFIED).

### 1.4 How `@ledgerhq/device-signer-kit-ethereum` 1.18.x submits it

- **VERIFIED** (npm registry): latest `1.18.1` (2026-09-21); `1.18.0` 2026-09-02; peer deps `@ledgerhq/context-module ^2.6.0`, `@ledgerhq/device-management-kit ^1.9.1`; bundles `ethers 6.14.1`.
- **VERIFIED** (`src/api/SignerEth.ts`, `src/api/model/TypedData.ts`): signature
  `signTypedData(derivationPath: string, typedData: TypedData, options?: { skipOpenApp?: boolean })` where
  `TypedData = { domain: { name?, version?, chainId?: number, verifyingContract?, salt? }, types: Record<string, {name,type}[]>, primaryType: string, message: Record<string, unknown> }`. `chainId` is a **number**, not bigint/string. Returns the usual DMK observable of `DeviceActionState`; final `output` is `Signature { r, s, v }`.
- **VERIFIED** (`SignTypedDataDeviceAction.ts`, `BuildEIP712ContextTask.ts`, `ProvideEIP712ContextTask.ts`): the state machine is OpenApp → GetAppConfig → GetAddress(`from`) → **BuildContext** → **ProvideContext** → **SignTypedData** → DetectBlindSigning. BuildContext: (a) parses the typed data; (b) if `domain.chainId` is set, asks the context module for `ETHEREUM_DYNAMIC_NETWORK` + `_ICON`; (c) if app ≥ 1.10.0 and device is not Nano S, calls `contextModule.getTypedDataFilters({verifyingContract, chainId, version: "v2" (app ≥1.12.0) | "v1", schema: types, …})`. If filters come back `type: "success"` → `clearSigningType = EIP7730`, else `BASIC`. ProvideContext streams struct definitions, then (if filters) `SendEIP712FilteringCommand(Activation)`, domain implementation, `MessageInfo` filter, per-field filters + token info, message implementation. The device only accepts filters whose signature verifies against `chainId || verifyingContract || schemaHash || …`.
- **VERIFIED** fallbacks: if BuildContext throws, or ProvideContext/SignTypedData fail with anything other than user refusal (`6985`), the action falls to `SignTypedDataLegacyTask`, which hashes domain and message client-side with ethers `TypedDataEncoder` and sends `SignEIP712Command` with `legacyArgs {domainHash, messageHash}` (the v0 "sign hashes" flow; device shows two hashes). `usedFallback` is recorded in internal state.
- **VERIFIED** (`SignTypedDataLegacyTask.ts`): the `EIP712Domain` key is stripped from `types` before hashing, so including it in your `types` is harmless (ledger-agent-intents includes it; `@x402/evm` does not).
- **VERIFIED** (ledger-agent-intents `ledger-provider.tsx`): converting the result to the 65-byte hex that `verifyTypedData`/x402 want:

```ts
const { observable } = signerEth.signTypedData(derivationPath, typedData, { skipOpenApp: true });
// ... observe until DeviceActionStatus.Completed, read output as { r, s, v }
function signatureToHex(sig: { r: string; s: string; v: number }) {
  const r = sig.r.replace(/^0x/, ""), s = sig.s.replace(/^0x/, "");
  return `0x${r}${s}${sig.v.toString(16).padStart(2, "0")}`;   // v is 27/28
}
```

- **VERIFIED** (`ContextModuleBuilder.ts`, `networkClientFactory.ts`): the context module sends `X-Ledger-Client-Version: context-module/<version>` and, if configured, `X-Ledger-Client-Origin: <originToken>` on every CAL request. Default CAL URL `https://global.api.prd.ledger.com/cal/v1`, `mode: "prod"`, `branch: "main"`.

Minimal wiring (INFERRED composition of VERIFIED pieces; matches ledger-agent-intents):

```ts
import { DeviceManagementKitBuilder } from "@ledgerhq/device-management-kit";
import { webHidTransportFactory } from "@ledgerhq/device-transport-kit-web-hid";
import { ContextModuleBuilder } from "@ledgerhq/context-module";
import { SignerEthBuilder } from "@ledgerhq/device-signer-kit-ethereum";

const dmk = new DeviceManagementKitBuilder().addTransport(webHidTransportFactory).build();
const contextModule = new ContextModuleBuilder({ originToken: ORIGIN_TOKEN /* "" if none */ }).build();
const signerEth = new SignerEthBuilder({ dmk, sessionId, originToken: ORIGIN_TOKEN })
  .withContextModule(contextModule).build();
```

---

## 2. Clear-signing descriptor status per chain (question 2)

### 2.1 The registry

- **VERIFIED** (`ethereum/clear-signing-erc7730-registry`, branch `master`, `registry/circle/`): two files, `eip712-TransferWithAuthorization.json` and `eip712-ReceiveWithAuthorization.json`, schema `erc7730-v2`, owner "Circle Internet Financial". Context:

```json
"eip712": {
  "domain": { "name": "USD Coin", "version": "2" },
  "deployments": [
    { "chainId": 1,     "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" },
    { "chainId": 10,    "address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85" },
    { "chainId": 137,   "address": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359" },
    { "chainId": 8453,  "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" },
    { "chainId": 42161, "address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831" },
    { "chainId": 43114, "address": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E" }
  ]
}
```

  Display format for `TransferWithAuthorization(...)`: `intent: "Authorize USDC transfer"`; fields `from` → "From" (`addressName`, wallet, local/ens), `to` → "To" (`addressName`, eoa/contract), `value` → "Amount" (`tokenAmount`, `tokenPath: "@.to"` = the verifying contract, so it renders `0.01 USDC`), `validAfter` → "Valid after" (`date`, timestamp), `validBefore` → "Valid before" (`date`), `nonce` → hidden (`visible: "never"`).
- **VERIFIED** (`index.eip712.json`, 344 entries): keys `eip155:1:0xa0b8…`, `eip155:10:…`, `eip155:137:…`, `eip155:8453:0x8335…`, `eip155:42161:…`, `eip155:43114:…` each map `TransferWithAuthorization` and `ReceiveWithAuthorization` to the circle files (plus a `Permit` entry from `registry/permit/`). **No `eip155:84532`, `eip155:11155111`, `eip155:5042002`, `eip155:5042` entries exist for any USDC type.**
- **VERIFIED** (git history, PR #2320): added 2026-02-06 by `lcastillo-ledger` (a Ledger account), approved by `fsamier`, merged same day, titled "Add circle eip712 TransferWithAuthorization for x402 payments"; the registry CI's Speculos run on `flex` reported "Clear signed" with 46 screenshots. A later 2026-04-10 "[V2 migration]" commit touched the file. No open PR adds testnet or Arc deployments (search of PR titles for circle/usdc/arc, VERIFIED).
- **INFERRED** why Arc/testnets cannot simply be appended: their domain `name` is `"USDC"`, not `"USD Coin"`, and the `eip712.domain` block is per-descriptor, so it needs a *second* descriptor file, not two more `deployments` rows. Per `research/clear-signing-erc7730.md` the median community PR takes ~4 weeks to merge and CAL ingestion is a further undocumented step. Not a 3-day path.

### 2.2 Mapping registry → what the Flex would show (if served)

| Chain | Descriptor in registry | Expected Flex screen (filtered) |
| --- | --- | --- |
| Ethereum mainnet (1) | yes | "Authorize USDC transfer": From, To, Amount `x USDC`, Valid after/before as dates |
| Base (8453) | yes | same |
| Base Sepolia (84532) | **no** | raw mode (§2.4) |
| Sepolia (11155111) | **no** | raw mode |
| Arc testnet (5042002) | **no** | raw mode |
| Arc mainnet (5042) | **no** | raw mode |

### 2.3 Is it actually in Ledger's CAL? Unknown; here is exactly why

- **VERIFIED**: `GET https://crypto-assets-service.api.ledger.com/v1/dapps?contracts=0x8335…&chain_id=8453&output=descriptors_eip712&descriptors_eip712_version=v2&descriptors_eip712=<set>&ref=branch:main` → `403 Not Authorized`, with or without `X-Ledger-Client-Version`. Same for `global.api.prd.ledger.com/cal/v1/dapps` (403) and for `output=descriptors_calldata`. The same host answers `/networks` and `/tokens` with 200 and no auth.
- **VERIFIED**: ledger-agent-intents points its CAL at `https://cdn.live.ledger.com/cryptoassets` and passes `originToken: VITE_LEDGER_API_KEY` ("public client identifier, not a secret", "Get your API key from the Ledger Developer Portal"). That CDN returns S3 `NoSuchKey` for `/dapps` from outside (VERIFIED), so it is not a public mirror of the descriptors either.
- **VERIFIED** (Ledger docs via search, `clear-signing/for-wallets`, `hw_app_eth_to_dmk` migration guide): "wallet integration requires enrollment in Ledger's partner program to obtain an `originToken`"; without it "only basic clear signing (e.g. ERC-20 transfers) is available" and complex calls "fall back to blind signing"; Transaction Check also needs it. No self-serve sign-up was found.
- **INFERRED**: the EIP-712 descriptor path (`/dapps`) is gated by the origin token, so a hackathon app without one gets `type: "error"` from `DefaultTypedDataContextLoader` → `clearSigningType = BASIC` → raw mode on every chain, Base mainnet included. With a token, Base mainnet *probably* clear-signs (Ledger authored the descriptor eight months ago), but nobody outside Ledger can confirm CAL ingestion without a device + token. **Ask a mentor on Discord day 1: "is `eip712-TransferWithAuthorization` live in CAL prod for 8453, and can we have an origin token for the week?"**

### 2.4 Raw ("basic") mode: what the device does without filters (VERIFIED in `LedgerHQ/app-ethereum` develop)

- `src/features/sign_message_eip712/eip712_v1_ui_logic.c` `ui_712_field_shown()`: on `SCREEN_SIZE_WALLET` (Stax/Flex/Apex) every field is shown in BASIC mode. On Nano, message fields are shown only if `N_storage.verbose_eip712` is on; domain fields always.
- `ui_712_continue_or_finish()`: `if (BASIC && !N_storage.dataAllowed && !N_storage.verbose_eip712) { ui_error_blind_signing(); return false; }`. So **on the Flex, an unfiltered EIP-712 message is refused unless either "Blind signing" or "Raw messages" is ON** in the Ethereum app settings (`src/nbgl/ui_home.c`: switches "Blind signing / Enable transaction blind signing" and "Raw messages / Displays raw content of EIP712 messages"). DMK surfaces the refusal as status `6a80` (per `research/dmk-ts-signer.md`).
- `src/nbgl/ui_sign_712.c`: review title "Review typed message", finish "Sign typed message?"; in BASIC mode the review is `SKIPPABLE_OPERATION` (skip button) and `set_gating_warning()` is applied. Fields appear as `key: value` pairs in struct order: domain (`name`, `version`, `chainId`, `verifyingContract`) then message (`from`, `to`, `value`, `validAfter`, `validBefore`, `nonce`). Addresses are checksummed via `getEthDisplayableAddress`; integers are decimal; `nonce` is 64 hex chars.
- `eip712_v1_filtering.c` lines 255-285: the "Contract: <name>" and "Network: <name or chainId>" pairs are emitted **only in the filtered (`EIP712_FILTERING_FULL`) path**, and "Network" only when the domain chainId differs from the app's own. In raw mode the user sees `chainId: 5042002` as a plain number. Filter signatures are hashed over `chainId || verifyingContract || schemaHash || …` (lines 98-132), so a Base descriptor can never be replayed to Arc.
- CHANGELOG (VERIFIED): 1.12.0 (2024-09-27) "unfiltered flows default to raw/verbose mode on Stax and Flex, blind-signing friction added"; 1.18.0 setting to show domain/message hashes; 1.20.0 skip button back in raw flow; 1.21.0 network field in the EIP-712 clear-signing flow; 1.22.0 fixed a blind-signing bypass when filtering active; latest 1.22.3 (2026-08-25).

Net: **raw mode on the Flex is a legible 10-row review of the exact six fields, after a one-time toggle.** It is not "Authorize USDC transfer" with a formatted amount, and the amount shows as `10000`, not `0.01 USDC`.

---

## 3. Arc chain IDs and the Ledger Ethereum app (question 3)

### 3.1 Arc facts

- **VERIFIED** (`eth_chainId`): Arc **mainnet = 5042** (`0x13B2`), Arc **testnet = 5042002** (`0x4CEF52`). The task brief's "mainnet and 5042002" conflates them; `5042002` is the testnet. Circle Facilitator Service, docs.arc.io `connect-to-arc.md` and Circle's supported-networks page all agree (VERIFIED).
- **VERIFIED** (docs.arc.io `connect-to-arc.md`): testnet RPC `https://rpc.testnet.arc.io`, explorer `https://explorer.testnet.arc.io`, faucet `https://faucet.circle.com`; mainnet RPC `https://rpc.mainnet.arc.io`, explorer `https://explorer.arc.io`. Older `rpc.testnet.arc.network` and `docs.arc.network` redirect/alias (301 observed for docs).
- **VERIFIED** (docs.arc.io `contract-addresses.md`, `evm-differences.md`): one balance, two interfaces. "the **native USDC gas token** uses 18 decimals of precision, while the **USDC ERC-20 interface** uses 6 decimals" at `0x3600000000000000000000000000000000000000` on both networks; divide native by 10¹² to display. Gas floor 20 gwei `maxFeePerGas`, below which the mempool **silently drops** the tx. `PREVRANDAO` = 0, no blobs, EIP-4788 omitted. Permit2 deployed at the canonical address on both. GatewayWallet testnet `0x0077777d7EBA4688BDeF3E311b846F25870A19B9`.
- **VERIFIED** (faucet.circle.com): 20 USDC per request, one request per asset+testnet every 2 hours, reCAPTCHA, no account. Arc Testnet is the default selection; Base Sepolia and Ethereum Sepolia also offered.
- **Contradiction noted**: Chainstack/GetBlock pages (via search) still say "Arc is testnet only"; docs.arc.io lists mainnet with an "Add Arc" button, CAL has an `arc` network descriptor, and Circle's facilitator settles on `eip155:5042`. Mainnet is live; the third-party pages are stale. Ledger's blog "Arc by Circle, secured by Ledger" (2026-09-16) calls Ledger a day-one partner but contains an unfilled `[LAUNCH DATE]` placeholder (VERIFIED via search snippet; INFERRED that Ledger Live support is live).

### 3.2 Does the Ethereum app know Arc?

- **VERIFIED** (`src/network.c`): the hardcoded `NETWORK_MAPPING` table has **no entry for 5042 or 5042002**. Lookup order is dynamic networks first, then the hardcoded table; if neither matches, `get_network_as_string_from_chain_id` prints the **decimal chain ID** and the ticker becomes `"???"` (`g_unknown_ticker`). `app_compatible_with_chain_id()` would refuse a *transaction* for an unknown chain unless a dynamic network was provided.
- **VERIFIED** (live, no auth): `GET https://crypto-assets-service.api.ledger.com/v1/networks?output=id,descriptors,icons&chain_id=5042002` → `{"id":"arc_testnet", descriptors: {stax, flex, nanox, apexp: {data:"0101080201015101012308 00000000004cef52 520b 'Arc Testnet' 2404 'USDC'", descriptorType:"network", descriptorVersion:"v1", signatures:{prod, test}}}}`. `chain_id=5042` → `{"id":"arc", icons for stax/flex/nanox/apexp, descriptors …}`. Also `base`, `base_sepolia`, `ethereum_sepolia` all present. **So Arc mainnet and testnet are Ledger-signed dynamic networks today.**
- **VERIFIED** (`ProvideNetworkConfigurationCommand.ts`): APDU `CLA e0 INS 30`, `P1 01` first chunk / `00` next, `P2 00` configuration TLV / `01` icon bitmap. `doc/apdu.md` §"PROVIDE NETWORK CONFIGURATION": "allows access to funds without needing to update the application for each new network… must be sent before any access to a network and stays valid until a new config is sent"; icon ignored on Nano. `network_info.c` verifies the TLV's DER signature against Ledger's network key (tags `0x23` chain id, `0x52` name, `0x24` ticker, `0x15` signature).
- **VERIFIED** (`BuildEIP712ContextTask.getAdditionalContexts`): when `domain.chainId !== undefined`, DMK requests `ETHEREUM_DYNAMIC_NETWORK` and `_ICON` contexts and `ProvideEIP712ContextTask` sends them with `ProvideNetworkConfigurationCommand` **before** the struct definitions. `DynamicNetworkContextLoader` skips only `DeviceModelId.NANO_S` (Nano S Plus is fine), picks `descriptors[deviceModelId]` and `signatures[cal.mode]`. The `/networks` endpoint needs no origin token (VERIFIED by my unauthenticated 200), so **this part works for a hackathon app**.
- **INFERRED** net effect on screens: for an EIP-3009 *typed message* in raw mode the Flex shows `chainId: 5042002` (the network name path is filter-only, §2.4); for an on-chain *transaction* on Arc (e.g. a plain USDC transfer or the one-time Gateway deposit) the Flex would show "Arc Testnet" and ticker `USDC` thanks to the dynamic descriptor. There is no "unknown network" warning in the EIP-712 flow; the unknown-chain `???` ticker only concerns native-value display in transactions.
- CHANGELOG (VERIFIED): dynamic networks added 1.13.0 (2024-11-26); removed from Nano S (LNS) 1.15.0; swap-mode fixes 1.19.3/1.20.1.

---

## 4. x402 facilitator flow on Base Sepolia and Arc testnet (question 4)

### 4.1 Protocol v2 wire format (VERIFIED: `specs/x402-specification-v2.md`, `specs/transports-v2/http.md`, `specs/schemes/exact/scheme_exact_evm.md`)

- Headers (all base64 of JSON): server → client `PAYMENT-REQUIRED` on the 402; client → server **`PAYMENT-SIGNATURE`**; server → client `PAYMENT-RESPONSE` on success. v1 used `X-PAYMENT` / `X-PAYMENT-RESPONSE` and network slugs like `base-sepolia` (VERIFIED, `x402-specification-v1.md` and the live `/supported` of x402.org which still lists `{"x402Version":1,"network":"base-sepolia"}`). Venice additionally accepts `X-402-Payment` (§6).
- `PaymentRequired` = `{ x402Version: 2, error?, resource: {url, description?, mimeType?}, accepts: PaymentRequirements[], extensions? }`.
- `PaymentRequirements` = `{ scheme: "exact", network: "eip155:84532", amount: "10000", asset: "<USDC addr>", payTo: "0x…", maxTimeoutSeconds: 60, extra: { name: "USDC", version: "2", assetTransferMethod?: "eip3009" | "permit2" } }`. **`amount`, not v1's `maxAmountRequired`.** Networks are CAIP-2.
- `PaymentPayload` = `{ x402Version: 2, resource?, accepted: <the chosen PaymentRequirements>, payload: { signature: "0x<65 bytes>", authorization: { from, to, value, validAfter, validBefore, nonce } }, extensions? }`. All authorization values are **decimal strings** (nonce hex).
- Facilitator API: `POST /verify` and `POST /settle` take `{ x402Version: 2, paymentPayload, paymentRequirements }`; verify returns `{ isValid, payer, invalidReason? }`, settle returns `{ success, transaction, network, payer, errorReason?, amount? }`; `GET /supported` returns `{ kinds: [{x402Version, scheme, network, extra?}], extensions, signers }`. Settlement calls `transferWithAuthorization` (not `receiveWithAuthorization`), so the **facilitator pays gas; the payer never needs native gas**.

### 4.2 Reference client behaviour (VERIFIED, `@x402/evm` 2.28.0 `exact/client/eip3009.ts`)

```ts
const nonce = createNonce();                 // random 32 bytes
const now = Math.floor(Date.now() / 1000);
authorization = {
  from: signer.address, to: getAddress(req.payTo), value: req.amount,
  validAfter: (now - 600).toString(),        // 10 min clock-skew buffer
  validBefore: (now + req.maxTimeoutSeconds).toString(),
  nonce,
};
signature = await signer.signTypedData({ domain: { name, version, chainId, verifyingContract: req.asset },
                                        types: authorizationTypes, primaryType: "TransferWithAuthorization", message });
```

The `ClientEvmSigner` type (`signer.ts`) is **just `{ address, signTypedData(typedData): Promise<0x…> }`** plus optional read helpers. That is the whole integration surface for a Ledger: wrap `signerEth.signTypedData` in that shape and hand it to `new ExactEvmScheme(ledgerSigner)` / `wrapFetchWithPayment(fetch, client)` (`@x402/fetch` README, VERIFIED). Reference facilitator verify (`exact/facilitator/eip3009.ts`): requires `extra.name`/`version`, checks `validBefore >= now + 6`, `validAfter <= now`, `value == amount`, `to == payTo`, then simulates. So a `validAfter` of `0` is accepted, and `validBefore` must exceed `maxTimeoutSeconds`-ish windows. Versions: `@x402/core`, `@x402/evm`, `@x402/fetch` all `2.28.0` (2026-09-29) (VERIFIED npm).

### 4.3 Base Sepolia: x402.org facilitator (free, no key)

- **VERIFIED** (live `GET https://x402.org/facilitator/supported`): `exact`, `upto`, `batch-settlement` on `eip155:84532`, plus Solana devnet and others; signer `0xd407e409E34E0b9afb99EcCeb609bDbcD5e7f1bf`; also v1 `base-sepolia`. No auth.
- **VERIFIED** (docs.cdp.coinbase.com `network-support.md`): CDP's production facilitator (`https://api.cdp.coinbase.com/platform/v2/x402`, VERIFIED 401 without key) covers `eip155:8453, 84532, 137, 42161, 480, 4801` + Solana; needs CDP API key id/secret; verification free, first 1,000 settlements/month free, then $0.001 each. **No Arc.**
- Seller side in 5 lines with `@x402/express` + `createFacilitatorConfig("https://x402.org/facilitator")`-style config (per x402 docs; exact helper names vary by version, INFERRED). Buyer side: the Ledger `ClientEvmSigner` above.

### 4.4 Arc testnet: Circle Facilitator Service (keyless trial)

- **VERIFIED** (live `GET https://api.circle.com/v1/facilitator/x402/supported`, 200, no auth):
  `kinds: eip155:5042 (asset 0x3600…, decimals 6, extra {name:"USDC", version:"2"}), eip155:5042002 (same), eip155:8453 ({name:"USD Coin"}), eip155:84532 ({name:"USDC"}), eip155:137 ({name:"USD Coin"}), eip155:80002 ({name:"USDC"})`; `extensions: ["payment-identifier","settlement-status"]`. **This single response is the authoritative per-chain `name` table and proves Circle will settle for us on Arc testnet, Arc mainnet and Base Sepolia.**
- **VERIFIED** (developers.circle.com facilitator-service pages + API reference): endpoints `POST https://api.circle.com/v1/facilitator/x402/verify`, `POST …/settle`, `GET …/status/{paymentId}` (sandbox host `api-sandbox.circle.com` also listed; testnet vs mainnet is chosen by the `network` field, not the host). Auth is either `Authorization: Bearer <CIRCLE_API_KEY>` **or** a `Facilitator-Seller-Proof` header (keyless trial). Keyless: first `/settle` for a new `payTo` auto-creates a seller account; a per-`payTo`, per-chain allowance applies (number not published); when exhausted `/settle` → `403 registration_required`. `/verify` never consumes the allowance. Settlement = `transferWithAuthorization` via a Circle relayer; Arc settlements are "instant finality", Base settlements can later flip to `failed reason=reorged`. EOAs and ERC-1271 accounts supported; ERC-6492 not. Pending → `errorReason: "settlement_pending"` + `extensions["settlement-status"].paymentId`; "Do not fulfill on pending"; retry with the same `payment-identifier` or the identical signed authorization (re-signing double-charges).
- **VERIFIED** seller proof (`sign-seller-proof` page): EIP-712 domain `{ name: "Circle Facilitator Seller Request", version: "1", chainId: <payment chain> }`, type `SellerRequest(string purpose,string method,bytes32 bodyHash,string network,address payTo,bytes32 nonce,uint64 issuedAt,uint64 expiresAt)`, `purpose ∈ verify|settle|status`, `bodyHash = keccak256(raw body)`, `expiresAt ≤ issuedAt + 300`, envelope `{version:1, signature, network, payTo, nonce, issuedAt, expiresAt}` base64url in `Facilitator-Seller-Proof`. The *seller* key signs this (a hot key is fine; it only proves control of `payTo`). It could also be the Ledger (a second typed-data prompt), but that is theatre, not security.
- **VERIFIED** settle body (API reference):

```json
{
  "x402Version": 2,
  "paymentPayload": {
    "x402Version": 2,
    "accepted": { "scheme": "exact", "network": "eip155:5042002", "amount": "10000",
                  "asset": "0x3600000000000000000000000000000000000000", "payTo": "0x<seller>",
                  "maxTimeoutSeconds": 60, "extra": { "name": "USDC", "version": "2", "assetTransferMethod": "eip3009" } },
    "resource": { "url": "https://…/research/brief", "description": "…", "mimeType": "application/json" },
    "payload": { "signature": "0x<r||s||v>",
                 "authorization": { "from": "0x<ledger>", "to": "0x<seller>", "value": "10000",
                                    "validAfter": "0", "validBefore": "1760200000", "nonce": "0x<32B>" } },
    "extensions": { "payment-identifier": { "info": { "required": true, "id": "<16-128 chars [A-Za-z0-9_-]>" } } }
  },
  "paymentRequirements": { "...same as accepted..." }
}
```

```bash
curl -X POST https://api.circle.com/v1/facilitator/x402/settle \
  -H "Content-Type: application/json" -H "Facilitator-Seller-Proof: $PROOF" -d @body.json
curl https://api.circle.com/v1/facilitator/x402/status/$PAYMENT_ID -H "Facilitator-Seller-Proof: $STATUS_PROOF"
```

- Circle's quickstart (VERIFIED) uses `domain {name:"USDC", version:"2", chainId:5042002, verifyingContract:0x3600…}`, value `1000000` (= 1 USDC, 6 decimals), random nonce, `validBefore` one hour out.

### 4.5 Do not confuse with Circle Gateway Nanopayments

- **VERIFIED** (live `GET https://gateway-api-testnet.circle.com/v1/x402/supported`, and the Circle blog "Turn your API into a storefront for agents"): the `@circle-fin/x402-batching` (3.5.0) path uses `facilitatorUrl: "https://gateway-api-testnet.circle.com"` and advertises `extra.name: "GatewayWalletBatched", version: "1", verifyingContract: <GatewayWallet>`, `minValiditySeconds: 604800`, on Sepolia, Base Sepolia, Fuji, Arbitrum Sepolia, … (Arc testnet in the quickstart). The buyer must first **deposit USDC into the GatewayWallet contract** (an on-chain `approve` + `deposit`, i.e. two Ledger *transactions*) and then signs an EIP-3009-shaped authorization whose domain is the **GatewayWallet, not USDC** → no registry descriptor can ever match → raw mode guaranteed; "EOA signatures only, ERC-1271 not supported" (VERIFIED). `BatchEvmScheme` does accept a custom `signTypedData` callback (Circle Wallets quickstart) so a Ledger *can* drive it (INFERRED). It is the right tool for sub-cent streams, the wrong tool for a demo whose point is the device screen. Use Facilitator Service (§4.4) instead.

---

## 5. How `ledger-agent-intents` wired it (question 5)

Repo: https://github.com/brackets-fistfulayen/ledger-agent-intents (redirects from `fistfulayen/…`), default branch `main`, last push 2026-04-13. Hackathon submission to Circle's "USDC OpenClaw Hackathon on Moltbook" (Feb 2026); Apache-2.0 per repo metadata, README says MIT (contradiction, VERIFIED).

- **VERIFIED** deps (`apps/web/package.json`): `@ledgerhq/device-management-kit`, `@ledgerhq/context-module`, `@ledgerhq/device-signer-kit-ethereum`, `device-transport-kit-web-hid`, `device-transport-kit-web-ble`, `device-trusted-app-kit-ledger-keyring-protocol` all pinned to **`0.0.0-develop-20260206115629`** snapshot builds; `viem ^2.45.1`. Not releases; today's release equivalents are dmk 1.9.x / signer-eth 1.18.1 / context-module 2.6.x.
- **VERIFIED** chains (`packages/shared/src/index.ts`, `x402-validation.ts`): intents on 8453, 84532, 11155111 (USDC on all three, ETH only on Sepolia); **x402 restricted to `eip155:8453` and `eip155:84532`** ("Supported: Base, Base Sepolia"). No Arc, no Venice.
- **VERIFIED** signing (`apps/web/src/lib/ledger-provider.tsx` `buildEthSigner`, `signTypedDataV4`): `new ContextModuleBuilder({ originToken: LEDGER_API_KEY }).setCalConfig({ url: "https://cdn.live.ledger.com/cryptoassets", mode: "prod", branch: "main" }).setWeb3ChecksConfig({ url: "https://web3checks-backend.api.ledger.com/v3" })`; `new SignerEthBuilder({ dmk, sessionId, originToken }).withContextModule(cm).build()`; then `ethSigner.signTypedData(derivationPath, parsed, { skipOpenApp: true })`, observed to completion, `signatureToHex` as in §1.4. Retry on "app not open" by opening the Ethereum app and signing again.
- **VERIFIED** payload (`apps/web/src/components/intents/IntentDetailContent.tsx` ~l.745-840): validates `extra.name/version` present, requires wallet chain == `accepted.network`, pre-checks USDC balance via viem, then
  `authorization = { from: account, to: accepted.payTo, value: accepted.amount, validAfter: String(nowSec), validBefore: String(nowSec + (accepted.maxTimeoutSeconds ?? 300)), nonce: randomNonce32BytesHex() }`; typed data `domain {name, version, chainId: Number, verifyingContract: accepted.asset}` with explicit `EIP712Domain` in `types`; message values kept as **strings** for the device; after signing, best-effort `verifyTypedData` locally (warn, do not block, "non-standard signature encoding from the device"); `paymentPayload = { x402Version: 2, resource, accepted, payload: { signature, authorization }, extensions: {} }`; `paymentSignatureHeader = btoa(utf8(JSON))`; stored on the intent (`status: "authorized"`, `expiresAt = validBefore`). Note they use `validAfter = now` (no skew buffer) unlike `@x402/evm`'s `now - 600`.
- **VERIFIED** agent side (`apps/backend/src/x402-client.ts`, `docs/api.md`): agent gets 402 → decodes `PAYMENT-REQUIRED` → `POST /api/intents` with `details.x402 = { resource, accepted }` → polls until `authorized` → fetches `details.x402.paymentSignatureHeader` with `AgentAuth` → retries the resource with `PAYMENT-SIGNATURE` → posts the decoded `PAYMENT-RESPONSE` as `settlementReceipt`. DB unique index on nonce (`002_x402_hardening.sql`), cron expires intents at `validBefore`.
- **VERIFIED gap**: no facilitator is named anywhere; the agent never calls `/verify` or `/settle`; the resource server does. Their live smoke test targets `https://x402-demo-discovery-endpoint.vercel.app/protected` (their own server; source not in this repo, search found no public repo). Which facilitator that server used on Base/Base Sepolia is unknown; INFERRED x402.org for 84532.
- Lesson for us (INFERRED): copy the signer wiring and `signatureToHex`, drop the intent DB (an in-process promise that resolves when the device signs is enough for a demo), and add Arc.

---

## 6. Venice x402 top-up through a Ledger (question 6)

- **VERIFIED** (docs.venice.ai `x402-venice-api.md`, `api-reference/endpoint/x402/top-up.md`, search): `POST https://api.venice.ai/api/v1/x402/top-up` with no header → 402 + `PAYMENT-REQUIRED` whose `accepts` offers **Base mainnet (`eip155:8453`, USDC `0x8335…`, `extra {name:"USD Coin", version:"2"}`, `maxTimeoutSeconds 300`) and Solana mainnet**; `x402Version: 2`; `accepts[].amount` in 6-decimal units; **minimum top-up $5**; canonical header `PAYMENT-SIGNATURE`, legacy `X-402-Payment` and `X-PAYMENT` accepted; success returns `PAYMENT-RESPONSE` + `{ walletAddress, amountCredited, newBalance, paymentId }`. Per-request auth afterwards is `X-Sign-In-With-X`: base64 JSON `{address, message, signature, timestamp, chainId: 8453}` where `message` is an EIP-4361 SIWE text (`domain api.venice.ai`, statement "Sign in to Venice AI", 5-minute expiry, fresh nonce per request) signed with `personal_sign`. Paid routes return `X-Balance-Remaining`; `402` on a paid route = insufficient balance.
- **VERIFIED**: **no testnet, no Base Sepolia, no faucet** anywhere in Venice's docs or search results. Pricing page: no free API tier; Pro subscribers get a one-time $10 credit (per `jury-and-ledger-strategy.md`).
- **VERIFIED** (`veniceai/x402-client` `src/index.ts`, npm `venice-x402-client` 0.2.0, 2026-04-12): `VeniceSigner` does `new Wallet(privateKey)` (ethers) for SIWE and `createSigner('base', this.wallet.privateKey)` + `createPaymentHeader(signer, x402Version, requirements)` from the **legacy `x402` v1 package** (`"x402": "^1.1.0"`, deprecated upstream) for the top-up. There is no injectable signer: a Ledger cannot be plugged into their client. The guide's own code is inconsistent (passes a v1-shaped `maxAmountRequired` requirement with version argument `2`, and sends `X-402-Payment`).
- **INFERRED** how to route it through the Flex (all pieces verified individually): build a viem custom account
  `toAccount({ address, signMessage: ({message}) => ledgerPersonalSign(message), signTypedData: (td) => ledgerSignTypedData(td), signTransaction: () => { throw } })`; use it (a) with `siwe` to produce the `X-Sign-In-With-X` header (the Flex shows the full SIWE text via the Ethereum app's personal-message review, which is genuinely readable), and (b) as `ClientEvmSigner` for `@x402/evm`'s `ExactEvmScheme` to produce `PAYMENT-SIGNATURE` for the top-up (`name: "USD Coin"`, `chainId: 8453`). ~60 lines; skip `venice-x402-client` entirely. Cost: $5 of real USDC on Base mainnet; the device screen is raw mode unless Base mainnet clear-signing is live for you (§2.3). One SIWE signature per Venice call means one Ledger tap per inference call: fine for a demo, unusable for an agent loop, so sign in once and reuse within the 5-minute window, or keep Venice behind an API key and reserve the Ledger for the money.

---

## 7. Gas, cost and setup per chain (VERIFIED facts, INFERRED totals)

| | Base Sepolia `84532` | Arc testnet `5042002` | Base mainnet `8453` | Arc mainnet `5042` |
| --- | --- | --- | --- | --- |
| Payer gas | 0 (facilitator pays) | 0 | 0 | 0 |
| Payer funds | faucet 20 tUSDC / 2 h | faucet 20 tUSDC / 2 h | real USDC (cents) | real USDC |
| Facilitator | x402.org, no key; Circle keyless | Circle keyless (`api.circle.com`) | CDP (key) or Circle keyless | Circle keyless |
| Finality | L2, reorg risk flagged by Circle | <1 s, "instant" | L2 | <1 s |
| Domain `name` | USDC | USDC | USD Coin | USDC |
| ERC-7730 descriptor | none | none | yes (if CAL + origin token) | none |
| Flex screen | raw | raw (`chainId 5042002`) | labelled, or raw | raw |
| Juror signal | Coinbase-flavoured | Circle/Arc, Breeding's chain | Venice-compatible | Circle flex |

Running your own facilitator instead (reference `examples/typescript/facilitator`, `FacilitatorEvmSigner` = viem wallet+public client) costs one hot key funded with testnet gas (Arc testnet gas is the same faucet USDC) and removes the seller-proof step; it also lets you demo on Sepolia (`11155111`) where nobody hosts a facilitator. INFERRED trade-off: more code, fewer external dependencies during the pitch.

---

## 8. Recommendation

**Chain: Arc testnet, `eip155:5042002`, USDC `0x3600000000000000000000000000000000000000`, domain `{name:"USDC", version:"2"}`, settled through Circle Facilitator Service keyless trial.** Reasons: zero payer gas and zero money; sub-second settlement so the demo loop is tight; the network and token are already Ledger-signed in CAL (§3.2) so nothing on the device is "unknown"; it is literally the Circle juror's product; and the Flex screen is *identical* to what Base Sepolia would show (both raw), so there is no readability penalty for choosing Arc over Base Sepolia.

**Payload that yields the most readable raw screen:**

- `validAfter: "0"` (renders as `0`, accepted by x402 reference verify and by the contract since `now > 0`); `validBefore` = `now + maxTimeoutSeconds` (Circle's quickstart even uses a year-2040 constant; keep it short in the demo so the "expires" story holds).
- `value` a round number of cents (`10000` = 0.01 USDC) and say so on the web UI beside the device prompt, since the device shows the atomic integer.
- `from` = the Ledger address shown earlier via `getAddress(path, {checkOnDevice:true})` so the user has already seen it.
- Keep `EIP712Domain` in `types` (harmless) and pass `chainId` as a number.
- Before prompting, make the user flip **"Raw messages" ON** in the Ethereum app settings on the Flex (and on the Nano S Plus, where it is the only way to see message fields). Do not ask them to enable "Blind signing"; "Raw messages" is the narrower toggle and the jury will ask.

**Stretch goal that is worth 30 minutes of asking, not 3 days of building:** Base mainnet `eip155:8453` with the Circle registry descriptor. If a mentor confirms the descriptor is served from CAL prod and gives the team an origin token, the *same code* with `name: "USD Coin"` gets the "Authorize USDC transfer / From / To / Amount 0.01 USDC / Valid before" screen, which is the single best slide for "Ledger clear-signs the agent's money". Fund it with $1 of USDC; settle through Circle keyless on 8453 (listed in their `/supported`) so no CDP account is needed. Record the screen on video in case the Paris Wi-Fi fails.

**What not to do:** Gateway Nanopayments for the headline demo (deposit transactions + un-descriptorable domain, §4.5); writing a new ERC-7730 descriptor for Arc expecting it on retail devices this week (§2.1); routing Venice through the Ledger as a *first* milestone (mainnet-only, $5, one tap per call, §6). Venice is a day-3 add-on once Arc works.

---

## 9. Gaps, contradictions, things I could not verify

1. **CAL ingestion of the Circle descriptor**: `/dapps` returns 403 without an origin token; unverifiable without a token or a device test. The registry CI "Clear signed" result was on Speculos with test keys.
2. **Origin token availability**: docs say partner program; ledger-agent-intents' `.env.example` says "Get your API key from the Ledger Developer Portal". No self-serve page found. Resolve with mentors on Discord day 1.
3. **Circle keyless trial allowance** (number of settlements per `payTo` per chain) is not published; plan for it to run out mid-demo and have a second `payTo` address ready, or a Circle API key (free Circle developer account; VERIFIED that Bearer auth binds the `payTo` and lifts the limit).
4. **Arc mainnet "live" vs third-party pages saying testnet-only**: resolved in favour of live (chainId 5042 answers, CAL and Circle list it), but Ledger's own blog has an unfilled `[LAUNCH DATE]`.
5. **18 vs 6 decimals**: the task brief and `jury-and-ledger-strategy.md` describe Arc USDC as 18-decimal; that is only the native gas balance. All EIP-3009 `value`s on Arc are 6-decimal, and Circle's facilitator advertises `decimals: 6`. Fix the strategy note.
6. **Arc mainnet chain ID**: the task brief implied 5042002 could be mainnet; it is the testnet. Mainnet is 5042.
7. **Which facilitator ledger-agent-intents used**: not in the repo.
8. **Venice header naming**: guide says `X-402-Payment`, endpoint reference says canonical `PAYMENT-SIGNATURE` with legacy aliases; guide mixes v1 field names with version 2. Use `PAYMENT-SIGNATURE` + v2 shape.
9. **DMK filter version**: `BuildEIP712ContextTask` picks v2 filters for app ≥ 1.12.0; Circle's descriptor uses `tokenAmount` with `@.to` token path and `date` formats, which are v2 features (amount-join / datetime filters, app 1.11.0+). On a Flex with app 1.22.x this is fine; on an old Nano S Plus app it may degrade (INFERRED).
10. **Nano S Plus in the EIP-712 clear-sign path**: DMK excludes only `NANO_S`; the S Plus is eligible for filters, dynamic networks, and raw mode with "Raw messages" on. Not tested here.
11. I did not fetch `getEvmChainId`/`createNonce` implementations or the `@x402/express` seller helper names; treat helper names in §4.3 as approximate.

---

## 10. Sources

Specs and contracts
- https://eips.ethereum.org/EIPS/eip-3009
- https://raw.githubusercontent.com/circlefin/stablecoin-evm/master/contracts/v2/EIP3009.sol
- https://raw.githubusercontent.com/circlefin/stablecoin-evm/master/contracts/v2/FiatTokenV2_2.sol
- https://developers.circle.com/stablecoins/usdc-contract-addresses
- Public RPC `eth_call`s (name/version/decimals/typehash/DOMAIN_SEPARATOR): https://ethereum-rpc.publicnode.com , https://ethereum-sepolia-rpc.publicnode.com , https://mainnet.base.org , https://sepolia.base.org , https://rpc.testnet.arc.io , https://rpc.mainnet.arc.io

x402
- https://raw.githubusercontent.com/coinbase/x402/main/specs/x402-specification-v2.md
- https://raw.githubusercontent.com/coinbase/x402/main/specs/x402-specification-v1.md
- https://raw.githubusercontent.com/coinbase/x402/main/specs/transports-v2/http.md
- https://raw.githubusercontent.com/coinbase/x402/main/specs/schemes/exact/scheme_exact_evm.md
- https://raw.githubusercontent.com/coinbase/x402/main/docs/core-concepts/facilitator.md
- https://raw.githubusercontent.com/coinbase/x402/main/typescript/packages/mechanisms/evm/src/exact/client/eip3009.ts
- https://raw.githubusercontent.com/coinbase/x402/main/typescript/packages/mechanisms/evm/src/exact/client/scheme.ts
- https://raw.githubusercontent.com/coinbase/x402/main/typescript/packages/mechanisms/evm/src/exact/facilitator/eip3009.ts
- https://raw.githubusercontent.com/coinbase/x402/main/typescript/packages/mechanisms/evm/src/signer.ts
- https://raw.githubusercontent.com/coinbase/x402/main/typescript/packages/mechanisms/evm/src/constants.ts
- https://raw.githubusercontent.com/coinbase/x402/main/typescript/packages/mechanisms/evm/src/shared/defaultAssets.ts
- https://raw.githubusercontent.com/coinbase/x402/main/typescript/packages/http/fetch/README.md
- https://raw.githubusercontent.com/coinbase/x402/main/typescript/packages/legacy/x402/README.md and `src/client/createPaymentHeader.ts`, `src/types/shared/evm/wallet.ts`
- https://x402.org/facilitator/supported (live GET)
- https://docs.cdp.coinbase.com/x402/network-support.md , https://docs.cdp.coinbase.com/x402/seller/facilitator.md
- npm registry JSON for `@x402/core`, `@x402/evm`, `@x402/fetch`, `@circle-fin/x402-batching`, `venice-x402-client`, `@ledgerhq/device-signer-kit-ethereum`

Circle / Arc
- https://developers.circle.com/agent-stack
- https://developers.circle.com/facilitator-service , /facilitator-service/quickstart , /facilitator-service/how-it-works , /facilitator-service/supported-networks , /facilitator-service/keyless-trial , /facilitator-service/sign-seller-proof
- https://developers.circle.com/api-reference/facilitator-service/settle-payment , /verify-payment
- https://api.circle.com/v1/facilitator/x402/supported (live GET)
- https://gateway-api-testnet.circle.com/v1/x402/supported (live GET)
- https://developers.circle.com/gateway/nanopayments , https://developers.circle.com/gateway-nanopayments/quickstarts/buyer
- https://www.circle.com/blog/turn-your-api-into-a-storefront-for-agents
- https://docs.arc.io/ , https://docs.arc.io/arc/references/connect-to-arc.md , https://docs.arc.io/arc/references/contract-addresses.md , https://docs.arc.io/arc/references/evm-differences.md
- https://faucet.circle.com/
- Search results (secondary): https://docs.chainstack.com/docs/arc-tooling.md , https://docs.getblock.io/api-reference/arc , https://www.ledger.com/blog-arc-by-circle-secured-by-ledger

ERC-7730 registry
- https://github.com/ethereum/clear-signing-erc7730-registry (branch `master`; tree via GitHub API)
- https://raw.githubusercontent.com/ethereum/clear-signing-erc7730-registry/master/registry/circle/eip712-TransferWithAuthorization.json
- https://raw.githubusercontent.com/ethereum/clear-signing-erc7730-registry/master/registry/circle/eip712-ReceiveWithAuthorization.json
- https://raw.githubusercontent.com/ethereum/clear-signing-erc7730-registry/master/registry/circle/testsv2/eip712-TransferWithAuthorization.tests.json
- https://raw.githubusercontent.com/ethereum/clear-signing-erc7730-registry/master/index.eip712.json
- https://github.com/ethereum/clear-signing-erc7730-registry/pull/2320 ; commits API for `registry/circle/...`

Ledger device app and DMK
- https://raw.githubusercontent.com/LedgerHQ/app-ethereum/develop/CHANGELOG.md
- https://raw.githubusercontent.com/LedgerHQ/app-ethereum/develop/doc/apdu.md , doc/eip712.md
- https://raw.githubusercontent.com/LedgerHQ/app-ethereum/develop/src/network.c , src/features/provide_network_info/network_info.c
- https://raw.githubusercontent.com/LedgerHQ/app-ethereum/develop/src/features/sign_message_eip712/eip712_v1_ui_logic.c , eip712_v1_filtering.c , src/features/sign_message_eip712_common/common_712.c , src/nbgl/ui_sign_712.c , src/nbgl/ui_home.c
- https://github.com/LedgerHQ/device-sdk-ts (tree via GitHub API) and raw files: `packages/signer/signer-eth/src/api/SignerEth.ts`, `api/model/TypedData.ts`, `api/model/TypedDataOptions.ts`, `internal/app-binder/device-action/SignTypedData/SignTypedDataDeviceAction.ts`, `internal/app-binder/task/BuildEIP712ContextTask.ts`, `ProvideEIP712ContextTask.ts`, `SignTypedDataLegacyTask.ts`, `BuildBaseContexts.ts`, `internal/app-binder/command/ProvideNetworkConfigurationCommand.ts`; `packages/signer/context-module/src/ContextModuleBuilder.ts`, `config/model/ContextModuleConfig.ts`, `shared/network/networkClientFactory.ts`, `shared/constant/HttpHeaders.ts`, `modules/ethereum/typed-data/data/HttpTypedDataDataSource.ts`, `typed-data/domain/DefaultTypedDataContextLoader.ts`, `typed-data/utils/getSchemaHash.ts`, `dynamic-network/data/HttpDynamicNetworkDataSource.ts`, `dynamic-network/domain/DynamicNetworkContextLoader.ts`; `packages/device-management-kit/src/api/network/DmkNetworkClient.ts`
- https://www.npmjs.com/package/@ledgerhq/device-signer-kit-ethereum (via registry JSON)
- Ledger CAL live GETs: `https://crypto-assets-service.api.ledger.com/v1/networks?output=id,descriptors,icons&chain_id={5042002,5042,84532,8453,11155111}` (200), `.../tokens?output=id,ticker,decimals,contract_address&chain_id=...` (200), `.../dapps?...descriptors_eip712...` (403), `https://global.api.prd.ledger.com/cal/v1/dapps` (403), `https://cdn.live.ledger.com/cryptoassets/dapps` (404)
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/dmk ; search snippets of https://developers.ledger.com/docs/clear-signing/for-wallets and https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/migrations/signers/eth/hw_app_eth_to_dmk

ledger-agent-intents
- https://github.com/brackets-fistfulayen/ledger-agent-intents (README via fetch; tree via API)
- raw: `apps/web/package.json`, `apps/web/.env.example`, `apps/web/src/lib/ledger-provider.tsx`, `apps/web/src/lib/x402-validation.ts`, `apps/web/src/components/intents/IntentDetailContent.tsx`, `apps/backend/src/x402-client.ts`, `apps/backend/scripts/x402-agent-demo.ts`, `apps/backend/scripts/x402-live-smoke-test.ts`, `packages/shared/src/index.ts`, `docs/api.md`, `PROJECT.md`

Venice
- https://docs.venice.ai/guides/integrations/x402-venice-api.md
- https://docs.venice.ai/api-reference/endpoint/x402/top-up.md
- https://github.com/veniceai/x402-client (`src/index.ts`) and npm `venice-x402-client`

Internal notes read: `HACKATHON.md`, `research/jury-and-ledger-strategy.md`, `research/dmk-ts-signer.md`, `research/clear-signing-erc7730.md`.
