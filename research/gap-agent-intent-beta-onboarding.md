# Ledger Agent Intent (beta): can a 3-day hackathon project rely on it?

> **Correction (2026-10-10, source audit).** On OS 1.7.0 the production catalog (provider 1) serves Ledger Sync 1.2.2; >= 1.3.0 (1.4.2) is only on provider 4, so plan on switching My Ledger to provider 4 rather than an automatic install. See `source-audit.md` §2 (M12).

Researched 2026-10-10 from primary sources only (docs page, wallet-cli `develop` source, the vendored SDK tarball unpacked, the deployed frontend's JS bundles, GitHub PRs via authenticated `gh`, npm registry, Terms of Use). No hardware touched, nothing installed. Scratch copies of every file read are under the session scratchpad (`.../scratchpad/ai/`).

Legend: **VERIFIED** = read in a primary source (code, docs, HTTP response). **INFERRED** = deduced from those sources; not executed end to end.

---

## TL;DR

- **Enrolment is not allow-listed.** No invite/waitlist/allowlist logic exists in the frontend bundle, the Terms of Use set no beta gate (only 18+ and sanctions), the production Keycloak realm is publicly reachable, and the production BFF answers 401 (auth) not 403 (blocked). Prerequisites are only: a supported device, **Ledger Sync already activated in Ledger Wallet**, a Chromium browser, and the Ledger Sync device app >= 1.3.0 (auto-installed). **INFERRED open to anyone**; we could not confirm by actually enrolling.
- **The only working environment is `production` served at `https://agent-intent.ledger-test.com/`.** Despite the hostname, that site is configured `AGENTIC_ENV: "production"` with the prd BFF. `agent-intent.ledger.com` (the SDK's "production" frontend) **does not resolve**. The staging BFF and staging Keycloak return **403** from the public internet. `--environment staging` is dead for outsiders. **VERIFIED.**
- **Ethereum mainnet, real funds, only.** The SDK throws on any `network !== "ethereum"`; the CLI rejects any non-`ethereum:main` account; the skill says "The Agent Intent SDK has no testnet, so a staging profile also proposes an Ethereum mainnet transfer." No Sepolia, no L2, no Solana in the released CLI. **VERIFIED.**
- **A non-CLI agent can create intents directly.** The vendored `@ledgerhq/agent-intent-sdk` (UNLICENSED, "restricted" publishConfig, but sitting in the public ledger-live repo) exports `createAgentIntentClient(...).createSendIntent()` which does one `POST {bff}/v1/intents` with a Bearer token obtained via an LKRP/Keycloak challenge. It also exports the whole enrolment-channel host, so a Node process can enrol itself without wallet-cli and persist the key however it likes. Node >= 24. Browser use is unverified (CORS unknown, and the agent secret would live in the browser). **VERIFIED exports; INFERRED browser limits.**
- **Nothing new merged since 2026-10-05 except two fixes.** `intents`, `status`, `cancel`, `swap`, native-SOL `send` are all **open PRs** (stacked, each re-vendoring a different SDK pack). Merged after 2.9.0: `--source` default change (#22688, 10-07) and a `sync` address bug fix (#22980, 10-06). **npm 2.9.0 (published 2026-10-05) therefore ships a `sync` that imports the wrong ETH/SOL addresses** and defaults `--source` to `openclaw`. **VERIFIED.**
- **Windows is a first-class host.** Keychain = `@napi-rs/keyring` -> Windows Credential Manager; the code has explicit CRLF handling for Windows; the feature author runs the test suite on Windows; wallet-cli ships a `windows-x64` binary. No dialogs are expected. WSL has no Secret Service and will fail. **VERIFIED code, INFERRED runtime behaviour.**
- **Execution:** the human opens `/intents/<id>` in the frontend, the frontend asks the BFF to **craft** the raw tx, the device signs it (Ethereum app, clear signing), the frontend posts the signature to `/v1/intents/{id}/signature`, and **Ledger's backend broadcasts** (statuses `crafted -> signed -> broadcast -> success`). The agent's free-text `description` is shown on the **web page only**; the device shows the standard Ethereum clear-signing screens (amount, recipient, fees). **VERIFIED flow from bundle; INFERRED that description never reaches the device.**

**Verdict for a 3-day build:** usable as a *demo backbone* if the team has one Ledger Sync-enabled account on Ethereum mainnet with a few euros of ETH and accepts real gas. It is **not** usable for anything that needs testnets, Solana, swaps, cancel/status polling, or a second chain. Budget half a day for the enrolment flow to fail once (frontend is "still being developed", enrolment is non-resumable). Have the fallback (below) wired on day 1.

---

## The seven questions

### 1. Is enrolment open or gated?

| Evidence | Status |
|---|---|
| Frontend bundle (`index-BJNJB1el.js`, 923 KB) greps for `waitlist`, `allow-?list`, `invite`, `invitation`, `beta access`, `closed beta`, `early access`, `whitelist`: only hits are a router `protocolAllowlist`, the DMK `allow-list-apps` device step, a swap `providers-whitelist` param, and one `BETA` badge string. No eligibility screen. | VERIFIED |
| Terms of Use (effective 28 Sep 2026): eligibility is 18+ with legal capacity and not on UN/OFAC/BIS/EU/UK sanctions lists. "The page does not mention invite-only access, waitlists, or allowlists." No country list. | VERIFIED |
| Production Keycloak realm discovery `https://global.api.prd.ledger.com/keycloak/realms/agent-intent-customers/.well-known/openid-configuration` -> **200** with issuer JSON. | VERIFIED |
| Production BFF `https://global.api.prd.ledger.com/agent-intent/v1/intents` unauthenticated -> **401** (auth required, not blocked). | VERIFIED |
| Sign-in is not an email/password account. The frontend authenticates with Ledger Sync via the device (`lkrp-authenticate`, "Confirm authentication on your Ledger device."). The agent's token comes from Keycloak realm `agent-intent-customers`, client `agentic-client`, broker `lkrp` (an LKRP challenge signed by the agent key). | VERIFIED |
| Docs: "If you don't have Ledger Sync activated already, you will be redirected to Ledger Wallet to activate before continuing." Ledger Sync device app >= 1.3.0 "installs automatically at Ledger Agent Intent onboarding"; manual path is Ledger Wallet > Settings > Experimental features > "My Ledger provider" = 4. | VERIFIED |
| Devices: "Ledger Nano Gen 5, Flex, Stax, Nano X, Nano S Plus" supported; original Nano S not. Browser must expose WebHID or Web Bluetooth (Chrome/Edge/Brave; not Safari/Firefox). | VERIFIED |

**Conclusion:** no allow-list is visible anywhere. The real gate is "you must already use Ledger Sync". Set that up in Ledger Wallet desktop on day 1 with the Flex (or Nano S Plus) before touching Agent Intent. **INFERRED** open to all; a server-side allow-list we cannot see is possible but there is no trace of one in UI copy or error strings.

### 2. Exact end-to-end enrol flow

**Agent side (wallet-cli 2.9.0, `enroll.ts`):**

```bash
npm i -g @ledgerhq/wallet-cli          # 2.9.0, 2026-10-05; ships windows-x64 binary
wallet-cli skill install               # optional: installs the skill into your coding agent
wallet-cli agent-intent enroll \
  --profile voice-bot \
  --name "Voice Bot" \
  --description "Proposes ETH payments from voice commands" \
  --source other \                     # 2.9.0 defaults to openclaw (!); develop defaults to other
  --app-url https://agent-intent.ledger-test.com/ \
  --expires-in 2h                      # default 30m, max 30d; link AND relay wait share this bound
# --environment production is the default and the only one that works (see Q3)
```

Order of operations inside `enroll` (VERIFIED from source):

1. Parse `--expires-in` (`^[1-9]\d*[smhd]$`, max 30d). Resolve BFF default `https://global.api.prd.ledger.com/agent-intent` (staging: `https://global.api.stg.ledger-test.com/agent-intent`), app URL default from SDK `AGENT_INTENT_FRONTEND_URLS` (production = `https://agent-intent.ledger.com/`, which is why the docs make you pass `--app-url`).
2. Precheck the profile id is unused in `session.yaml` and has no orphaned keychain entry.
3. `createSoftwareAgentIdentity()` (fresh secp256k1 key), `createRelayHost()` (WebSocket host against `https://trustchain.api.live.ledger.com`, candidate + completion timeouts stretched to `--expires-in`).
4. Build a **v2 enrollment request** bound to the relay host's ephemeral public key, and the URL: `https://agent-intent.ledger-test.com/agents/new?v=2&publicKey=…&name=…&description=…&source=…&expiresAt=…&channelEnvironment=production&channelHost=…&signature=…`. Only the public key travels; the URL is self-signed.
5. Under a cross-process file lock: save the secret key to the OS keychain, add the pending profile to `session.yaml`. On failure roll back the keychain write.
6. **Print** (human mode): the enrollment URL, the public-key fingerprint, the text "Compare this fingerprint with the one shown when the enrollment link is opened, before approving — this step never touches a Ledger device." and `Profile "voice-bot" saved as pending. Waiting for approval until <ISO> — keep this process running.` In `--output json` mode: one NDJSON line `{"type":"enrollment-pending","command":"agent-intent enroll","network":"all","profileId","enrollmentUrl","fingerprint","expiresAt"}`.
7. **Block** on `host.waitForCompletion()`. SIGINT/SIGTERM close the socket and abort. Timeouts (SDK README): 15 min for the browser to connect by default, but wallet-cli overrides candidate and completion timeouts to `--expires-in`; handshake, persist, ack are 30 s each.
8. When a completion arrives: `authenticateEnrollmentCompletion` gets an App-18 Keycloak token with the agent key for the claimed `trustchainId`, then restores the App-16 (Ledger Sync) trustchain with the agent key and requires JWT permission exactly `0xfffffffb` ("controlled-test grant"). Then persists `trustchainId` + `accountAccess {mode: "direct-app16-key-reader", environment, trustchainId, applicationPath m/0'/16'/N'}`.
9. Prints `✔ Agent Intent profile "voice-bot" enrolled. Trustchain ID: <id> (account access: production)` or JSON envelope with `enrolled: true`.
10. On any failure/timeout: `Enrollment did not complete (...). Profile "voice-bot" stays pending and cannot be resumed — start a fresh enrollment with a new --profile id.`

**Human side (web app at `/agents/new`, VERIFIED from bundle strings + docs, screen order INFERRED):**

1. Page "Agent Enrollment - Review" shows name, description, source, **Agent ID** (fingerprint) with copy "This is your agent's unique cryptographic identity..." and "When you approve, your agent's ID is registered by your Ledger device, ensuring only your agent can send you proposals." Compare the fingerprint with the CLI output.
2. Sign in with Ledger Sync: choose transport (USB or Bluetooth; "USB is unavailable on iPhone and iPad"), browser device picker, "Enter your PIN to unlock your Ledger device.", "Allow the secure connection on your device to check Ledger Sync.", "Confirm opening the Ledger Sync app on your device.", "Confirm authentication on your Ledger device." If Ledger Sync is not activated, hand-off link `https://go.ledger.com/ledger/ledgersync`.
3. "Approve agent on your Ledger": the frontend calls `addMemberWithHardware(..., {id: publicKey, name, permissions})` on the **App-18** trustchain. Docs: "Your signer shows the truncated fingerprint of your public key, your 'Agent ID'". Refusal string: "Agent approval was cancelled or refused on your Ledger device."
4. "Allow the agent to see your Ledger accounts" -> `addMembersToSubtreeWithHardware` on the **App-16** (Ledger Sync) subtree; another device confirmation. Failure copy: "Full Ledger Sync account access was not shared." / "Enrollment completed without App-16 account access."
5. Delivery: "Your Ledger approved the agent. Sending the encrypted result to your agent…" -> "The encrypted result was delivered and acknowledged by your agent." Failure: "Your agent hasn't confirmed the result yet. Make sure its enroll command is still running, then re[try]" and "Agent not confirmed ... this request has [expired]".

**Device-specific notes (INFERRED):** Nano S Plus = USB/WebHID only, button navigation through the Ledger Sync app prompts. Flex = USB or Web Bluetooth (Chrome on Windows 11 supports Web Bluetooth), touch confirmations. Both need the latest OS; the Ledger Sync app install happens through the frontend's DMK session (string "Preparing a one-time update for your agents" / `allow-list-apps` / `confirm-open-app` steps exist in the bundle).

**After enrolment, to make `--account` labels work:**

```bash
wallet-cli agent-intent sync --profile voice-bot      # imports Ledger Sync accounts, no device
wallet-cli session view                               # shows ethereum-1 etc.
```

Gotcha (VERIFIED, PR #22980 merged 2026-10-06, **not in npm 2.9.0**): 2.9.0's `sync` stores the seed public key (`04…`) instead of the address for Ethereum/Solana accounts, so `balances` says `Bad address` and `send --account ethereum-1` proposes from a bogus sender. **Workaround: pass `--from 0xYourAddress` instead of `--account`**, or run wallet-cli from source on `develop`. PR text: "This isn't in production yet, so there is no migration."

### 3. Does `--environment staging` allow anything other than Ethereum mainnet?

No. And staging is not reachable anyway.

- SDK `intents.js`: `if (intent.network !== "ethereum") throw new AgentIntentSdkError('unsupported network …')`. Type `SendIntent.network: "ethereum"`. **VERIFIED**
- CLI `send.ts` `resolveSenderFromAccount`: requires `name === "ethereum" && env === "main"`, else `Agent Intent send intents support Ethereum mainnet accounts only.` **VERIFIED**
- Skill: "Ethereum mainnet only ... The Agent Intent SDK has no testnet, so a staging profile also proposes an Ethereum mainnet transfer." **VERIFIED**
- Docs: "This is not a sandbox. The intents you approve produce real signatures and real on-chain transactions." **VERIFIED**
- Staging hosts from the public internet (curl, 2026-10-10): `https://global.api.stg.ledger-test.com/agent-intent/v1/intents` -> **403**; `https://global.api.stg.ledger-test.com/keycloak/realms/agent-intent-customers/.well-known/openid-configuration` -> **403** (prod equivalent -> 200). `https://agent-intent.ledger.com/` -> **DNS does not resolve**. **VERIFIED**
- The deployed `agent-intent.ledger-test.com` page injects `BFF_BASE_URL: "https://global.api.prd.ledger.com/agent-intent"`, `AGENTIC_ENV: "production"`, `ENABLE_MOCKS: "false"`. The "test" hostname is the production beta. **VERIFIED**

Contradiction worth a dev-feedback line: the SDK constant says staging frontend = `ledger-test.com`, production = `ledger.com`; reality is the reverse of what a reader expects, so a default `enroll` (production, no `--app-url`) prints a link to a host that does not resolve.

Also not in 2.9.0: ERC-20 is supported (`--token <contract>` resolved via CAL), native ETH is supported, nothing else. Open PRs would add native SOL (`solana:main`, `--memo`, no SPL) and swaps (ETH/ERC-20 mainnet, providers `oneinch|velora|okx|lifi`).

### 4. What does the vendored SDK expose, and can a non-CLI agent use it?

`vendor/ledgerhq-agent-intent-sdk-0.0.0.tgz` (42,652 bytes) unpacked: `package.json` (`@ledgerhq/agent-intent-sdk` 0.0.0, `"license": "UNLICENSED"`, `publishConfig.access: "restricted"`, deps only `@noble/curves` 2.4.0 + `@noble/hashes` 2.4.0, `engines.node >= 24`, ESM only), `README.md`, and `dist/` with: `auth`, `bytes`, `client`, `completion`, `enrollment`, `enrollmentChannel`, `fingerprint`, `identity`, `intents`, `recovery`, `requestFields`. **VERIFIED**

Public surface (from `.d.ts`, VERIFIED):

- `createSoftwareAgentIdentity(secretKey?)` -> `{publicKey, signDigest, deriveSharedSecret, exportSecretKey}`
- `createAgentEnrollmentRequest(identity, {name, description, source, expiresAt, channel?})`, `createAgentEnrollmentUrl(baseUrl, request)` -> `/agents/new?...`, `validateAgentEnrollment(search)`
- `createAgentEnrollmentChannelHost({environment, relayBaseUrl, timeouts?})` -> `{binding, waitForCompletion({request, authenticate, persist}), close}`; `createAgentEnrollmentChannelCandidate` (browser side)
- `createAgentRecoveryRequest`, `createAgentRecoveryUrl`, recovery completion helpers
- `createAgentTokenProvider({identity, trustchainId, keycloak, fetch?})`, `AGENT_KEYCLOAK_ENVIRONMENTS` (staging/production realm `agent-intent-customers`, client `agentic-client`, broker `lkrp`), `staticAccessTokenProvider(token)`
- `createAgentIntentClient({bffBaseUrl, identity, trustchainId, environment, keycloak?, tokenProvider?, fetch?, authFetch?})` -> `{publicKey, createSendIntent(intent): Promise<deeplink>, createSignedIntent(intent, nonce?)}`
- `SendIntent = {type:"send", network:"ethereum", sender, recipient, amount: bigint|string, asset: {type:"native"} | {type:string, assetReference, assetOwner?}, feeStrategy:"slow"|"medium"|"fast", description?}`; `encodeSendIntentTlv`, `signCreateIntent`, `serializeCreateIntent`, `createNonce`
- `formatAgentPublicKeyFingerprint(pubkey)`, `SUPPORTED_AGENT_SOURCES = ["openclaw","hermes","claude-code","codex","cursor","muse","grok-bot","other"]`
- Not present in this pack: `listIntents`, `createSwapIntent`, status, cancel (those live in unmerged SDK PRs #16/#17/#19/#21 that the open wallet-cli PRs vendor).

What `createSendIntent` does on the wire (VERIFIED from `client.js` + `auth.js`):

1. Keycloak PKCE auth-code dance against `{keycloak.baseUrl}/realms/agent-intent-customers/protocol/openid-connect/auth?response_type=code&client_id=agentic-client&scope=openid&redirect_uri=.../broker/lkrp/endpoint&code_challenge=...` with `Accept: application/json` -> returns an LKRP challenge TLV + `json.host`.
2. Sign `sha256(challengeTlv)` with the agent key (DER), `POST https://{host}/openid/v1/authenticate` -> authorization code; `POST .../openid/v1/token` (grant `authorization_code`); `POST .../openid/v1/exchange` with Bearer idp token -> final `access_token`. A Node cookie jar is emulated (`withNodeCookieJar`).
3. `POST {bff}/v1/intents` with `Authorization: Bearer <token>`, `Content-Type: application/json`, `Accept: text/plain`, body `{issuer, signature, nonce, intent}` where `intent.amount` is an exact integer string and `signature` is the agent's signature over the TLV encoding (tags 0x11 sender, 0x12 recipient, 0x13 amount, 0x14 asset, 0x15 fee, 0x16 description, 0x23 network). Response body is a plain-text deeplink; the SDK rewrites it onto the frontend origin -> `https://agent-intent.ledger-test.com/intents/<id>`.

Minimal Node usage (adapted from the SDK README, VERIFIED shape; `savedSecretKey` and `trustchainId` come from an enrolment):

```ts
import { createAgentIntentClient, createSoftwareAgentIdentity } from "@ledgerhq/agent-intent-sdk";
const identity = createSoftwareAgentIdentity(savedSecretKey);
const client = createAgentIntentClient({
  bffBaseUrl: "https://global.api.prd.ledger.com/agent-intent",
  identity, trustchainId, environment: "production",
});
const deeplink = await client.createSendIntent({
  type: "send", network: "ethereum", sender, recipient,
  amount: "1000000000000000", asset: { type: "native" },
  feeStrategy: "medium", description: "Voice: pay Alice 0.001 ETH",
});
```

Headless enrolment without wallet-cli (SDK README, VERIFIED):

```ts
const host = createAgentEnrollmentChannelHost({ environment: "production", relayBaseUrl: "https://trustchain.api.live.ledger.com" });
const request = createAgentEnrollmentRequest(identity, { name, description, source: "other", expiresAt, channel: host.binding });
console.log(createAgentEnrollmentUrl("https://agent-intent.ledger-test.com/", request));
await host.waitForCompletion({ request, authenticate: async c => {/* verify App-18 token */}, persist: async c => {/* save c.trustchainId, c.accountAccess */} });
```

Practical answer for a voice agent:

- **Easiest:** shell out to `wallet-cli agent-intent send ... --output json` and parse `deeplink`. Zero SDK licensing questions, keychain handled.
- **Direct:** `npm i ./vendor/ledgerhq-agent-intent-sdk-0.0.0.tgz` in a Node 24 service and call `createSendIntent`. Works in Node (uses `fetch`, `WebSocket`, `@noble`). **INFERRED** it would also run in a browser bundle, but (a) BFF CORS for arbitrary origins is unknown, (b) putting the agent secret in a browser defeats the model. Keep intent creation server-side.
- **Licence:** the tarball is `UNLICENSED` and intended for Ledger's private JFrog registry; the wallet-cli PR says it "should be replaced by the registry version once the package is published". Using it in a hackathon demo is tolerated-looking but not granted. Say so in the write-up.
- **Raw HTTP without the SDK** is possible (the three auth legs + one POST above) but you would have to re-implement the TLV encoding and LKRP challenge signing; not worth it in 3 days.

### 5. Did `cancel|status|intents|swap` and native-SOL `send` merge since 2026-10-05?

No. As of 2026-10-10 (authenticated `gh api`, VERIFIED):

| PR | Adds | State | Base branch | Note |
|---|---|---|---|---|
| #22400 | `enroll/recover/list/show` | **merged 2026-10-05 09:25Z** | develop | in npm 2.9.0 |
| #22461 | `sync` | **merged 2026-10-05** | (stacked) | in npm 2.9.0 |
| #22476 | `send` (ETH/ERC-20) | **merged 2026-10-05 11:16Z** | develop | in npm 2.9.0 |
| #22980 | fix `sync` addresses | **merged 2026-10-06** | develop | **not** in npm 2.9.0 |
| #22688 | `--source` default `other`, recover for all sources | **merged 2026-10-07** | develop | **not** in npm 2.9.0 |
| #23033 | `agent-intent intents` (list, `--status`, `--page-size`, `--cursor`) | open | develop | vendors SDK PR #16 |
| #23037 | `agent-intent status` | open | branch of #23033 | stacked |
| #23174 | `agent-intent cancel` | open (created 10-09) | branch of #23037 | stacked |
| #23045 | `agent-intent swap` | open | develop | vendors SDK PR #19; checklist unticked |
| #23105 | `send` native SOL (`--memo`) | open | develop | vendors SDK PR #21; needs frontend #209 |
| #22976 | skill: forbid sandbox escapes during enroll | open draft | develop | docs only |
| #22992 | `sync`: skip unknown derivation modes | open | develop | |

npm: `@ledgerhq/wallet-cli` dist-tag `latest` = **2.9.0**, published 2026-10-05T19:23Z; no newer release. Each open PR says "Whichever lands later needs one pack built from the SDK main that contains all of them" and "Manual test on production with an enrolled profile" is unticked on #23033/#23045. **Do not plan on any of these landing before Oct 13.** If you need `status`/`cancel`, the frontend exposes `GET /v1/intents/{id}`, `POST /v1/intents/{id}/reject`, `GET /v1/intents`, `GET /v1/intents/stats` to the *human* session, not to the agent token (agent-scoped listing is "live in service v0.3.0" per #23033 but has no released client). Polling for approval from the agent side is therefore **not available in 2.9.0**; the human sees the result in the web app.

### 6. Windows Credential Manager behaviour

- Keychain backend is `@napi-rs/keyring` (`Entry(service, account)`), i.e. keyring-rs; npm 2.1.0 ships `win32-x64-msvc`, `win32-arm64-msvc`, `win32-ia32-msvc` binaries. **VERIFIED**
- Service name `ledger-wallet-cli` (`APP_NAME`); account `agent-intent-key-<16 hex>` where the hex is `sha256(stateDir + " agent-intent " + profileId)[0:16]`. Entries therefore appear in Credential Manager > Windows Credentials > Generic Credentials. **VERIFIED naming; INFERRED exact TargetName format (keyring-rs composes it from service and account).**
- `loadAgentIntentSecretKey` does a "CRLF-tolerant trim: a keychain entry written on Windows may carry a trailing \r" — the authors tested on Windows. PR #22980/#23033 bodies: "In `pnpm test`, the failing set is identical to `develop` on Windows (symlink/file-mode tests)." **VERIFIED**
- Error text if the store fails: `Could not store the agent's secret key in the OS keychain (...). Agent Intent needs a working OS keychain: macOS Keychain, Windows Credential Manager, or on Linux a running Secret Service provider ... Nothing was saved.` No file fallback by design. **VERIFIED**
- State dir on Windows (bunli `stateDir`): `%LOCALAPPDATA%\ledger-wallet-cli\State\` holding `session.yaml` and `.session.lock`. **VERIFIED code path; INFERRED exact join.**
- Secret is stored **unencrypted** in the credential blob unless a wrapping key is passed (the CLI passes none for Agent Intent). Windows Credential Manager does not prompt the user for Generic Credentials, so no UI dialog is expected during `enroll`/`send`. **INFERRED**
- **WSL/containers/CI:** no Secret Service -> `enroll` fails. Run wallet-cli natively on Windows (PowerShell), not in WSL. The skill's "sandbox" note (needs `dangerouslyDisableSandbox: true` for `enroll/recover/sync/send`) is about agent sandboxes blocking keychain + WebSocket access, not about Windows. **VERIFIED**
- Password-protected entries (`ENC:` prefix) exist in the format but no CLI flag sets one for Agent Intent; if the store is `ENC:` the CLI throws `AgentIntentPasswordRequiredError`. **VERIFIED**

### 7. How is an approved intent executed, and does the description reach the device?

From the frontend bundle `useIntentReviewFlow-C0W2wnAb.js` (VERIFIED strings; sequencing INFERRED):

1. Human opens `https://agent-intent.ledger-test.com/intents/<id>` ("Intent Review - Send"). Page fields: `Proposed by`, `Amount`, `To :`, `Fee priority :`, and the agent's `Description` rendered in a muted box. Status badges: `created`, `crafted` = "Pending your approval", `signed`, `broadcast` = "Broadcasted", `success` = "Accepted", `failed`, `rejected`, `expired`.
2. `POST /v1/intents/{intentId}/craft` -> BFF returns `{rawTransaction, details}`; the frontend treats it as `broadcast: false` ("The craft response did not contain a valid raw transaction." otherwise).
3. "Review transaction on your Ledger": device signs through the Ledger Wallet Provider / Ledger Button core (`@ledgerhq/ledger-wallet-provider-core`) in the **Ethereum app**; the frontend parses the returned signed RLP (legacy / type-1 / type-2) and extracts r,s,v. Refusal string: "User refused on the device".
4. `POST /v1/intents/{intentId}/signature` with `{signature}`. Error source `broadcast`: "The signed transaction could not be submitted." -> **Ledger's backend broadcasts**, not the browser and never the agent.
5. Reject path: `POST /v1/intents/{intentId}/reject` (no device needed).

Docs confirm the device side: "You review the transaction with Clear Signing and Transaction Check before you sign it." and "The description your agent wrote is text the agent controls and can differ from the transaction itself. If the two disagree, reject." That sentence is the strongest evidence that **the description is web-only and the device shows only the crafted transaction** (amount, recipient hex, fees). **INFERRED** (no device-screen capture available).

Agent-side execution feedback: none in 2.9.0 (see Q5). The CLI prints "Open the link to review it; it only executes once approved on a Ledger device." and returns.

---

## Other facts a team needs

- **Who built it / jury link.** The precursor repo `brackets-fistfulayen/ledger-agent-intents` (created 2026-02-04, last push 2026-04-13, "Agent Intent Queue + Ledger Hardware Signing - Hackathon Project", for Circle's USDC/OpenClaw hackathon on Moltbook) is owned by an org whose name is Ian C. Rogers' GitHub handle (`fistfulayen` = "ian c rogers"). It used an Express/Postgres intent queue, x402 EIP-3009 payments on Base (chainId 8453), DMK via WebHID/BLE, and agent auth via `Authorization: AgentAuth <timestamp>.<bodyHash>.<signature>`. The production Agent Intent kept the "Agents propose. Humans sign/approve. Ledger enforces." slogan, the secp256k1 agent key, and the review-link UX, but moved to LKRP trustchains (App-18 for the agent registry, App-16 for Ledger Sync accounts), Keycloak, a BFF, and an encrypted WebSocket relay. **VERIFIED**
- **Ian Rogers (jury) wrote the Agent Stack preview and the roadmap** that lists Agent Intents in Q3 and Agent Policies ("spend no more than $500/day") after; see `research/prior-art-hackathon-projects.md`. Terms of Use already mention "Agent Rules" and approval "under your configured Agent Rules" -> policies are coming but not in the product today. **VERIFIED Terms text; INFERRED not shipped (no rules UI strings in bundle).**
- **Frontend routes:** `/`, `/agents/new` (enrolment), `/agents/$id`, `/intents/$id`, `/history`. BFF (human session) endpoints seen: `/v1/agent-profiles`, `/v1/agent-profiles/{agentPubkey}`, `/v1/tokens`, `/v1/intents`, `/v1/intents/stats`, `/v1/intents/{id}`, `/craft`, `/signature`, `/reject`, `/v1/qr`. **VERIFIED**
- **Removal is two steps and "still being developed":** remove in Agent Intent, then remove the member in Ledger Wallet's Ledger Sync settings. Frontend copy: "You will first have to remove account access through Ledger Wallet. Once it's removed in Ledger Wallet, click 'Check again' below." **VERIFIED**
- **Profiles are single-machine state.** Secret in the local keychain, metadata in `session.yaml`. Moving the agent to a VM means re-enrolling (or `recover` with the same key copied by hand, which the CLI does not support). **VERIFIED**
- **`--expires-in` also bounds the relay wait**, so a 30 m default is a 30 m window for the human to finish the whole web flow, including a possible Ledger Sync app install. Use `--expires-in 2h` for demos. **VERIFIED**
- **Feedback form (required dev-experience write-up fodder):** `https://forms.gle/MdYoA1Sc6ESuWmCp8`. Concrete, verifiable complaints: SDK frontend constants inverted vs reality; npm 2.9.0 `sync` imports wrong addresses; default `--source openclaw` mislabels agents in 2.9.0; no agent-side status/list in the release; staging unreachable; "production" frontend DNS missing. **VERIFIED**

---

## Can a 3-day project rely on it?

**Yes, narrowly, as the approval rail for a mainnet ETH/ERC-20 payment demo**, if all of the following are true on day 1:

1. One team member has Ledger Sync activated in Ledger Wallet on the Flex (BLE or USB) or Nano S Plus (USB), and the device OS is current.
2. The Ethereum mainnet account connected to Ledger Sync holds a few euros of ETH (gas) and you are willing to send real value (send to yourself).
3. Enrolment runs on a native Windows PowerShell (or macOS) shell with Chrome/Edge; not WSL, not a container.
4. You use `--from <0xaddress>` (not `--account`) unless running wallet-cli from `develop`.
5. The demo tolerates "agent proposes -> human approves in the web app -> tx appears on Etherscan" with the agent learning the outcome only by the human telling it (or by the team polling Etherscan for the sender's nonce). **INFERRED** workaround.

**No** if the pitch needs: testnets, Solana/L2/Base, swaps, cancel, agent-side status, policy rules, or any device other than the signer the human already uses with Ledger Sync.

### Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Enrolment fails mid-flow (frontend "many items still in development ... expect bugs and mocked parts") | medium | Pre-enrol on Oct 10/11; keep `--expires-in 2h`; new `--profile` id each attempt; record a video of a successful run immediately. |
| Ledger Sync app 1.3.0 install stalls | low-medium | Install via Ledger Wallet > Experimental > My Ledger provider 4 beforehand. |
| Service-side allow-list we cannot see | low | Discover on day 1; fallback below. |
| Frontend/SDK contract changes during the week ("can change without notice") | medium | Pin `@ledgerhq/wallet-cli@2.9.0`; do not depend on open PRs. |
| Real-funds mistake | low | Dedicated account, tiny amounts, send to self; `--dry-run` first. |

### Fallback if enrolment is gated or breaks

Build the **same shape** with primitives that are released and fully local; the jury cares about the agent/human boundary, not the hosted queue:

1. **Signer-in-the-loop via DMK** (`research/dmk-ts-signer.md`, `research/dmk-skills.md`): the voice/Node agent builds the transaction, your own tiny web page (WebHID/BLE) or Node (node-webusb transport) asks the device to clear-sign it; the human reviews on-device; your code broadcasts. Works on Sepolia, works with both devices, no Ledger backend dependency. This is also exactly what wallet-cli's own `send` does (it "always broadcasts" per issue #21908).
2. **wallet-cli as the executor** (`research/ledger-cli-agent-stack.md`): agent runs `wallet-cli send ethereum-sepolia-1 --to … --amount '0.01 ETH' --dry-run` to propose and the human runs the same command without `--dry-run` with the device plugged in. Crude but honest about the boundary and testnet-capable.
3. **Own intent queue** modelled on `brackets-fistfulayen/ledger-agent-intents` (MIT): agent signs intents with a secp256k1 key (`AgentAuth` header), human reviews in a page and signs with DMK. This is what the juror himself built; a 2026 version that uses Agent Intent *when available* and falls back to the local queue otherwise is a defensible architecture and a strong "DX feedback" story.

Keep Agent Intent as an **optional adapter** behind one interface (`proposeIntent(send) -> reviewLink`), with the DMK/local path as the default that always demos.

---

## Sources (all read 2026-10-10)

- Docs: https://developers.ledger.com/docs/ai-tools/agent-intent and raw `.md` https://developers.ledger.com/docs/ai-tools/agent-intent.md
- Frontend: https://agent-intent.ledger-test.com/ (index HTML with injected `__APP_CONFIG__`), bundles `/assets/index-BJNJB1el.js`, `/assets/useIntentReviewFlow-C0W2wnAb.js`, `/assets/mockLedgerAccounts-fQOC6w2P.js`
- Terms: https://shop.ledger.com/pages/ledger-agent-intent-terms-of-use ; Ledger Sync hand-off https://go.ledger.com/ledger/ledgersync
- wallet-cli source (`develop`): https://github.com/LedgerHQ/ledger-live/tree/develop/apps/wallet-cli — `src/commands/agent-intent/{index,enroll,send,recover,sync,list,show}.ts`, `src/agent-intent/{relay,completion-auth,send-intent,evm,profile-identity,service-errors,profile-format,token-lookup}.ts`, `src/key-ring/{agent-intent-keychain,keychain-entry,constants}.ts`, `src/session/session-store.ts`, `src/output.ts`, `package.json`, `README.md`, `CHANGELOG.md`, `vendor/README.md`, `vendor/ledgerhq-agent-intent-sdk-0.0.0.tgz`, `npm/` (darwin-arm64, linux-arm64, linux-x64, windows-x64)
- Raw file base: https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/
- PRs: https://github.com/LedgerHQ/ledger-live/pull/22400 , /22461 , /22476 , /22688 , /22976 , /22980 , /22992 , /23033 , /23037 , /23045 , /23084 , /23105 , /23174 ; issue /21908
- GitHub search: https://api.github.com/search/issues?q=repo:LedgerHQ/ledger-live+agent-intent (and `created:>2026-10-05`)
- Skill: https://raw.githubusercontent.com/LedgerHQ/agent-skills/main/skills/wallet-cli/wallet-cli-usage/SKILL.md (and `references/business-logic.md`)
- npm: https://registry.npmjs.org/@ledgerhq/wallet-cli , https://registry.npmjs.org/@napi-rs/keyring , https://unpkg.com/@bunli/utils@0.6.0/dist/index.js
- Reachability probes: https://global.api.prd.ledger.com/keycloak/realms/agent-intent-customers/.well-known/openid-configuration (200), https://global.api.prd.ledger.com/agent-intent/v1/intents (401), https://global.api.stg.ledger-test.com/agent-intent/v1/intents (403), https://global.api.stg.ledger-test.com/keycloak/realms/agent-intent-customers/.well-known/openid-configuration (403), https://agent-intent.ledger.com/ (NXDOMAIN), https://trustchain.api.live.ledger.com/ (404 root)
- Precursor: https://github.com/brackets-fistfulayen/ledger-agent-intents (README, repo metadata; owner handle resolves to "ian c rogers")
- Private (404 to us, confirming they are not public): https://github.com/LedgerHQ/agent-intent-sdk , https://github.com/LedgerHQ/agent-intent-frontend , https://github.com/LedgerHQ/agent-intent-service
- Related notes in this repo: `research/prior-art-hackathon-projects.md`, `research/jury-and-ledger-strategy.md`, `research/ledger-cli-agent-stack.md`, `research/dmk-ts-signer.md`, `research/dmk-skills.md`
