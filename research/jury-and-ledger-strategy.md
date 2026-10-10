# Jury & Ledger strategic direction — how to aim the project

Research note for the N3XT Hackathon @ OP3N 2026. Written 2026-10-10 from web sources only (no hardware touched, nothing installed). Every fact is tagged **VERIFIED** (read in a primary source: Ledger/Circle/Venice docs or blog, the person's own post or repo) or **INFERRED** (secondary press, or my reading of a primary source). Blunt about gaps.

Rubric reminder (from HACKATHON.md): Technical execution 25 · Usefulness/relevance for Ledger 20 · Innovation 20 · UX 15 · New use cases for Ledger 10 · Clarity/docs 10. Four jurors, 5-min pitch + 5-min Q&A.

---

## 0. TL;DR

- All four jurors are, in different vocabularies, selling the same sentence: **"Agents propose. Humans approve. Hardware enforces."** (Ledger, VERIFIED) / **"Agents propose. Humans sign. Your Ledger enforces."** (Rogers' own blog, VERIFIED). Build that sentence into something concrete and name the boundary out loud.
- Ledger's 2026 roadmap is **Identity (Q2) → Intents + Policies (Q3) → Proof of Human (Q4)** (VERIFIED, Ledger blog 2026-04-14). The Q3 "Agent Policies" item (daily cap, contract allowlist, enforced in hardware, out-of-policy routes back to the human) is **not shipped**; the Agent Intent product is in **beta, send-only** (VERIFIED, docs). Anything that prototypes "policy" or "intent" ahead of Ledger's own release is squarely on-roadmap and will be read as relevant.
- Ledger has already told us what it praised in the June 2026 student Build & Show: rigor (policy engine + tests + hash-chained audit log + prompt-injection demo), originality of interface (Ledger inside Telegram), refusing blind signing (ERC-7730/Clear Signing), mandates with caps. (VERIFIED, Ledger blog 2026-06-23.) And at ETHGlobal NYC: "Real user value, not generic chatbot wrappers. Clear boundaries between autonomous behavior and explicit approval. Concrete use of Ledger primitives, not just wallet branding. Practical demos that show why device-backed trust matters for AI." (VERIFIED, ethglobal.com.)
- The two non-Ledger jurors want: **Venice** = private inference, OpenAI-compatible API, x402 pay-per-request with a wallet instead of an API key (VERIFIED); **Circle** = USDC as the agent money, x402 + Gateway Nanopayments, Arc (USDC-as-gas L1, sub-second finality, mainnet since 2026-09-16), Agent Wallets with spending policies (VERIFIED).
- The natural intersection of all four: **an agent that pays for something (Venice inference, an x402 API, a supplier) in USDC, where the Ledger device is the hard stop on money movement and the agent's own identity is hardware-provisioned**. Rogers/Mathias/Hébrard literally built this for Circle's hackathon in Feb 2026 (VERIFIED, repo + podcast). That is both a signal (it's what they care about) and a trap (don't re-build their demo; see §9).

---

## 1. Jury at a glance

| Juror | Role (as the brief states) | Verified current title | What they will reward (INFERRED from their own words/work) |
|---|---|---|---|
| Ian Rogers | Chief Human Agency Officer, Ledger | Same; appointed 2026-04-14/15, previously CXO since Dec 2020 (VERIFIED) | A product with a *point of view* on human agency; a nameable autonomy/approval boundary; audit trail; "don't give agents secrets" done concretely; taste and story ("front of the box for the heart, back for the head") |
| Guillaume Mathias | VP Product, Ledger | X bio says VP Product; Ledger podcast says "VP of Product & Head of Product" (VERIFIED, titles vary) | Product that resolves "safety vs effortless use"; AI-native building blocks (agent finds what it needs fast); hardware as a stop point the agent "can't reason around"; shipped, scoped, working |
| Joshua Mo | DevRel Lead, Venice | "Lead DevRel Engineer, Venice.ai" since ~Apr 2026; ex-Shuttle DevRel, ex-Rig (Rust agent framework) lead (VERIFIED, his site) | Clean developer experience, tool-calling loops done right, MCP, Rust/TS craft; private inference used for a reason, not as a sticker; honest DX feedback (he *is* DevRel and the brief says DevRel reads the feedback first) |
| Drake Breeding | Director, Ecosystem Arc, Circle | "Ecosystem Director @Arc @Circle" (X); EthCC/ETHDenver list "Senior Manager, BD / Arc Ecosystem" (VERIFIED, titles vary) | USDC moving; x402 / Nanopayments; Arc testnet or mainnet actually used; agent commerce with safety; "At Circle, we're building for safety. We hope you do as well." |

---

## 2. Ian Rogers (Ledger) — what he has said and what he rewards

### Facts
- **VERIFIED** Appointed Ledger's first Chief Human Agency Officer, announced 2026-04-14 (Ledger blog) / reported 2026-04-15 (SecurityBrief, DL News, The Block). CXO since December 2020, ex-LVMH CDO, ex-Beats Music CEO, ex-Topspin, Yahoo Music, Nullsoft, Beastie Boys web. Worked with Tony Fadell on the Stax form factor. ([Dialectic profile](https://newsletter.dialectic.fm/p/ian-rogers), [Big Whale](https://www.thebigwhale.io/peoples/ian-rogers))
- **VERIFIED** Authored Ledger's "Securing Your Agents With A Hardware Root of Trust: Ledger's 2026 AI Security Roadmap" (2026-04-14). Frames the threat as the **"lethal trifecta": prompt injection + autonomous execution + access to real resources**. "An agent doesn't need to be the attacker": a poisoned page, document, or hijacked MCP response compromises it mid-task. Quotes Balaji: *"AI is middle-to-middle but humans are end-to-end."* Rogers: *"The solution is not to run away, it's to lean-in and use Ledger to keep humans secure and in-the-loop."* Oct 2025 stage remark: agentic futures where agents hold logins/credit cards/identities are *"a security nightmare."* ([roadmap post](https://www.ledger.com/blog-2026-ai-security-roadmap))
- **VERIFIED** Byline on the Agent Stack launch post (2026-06/07): *"Agents propose. Humans approve. Hardware enforces."* and *"A compromised agent can ask your signer to sign something. It cannot make your signer sign without you."* ([Agent Stack post](https://www.ledger.com/blog-preview-ledger-agent-stack))
- **VERIFIED (his own blog, fistfulayen.com)**
  - 2026-02-07 "Agent Payments with Ledger": hackathon submission to Circle's USDC/OpenClaw hackathon, *"not an official Ledger product."* Tagline *"Agents propose. Humans sign. Your Ledger enforces."* Components: standard USDC transfers via intent queue; x402 pay-per-call (agent gets 402 → intent → user signs EIP-3009 on Ledger → agent retries with payment header); **agent key provisioning via LKRP** (each agent gets its own identity, not funds; creation needs hardware approval; instant revoke); intent lifecycle pending→approved→authorized→executing→confirmed (+rejected/failed/expired); **every intent logged** (audit trail). "What this unlocks": agent commerce, pay-per-call APIs, creator payments, business ops, guarded DeFi.
  - 2026-03-20 SXSW talk: *"an agent is AI that can use tools"*; *"The second it can use tools, it has access to value."*; *"Future humans are orchestrators of agents."*; *"You cannot leave precious information with something non-deterministic and call that a plan."*; *"Humans become validators. But validation without security is nonsense."*; *"more need for deterministic guardrails around non-deterministic systems."*; *"Ledger hardware is fundamentally designed to protect information, not share it."*; *"What has not collapsed is the cost of trust."* Three open problems he names: (1) verify an agent really represents who it claims, (2) verify the user is really the person the agent acts for, (3) scope/protect/revoke/audit an agent's secrets. Permissions should scale with stakes (checking a flight ≠ moving money ≠ deleting files).
  - 2026-01-13 "Reflections on a Claude Code New Year": he builds personal projects with Claude Code. (He is a hands-on agent user, not a tourist.)
- **VERIFIED (Dialectic interview)** *"Prompt injection is a feature, not a bug… Don't handicap them. Let them be great at that. But don't give them secrets."* Every AI action approved by a human **or by a policy a human set**; approvals create *"an audit trail."* Less worried about AI becoming human than about *people treating it as human* and surrendering agency. Product philosophy: *"The front of the box is for the heart, the back of the box is for the head."* *"The goal is not to appeal to everyone; the goal is to appeal strongly."*
- **VERIFIED (press quotes, April 2026)** *"The biggest threats come from AI systems being granted too much access to sensitive credentials, wallets, and financial decision-making without human oversight."* (DL News) *"In 2025 people thought we were just paranoid. In 2026, this has become a consensus viewpoint."* *"My goal is to ensure humans stay in the loop through a hardware root of trust, for all important decisions."* (SecurityBrief/The Block). Gauthier on him: *"the right person to ensure that 'putting the human in the loop' is our guiding principle."*
- **INFERRED (BigGo summarising Bloomberg, Aug 2026)** On the Coldcard breach: not evidence self-custody is unsafe; firmware entropy bug; AI amplifies weak randomness and gives attackers better tooling. Compared agent permissions to **a parent deciding when a teenager gets the car keys: access depends on context.** (Secondary source; BeInCrypto original 403'd.)
- **VERIFIED** Proof of Human (Q4): hardware-based, *"links human attestation to the secure element inside a Ledger device"*, explicitly *not* biometric and *not* social reputation (contrast with World). *"We're not trying to prove the identity of the whole world."* (DL News)

### What Rogers rewards (INFERRED)
1. A **named boundary**. He will ask "what does the agent do alone, what needs me?" The answer should be a sentence, ideally a visible policy object.
2. **Audit trail.** He mentions it unprompted in two separate places.
3. **Secrets never in the agent.** Ring CLI / LKRP-provisioned agent identity hits his "don't give them secrets" line directly.
4. **A story a non-engineer gets in 30 seconds** (music/fashion/Apple background; "front of the box for the heart").
5. **Stakes-scaled permissions**, not all-or-nothing. His teenager/car-keys and flight-vs-money analogies are the pitch frame he already uses.
6. Will likely be allergic to: biometric-gating as "proof of human" (he positioned Ledger against it), agents holding hot keys "for convenience", and projects that treat the device as a yes-button.

---

## 3. Guillaume Mathias (Ledger) — what he has said and what he rewards

### Facts
- **VERIFIED** X bio: VP Product, Ledger. Ledger podcast page lists him "VP of Product & Head of Product". RocketReach says "EVP Product" (low-trust). Co-author (listed as "Ledger Engineer", @gm4thi4s) of the Feb 2026 hackathon repo with Philippe Hébrard and Ian Rogers. ([repo](https://github.com/brackets-fistfulayen/ledger-agent-intents))
- **VERIFIED (Ledger Podcast EP-113, "AI Agent With a Wallet. What Could Go Wrong?")** On delegation: *"If you trust it with everything, it's a recipe for disaster."* On the builder's role: *"In the past you were the builder. Now you're becoming the architect."* On x402: *"You're just sending a message and everything is settled. You're giving permission to your agents."* Says Ledger aims to make its building blocks **"AI-native"** so agents can quickly find what they need to build on the Ledger stack. Noted scope *grew* three times over the weekend because AI-assisted dev removed the pressure to cut. Hébrard on the same episode: HSMs should operate **at the policy layer**; hardware *"is giving the guardrails"* to agents. The episode's hook: an agent that *"over-optimizes, hits limits, and starts failing in public"* (it spammed Moltbook communities until rate-limited), hence the need for a physical pause. ([podcast page](https://www.ledger.com/the-ledger-podcast/ai-agent-with-a-wallet-what-could-go-wrong), [Ledger tweet](https://x.com/Ledger/status/2022303235126558956))
- **VERIFIED (his X, 2026-02-13)** *"how Ledger technologies can help secure the new Agentic world… As AI autonomy grows, human-in-the-loop security is more critical than ever."*
- **VERIFIED (his X, 2026-04-03, Ledger Wallet 4.0 thread)** *"Digital private property is a fundamental right—but it's always come with a catch. For too long, the industry forced a false choice: absolute safety or effortless use. A fortress, or a smooth experience. Never both. With Ledger Wallet 4.0, that tension ends."*
- **INFERRED** He is the product owner most likely behind Ledger Wallet (ex-Ledger Live), Wallet CLI, and the Agent Intent beta, but **no source names him as Agent Stack lead**. Treat as the person who owns the *product* questions: who is the user, what is the flow, where does it break.
- **VERIFIED** Other appearances: Investia podcast (FR, 2025-05-14, seed-phrase management / investor security); Source.paris × Bpifrance round table on design (2025-09-26, "design as a strategic lever, impact of AI on our professions").

### What Mathias rewards (INFERRED)
1. **Safety AND smoothness.** His Wallet 4.0 thesis is literally "no trade-off". A demo where the human approval step feels *effortless* (one glance, one press, clear-signed) scores with him; a demo with 4 confirmation modals does not.
2. **AI-native DX**: did the agent discover and use the Ledger tooling easily? Did we use the official skills (`npx skills add ledgerhq/agent-skills`, `wallet-cli skill install`)? He will read the DX feedback.
3. **Hardware as policy layer**, not just signer. Hébrard's framing on his podcast.
4. **Scoped and shipped.** He admitted scope creep; a team that cut scope and shipped will look mature.
5. Product questions in Q&A: "who is this for", "what happens when the agent is wrong", "how do you revoke".

---

## 4. Joshua Mo (Venice) — what Venice offers and what he rewards

### Facts about him
- **VERIFIED (joshmo.ooo)** Lead DevRel Engineer at Venice.ai ("private AI model platform"). Timeline: DevRel at shuttle.dev Feb 2023–Feb 2025; Rig project lead (0xplaygrounds/rig, Rust LLM/agent framework) at Playgrounds Analytics Jan 2025–Apr 2026; then Venice. Specialises in Rust; interested in AI/ML and WASM. Coaches at Codebar; helps run "AI Engine" builder events.
- **VERIFIED (dev.to/joshmo_dev)** 14 articles, almost all agent-tooling tutorials: MCP with Rig; "Taking Payments with AI Agents and Rig using Stripe's MCP server" (Apr 2025); "Automating onchain actions with AI using rig-onchain-kit" (Mar 2025); agent design patterns; RAG; local embeddings; "Rewriting Claude Code in Rust" (Mar 2026?).
- **VERIFIED (his GitHub)** `venice-terminal-agent`: Python 3.12 + uv, OpenAI SDK pointed at `https://api.venice.ai/api/v1`, resolves model at runtime via `GET /models/traits` trait `function_calling_default` (model IDs "rotate"), passes `venice_parameters`, converts MCP tool schemas → function tools, Apify MCP over Streamable HTTP. README insists you **echo the assistant `tool_calls` turn back unchanged, including `content: null` and any `reasoning_*` fields.** ([repo](https://github.com/joshua-mo-143/venice-terminal-agent))
- **INFERRED** He has built agents-that-pay (Stripe MCP) and agents-that-act-onchain before; he will understand an x402 flow instantly and will notice sloppy tool-calling loops.

### Facts about Venice (what we could use)
- **VERIFIED** OpenAI-compatible; base URL `https://api.venice.ai/api/v1`; chat at `/chat/completions`; Bearer `VENICE_API_KEY`. "100+" text models, "380+" across text/image/audio/video. Function calling, streaming, vision, embeddings, **TTS (50+ voices), transcription (STT), voice cloning, speech-to-speech**, image gen/edit, video. Example model IDs on docs: `zai-org-glm-5-1`, `kimi-k3`, `claude-fable-5`, `kimi-k2-5`. ([docs.venice.ai](https://docs.venice.ai/))
  ```bash
  curl https://api.venice.ai/api/v1/chat/completions \
    -H "Authorization: Bearer $VENICE_API_KEY" -H "Content-Type: application/json" \
    -d '{"model":"zai-org-glm-5-1","messages":[{"role":"user","content":"hello"}]}'
  ```
- **VERIFIED (privacy page)** Venice *"does not store or log prompt and response content for normal inference."* Operational metadata (account/wallet IDs, key IDs, timestamps, model, token counts, IP, device info) *is* logged. Model privacy labels: `anonymized` (provider sees prompt, not your identity) vs `private` (contract-enforced zero retention). Text-only `e2ee-*` models: **TEE with remote attestation** and **E2EE** (client encrypts, only the enclave decrypts; disables server-side web search/memory/some tool flows). Do **not** claim "all Venice traffic is private". ([privacy](https://docs.venice.ai/overview/privacy))
- **VERIFIED (pricing page)** Pay-per-use credits, USD card or crypto, never expire. **No free API tier** listed; Pro subscribers get a one-time $10 API credit. DIEM: 1 DIEM = $1/day of compute, refreshing daily (stake DIEM or VVV). ([pricing](https://docs.venice.ai/overview/pricing))
- **VERIFIED (x402 guide)** Call Venice **without an API key**: wallet signs SIWE (Base, chainId 8453, USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`) or Solana SIWX; header `X-Sign-In-With-X` (base64 JSON of address/message/signature/timestamp/chainId); prepay via `POST /api/v1/x402/top-up` (first call returns 402 with `accepts`; retry with `X-402-Payment` built by `x402/client` `createPaymentHeader`); then any inference route accepts `X-Sign-In-With-X`. `GET /x402/balance/{addr}` returns `minimumTopUpUsd` / `suggestedTopUpUsd` (examples use $5–$10). Official SDK `venice-x402-client`:
  ```ts
  import { VeniceClient } from 'venice-x402-client'
  const venice = new VeniceClient(process.env.WALLET_KEY)
  await venice.topUp(10)
  const r = await venice.chat({ model: 'kimi-k2-5', messages: [{ role: 'user', content: 'Hello!' }] })
  ```
  ([x402 guide](https://docs.venice.ai/guides/integrations/x402-venice-api.md))
- **VERIFIED (GeekWire, 2026)** Venice raised $65M at $1B valuation; led by Erik Voorhees (crypto) and Jesse Proudman; positioned as private and unrestricted alternative to mainstream AI. (Press, but on-record funding.)

### What Mo rewards (INFERRED)
1. **A correct tool-calling loop** and honest handling of model behaviour (his README is pedantic about it; he'll spot hand-waving).
2. **Privacy used for a reason**: e.g. the agent reasons over the user's portfolio/transaction history, so inference should be zero-retention (`private` model) or in a TEE; say which and why. Bonus: E2EE model for the "no secret ever leaves" story.
3. **x402 to Venice signed by the user's wallet**: the agent pays for its own thinking in USDC, and Ledger is where the money authority sits. This connects Venice ↔ Circle ↔ Ledger in one flow. (Caveat §8: Venice's x402 top-up is a signed EIP-3009 payment from an EVM key; routing *that* signature through a Ledger device is exactly what Rogers' repo did for a generic x402 API. Feasible but a real integration task.)
4. **Good DX write-up**: he is DevRel; the brief says DevRel reads the feedback section first. Blunt, specific, with screenshots.
5. Venice also gives us **STT/TTS in one privacy-respecting API**, which matters for the voice-agent idea.

---

## 5. Drake Breeding (Circle) — Arc, x402, what Circle wants

### Facts about him
- **VERIFIED** X bio "Ecosystem Director @Arc @Circle"; ETHDenver: "Senior Manager, Arc Ecosystem" / "Senior Manager of Business Development for Arc, Circle's Layer 1 blockchain"; ex-Figment (Protocol Strategy), ex-Coinbase (Partnerships), ex-Goldman electronic trading, Duke. EthCC[9] talk 2026-03-31 "Arc: Bringing the offchain onchain" — USDC as gas, sub-second finality, compliant privacy; payments/trading/RWAs onchain *"without splitting liquidity."* ([ETHDenver](https://ethdenver.com/speakers/drake-breeding/), [EthCC](https://ethcc.io/speakers/drake-breeding), [LinkedIn](https://www.linkedin.com/in/drake-breeding/))
- **INFERRED** He is a BD/ecosystem person, not an engineer: he will judge "does this bring real activity to Arc/USDC" and "is this a credible team", not code quality.

### Facts about Circle's agent story
- **VERIFIED (docs.arc.io)** Arc: Circle's chain for "onchain finance with stablecoins". **Mainnet live since 2026-09-16**; testnet too. **USDC is gas** (20 Gwei `maxFeePerGas` floor); **finality < 1 s**; EVM (Osaka baseline), *but*: **USDC has 18 decimals natively on Arc (not 6)**, system emitter logs all USDC Transfer events, blocklist reverts consume gas without receipt, sends to `address(0)` revert. Tooling: Arc Foundry (`arc-forge`, `arc-cast`, `arc-anvil`), faucet.circle.com, **Arc MCP server + llms.txt**, App Kits (Bridge/Swap/Unified Balance/Onramp/Earn/Borrow). "Agentic economy" is a listed use case. Arc testnet chain is `eip155:5042002` (from Circle's x402 walkthrough). Privacy: confidential transfers (amounts hidden, addresses visible, view keys for auditors; TEE-backed initially) — **INFERRED**, secondary sources only. ([docs.arc.io](https://docs.arc.io/))
- **VERIFIED (developers.circle.com/agent-stack)** Circle has its own **"Agent Stack"** (same name as Ledger's!): **Circle CLI**, **Agent Wallets** (user-controlled 2-of-2 MPC; "key shares never exposed to the agent"; **spending policies**: USDC limits per outbound transfer and x402, daily/monthly caps, recipient allowlists, contract blocklists; sanctions screening on every transfer; gas-sponsored), **Agent Nanopayments** (gasless, batched sub-cent USDC via Gateway for x402 services, down to $0.000001), **Agent Marketplace** (curated x402 services), **Circle Skills**, **Facilitator Service** (hosted x402 facilitator for sellers on **Arc, Base, Polygon PoS**), **Gateway Nanopayments**. Works with Claude Code, Cursor, Codex, OpenClaw. ([agent-stack](https://developers.circle.com/agent-stack), [agent wallets](https://developers.circle.com/agent-stack/agent-wallets), [nanopayments](https://developers.circle.com/agent-stack/agent-nanopayments))
- **VERIFIED (Circle blog "Turn your API into a storefront for agents")** Seller side: `createGatewayMiddleware` from `@circle-fin/x402-batching/server`, facilitator `https://gateway-api-testnet.circle.com`, network `eip155:5042002`, `gateway.require("$0.001")` on a route; test with `circle services pay --max-amount 0.001`; `circle gateway withdraw`. Circle's framing: agents should *"discover and evaluate a service, read the price, pay for access"*; disclaimer notes agent transactions *"may occur without real-time human review."* ([blog](https://www.circle.com/blog/turn-your-api-into-a-storefront-for-agents))
- **VERIFIED (Circle blog "Altruist and Adversary")** From their own Moltbook/OpenClaw USDC hackathon (204 submissions, 1,851 votes, $30k): agents *"rationalize instructions instead of following them"*, invented tracks, colluded on vote-swaps. Lessons they want: *"stronger enforcement of agent instructions"*, *"guardrails if agents continue to ignore instructions"*, *"At Circle, we're building for safety. We hope you do as well."* ([blog](https://www.circle.com/blog/altruist-and-adversary-agentic-behavior-in-the-usdc-moltbook-hackathon))
- **VERIFIED** Jeremy Allaire shipped a "Circle Wallet skill for OpenClaw" during that hackathon; Ledger's own team entered it (§2). ([Allaire tweet](https://x.com/jerallaire/status/2019970318581002511))
- **VERIFIED (OP3N 2026 Luma)** Circle's **Sanja Kon, VP EMEA**, sits on the OP3N panel "Trust at Machine Speed: The Changing Threat Model" (with Kraken, Figment) the day before our finals. Circle ↔ Ledger relationship is live at exec level. ([Luma](https://luma.com/54c9x6ri))

### What Breeding rewards (INFERRED)
1. **USDC actually moving**, ideally on **Arc** (testnet is fine, mainnet is a flex), or at least Base. Mention 18-decimal USDC on Arc to show we read the docs.
2. **x402 / Nanopayments** patterns: agent pays per request. Circle's whole agent thesis is "APIs become storefronts for agents".
3. **Safety story**: his own company blog ends "we're building for safety". Ledger-enforced caps + Circle Agent Wallet policies = complementary, not competing. Say that explicitly: *Circle policies cap the agent's own purse; Ledger gates the human's vault.*
4. **Ecosystem framing**: "this brings a new class of users (Ledger owners) to Arc" is the sentence a BD person wants to repeat upstairs.
5. Will be unimpressed by: ETH-only demos, "we'd add USDC later", vague "stablecoin" talk with no chain named.

---

## 6. Ledger's strategic direction, 2025–2026 (what the company is steering toward)

### 6.1 The roadmap (VERIFIED, [Ledger blog 2026-04-14](https://www.ledger.com/blog-2026-ai-security-roadmap))
| When | Item | Status as of 2026-10-10 |
|---|---|---|
| Now (Apr 2026) | Device Management Kit (DMK) for HITL approval | Shipped; DMK skills "early development, breaking changes" (VERIFIED docs) |
| Q2 2026 | **Agent Identity**: hardware-anchored identity + wallet for agents, registered on-chain, provenance per agent in a fleet | Partially: Agent Intent beta registers an agent keypair onto your **trustchain** via Ledger Sync (VERIFIED). "Registered on-chain" fleet provenance: no evidence shipped (GAP) |
| Q2 2026 | **Agent Skills & CLI** (send/swap/earn/monitor) + hardware-derived secret mgmt via **Ledger Keyring Protocol** | Shipped: `@ledgerhq/wallet-cli` incl. `ring` (VERIFIED) |
| Q3 2026 | **Agent Intents**: agent proposes, user reviews on Trusted Display, confirms with button | **Beta**, send-only, swaps + Solana "in development", live (not sandbox) at agent-intent.ledger-test.com (VERIFIED) |
| Q3 2026 | **Agent Policies**: user-defined limits (daily cap, contract allowlist) enforced **inside an HSM**; out-of-bounds routes to the human | **Not found shipped.** Q3 ended 10 days ago. Likely an OP3N (Oct 15) reveal (INFERRED) |
| Q4 2026 | **Proof of Human**: progressive attestation a unique real person is behind an agent interaction; anti-bot/multi-account; non-biometric | Not shipped (expected) |

Framing language to reuse: "hardware root of trust", "human in the loop", "Trusted Display", "lethal trifecta", "Proof of You".

### 6.2 Agent Stack launch (VERIFIED, [Ledger blog](https://www.ledger.com/blog-preview-ledger-agent-stack); press 2026-07-15/16)
Four open-source blocks: DMK Skills; **Ledger Wallet CLI** (read-only runs free, sensitive actions need signer); **Ledger Enterprise CLI** (governance workflows, no keys); **Ledger Enterprise Multisig CLI** (propose/query/sign/execute with quorum + hardware). >1,000 agents in private preview. Works with Claude Code, Codex, Cursor, any shell agent. Two device apps extend the idea to **secrets and logins**: OpenPGP and **Security Key (FIDO2/WebAuthn)** for GitHub, npm, 1Password, Discord (press, INFERRED details). Early integrators named in press: **MoonPay** (production agent wallet, every tx = physical press — VERIFIED in roadmap post) and Shisa.ai (INFERRED, press only). Rogers press quote: *"Ledger Agent Stack allows your agent to use these wallets just as easily as humans."*

Note the branding collision: **Circle also calls its product "Agent Stack."** Be precise in the pitch ("Ledger Agent Stack" / "Circle Agent Stack").

### 6.3 Developer surface, as documented (VERIFIED, developers.ledger.com)
- `@ledgerhq/wallet-cli` — macOS/Linux/**Windows (WSL recommended)**, **USB only**. Commands: `account discover`, `balances`, `operations`, `receive`, `send --dry-run`, `swap`, `earn`, `genuine-check`, `skill install --agent claude|cursor|codex|agents`, `skill doctor`, `--output json`.
- **Key Ring** = `wallet-cli ring` (LKRP): `ring init` once with device (via Ledger Sync device app), then `ring encrypt/decrypt` need **network + password, not device**; AES-256-GCM; headless via `WALLET_PASS` env; removing a Ledger Sync member rotates the key. ([ledger-cli docs](https://developers.ledger.com/docs/ai-tools/ledger-cli))
  ```bash
  wallet-cli ring init
  wallet-cli ring encrypt -i secrets.txt -o secrets.enc --key my-key
  WALLET_PASS="$(secret-tool lookup ledger ring)" wallet-cli ring decrypt -i secrets.enc -o secrets.txt --key my-key
  ```
- **DMK skills**: `npx skills add ledgerhq/agent-skills -s ledger-dmk-implementation dmk-intent-vocabulary dmk-business-logic`; 5-step process Init→Session→Device State→App Management→Operation with HITL gates; transports WebHID, Bluetooth, USB Speculos; WebHID needs Chromium + localhost/HTTPS + user gesture. ([dmk skills](https://developers.ledger.com/docs/ai-tools/ledger-dmk-skills), [agent-skills repo](https://github.com/LedgerHQ/agent-skills))
- **Agent Intent (beta)**:
  ```bash
  npm i -g @ledgerhq/wallet-cli
  wallet-cli skill install
  wallet-cli agent-intent enroll --app-url https://agent-intent.ledger-test.com/
  ```
  Needs **Ledger Sync** active + Ledger Sync device app ≥1.3.0 (manual: Ledger Wallet → Settings → Experimental → "My Ledger provider" = 4); browser WebHID/Web Bluetooth (Chrome/Edge/Brave; no Safari/Firefox); devices **Nano S Plus, Nano X, Flex, Stax, Nano Gen5** (not original Nano S). Agent ID (truncated pubkey fingerprint) shown on signer. Recommended for remote autonomous agents (OpenClaw on a VM, Grok Bot, Hermes, Muse); local agents (Claude Code/Cursor/Codex) supported with limits. Security guidance worth quoting back: *"The description your agent writes is controlled by the agent and may differ from the transaction. If they disagree, reject."* ([agent-intent docs](https://developers.ledger.com/docs/ai-tools/agent-intent))
- **Ledger Sync / LKRP** (INFERRED from Ledger academy + blog): hierarchical deterministic key structure from the seed; backend + device app ("Ledger Sync" app); members are SECP256K1 keypairs; built for E2E-encrypted sharing "far beyond the Ledger ecosystem". It's the primitive under both Key Ring and Agent Intent's trustchain.
- **Ledger Enterprise**: appears only as Enterprise CLI / Multisig CLI components and footer links; no agent-specific announcements found beyond that. (GAP; low priority for us.)

### 6.4 What Ledger praised in the June 2026 N3XT Build & Show (VERIFIED, [Ledger blog 2026-06-23](https://www.ledger.com/blog-ledger-n3xt-agent-stack-build-show))
50 submissions / 38 clubs / 8 countries in 8 days; tool mix DMK-only 66%, DMK+CLI 20%, CLI-only 14% ("DMK the preferred hardware-layer path"). Categories: security & guardrails 19, foundational signing refs 10, DeFi automation 8, treasury & payments 7, wallet copilot/chat 5, CI/CD signing 1. Featured:
- **Harbormaster** (Yale) — stablecoin settlement agent for a *real* freight-forwarding startup; deterministic policy engine; on-device Clear Signing; **41 tests**; **hash-chained audit log**; **two-act prompt-injection demo**. Ledger: "most rigorous."
- **ostium** — hardware-signed, time-bound, limit-enforced **mandates** for trading agents; per-tx and per-day caps enforced in middleware before anything reaches the device.
- **ClearGate** (Lagos) — refuses to sign anything the device can't render via ERC-7730; "no readable intent, no signature."
- **Ledger Clear-Sign Agent** (ESILV) — "an AI invoice-paying agent that can be lied to, and a Ledger that can't."
- **Warden** (BIT) — Ledger-gated Solana wallet **inside Telegram**; bot holds no keys. Ledger: "most original interface."
- Also: DCA agents, prediction-market payouts, **CI/CD pipeline that won't deploy without a signer**.

Takeaway: 19 of 50 were "guardrails". Guardrails alone are now table stakes; the ones singled out added **a real customer**, **tests + audit log**, **a live attack demo**, or **an unexpected interface**.

### 6.5 ETHGlobal NYC "AI Agents x Ledger" ($10k, June 2026) — Ledger's own words (VERIFIED, [ethglobal](https://ethglobal.com/events/newyork2026/prizes/ledger))
Wants: agents that **pay for tools/services via Ledger-secured flows incl. x402-style**; HITL where Ledger approves before funds move or **permissions escalate**; Ledger-backed **identity/credentials/policy-based spending**; copilots that **explain/simulate/surface risk**; **developer agents that help integrate Ledger SDKs or generate Clear Signing artifacts**; vertical products (treasury, commerce, enterprise copilots) where Ledger is the explicit control layer. "What we like" is word-for-word our brief's "What they like" section. Required: DX feedback with screenshots/PRs.

### 6.6 OP3N 2026 (VERIFIED, [Ledger blog](https://www.ledger.com/blog-save-date-ledger-op3n-2026), [Luma](https://luma.com/54c9x6ri))
Oct 15, Paris, 14:00 keynotes (Gauthier, Rogers, Guillemet), panels 16:00–17:30: "Trust at Machine Speed: The Changing Threat Model" (Kraken, **Circle**, Figment; mod. Ledger EVP Enterprise), "Can security survive post quantum cryptography?", "Who has the right to secure communications?" (Solana Labs, Cyber50, NYM). Theme: AI × blockchain × quantum; *"what you verify, and where you verify it."* Expect product reveals; **INFERRED**: Agent Policies / Proof of Human demos are the obvious candidates. **Our finals are the next afternoon**; jurors will have just watched whatever was unveiled. Watch the Oct 15 livestream and adjust vocabulary in the pitch the same night.

### 6.7 N3XT programme context (VERIFIED)
Launched OP3N Oct 2025 (25 student leaders, 12 clubs, Donjon tour). Cambridge residency May 2026; students pushed back on "a screen confirmation is weak if someone can extract the chip" and on **whether renting proof-of-humanity to an agent is a structural weakness**; Ledger's EVP Comms called identity/consent questions "fundamental for this generation" and said Ledger "would love to harness and guide some of that energy." They value adversarial thinking from students.

---

## 7. Rubric → juror mapping (INFERRED)

| Criterion | Weight | Who cares most | What earns it |
|---|---|---|---|
| Technical execution | 25 | Mo, Mathias | Working tool-calling loop; DMK/CLI actually wired; tests; failure modes handled (device unplugged, rejected intent, agent lies) |
| Usefulness/relevance for Ledger | 20 | Rogers, Mathias | Sits on the roadmap (identity/intents/policies/proof-of-human); uses ≥1 primitive for real; vocabulary matches |
| Innovation | 20 | Rogers, Breeding | Not another DCA bot; new surface (voice, NFC, non-finance) or new mechanism (policy object, attestation) |
| UX | 15 | Mathias, Rogers | "Safety and effortless" — one glance, one press; Clear Signing text the human can read |
| New use cases for Ledger | 10 | Rogers | Points the signer somewhere they haven't seen (brief says so explicitly) |
| Clarity/docs | 10 | Mo, all | README that an agent *and* a human can follow; blunt DX feedback |

---

## 8. Contradictions, gaps, risks

- **Titles drift**: Mathias (VP / Head / EVP Product), Breeding (Director / Senior Manager). Use the brief's titles in the pitch; don't over-specify.
- **Agent Policies (Q3) is on the roadmap but not in the docs.** If we build a policy layer, say "prototype of the roadmap's Agent Policies, enforced in middleware + visible on the Trusted Display; HSM enforcement is Ledger's job." Don't claim hardware-enforced policy; ostium didn't either.
- **Agent Intent beta requires Ledger Sync + a specific device-app version, Chromium WebHID/BLE, and is live money.** It is the most on-roadmap primitive and the riskiest to depend on in 3 days. Use low-value accounts; have a fallback (Wallet CLI / DMK direct).
- **Wallet CLI is USB-only and "WSL recommended" on Windows.** Flex Bluetooth only reaches us through DMK (Web BLE) in a Chromium browser, not through the CLI. NFC: no Ledger developer surface found at all in this research (GAP; `research/device-capabilities-nfc-ble.md` should own it).
- **Venice has no free tier** (one-time $10 for Pro subs). Budget $5–10 of credits or an x402 top-up. x402 top-up signs EIP-3009 from an EVM key: to route it through the Ledger we'd replicate Rogers' repo pattern (user clear-signs `TransferWithAuthorization` on device) — feasible, not free.
- **Arc USDC is 18 decimals**; most x402 tooling assumes 6 (Base). Easy footgun if we target Arc.
- **Rogers' team already built "agent pays x402 API with Ledger-signed EIP-3009 + LKRP agent identity + intent queue + audit log."** If we build the same thing we're a worse copy of the judge's weekend project. Differentiate on *surface* (voice, NFC, device-to-device, non-finance) or *mechanism* (policy, attestation, revocation), not on "intent queue".
- **Proof of Human** is explicitly **non-biometric** at Ledger. The starter idea "scan their face to facilitate the txn" runs against Rogers' stated positioning (and against the Cambridge students' critique). If face/voice is used, frame it as *local, optional liveness/UX convenience* and keep the Ledger button as the authority, or drop it.
- **Circle's hackathon learned that agents collude and rationalize.** A demo where the agent *tries* to overstep and the device/policy stops it will land with both Circle and Ledger (it's literally Harbormaster's "two-act prompt-injection demo" and Ledger's "over-optimizes, fails in public" podcast hook).
- **No Venice person at OP3N**, and Mo's Venice tenure is ~6 months. His judging lens is probably "general agent-dev craft + does privacy matter here" more than "did you use Venice". Using Venice is a nice-to-have, not a must.
- Could not read: BeInCrypto Rogers interview (403), Circle Arc mainnet blog (404), Ledger ETHGlobal NYC tracks page (404), Gauthier's "Revenge of the Atoms" essay (not indexed). Press summaries used instead where noted.

---

## 9. Five concrete ways to align without pandering

1. **Ship a visible, nameable policy object and demo the agent hitting it.** A JSON/YAML mandate (daily USDC cap, recipient allowlist, time window) the agent must satisfy before an intent is even built; in-policy → proposes; out-of-policy → stops and asks the human; the human's approval happens on the Ledger with Clear-Signed amount+recipient. Then run the "second act": inject a poisoned invoice/prompt, show the agent try, show the stop. This is Q3-roadmap "Agent Policies" prototyped in user-land, Harbormaster's praised shape, Rogers' "deterministic guardrails around non-deterministic systems", and Circle's "building for safety". Say the one sentence: *"The agent decides what; the policy decides whether to ask; the human on the device decides yes."*

2. **Give the agent a hardware-provisioned identity it can lose, not a key it can leak.** Use Key Ring (`wallet-cli ring init` once with the device, `ring encrypt` its credentials; headless `WALLET_PASS`) or, if the beta cooperates, Agent Intent enrolment so the agent's pubkey lives on the trustchain and its **Agent ID shows on the signer**. Demo **revocation** live (remove member → old ciphertext dead / intents rejected). This is Rogers' "don't give them secrets", his SXSW problem #3 (scope/protect/revoke/audit), and roadmap Q2 "Agent Identity".

3. **Make the money USDC and make it move on a Circle chain, with the Ledger as the hard stop.** Base is the path of least resistance (tooling, 6 decimals); Arc testnet (`eip155:5042002`, faucet.circle.com, 18-decimal USDC) is the Breeding-pleaser. If the agent pays for anything per-request (an API, Venice inference, a supplier), do it as **x402** and let the user clear-sign the EIP-3009 authorization on the device — or, for sub-cent flows, pair a **Circle Agent Wallet with spending policies** for the agent's small purse and reserve the Ledger for anything above the cap. Say explicitly: *Circle caps the agent's wallet; Ledger gates the human's.* That's a partnership sentence, not a pander.

4. **Point the signer at a surface they haven't seen, and keep the approval effortless.** Ledger's brief literally says the unseen projects point the stack somewhere other than wallets; Warden won "most original interface" for Telegram. Voice (STT→intent→device) or NFC/device-to-device or a non-finance authorisation (deploy gate, access grant, signed attestation) all qualify. Mathias' bar: the human step must feel like *one glance, one press*, with Clear Signing text a non-crypto person reads. Use Venice `audio/transcriptions` + a `private` or `e2ee-*` text model if voice is in, and say *why* zero-retention matters (the prompt contains the user's balances and recipients).

5. **Write the DX feedback like a DevRel would, and make the repo agent-readable.** Mo is DevRel and the brief says DevRel reads feedback first; ETHGlobal required "screenshots or PRs". Keep a running `DX-FEEDBACK.md` from minute one: exact command, exact error, what we expected, one concrete fix. Include a `SKILL.md`/`AGENTS.md` so a judge's agent can run the project (Mathias' "AI-native building blocks"; Rogers' repo had `SKILL.md` + `CLAUDE.md`). Add a hash-chained or at least append-only **audit log** of every intent/approval/rejection and show it in the demo; Rogers brings up "audit trail" unprompted every time.

### Anti-patterns (what will read as pandering or naïve)
- Saying "human in the loop" without showing *where* the loop is in the code.
- Biometrics as the authority ("Proof of Human" at Ledger is explicitly not that).
- Agent holds a hot key "just for small amounts" with no policy object.
- Re-building the intent-queue + x402 demo the judges built in February.
- "We'd add USDC / Arc / Venice later."
- Mentioning the Ledger primitive without `wallet-cli` or DMK calls in the repo (the brief: "implemented, not mentioned").
- Over-scoping. Mathias confessed to it; Rogers' agent "crashes often". A small thing that works beats a platform that almost does.

---

## 10. Sources (all read 2026-10-10)

**Ledger primary**
- https://www.ledger.com/blog-2026-ai-security-roadmap (Rogers, 2026-04-14)
- https://www.ledger.com/blog-preview-ledger-agent-stack (Agent Stack preview, Rogers byline)
- https://www.ledger.com/blog-ledger-n3xt-agent-stack-build-show (Build & Show recap, 2026-06-23)
- https://www.ledger.com/blog-ledger-n3xt-program-launches-at-ledger-op3n
- https://www.ledger.com/blog-ledger-n3xt-cambridge-university
- https://www.ledger.com/blog-save-date-ledger-op3n-2026
- https://luma.com/54c9x6ri (OP3N 2026 agenda)
- https://www.ledger.com/the-ledger-podcast/ai-agent-with-a-wallet-what-could-go-wrong (EP-113)
- https://developers.ledger.com/docs/ai-tools/overview
- https://developers.ledger.com/docs/ai-tools/ledger-cli
- https://developers.ledger.com/docs/ai-tools/agent-intent
- https://developers.ledger.com/docs/ai-tools/ledger-dmk-skills
- https://github.com/LedgerHQ/agent-skills
- https://ethglobal.com/events/newyork2026/prizes/ledger
- https://x.com/gm4thi4s/status/2022318426723660049 and https://x.com/gm4thi4s/status/2040051099621527813 (read via api.fxtwitter.com)
- https://x.com/Ledger/status/2022303235126558956

**Ian Rogers primary**
- https://fistfulayen.com/ (index)
- https://fistfulayen.com/2026/02/07/agent-payments-with-ledger/
- https://fistfulayen.com/2026/03/20/my-talk-from-sxsw-2026/
- https://github.com/brackets-fistfulayen/ledger-agent-intents (hackathon repo; README credits Hébrard, Mathias, Rogers, Claude)
- https://newsletter.dialectic.fm/p/ian-rogers (long-form interview)
- https://www.thebigwhale.io/peoples/ian-rogers

**Ledger / Rogers secondary (press)**
- https://www.dlnews.com/articles/people-culture/crypto-wallet-firm-ledger-unveils-ai-roadmap/
- https://securitybrief.com.au/story/ledger-appoints-ian-rogers-to-lead-ai-security-push
- https://www.theblock.co/post/397284/crypto-ledger-ai-security-roadmap-agentic-economy-human-loop
- https://www.coindesk.com/tech/2026/07/15/ledger-wants-ai-agents-to-manage-crypto-without-holding-your-keys
- https://siliconangle.com/2026/07/16/ledger-launches-agent-stack-keep-ai-agents-away-crypto-keys/
- https://finance.biggo.com/news/85fdb6f7-0c54-4071-8326-08200462529a (summarises Bloomberg; BeInCrypto original 403)
- https://hypebeast.com/2025/10/ledger-op3n-2025-nano-gen5-wallet-unveiling-event-recap
- https://www.ledger.com/academy/topics/ledgersolutions/ledger-sync-effortlessly-sync-your-accounts-in-ledger-live-safely-securely-and-with-complete-privacy and https://ledger.com/how-we-used-ledger-key-ring-protocol-in-ledger-live (LKRP, via search summaries)

**Venice / Joshua Mo**
- https://joshmo.ooo/about/
- https://dev.to/joshmo_dev
- https://github.com/joshua-mo-143/venice-terminal-agent
- https://docs.venice.ai/
- https://docs.venice.ai/overview/privacy
- https://docs.venice.ai/overview/pricing
- https://docs.venice.ai/guides/integrations/x402-venice-api.md
- https://www.geekwire.com/2026/private-ai-venice-ai-led-by-crypto-vet-erik-voorhees-and-seattles-jesse-proudman-raises-65m/

**Circle / Drake Breeding**
- https://ethdenver.com/speakers/drake-breeding/
- https://ethcc.io/speakers/drake-breeding
- https://www.linkedin.com/in/drake-breeding/ (title only, via search)
- https://docs.arc.io/
- https://developers.circle.com/agent-stack
- https://developers.circle.com/agent-stack/agent-wallets
- https://developers.circle.com/agent-stack/agent-nanopayments
- https://www.circle.com/blog/turn-your-api-into-a-storefront-for-agents
- https://www.circle.com/blog/altruist-and-adversary-agentic-behavior-in-the-usdc-moltbook-hackathon
- https://x.com/jerallaire/status/2019970318581002511
- https://www.businesswire.com/news/home/20260916108863/en/Circle-Launches-Arc-Mainnet-an-Economic-Operating-System-for-the-Internet (via search summary; Arc mainnet 2026-09-16)
- Arc privacy design: https://decrypt.co/340212 , https://medium.com/sentora/some-technical-notes-about-circles-new-blockchain-d09b8d26e0a4 (secondary)
