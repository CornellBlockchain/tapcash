# Ledger Clear Signing and ERC-7730 — research note

> **Correction (2026-10-10, source audit).** Default Speculos trusts Ledger's TEST PKI root, so the release Ethereum ELF should accept test-signed descriptors with no test-key app build (§3.3; end to end INFERRED); the hosted backend is `app.devicesdk.ledger-test.com`; Address Book needs Ethereum >= 1.23.0 and OS >= 1.7.0 (l.129, l.136). See `source-audit.md` §2 (M04, M05) and §5.

Researched 2026-10-10 for the N3XT hackathon (deadline Oct 13 23:59 CEST). Hardware: Nano S Plus (USB), Flex (USB/BLE/NFC). Host: Windows 11.

Tags: **VERIFIED** = read in a primary source (spec, docs page, source code, GitHub API). **INFERRED** = my conclusion from verified pieces, or a secondhand/search-snippet claim.

## TL;DR for a 3-day build

1. **Clear signing = a signed descriptor that the Ethereum device app verifies and renders.** The descriptor (ERC-7730 JSON) is converted off-device into TLV "instructions", each signed by a Ledger CAL key; the device checks the signature against a Ledger PKI certificate and only then shows intent + labelled fields. Unsigned/unknown data falls back to blind signing. (VERIFIED, see §3, §6)
2. **You cannot get a custom descriptor onto a retail Nano S Plus / Flex in 3 days via the official route.** Registry PRs from community authors take days-to-months (median ~4 weeks over May–Sep 2026; 19 community PRs opened Sep 14–Oct 9 are still open; maintainer wrote on Oct 8 "Approving and merging descriptors will take time"). Even after merge, Ledger's CAL ingestion into `global.api.prd.ledger.com/cal/v1` is a separate, undocumented step. (VERIFIED on PR data; CAL step INFERRED)
3. **Local/dev loading exists but only for Speculos (emulator), not retail devices.** Ledger's DMK sample app has an "ERC-7730 Tester" (`@ledgerhq/cal-interceptor`, private package) that converts a pasted descriptor with `python-erc7730`, signs it with a hard-coded **test key**, and intercepts CAL HTTP calls. The device must be provisioned with test certificates, which the code says is for "Speculos testing". A retail device's Ethereum app is built with prod keys. (VERIFIED code; "retail device rejects" is INFERRED from key handling, not tested)
4. **EIP-712 descriptors can carry arbitrary non-financial semantics.** The `eip712` context binds on domain `name`/`version` + `verifyingContract`/`chainId`, and fields can be `raw` strings with any label. A live example (Cofund, PR #3072, open) clear-signs "Invite member", "Remove member", "Rotate signing key". The device renders filtered EIP-712 fields directly in the Ethereum app, no Generic Parser needed. Same signing-key constraint applies though. (VERIFIED)
5. **Workable hackathon path for "approve this action" on real hardware:** EIP-191 `personal_sign` / `signMessage`. The Ethereum app displays the full ASCII message text on screen (hex if non-printable), no descriptor or registry needed, works today on both devices via DMK `signerEth.signMessage(path, message)`. Not "clear signing" in the ERC-7730 sense, but it is human-readable, device-verified intent. Second option: EIP-712 without a filter: on Stax/Flex the app defaults to raw/verbose mode showing all fields (with blind-signing friction); on Nano you must enable the "Verbose EIP712" setting, otherwise only hashes are shown. (VERIFIED in app-ethereum source/changelog)
6. **Screen text limits (device firmware constants):** generic-parser field label ≤ 20 chars (`MAX_FIELD_NAME_SIZE 21`), intent/operation type ≤ 30 (`OPERATION_TYPE_SIZE 31`), contract name ≤ 30, owner/creator name ≤ 22, URL ≤ 26. Nano S Plus screen is 128×64 px; Flex is 480×600 px touchscreen. Values longer than the screen paginate. (VERIFIED constants; pagination INFERRED)

---

## 1. What Clear Signing is (Ledger's framing)

Source: https://developers.ledger.com/docs/clear-signing/overview (VERIFIED)

- "What you see is what you sign." A protocol author publishes metadata (an ERC-7730 descriptor) mapping contract functions or EIP-712 messages to human-readable fields; a compatible wallet uses it to render the transaction on the signer's Secure Screen. Clear Signing never modifies the transaction; it adds a display layer verified on the signer.
- Ledger launched the initiative in 2023; on **May 12, 2026** stewardship moved to the Ethereum Foundation (Trillion Dollar Security Initiative). Registry now at `github.com/ethereum/clear-signing-erc7730-registry`; Ledger remains a steward with Trezor, MetaMask, WalletConnect, Sourcify, Fireblocks, Cyfrin. (VERIFIED: https://www.ledger.com/blog-ledger-clear-signing-ethereum-foundation)
- Where it displays: Ledger Wallet over WalletConnect (always); Ledger Wallet web3 browser / Ledger Wallet Button (only if dApp integrates); third-party wallets only "with a Clear Signing agreement with Ledger". Touchscreen signers additionally run Transaction Check.
- Older Ledger pages (`/docs/clear-signing/erc7730`, `/erc7730/process`, `/eip712`) still exist but redirect/duplicate the overview; the detailed Ledger reference pages (`/reference/erc7730-reference`, `/reference/specifications`, `/for-dapps/validate-submit`) returned 404 on 2026-10-10. Search snippets of the dead `erc7730-reference` page said "Ledger's tools and the registry currently target ERC-7730 v1" — this **contradicts** the registry README, which says `erc7730-v2.schema.json` is the latest released schema and new descriptors must use v2. Treat the v1 statement as stale. (VERIFIED both sides; contradiction noted)

## 2. ERC-7730 descriptor anatomy

Sources: https://eips.ethereum.org/EIPS/eip-7730 (Draft; authors Castillo, Rein, Aoun, Galansky, Rozwarski, Uzdogan, Fredrik, Forshtat) and https://ethereum.org/developers/tutorials/clear-signing (VERIFIED)

Top-level keys: `$schema`, `context`, `metadata`, `display`, optional `includes`.

```json
{
  "$schema": "../../specs/erc7730-v2.schema.json",
  "context": {
    "$id": "MyContract",
    "contract": { "deployments": [ { "chainId": 1, "address": "0x..." } ] }
  },
  "metadata": { "owner": "My Project", "info": { "url": "https://..." }, "contractName": "MyContract" },
  "display": {
    "formats": {
      "transfer(address to,uint256 value)": {
        "intent": "Send",
        "interpolatedIntent": "Send {value} to {to}",
        "fields": [
          { "path": "value", "label": "Amount", "format": "tokenAmount", "params": { "tokenPath": "@.to" } },
          { "path": "to",    "label": "To",     "format": "addressName" }
        ]
      }
    }
  }
}
```

- **Format keys**: full Solidity signature with parameter names (calldata), or the EIP-712 `encodeType` string of the primary type (e.g. `Permit(address owner,address spender,uint256 value,uint256 nonce,uint256 deadline)`).
- **Paths**: `#.` decoded data (default when no root), `$.` the descriptor file itself (`$.metadata.enums.x`), `@.` container (`@.to`, `@.value`, `@.from`, `@.chainId`). Arrays need `.[]`, `.[0]`, slices `[0:20]`, `[-1]`.
- **Formats (v2/v3-next schema)**: `raw`, `addressName`, `tokenTicker`, `calldata`, `amount`, `tokenAmount`, `nftName`, `date`, `duration`, `unit`, `enum`, `chainId`, `interoperableAddressName`. `$ref` reuse via `display.definitions`.
- **Intent**: required (string or flat object). `interpolatedIntent` optional; spec says resource-constrained devices "may skip interpolatedIntent support" and must fall back to static `intent` if any path is invalid. Ledger's generic parser puts the intent after "Review ..." on the first screen (TLV `OPERATION_TYPE`).
- **Visibility**: `visible: "always" | "never" | "optional" | {ifNotIn|mustMatch}`. Reviewers reject hiding value-bearing fields (amounts, spenders, recipients, deadlines).
- **No string length limits in the schema** (checked `erc7730-v3.0.0-next.schema.json`: no `maxLength` anywhere). Limits live in the device firmware (§7) and the linter warns "exceeds <size> characters and may be truncated on Ledger devices".
- Security section: bind to proxy address for upgradeable proxies; one file per facet for diamonds; wallets must verify ENS before interpolation; test long names/addresses for truncation.
- Advanced v2 features (maps, bundled fields, interoperable addresses) "may not be supported by all hardware wallets" (clearsigning.org/build). Ethereum-Magicians thread (Mar 2025, Ledger): nested calldata "not yet supported on Ledger devices" at that time; app-ethereum changelog later added "Transaction nested calldata clear-signing" and "EIP-712 calldata clear-signing". (VERIFIED)

### EIP-712 context (the part relevant to non-financial "approve this action")

```json
"context": {
  "$id": "Cofund",
  "eip712": {
    "deployments": [ { "chainId": 1, "address": "0xD59e..." } ],
    "domain": { "name": "Cofund", "version": "1" }
  }
}
```

- `domain` keys must match the message's EIP712Domain; `deployments` constrain `chainId` + `verifyingContract`; `domainSeparator` alternative; `schemas` deprecated.
- Real example (registry PR #3072, open since Sep 30): `InviteUser(string company,string callerId,string userId,bool userIsAdmin,string userPosition,uint256 expiresAt,string authId)` → intent "Invite member", fields `Company`, `Invited by`, `Member ID`, `Admin rights`, `Position` (all `raw`), `Expires` (`date`), `authId` hidden. Also "Remove member", "Rotate signing key" (`interpolatedIntent: "Move member {userId} to {newAddress}"`), "Activate transfer policy". CI passed 48 test cases; AI review posted; not merged. (VERIFIED: https://github.com/ethereum/clear-signing-erc7730-registry/pull/3072)
- Merged example: `registry/safe/eip712-Safe-Multisig.json` (owner "Ledger Multisig", domain name "Ledger Multisig" version "1.0.0", ~40 deployments) with message types like `AddAddressBookEntry`, `AddProposer`, `Delegate`, `DeleteRequest`. So governance/admin-style EIP-712 messages are already clear-signed on Ledger devices. (VERIFIED via `index.eip712.json`)
- **Conclusion**: ERC-7730 happily describes non-financial typed data. The blocker is distribution (signing + registry), not expressiveness.

## 3. How the descriptor reaches the device (Ledger pipeline)

### 3.1 Registry → CAL → wallet → device

- Wallet integration page: the Ethereum signer's **context module** fetches the descriptor + security context for the target contract; the signer renders decoded fields on the Secure Screen; no descriptor → blind signing. (VERIFIED: https://developers.ledger.com/docs/clear-signing/for-wallets.md)
- Ledger converts registry descriptors into **signed TLV instructions** served by its CAL (Crypto Assets List) API. Default endpoints baked into `@ledgerhq/context-module` `ContextModuleBuilder.ts` (VERIFIED):
  - CAL: `https://global.api.prd.ledger.com/cal/v1`, `mode: "prod"`, `branch: "main"` (type `ContextModuleCalBranch = "next" | "main" | "demo"`, `ContextModuleCalMode = "prod" | "test"`)
  - Web3 checks: `https://global.api.prd.ledger.com/transaction-checks/v3`
  - Metadata (NFT) service: `https://nft.api.live.ledger.com`
  - Blind-signing reporter: `https://blind-signing.api.ledger.com/ingest`
- Calldata request (`HttpCalldataDescriptorDataSource.ts`, VERIFIED):
  ```ts
  this.http.get(`${this.config.cal.url}/dapps`, { params: {
    output: "descriptors_calldata", chain_id: chainId,
    contracts: address, contract_address: address,
    ref: `branch:${this.config.cal.branch}` } })
  ```
  Response: `descriptors_calldata[address][selector]` → `{ version: "v1", transaction_info: { descriptor: { data, signatures: { prod, test } } }, enums, fields[] }`. The module picks `signatures[config.cal.mode]`.
- EIP-712 request (`HttpTypedDataDataSource.ts`, VERIFIED): `GET {cal}/dapps?contracts=<addr>&chain_id=<id>&output=descriptors_eip712&descriptors_eip712_version=<v1|v2>&descriptors_eip712=<set>&ref=branch:<branch>`. Lookup key is `descriptors_eip712[address][schemaHash]` where schemaHash = sha224 of the message's `types` (computed client-side). Response `instructions[]` contains a **message info** entry (`display_name`, `field_mappers_count`, `signatures`) and per-field filters (`display_name`, `field_path`, `format`, `signatures`, optional `coin_ref`, trusted-name/calldata variants).
- On the device (app-ethereum `doc/apdu.md`, VERIFIED): EIP-712 FILTERING APDU (INS `0x1E`). Message-info signature is over `183 || chainId(8 bytes BE) || contract address || schema hash || filters count || display name`; per-field signatures over `11/22/33/44/55/...` magic || chainId || address || schema hash || field path || display name (...). Raw field filter magic `72` (in `eip712_v1_filtering.c`). Up to `MAX_FILTERS 50` per message. Calldata (generic parser) flow: `SIGN store-only` → `TRANSACTION INFO` (signed) → per-field `TX FIELD DESCRIPTION` + token/NFT/enum/trusted-name metadata → `SIGN start`, device checks a hash of received fields before display (`doc/gcs.md`).
- Keys: `src/public_keys.h` defines `LEDGER_SIGNATURE_PUBLIC_KEY` with `#if HAVE_CAL_TEST_KEY / #elif HAVE_CAL_STAGING_KEY / #else prod`. Newer flows load Ledger PKI certificates (`/cal/v1/certificates?output=descriptor&target_device=&public_key_usage=&public_key_id=`) with key ids like `cal_calldata_key`, `cal_trusted_name`, `token_metadata_key`. (VERIFIED)
- **Gap**: nothing public documents when/how a merged registry PR gets ingested into Ledger's CAL, or SLA. A 2024 ETHGlobal write-up (Kiln "Clearly Vaults") said CI was green but "additional approval was required on the CAL review". (INFERRED / secondhand: https://kilnfi.notion.site/Clearly-Vaults-ETHGlobal-2024-140c1910fb6e80098f35d197fdaed427 page did not render for me)

### 3.2 DMK integration (what your app writes)

Source: https://developers.ledger.com/docs/device-interaction/references/signers/eth.md, https://developers.ledger.com/docs/clear-signing/for-wallets.md (VERIFIED)

```sh
npm install @ledgerhq/device-management-kit @ledgerhq/device-transport-kit-web-hid @ledgerhq/device-signer-kit-ethereum
```
```ts
// default context module (needs an originToken from Ledger for Transaction Check; clear signing descriptors still fetch without it — INFERRED, docs only say TX checks are unavailable without it)
const signerEth = new SignerEthBuilder({ dmk, sessionId, originToken: "origin-token" }).build();

// custom context module
import { ContextModuleBuilder, ContextModuleChainID } from "@ledgerhq/context-module";
const contextModule = new ContextModuleBuilder({ originToken })
  .setChain(ContextModuleChainID.Ethereum)
  .setCalConfig({ url: "https://global.api.prd.ledger.com/cal/v1", mode: "test", branch: "next" }) // README calls it addCalConfig; source has setCalConfig
  .removeDefaultLoaders()      // optional
  .addLoader(myCustomLoader)   // ContextLoader { canHandle(input, expectedTypes), load(input) -> ClearSignContext[] }
  .addTypedDataLoader(loader)  // replaces EIP-712 loader
  .build();
const signerEth = new SignerEthBuilder({ dmk, sessionId }).withContextModule(contextModule).build();

// signing
signerEth.signTransaction("44'/60'/0'/0/0", txBytes /* Uint8Array */, { domain?: string });
signerEth.signTypedData("44'/60'/0'/0/0", { domain, types, primaryType, message });
signerEth.signMessage("44'/60'/0'/0/0", "text shown on device");
// each returns { observable, cancel }; states NotStarted/Pending/Stopped/Completed/Error; Pending carries requiredUserInteraction (SignTypedData, SignPersonalMessage, UnlockDevice, ConfirmOpenApp, Web3ChecksOptIn, ...)
```
- Custom loader README warning: "The payload represents data sent to the device and must be signed by a trusted authority." i.e. you can plug any data source, but the device still verifies Ledger's signature. (VERIFIED)
- Context module supports Ethereum, Solana, Concordium. Marked "still under development", breaking changes possible.
- Transports in `device-sdk-ts`: `web-hid`, `web-ble`, `node-hid`, `rn-hid`, `rn-ble`, `speculos`, `mockserver`. Speculos transport: `npm install @ledgerhq/device-transport-kit-speculos`, `speculosTransportFactory("http://localhost:5000")`. (VERIFIED)
- Address book / contacts: "require a non-Nano S device and a recent Ethereum app" (Nano S Plus OK). Nano S (original) support was removed from app-ethereum in 1.17.0 (2025-05-05). (VERIFIED)

### 3.3 Local / dev loading: the ERC-7730 Tester and `@ledgerhq/cal-interceptor`

Sources: `device-sdk-ts/apps/sample/src/components/ClearSigningView/ERC7730TesterDrawer.tsx`, `packages/tools/cal-interceptor/src/*`, `apps/sample/api/index.py` (VERIFIED by reading source). Hosted at https://app.devicesdk.ledger.com/clear-signing-tools (JS app; page body did not render through fetch). Ledger's dApp guide says it works "with a connected Ledger signer or the Speculos emulator". (VERIFIED: https://developers.ledger.com/docs/clear-signing/for-dapps/get-started.md)

How it works:
1. You paste an ERC-7730 JSON. `ERC7730Client.processDescriptor()` POSTs to `/api/process-erc7730-descriptor` (Flask, same origin).
2. Flask uses `python-erc7730` (`erc7730_descriptor_to_calldata_descriptors`, `..._v2_...`, `convert_erc7730_to_eip712`, v1 and v2 both supported, auto-detected) to produce Ledger CAL-format descriptors, then **signs every TLV with a hard-coded `TEST_SIGNING_KEY`** (secp256k1, DER, "CAL staging key"), returning `{ data, signatures: { test: sig, prod: sig } }` keyed `chainId:address`.
3. `/api/certificates` fetches real certs from `global.api.prd.ledger.com/cal/v1/certificates`, filters to `cal_calldata_key, erc20_metadata_key, cal_network, plugin_selector_key, cal_trusted_name, cal_gated_signing, domain_metadata_key, token_metadata_key`, and **replaces the public key inside each certificate with `TEST_VERIFYING_KEY`** so "a Speculos device provisioned with the test certificates accepts it".
4. `CalInterceptor` monkey-patches `fetch`; for `/cal/.../dapps?output=descriptors_calldata|descriptors_eip712` and `/certificates?output=descriptor` it returns the stored local data. The drawer forces `calConfig.mode = "test"` while active.
5. Package `@ledgerhq/cal-interceptor` is `"private": true`, version 0.0.1: **not on npm**; you'd vendor it from the monorepo.

Consequences (INFERRED from the above):
- Works against Speculos running an Ethereum app built with test keys (`use_test_keys` in `ledger_app.toml`, per https://ethereum-plugin-sdk.ledger.com/test_framework/ragger/). A retail Nano S Plus / Flex runs the prod-key build and trusts only Ledger's PKI root, so the re-signed certificate and test-signed descriptors should be rejected → blind signing. I did not find any doc promising otherwise, and the sample app comments say "for Speculos testing" three times.
- `mode: "test"` on the real CAL only selects a different signature over the *same* Ledger-published descriptors (the `test` signature is by Ledger's test key, useful for Speculos). It is not a way to see unpublished descriptors. `branch: "next"`/`"demo"` may expose descriptors merged but not yet on `main` — undocumented; worth probing with curl (`GET .../dapps?output=descriptors_calldata&chain_id=1&contracts=0x...&ref=branch:next`).

### 3.4 Speculos on Windows

- Speculos docs: Linux native build; macOS via Docker; **Windows via WSL 2** (same build as Linux; display needs an X server such as VcXSrv with `export DISPLAY="$(sed -n 's/nameserver //p' /etc/resolv.conf):0"`, or run `--display headless` / `text`). `./speculos.py path/to/app.elf`, model auto-detected for recent SDK builds; OCR supports Nano X, Nano S+, Flex, Stax, Apex+. REST API default port 5000 (per DMK Speculos transport default). (VERIFIED: https://speculos.ledger.com/, /installation/wsl.html, /user/usage.html)
- You still need an app-ethereum ELF built with test keys for nanos2 (Nano S Plus) and/or flex. Options listed by Ledger: the VS Code Ledger extension builds dependencies, clone + build with test flags, or reuse a CI artifact from `app-plugin-boilerplate`. (VERIFIED)

## 4. Authoring workflow and tooling

- **JSON builder / preview**: Ledger's "ClearSigning.org Build" page https://clearsigning.org/build/ lists Sourcify's playground https://clear-signing.sourcify.dev ("Clear Signing Playground"), the Sourcify TS lib https://github.com/sourcifyeth/clear-signing (GUIDE.md for wallets), Rust lib https://github.com/llbartekll/clear-signing, Cyfrin `clearsig` https://github.com/Cyfrin/clearsig. Ledger's older "JSON Builder" (`get-clear-signed.ledger.com`) is not linked from current pages; search snippets still mention it giving device screenshots. (VERIFIED list; builder status INFERRED)
- **python-erc7730** (PyPI `erc7730` 1.0.11, 2026-09-09, Python >=3.12,<3.13; docs https://ledgerhq.github.io/python-erc7730; registry CI pins the `sourcifyeth/python-erc7730` fork). (VERIFIED)
  ```sh
  pip install --user erc7730            # or: uvx --from "$(cat .github/requirements.txt)" erc7730 <cmd>
  erc7730 schema                        # print JSON schema (add 'resolved' for resolved form)
  erc7730 lint registry/<entity>        # --v2 to force, --skip-abi-validation for offline
  erc7730 format
  erc7730 resolve <descriptor>.json
  erc7730 generate --chain-id=1 --address=0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45          # ABI from Sourcify/Etherscan
  erc7730 generate --chain-id=1 --address=0x0000000000000000000000000000000000000000 --abi abis.json
  erc7730 generate --chain-id=1 --address=0x0000000000000000000000000000000000000000 --schema schemas.json   # EIP-712 bootstrap
  erc7730 calldata registry/uniswap/calldata-UniswapV3Router02.json --chain-id=1   # Ledger Generic Parser descriptors
  erc7730 convert eip712-to-erc7730 <ledger-legacy.json> <out.json>
  export ETHERSCAN_API_KEY=...          # only needed when contract isn't on Sourcify
  ```
  Linter checks: ABI fetch (Sourcify → Etherscan), proxy heuristic, selector/field validity, EIP-712 primary type present, "Object too long … may be truncated on Ledger devices" for owner/legal name/URL/contract id/intent/label (size not documented on that page; see §7 for firmware numbers), Permit heuristic.
- **Registry layout** (`registry/<entity>/calldata-<Name>.json`, `eip712-<Name>.json`, `common-*.json`, `testsv2/*.tests.json`, `sigs/` attestations). `$schema` must be the relative path `"../../specs/erc7730-v2.schema.json"` (CI rejects URLs). One entity folder per PR. Every added/changed descriptor needs a `testsv2` fixture; calldata tests need ≥1 case per selector (`rawTx`), EIP-712 tests use `data`, both with `expected { intent, interpolatedIntent?, owner, fields }`. (VERIFIED: README)
- **Sourcify verification is mandatory** for calldata descriptors ("ci: require Sourcify verification and validate every deployment", PR #3038 merged Sep 24 2026; tutorial: "Sourcify verification is required before a descriptor is accepted"). (VERIFIED)
- Newer CI (Sep–Oct 2026): visual test report at `tests.erc7730.sourcify.dev/?pr=<n>`, EIP-55 checksum check, and an **advisory AI review** running two models per PR (currently `claude-sonnet-5-5` and `gpt-6-luna`; PR #3102 proposes GPT-6.1 Sol / Sonnet 5.5). (VERIFIED from PR titles/comments)

## 5. Review / registration timeline (the 3-day question)

Data pulled via GitHub API on 2026-10-10 (VERIFIED):

- Community (non-maintainer) PRs merged May–Sep 2026, created→merged: #2591 2d, #2950 <1d, #2910 5d, #2569 7d, #2562 8d, #2560 8d, #2572 11d, #2570 11d, #2576 14d, #2906 23d, #2593 29d, #2594 30d, #2661 40d, #2616 61d, #2599 86d, #2595 94d, #2581 107d, #2575 110d, #2578 124d, #2561 129d. Median ≈ 4 weeks; fast lane ≈ 1–2 weeks for clean PRs from known protocols.
- **19 community descriptor PRs opened Sep 14 – Oct 9 2026 are still open** (Wormhole, Symbiotic, Flare ×6, Safe, LI.FI, Morpho, Zodiac, Babylon, Cofund EIP-712, Taryven, Chainlink, 8 Polygon descriptors from one author, etc.). No descriptor PR from an external author merged since Sep 21 except Cyfrin-audit fixes by maintainers.
- Maintainer comment on #3072 (Oct 8): "The AI review is work-in-progress … Approving and merging descriptors will take time until we refined it. Sorry for keeping you waiting."
- Review guidelines (`docs/REVIEWING.md`): review is "deliberately short and basic", plausibility not security; no SLA stated. Post-merge: auditors (Cyfrin first) publish ERC-8176 EAS attestations; wallets set trust policy. (VERIFIED)
- Ledger's own docs: "Once a pull request is approved and merged, compatible wallets automatically fetch the metadata" (search snippet of a dead page) — but Ledger devices need the CAL-signed form, and no page documents the registry→CAL cadence. (INFERRED gap)

**Verdict**: Registry submission during the hackathon is good for the "DevRel feedback" write-up and shows process literacy, but it will not light up on a retail device before Oct 13 or Oct 16. Plan the demo without it.

## 6. EIP-712 and "approve this action" semantics on device

What the Ethereum app does with typed data (VERIFIED: `doc/eip712.md`, `doc/apdu.md`, CHANGELOG, `settings.py`, `shared_context.h`):

- Flow: struct definitions streamed (INS `0x1A`), optional FILTERING activation + message info + per-field filters (INS `0x1E`), implementations (INS `0x1C`), then SIGN. Domain and message fields are displayed as they stream.
- **With a Ledger-signed filter set** (from a registry descriptor): fields hidden by default, only filtered fields shown with their `display_name`, formats raw / amount-join / datetime / trusted-name / calldata. "Review <display_name>" intent. This is the ERC-7730 path.
- **Without a filter set**: "basic filtering handled by the app itself" + blind-signing friction (1.14.0). On **Stax & Flex the unfiltered flow defaults to raw/verbose mode** (shows every field with its struct key name, plus a skip button). On **Nano** you only get domain hash + message hash unless the user enables the in-app setting **"Verbose EIP712"** (`N_storage.verbose_eip712`; settings enum `VERBOSE_EIP712`), which then shows all raw fields. A "Display hash" setting (1.18.0, 2025-08) shows TX/EIP-712 hashes even while clear-signing. (VERIFIED; the exact Nano behaviour "hashes only" is INFERRED from changelog items "EIP-712 message hash being shown twice on Nano" and the verbose setting's existence.)
- `hw-app-eth` (deprecated in favour of DMK) notes `signEIP712Message` (full struct flow) "is not compatible with nano S (LNS)" and falls back to `signEIP712HashedMessage`. Nano S Plus is supported. (VERIFIED: https://cdn.jsdelivr.net/npm/@ledgerhq/hw-app-eth@7.8.11/README.md)
- So, for a hackathon "agent asks human to approve action X": sending EIP-712 typed data with descriptive field names (`action`, `target`, `expires`) and asking the demo user to toggle "Verbose EIP712" on the Nano S Plus (Flex shows it by default) gives readable, device-verified approval today, without a descriptor. It is labelled with blind-signing friction, which you should disclose.

### EIP-191 personal message (the zero-friction alternative)

- `SIGN ETH PERSONAL MESSAGE` (INS `0x08`): message streamed in 255-byte chunks. `cmd_sign_message.c` builds a display buffer: if every byte is printable/whitespace the **full text is displayed** (whitespace normalised to spaces on Nano); otherwise shown as `0x` hex. Hard cap `msg_length <= (65535-3)/2 = 32766` bytes; memory-allocated buffer, so practical length is device RAM. (VERIFIED)
- DMK: `signerEth.signMessage(derivationPath, message)` — "message: string, displayed on the device". (VERIFIED)
- Verifier side: `ecrecover` on `keccak256("\x19Ethereum Signed Message:\n" + len + msg)`; use viem `verifyMessage`. Any backend can check that *this* device key approved *this* text. No registry, no Ledger key, works on both devices now. (INFERRED standard practice)

## 7. Display limits: Nano S Plus vs Flex

Firmware constants (VERIFIED, app-ethereum `develop`):

| Item | Constant | Max chars (excl. NUL) |
| --- | --- | --- |
| Field label (generic parser) | `MAX_FIELD_NAME_SIZE 21` | 20 |
| Field separator | `MAX_SEPARATOR_SIZE 32` | 31 |
| Intent / operation type ("Review <x>") | `OPERATION_TYPE_SIZE 31` | 30 |
| Owner / creator name | `CREATOR_NAME_SIZE 23` | 22 |
| Creator legal name | `CREATOR_LEGAL_NAME_SIZE 31` | 30 |
| Creator URL | `CREATOR_URL_SIZE 27` | 26 |
| Contract name | `CONTRACT_NAME_SIZE 31` | 30 |
| Deploy date | `DEPLOY_DATE_SIZE 11` | `YYYY-MM-DD` |
| EIP-712 filters per message | `MAX_FILTERS 50` | 50 fields |

Screens (VERIFIED `ledger-secure-sdk/lib_nbgl/include/nbgl_types.h`): Nano S Plus / Nano X 128×64 px, smallest font 11 px (≈4 text lines, ~16–20 chars per line, INFERRED); Flex 480×600 px; Stax 400×672. NBGL "use case" review APIs paginate long values automatically; Nano shows one field (or part of one) per screen and the user scrolls; Flex/Stax show several fields per page ("Can now buffer & show multiple EIP-712 fields on one page for NBGL devices", changelog). The linter's "may be truncated" warning maps to the table above. (VERIFIED constants, INFERRED chars-per-line)

Practical: keep `intent` ≤ 30 chars, `label` ≤ 20 chars, `owner` ≤ 22 chars; long `raw` strings will paginate on Flex and scroll on Nano but are not refused.

## 8. Hackathon angles this enables

1. **Human-approval gate via EIP-191/EIP-712 on real hardware** (Nano S Plus + Flex): agent composes a plain-English action, user reads the whole message on the Secure Screen, signature returned to the agent/backend as an audit record. No registry dependency. Flex NFC/BLE doesn't change the signing flow.
2. **"Clear-signing lint & preview" for agents**: use `erc7730 generate` + `lint` + Sourcify playground to auto-draft descriptors for a target contract, and show the diff. Pitch: "the agent writes the ERC-7730 for the contract it wants to call, a human reviews, the registry PR is opened". Submit a real PR as part of the demo (good DevRel-feedback material).
3. **Speculos-backed clear-signing demo** (if time): WSL2 + Speculos + test-key `app-ethereum` + vendored `cal-interceptor` → show a custom descriptor rendering "Invite member"-style intent on an emulated Flex, while the real Flex shows the EIP-712 verbose fallback. Honest story about why retail devices can't take unsigned descriptors.
4. **Blind-signing detector UX**: DMK's `UserInteractionRequired` / context errors let the app warn "this will blind-sign" before the device prompt, as Ledger's docs require ("make sure your application warns users when signing falls back to blind signing").

## 9. Open questions / gaps

- Does a retail Nano S Plus/Flex really reject test-key-signed descriptors + rewritten certificates? Strongly implied by code, not tested. Quick test: run the hosted tester with the real Flex.
- Does `ref=branch:next` on the public CAL expose unreleased descriptors? Undocumented; probe with curl.
- How long between registry merge and CAL `main` availability? No public statement; ask on the hackathon Discord.
- Exact Nano unfiltered EIP-712 behaviour (hashes only vs raw fields) with Verbose EIP712 off — verify on the Nano S Plus before relying on it in the demo.
- Whether `originToken` is required for descriptor fetch (docs only tie it to Transaction Check). Test with and without.
- Ledger's hosted tester page needs its Flask API; running the DMK sample app locally requires Python + `erc7730` + Flask (`apps/sample/api/index.py`), not documented in the sample README.

## Sources

Ledger docs
- https://developers.ledger.com/docs/clear-signing/overview
- https://developers.ledger.com/docs/clear-signing/for-dapps/get-started.md
- https://developers.ledger.com/docs/clear-signing/for-wallets.md
- https://developers.ledger.com/docs/clear-signing/reference/external-resources
- https://developers.ledger.com/docs/clear-signing/erc7730/process
- https://developers.ledger.com/docs/clear-signing/eip712 (redirects to overview)
- https://developers.ledger.com/docs/clear-signing/eip712-messages (redirects to overview)
- https://developers.ledger.com/docs/clear-signing/reference/erc7730-reference.md (404 on 2026-10-10)
- https://developers.ledger.com/docs/clear-signing/reference/specifications.md (404)
- https://developers.ledger.com/docs/clear-signing/for-dapps/validate-submit.md (404)
- https://developers.ledger.com/docs/ledger-live/exchange/earn/clear-signing.md
- https://developers.ledger.com/docs/device-interaction/references/signers/eth.md
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/how_to_use_a_signer
- https://www.ledger.com/blog-ledger-clear-signing-ethereum-foundation
- https://www.ledger.com/blog-the-evolution-of-clear-signing
- https://ethereum-plugin-sdk.ledger.com/test_framework/ragger/

Standard / registry / ecosystem
- https://eips.ethereum.org/EIPS/eip-7730
- https://eips.ethereum.org/assets/eip-7730/erc7730-v3.0.0-next.schema.json
- https://ethereum.org/developers/tutorials/clear-signing
- https://github.com/ethereum/clear-signing-erc7730-registry (README, docs/REVIEWING.md, index.eip712.json, registry/safe/, PRs #3072 #3055 and PR list via GitHub API)
- https://github.com/LedgerHQ/clear-signing-erc7730-registry (old location, README mirrored)
- https://clearsigning.org/build/
- https://clear-signing.sourcify.dev
- https://docs.sourcify.dev/blog/intro-to-erc7730/
- https://ethereum-magicians.org/t/eip-7730-proposal-for-a-clear-signing-standard-format-for-wallets/20403
- https://pypi.org/project/erc7730/
- https://ledgerhq.github.io/python-erc7730 (+ /pages/usage_cli.html, /pages/lint.html)
- https://github.com/LedgerHQ/python-erc7730

Source code read (GitHub API, `develop`/`master`)
- LedgerHQ/device-sdk-ts: `packages/signer/context-module/README.md`, `src/ContextModuleBuilder.ts`, `src/config/model/ContextModuleConfig.ts`, `src/modules/ethereum/calldata/data/HttpCalldataDescriptorDataSource.ts`, `src/modules/ethereum/typed-data/data/HttpTypedDataDataSource.ts`; `packages/tools/cal-interceptor/{package.json,src/CalInterceptor.ts,src/ERC7730Client.ts,src/ERC7730Helper.ts}`; `apps/sample/src/components/ClearSigningView/{ERC7730TesterDrawer.tsx,CalNetworkDataSource.ts}`; `apps/sample/api/index.py`; `packages/transport/speculos/README.md`
- LedgerHQ/app-ethereum: `README.md`, `CHANGELOG.md`, `doc/apdu.md`, `doc/eip712.md`, `doc/gcs.md`, `doc/tlv_structs.md`, `src/public_keys.h`, `src/shared_context.h`, `src/features/generic_tx_parser/{gtp_field.h,gtp_tx_info.h}`, `src/features/sign_message_eip712/eip712_v1_filtering.{h,c}`, `src/features/sign_message/cmd_sign_message.c`, `client/src/ledger_app_clients/ethereum/settings.py`
- LedgerHQ/ledger-secure-sdk: `lib_nbgl/include/nbgl_types.h`
- https://cdn.jsdelivr.net/npm/@ledgerhq/hw-app-eth@7.8.11/README.md

Speculos
- https://speculos.ledger.com/
- https://speculos.ledger.com/installation/wsl.html
- https://speculos.ledger.com/user/usage.html

Not reachable / not rendered
- https://app.devicesdk.ledger.com/clear-signing-tools (JS shell only)
- https://kilnfi.notion.site/Clearly-Vaults-ETHGlobal-2024-140c1910fb6e80098f35d197fdaed427 (Notion, no content via fetch; cited from search snippet)
- https://docs.monad.xyz/guides/clear-signing (connection refused)
- https://www.npmjs.com/package/@ledgerhq/context-module, /@ledgerhq/cal-interceptor (403)
