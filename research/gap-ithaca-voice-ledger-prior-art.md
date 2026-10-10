# Gap note: voice + hardware-signer prior art (ITHACA, Orchestra, and everything else I could find)

Research note for the N3XT @ OP3N hackathon (brief: `../HACKATHON.md`). Compiled 2026-10-10 from the ETHGlobal showcase, GitHub source (read via `gh api` raw-content calls, nothing installed, no hardware touched), Ledger docs and press. Resolves the contradiction between `voice-face-agent-feasibility.md` §5 ("voice + Ledger is open ground") and `prior-art-hackathon-projects.md` (ITHACA exists and placed).

Legend: **VERIFIED** = read in a primary source (showcase page, repo source file, README, Ledger docs). **INFERRED** = derived; treat as a lead.

---

## 0. Verdict in six lines

1. **The contradiction resolves in favour of `prior-art-hackathon-projects.md`.** ITHACA (ETHOnline 2026, Sep 4–16) is a real, deployed, voice-run agent whose Ledger Flex signs via DMK, and it took **3rd place in "AI Agents x Ledger"** ($500 tier). `voice-face-agent-feasibility.md` §5 missed it because its corpus search predated/skipped ETHOnline 2026. **VERIFIED.**
2. **Orchestra is NOT voice.** "Talk to your crypto" is a metaphor; the only input is `<input type="text">`. No mic, no SpeechRecognition, no STT vendor anywhere in the repo. **VERIFIED** (frontend `SearchBar.jsx`, README "User types").
3. **ITHACA's Ledger primitive is a one-time EIP-712 standing mandate, not per-transaction signing.** The device never sees the spoken command. It shows five raw struct fields (`investCap`, `protectCap`, `safeHaven`, `expiry`, `nonce`) in the Ethereum app's unfiltered EIP-712 path, with blind signing enabled. **VERIFIED code; INFERRED exact rendering.**
4. **ITHACA's "Face ID" is a WebAuthn platform-authenticator presence check whose result is discarded, skipped when no biometric hardware exists, plus a purely cosmetic 2.3-second "Scanning your face…" animation.** No camera, no face model, no liveness, no speaker identification. The voice channel itself is unauthenticated. **VERIFIED.**
5. **ITHACA's Key Ring broker is not wired into the deployed voice app.** The Vercel app signs agent actions with `AGENT_PRIVATE_KEY` from env; the broker (`ledger-broker/`) is a separate Node process consumed only by the optional daemon. **VERIFIED.**
6. **Nobody has (a) put the spoken intent itself on the Secure Screen, (b) made identity (face/voice/FIDO2) select *which* policy gets signed, (c) done voice + Ledger for anything other than DeFi yield/swaps, or (d) demoed on a Nano S Plus.** Those are the four open doors. Section 6 lists exactly what to do differently.

---

## 1. ITHACA teardown

### 1.1 Identity card

| | |
|---|---|
| Showcase | https://ethglobal.com/showcase/ithaca-i7yxs — **VERIFIED** |
| Tagline | "You talk, it invests. A voice-run AI that grows your USDC on its own and can't be robbed." |
| Hackathon | ETHOnline 2026 (online, Sep 4–16 2026; submissions closed Sep 13) — **VERIFIED** (https://developers.ledger.com/ethonline) |
| Prize | Showcase "Winner of: Ledger - AI Agents x Ledger 3rd place". Track prizes were 1st $2,000 / 2nd $1,000 / 3rd $500. 1st = **Harness** (per-agent container + ENS + Ledger-set daily limit). 2nd not found on any Ledger-flagged page. — **VERIFIED** (showcase pages; https://ethglobal.com/events/ethonline2026/prizes/ledger) |
| Repo | https://github.com/chrsnikhil/ithaca — MIT, 0 stars, **14 commits, all by one author, 2026-09-10 → 2026-09-12** — **VERIFIED** (`gh api repos/.../commits`) |
| Author | GitHub `chrsnikhil` = "Chris Nikhil", location Chennai, X `@Knightinga86439`. Showcase lists no team; the repo has a single committer, so this reads as a **solo build**. — **VERIFIED profile; INFERRED solo** |
| Live app | https://guardian-rho-two.vercel.app (desktop Chrome/Edge only) |
| Demo video | Present on the showcase page as a Mux stream (`stream.mux.com/S02ErOfZRpkcuV00x6IwLdOMXI4pcS01wVG3zib025w1kfU`, uploaded as `ETHONLINE FINAL DEMO.mp4`, 1080p, **no caption track**). I could not watch it; content below comes from the 11-scene demo deck that the README says the video was cut from. — **VERIFIED existence; content INFERRED from deck** |
| Internal name | Everything is prefixed `guardian-`; "ITHACA" is the product name (README note; deck comment "R20: product renamed GUARDIAN → ITHACA"). |
| Also submitted | `graphscout/` to The Graph track ("Best AI Tooling or AI Use Case"); `ledger-broker/SUBMISSION.md` targets "AI Agents x Ledger ($3,500)". Both SUBMISSION files still say "(add on push)" for repo/video. — **VERIFIED** |

### 1.2 Voice stack (what actually does STT/TTS)

**Gemini Live does everything speech-related. ElevenLabs is a UI component library here, not a voice vendor.** **VERIFIED.**

- `guardian/package.json`: `@google/genai ^2.21.0`, `@elevenlabs/client ^1.24.0`, `@elevenlabs/elevenlabs-js ^2.66.0`, `@elevenlabs/react ^1.15.1`, `@ledgerhq/device-management-kit ^1.9.0`, `@ledgerhq/device-signer-kit-ethereum ^1.18.0`, `@ledgerhq/device-transport-kit-web-ble ^1.3.2`, `@ledgerhq/device-transport-kit-web-hid ^1.2.4`, `ethers ^6.17`, Next 16.3.4, React 19.2.8.
- `guardian/app/api/gemini-token/route.ts` mints a **single-use ephemeral token** (`ai.authTokens.create`, `apiVersion: "v1alpha"`, 30-min expiry, 2-min new-session window) with the whole session config locked server-side:

```ts
const MODEL = process.env.GEMINI_LIVE_MODEL || "gemini-2.5-flash-native-audio-latest";
liveConnectConstraints: {
  model: MODEL,
  config: {
    responseModalities: [Modality.AUDIO],
    inputAudioTranscription: {}, outputAudioTranscription: {},
    speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName } } }, // Charon/Puck/Aoede/Kore/Zephyr per avatar
    realtimeInputConfig: { automaticActivityDetection: { disabled: true } }, // PUSH-TO-TALK, VAD off
    tools: [{ functionDeclarations: guardianToolDeclarations }],
    systemInstruction, // base prompt + LIVE VAULT STATE read on-chain at token time
    enableAffectiveDialog: true,
  },
},
```

  Comment in that file: "CRITICAL: with ephemeral tokens the session config is LOCKED here via liveConnectConstraints — client-provided systemInstruction/tools are ignored." and "proactiveAudio stays OFF — it was suppressing responses". Those are two real DX lessons for anyone copying the Gemini Live route.
- `guardian/app/lib/useGuardianVoice.ts`: `getUserMedia` mono 16 kHz with echo cancellation; AudioWorklet (`/worklets/capture-worklet.js`) → Int16 PCM → `sendRealtimeInput({ audio: { data, mimeType: "audio/pcm;rate=16000" } })` only while the button is held; turn boundaries via `activityStart`/`activityEnd`; 24 kHz playback worklet as jitter buffer; half-duplex (mic muted while agent speaks); barge-in on `serverContent.interrupted`; iOS `AudioContext.resume()` on pointer-down. **VERIFIED.**
- ElevenLabs usage: `components/ui/{orb,live-waveform,conversation,voice-button,mic-selector,...}.tsx` are the ElevenLabs UI kit; `GuardianShell.tsx` imports only the `ElevenLabs.Voice` *type* to shape the avatar picker. `hooks/use-scribe.ts` imports `Scribe` realtime STT from `@elevenlabs/client` but is **referenced nowhere** (grep across `GuardianShell.tsx`, `Guardian.tsx`, `talk/page.tsx` finds no `useScribe`). The deck badge reads literally "GEMINI LIVE · ELEVENLABS UI". **VERIFIED.**
- Five selectable avatars (clay-robot "Guardian", dog "Biscuit", "Juno", "Ginger", alien "Nova"), each a Gemini prebuilt voice + looping mp4 clips. Pure presentation.

### 1.3 How a voice command becomes an on-chain action

Thirteen function declarations in `guardian/app/lib/guardianTools.ts` (**VERIFIED**): `check_wallet_safety`, `get_guard_status`, `execute_rescue(amountUsdc)`, `discover_subgraph`, `get_subgraph_schema`, `query_subgraph`, `show_panel(panel)`, `get_portfolio`, `compare_markets`, `invest_now(amountUsdc?)`, `protect_now(amountUsdc?)`, `set_danger(on)`, `propose_policy(investCapUsdc, protectCapUsdc?, hours?)`.

Routing (**VERIFIED**, `useGuardianVoice.ts` + `GuardianShell.tsx` + `api/tools/route.ts` + `lib/engine.ts`):

| Tool | Where it runs | Ledger involved? |
|---|---|---|
| `show_panel`, `propose_policy` | client (`CLIENT_TOOLS`) | `propose_policy` only **drafts** `{investUsdc, protectUsdc, safeHaven: FLEX_OWNER, hours}` on screen. The user must then press a button; voice never triggers the device. |
| `compare_markets`, `get_portfolio`, `check_wallet_safety`, subgraph tools | `POST /api/tools` (server, holds `GRAPH_API_KEY`) | no |
| `invest_now`, `protect_now` | server returns an **ack only** ("executing on your device"); the client `onTool` hook then calls `commandRef.current("invest"|"protect")` → `POST /api/act` with `{policy, signature}` pulled from `localStorage` | **no device tap**. Server `runCommand` re-verifies the stored mandate (`ethers.verifyTypedData` recovers to the hard-coded `FLEX_OWNER`, checks expiry) and sends the tx with `AGENT_PRIVATE_KEY`. |
| `execute_rescue` | server, legacy Arc path, server-held mandate from `/arm` | no |
| autonomous tick | `POST /api/tick` every loop with the same stored mandate | no |

Spoken flow from the deck (scene 4): YOU: "Put my idle USDC to work." → ITHACA: "Compound's the safe pick — deploying." → caption `→ invest(USDC → COMPOUND) · inside the mandate`. Presenter note: "Say 'put my idle USDC to work' — Ithaca senses the markets, checks the mandate, and acts." **VERIFIED** (`guardian-demo/index.html`).

System prompt excerpts (**VERIFIED**, `guardianSystemInstruction`): "ARMING BY VOICE: when the user dictates their rules — how much to invest, how much to protect, how long — call propose_policy … Only their Flex signature can authorize it; you never sign for them." and "CRITICAL — arming: you CANNOT invest, deploy, or protect until the guardian is armed with a policy the user signed on their Ledger Flex." The prompt also injects live vault balances and the graphscout market ranking at token-mint time.

**So the autonomy/approval boundary is:** human signs one Policy (and, optionally, one Escalation per out-of-bounds evacuation); everything else, including every voice-triggered invest/protect, runs on a hot key without the device. That is a legitimate design, and it is exactly what the brief's "sign once, agent acts within caps" idea looks like when built.

### 1.4 What the Ledger actually signs

`guardian/app/lib/useLedgerPolicy.ts` (**VERIFIED**):

```ts
const PATH = "44'/60'/0'/0/0";
// transport chosen at runtime
const { webBleTransportFactory } = await import("@ledgerhq/device-transport-kit-web-ble");   // or
const { webHidTransportFactory } = await import("@ledgerhq/device-transport-kit-web-hid");
const dmk = new DeviceManagementKitBuilder().addTransport(factory).build();
const device = await firstEmitted(dmk.startDiscovering({}), 30_000 /* "no Flex found — connect it by USB, unlock it, open the Ethereum app" */);
const sessionId = await dmk.connect({ device });
const signerEth = new SignerEthBuilder({ dmk, sessionId }).build();
if (beforeSign) await beforeSign();          // Face ID gate, AFTER device chooser, BEFORE signing
const { observable } = signerEth.signTypedData(PATH, { domain, types, primaryType, message });
// subscribe → DeviceActionStatus.Completed → { r, s, v } → ethers.Signature.from(...).serialized
```

Domain: `{ name: "Guardian", version: "1", chainId, verifyingContract: GuardianVaultMulti }`.

Two message types:

```
Policy(uint256 investCap,uint256 protectCap,address safeHaven,uint256 expiry,uint256 nonce)
  investCap  = round(usdc * 1e6)        protectCap = round(usdc * 1e6)
  safeHaven  = FLEX_OWNER (default)     expiry = now + hours*3600 (default 168 h)
  nonce      = unix seconds at signing

Escalation(uint256 amount,address safeHaven,uint256 expiry,uint256 nonce)
  one specific evacuation, expiry default now + 1 h, single-use on-chain
```

- **One-time mandate vs per-transaction:** standing mandate. The only per-event signature is `Escalation`, used for a high-risk evacuation beyond the mandate. `signTransaction`/`signMessage` are never called; the Ledger never broadcasts anything. **VERIFIED.**
- **No clear-signing descriptor.** No `@ledgerhq/context-module` configuration, no `originToken`, no ERC-7730 file in the repo. UI hints say literally: "USB · unlock the Flex, open the Ethereum app (blind signing on) · desktop Chrome/Edge". **VERIFIED.**
- **What the Flex shows (INFERRED from VERIFIED app behaviour, see `clear-signing-erc7730.md` §6):** the Ethereum app's unfiltered EIP-712 path. On Flex/Stax that defaults to raw/verbose mode: the struct name and each field with its key name and raw value, plus the blind-signing warning. So the signer reads something like `investCap 1000000000`, `protectCap 1000000000`, `safeHaven 0xDeC3…`, `expiry 1757…`, `nonce 1757…`. No USDC formatting, no human words, no sign of the voice command. On a Nano S Plus the same request would show only domain/message hashes unless "Verbose EIP712" is enabled. **The spoken intent is not on the device; the caps are.**
- Transports: WebHID (USB) and Web Bluetooth, both desktop Chrome/Edge (BLE also Android Chrome). Discovery takes the first device found. A `?m=<base64>` URL import exists so a phone can load a mandate the desktop Flex signed ("the Flex can only sign on desktop"). **VERIFIED** (`mandate.ts`).
- Owner address is a **hard-coded constant** `FLEX_OWNER = 0xDeC312D5Fe0eaef03048BE83137f87cE7907A7Da`; both client and server compare the recovered signer to it. A different Ledger would "sign, but signer … ≠ Flex owner". Single-user by construction. **VERIFIED.**

### 1.5 The on-chain guard: `GuardianVaultMulti.sol`

**VERIFIED** (`guardian-contracts/contracts/GuardianVaultMulti.sol`, MIT; README claims 26 passing Hardhat tests).

- `EIP712("Guardian","1")`; typehashes exactly as above.
- `_verify(p, sig)` on `invest()` and `protect()`: ECDSA-recover must equal `owner`, `block.timestamp <= expiry`. **`nonce` is in the struct but never stored or checked** — replay/revocation protection comes only from expiry and `protectedPerPolicy[digest]` cumulative accounting. Consequence (INFERRED): a signed Policy cannot be revoked before expiry except by `setAgent()` to a dead address.
- `investCap` = max total live position across venues (point-in-time check `totalPosition + amount <= investCap`); `protectCap` = cumulative USDC evacuated per policy digest; `safeHaven` must be in `safeHavenAllowed` (owner-set mapping).
- Venue allowlist (`venues`, `aTokens`) fixed at construction, **not** part of the signed Policy.
- `onlyAgent`: `invest(policy,sig,venue,amount)`, `deRisk(venue,amount)` (no signature), `rebalance(from,to,amount)` (no signature), `protect(policy,sig,amount)`, `approveAndProtect(escalation,sig,amount)` (requires `!escalationUsed[digest]`, `amount <= e.amount`, marks used, `e.safeHaven` may be outside the allowlist).
- `onlyOwner`: `setAgent`, `setSafeHaven`, `ownerWithdraw(amount,to)`. `deposit` is public.
- Deployed: Base Sepolia vault `0x81AEbF68946D62FDf088579A6F6F2c587015e28A`, Arc testnet vault `0x67ef856e1a95be96aa4Cdbd7B0cF348A6C4dD808`, agent `0x975Bb943F18fe44333eF28D18865ca5A5D63c23D`. CCTP V2 burn (Base) `0x285c…` / mint (Arc) `0x4ca0…`. Venues on Sepolia are mocks (`MockYieldVenue.sol`, `MockAavePool.sol`, `MockUSDC.sol` exist) while graphscout ranks real mainnet subgraphs — the "Aave / Compound / Moonwell" ranking and the Sepolia funds are decoupled. **VERIFIED files; INFERRED decoupling.**

### 1.6 Key Ring broker (`ledger-broker/`)

**VERIFIED** (`src/broker.js`, `README.md`, `SUBMISSION.md`):

- Node `http` server on `127.0.0.1:8799`, one capability: `POST /capability/sign-vault-action { method, args, broadcast? }`, gated by header `x-broker-token`. `CAPABILITY_METHODS = {invest, deRisk, rebalance, protect}`; asserts `tx.to === vault`; appends an audit line to `audit.jsonl`; never returns the key.
- Secret backends: `keyring` = `wallet-cli ring decrypt` of `agent-key.enc` (ring key name `guardian-agent`) with `WALLET_PASS` from env; `local` = AES-256-GCM passphrase (dev). `src/enroll.mjs` uses the LKRP SDK (`addMember`) to enrol USB-less hosts and revoke them.
- Commit 2026-09-12 19:09: "Ledger Key Ring backend proven live: fix wallet-cli spawn on Windows" — so it was exercised on Windows.
- **But** `guardian/app/lib/vaultMulti.ts` line 91: `const pk = process.env.AGENT_PRIVATE_KEY || process.env.PRIVATE_KEY;` with comment "execute bounded actions with the agent relayer key (AGENT_PRIVATE_KEY, server-only)". The Vercel app that the voice demo runs never talks to the broker. The broker is consumed only by `guardian-agent/daemon-multi.js` when `BROKER_URL` is set. A juror reading the showcase text ("A broker built on the Ledger Key Ring holds the agent's key") would assume the live app uses it; the code says otherwise.

### 1.7 Face / liveness / speaker identification

Two unrelated things both called "Face ID" (**VERIFIED**):

1. `guardian/app/lib/faceId.ts` — real WebAuthn, but as a gate only:

```ts
const available = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
if (!available) return { ok: true, skipped: true };            // no Face ID / Touch ID / Hello → don't block
// first run: navigator.credentials.create({ authenticatorSelection: { authenticatorAttachment: "platform", userVerification: "required", residentKey: "preferred" } })
// later:     navigator.credentials.get({ allowCredentials: [stored], userVerification: "required" })
return { ok: true };   // assertion result discarded; nothing sent to a server
```

   Header comment: "It's a presence/identity gate for the arming UX, not a server-verified credential — the cryptographic authority over funds remains the Flex's EIP-712 signature." Runs as `beforeSign` on arm and on escalation, after the DMK device chooser (because WebAuthn would otherwise consume the user gesture and WebHID/BLE `requestDevice` would fail with "Must be handling a user gesture" — a real integration lesson). On Windows this is Windows Hello, which falls back to PIN with UV=true (see `voice-face-agent-feasibility.md` §6.1). Credential ID lives in `localStorage`.
2. `guardian/app/FaceIdFlow.tsx` — the onboarding sheet: "Set up Face ID" → "Scanning your face… Hold still — almost there." → `setTimeout(() => setPhase("done"), 2300)` → "Face ID enabled. You're all set. Your capital is locked down." No camera, no model, no API. Pure theatre.

No speaker identification, no voice biometrics, no liveness. Once armed, anyone within earshot of the mic can say "put my money to work" or "get me out"; the damage is bounded by the contract (funds only go to allowlisted venues or the owner's safe haven), which is the project's honest answer.

### 1.8 Chains, assets, infra

Base Sepolia + Arc testnet, USDC only, Circle CCTP V2 round trip proven, "USYC-ready" on Arc mainnet (claimed). Next.js 16 PWA on Vercel, "no backend daemon" for the live app (optional `guardian-agent/` daemon with Groq `llama-3.3-70b-versatile` for a separate LLM loop). The Graph gateway + Subgraph MCP via `graphscout/` (claims ~98x fewer tokens, one round trip). Built with Claude and Cursor (listed technologies). **VERIFIED.**

### 1.9 DX feedback / what went wrong

- **No DX feedback document in the repo.** Final commit: "Repo cleanup: drop internal working docs from the public repo; reframe security notes as guarantees". Both SUBMISSION.md files have placeholder video/repo links. The ETHOnline rules weighed DX feedback "as much as the code"; absence here is notable. **VERIFIED.**
- Lessons visible in code comments (**VERIFIED**): ephemeral-token config lock; `proactiveAudio` suppressing responses; VAD disabled to avoid echo; `ScriptProcessorNode` fallback when AudioWorklet unavailable; iOS AudioContext priming; WebAuthn vs device-chooser gesture ordering; `invest_now` ack-then-client-execute dance because the server cannot hold the mandate; `Number(v) < 27 ? v + 27` normalisation of DMK's `v`; `startDiscovering` first-device + 30 s timeout; capability guards for missing `navigator.hid`/`navigator.bluetooth` ("Safari / Firefox / all iOS browsers lack both"); Windows `wallet-cli` spawn fix; contract cap is point-in-time so the engine deploys "headroom" not raw idle to avoid `OverInvestCap` reverts.
- Deck presenter notes give the pitch verbatim (**VERIFIED**): "every agent wallet in 2026 is a gas pedal with no brakes"; "Sign once; it acts autonomously within those bounds for as long as you allow"; "A stolen key can annoy — never steal"; "The Graph gives it eyes. Ledger gives it a conscience. Circle gives it a safe harbor." Scene 6 mandate panel rows: INVEST ≤ CAP · allowlisted venues only / PROTECT → SAFE HAVEN · any time, instantly / EXPIRES dies unless renewed / NOTHING ELSE send-anywhere → onlyOwner.

---

## 2. Orchestra teardown

### 2.1 Identity card

| | |
|---|---|
| Showcase | https://ethglobal.com/showcase/orchestra-mkifq — **VERIFIED** |
| Tagline | "Talk to your crypto. An AI agent for seamless swaps and sends with Ledger security." |
| Hackathon | ETHGlobal Cannes 2026. Repo created 2026-04-03, 23 commits Apr 3–5 2026 by Youssef Jeddi and `Hassene26`; `pushed_at` 2026-10-07 (README/description touch, no code history after Apr 5). — **VERIFIED** |
| Prize | **0G — "Best OpenClaw Agent on 0G" 3rd place.** No Ledger prize listed. Cannes Ledger track was "AI Agents x Ledger $3,700 (1st $1,500 / 2nd $1,000 / 3rd $700 / 4th $500)". — **VERIFIED** (showcase; https://ethglobal.com/events/cannes2026/prizes/ledger) |
| Ledger feature | Quoted on https://shop.ledger.com/pages/ledger-agent-stack as an early tester: "a swarm of AI agents managing your on-chain portfolio from natural language", crediting DMK. — **VERIFIED** |
| Repo | https://github.com/youssef-jeddi/Orchestra — license field null (package.json says MIT), 0 stars. Live https://orchestra-weld.vercel.app. Demo video on showcase as Mux stream (`yzd5VYr00B021fH8KK2YsyTYJDh8vEyJZc9TNE11YhdZE`, source `.mov`), not watched. |

### 2.2 Input modality: text only

- README: "**User types:** *'swap 10 USDC for ETH'*"; frontend described as "Chat interface".
- `frontend/src/components/SearchBar.jsx`: single `<input type="text">`, placeholder "Where do you want to invest today?", submit on Enter. No `SpeechRecognition`, `getUserMedia`, `MediaRecorder`, Whisper, ElevenLabs, Deepgram, OpenAI Realtime anywhere in the tree (344 paths listed; none audio-related). **VERIFIED.** "Talk to your crypto" means natural language, not speech.

### 2.3 Agent and policy design

- Bridge server (Express, `src/integrations/ledger/serve.ts`) `POST /intent`: **Planner AI** (Groq or 0G Compute, runtime-switchable) → structured plan with USD estimate → **Gatekeeper AI** reads profile from 0G Storage → `AUTO_EXECUTE | NEEDS_APPROVAL | BLOCKED` → **server-side safety net** overrides the LLM in both directions against `autoApproveLimit` (default $100): `if (totalEstimatedValueUsd > autoApproveLimit && verdict === "AUTO_EXECUTE") verdict = "NEEDS_APPROVAL"` and the reverse. → Executor. **VERIFIED.**
- Custody: a Safe per user with the **Ledger as owner** and an **agent EOA (`AGENT_PRIVATE_KEY` in `.env`, generated by a script) as AllowanceModule delegate**; on-chain spending limits for ETH/WETH/USDC. **No Key Ring, no broker.** **VERIFIED** (README, `serve.ts`).
- `contracts/src/OrchestraPolicy.sol` is a 40-line registry `mapping(address => UserPolicy{safeAddress, agentWallet, spendingLimitUSD, initialized})` keyed by `msg.sender`; `finalize-limit-update` writes it **with the agent key** ("agent wallet signs — it's just a registry write", "non-critical"), so the registry entry is keyed by the agent address, not the Ledger. It enforces nothing. **VERIFIED code; INFERRED keying bug.**
- A separate, older "SafeSwarm × Ledger" module (`riskEngine.ts`, `types.ts`) has three tiers ($100 auto / $1,000 approval / $100k liquidity floor) but its middle-band branches both return `autonomous`; the design doc `safeswarm-ledger.md` describes an ERC-7730 descriptor for the Universal Router that only formats `deadline`. **VERIFIED.**

### 2.4 What the Ledger signs and shows

- Packages: `@ledgerhq/device-management-kit ^1.2.0`, `device-signer-kit-ethereum ^1.13.0`, `device-transport-kit-web-ble ^1.3.2`, `@ledgerhq/context-module ^1.15.0` (installed, never configured; no `originToken`). **Web BLE only** in both `dmk.ts` and `frontend/src/lib/ledger.js`. **VERIFIED.**
- **Per-transaction signing**, the opposite of ITHACA: `signer.signTransaction("44'/60'/0'/0/0", rlpBytes, { skipOpenApp: true })` for approval tx / swap tx / Safe MultiSend, and `signer.signTypedData(path, typedData, { skipOpenApp: true })` for Permit2. Before signing, `OpenAppDeviceAction({ appName: "Uniswap" })` is attempted ("Uniswap app opened (clear signing)"), falling back to the Ethereum app. **VERIFIED.**
- Device display (INFERRED from the above): a Universal Router swap with the Uniswap plugin app open gets Ledger's stock Uniswap clear-signing screen; the Safe `execTransaction`/MultiSend for a spending-limit change and the Sepolia ERC-20 approve render as generic contract calls in the Ethereum app (likely blind-signing prompt). No custom descriptor is possible for them (same registry constraint as everyone else).
- Approval transport: server broadcasts `APPROVAL_REQUIRED { tradeId, unsignedTxHex, summary, riskLevel }` over WebSocket; the browser `ApprovalOverlay` shows `summary` and a truncated hex and a "Sign on Ledger" button; result returns as `APPROVAL_RESULT`. 5-minute timeout. **VERIFIED.**
- README setup error: "A Ledger hardware wallet (Nano S/X) with Bluetooth" — Nano S / S Plus have no Bluetooth; only Nano X / Stax / Flex do. **VERIFIED text; hardware fact from `device-capabilities-nfc-ble.md`.**
- Chain: Sepolia only (USDC, WETH, ETH). No face/liveness/voice identity of any kind.

---

## 3. Every other voice- or identity-adjacent project found

### 3.1 Voice wallets with no hardware signer (the corpus `voice-face-agent-feasibility.md` already had, plus two)

| Project | Event | Voice stack | Signing | Source |
|---|---|---|---|---|
| Speaky | ETHGlobal New Delhi | OpenAI Realtime over WebRTC, Nuxt 4 | MetaMask popup | https://ethglobal.com/showcase/speaky-vdd3b **VERIFIED** |
| Vane | ETHGlobal Trifecta – Agents | Alexa skill, Lambda, DynamoDB | Privy server wallets, deny-all unless whitelisted | https://ethglobal.com/showcase/vane-2v96c **VERIFIED** |
| LightWallet | ETHGlobal New York 2023 | ASR + "voiceprint matching" (a speaker-ID claim, undocumented) | MetaMask / WalletConnect. Won Mask 3rd, WalletConnect "Most Innovative" 2nd | https://ethglobal.com/showcase/lightwallet-e2ici **VERIFIED** |
| say less | ETHGlobal Bangkok | OpenAI streaming API | Circle Developer-Controlled Wallets | https://ethglobal.com/showcase/say-less-dz1qr **VERIFIED** |
| VoiceVault, EthTalk, Voice to Web3, Irada, Siri Chain, My Precious (Alexa), SOLA AI | various | see `voice-face-agent-feasibility.md` §5 | software/custodial | (previously VERIFIED there) |

### 3.2 Voice *output* + Ledger

- **Kickoff.bot / Aivy Studio** (ETHGlobal NYC 2026, https://github.com/jmgomezl/aivy-studio): seller agent "speaks its verdict via ElevenLabs voice" (TTS only, no voice input); DMK over WebHID as a "Ledger approval gate" node; "pre-signed delegation policy (sign once, agent operates within limits)". Has `docs/ledger-dx-feedback.md` — the most concrete public DX doc I found: `@ledgerhq/context-module` is a hidden hard dep (build fails without it), DMK does not resolve under raw Node ESM ("Directory import … is not supported", must use tsx/Vite), wrong package names circulate, `originToken` under-documented, `signTransaction` wants RLP-encoded *unsigned* `Uint8Array` and returns `{r,s,v}` to reassemble with ethers v6 `Signature.from`. **VERIFIED.**
- **Wikshi** (ETHOnline 2026): gives *agents* a phone voice and video face via x402 on Hedera; no Ledger. **VERIFIED.**

### 3.3 Audio (not voice) + custom hardware signer

- **MelodyPay** (ETHOnline 2026): air-gapped ESP32-S3 wallet, FSK audio via ggwave, EIP-712/EIP-3009 `ReceiveWithAuthorization` signed in C, USDC on Arc testnet, ENS merchant subnames. No Ledger. Shows jurors have seen "hardware + sound + USDC" already. **VERIFIED** (https://ethglobal.com/showcase/melodypay-9ntio).

### 3.4 Face / human-verification + agent spending (no Ledger)

- **FaceGate** (ETHOnline 2026): World ID Selfie Check liveness, nullifiers only, SDK `@facegate/sdk`. **VERIFIED.**
- **Axis** (ETHGlobal Tokyo 2026): treasury agent; small trades auto, medium need a **fresh World ID verification**, large blocked; EIP-712 mandate signed in Uniswap Wallet extension. Same tiered shape as Orchestra/ITHACA with World ID in the Ledger slot. **VERIFIED** (https://ethglobal.com/showcase/axis-ybtp8).
- Also Tokyo 2026: **DSAP Protocol**, **My Agent Ohana**, **Proviso** (World ID approvals for agent spending). **VERIFIED titles from listing page.**

### 3.5 Ledger as FIDO2 in an agent flow

- **Speakeasy** (ETHOnline 2026): "Ledger is the actual KMS and the login authenticator" — Ledger Security Key (FIDO2/CTAP) for OAuth login, Key Ring for agent/facilitator/keeper keys, DMK + node-hid or Speculos. No voice despite the name. **VERIFIED** (https://ethglobal.com/showcase/speakeasy-j4fws).

### 3.6 Ledger's own roadmap (why identity matters to this jury)

The Block (2026-04): Q2 "hardware-linked identities for AI agents"; Q3 "agent intents and policies … reviewed on a trusted display … hardware-enforced policies"; Q4 **"proof of human" features "aimed at verifying that a real person is behind an AI agent"**. Ian Rogers (on the N3XT jury) was named "first chief human agency officer to lead its AI efforts". No biometric modality is named anywhere. **VERIFIED** (https://www.theblock.co/post/397284/...). The Agent Stack shop page lists "Proof of You" as coming soon (per `prior-art-hackathon-projects.md`). ITHACA already occupies "intents and policies"; nobody has shipped a credible "proof of human in front of a signer" demo.

### 3.7 Search coverage and gaps (be honest)

- `https://ethglobal.com/showcase?search=voice` and `?search=ledger%20voice` **ignore the query server-side** and return the ETHGlobal Tokyo 2026 listing (33 projects, none voice). Per-project pages had to be reached by slug. **VERIFIED.**
- `gh search code` for `device-management-kit` + `speech|SpeechRecognition|elevenlabs|whisper` returned nothing; `gh search repos "voice ledger"` returns only bookkeeping apps named VoiceLedger. **VERIFIED.**
- WebSearch (standard + extended) across ETHGlobal/Devfolio/lablab/DoraHacks for voice + Ledger surfaced nothing beyond ITHACA. **VERIFIED negative.**
- I could not watch either Mux demo video (no caption tracks). Deck notes are a strong proxy for ITHACA; nothing equivalent exists for Orchestra.
- I did not enumerate all ~850 ETHOnline 2026 projects; `prior-art-hackathon-projects.md` covered the 27 Ledger-flagged pages. A voice project that used Ledger without tagging it could have been missed. **INFERRED residual risk: low.**
- 2nd place "AI Agents x Ledger" at ETHOnline 2026 remains unidentified.

---

## 4. Side-by-side

| Dimension | ITHACA | Orchestra | Starter idea #1 as written |
|---|---|---|---|
| Input | voice (Gemini Live, push-to-talk) | typed chat | voice |
| Speech vendor | Google Gemini 2.5 Flash native audio | none | TBD |
| Ledger signs | one EIP-712 `Policy` (168 h) + single-use `Escalation` | every over-limit tx (`signTransaction`) + Permit2 typed data + Safe MultiSend | per spoken transaction (implied) |
| Device shows | raw EIP-712 fields, blind-signing on, no descriptor | Uniswap plugin clear-sign for swaps; generic contract call for Safe ops | TBD |
| Spoken intent on screen? | no | n/a | the open door |
| Identity | WebAuthn presence gate (skippable, result discarded) + fake scan animation | none | "scan their face" |
| Agent key | `AGENT_PRIVATE_KEY` env on Vercel; Key Ring broker exists but detached | `AGENT_PRIVATE_KEY` env | TBD |
| Guard | custom vault, caps + allowlists + expiry | Safe AllowanceModule + trivial registry | TBD |
| Transport | WebHID + Web BLE, Flex only (hard-coded owner) | Web BLE only | USB (Nano S Plus) + BLE/USB (Flex) |
| Chain / asset | Base Sepolia + Arc testnet, USDC | Sepolia, ETH/WETH/USDC | TBD |
| Use case | DeFi yield rotation | swaps/sends | "send money by voice" |
| DX feedback | none in repo | none | required by N3XT brief |
| Result | 3rd, AI Agents x Ledger | 3rd, 0G track; Ledger shop feature | — |

---

## 5. Why a juror will read starter idea #1 as "ITHACA again"

Ian Rogers and Guillaume Mathias almost certainly saw ITHACA: it placed in Ledger's own track four weeks ago, Ledger DevRel judged it, and it is the only voice entry in that track. Orchestra is on Ledger's shop page. The pitch "voice agent, Ledger confirms, face check" maps onto ITHACA's showcase text one-for-one ("voice-run AI", "Ledger Flex signs", "Face ID gates the arm"). "Face scan" without substance will land worse than no face at all, because ITHACA's face step is already known to be a WebAuthn gate with a cosmetic animation. "Agent proposes, policy caps, Ledger signs" is also the exact shape of Harness (1st), Orchestra, Axis, Finity, Mandate ×3 and 25+ others (`prior-art-hackathon-projects.md` §8).

---

## 6. What a new project must do differently (concrete, each one checkable in code)

Ordered by how much it changes what the juror *sees*, not by effort.

1. **Put the spoken intent on the Secure Screen.** ITHACA's device shows `investCap 1000000000`. Make the device show the words. Two no-registry paths that work on both devices today (from `clear-signing-erc7730.md` §6): `signerEth.signMessage(path, "Pay 25 USDC to alice.eth (0x1234…) · said at 14:02:11 · req 7f3a")` renders the full ASCII on screen (EIP-191); or EIP-712 with descriptive field names (`action`, `to`, `amount`, `spokenAt`, `transcriptHash`) that the Flex renders field-by-field in verbose mode. Then the TTS reads back *exactly those fields* before the tap: "what you hear is what you sign". Nobody has done this.
2. **Per-utterance signing, not a standing mandate.** ITHACA's whole thesis is "sign once, act forever". Invert it: every spoken payment is one device tap, and the autonomous part is everything *around* the payment (resolve the contact, pick the chain, check the balance, draft the message, schedule, retry). State the boundary in one sentence in the README and the pitch, as the brief asks.
3. **Make identity select the policy, and make it unskippable.** ITHACA's `faceIdGate` returns `ok:true` when no biometric exists and discards the assertion. If face/voice/FIDO2 identity is kept, it must change what gets signed: e.g. the recognised person's own contact book / daily cap / allowed assets is what gets decrypted (Key Ring or WebAuthn PRF) and drafted; an unrecognised face gets nothing to sign. Strongest Ledger-native variant: the **Flex as FIDO2 roaming authenticator** for the session (brief line "Device as a security key"), which is "device-backed identity" from the same device that signs. Be explicit on stage that face/voice recognition is personalisation and replay deterrence, not authorisation; the tap is authorisation. That honesty is itself a differentiator from ITHACA's "Face ID as a second factor" wording.
4. **Pick a non-DeFi or people-payments use case.** ITHACA = yield rotation; Orchestra = swaps. The brief says "Most existing work points the stack at wallets and transactions… Non-finance ideas count." Even inside payments, "send 20 USDC to Mum" from a contact book, or the accessibility story (a blind user cannot read the Secure Screen; the agent reads the device fields aloud so the tap is informed, extending LightWallet's 2023 angle to a hardware signer) is a story no voice+Ledger project has told.
5. **Demo on the Nano S Plus as well as the Flex.** ITHACA hard-codes a single Flex owner and every status string says "Flex". Showing the same intent on a 128×64 screen (with "Verbose EIP712" or an EIP-191 message) proves the design is about Ledger signers, not one device.
6. **Use Key Ring inside the app that runs the demo**, for something that is not "decrypt an API key at boot" (15+ projects do that). Candidates: encrypt the per-person contact book/policy under the ring; or encrypt the voice-enrolment embeddings so they are useless off this Ledger.
7. **Avoid ITHACA's exact aesthetic and vocabulary:** Gemini Live orb + waveform avatars, "gas pedal with no brakes", "a stolen key can annoy, never steal", "sign once". Also avoid the "poisoned invoice" demo (5+ projects) and ETHGlobal-style AI voiceover in the video (ETHGlobal bans it; the N3XT brief does not, but a human narrator costs nothing).
8. **Ship the DX feedback document** (required by N3XT, absent from ITHACA). Concrete items already known from this corpus: `context-module` hidden peer dep, Node ESM resolution, `originToken` opacity, `v` normalisation, WebAuthn-vs-device-chooser gesture ordering, Windows `wallet-cli` spawn, EIP-712 verbose-mode difference between Flex and Nano.
9. **Jury-specific hooks (tactical, INFERRED):** Joshua Mo (Venice, privacy AI) will notice if STT runs locally (whisper.cpp on this machine is already proven, see `project_typewhisper_local_stt`) instead of streaming the user's voice to Google; Drake Breeding (Circle) will notice USDC as the asset; Ian Rogers owns "proof of human" on Ledger's roadmap, so frame the identity step in those words.

---

## 7. Corrections to make in the other notes

- `research/voice-face-agent-feasibility.md` §5, line "Nobody has combined voice intent with a hardware clear-signing screen… 'voice + Ledger' is open ground (INFERRED from absence)": **false as of Sep 2026.** Replace with: "ITHACA (ETHOnline 2026, 3rd place AI Agents x Ledger) combined voice intent (Gemini Live) with a Ledger Flex that signs one EIP-712 standing mandate via DMK; nobody has put the spoken intent itself on the device screen or made identity select the policy." The §5 table should add ITHACA, say less, and mark LightWallet as 2023 with a "voiceprint matching" claim.
- `research/prior-art-hackathon-projects.md` §7a: tighten "Gemini Live + ElevenLabs" to "Gemini Live (STT, reasoning, TTS) with the ElevenLabs React UI kit; no ElevenLabs speech"; add "Key Ring broker not used by the deployed app"; add "Face ID = WebAuthn gate, skippable, plus cosmetic animation". Mark Orchestra as "text chat, VERIFIED not voice" rather than "not confirmed".

---

## 8. Sources

ITHACA
- https://ethglobal.com/showcase/ithaca-i7yxs
- https://github.com/chrsnikhil/ithaca (README.md; guardian/package.json; guardian/app/api/gemini-token/route.ts; guardian/app/api/tools/route.ts; guardian/app/api/act/route.ts; guardian/app/api/escalate/route.ts; guardian/app/lib/{engine,guardianTools,useGuardianVoice,useLedgerPolicy,useLedgerMandate,mandate,faceId,vaultMulti}.ts; guardian/app/{GuardianShell,Guardian,FaceIdFlow}.tsx; guardian/app/arm/page.tsx; guardian/hooks/use-scribe.ts; guardian/README.md; guardian-contracts/contracts/GuardianVaultMulti.sol; ledger-broker/{README.md,SUBMISSION.md,src/broker.js}; graphscout/SUBMISSION.md; guardian-demo/index.html; guardian-agent/.env.example; commit list via `gh api repos/chrsnikhil/ithaca/commits`; `gh api users/chrsnikhil`)
- https://guardian-rho-two.vercel.app (not loaded)
- Mux manifest https://stream.mux.com/S02ErOfZRpkcuV00x6IwLdOMXI4pcS01wVG3zib025w1kfU.m3u8 (video exists, no captions)

Orchestra
- https://ethglobal.com/showcase/orchestra-mkifq
- https://github.com/youssef-jeddi/Orchestra (README.md; package.json; src/integrations/ledger/{dmk,signer,bridge,serve,types,riskEngine,clearSigning}.ts, safeswarm-ledger.md, ui/main.ts; src/agents/gatekeeper/actions/triggerLedgerApproval.ts; contracts/src/OrchestraPolicy.sol; frontend/src/lib/ledger.js; frontend/src/hooks/useLedger.js; frontend/src/components/{SearchBar,ApprovalOverlay}.jsx; full tree via git/trees API; commit list)
- https://shop.ledger.com/pages/ledger-agent-stack

Events, prizes, roadmap
- https://ethglobal.com/events/ethonline2026/prizes/ledger
- https://developers.ledger.com/ethonline
- https://ethglobal.com/events/cannes2026/prizes/ledger
- https://ethglobal.com/showcase/harness-vvvaq
- https://www.theblock.co/post/397284/crypto-ledger-ai-security-roadmap-agentic-economy-human-loop
- https://developers.ledger.com/docs/clear-signing/eip712 (redirects to overview; no EIP-712 display detail)

Other projects
- https://ethglobal.com/showcase/speaky-vdd3b ; https://ethglobal.com/showcase/vane-2v96c ; https://ethglobal.com/showcase/lightwallet-e2ici ; https://ethglobal.com/showcase/say-less-dz1qr
- https://ethglobal.com/showcase/facegate-omma4 ; https://ethglobal.com/showcase/melodypay-9ntio ; https://ethglobal.com/showcase/wikshi-pbc1d ; https://ethglobal.com/showcase/axis-ybtp8 ; https://ethglobal.com/showcase/speakeasy-j4fws
- https://github.com/jmgomezl/aivy-studio (README.md, docs/ledger-dx-feedback.md)
- https://github.com/drewmanley16/ledger-mcp
- https://raw.githubusercontent.com/YagnaRDK/Arx/main/docs/research/prior-art.md
- https://ethglobal.com/showcase?search=voice and ?search=ledger%20voice (query ignored; Tokyo 2026 listing)

Local notes relied on for device-display facts
- `research/clear-signing-erc7730.md` §6 (EIP-712 unfiltered rendering: Flex/Stax verbose by default, Nano needs "Verbose EIP712"; EIP-191 renders full ASCII)
- `research/dmk-ts-signer.md`, `research/dmk-skills.md`, `research/device-capabilities-nfc-ble.md`, `research/voice-face-agent-feasibility.md`, `research/prior-art-hackathon-projects.md`

Searches that returned nothing relevant (negative evidence): WebSearch "ethglobal showcase voice Ledger agent hardware wallet"; "ITHACA ETHOnline 2026 Ledger voice agent Gemini Live ElevenLabs"; "devfolio OR lablab.ai … voice agent Ledger"; "lablab.ai OR devfolio.co OR dorahacks.io Ledger voice assistant"; "ETHOnline 2026 AI Agents x Ledger 2nd place"; `gh search code "device-management-kit speech"`, `"elevenlabs ledgerhq"`, `"whisper device-signer-kit-ethereum"`, `"webkitSpeechRecognition ledgerhq"`.
