# Feasibility: voice agent + face gate + Ledger signer ("Siri for your wallet")

Research note for starter idea #1. Written 2026-10-10 from web sources only; no hardware touched, nothing installed.
Tags: **VERIFIED** = read in a primary source (official docs, spec, repo). **INFERRED** = derived, second-hand, or not confirmed.

Scope: Windows 11 host, Chromium browser, Ledger Nano S Plus (USB) and Ledger Flex (USB/BLE/NFC), 3 days of build time, deadline Oct 13 23:59 CEST.

---

## 0. TL;DR

- Every building block exists and runs in a Chromium browser on Windows. The whole thing can be one Vite page plus a ~30-line token server.
- **Ledger signing path (VERIFIED):** `@ledgerhq/device-management-kit` + `@ledgerhq/device-transport-kit-web-hid` + `@ledgerhq/device-signer-kit-ethereum`. WebHID = Chromium only, HTTPS or localhost, needs a click to start discovery. `signTransaction(path, Uint8Array)` returns `{r,s,v}` through an RxJS observable whose `Pending` states tell you exactly when the user must look at the device.
- **Voice (VERIFIED):** OpenAI Agents SDK `@openai/agents/realtime` gives a browser WebRTC voice agent with `tool({ needsApproval: true })` and a `tool_approval_requested` event. That event is the natural hook to run the face check and then hand the tx to the Ledger. Zero-cost fallback: Chrome's Web Speech API (now with on-device recognition on Windows) + `speechSynthesis` + one text LLM call.
- **Face (VERIFIED):** two very different options. (a) WebAuthn with Windows Hello = IR-camera face, anti-spoof, 20 lines, but the site cannot tell face from PIN and cannot bind transaction text into the signature. (b) Webcam libraries (`@vladmandic/human` has 1024-d embeddings, blink, anti-spoof and liveness models in <1 MB each) = fully controllable, demo-friendly, trivially spoofable in principle.
- **Trust model (blunt):** the Ledger button press on a clear-signed screen *is* the authorisation. A browser face check adds no cryptographic security to the signature. It adds value only as (1) **speaker identification** that selects account/policy/spending limits before the agent acts, (2) a **liveness gate against replayed/synthetic voice** so an attacker with the user's TTS clone cannot even get a request to the device, and (3) **multi-person approval** at the agent-policy layer. Pitch it that way and the jury's "name the boundary between agent and human" box is ticked.
- **Prior art:** many voice wallets (Speaky, Vane, LightWallet, VoiceVault, EthTalk, Voice-to-Web3, Siri Chain, SOLA AI). None uses a hardware signer; all delegate signing to MetaMask, Privy, Coinbase CDP or Circle. "Voice + Ledger" is open ground (INFERRED from absence in searches).
- **Strongest version (section 9):** *"Voice is for intent, face is for identity, the Ledger is for authority."* Voice agent captures intent → face identifies which enrolled person is speaking and loads that person's policy (allowed recipients, daily cap) → agent builds the tx and speaks back exactly what the Secure Screen will show → Ledger clear-signs → broadcast. Policy/contact book encrypted with Key Ring (second Ledger primitive). Optional: Ledger Flex itself as the FIDO2 WebAuthn authenticator for the session login, replacing Windows Hello.

---

## 1. Hackathon fit (from HACKATHON.md)

The brief wants: a concrete Ledger primitive actually implemented; an explicit autonomous-vs-approved boundary; real user value; runnable code or a recorded walkthrough. Jury includes Circle's ecosystem director and Venice's DevRel lead. Judging: technical 25 / Ledger relevance 20 / originality 20 / UX 15 / new use cases 10 / clarity 10.

Ledger's own hackathon prize page for ETHGlobal NY 2026 (VERIFIED, https://ethglobal.com/events/newyork2026/prizes/ledger) repeats the same wish list: "Human-in-the-loop agents where Ledger approves high-risk actions before funds move", "Ledger-backed identity, credentials, or policy-based spending for autonomous systems", "Clear separation between autonomous actions and explicit approval", "Concrete use of Ledger primitives, not just wallet branding". Policy-based spending is listed explicitly, which supports the "face selects policy" framing.

---

## 2. Ledger building blocks on Windows + browser

### 2.1 Device Management Kit (DMK), TypeScript

VERIFIED (https://github.com/LedgerHQ/device-sdk-ts, https://github.com/LedgerHQ/device-sdk-ts/blob/develop/packages/device-management-kit/README.md):

Packages in the monorepo:

| Package | Role |
|---|---|
| `@ledgerhq/device-management-kit` | core |
| `@ledgerhq/device-transport-kit-web-hid` | USB via WebHID (browser) |
| `@ledgerhq/device-transport-kit-web-ble` | Bluetooth via Web Bluetooth (browser) |
| `@ledgerhq/device-transport-kit-node-hid` | USB from Node |
| `@ledgerhq/device-transport-kit-speculos`, `-mockserver` | emulator / tests |
| `@ledgerhq/device-signer-kit-ethereum` (also bitcoin, solana, hyperliquid, zcash, icp) | per-chain signers |
| `@ledgerhq/device-trusted-app-kit-ledger-keyring-protocol` | Key Ring protocol |

Setup + discovery + connect (VERIFIED, core README; the README's own `connect` snippet is malformed, this is the corrected form):

```ts
import { ConsoleLogger, DeviceManagementKitBuilder, OpenAppCommand, GetAppAndVersionCommand } from "@ledgerhq/device-management-kit";
import { webHidTransportFactory } from "@ledgerhq/device-transport-kit-web-hid";

const dmk = new DeviceManagementKitBuilder()
  .addLogger(new ConsoleLogger())
  .addTransport(webHidTransportFactory)
  .build();

// must be triggered from a user gesture (button click)
dmk.startDiscovering().subscribe({
  next: async (device) => {
    const sessionId = await dmk.connect({ device, /* options: { isRefresherDisabled: true } */ });
    dmk.getDeviceSessionState({ sessionId }).subscribe(console.log); // connected | locked | busy | disconnected
    await dmk.sendCommand({ sessionId, command: new OpenAppCommand("Ethereum") });
    const { name, version } = await dmk.sendCommand({ sessionId, command: new GetAppAndVersionCommand() });
  },
  error: console.error,
});
```

INFERRED: the exact shape of the `connect()` argument (`{device}` vs `{deviceId}`) differs between the README text and the DMK Skills prose; check the `.d.ts` on install. Session states `connected / locked / busy / disconnected` are VERIFIED (https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/dmk).

Constraints (VERIFIED, https://developers.ledger.com/docs/ai-tools/ledger-dmk-skills): WebHID only in Chromium browsers, only on `localhost` or HTTPS, discovery must start from a user gesture. DMK cannot distinguish two devices of the same model over WebHID and cannot prevent connecting the same device twice (VERIFIED, dmk how-to page).

Windows specifics: no Ledger doc states Windows caveats for WebHID. Ledger Live itself speaks HID to the device on Windows, and the DMK one-pager lists "Windows · Linux · macOS via Node-HID, WebHID and WebBLE" (INFERRED from https://developers.ledger.com/pdf/dmk-one-pager.pdf via search snippet). Treat "Chrome + WebHID + Nano S Plus on Windows 11" as expected-to-work but unverified until you plug in.

### 2.2 Ethereum signer kit

VERIFIED (https://github.com/LedgerHQ/device-sdk-ts/blob/develop/packages/signer/signer-eth/README.md and https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/how_to_use_a_signer):

```ts
import { SignerEthBuilder } from "@ledgerhq/device-signer-kit-ethereum";

const signerEth = new SignerEthBuilder({ dmk, sessionId, originToken: "origin-token" }).build();

const { observable, cancel } = signerEth.getAddress("44'/60'/0'/0/0", { checkOnDevice: true });
// signTransaction(derivationPath: string, transaction: Uint8Array, { skipOpenApp?: boolean })
// signMessage(derivationPath, message: string)
// signTypedData(derivationPath, typedData /* EIP-712 */)
```

Observable emits `DeviceActionState` with status `NotStarted | Pending | Stopped | Completed | Error`. In `Pending`, `intermediateValue.requiredUserInteraction` is one of `VerifyAddress, SignTransaction, UnlockDevice, ConfirmOpenApp, SignPersonalMessage, SignTypedData, SignDelegationAuthorization, VerifySafeAddress, Web3ChecksOptIn, None`. `Completed.output` for sign calls is `{ r: 0x.., s: 0x.., v: number }`; for `getAddress` it is `{ publicKey, address, chainCode? }`.

Practical notes:
- `transaction` is the **unsigned serialized tx bytes** (`Uint8Array`), not an ethers object. Build it with viem `serializeTransaction` or ethers `Transaction.unsignedSerialized`, then reassemble with `r,s,v` and broadcast via any RPC (INFERRED standard pattern; the README does not show the serialisation step).
- `originToken` is "provided by Ledger"; without it Transaction Checks (Web3 Checks) are unavailable but signing still works (VERIFIED on the signer how-to page). Ask in the hackathon Discord for one; it's a mentor question, not a blocker.
- The `requiredUserInteraction` values are gold for the voice UX: when the state flips to `SignTransaction` the agent should say "Check the amount and recipient on your Ledger and press to approve."

### 2.3 Clear signing on the device

VERIFIED (https://developers.ledger.com/docs/clear-signing/overview via search): ERC-7730 metadata lets the Secure Screen render human-readable fields; Ledger's Generic Parser reads registry metadata so dApps no longer need plugins; unsupported calldata falls back to blind signing (unreadable hash/calldata). Stewardship moved to the Ethereum Foundation on 2026-05-12 and the format is at ERC-7730 V2.

INFERRED: a plain native ETH transfer (and ERC-20 transfer with known token metadata) is always clear-signed on the Ethereum app: amount, recipient, fees. For a hackathon demo stick to native transfers or a well-known token on Sepolia so the device shows readable fields. Do not demo arbitrary contract calls.

### 2.4 Bluetooth to the Flex from a browser

VERIFIED (https://developers.ledger.com/docs/device-interaction/beginner/ble_flex_stax.md): add `webBleTransportFactory` from `@ledgerhq/device-transport-kit-web-ble` alongside WebHID; needs DMK ≥ 0.4.0. Flex has BT (VERIFIED, Ledger press release). Chrome on Windows supports Web Bluetooth and uses the Windows BT stack (INFERRED, Google support page via search). No pairing docs for Windows found. Gap: nothing says Nano S Plus can do BLE (it cannot, no radio).

### 2.5 NFC on the Flex

VERIFIED (https://www.businesswire.com/news/home/20240726882083/en/...): the Flex's NFC is used by the **Ledger Security Key** app to tap a phone for FIDO2 login. No developer API for NFC appears anywhere in the developer portal search results. INFERRED: NFC is not reachable from the DMK or from a Windows browser. Irrelevant for idea #1.

### 2.6 Ledger Security Key app (device as FIDO2 authenticator)

VERIFIED (https://developers.ledger.com/docs/ai-tools/hardware-security/security-key, press release): Security Key app supports FIDO2 and U2F, provides 2FA and passkeys, runs on Stax and Flex, works over USB on a PC and NFC tap on a phone. Keys are generated on-device; "agents can use a session you already opened, but cannot start a new hardware-gated session without a person present".

Gaps: the Ledger Help Center article (https://support.ledger.com/article/12350325732893-zd) returned no content to the fetcher. Not verified: whether Nano S Plus can run it (press says Stax/Flex only), whether it supports discoverable credentials (a July 2026 Privacy Guides forum post implies Trezor does and Ledger does not; INFERRED), and whether device PIN unlock sets the WebAuthn UV flag.

Why it matters here: the Flex can be the WebAuthn authenticator for your web app's login (`authenticatorAttachment: "cross-platform"`). That is "device-backed identity" with the *same* device that signs. See 6.4.

### 2.7 Ledger Wallet CLI, Key Ring, Agent Intent

VERIFIED (https://developers.ledger.com/docs/ai-tools/ledger-cli):
- `npm i -g @ledgerhq/wallet-cli`; supported OS macOS, Linux, **Windows (WSL recommended)**. Commands: `genuine-check`, `account discover <network>`, `balances`, `operations`, `receive`, `send` (sign+broadcast, `--dry-run`), `swap *`, `earn *`, `ring init|encrypt|decrypt|keys|destroy`; everything takes `--output json`. Agent skill: `wallet-cli skill install --agent <cursor|claude|codex|agents>`.
- Key Ring: `ring init` once with the device (Ledger Sync app), then `ring encrypt -i secrets.txt -o secrets.enc --key my-key` / `ring decrypt` without the device; AES-256-GCM; password via `WALLET_PASS` env; encrypt/decrypt need network access to restore the Ledger Sync trustchain; password unrecoverable.
- Agent Intent (VERIFIED, https://developers.ledger.com/docs/ai-tools/agent-intent): beta. `wallet-cli agent-intent enroll --app-url https://agent-intent.ledger-test.com/`. Agent signs an intent with its own key pair, user reviews in the web portal and approves on the signer with Clear Signing. Send only; swap/Solana in development. Browser must expose WebHID/WebBLE (Chrome/Edge/Brave). Supports Nano S Plus, Nano X, Flex, Stax, Nano Gen5.

Relevance: the voice agent could run the CLI (`wallet-cli send --output json`) instead of DMK. Downsides for this idea: WSL recommended on Windows (friction), and the CLI's `send` collapses "build tx" and "sign" into one shell command, so you lose the browser-side `requiredUserInteraction` states that make the voice UX feel alive. Use DMK in-browser for the demo; mention CLI/Key Ring as the policy-store encryption layer.

---

## 3. Speech-to-text options

| Option | Runs where | Cost | Realtime? | Windows/Chromium notes | Tag |
|---|---|---|---|---|---|
| Web Speech API `SpeechRecognition` | browser; Chrome sends audio to Google unless `processLocally` | free | yes (interim results) | Chrome 135+ desktop ships **on-device** recognition on Windows/Mac/Linux, ~60 MB language pack, `SpeechRecognition.available()` / `install()`; still exposed as `webkitSpeechRecognition`; Firefox behind flag; Safari prefixed | VERIFIED (MDN, Chromium intent-to-ship) |
| OpenAI Realtime, transcription session | cloud, WebRTC from browser | `gpt-live-transcribe` $0.017/min; `gpt-4o-mini-transcribe` $0.003/min est. | yes | `type: "transcription"`, `gpt-live-transcribe` has no server VAD (do client-side VAD + commit) | VERIFIED (OpenAI docs/pricing) |
| Deepgram Nova-3 streaming | cloud WebSocket | $0.0048/min promo (regular ~$0.0077), **$200 free credit, no card** | yes | `@deepgram/sdk`, `deepgram.listen.v1.connect({model:"nova-3"})` | VERIFIED (deepgram.com/pricing, docs) |
| Whisper in browser (Transformers.js) | browser WebGPU/WASM | free | pseudo (chunked) | `realtime-whisper-webgpu` example uses `onnx-community/whisper-base`, encoder fp32 / decoder q4, device `webgpu`, `max_new_tokens 64`; ~200 MB download | VERIFIED (worker.js in huggingface/transformers.js-examples) |
| whisper.cpp / faster-whisper | local server | free | near | Python/CTranslate2, server-side only, not browser | INFERRED (third-party) |

Web Speech snippet (VERIFIED, MDN https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition):

```js
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const rec = new SR();
rec.lang = "en-US"; rec.interimResults = true; rec.continuous = false;
// rec.processLocally = true;  // Chrome 135+ desktop, after SpeechRecognition.install({langs:["en-US"]})
rec.onresult = (e) => console.log(e.results[0][0].transcript);
button.onclick = () => rec.start();   // needs a user gesture
```

Lazy verdict: for a 3-day demo, Web Speech is free and already on the machine. Its weakness is turn-taking (no barge-in, no VAD polish). If you want a conversational feel, go straight to the OpenAI Realtime speech-to-speech path below, which removes the STT/TTS plumbing entirely.

---

## 4. Voice agent platforms

### 4.1 OpenAI Realtime via Agents SDK (recommended)

VERIFIED (https://openai.github.io/openai-agents-js/guides/voice-agents/build/, https://developers.openai.com/docs/guides/realtime-webrtc, https://openai.github.io/openai-agents-js/guides/human-in-the-loop/):

Server mints an ephemeral client secret (never ship the API key to the browser):

```js
app.get("/token", async (req, res) => {
  const r = await fetch("https://api.openai.com/v1/realtime/client_secrets", {
    method: "POST",
    headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}`, "Content-Type": "application/json",
               "OpenAI-Safety-Identifier": "hashed-user-id" },
    body: JSON.stringify({ session: { type: "realtime", model: "gpt-realtime-2.1", audio: { output: { voice: "marin" } } } }),
  });
  res.json(await r.json());   // { value: "ek_..." }
});
```

Browser agent with an approval-gated tool:

```ts
import { RealtimeAgent, RealtimeSession, tool } from "@openai/agents/realtime";
import { z } from "zod";

const sendEth = tool({
  name: "send_eth",
  description: "Send ETH to a contact or address.",
  parameters: z.object({ to: z.string(), amountEth: z.string() }),
  needsApproval: true,                       // agent emits tool_approval_requested before executing
  async execute({ to, amountEth }) {
    return await buildSignBroadcastWithLedger(to, amountEth);   // DMK path from section 2
  },
});

const agent = new RealtimeAgent({ name: "Wallet", instructions: "...", tools: [sendEth] });
const session = new RealtimeSession(agent, { model: "gpt-realtime-2.1" });

session.on("tool_approval_requested", async (_ctx, _agent, request) => {
  const ok = await faceGate();             // section 6: WebAuthn or webcam liveness+match
  ok ? session.approve(request.approvalItem)
     : session.reject(request.approvalItem, { message: "Identity check failed." });
});

await session.connect({ apiKey: async () => (await (await fetch("/token")).json()).value });
```

- Transport: `OpenAIRealtimeWebRTC` (default in browser, handles mic + playback) or `OpenAIRealtimeWebSocket` (you handle audio). WebRTC recommended for browsers.
- `needsApproval` may be a boolean or `async (ctx, args) => boolean` (e.g. only above a threshold amount). `{ alwaysApprove: true }` available.
- Output guardrails (`RealtimeOutputGuardrail`) can veto the agent's spoken text; useful to stop it from reading out a private key or hallucinated address.
- Raw data-channel function calling (if you skip the SDK): `session.update` with `tools`, read `response.done` → `output[].type === "function_call"` (`call_id`, `arguments` JSON string), reply with `conversation.item.create {type:"function_call_output", call_id, output}` then `response.create` (VERIFIED, realtime-conversations guide).

Models and prices on 2026-10-10 (VERIFIED, https://developers.openai.com/docs/pricing and /docs/models): `gpt-realtime-2.1` audio $32/M in, $64/M out; `gpt-realtime-2.1-mini` $10/M in, $20/M out; `gpt-live-1` flat $0.05/min; `gpt-realtime-mini` deprecated. Third-party estimates put full-fat realtime at roughly $0.18–0.24 per conversation minute (INFERRED). A day of demo rehearsal on `-mini` is pocket change.

### 4.2 Alternatives

- **ElevenLabs Agents** (VERIFIED, https://elevenlabs.io/docs/agents-platform/libraries/react, https://elevenlabs.io/pricing/agents): `@elevenlabs/react` `useConversation({ clientTools: { name: fn } })`, tool names configured in their dashboard, tool must be marked "blocking" to wait on the result. Free tier 15 minutes/month, 4 concurrent; $0.08/min overage; LLM billed separately. Good voices, but 15 free minutes will not survive a rehearsal day.
- **Vapi** (VERIFIED, https://docs.vapi.ai/quickstart/web, https://docs.vapi.ai/tools/client-side-websdk): `@vapi-ai/web`, `vapi.start(assistantId)`. Client-side tools fire `tool-calls` messages but **cannot return a result to the model**; you'd need a server webhook for the Ledger signature result. ~$0.05/min platform fee plus provider costs (INFERRED). Worse fit.
- **LiveKit Agents** (VERIFIED, https://docs.livekit.io/agents/): Python/Node agent process joining a WebRTC room; STT-LLM-TTS plugins; tool calls can be forwarded to the frontend. Windows support is undocumented and community threads show Python path/version pain (INFERRED). Too much infrastructure for 3 days.
- **Deepgram Voice Agent API** $0.075/min (VERIFIED pricing page). Not evaluated further.

### 4.3 Text-to-speech

- Browser `speechSynthesis`: free, zero setup, robotic (INFERRED on quality).
- OpenAI `gpt-4o-mini-tts` $0.60/M text in, $12/M audio out; `tts-1` $15/M chars (VERIFIED pricing).
- Deepgram Aura-2 $0.030 per 1k chars (VERIFIED).
- In-browser Kokoro-82M via `kokoro-js` (Apache-2.0, WebGPU/WASM). npm page returned 403 to the fetcher; repo confirms model and licence (VERIFIED licence, INFERRED JS package details).
- If you use Realtime speech-to-speech you need none of these.

---

## 5. Existing "voice wallet" projects (prior art)

All VERIFIED from their showcase pages unless noted.

| Project | Where | Stack | Signing/authorisation | Hardware signer? |
|---|---|---|---|---|
| Speaky | ETHGlobal New Delhi, https://ethglobal.com/showcase/speaky-vdd3b, repo https://github.com/frankdierolf/speaky | OpenAI Realtime over WebRTC, Nuxt 4, ethers.js | MetaMask popup | no |
| Vane | ETHGlobal Trifecta, https://ethglobal.com/showcase/vane-2v96c, repo https://github.com/acgodson/vane | Alexa skill, Lambda, Privy server wallets, Covalent AgentKit | Privy "deny-all for value > 0" unless recipient whitelisted | no |
| LightWallet | ETHGlobal New York, https://ethglobal.com/showcase/lightwallet-e2ici | voice commands for visually impaired users | not stated | no |
| VoiceVault | lablab.ai, https://lablab.ai/submissions/b0cnjqu41oqdf613oagnzgen | OpenAI Agents SDK multi-agent, Circle wallets on Arc | Circle programmable wallets | no |
| EthTalk | ETHGlobal Bangkok, https://ethglobal.com/showcase/ethtalk-a0p87 | OMI necklace, Coinbase CDP SDK, Base Sepolia | CDP server wallet | no |
| Voice to Web3 | Devfolio, https://devfolio.co/projects/voice-to-web-53a6 | Whisper + LangChain + CDP | CDP | no |
| Irada | ETHOnline 2023, https://ethglobal.com/showcase/irada-kiyxt | Siri/Alexa/Google Assistant concept, Web3Auth | unfinished | no |
| Siri Chain | ETHGlobal Bangkok, https://ethglobal.com/showcase/chain-wdgqp | Apple AppIntents shortcuts | not stated | no |
| My Precious Web3 Voice Wallet for Alexa | ETHGlobal, https://ethglobal.com/showcase/my-precious-web3-voice-wallet-for-alexa-qkbpz | Alexa | not stated | no |
| SOLA AI | Trezor partner page, https://trezor.io/de/coins/wallet/sola-ai | Solana voice intents | software wallet | no |

Observations:
- The only project with a real authorisation idea is Vane: policy (whitelist) at the agent layer. Nobody has combined voice intent with a hardware clear-signing screen. INFERRED: "voice + Ledger" is unclaimed in the ETHGlobal/Devfolio/lablab corpus this search reached; no Ledger prize track existed at ETHOnline 2025 (VERIFIED, prizes page lists 14 sponsors, no Ledger).
- VoiceVault used Circle wallets; juror Drake Breeding is Circle's ecosystem director. A USDC-on-testnet transfer as the demo asset is a cheap nod (INFERRED tactical note).
- LightWallet's accessibility angle is a genuine "real user value" story, but see 7.4 for the tension with the Secure Screen.

---

## 6. The face-scan component

### 6.1 Option A: WebAuthn with a platform authenticator (Windows Hello / Face ID)

What it is: `navigator.credentials.get({ publicKey: { challenge, userVerification: "required", rpId } })` prompts Windows Hello; the returned assertion carries authenticatorData with the UV flag and a signature over `authenticatorData || SHA-256(clientDataJSON)` (VERIFIED flags, MDN; INFERRED exact signature formula from spec knowledge, spec body too long to fetch).

Facts (all VERIFIED unless marked):
- Windows Hello is the platform authenticator on Windows 10/11; Chrome/Edge route through the Win32 WebAuthn API and show the Windows dialog (https://learn.microsoft.com/en-us/windows/security/identity-protection/hello-for-business/webauthn-apis, https://passkeys.dev/docs/reference/windows/).
- Windows Hello **face requires a near-IR camera**; it is spoof-resistant against photos/LCD replays because IR does not show in them; FAR < 1/100,000 (https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/windows-hello-face-authentication).
- Since Windows 11 22H2 a PIN is mandatory; biometrics optional. **If no biometrics are enrolled or available, Windows silently falls back to PIN and still returns UV=true.** In Chrome 120+ `required` and `preferred` behave the same here (passkeys.dev Windows page).
- The relying party **cannot learn the modality**. The `uvm` extension exists in the IANA registry but is not listed on MDN and no evidence of Chrome/Windows support was found (INFERRED: unsupported). `txAuthSimple` (display RP text during auth) was removed in WebAuthn L2 because browsers refused to render RP text; a 2024 "transaction confirmation" revival (w3c/webauthn PR #2020) has not shipped (VERIFIED from WG mail archive; status INFERRED).
- `prf` extension (derive a secret from the credential) now works with Windows Hello on 25H2 and Chrome 147 added PRF-on-create for Windows per Corbado/Bitwarden community reports (INFERRED, third-party). Use case: decrypt the contact book/policy only after the face/PIN check. Nice, not essential.
- **Secure Payment Confirmation** is the one standard that does bind payee + amount + instrument into a platform-authenticator signature and shows them in browser UI (VERIFIED, https://www.w3.org/TR/secure-payment-confirmation/). But: credential must be created with `payment: { isPayment: true }`, flow must go through `PaymentRequest` with `supportedMethods: "secure-payment-confirmation"`, and Chrome's own June 2025 demos were Android-only with desktop "soon"; March 2026 WG minutes still do not confirm Windows desktop (VERIFIED minutes; desktop status INFERRED as not shipped). The Chrome developer page claiming macOS/Windows support is dated 2022 and contradicts the 2025 demo page. Do not bet the demo on SPC.
- iPhone Safari Face ID: works as a platform authenticator, same opacity (face vs passcode indistinguishable to the RP). Not relevant unless you build a mobile front end (INFERRED).

Verdict: honest, fast, strong against spoofing, but it is a **"this Windows user unlocked"** signal, not a face signal, and it cannot bind transaction content. 20 lines of code.

### 6.2 Option B: webcam face recognition in the browser

- `@vladmandic/human` (VERIFIED, https://github.com/vladmandic/human, wiki/Models, wiki/Embedding, demo/faceid): BlazeFace detector, 468-pt mesh, iris, HSE FaceRes description → `result.face[i].embedding` is a **1024-float** vector; `human.match.similarity(a,b)` (Euclidean by default), `human.match.find(emb, db)`; "similarity above 50% can be considered a match". Optional `config.face.antispoof.enabled` → `result.face[0].real` and `config.face.liveness.enabled` → `result.face[0].live`; both models < 1 MB, trained on low-res data, presented by the author as "quick checks alongside other indicators". The `demo/faceid` already does: single-person check, face size, gaze direction, detection scores, **blink detection with temporal speed check**, optional antispoof/liveness, and stores descriptors in IndexedDB. Backends WebGPU/WebGL/WASM; Node 14–22. Author recommends WebGL. `npm i @vladmandic/human` or CDN `https://cdn.jsdelivr.net/npm/@vladmandic/human/dist/human.js`.
- `face-api.js` (`@vladmandic/face-api`): archived 2025-02-05, superseded by Human (VERIFIED). Skip.
- MediaPipe `@mediapipe/tasks-vision` FaceLandmarker (VERIFIED, https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js): 478 landmarks + 52 ARKit-style blendshapes incl. `eyeBlinkLeft`/`eyeBlinkRight` (VERIFIED enum `EYE_BLINK_LEFT/RIGHT` in MediaPipe Python source; camelCase output INFERRED). No recognition embedding, so you'd pair it with another model. Only worth it for blink/head-turn challenge-response.
- InsightFace / ArcFace (VERIFIED, https://github.com/deepinsight/insightface): Python, ONNX Runtime; code MIT but **models non-commercial** and buffalo_l now "contact the company for licensing". Server-side only. Overkill and licence-awkward for a hackathon.
- Passive anti-spoof in JS: FaceX (WASM, Apache-2.0), Faceplugin JS (MIT, ONNX Runtime Web), sssxyd/face-liveness-detector (human.js + opencv.js) exist (INFERRED from search; not read).

Verdict: Human gives recognition + blink + antispoof + liveness in one dependency with a ready-made demo to crib from. It is not a security control; a printed photo plus a video on a phone defeats most of it, and the author says as much implicitly. It *is* good enough for "who is speaking" personalisation and as a replay/TTS-clone deterrent.

### 6.3 Option C: voice biometrics instead of face

ECAPA-TDNN ONNX exports exist (~83 MB, Apache-2.0) and sherpa-onnx has speaker verification, but no ready-made browser JS library was found (INFERRED). Not for 3 days.

### 6.4 Option D: the Ledger itself as the WebAuthn authenticator

The Flex with the Security Key app is a FIDO2 roaming authenticator over USB (VERIFIED, 2.6). Your web app can `navigator.credentials.get({ publicKey: { ..., allowCredentials: [...], }})` with `authenticatorAttachment: "cross-platform"` at registration and the Flex answers. That is "device-backed identity" using the same device that signs, and it directly fits Ledger's brief line "Device as a security key". Gaps: must verify the Flex returns UV (PIN unlock) and whether USB WebAuthn works while the DMK holds the HID interface (likely conflict: DMK talks to the Ethereum app, Security Key is a different app; you'd switch apps). INFERRED and risky; prototype only if time remains.

---

## 7. Trust model, honestly

### 7.1 What the Ledger press already gives you

The private key never leaves the Secure Element. The device renders the transaction (clear-signed) on its own screen and signs only what the human approves by pressing/tapping. Nothing the browser does, including a face check, changes the bytes that get signed or who can press the button. Software in the browser is exactly the thing Ledger's threat model assumes compromised (HACKATHON.md: "in hardware rather than in software that can be rewritten remotely").

So: **a browser face check adds zero cryptographic assurance to the signature.** Say this out loud in the pitch; the jury will respect it.

### 7.2 What a face/biometric step can genuinely add

1. **Speaker identification → policy selection.** A shared household/office laptop with one Ledger and several enrolled faces. The voice agent uses face match to pick *whose* contact book, *which* account path (`44'/60'/0'/0/N`), and *which* spending rules apply, before it ever constructs a tx. This is Ledger's "policy-based spending for autonomous systems" and the "clear boundary" between what the agent does alone and what the human approves: the agent may *draft* within policy; only the Secure Screen press *authorises*. This is the strongest, most honest use.
2. **Liveness gate against spoofed voice.** Voice is the weakest link: TTS clones and replays are cheap. Requiring an eyes-blink/head-turn liveness check at the moment a spend tool is called means a recording of your voice does not reach the device. The device press would also stop it, but only if the attacker is not physically present; the liveness gate stops a remote/accidental trigger from even producing an on-device prompt (prompt fatigue is itself a risk: users who see too many Secure Screen prompts start approving without reading).
3. **Multi-party approval at policy level.** Two enrolled faces must be seen (sequentially) before the agent will build a tx above X. Still single-signer on-chain, so frame it as policy, not multisig.
4. **Attributability.** Store (locally, Key-Ring-encrypted) a log "face id 2 asked for 0.5 ETH to Alice at 14:03, device approved at 14:04". The brief likes "a decision that has to be attributable later".

### 7.3 What face does NOT add (do not claim it)

- Not a second factor for the signature. The device PIN is already the "who" factor for the device.
- WebAuthn UV cannot prove face was used (PIN fallback is indistinguishable).
- Webcam recognition is not anti-spoof grade; Human's own models are "quick checks".
- A browser cannot display tamper-proof transaction text; only the Secure Screen can. Do not let the agent's spoken read-back be the thing users rely on.

### 7.4 A tension worth naming

Voice-first UX serves blind and low-vision users (LightWallet's thesis), but the Ledger security property depends on *reading* the Secure Screen. The Flex has no audio. If the agent reads the on-device content aloud, a compromised agent can lie. Honest mitigation for the pitch: the agent speaks the tx *before* sending it to the device, the user confirms verbally, and the device shows the same thing; for sighted users the screen is the final word, for blind users this is a known gap that Ledger's hardware would need to close (speech out from the Secure Element). Mention it as a "new use case for Ledger" (10% of the score).

---

## 8. 3-day build constraints (Windows + these two devices)

- Browser: **Chromium only** (WebHID, Web Bluetooth). Edge or Chrome on Windows 11. Firefox/Safari out.
- Serve on `localhost` or HTTPS; discovery and `getUserMedia` and WebAuthn all need a user gesture / secure context.
- Nano S Plus: USB only, two buttons, small screen; fine for the Ethereum app and shows full addresses with scrolling (INFERRED). Flex: USB or BLE, touch E Ink; nicer demo screen. NFC unusable for us.
- Windows Hello face needs an IR camera; **unknown whether the host laptop has one** (the memory notes a Legion 83DG; many Legion models lack IR). If not, Windows Hello falls back to PIN/fingerprint silently and the "face" story in Option A collapses. Check `Settings > Accounts > Sign-in options` on day 1. Webcam Option B works with any camera.
- API keys stay on a tiny Node/Express token server (`/token` ephemeral secret). Vite dev server + one Express file is enough.
- Budget: Realtime `-mini` is ~$10/M audio-in tokens; Deepgram gives $200 free; ElevenLabs free tier is 15 minutes total. Web Speech is free.
- Only two Ledger apps relevant: Ethereum (for DMK signing) and optionally Security Key (Flex). Switching apps mid-demo costs time; pick one per device.
- Everything in the Ledger AI-tools pages is labelled early/experimental with breaking changes; pin versions on day 1 and do not `npm update` on day 3.
- DMK Skills for coding agents: `npx skills add ledgerhq/agent-skills -s ledger-dmk-implementation dmk-intent-vocabulary dmk-business-logic` (VERIFIED). Install into Claude Code/Cursor to speed up the DMK glue; the Ledger docs explicitly promote this and the required DX write-up can report how well it worked.

---

## 9. Strongest version of the idea

**Name:** something like "Hearsay" / "Say & Sign" (placeholder).

**One-liner:** A voice agent that can *draft* payments but never *authorise* them: your face picks the policy, your voice states the intent, your Ledger signs the truth.

**Flow (demo script, ~90 s):**
1. Page open in Chrome. "Connect Ledger" button → WebHID → Ethereum app opens → `getAddress(checkOnDevice:true)` once (address shown on device, agent says "Account verified on device").
2. User says: "Send Alice twenty dollars of USDC." Realtime agent resolves "Alice" from the user's encrypted contact book (Key-Ring-decrypted at session start, or WebAuthn-PRF-gated) and calls `send_token` with `needsApproval: true`.
3. `tool_approval_requested` → camera widget: Human runs single-face, blink, antispoof/liveness, 1024-d match against enrolled faces. Agent: "I see Sahas. Your policy allows up to $50/day to saved contacts. Sending 20 USDC to Alice, 0x1234…abcd, fee about $0.01. Check your Ledger."
4. If a *different* enrolled face is present (teammate), the agent loads *their* policy instead; if unenrolled or no liveness, it rejects and says why.
5. Signer kit `signTransaction` → state `SignTransaction` → Flex shows amount/recipient (clear-signed ERC-20 transfer on Sepolia or Base Sepolia) → tap approve → `{r,s,v}` → broadcast → agent speaks the tx hash link.
6. Local attributable log line written, encrypted with `wallet-cli ring encrypt` (or shown as the file the agent cannot read without the Ledger-derived key).

**Explicit boundary slide:** Agent autonomously: listen, parse, resolve contacts, check policy, build calldata, simulate, speak. Human: identity (face/Hello), consent (voice "yes"), **authority (Ledger press on Secure Screen)**. Nothing moves without step 3 of that list; the first two are UX, not security, and you say so.

**Why Ledger primitives are "implemented, not mentioned":** DMK + WebHID + signer-kit-ethereum with the `requiredUserInteraction` state machine driving the agent's speech; Key Ring (or Agent Intent if you want the remote-agent variant) as the second primitive. Clear signing is what makes "the device shows the truth" true.

**Stretch (only if day 2 is clean):** replace Windows Hello with the Flex Security Key app as the WebAuthn login (same device for identity and authority); or expose the agent as a remote Agent Intent proposer so a phone-side voice note creates a queued intent approved later on the Flex.

**Pitch risk to pre-empt:** "Why not just press the button?" Answer: the button protects the key; the face+policy layer protects the *human's attention*. It decides which prompts ever reach the Secure Screen, who they are for, and what the agent is allowed to draft. That is the agent-safety problem Ledger's own brief is asking about.

---

## 10. Contradictions and gaps found

- Chrome developer SPC page (2022) says desktop macOS/Windows supported; Chrome's June 2025 demo page says desktop "soon"; March 2026 WG minutes still silent. Treat SPC desktop as unavailable.
- DMK README `connect` example is syntactically broken; parameter name differs across pages.
- Ledger Security Key help article unreadable by the fetcher; UV behaviour and resident-key support for the Flex unverified; Nano S Plus support unverified (press says Stax/Flex).
- OpenAI voice-agents overview page names a `gpt-6-astra` chained model while the pricing/models pages list `gpt-realtime-2.1`, `gpt-live-1`, etc.; use the models page as truth and check the account's model access on day 1.
- Realtime per-minute cost figures are third-party; per-token prices are official.
- ElevenLabs pages show Starter price inconsistently ($6 vs $1 first month).
- MediaPipe blendshape PDF model card is binary; names inferred from the Python enum.
- No source confirms Chrome Web Bluetooth pairing steps for Flex on Windows.
- Whether `originToken` is required for *any* signer-kit usage vs only Transaction Checks: docs say only checks are affected. Confirm by trying without it.

## 11. Open questions for day 1 (hardware/tooling, not researchable online)

1. Does the host laptop have a Windows Hello IR camera? (Decides Option A viability as a *face* story.)
2. Does Chrome on this Windows 11 build see the Nano S Plus and Flex over WebHID without Ledger Live running? (Ledger Live may hold the HID interface.)
3. Does the Ethereum app clear-sign a USDC transfer on Sepolia/Base Sepolia on the Flex firmware you have, or does it blind-sign?
4. Which `gpt-realtime-*` models does the OpenAI account have access to; is `gpt-realtime-2.1-mini` enough for tool calls?
5. Can WSL-less Windows run `wallet-cli ring init` natively (doc says WSL recommended)? If not, Key Ring becomes a recorded side-demo.
6. Does the Flex Security Key app coexist with the Ethereum app in one demo without reconnects?
7. Can a mentor issue an `originToken` for Transaction Checks within the week?

---

## 12. Sources

Ledger
- https://developers.ledger.com/docs/ai-tools/overview
- https://developers.ledger.com/docs/ai-tools/ledger-dmk-skills
- https://developers.ledger.com/docs/ai-tools/ledger-cli (incl. #key-ring)
- https://developers.ledger.com/docs/ai-tools/agent-intent
- https://developers.ledger.com/docs/ai-tools/hardware-security/security-key
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/how_to_use_a_signer
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/dmk
- https://developers.ledger.com/docs/device-interaction/integration/how_to/transports.md
- https://developers.ledger.com/docs/device-interaction/beginner/ble_flex_stax.md
- https://developers.ledger.com/docs/clear-signing/overview
- https://developers.ledger.com/pdf/dmk-one-pager.pdf (via search snippet)
- https://github.com/LedgerHQ/device-sdk-ts
- https://github.com/LedgerHQ/device-sdk-ts/blob/develop/packages/device-management-kit/README.md
- https://github.com/LedgerHQ/device-sdk-ts/blob/develop/packages/signer/signer-eth/README.md
- https://www.businesswire.com/news/home/20240726882083/en/Introducing-LEDGER-FLEX-Easy-Secure-Self-Custody-Free-From-Compromise
- https://ethglobal.com/events/newyork2026/prizes/ledger
- https://ethglobal.com/events/ethonline2025/prizes
- https://support.ledger.com/article/12350325732893-zd (fetch returned no content)

Speech / voice agents
- https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition
- https://groups.google.com/a/chromium.org/g/blink-dev/c/VNOok2dbmHM/m/TQpe9shjCgAJ
- https://developers.openai.com/docs/guides/realtime-webrtc
- https://developers.openai.com/docs/guides/realtime-conversations
- https://developers.openai.com/docs/guides/realtime-transcription
- https://developers.openai.com/docs/guides/voice-agents
- https://developers.openai.com/docs/pricing
- https://developers.openai.com/docs/models
- https://openai.github.io/openai-agents-js/guides/voice-agents/build/
- https://openai.github.io/openai-agents-js/guides/human-in-the-loop/
- https://elevenlabs.io/docs/agents-platform/overview
- https://elevenlabs.io/docs/agents-platform/libraries/react
- https://elevenlabs.io/pricing/agents
- https://docs.vapi.ai/quickstart/web
- https://docs.vapi.ai/tools/client-side-websdk
- https://docs.livekit.io/agents/
- https://developers.deepgram.com/docs/live-streaming-audio
- https://deepgram.com/pricing
- https://github.com/xenova/whisper-web
- https://github.com/huggingface/transformers.js-examples
- https://raw.githubusercontent.com/huggingface/transformers.js-examples/main/realtime-whisper-webgpu/src/worker.js
- https://github.com/hexgrad/kokoro
- https://www.npmjs.com/package/kokoro-js (403)

WebAuthn / Windows Hello / SPC
- https://learn.microsoft.com/en-us/windows/security/identity-protection/hello-for-business/webauthn-apis
- https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/windows-hello-face-authentication
- https://passkeys.dev/docs/reference/windows/
- https://chromium.googlesource.com/chromium/src/+/404ca6f/content/browser/webauth/uv_preferred.md
- https://developer.mozilla.org/en-US/docs/Web/API/Web_Authentication_API/Authenticator_data
- https://developer.mozilla.org/en-US/docs/Web/API/Web_Authentication_API/WebAuthn_extensions
- https://www.w3.org/TR/webauthn-3/ (partial read)
- https://www.iana.org/assignments/webauthn/webauthn.xhtml
- https://github.com/w3c/webauthn/issues/1386 and https://github.com/w3c/webauthn/pull/2020 (via W3C mail archive)
- https://www.w3.org/TR/secure-payment-confirmation/
- https://developer.chrome.com/docs/payments/secure-payment-confirmation
- https://www.w3.org/2025/06/chrome-spc-demos.html
- https://www.w3.org/2026/03/26-wpwg-minutes.html
- https://www.corbado.com/blog/passkeys-prf-webauthn and https://community.bitwarden.com/t/encryption-prf-via-windows-hello-passkey/94236 (third-party PRF status)

Face / liveness
- https://github.com/vladmandic/human
- https://github.com/vladmandic/human/wiki/Models
- https://github.com/vladmandic/human/wiki/Embedding
- https://github.com/vladmandic/human/tree/main/demo/faceid
- https://github.com/vladmandic/face-api (archived)
- https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js
- https://huggingface.co/spaces/learnmlf/FollowYourEmoji/blob/main/media_pipe/face_landmark.py (blendshape enum)
- https://github.com/deepinsight/insightface
- https://huggingface.co/astrolabos/ecapa-tdnn (speaker embedding ONNX)

Prior art
- https://ethglobal.com/showcase/speaky-vdd3b and https://github.com/frankdierolf/speaky
- https://ethglobal.com/showcase/vane-2v96c and https://github.com/acgodson/vane
- https://ethglobal.com/showcase/lightwallet-e2ici
- https://lablab.ai/submissions/b0cnjqu41oqdf613oagnzgen
- https://ethglobal.com/showcase/ethtalk-a0p87
- https://devfolio.co/projects/voice-to-web-53a6
- https://ethglobal.com/showcase/irada-kiyxt
- https://ethglobal.com/showcase/chain-wdgqp
- https://ethglobal.com/showcase/my-precious-web3-voice-wallet-for-alexa-qkbpz
- https://trezor.io/de/coins/wallet/sola-ai
