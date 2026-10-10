# Key Ring: recovery, rotation and headless enrolment, resolved from primary sources

> **Correction (2026-10-10, source audit).** Ledger Sync `GetSeedId` (m/99'/99') also returns an app attestation signed by a production-only key whose public key is in `app-ledger-sync/src/crypto_data.h`, verifiable offline. See `source-audit.md` §4.5, §4.8 and §5.

Researched 2026-10-10 for the N3XT hackathon (deadline 2026-10-13 23:59 CEST). Web only; no hardware touched, nothing installed.
Tags: **VERIFIED** = read in a primary source (whitepaper PDF, ledger-live source/docs, app-ledger-sync firmware source, Harness/rewall source). **INFERRED** = my reading across sources.

This note settles three contradictions between `HACKATHON.md`, `research/key-ring.md`, `research/ledger-cli-agent-stack.md`, `research/walkthrough-video.md`, `research/dmk-skills.md`, `research/hardware-security-fido-pgp-ssh.md` and `research/prior-art-hackathon-projects.md`.

## TL;DR

| Question | Answer | Status |
| --- | --- | --- |
| (a) Are ring keys "derived from your Ledger seed"? | **No.** The ring root is a random 64-byte xpriv generated on the device. What *is* seed-derived is the device's LKRP identity key at BIP32 path **`m/99'/99'`** (`SEED_ID_PATH = {0x80000063, 0x80000063}` in app-ledger-sync). The root is ECDH-encrypted to that identity and stored in the `Seed` block on Ledger's trustchain backend. Recovery = same seed **and** backend still holding the tree. | VERIFIED (whitepaper + firmware + SDK) |
| (a') Does the 1-year Ledger Sync inactivity purge kill ring data? | Ledger's FAQ says inactive-for-one-year Ledger Sync "and its associated data will be automatically deleted". Whether that deletes the trustchain **root** (which the ring shares) or only Cloud Sync data, and whether ring traffic counts as activity, is **not documented anywhere**. Treat as a real, unquantified risk. | FAQ sentence VERIFIED via search snippet (page is JS-rendered); consequence INFERRED |
| (b) Does removing a Ledger Sync member in Ledger Wallet rotate the ring key? | **No, per the code.** `removeMember` rotates only `this.context.applicationId`; Ledger Wallet's SDK is built with `applicationId = 16`, the ring lives at `17`. Ledger Wallet's "Manage instances" lists only app-16 members; app-17 members are invisible there. The docs sentence "Removing a Ledger Sync member rotates the Key Ring encryption key" is wrong or at best ambiguous. The ring rotates only when an **app-17** member is removed, and the only shipped UI that can do that is Ledger's dev tool `live.ledger.tools/trustchain`. | VERIFIED code; "docs are wrong" INFERRED (no runtime test) |
| (c) Can a USB-less host join the ring? | **Yes, three ways, all proven by others.** (1) Harness: host runs `getOrCreateTrustchain(appId 17)` with the device reached through a browser APDU relay (WebHID + HTTP long-poll); host key never leaves the host; production backend; real Flex/Gen5. (2) Harness `verified.md`: SDK `addMember` from an already-enrolled software member added a VM with no device (members 1 to 2, `m/0'/17'/0'`). (3) rewall: generate the member keypair next to the device, enrol via the DMK trusted-app kit `authenticate(...)`, ship the private key to the agent sealed on-chain; agent then calls `authenticate({keyPair, trustchainId})` with no device. `wallet-cli` exposes none of these. | VERIFIED (source) |

**One sentence for the stage:**

> "The Ledger decides who gets into the ring and who gets thrown out; it does not do the encryption and does not keep the key: the ring key is a random secret the device generated once, locked to your seed and parked on Ledger's server, so your 24 words bring it back only while that server still has it, and any enrolled machine with its member key, its password and a network connection decrypts without the device."

Shorter variant: "Your Ledger guards *membership*, not *ciphertext*: it admits and evicts machines; it never sees the data, and recovery needs your seed plus Ledger's server."

## 1. Recovery: what the seed does and does not give you

### 1.1 The root is random (VERIFIED, whitepaper)

Whitepaper, "Design goal": *"secure devices never share data derived from the user 24 words seed, LKRP encryption keys are always randomly generated and encrypted inside the LKRP object."* Earlier: *"LKRP never shares private keys kept by the secure device storage i.e derived from the user 24 words seed phrase ... Instead it must share randomly generated encryption keys to other applications."*

"Tree initialization": *"The secure device randomly generates a random extended private key ... The Seed command is used as a backup for the secure device to retrieve the private key. Since we don't want to share internal private keys, we create a random private key, create a backup and read the backup when needed."*

Command table: `Seed` = *"Indicates the generation of a random root encryption key. The content of this command is encrypted for the issuer of the command."*

So the root never persists on the device; the device reads it back from the `Seed` block every time it needs to derive or publish.

### 1.2 What *is* seed-derived: the device identity at `m/99'/99'` (VERIFIED, firmware)

`LedgerHQ/app-ledger-sync`, `src/app_main.c`:

```c
const uint32_t SEED_ID_PATH[] = {0x80000063, 0x80000063};   // m/99'/99'
const size_t SEED_ID_PATH_LEN = 2;
```

`src/crypto.c`:
- `crypto_sign_block()` signs block hashes with `bip32_derive_with_seed_ecdsa_sign_hash_256(HDW_NORMAL, CX_CURVE_256K1, SEED_ID_PATH, ...)`.
- `crypto_ecdh_decrypt()` does `crypto_derive_private_key(&private_key, chain_code, SEED_ID_PATH, SEED_ID_PATH_LEN)` then ECDH with the sender's ephemeral key, then AES decrypt. This is how the device opens the `Seed`/`Derive`/`PublishKey` payloads addressed to itself.
- `GET_SEED_ID` (INS 0x05) returns this public key; the SDK uses it to sign the backend's auth challenge (`getSeedId(challenge)` in `02-trustchain-sdk.md`).

Consequence (INFERRED, tight): a replacement device restored from the same 24 words derives the same `m/99'/99'` key, so it (1) authenticates to the backend as the same "seed id", (2) is handed the same trustchain by `api.getTrustchains`, and (3) can decrypt the `Seed` block and re-derive `m/0'/17'/N'`. That is the entire mechanism behind the docs' "creates or recovers the Key Ring from your Ledger seed". The SDK even distinguishes `TrustchainAlreadyInitialized` from `TrustchainAlreadyInitializedWithOtherSeed`.

### 1.3 Where the only copy of the root lives (VERIFIED, SDK)

`sdk.ts` `getOrCreateTrustchain`: creates `StreamTree.createNewTree(hw, ...)` on the device, then `api.postSeed(jwt, hex(commandStream))`. Nothing is written locally except, in `wallet-cli` `init.ts`, `session.setTrustchain({rootId, applicationPath})` and the member private key into the OS keychain. Every `ring encrypt/decrypt` calls `sdk.restoreTrustchain`, which runs `fetchTrustchainAndResolve`, which runs `api.getTrustchain(jwt, rootId)`, then `SoftwareDevice.readKey` on the freshly downloaded tree (`load-key-ring.ts`). There is **no local cache of the stream tree**.

Therefore (INFERRED):
- Lose the member key or password: recover with seed + device (`ring init` on a new machine) **as long as the backend still has the root**.
- Backend deletes the root (`destroyTrustchain` = `DELETE /v1/trustchain/{rootId}`, triggered by `ring destroy` when the ring is the last open application, by Ledger Wallet "Delete Sync" when Sync is the last open application, or by any server-side purge): **every ring ciphertext is unrecoverable forever, seed or no seed**. The root exists nowhere else.
- A member who still holds its private key *and* a saved copy of the serialized tree could decrypt offline (`StreamTree.deserialize` + `SoftwareDevice.readKey` are pure functions of those two inputs). No shipped tool saves the tree. This is a hackathon-sized gap (see section 5).

### 1.4 The inactivity purge (partially VERIFIED)

`https://support.ledger.com/article/Ledger-Sync-FAQs` is JS-rendered; `curl`, `WebFetch` and a reader proxy all returned no article body. Two independent web-search snippets of that page returned the sentence: *"if you activate Ledger Sync but then remain inactive for one year, the Ledger Sync and its associated data will be automatically deleted"*, and *"If you choose to delete Ledger Sync, the associated data will be removed instantaneously."* I could not read the surrounding paragraph.

Unknowns (nothing in ledger-live docs, SDK, PRs, whitepaper or blog addresses them):
1. Does "Ledger Sync and its associated data" mean the **trustchain root** (which would take the ring with it) or only the Cloud Sync payload / app-16 stream?
2. Does an app-17 member authenticating to `trustchain.api.live.ledger.com` count as "activity"? Ring encrypt/decrypt does `GET /v1/challenge` + `POST /v1/authenticate` + `GET trustchain` every call, so plausibly yes, but unverified.
3. Is there any notice before deletion?

Ask on the hackathon Discord. Until answered, the honest line is "Ledger's server may delete an inactive ring after a year; we have no spec for what 'inactive' means for the ring."

### 1.5 Verdict on the four notes

- `HACKATHON.md` ("keys derived from your Ledger seed"), `research/walkthrough-video.md` ("recoverable from the seed"), `research/dmk-skills.md` ("seed-derived keys"), `research/hardware-security-fido-pgp-ssh.md` ("recovers from seed", "seed-recoverable secrets") are **marketing shorthand**. Correct phrasing: *seed-recoverable identity; server-held random key*.
- `research/key-ring.md` section 3.3 is correct and is now backed by firmware source (the `m/99'/99'` path was unknown there). Its section 7 inactivity INFERENCE stands as an open risk.
- Contrast worth a slide: the **Security Key (FIDO) app** really is seed-derived and survives backend loss (`hardware-security-fido-pgp-ssh.md` section 2.4). The ring is the opposite trade: convenience (no device per operation) paid for with a server dependency.

## 2. Rotation: what actually rotates when

### 2.1 The SDK, verbatim (VERIFIED, `sdk.ts` 1.0.0)

```ts
async removeMember(deviceId, trustchain, memberCredentials, member, callbacks) {
  ...
  const applicationId = this.context.applicationId;
  ...
  const newPath = streamTree.getApplicationRootPath(applicationId, 1);
  // We close the current trustchain with the hardware wallet in order to get a user confirmation of the action
  const sendCloseStreamToAPI = await this.closeStream(streamTree, applicationRootPath, trustchainId, withJwt, withHw);
  // derive a new branch of the tree on the new path
  streamTree = await this.pushMember(streamTree, newPath, trustchainId, withJwt, withHw, { id: memberCredentials.pubkey, name: this.context.name, permissions: Permissions.OWNER });
  // add the remaining members
  for (const m of withoutMemberOrMe) {
    streamTree = await this.pushMember(streamTree, newPath, trustchainId, withJwt, withSw, m);
  }
  ...
  await sendCloseStreamToAPI();
```

`getApplicationRootPath(applicationId, increment)` (`StreamTree.ts`) returns `m/0'/{applicationId}'/{highest existing index + increment}'`. So `removeMember` closes `m/0'/X'/N'` and opens `m/0'/X'/N+1'` **for X = the SDK instance's own applicationId only**. Nothing touches any other application's branch.

### 2.2 Who runs which applicationId (VERIFIED)

| Caller | `applicationId` | Source |
| --- | --- | --- |
| Ledger Wallet desktop/mobile (`useTrustchainSdk.ts`) | `16` | `const applicationId = 16;` |
| `wallet-cli ring` (`lkrp-sdk.ts`, `LKRP_APPLICATION_ID`) | `17` | `docs/ledger-sync/01-hardware-lkrp.md`: "17 = wallet-cli" |
| `wallet-cli agent-intent` | agent trustchain `18`, granted access to `16` | SKILL.md |
| Ledger dev tool `apps/web-tools/src/trustchain` (live.ledger.tools/trustchain, HTTP 200) | selectable: 16 / 17 / 18 | `AppSetApplicationId.tsx` |

Ledger Wallet's remove flow (`apps/ledger-live-desktop/.../hooks/useRemoveMember.ts`) calls `sdk.removeMember(deviceId, trustchain, memberCredentials, member, ...)` on that app-16 SDK. Its member list comes from `sdk.getMembers`, which resolves `fetchTrustchainAndResolve(jwt, rootId, this.context.applicationId)` and returns `resolved.getMembersData()` of the **app-16 stream**.

### 2.3 Resolution (code VERIFIED, runtime behaviour INFERRED)

1. Removing a Ledger Sync instance in Ledger Wallet closes `m/0'/16'/N'` and opens `m/0'/16'/N+1'`. The ring branch `m/0'/17'/0'` is untouched; `wallet-cli` `restoreTrustchain` still resolves `getApplicationRootPath(17)` = `m/0'/17'/0'`, same `walletSyncEncryptionKey`, same HKDF domain keys. **Ring ciphertext survives.** `restoreTrustchain` passes `ignorePermissionsChecks = true`, so even a changed JWT permission map would not block it.
2. Ring (app-17) members never appear in Ledger Wallet's "Manage instances", so a user **cannot** evict a stolen laptop's ring membership from Ledger Wallet. `wallet-cli` has no `ring members` / `ring remove-member` either (commands: `init|encrypt|decrypt|keys|destroy`). The only shipped path to rotate the ring is the developer tool at `live.ledger.tools/trustchain` with applicationId set to 17 (`AppMemberRow.tsx` calls `sdk.removeMember(deviceId, ...)`, device confirmation required), or custom SDK code.
3. The docs sentence in `developers.ledger.com/docs/ai-tools/ledger-cli.md` ("Removing a Ledger Sync member rotates the Key Ring encryption key") and the in-repo SKILL.md ("the LKRP protocol rotates when a ring member is removed") describe the *protocol* behaviour correctly only if "member" means an app-17 member. The `ledger-cli-agent-stack.md` and `walkthrough-video.md` notes marked this VERIFIED because the docs say it; the docs conflate the two applications. **Downgrade to: VERIFIED that removing a ring member rotates the ring; INFERRED (from code) that removing a Ledger Sync instance does not.**
4. The second rotation-like path is `ring destroy` then `ring init`: `destroyApplication` closes `m/0'/17'/N'` (if Sync is still active) and the next `getOrCreateTrustchain` sees `resolved.isClosed()` and reopens at `m/0'/17'/N+1'` (new child key). Old ciphertext is then undecryptable through any tool, though the closed stream's key still exists on the backend and could be re-derived by the device (no tooling). INFERRED from `sdk.ts` + `destroy.ts`.
5. Cross-app destruction: before ledger-live PR #18568 (merged 2026-06-29) both apps deactivated via `DELETE /trustchain/{rootId}`; "Delete Sync" wiped the ring and vice versa. Now `destroyApplication` closes only its own stream unless it is the last open application. Whether the Ledger Wallet build on a given laptop has this fix depends on its release; INFERRED that October 2026 builds do. `wallet-cli` 2.9.0 `ring destroy` uses `destroyApplication` (VERIFIED, `destroy.ts` + `sdk.ts`).
6. The `getOrCreateTrustchain`-after-close bug Harness hit (`SW_STREAM_CLOSED 0xb00c`, "application permanently unusable") is fixed in the same PR; `sdk.ts` 1.0.0 has `if (resolved?.isClosed()) { path = getApplicationRootPath(applicationId, 1) ... }`. VERIFIED.

Demo hazards that remain real: if your demo removes a *ring* member (via web-tools or your own code), every `--key` rotates at once (single root, HKDF labels); re-encrypt first. If you `ring destroy` on the only machine while Ledger Sync is off, the whole root is deleted and nothing comes back.

## 3. Headless enrolment: how Harness and rewall did it

### 3.1 Harness (1st, ETHOnline 2026 "AI Agents x Ledger"), VERIFIED from source

Files: `web/lib/ring-server.ts`, `web/lib/relay.ts`, `web/lib/relay-client.ts`, `web/app/api/enrolments/[id]/ring/route.ts`, `web/lib/wallet-cli-state.ts`, `tools/harness-ring`, `docs/verified.md`, `FEEDBACK.md`.

Mechanism (production backend, real Flex / Nano Gen5, versions `@ledgerhq/wallet-cli@2.1.0`, `ledger-key-ring-protocol@0.15.2`, `hw-ledger-key-ring-protocol@0.10.7`, DMK 1.9.0):

```ts
// web/lib/ring-server.ts
export const APPLICATION_ID = 17;
const API = "https://trustchain.api.live.ledger.com";
...
const transport = new RelayTransport(relaySessionId);
const withDevice = () => (job) => job(transport);
const sdk = getSdk(false, { applicationId: APPLICATION_ID, name: memberName, apiBaseUrl: API }, withDevice);
const result = await sdk.getOrCreateTrustchain("relay", credentials);
```

- The host (a VPS) generates and keeps its own secp256k1 member key (`web/lib/enrolment.ts`, `secp256k1.utils.randomSecretKey()`), one per tenant, reused so repeated onboarding does not accumulate members ("A ring member cannot be removed without rotating the ring").
- `RelayTransport.send/exchange` queues an APDU; the browser long-polls `GET /api/relay/{id}`, forwards the APDU to the Ledger via `@ledgerhq/hw-transport-webhid`, and `POST`s the reply. Comment in source: "The broker is the caller, so `getOrCreateTrustchain` admits it directly: there is no separate `addMember`, and the broker's key never leaves this host."
- One device confirmation ("Connect to Ledger Sync?" / "Turn on sync..." screens) admits the host as OWNER on `m/0'/17'/0'`.
- `writeWalletCliState()` then forges `wallet-cli`'s own state so the unmodified CLI works on the VM: `session.yaml` as single-line flow YAML `{accounts: [],trustchain: {rootId: ..., applicationPath: "m/0'/17'/0'"},domains: [],passwordSalt: <hex>}` and a keychain entry `"ENC:" + hex(iv||aes256gcm(privkey_hex)||tag) + "\n" + pubkey` wrapped with PBKDF2-SHA256 600 000 rounds; account name `member-private-key-` + first 16 hex of `sha256(stateDir)`.
- On headless Linux `keyring-rs` picks the kernel keyring (not persistent across reboot); `tools/harness-ring` wraps each `wallet-cli ring encrypt|decrypt` in `keyctl session -`, injects the key with `keyctl padd user "keyring:${account}@ledger-wallet-cli" @s`, and uses a per-tenant `XDG_STATE_HOME`.
- `docs/verified.md` additionally records: "**USB-less enrolment works, proven end to end (2026-09-05).** `ring init` on a MacBook with a Nano Gen5 attached; `tools/lkrp-add-member.mjs` run on that Mac added this Oracle Cloud aarch64 VM as member #2 (`members: 1 -> 2`) with no device involved; the VM then decrypted a ciphertext produced on the Mac. Only a public key crossed the wire. ... `applicationPath` `m/0'/17'/0'`." That script is not in the current tree, but the claim is theirs and specific. This upgrades `key-ring.md`'s "plausible, untested" for SDK `addMember` on app 17 to **third-party reported working on the production backend**.
- They did **not** use a `SoftwareDevice` for the shipped relay flow; the device signs the `AddMember`/`PublishKey` blocks through the relay. `prior-art-hackathon-projects.md`'s description ("host generates keypair, Ledger admits it to the ring with one tap") is accurate.

### 3.2 rewall (ETHOnline 2026), VERIFIED from source

Files: `ledger/README.md`, `ledger/DX.md`, `ledger/src/lkrp.ts`, `ledger/src/enroll.ts`, `ledger/src/agent.ts`.

- Uses the **DMK trusted-app kit**, not the ledger-live SDK: `@ledgerhq/device-trusted-app-kit-ledger-keyring-protocol@0.5.0` with `LedgerKeyringProtocolBuilder({ dmk, applicationId: 17, env: LKRPEnv.STAGING })`, device = Speculos running self-built `app-ledger-sync` 1.2.2 (`speculosTransportFactory`, `DeviceModelId.NANO_SP`).
- Owner side (`enroll.ts`): `NobleKeyPair.generate(Curve.K256)` on the machine with the device, then `lkrp.authenticate({ keyPair: member, clientName: AGENT, permissions: Permissions.OWNER, sessionId })`; the device approves, the member is enrolled. The **private key** is then sealed as a Rewall/ENS secret for the agent's name.
- Agent side (`agent.ts`): `withoutDevice()` builds a DMK with no transport; `lkrp.authenticate({ keyPair, clientName, permissions, trustchainId })` with no session; then `encryptData/decryptData` with `output.encryptionKey`. Type that makes this legal: `{ keyPair; clientName; permissions } & ({ trustchainId; sessionId? } | { trustchainId?; sessionId })`.
- Their DX findings (all reproduced in `DX.md`): only `Permissions.OWNER` enrols (`CAN_ENCRYPT` fails with "Security issue with bad state"); the kit has **no add-by-public-key use case** ("the keypair must exist on the machine holding the device at the moment of approval"), although `app-ledger-sync`'s Python tests do `stream.edit().add_member("Bob", bob.get_public_key(), 0xFFFFFFFF, True)`; production backend rejects self-built apps with `401 Attestation is for an unknown application`, so Speculos demos must use STAGING; `WALLET_CLI_MOCK=1` mocks the backend, not the device; `wallet-cli` ignores all `SPECULOS_*` env vars (bundled transport is WebUSB only); `applicationId` is undocumented (they found 17 in the wallet-cli bundle).
- Note the trust difference: rewall ships the member **private key** to the agent (sealed on-chain). Harness never moves a private key. The ledger-live SDK's `addMember(trustchain, creds, member)` (software-signed, takes a `member.id` pubkey) is the add-by-public-key primitive rewall wished for; it lives in `@ledgerhq/ledger-key-ring-protocol`, not in the DMK kit they used.

### 3.3 What `wallet-cli` itself offers (VERIFIED)

`ring init` is the only enrolment verb and hard-requires a USB device via `withLkrpDeviceSession` (`init.ts`). Agent Intent (`agent-intent enroll`, app 18) proves Ledger already runs a WebSocket "Trustchain relay" for device-elsewhere approval, but it is wired to app 18/16, not to the ring.

### 3.4 Resolution

`key-ring.md`'s "no documented way to enrol a USB-less host" stays true for **Ledger's documentation and CLI**. `prior-art-hackathon-projects.md` is also right: two teams shipped it, and Harness proved both the relay path and the `addMember` path on the production backend with real devices. The gap is tooling and docs, not protocol or backend permissions.

## 4. Corrections to apply to sibling notes

| Note | Claim | Correction |
| --- | --- | --- |
| `HACKATHON.md` (brief wording) | "keys derived from your Ledger seed" | Leave the brief verbatim (it is Ledger's text); annotate in our pitch: identity is seed-derived (`m/99'/99'`), key is random and server-held. |
| `walkthrough-video.md` section 3, `dmk-skills.md` table, `hardware-security-fido-pgp-ssh.md` sections 2.4/5 | "recoverable from seed", "seed-derived AES keys" | Replace with "recoverable with the same seed while Ledger's trustchain backend still stores the root; key itself is random". |
| `ledger-cli-agent-stack.md` line 130, `walkthrough-video.md` lines 138/189, `prior-art-hackathon-projects.md` line 30 | VERIFIED: removing a Ledger Sync member rotates the ring key | Downgrade: docs say so, code says removal rotates only the caller's applicationId (16 for Ledger Wallet). Ring rotates only on app-17 member removal, which no shipped UI except live.ledger.tools/trustchain performs. |
| `key-ring.md` section 3.3 | device identity key path unknown ("gap") | `m/99'/99'` from `app-ledger-sync/src/app_main.c`. |
| `key-ring.md` TL;DR / section 9 | SDK `addMember` with SoftwareDevice "plausible, untested" | Harness `docs/verified.md` reports it working on prod, 2026-09-05, app 17. Still not reproduced by us. |
| `key-ring.md` section 7 | "Where can a user see/remove ring members? ... unknown" | Not in Ledger Wallet (app-16 list only). Yes in `live.ledger.tools/trustchain` (dev tool, applicationId selector includes 17). |

## 5. Hackathon angles this opens (INFERRED)

1. **`ring` lifecycle commands Ledger forgot**: `ring members` (`sdk.getMembers`), `ring add-member <pubkey> --name` (`sdk.addMember`, software-signed, no device), `ring remove-member` (`sdk.removeMember`, device tap), `ring rotate` (remove-and-readd with automatic re-encrypt of every file listed under `ring keys` domains). Directly answers rewall's "the one thing to change" and the brief's "Bring Key Ring to environments without USB". Risk: `addMember` on prod for app 17 is third-party-reported, not Ledger-documented; test on day 1 with our two devices.
2. **`ring backup` / offline recovery**: save the serialized trustchain (`api.getTrustchain` output) encrypted under the ring itself or a passphrase; `ring decrypt --offline <blob>` then needs no backend. Closes the backend-dependency hole from section 1.3 and gives the stage a crisp "what if Ledger's server is gone" answer. Pure software, no device needed after init.
3. **Browser-relay enrolment on Windows**: Harness's relay means the enrolling machine never needs libusb/WebUSB; Chrome WebHID on Windows 11 with the Flex over USB-C handles the device, and the agent host (VPS, WSL, or the same laptop's headless service) runs the SDK. The Flex's Bluetooth could be driven via DMK's Web Bluetooth transport in the same browser page (untested; Chrome on Windows supports Web Bluetooth).
4. **Honest trust-model slide**: "Ledger guards membership, not ciphertext". Jury includes Ledger's VP Product; stating the limits precisely (random root, `m/99'/99'`, server-held, member key + password decrypts without device) is a differentiator against the ~20 ETHOnline projects that said "hardware-backed secrets".
5. **Ring + Signer split for our Idea 1 (voice agent)**: ring holds LLM/STT/RPC keys (autonomous side); the Flex clear-signs transactions (approved side). Face scan is theatre unless it gates something the device does not; drop or reframe it as liveness for the voice channel.
6. Idea 2 (NFC ledger-to-ledger) is unrelated to the ring.

## 6. Constraints to respect

- Windows 11 host: `wallet-cli` ships `@ledgerhq/wallet-cli-windows-x64` 2.9.0 but docs say "WSL recommended"; `ring init` needs WebUSB over libusb; the relay approach sidesteps this. No `/dev/tty` on Windows, so always set `WALLET_PASS` for piped calls.
- Both devices (Nano S Plus, Flex) run the Ledger Sync app; production backend accepts only Ledger-signed app attestation, so real devices are required for prod; Speculos only works against STAGING (`LKRPEnv.STAGING`, host visible in the bundle).
- Only `Permissions.OWNER` enrols (rewall); any member we add can add others and read everything.
- `@ledgerhq/ledger-key-ring-protocol` 1.0.0: ESM build has extensionless imports (use CJS via `createRequire`); older versions pulled an unpublished `@ledgerhq/live-dmk-speculos` (Harness needed an `overrides` stub). Check 1.0.0 installs cleanly before committing to it.
- Headless Linux keychain is the kernel keyring (non-persistent) unless a Secret Service runs; Harness's `keyctl session -` wrapper is the known workaround. On Windows the backend is Credential Manager (per-user, persistent).
- Any ring member removal rotates every `--key` at once; `ring destroy` on the last open application deletes the root for all applications.
- 3 days: do not attempt firmware or backend changes; everything above is client-side TypeScript against existing APIs.

## 7. Open questions for Ledger (Discord)

1. Does the one-year Ledger Sync inactivity deletion remove the trustchain **root** (`DELETE /trustchain/{rootId}`) or only Cloud Sync data? Does app-17 authentication count as activity? Any warning?
2. Is `addMember` (software-signed) on the app-17 stream an intended, supported use on production, or tolerated? Any plan for `ring add-member`/`ring members`?
3. Is the docs sentence "Removing a Ledger Sync member rotates the Key Ring encryption key" intended to mean app-17 members only? Where should users manage ring members, given Ledger Wallet shows only app-16 instances?
4. Why do non-OWNER permissions fail at enrolment ("Security issue with bad state")? Is scoped permission on the roadmap?
5. Is there any supported offline decryption path (device reads the `Seed` backup) for an air-gapped host, or an export of the trustchain for backup?
6. Minimum Ledger Sync app version for `ring init`; exact device screen text at enrolment ("Connect to Ledger Sync?" / "Turn on sync for Ledger Wallet?" per rewall on Speculos 1.2.2).
7. Is `live.ledger.tools/trustchain` a supported way for end users to remove ring members, or dev-only?

## Sources

Primary, read in full or in the quoted sections:
- Whitepaper PDF (text extracted with pdftotext): https://raw.githubusercontent.com/LedgerHQ/ledger-key-ring-protocol-whitepaper/main/Ledger%20Key%20Ring%20Protocol%20Technical%20White%20Paper.pdf
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/docs/ledger-sync/01-hardware-lkrp.md
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/docs/ledger-sync/02-trustchain-sdk.md
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/docs/ledger-sync/scenarios.md
- https://unpkg.com/@ledgerhq/ledger-key-ring-protocol@1.0.0/src/sdk.ts
- https://unpkg.com/@ledgerhq/hw-ledger-key-ring-protocol/src/StreamTree.ts
- https://unpkg.com/@ledgerhq/hw-ledger-key-ring-protocol/src/Device.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/commands/ring/destroy.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/commands/ring/init.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/key-ring/lkrp-sdk.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/key-ring/load-key-ring.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/.agents/skills/ledger-wallet-cli/SKILL.md
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/ledger-live-desktop/src/mvvm/features/WalletSync/hooks/useRemoveMember.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/ledger-live-desktop/src/mvvm/features/WalletSync/hooks/useTrustchainSdk.ts
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/web-tools/src/trustchain/components/AppSetApplicationId.tsx
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/web-tools/src/trustchain/components/AppMemberRow.tsx
- https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/web-tools/README.md (live.ledger.tools; /trustchain returns HTTP 200)
- https://github.com/LedgerHQ/ledger-live/pull/18568 (merged 2026-06-29, per-application close)
- https://developers.ledger.com/docs/ai-tools/ledger-cli.md
- app-ledger-sync firmware: https://raw.githubusercontent.com/LedgerHQ/app-ledger-sync/develop/src/app_main.c , /src/crypto.c , /src/constants.h , /doc/COMMANDS.md
- Harness: https://github.com/LeoFranklin015/Harness (`web/lib/ring-server.ts`, `web/lib/relay.ts`, `web/lib/relay-client.ts`, `web/lib/enrolment.ts`, `web/lib/wallet-cli-state.ts`, `web/app/api/enrolments/[id]/ring/route.ts`, `tools/harness-ring`, `docs/key-ring.md`, `docs/verified.md`, `docs/questions.md`, `ledger.md`, `FEEDBACK.md`, `ARCHITECTURE.md`)
- rewall: https://github.com/oynozan/rewall (`ledger/README.md`, `ledger/DX.md`, `ledger/src/lkrp.ts`, `ledger/src/enroll.ts`, `ledger/src/agent.ts`, `ledger/package.json`)
- https://ethglobal.com/showcase/harness-vvvaq ; https://ethglobal.com/showcase/rewall-32xx8

Secondary / partial:
- https://support.ledger.com/article/Ledger-Sync-FAQs (JS-rendered; body not retrievable by curl/WebFetch/reader proxy; the inactivity and delete sentences come from two web-search snippets of this page)
- https://www.ledger.com/blog-ledger-sync-synchronize-your-crypto-accounts-effortless-private-and-secure (marketing: "create an infinite number of encryption keys with your secret recovery phrase"; contradicts the whitepaper's wording, consistent with the mechanism in section 1.2)
