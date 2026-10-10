# Prior art: what has already been built on Ledger's AI tools (Agent Stack, Key Ring, DMK skills, Signer)

Research note for the N3XT @ OP3N hackathon (brief: `../HACKATHON.md`). Compiled 2026-10-10 from public web + GitHub (`gh search code/repos`, repo READMEs, ethglobal.com showcase pages). No hardware touched, nothing installed.

Legend: **VERIFIED** = read in a primary source (showcase page, README, Ledger docs, SDK source). **INFERRED** = derived from a secondary source or from pattern-matching; treat as a lead, not a fact.

---

## 0. Executive summary (read this if nothing else)

1. **The "agent proposes, Ledger approves" pattern is saturated.** Across ETHOnline 2026 (~850 projects, 27 showcase pages), ETHGlobal NYC 2026, Cannes 2026 and Ledger's own June 2026 bounty, I counted **60+ projects** whose Ledger primitive is "human taps the device before funds move" plus some spending-cap / policy contract. Judges have seen this dozens of times. **VERIFIED** (enumerated in Sections 2-5).
2. **Key Ring (`wallet-cli ring`) is almost always used the same way:** encrypt an API key / spending key at rest, `ring decrypt` into memory at startup. Agentry, Klaxon, Mandate, RingTree, Speakeasy, Veyra, VaultBreaker, Obolos, Finity, Vela, Arx, Harness, Naumachy, Bramble, Ledger Guard, SingIt, Chapter 2 all do exactly this. **VERIFIED.** The one creative Key Ring use: **SoulVault** (derives per-epoch keys from the ring so a dead agent's successor recovers encrypted memory with a fresh wallet) and **Harness / rewall** (headless host *joins* a ring through a browser relay with one device confirmation). Those won.
3. **Both starter ideas have direct prior art:**
   - **Voice agent + Ledger:** **ITHACA** (ETHOnline 2026) is "voice-run AI that invests your USDC", Gemini Live + ElevenLabs, Ledger Flex signs one mandate via DMK, Key Ring broker holds the agent key, and it took **3rd place in AI Agents x Ledger**. **VERIFIED.** Orchestra (Cannes 2026, "Talk to your crypto", DMK over Bluetooth) is chat/NL, not confirmed voice. Nobody combined voice **and** face.
   - **Face check:** every face-gated project (Quorly, Veyra, Human-Gated Copilot, Proctor, FaceGate, Securtxn, Xander, BOLT, NotWallet, WARDEN) used **World ID Selfie Check**, never a local camera model, and none combined it with a Ledger signer in a single approval flow. **VERIFIED.** Ledger itself has "Proof of Human / Proof of You" on its Q4 2026 roadmap with "liveness verification". **VERIFIED** (roadmap post, thirdweb article). A face check that is *attested on the device* would be stepping onto Ledger's own roadmap: good for "usefulness for Ledger", risky for "they've already thought about it".
   - **NFC Ledger-to-Ledger:** **no project has done it.** The Flex SDK does expose NFC in both `CARD_EMULATION` and `READER` modes (`lib_nfc/include/nfc_ledger.h`), gated by `ENABLE_NFC` / `ENABLE_NFC_READER` for `TARGET_STAX TARGET_FLEX TARGET_APEX_P` in `Makefile.standard_app`. **VERIFIED.** Ledger's own Recovery Key (NFC card <-> Flex/Stax) proves device-as-reader works in production. **VERIFIED** (press). But: you only have **one** NFC-capable device (Nano S Plus has no NFC), building a BOLOS app needs the Docker app-builder + Speculos (Speculos does not emulate NFC radio, **INFERRED**), and `lib_nfc/doc/mainpage.dox` literally says "TO BE COMPLETED". Closest prior art: Tap Pay (Tokyo 2026, two Android phones as NFC terminal), NotWallet (NFC card UID as key factor), Bank Rock (NTAG 424 DNA rock), Tappy (NFC sticker starts flow, Flipper Zero approves), Blee (BLE mesh USDC), MelodyPay (payments over sound, ESP32).
4. **Winners share three traits:** a real device in the demo (not Speculos only), a concrete non-obvious Ledger primitive (BOLOS app on the Secure Element, ring enrollment over a relay, EIP-7702 batch signed once), and a blunt DX feedback doc. The 2026 Ledger winners: Harness (1st ETHOnline), Lunave (1st NYC, custom BOLOS app on Apex P), Signel (1st Cannes, EIP-7702 via DMK), Veryclear (1st Cannes clear-signing), SoulVault (1st Continuity ETHOnline). **VERIFIED.**
5. **Non-finance is nearly empty.** The brief says "Non-finance ideas count" and "the projects they haven't seen yet point it somewhere else". Non-finance Ledger entries found: AUETH (PAM login via wallet, no Ledger named), Klaxon (CI secrets), SoulVault (document redaction), Bramble (WireGuard mesh), Harness (ssh to agent containers), rewall (secret manager + TOTP 2FA), NextKey (secrets release), Aegis (skill-file trust registry), Dead Men Tell Tales (dead-man switch for journalists). That is maybe 9 of ~70. **White space.**

---

## 1. Ledger's own tools, demos and posts (what the primitives are, as Ledger frames them)

| Item | What it is | Status | Source |
|---|---|---|---|
| **Ledger Agent Stack** (preview blog, dated 06/10/2026 on page; press says launch July 15-16 2026) | Four blocks: DMK Skills, Ledger Wallet CLI, Ledger Enterprise CLI, Ledger Enterprise Multisig CLI. Slogan "Agents propose. Humans approve. Hardware enforces." Signed by Ian C. Rogers (Chief Human Agency Officer, **on your jury**). Mentions the college.xyz $5k bounty and the ETHGlobal NYC $10k pool. No example projects named. | **VERIFIED** | https://www.ledger.com/blog-preview-ledger-agent-stack ; https://shop.ledger.com/pages/ledger-agent-stack |
| **Agent Stack shop page community demos** | Names early testers: acidburn (autonomous Solana marketplace agent), fianso (treasury agent, signer rejected a poisoned invoice), stoke (treasury "control plane" with deterministic policy firewall), Youssef Jeddi's **Orchestra** (agent swarm managing portfolios via DMK; same Orchestra placed at Cannes 2026). Roadmap "coming soon": Agent intent and policies; **Proof of You**. | **VERIFIED** | https://shop.ledger.com/pages/ledger-agent-stack |
| **2026 AI Security Roadmap** (Apr 14 2026, Ian Rogers) | Q2: Agent Identity, Agent Skills & CLI incl. "hardware-derived secret management through the Ledger Keyring Protocol". Q3: Agent Intents, Agent Policies ("spend no more than $500/day", "only these three contracts"). Q4: **Proof of Human** (progressive attestation, anti-bot). Names **MoonPay** production integration; names **Koda** (Ledger's internal agentic dev tool) demoed at Paris "Agents Anonymous + OpenClaw" meetup at Ledger HQ. | **VERIFIED** | https://www.ledger.com/blog-2026-ai-security-roadmap ; https://luma.com/v0bj508l |
| **Ledger Wallet CLI** `@ledgerhq/wallet-cli` | Docs show v2.1.0; repo README shows 2.9.0 (contradiction, docs stale). Commands: `account discover`, `balances`, `operations`, `send --dry-run`, `receive --verify`, `swap`, `earn`, `genuine-check`, `ring {init,encrypt,decrypt,keys,destroy}`, `agent-intent {enroll,recover,list,show,sync,send}`, `skill {install,doctor}`. **USB only** (no BLE). Docs: "macOS, Linux, Windows (WSL recommended)". Read-only cmds need no device. | **VERIFIED** | https://developers.ledger.com/docs/ai-tools/ledger-cli ; https://github.com/LedgerHQ/ledger-live/blob/develop/apps/wallet-cli/README.md |
| **Key Ring / LKRP** | `ring init` once with device via Ledger Sync app; afterwards `ring encrypt/decrypt` need **network** (restores trustchain) but **no device**. AES-256-GCM, per-`--key` HKDF-SHA256 from the LKRP root. Password from `WALLET_PASS` when no TTY. `--unsecure-no-password` exists. Removing a Ledger Sync member rotates the key (old ciphertext unrecoverable). `ring` superseded an earlier `secrets` command group (PR #16859 -> #17743). | **VERIFIED** | same + https://github.com/LedgerHQ/ledger-live/pull/17743 ; https://github.com/LedgerHQ/ledger-live/issues/21910 |
| **Agent Intent (beta)** | Hosted queue at https://agent-intent.ledger-test.com/ (not a sandbox; real signatures). Only **Send** intents today; swap + Solana "in development". Agent gets its own keypair registered on the trustchain; device shows an "Agent ID" fingerprint. Flow: `wallet-cli skill install` then `wallet-cli agent-intent enroll --app-url https://agent-intent.ledger-test.com/`. Needs Chrome/Edge/Brave (WebHID/WebBLE), Ledger Sync app >= 1.3.0, Nano S Plus **is** supported. | **VERIFIED** | https://developers.ledger.com/docs/ai-tools/agent-intent |
| **DMK skills** `LedgerHQ/agent-skills` | 3 skills: `ledger-dmk-implementation` (5-step Init->Session->Device State->App Mgmt->Operation, HITL gates), `dmk-intent-vocabulary`, `dmk-business-logic`; plus `wallet-cli-usage`. Install `npx skills add ledgerhq/agent-skills -s ...`. 6 stars, 35 commits, 5 open issues. Transports named: WebHID, Bluetooth, USB Speculos. | **VERIFIED** | https://github.com/LedgerHQ/agent-skills ; https://developers.ledger.com/docs/ai-tools/ledger-dmk-skills |
| **`brackets-fistfulayen/ledger-agent-intents`** | "Agent Intent Queue + Ledger Hardware Signing - Hackathon Project" for the OpenClaw USDC hackathon on Moltbook (deadline Feb 8 2026). "Agents propose. Humans sign. Ledger enforces." Private intents, x402 pay-per-call, demo video https://youtu.be/FTySyizcy4U. Polyledger (Cannes 2026 2nd) builds on it. "fistfulayen" is Ian Rogers' long-running blog handle, so this is very likely the juror's own prototype. | repo **VERIFIED**; authorship **INFERRED** | https://github.com/brackets-fistfulayen/ledger-agent-intents |
| **shisa-ai/shisad `contrib/ledger-bridge`** | Production-style HTTP bridge: daemon POSTs an `IntentEnvelope` + hash, bridge signs EIP-712 over USB via DMK `signTypedData`. Has a `ConfirmationLevel` enum L0 SOFTWARE ... L4 TRUSTED_DISPLAY_AUTHORIZATION. Shisa named as early adopter in press. Third-party MCP complement: `srotzin/hive-mcp-ledger-bridge`. | **VERIFIED** | https://github.com/shisa-ai/shisad/tree/main/contrib/ledger-bridge ; https://github.com/srotzin/hive-mcp-ledger-bridge |
| **tetsuo-ai/agenc-core** | Non-hackathon agent runtime (37 stars) with a `services/Ledger/walletCli.ts` that downloads, sha512-verifies and installs `@ledgerhq/wallet-cli` under `AGENC_HOME/tools` after explicit user confirmation; exposes `install_ledger_wallet_cli` / `ledger_wallet_cli_status` tools. Shows what "wallet-cli as an agent tool" looks like outside a hackathon. | **VERIFIED** | https://github.com/tetsuo-ai/agenc-core |
| **Walkthrough video** (brief) | Title: "Ledger Tracks Explained \| Etienne Waldron & Oscar Chaix at ETHOnline 2026". Description/chapters not retrievable. | **VERIFIED** (title only) | https://www.youtube.com/watch?v=328z0_foOi4 |
| **Ledger ETHOnline page** | Hard rule for that event: "must be built on the Ledger Agent Stack, specifically the Ledger Key Ring CLI (`wallet-cli ring`)". Judging bar verbatim: "Real user value, not generic chatbot wrappers / clear boundaries between autonomous behavior and explicit approval / concrete use of Ledger primitives, not just wallet branding / practical demos showing why device-backed trust matters / runnable without us in the room." **DX feedback judged as much as code.** Same bar is in our brief. | **VERIFIED** | https://developers.ledger.com/ethonline ; https://developers.ledger.com/ethglobalnyc |

Ledger Academy framing worth quoting in a pitch (from the Arx team's research notes, which cite Ledger Academy): the "lethal trifecta" (prompt injection, autonomous execution, access to real resources) and four threat classes "Authorization Manipulation, Credential Compromise, Software Override, Permission Escalation". **INFERRED** (second-hand; verify at https://www.ledger.com/academy/topics/agentic-ai/agentic-ai-security-guide before quoting).

---

## 2. ETHOnline 2026 (Sep 4-16 2026) Ledger track: winners and every Ledger-using entry found

Track: "AI Agents x Ledger" $3,500 (1st $2,000 / 2nd $1,000 / 3rd $500) + "Extend to Ledger" (Continuity) $1,500 (1st $1,000 / 2nd $500). **VERIFIED** https://ethglobal.com/events/ethonline2026/prizes

Method: ethglobal.com's `prizes=ledger` filter does **not** work server-side (returns all projects), so I paged all 27 showcase pages and flagged descriptions, then cross-checked with `gh search code "wallet-cli ring decrypt"` / `"ledger-dmk-implementation"` and the Arx team's own competitor research. Prize placements come from each project's showcase page. ETHGlobal has no central winners page for this event.

### 2a. Confirmed Ledger prize winners

| Place | Project | One line | Ledger primitive | Links |
|---|---|---|---|---|
| **1st, AI Agents x Ledger** | **Harness** | Every AI agent gets a container, an ENSv2 name and an on-chain daily spend limit, set up with one Ledger confirmation; `ssh runner.acme.harness.eth`. | DMK (WebHID), **Key Ring joined by a headless VM through a browser relay** (host generates keypair, Ledger admits it to the ring with one tap), `ring encrypt/decrypt` on the VM with no device, EIP-7702 batching 4 setup txs into one confirmation, LKRP SDK + hw-transport-webhid, x402 EIP-3009 payments. | https://ethglobal.com/showcase/harness-vvvaq ; https://github.com/LeoFranklin015/Harness |
| **2nd, AI Agents x Ledger** | *not found* | Checked every Ledger-flagged page (Vela, Klaxon, Mandate x3, Amulet, RingTree, Speakeasy, Arx, Attenuate, Finity, Obolos, Naumachy, Veyra, Bramble, Moor, VaultBreaker, Ledger Guard, NextKey, AgentKey, Try Mandate, Agentry); none lists it. | | gap |
| **3rd, AI Agents x Ledger** | **ITHACA** | "Voice-run AI that invests your USDC and aims to be resistant to theft." Gemini Live (STT+reasoning+TTS) wrapped in an ElevenLabs orb UI; each spoken command maps to an on-chain action; `GuardianVaultMulti` contract checks the Ledger-signed mandate (caps, venues, safe address, expiry, one-time escalations) in the same tx. | **Ledger Flex signs one mandate via DMK (USB or Bluetooth)**; Key Ring broker holds the agent key. Graph MCP, Circle CCTP v2, Base + Arc, Next.js PWA. | https://ethglobal.com/showcase/ithaca-i7yxs ; https://github.com/chrsnikhil/ithaca |
| **1st, Extend to Ledger** | **SoulVault** | Encrypted continuity for agent swarms + wallet-authorized selective disclosure of redacted documents (presidio-web in browser). Live org `soulvault-ensv2.eth`. | DMK + Ethereum Signer Kit with clear signing; **Key Ring epoch keys "derived, never stored"**, successor agent recovers memories with a fresh wallet; `dmk-speculos-browser` custom skill. | https://ethglobal.com/showcase/soulvault-h2gs1 ; https://github.com/nacmonad/soulvault |
| **2nd, Extend to Ledger** | **Preflight MCP** | MCP server (`preflight_check`) that scores a contract on on-chain behaviour (11 signals, noisy-OR) before an agent signs; HIGH verdict requires a physical press on a Ledger. Extends author's Singapore 2024 project. | `wallet-cli ring` as credential store; `wallet-cli receive --verify` as the device gate; **reads USB tree directly (47 ms) because `wallet-cli` scan took ~1 min and blew the MCP 60 s timeout**; 13 hardware test cases on a **Nano S Plus** found 9 defects; upstream PR LedgerHQ/device-sdk-ts#1884. | https://ethglobal.com/showcase/preflight-mcp-1i1qm ; https://github.com/ritiklakhwani/preflight |

### 2b. Every other ETHOnline 2026 entry that actually touches a Ledger primitive (no Ledger prize listed)

Grouped by the *kind* of Ledger use. "KR" = `wallet-cli ring`; "DMK" = Device Management Kit; "BOLOS" = custom device app.

**Custom device app / Secure Element logic (rare, high effort):**
- **Vela**: ~5,400-line BOLOS app for **Ledger Flex** storing spending mandates for 8 agents in NVRAM; chip builds the Hedera tx itself (on-chip protobuf), parses calldata recipient; each draw anchored to HCS; KR seals broker secrets; Chainlink CRE in Nitro enclave can narrow but not widen a mandate. WebHID console. Explicitly argues against Ledger's "one tap per transaction" model. https://ethglobal.com/showcase/vela-cscxk ; https://github.com/edenbd1/vela (same author as Lunave, NYC 1st).
- **Amulet**: ESP32-S3 wearable pendant with round touch display + haptics is the only device allowed to carry txs to a **Nano X over BLE**; brain on untrusted server, policy in ENS, KR for brain secrets; upstream PR LedgerHQ/app-ethereum#1109 documenting the `v` byte. https://ethglobal.com/showcase/amulet-tkj8k ; https://github.com/IronicDeGawd/EthOnline2026-Amulet

**Key Ring as headless / remote secret backend (the ETHOnline hard requirement):**
- **Klaxon**: CI secrets split in two; share A encrypted under KR and committed to repo; share B released by a witness only after the GitHub runner pays 0.001 HBAR with a signed commitment memo + OIDC; ERC-7730 descriptors for the Sepolia policy contract. Has `docs/LEDGER-FEEDBACK.md`. https://ethglobal.com/showcase/klaxon-s492r ; https://github.com/KaranSinghBisht/klaxon
- **Agentry / Vault402**: Hedera x402 purchasing agent; KR decrypts the Hedera operator key at startup ("device-trustchain gate, not a per-payment button press", their words). https://ethglobal.com/showcase/agentry-qp8ab ; https://github.com/anbusan19/ethonline
- **RingTree**: broker hands agents on EC2 signed, time-limited capabilities; KR protects OpenAI/Graph/payment creds; **Ledger Flex** via DMK/WebHID approves permissions and signs payments. https://ethglobal.com/showcase/ringtree-s5swe ; https://github.com/akashbiswas0/Ringtree
- **Veyra**: capability broker gated by **World ID Face Auth** + KR per-user slots (`veyra-user-<leafIndex>`) + Bazantic x402 ($0.01/call). Face + Key Ring, but no signer in the loop. https://ethglobal.com/showcase/veyra-5xefs ; https://github.com/vick2592/Veyra
- **VaultBreaker**: scoped capability tokens; KR encrypts settlement credential; **seed-derived AES fallback when no wallet-cli**. https://ethglobal.com/showcase/vaultbreaker-xw79k ; https://github.com/hrshjswniii/VaultBreaker
- **Speakeasy** (repo `verycool`): non-custodial 1inch Aqua trading backend for agents; KR encrypts agent/facilitator/keeper/PASETO keys; **Ledger Security Key (FIDO2) for OAuth login**; DMK + node-hid in physical mode; Nix flake; notes the Windows build had to move to WSL ext4 for Unix sockets. https://ethglobal.com/showcase/speakeasy-j4fws ; https://github.com/grievouswounds/verycool
- **Naumachy**: AI gladiators write 1inch SwapVM strategies; KR seals VPS secrets (they enrolled a headless VPS by running a KR member inside a GNOME keyring under `dbus-run-session` because wallet-cli is WebUSB-only); champion payout clear-signed on **Flex**. https://ethglobal.com/showcase/naumachy-nfou5 ; https://github.com/raouf2ouf/naumachy
- **Obolos**: agent marketplace within human budgets; KR protects inference credential + Hedera payer key; **adapted upstream wallet-cli ring to support Speculos transport**; Speculos only, says so. https://ethglobal.com/showcase/obolos-7yt2h ; https://github.com/saiisback/obolos
- **Finity** (repo `token-sesh`): "Ledger-approved pocket money"; owner clear-signs an Agent Mandate; `finityd` broker enforces; KR protects broker bundle; HCS receipts. npm `@therick/finity`. https://ethglobal.com/showcase/finity-yudu7 ; https://github.com/Ithaca-Labs/token-sesh
- **Bramble**: WireGuard mesh with ENSv2 as authority; Ledger signs enrollment via `@ledgerhq/hw-app-eth` (because `wallet-cli send` lacks Sepolia); KR encrypts the ACL-granting key. ADR + DX feedback docs. https://ethglobal.com/showcase/bramble-wvkne ; https://github.com/WhyAsh5114/bramble
- **Ledger Guard**: DeFi exit guards clear-signed on Ledger (DMK/WebHID + ERC-7730 descriptors); KR for keeper secrets. https://ethglobal.com/showcase/ledger-guard-ssq07 ; https://github.com/n1shanthb/Ledger-gaurd
- **rewall**: serverless secret manager on ENSv2 text records; TOTP 2FA browser extension; MCP server redacts values before the model; **server without USB joins a key ring after human approval on device** (demoed against app-ledger-sync in Speculos). https://ethglobal.com/showcase/rewall-32xx8 ; https://github.com/oynozan/rewall
- **Arx**: "programmable authorization firewall between agents and a hardware signer"; DMK 1.9.0 + eth signer 1.18.0 + Speculos 1.2.1; KR backs the capability broker; 14 adversarial scenarios as tests. Their `docs/research/prior-art.md` is a competitor map of the same track (useful meta-source). https://ethglobal.com/showcase/arx-z0ekp ; https://github.com/YagnaRDK/Arx
- **Chapter 2**: Android "AI Guardian" app; Ledger Nano X / Flex over Bluetooth for ESCALATE approvals; KR via subprocess adapter. Arx's research claims the backend has **zero `@ledgerhq` deps and shells a non-existent `wallet-cli ring sign`** that silently falls back to software. **INFERRED** (not independently verified). https://ethglobal.com/showcase/chapter2-pe1u4 ; https://github.com/maxiggle/ethonline-2026
- **SingIt** (Continuity): Telegram purchasing agent; Ledger reviews an EIP-191 message (purchase, amount, network, recipient) via DMK + eth signer; KR optional for gateway key. https://ethglobal.com/showcase/singit-g9b55 ; https://github.com/bubon-ik/SingItAI

**Signer-gated mandates / spending policy (the crowded middle):**
- **Mandate** (Satianurag, showcase "mandatei"): Base mainnet x402 agent; DMK HID + Ethereum Signer Kit sign the USDC funding authorization with a **custom ERC-7730 descriptor**; KR seals the software spending key; had to use `ledger:test-cal` + ledger-dev Ethereum app because production CAL returns 403 without a partner `LEDGER_ORIGIN_TOKEN`. Physical Nano S Plus run. https://ethglobal.com/showcase/mandatei-3f7h0 ; https://github.com/Satianurag/mandate
- **Mandate Agents** (yashj09/creditline): borrows on Compound v3, bridges via CCTP to Arc, pays; irreversible steps wait for a Ledger co-signature the contract rebuilds byte-for-byte; npm `@yashjain99/mandate-{sdk,ai,mcp}`. https://ethglobal.com/showcase/mandate-agents-wxnex ; https://github.com/yashj09/creditline
- **Try Mandate / AgentNS**: ERC-8004 agent identity + ENSv2; ownership transfer / permission escalation blocked in a `PermissionGate` until a physically connected Ledger clear-signs via DMK. https://ethglobal.com/showcase/try-mandate-o28rb ; https://github.com/sumithprabhu/AgentNS
- **AgentKey**: ENSv2 subname per agent, policy in text records, Chainlink CRE in Nitro TEE enforces, reinstatement needs EIP-712 from the creating Ledger; Speculos in Docker with screenshot polling. https://ethglobal.com/showcase/agentkey-qcqpp ; https://github.com/freedanjeremiah/ethonline2026-agent-key
- **Attenuate**: agent permissions as ENSv2 subnames, child grant must be strict subset (enforced in registry); DMK signs root mandate over Speculos; built a broker instead of KR because wallet-cli has no emulated transport. https://ethglobal.com/showcase/attenuate-n87ab ; https://github.com/RudranshG07/Attenuate
- **Moor**: 1inch Aqua range order signed once from Ledger via **Ledger Wallet API** (`@ledgerhq/wallet-api-client-react`) + EIP-7702 `executeBatch`; ERC-7730 descriptors submitted to the registry. https://ethglobal.com/showcase/moor-bps0m ; https://github.com/salviega/moor
- **NextKey**: secrets handed to a person or agent, released by ENS rules, confirmed on Ledger (one scalar mult yields address + unwrapping key so "a Ledger is asked to sign once"). https://ethglobal.com/showcase/nextkey-key-lock-m62ue ; https://github.com/4bridges/nextkey
- **NotYet**: timelock-encrypted (drand) period keys; DMK signs the schedule on-device with an ERC-7730 descriptor; device co-signs over-cap spends; won a Bazantic prize. https://ethglobal.com/showcase/notyet-hy3kh ; https://github.com/0xkeccak/NotYet
- **YourTurn 2.0** (Continuity, won Hedera Continuity): booking-recovery agent; DMK + Ethereum Signer Kit + node-hid sign an EIP-712 Recovery Mandate. https://ethglobal.com/showcase/yourturn-2-0-od7iw ; https://github.com/Devpen787/yourturn
- **Rebalance** (A1igator): Codex/Claude-Code-driven portfolio rebalancer with Ledger authorization docs. https://github.com/A1igator/rebalance
- **Allowance**: EIP-712 spending rules + ERC-8004 reputation guard as x402 hook; `LedgerTrustRoot` written against DMK **but never ran, no device**; reports app-ethereum fails to build against its own SDK (`C_chain_1_14px_bitmap`). https://ethglobal.com/showcase/allowance-x9syo ; https://github.com/IrushaBasukala/Allowance
- **Watcher**: smart-vault withdrawal delay; "optional hardware authorization" via ECDSA, no Ledger SDK named. https://ethglobal.com/showcase/watcher-o0mcp
- **Privet**: honest "Ledger not connected" (no CLI or device available). https://ethglobal.com/showcase/privet-k5ac8

**Mentions Ledger but not confirmed to use a Ledger SDK:** Detent, Coram, Mandate (nisargpatel), Mandate Run, Usenami Signer (Continuity, Nitro enclave), WARDEN (World ID + Privy), Vector52, Quorly. Name-only collisions: LedgerMind, Ledger-of-Work, Ledger Firewall, Hedera Lab ("ledger verification").

### 2c. Things ETHOnline 2026 entrants said about the DX (free material for our mandatory DX write-up, and real constraints)

- `wallet-cli` transport is **WebUSB/USB only**; headless hosts had to be enrolled through a browser relay (Harness, rewall), a GNOME keyring under `dbus-run-session` (Naumachy), or a patched Speculos transport (Obolos). **VERIFIED** (their READMEs).
- `wallet-cli send` does not support **Sepolia** (Bramble) and Hedera is not a wallet-cli currency (Agentry). **VERIFIED.**
- The HID channel does not multiplex: two concurrent `wallet-cli` processes corrupt each other's APDU exchange (Ledger docs via Arx notes). **INFERRED.**
- `wallet-cli` device scan took ~1 minute and exceeded the MCP client's 60 s timeout (Preflight). **VERIFIED.**
- Production CAL (clear-signing metadata) returns 403 without a partner `LEDGER_ORIGIN_TOKEN`; without `originToken` the eth signer "silently degrades to blind signing" (Mandate, agent-skills `dmk-business-logic`). **VERIFIED.**
- Ledger Hedera app cannot sign `AccountAllowanceApprove` (Dead Men Tell Tales, NYC). **VERIFIED.**
- `ring decrypt` stdout/stderr semantics and `--output json` behaviour undocumented (issue #21910, filed Sep 13 2026, still open, no Ledger reply). **VERIFIED.**
- Agent Intent beta: Send only; Nano S Plus supported; Chrome-family browser required. **VERIFIED.**

---

## 3. ETHGlobal New York 2026 (Jun 12-14) "AI Agents x Ledger" $10,000, 5 places

| Place | Project | One line | Ledger primitive | Links |
|---|---|---|---|---|
| **1st** | **Lunave** | AI-managed private USDC yield; co-pilot proposes, Ledger validates, agent maintains allocation. | **Native BOLOS app on Ledger Apex P** signing Unlink's EdDSA-Poseidon over BabyJubJub inside the SE (~26 s via `cx_bn`); Ethereum app for Permit2; **OpenPGP** so the strategy must be decrypted on-device before deposit. Chainlink CRE / Confidential AI. | https://ethglobal.com/showcase/lunave-5xkf2 ; https://github.com/edenbd1/lunave |
| **2nd** | **Aegis (Safe Skills)** | Trust check before an agent loads a SKILL.md: ENS name pins reviewed hash, Chainlink CRE LLM review in TEE writes verdict; Ledger signature can authorize a policy override but not tampering. Also 1st ENS. | Ledger hardware signature (SDK not named). | https://ethglobal.com/showcase/aegis-p4gj2 ; https://github.com/freeslugs/eth-global-nyc-2026 |
| **3rd** | **Dead Men Tell Tales** | Pirate-themed dead-man switch: encrypt memo in browser, arm agent with Ledger-signed Hedera payment, World ID check-ins, drand/tlock capsules, Hedera Schedule/HCS/File services. | Ledger via **WebHID** for arm/cancel; worked around Hedera app not signing allowance approvals. Also won Hedera "No Solidity Allowed". | https://ethglobal.com/showcase/dead-men-tell-tales-c53bp ; https://github.com/jasperdegens/dmtt |
| **4th** | **Stream Vaults** | Superfluid USDC stream to a DCA bot; capital-on-demand; four kill switches. | **DMK over WebHID; one hardware-signed EIP-7702 onboarding tx; ERC-7730 clear signing.** Also 2nd Uniswap. | https://ethglobal.com/showcase/stream-vaults-m9qz5 ; https://github.com/JulioMCruz/Streams |
| 5th | *not found* | | | gap |

Other NYC 2026 Ledger-flagged entries (no Ledger prize shown): **xPayables** (Ledger-signed owner policy gateway for agent USDC on Arc, WebHID), **QuickLedgerBooks** (AI bookkeeping, Nano S Plus approves txs; won ENS), **CivicShield** (disaster-relief fund; installed DMK skills), **Aivy Studio / Kickoff.bot** (has `docs/ledger-dx-feedback.md`; ElevenLabs *voice* for agent verdicts), **apWallet** (ENS budgets + `@ledgerhq/hw-app-eth` escalation, scaffold only), **Phora**. **VERIFIED** (showcase pages / repos). Ledger's NYC track text also listed "Developer agents that help teams integrate Ledger SDKs, generate Clear Signing artifacts" as a wanted direction. **VERIFIED.**

---

## 4. ETHGlobal Cannes 2026 (Jul 2026) Ledger $10,000: "AI Agents x Ledger" $3,700 + "Clear Signing, Integrations & Apps" $6,300

| Place | Project | One line | Ledger primitive | Links |
|---|---|---|---|---|
| **1st, AI Agents** | **Signel** (repo `signet`) | Upgrade EOA to EIP-7702 smart account via Ledger, then agents act within owner-set on-chain permissions. | DMK over WebHID. | https://ethglobal.com/showcase/signel-jfdgu ; https://github.com/HAPPYS1NGH/signet |
| **2nd, AI Agents** | **Polyledger** (PoC Innovation) | Bull/Bear/Quant agent council votes on Polymarket trades; user signs on Ledger. | **Custom device app forked from app-ethereum** with a "Market Context Protocol" APDU showing market/side/outcome/price instead of raw EIP-712; DMK USB/BLE; builds on `ledger-agent-intents`; Chainlink CRE oracle. | https://ethglobal.com/showcase/polyledger-u5k4j ; https://github.com/PoCInnovation/ethglobal2026 |
| 3rd/4th AI Agents | *not found* | | | gap |
| **1st, Clear Signing** | **Veryclear** (lfglabs `explain.md`) | "Scriptable ERC-7730 descriptions for Ethereum transactions", proofs verified on an edge device like a Ledger. | ERC-7730. | https://ethglobal.com/showcase/veryclear-vu8i7 ; https://github.com/lfglabs-dev/explain.md |

Other Cannes 2026 Ledger entries: **Orchestra** ("Talk to your crypto": Planner AI + Gatekeeper AI, Safe + AllowanceModule, DMK over **Bluetooth** for high-value approvals; 3rd in 0G track; featured on Ledger's shop page), **maki** (Cannes finalist; hardware-isolated keys sign every tx, Ledger second-signer path), **SecretPay** (x402 burner wallets from Unlink ZK pool, DMK approval for large payments), **Whisperrr** (betting, AI risk breakdown shown via Clear Signing), **AgentPass** (`device-signer-kit-ethereum` over WebHID), **Imink Ledger** (name only). **VERIFIED.** Press coverage of Cannes finalists (ENShell, DIVE, maki, Défi, ALMA, npmguard, VEIL VPN, PaintGlobal, EVM PORST, Corpus) does not mention Ledger. **VERIFIED** (crypto.news).

---

## 5. Older Ledger prizes (2024-2025): all DMK integrations and ERC-7730 clear-signing tooling, zero AI

| Event | Prize | Winner | Built | Link |
|---|---|---|---|---|
| ETHGlobal Singapore 2024 | Best Ledger Hardware Integration, 1st | **LedgeFolio** | Web app: Ledger + NFTs, bridging, ENS | https://ethglobal.com/showcase/ledgefolio-1ub39 |
| ETHGlobal Bangkok, Nov 2024 | Best Ledger Integration 1st + Clear Signing 2nd | **LedgerSuite** | ERC-7730 JSON generator + portfolio + multichain tx via `@ledgerhq/device-management-kit` + `device-signer-kit-ethereum` | https://ethglobal.com/showcase/ledgersuite-9jwzr |
| Bangkok 2024 | Clear Signing 1st | **Clearly Vaults** (Kiln) | Generic ERC-4626 parsing PR to `clear-signing-erc7730-registry` | https://ethglobal.com/showcase/clearly-vaults-ozoc1 |
| Bangkok 2024 | Best Ledger Integration 2nd | **TukTuk Delivery** | Street-food dApp with QR receipt on-chain | https://www.ledger.com/blog/ethglobal-bangkok-ledger-features-security-focused-projects |
| ETHGlobal Cannes, Jul 2025 | Clear Signing 1st | **ClearSignKit** | LLM generates ERC-7730 from ABI; Hardhat 3 plugin; extends `python-erc7730` | https://ethglobal.com/showcase/clearsignkit-ffum9 |
| Cannes 2025 | Clear Signing 2nd | **ERC7730 JSON builder** | Multi-chain + AI autocomplete + one-click PR to Ledger registry | https://ethglobal.com/showcase/erc7730-json-builder-e3510 |
| Cannes 2025 | Hardware Integrations 2nd | **LedgerFlow** | Patched app-ethereum clear-signing QR to link to per-chain explorers; Ragger/Speculos tests; DMK docs feedback | https://ethglobal.com/showcase/ledgerflow-wsxrx |
| ETHGlobal NYC 2025 | Hardware Integrations 1st | **Hardhat3-Ledger** | Ledger signer for Hardhat 3 via DMK + `hw-transport-node-hid`, tested on Flex | https://ethglobal.com/showcase/hardhat3-ledger-198y7 |
| ETHGlobal Buenos Aires, Nov 2025 | Hardware Integrations 2nd | **ledger-dmk-interop** | DMK Cosmos signer + DMK->viem/wagmi account | https://ethglobal.com/showcase/ledger-dmk-interop-bwa58 |

Prize structures by event (all **VERIFIED** from ethglobal prize pages): Singapore 2024 $5k hardware; Bangkok 2024 $10k; Cannes 2025 $10k (Clear Signing $4k, Hardware $5k, Docs $1k); NYC 2025 $6k (Hardware $5k + Wildcard $1k); Buenos Aires 2025 $10k (Clear Signing $4k, Hardware $5k, Creativity $1k). The AI-agent framing only starts with NYC 2026. Tokyo 2026 had **no** Ledger prize. **VERIFIED.**

---

## 6. Ledger's own June 2026 Agent Stack bounty ("Build & Show with the Ledger Agent Stack", BNT-0038, college.xyz $5k)

Small student projects, all Speculos-only, all "poisoned invoice -> device shows wrong recipient -> reject":
- **Agent Shield** (Tasfia-17/AgentSheild): CI/CD test suite "proving agents cannot steal funds when bounded by Ledger"; PolicyEngine -> DMK -> Speculos; `docker-compose up`, pytest attack suite. https://github.com/Tasfia-17/AgentSheild
- **FAILSAFE** (Tushar-Kumar-Singh/Hardware-Signer): treasury agent reads poisoned invoice; Speculos signs; DEMO vs LIVE modes. https://github.com/Tushar-Kumar-Singh/Hardware-Signer
- **ledger-hardware-agent** (rehna-jp): "Zero to Signed Transaction" with DMK skills + Speculos Nano X. https://github.com/rehna-jp/ledger-hardware-agent
- **RangeGuard** (sammajayi): prediction-market payout agent; DMK 5-step flow -> Speculos Nano S Plus (built `eth_nanos2.elf` in app-builder Docker). https://github.com/sammajayi/rangeguard
All **VERIFIED** (READMEs). Takeaway: the "poisoned invoice" demo is now a cliché; do not make it the centrepiece.

---

## 7. Prior art specific to the two starter ideas

### 7a. Voice agent that sends transactions
- **ITHACA** (ETHOnline 2026, **3rd place Ledger**): voice-first (Gemini Live + ElevenLabs), Ledger Flex signs one mandate via DMK, Key Ring broker, on-chain `GuardianVaultMulti` enforces. **This is the exact shape of idea #1 minus the face check, and it already placed.** https://github.com/chrsnikhil/ithaca
- **Orchestra** (Cannes 2026): "Talk to your crypto"; NL chat, DMK over Bluetooth; voice not confirmed. https://github.com/youssef-jeddi/Orchestra
- **Wikshi** (ETHOnline 2026): gives *agents* a phone voice and a video face (outbound calls, metered per second). Not user voice control. https://ethglobal.com/showcase/wikshi-pbc1d
- **Kickoff.bot / Aivy Studio** (NYC 2026): seller agent speaks verdict via ElevenLabs.
- Outside hackathons: TOMI wallet voice assistant (press), Vapi "payment confirmation" voice agents. **INFERRED** (press snippets only).
- No project found that puts the *transcript* or *intent hash* on the Ledger screen as a clear-signed field, nor one that uses the device as the anti-spoof gate for voice (voice is trivially replayable; the device tap is the actual authorization). That framing is open.

### 7b. Face check as a factor
- All hackathon face checks = **World ID Selfie Check** (liveness + facial similarity, ZK proof, nullifier). Quorly ($500-5k needs selfie <3 min old), Human-Gated Copilot (signal = keccak of action payload), Proctor (human answers from phone, silence = refusal), Veyra (face auth before agent execution), FaceGate (credential-sharing SDK), Securtxn, Xander, BOLT, NotWallet (selfie gates limit raise), WARDEN, Dead Men Tell Tales (same human re-proves on each check-in). **VERIFIED.** None pairs the selfie with a Ledger signature in a *single* approval; most are Privy/World-only.
- Ledger roadmap Q4 2026 "Proof of Human" with "added liveness verification" (thirdweb write-up) and "Proof of You" (shop page). **VERIFIED.** A face-gated Ledger flow is on-strategy for the "usefulness for Ledger" criterion but will get the question "how is this not World ID?".
- Nothing found doing **local, on-laptop face recognition** (e.g. MediaPipe/face-api.js) as a pre-check before a device tap. Cheap to build on Windows with a webcam; the honest pitch is "face = who is at the keyboard, Ledger tap = consent", not "face = security".

### 7c. NFC between two Ledgers ("use it like a wallet")
- **No prior project.** Zero hackathon entries use Ledger NFC at all. **VERIFIED** (27 ETHOnline pages + NYC/Cannes sweeps + gh search "ledger flex nfc" returned nothing).
- SDK facts (**VERIFIED** from `LedgerHQ/ledger-secure-sdk` master):
  - `Makefile.standard_app`: `ifeq ($(ENABLE_NFC), 1)` and target in `TARGET_STAX TARGET_FLEX TARGET_APEX_P` -> `DEFINES += HAVE_NFC`, `SDK_SOURCE_PATH += lib_nfc`; `ENABLE_NFC_READER=1` -> `HAVE_NFC_READER`.
  - `lib_nfc/include/nfc_ledger.h`: `NFC_LEDGER_MODE_CARD_EMULATION = 0x00`, `NFC_LEDGER_MODE_READER = 0x01`; `NFC_LEDGER_init/start/stop`, `NFC_LEDGER_send(packet, len, timeout_ms)`, `NFC_LEDGER_rx_seph_apdu_evt(...)`. `io/src/os_io.c` wires `ITC_IO_NFC_START_CE` / `ITC_IO_NFC_START_READER` and `os_io_nfc_reader_rx`.
  - `lib_nfc/doc/mainpage.dox`: "only available on Stax product ... TO BE COMPLETED" (stale vs Makefile; docs gap worth reporting).
  - Nano S Plus (`nanos2`) and Nano X have **no** NFC target flag.
- Production uses: **Ledger Security Key** app (FIDO2/U2F, `src/nfc_io.c`) logs in by tapping Flex/Stax to a phone (card-emulation mode). **Ledger Recovery Key** is an NFC card with its own SE that the Flex/Stax reads (reader mode) over "secure NFC wireless channels with no intermediary" (press, Jun 2025). **VERIFIED** (repo + press). So device-as-card and device-as-reader both ship; device-to-device is the untested combination.
- Practical blockers for a 3-day build: one Flex only (second NFC endpoint must be a phone or an NTAG/ACR122-style reader); a BOLOS app needs the `ledger-app-builder` Docker toolchain and sideloading onto a real Flex (Speculos has no NFC radio emulation, **INFERRED**); and an on-chain "transfer" between two cold wallets still needs a signed tx broadcast by something online, so "tap to pay" is really "tap to hand over a signed EIP-3009/`transferWithAuthorization` payload" (that is exactly what MelodyPay did over sound and Blee did over BLE, both ETHOnline 2026, both without Ledger). **VERIFIED** (their pages).
- Nearest neighbours: **Tap Pay** (Tokyo 2026, two Android phones as ENS-verified NFC terminal), **NotWallet** (NFC card UID + passphrase via MFKDF derives a key), **Bank Rock** (NTAG 424 DNA signed-URL taps prove physical presence), **Tappy** (NFC sticker opens the shop; Flipper Zero button approves; 2-of-2 keys), **LockENS** (ENSv2 access passes via tap), **Blee** (BLE mesh USDC with EIP-3009 pre-signed), **MelodyPay** (ESP32 air-gapped wallet, FSK audio). **VERIFIED.**
- Hardware-companion precedent that *did* reach Ledger: **Amulet** (ESP32 pendant speaks APDUs to a Nano X over BLE). Shows judges reward a physical second device talking Ledger's protocol.

---

## 8. Saturation map (what judges have already seen, roughly by count)

| Pattern | Approx. count seen | Examples |
|---|---|---|
| Spending cap / mandate contract + Ledger tap for over-limit | 25+ | Harness, Finity, Mandate x3, AgentKey, Attenuate, Vela, Arx, Ledger Guard, Chapter 2, Orchestra, Signel, xPayables, Stream Vaults |
| Key Ring decrypts agent credentials at boot | 15+ | Agentry, Klaxon, RingTree, Speakeasy, VaultBreaker, Veyra, Obolos, Naumachy, Bramble, SingIt |
| x402 agent payments with device approval | 15+ | Agentry, Klaxon, Mandate, Finity, Vela, SecretPay, Dead Men Tell Tales |
| ENS/ENSv2 name as agent permission record | 10+ | Harness, Attenuate, AgentKey, Try Mandate, apWallet, rewall |
| "Poisoned invoice, device shows wrong recipient" demo | 5+ | FAILSAFE, Agent Shield, fianso demo, Arx |
| ERC-7730 generators/tooling | 6 | LedgerSuite, ClearSignKit, JSON builder, Clearly Vaults, Veryclear, LedgerFlow |
| Custom BOLOS device app | 3 | Lunave (Apex P), Vela (Flex), Polyledger (app-ethereum fork) |
| Voice control | 1-2 | ITHACA, (Orchestra) |
| Face/liveness | ~10, all World ID | Quorly, Veyra, Proctor, Human-Gated Copilot |
| NFC with Ledger | 0 | |
| Ledger Security Key (FIDO2) in an agent flow | 1 | Speakeasy |
| OpenPGP app in an agent flow | 1 | Lunave |
| Agent Intent beta (`wallet-cli agent-intent`) | 0 hackathon uses found | (Ledger's own `ledger-agent-intents` prototype) |
| Non-finance use of the signer | ~9 | Klaxon, SoulVault, Bramble, Harness, rewall, NextKey, Aegis, DMTT, AUETH |

---

## 9. Open space (where we could be original, given 3 days, Windows, Nano S Plus + Flex)

- **Ledger Agent Intent beta is unused by anyone.** `wallet-cli agent-intent enroll` + the hosted queue + Nano S Plus support = a working async approval queue for free. Nobody has built a product on it. Risk: beta, Send-only, hosted at ledger-test.com.
- **Security Key / OpenPGP apps as agent primitives** are nearly untouched (1 use each) and need no custom firmware: FIDO2 tap on the Flex over NFC-to-phone or USB; PGP decrypt-on-device as "the agent cannot read this until a human taps".
- **NFC on the Flex** is a true first, but only as "Flex <-> phone/reader", not "Flex <-> Flex" (one NFC device). The card-emulation side is the proven path (Security Key does it).
- **Voice + Ledger** exists (ITHACA, 3rd). To be original, change what the device *shows*: clear-sign the spoken intent itself, or use voice only for *reading back* what the device will display, or target a non-finance action.
- **Face + Ledger** does not exist as one flow; every face check is World ID. A local liveness check gating the *Agent Intent queue* on the Flex would be new, but the jury (Ian Rogers owns "Proof of Human") will probe why it is better than World's.
- **Non-finance** is explicitly invited in the brief and <15% of entries went there.
- **DX feedback**: entrants with the best feedback docs (Klaxon `LEDGER-FEEDBACK.md`, Bramble ADR 0001, Mandate `DX.md`, Arx research) are also the ones judges remembered. The open issue #21910 and the stale `lib_nfc` doc are concrete, citable gaps nobody has fixed.

---

## 10. Contradictions and gaps found

- wallet-cli version: docs say v2.1.0, repo README says 2.9.0. **VERIFIED both.**
- `lib_nfc/doc/mainpage.dox` says Stax-only; `Makefile.standard_app` enables NFC for Stax, Flex and Apex P. **VERIFIED both** (doc is stale).
- Agent Stack launch date: blog page shows 06/10/2026; press says July 15/16 2026. **VERIFIED both.**
- Ledger's ETHOnline page says both tracks "must be built on ... `wallet-cli ring`", yet winners Harness/SoulVault/Preflight all also used DMK; ITHACA used DMK + ring. Ring alone did not win anything. **INFERRED** from placements.
- Missing placements I could not find on any public page: ETHOnline 2026 AI Agents x Ledger **2nd**; NYC 2026 **5th**; Cannes 2026 AI Agents **3rd/4th** and Clear Signing 2nd-4th. ETHGlobal publishes winners only on individual showcase pages.
- `support.ledger.com` NFC article (18934878523037) would not render for fetch; NFC-on-Ledger facts above come from SDK source + Ledger Academy page + press instead.
- Chapter 2's "fake LKRP / `ring sign`" claim is from a competitor's research doc, not independently verified.
- Authorship of `brackets-fistfulayen/ledger-agent-intents` as Ian Rogers is inferred from the handle only.

---

## 11. Sources (every URL used)

Ledger primary:
- https://developers.ledger.com/docs/ai-tools/overview
- https://developers.ledger.com/docs/ai-tools/ledger-cli
- https://developers.ledger.com/docs/ai-tools/ledger-dmk-skills
- https://developers.ledger.com/docs/ai-tools/agent-intent
- https://developers.ledger.com/ethonline
- https://developers.ledger.com/ethglobalnyc (404 at fetch time; content via search snippets and ethglobal prize page)
- https://www.ledger.com/blog-preview-ledger-agent-stack
- https://www.ledger.com/blog-2026-ai-security-roadmap
- https://shop.ledger.com/pages/ledger-agent-stack
- https://www.ledger.com/blog/ethglobal-bangkok-ledger-features-security-focused-projects
- https://www.ledger.com/academy/topics/ledgersolutions/ledgers-next-generation-devices-ledger-stax-vs-ledger-flex
- https://github.com/LedgerHQ/agent-skills
- https://github.com/LedgerHQ/ledger-live/blob/develop/apps/wallet-cli/README.md
- https://github.com/LedgerHQ/ledger-live/pull/17743 ; https://github.com/LedgerHQ/ledger-live/pull/16859 ; https://github.com/LedgerHQ/ledger-live/issues/21910
- https://github.com/LedgerHQ/ledger-secure-sdk (Makefile.standard_app, lib_nfc/, io/src/os_io.c, target/)
- https://github.com/LedgerHQ/app-security-key
- https://www.youtube.com/watch?v=328z0_foOi4
- https://luma.com/v0bj508l

ETHGlobal prize pages: https://ethglobal.com/events/ethonline2026/prizes ; /events/ethonline2026/prizes/ledger ; /events/newyork2026/prizes ; /events/newyork2026/prizes/ledger ; /events/cannes2026/prizes ; /events/cannes/prizes ; /events/buenosaires/prizes ; /events/newyork2025/prizes ; /events/bangkok/prizes ; /events/tokyo2026/prizes ; /events/singapore2024/prizes ; /events/london2024/prizes

ETHGlobal showcase pages fetched (ETHOnline 2026 listing pages 1-27 plus): harness-vvvaq, ithaca-i7yxs, soulvault-h2gs1, preflight-mcp-1i1qm, vela-cscxk, klaxon-s492r, agentry-qp8ab, ringtree-s5swe, veyra-5xefs, vaultbreaker-xw79k, speakeasy-j4fws, naumachy-nfou5, obolos-7yt2h, finity-yudu7, bramble-wvkne, ledger-guard-ssq07, rewall-32xx8, arx-z0ekp, chapter2-pe1u4, singit-g9b55, mandatei-3f7h0, mandate-agents-wxnex, try-mandate-o28rb, agentkey-qcqpp, attenuate-n87ab, moor-bps0m, nextkey-key-lock-m62ue, notyet-hy3kh, yourturn-2-0-od7iw, allowance-x9syo, watcher-o0mcp, privet-k5ac8, amulet-tkj8k, detent-0yj8s, coram-t4bvf, warrant-c3jsf, autocfo-ab0dx, quorly-yd6dy, aueth-spkf4, ledgermind-v1y6k, agentpermit-delta-e5ots, bank-rock-dc6ef, notwallet-m2fcz, proctor-f8bk7, countersign-6svcb, pocket-pdp8v, wikshi-pbc1d, melodypay-9ntio, blee-5v9rf, incepson-m71nq, human-gated-copilot-4bbnw, mandate-run-rgu6v, capability-descent-7mmjb, inheritable-mandates-gecc6, takarabako-hem4m, facegate-omma4, securtxn-xrqc6, faregate-w3jpz, tappy-f3n7n, mandate-v6m92, leekdiyhardwarewallet-5qssg, preflight-0hj4z, froggy-284ag, agentpass-mkb37; NYC 2026: lunave-5xkf2, aegis-p4gj2, dead-men-tell-tales-c53bp, stream-vaults-m9qz5, xpayables-h9950, quickledgerbooks-4dbhh (+ listing pages 1-4); Cannes 2026: polyledger-u5k4j, signel-jfdgu, veryclear-vu8i7, orchestra-mkifq, maki-564eg, secretpay-j4rpy, whisperrr-91mvn, agentpass-92p9u (+ listing pages 1-4); older: ledgersuite-9jwzr, ledgefolio-1ub39, clearly-vaults-ozoc1, clearsignkit-ffum9, erc7730-json-builder-e3510, ledgerflow-wsxrx, hardhat3-ledger-198y7, ledger-dmk-interop-bwa58, ledger-kit-qp0yy, alpha-ledger-f6wuf, clawmarket-mvbjx. Also https://ethglobal.com/showcase?prizes=ledger and ?search=ledger (filters ignored server-side).

GitHub repos read (README/source via `gh api`): LeoFranklin015/Harness, chrsnikhil/ithaca, nacmonad/soulvault, ritiklakhwani/preflight, edenbd1/vela, edenbd1/lunave, KaranSinghBisht/klaxon, anbusan19/ethonline, akashbiswas0/Ringtree, vick2592/Veyra, hrshjswniii/VaultBreaker, grievouswounds/verycool, raouf2ouf/naumachy, saiisback/obolos, Ithaca-Labs/token-sesh, WhyAsh5114/bramble, YagnaRDK/Arx (incl. docs/research/prior-art.md), maxiggle/ethonline-2026, bubon-ik/SingItAI, Satianurag/mandate, yashj09/creditline, sumithprabhu/AgentNS, freedanjeremiah/ethonline2026-agent-key, RudranshG07/Attenuate, salviega/moor, IronicDeGawd/EthOnline2026-Amulet, NFTeria/UNICA, namixai/signer-ethonline2026, mhrk04/warden, Devpen787/yourturn, A1igator/rebalance, Tasfia-17/AgentSheild, Tushar-Kumar-Singh/Hardware-Signer, rehna-jp/ledger-hardware-agent, lvelf/CivicShield, jasperdegens/dmtt, jmgomezl/aivy-studio, AJP-432/apWallet, sammajayi/rangeguard, pj-casey/ledger-toolkit, justinwender/phora, PoCInnovation/ethglobal2026, brackets-fistfulayen/ledger-agent-intents, srotzin/hive-mcp-ledger-bridge, shisa-ai/shisad (contrib/ledger-bridge), tetsuo-ai/agenc-core.

Press / secondary: https://blog.thirdweb.com/ledger-agent-stack-hardware-gated-wallet-security-for-ai-agents/ ; https://www.theblock.co/post/408549/ledger-unveils-hardware-backed-agent-stack ; https://siliconangle.com/2026/07/16/ledger-launches-agent-stack-keep-ai-agents-away-crypto-keys/ ; https://www.coindesk.com/tech/2026/07/15/ledger-wants-ai-agents-to-manage-crypto-without-holding-your-keys ; https://crypto.news/ai-agents-privacy-and-prediction-markets-define-ethglobal-cannes-2026-finalists/ ; https://www.esilv.fr/ethglobal-new-york-les-equipes-de-devinci-blockchain-remportent-cinq-recompenses-internationales/ ; https://www.theblock.co/post/359217/ledger-recovery-key ; https://decrypt.co/326759/ledger-introduces-physical-recovery-key-nfc-backup-for-wallets ; https://dlnews.com/articles/people-culture/crypto-wallet-firm-ledger-unveils-ai-roadmap/ ; https://support.ledger.com/article/18934878523037-zd (not retrievable) ; https://cryptobriefing.com/tomi-launches-ai-voice-assistant/ ; https://tessl.io/registry/skills/github/LedgerHQ/agent-skills/wallet-cli-usage
