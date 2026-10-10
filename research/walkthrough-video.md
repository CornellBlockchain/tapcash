# Research note: the "Ledger Tools Walkthrough" video (ETHOnline 2026)

Written 2026-10-10 for the N3XT @ OP3N hackathon (brief: `../HACKATHON.md`). Scope: what the video actually shows, the mental model the Ledger product team presents, and the resources it points at. ETHOnline rules/prizes are ignored except where they reveal what Ledger considers a strong project.

Tags: **VERIFIED** = read in a primary source (YouTube page metadata, the auto-caption track, Ledger docs, npm registry, GitHub). **INFERRED** = my reading between the lines.

## 1. Video identity (VERIFIED)

| Field | Value |
| --- | --- |
| URL | https://www.youtube.com/watch?v=328z0_foOi4 |
| Real title | **"Ledger Tracks Explained \| Etienne Waldron & Oscar Chaix at ETHOnline 2026"** (the brief's "Ledger Tools Walkthrough" is a nickname) |
| Channel | ETHGlobal (https://www.youtube.com/@ETHGlobal), not Ledger |
| Published | 2026-09-09 18:00 PT |
| Length | 1717 s = 28:37 |
| Speakers | Etienne Waldron and Oscar Chaix, both **product managers at Ledger working on the AI initiatives** (self-described at 00:11). Captions mangle the names as "Eten Walden" and "Oscar Sheeks". |
| Format | Slide talk (Etienne) -> tool overview (Oscar) -> **pre-recorded screen capture at 2x speed** of Claude Code driving wallet-cli (Oscar, 07:52-12:52) -> tracks + judging (Etienne) -> live Q&A |
| Captions | Auto-generated only (English + 20 machine translations). No human transcript exists. I pulled the English track via the YouTube innertube player endpoint; cleaned transcript is in Appendix A. |

Official description (from the page's `shortDescription`, abridged): "Etienne Waldron and Oscar Chaix from Ledger explain how hardware-backed security can keep humans in control of AI agents. They outline prompt injection, hallucinated actions, and plaintext secrets, then present a model where an agent proposes an action, the user verifies it on screen, and Ledger hardware signs without exposing the private key. They introduce Ledger Wallet CLI, Device Management Kit skills, Keyring CLI, OpenPGP, and FIDO2 ... Oscar demonstrates an agent checking balances, recommending a yield action, and completing a deposit after hardware confirmation and transaction simulation. He provisions Keyring CLI, encrypts an Anthropic API key, and lets the agent authenticate without placing the secret in its context."

Chapters (from the description):

```
00:00 Introduction to Ledger Agent Security      13:27 Ledger Hackathon Tracks
00:11 Meet Etienne Waldron and Oscar Chaix       14:04 Giving Agents Access Without Keys
00:44 Ledger Hardware and Secure Elements        14:44 Remote Agents and Hosted Machines
01:51 Security Risks in the Agentic Era          15:24 Keeping Humans in the Loop
02:27 Human Approval and Hardware Signing        16:01 New-Project Track Prizes
03:06 Ledger Wallet CLI for AI Agents            16:13 Continuity Track and Integrations
04:42 Device Management Kit Skills               17:42 Judging Criteria and Documentation
05:45 Keyring CLI for Agent Secrets              18:53 Developer Resources and Quick Links
07:03 OpenPGP and FIDO2 Applications             19:27 Fraudulent Contract Check Q&A
07:52 Agent Portfolio and Yield Demo             22:07 API Key and Bug Report Questions
09:03 Clear Signing and Transaction Checks       23:11 Nano X and Keyring Security Q&A
09:49 Encrypting an Anthropic API Key            25:07 Trust Chain Authorization Model
12:52 Why Secure Secrets Matter for Agents       28:12 Closing and Final Device Notes
```

## 2. The mental model the product team presents

### 2.1 One sentence (VERIFIED, 02:27-03:00)

> "Agents should propose actions but you as a human should be approving them. The hardware signs."

Supporting claims from the talk:
- Secure element with the screen "sitting immediately on top of this chip": what is displayed cannot be tampered with, "what you see is what you sign" (01:05-01:28).
- Threats named for the "agentic era": prompt injection, hallucination ("they tend to hallucinate less and less"), and **secrets in plaintext `.env` files** (01:51-02:26). Note the third one: it is what Key Ring is positioned against and it has nothing to do with crypto.
- "Anything that can act for you can also be turned against you" (01:53).
- Ledger's own marketing compresses it to "Agents propose. Humans approve. Hardware enforces." (Ledger blog, VERIFIED) and the docs overview calls the signer "the final gate" (VERIFIED).

### 2.2 Three pillars (VERIFIED, 03:06-07:32)

Oscar frames the Agent Stack as three pillars. The talk's order and his emphasis:

| # | Pillar | What he says it is | Emphasis |
| --- | --- | --- | --- |
| 1 | **CLIs** (Ledger Wallet CLI, Ledger Enterprise CLI, Enterprise Multisig CLI) | Lets "codex or claude code or any other agent that has access to a terminal" automate what you'd do by hand in the Ledger apps, "with your device security". Released **May 2026**; new capabilities since. Example prompts: read portfolio and lock 20% into BTC by clear signing; give per-asset targets and get optimised swaps proposed; check a recipient's on-chain history; optimise gas. | Mature; the demo vehicle |
| 2 | **Teach an agent to sign** = DMK skills | Skills that let any coding agent integrate the Device Management Kit SDK into "your app or any form of page or workflow". "Something that used to take days if not weeks currently takes 10 minutes." Example prompts: "integrate Ledger to my wallet", "require Ledger confirmation before my bot sends anything". He explicitly flags **non-crypto use cases** because the device also runs **Ledger Security Key (FIDO2 2FA)**. | Breadth |
| 3 | **Key Ring CLI** | "Relatively new and probably **the one we want the most experimentation with**." Provision your machine with the Ledger, then agents encrypt/decrypt secrets (API keys etc.) without the device. Recoverable from the seed via the "decentralised" Ledger Trust Chain. "Any form of hacks or experimentation to extend the limits of this feature or make it available on more setups, for example **remote agent setups**, will be quite interesting for us." | **Where they want novelty** |

Plus two "beyond crypto" device apps mentioned in passing (07:03): **OpenPGP** (Ledger as an encrypting machine / smart card) and the **FIDO2 security key** app. "A lot of promising things to do with those different primitives if you have an agentic workflow that needs to access certain websites or secrets or API keys."

### 2.3 How Key Ring differs from a signer (VERIFIED, Q&A 23:11-28:04)

This is the most technically useful part of the video, prompted by an attendee who noticed the agent seemed to hold the plaintext key in its context.

Oscar's answer, paraphrased with his words where possible:
- OpenPGP and Ring CLI are "two primitives to encrypt and decrypt secrets. They do work differently."
- **OpenPGP**: device app found in developer settings; everything is only decrypted "if you have your Ledger plugged in and sometimes if you approve on your device", configurable in the app. "Useful for certain types of secrets."
- **Ring CLI**: runs on "the keyring protocol that we also use at Ledger to encrypt Ledger account information on Ledger Wallet" (Ledger Sync). "That doesn't happen with a device plugged in and formal validations on the device. It happens through the trust chain with a simple web connection." **"You use your device to provision a certain machine with the rights to encrypt/decrypt those secrets ... your Ledger hardware serves as the root for that authorization. But then once you're initialized the agent in effect can decrypt or encrypt autonomously."** It is "more fitted for an agentic workflow" and for things "less sensible than transactions, like accessing API keys".
- Extra layer: "a password that's tied to your machine's OS" (the OS keychain / `WALLET_PASS`, see 3.3).
- The trust chain "is actually decentralized ... because your secrets are encrypted via your Ledger on your machine they're not accessible through that trust chain directly ... you're a bit more self-custodial on your secrets ... accessible through the machines that you're self-provisioning with your Ledger hardware."
- The attendee's summary (an agent talks to a provisioned machine, which does the decrypt and acts, so the agent only ever sees the result) gets a "Yeah, correct" (27:21). INFERRED: Oscar is agreeing to the architecture, not endorsing the "World ID selfie" part the attendee threw in.
- Nano X **can** initialise the ring (23:32; the answer "Okay. So, that's good." reads as a yes but is garbled).

Translation for us (INFERRED): Key Ring is a **machine-provisioning primitive, not a per-action approval primitive**. Per-action human approval = signer (wallet-cli `send`, DMK, Agent Intent, or OpenPGP with touch-to-decrypt). Don't pitch Key Ring as "the human approves each decrypt"; the product team explicitly says it isn't that.

### 2.4 Transaction Check and clear signing (VERIFIED, 09:03-09:41 and 19:27-22:06, 28:13)

- Demo deposit shows **two device screens**: approve (token allowance) then deposit, both clear-signed, both with **Transaction Check**.
- Transaction Check = backend simulation via "a few third-party providers including Blockaid and Cyvers" (captions: "blockade and cyers"), run **in parallel** ("unique in this industry"), results **rendered on the device**, not in software, so a hacked front end can't hide a warning. Optional; shows reasons; user can proceed anyway. Launched "May of last year" (= May 2025).
- **"Only available on our latest devices, so touchscreen devices like the Ledger Stax, Ledger Flex, the Ledger Nano Gen 5, not on Nanos."** Repeated at 28:13. You can simulate via "toolings, playgrounds, software simulators" (= Speculos; INFERRED).
- Hardware consequence for us: **Flex shows Transaction Check, Nano S Plus does not.** Demo on the Flex if the pitch leans on fraud detection.

## 3. Exactly what is demonstrated (07:52-12:52)

The demo is a screen recording of **Claude Code** ("my cloud code agent", 12:57) in a terminal with a Ledger device attached and the **Solana and Ethereum apps installed**. No commands are legible in the captions; the list below is reconstructed from narration (VERIFIED) and mapped onto documented wallet-cli commands (INFERRED, marked).

### 3.1 Part A: portfolio -> yield -> deposit with device confirmation

| Step | Narration (VERIFIED) | Likely command (INFERRED from docs) |
| --- | --- | --- |
| 1 | "Check my balances with the Ledger wallet CLI and determine if there's any yield opportunities" | `wallet-cli balances <label>`; `wallet-cli earn yields -n ethereum` (both no-device) |
| 2 | Finds **15 USDC** on the first account, lists yield opportunities, recommends not staking everything (test funds) | read-only |
| 3 | Oscar goes ahead "directly through the CLI" with the recommendation | `wallet-cli earn deposit <label> --amount '...'` |
| 4 | Two device screens: approve, then deposit; both clear-signed and Transaction-Checked | device confirmation on the Ledger |
| 5 | Agent confirms both transactions on-chain | read-only |

Docs confirm `earn` covers ERC-4626 vaults on EVM and native staking on Solana (VERIFIED, ledger-cli page).

### 3.2 Part B: encrypting an Anthropic API key with Key Ring

| Step | Narration (VERIFIED) | Likely command (INFERRED) |
| --- | --- | --- |
| 1 | "Now I want you to encrypt my Anthropic API key" | - |
| 2 | Agent: no key ring on this machine yet. Offers ways to supply the key; **recommends the clipboard "so that it never sees the API key itself"** | `wallet-cli ring init` (needs device, runs through the Ledger Sync app) |
| 3 | Oscar instead points it at a plaintext file | `wallet-cli ring encrypt -i <file> -o <file>.enc --key <name>` |
| 4 | Agent encrypts, **deletes the original file** | `rm` |
| 5 | "From now on I don't really need my Ledger device." Password "protected in the matching keychain" (macOS Keychain; INFERRED from docs) | - |
| 6 | Proof: agent decrypts and calls the Anthropic API, gets **HTTP 200**, "without ever reading it or consuming it or leaking it" | `wallet-cli ring decrypt -i ... --key <name>` piped into `curl` (INFERRED) |
| 7 | Oscar asks it to prove the key is not in "the history or the memory of the agent" | agent greps its own transcript (INFERRED) |

Caveat the audience raised (23:50): on screen it "looked like Claude still had access to the raw text within its context". Oscar does not directly deny it for the demo; he explains the protocol instead. INFERRED: step 3 (pointing at a plaintext file the agent can read) undermines the "never sees it" claim; the clipboard path or a pipe (`pbpaste | wallet-cli ring encrypt ...`) is the clean version. If we demo this, do it the clean way and say so.

### 3.3 Documented commands behind the demo (VERIFIED, ledger-cli docs + SKILL.md)

```bash
npm i -g @ledgerhq/wallet-cli            # also pnpm/yarn/bun
wallet-cli --version                      # docs show v2.1.0; npm latest is 2.9.0 (2026-10-05)
wallet-cli skill install --agent claude   # embeds the wallet-cli-usage skill (cursor|claude|codex|agents)
wallet-cli genuine-check
wallet-cli account discover ethereum      # device once per network
wallet-cli balances <label>               # no device
wallet-cli earn yields -n ethereum        # no device
wallet-cli earn deposit <label> --amount '0.5 ETH'
wallet-cli send <label> --to 0x... --amount '0.1 ETH' --dry-run

# Key Ring (LKRP)
WALLET_PASS=$(security find-generic-password -a default -s ledger-wallet-cli -w) wallet-cli ring init
wallet-cli ring encrypt -i secrets.txt -o secrets.enc --key my-key   # no device; needs network + WALLET_PASS
wallet-cli ring decrypt -i secrets.enc -o secrets.txt --key my-key
wallet-cli ring keys
wallet-cli ring destroy
wallet-cli --output json <anything>
```

Rules the official skill imposes on agents (VERIFIED, SKILL.md): never type or choose the password; inject via `$(keychain lookup)`; never print decrypted output (pipe to file/process/clipboard); `ring encrypt/decrypt` need **network** every run ("to restore the Ledger Sync trustchain") but **not the device**; removing a Ledger Sync member **rotates the key** and old ciphertext becomes undecryptable; `ring init --unsecure-no-password` exists and is discouraged.

### 3.4 Repos and pages shown or named

- developers.ledger.com/ethonline (QR code at 18:53; "all the commands that you need") - VERIFIED, still live.
- "Developer portal ... brand new page with all of this inside" - the ai-tools section: https://developers.ledger.com/docs/ai-tools/overview
- "Look at the repos we have. We have many public repos. You can publish a PR on pretty much anything" (17:21). No specific repo named in the talk. The pages link https://github.com/LedgerHQ/agent-skills and https://github.com/LedgerHQ/developer-portal.
- Agents name-dropped as targets: Codex, Claude Code (03:32); OpenClaw, Grok Bot, Hermes as autonomous agents that "need to access those secrets on a more regular basis" (13:08).

## 4. What Ledger says it wants (strong-project signals)

### 4.1 Explicit, from the talk (VERIFIED, 13:27-18:53)

1. "Agents don't store passwords directly ... what can you build where you **give the agent permission to use your keys without giving it your keys** directly." (14:04) This is the headline use case.
2. "Implement Key Ring in a machine where you can't [plug in a Ledger]: a **VPS, a CI runner, anything hosted**." (14:44) Called "also very interesting".
3. "Agents that pay for APIs, tools ... x402 ... add Ledger in the flows for **autonomous payments or payments under certain conditions**." (15:00)
4. "**Human in the loop** for approving high-risk actions, moving funds ... **thresholds**: after a certain amount you get in the loop." (15:24) "Voluntarily global ... giving creativity its own place."
5. Continuity-style: add a Ledger signer to an existing product via DMK skills; "make wallet-cli ring the key backend for the environment" (replace `.env`); "device confirmation when it matters in typical flows of your product"; fix an issue / PR in a Ledger repo.
6. Judging (17:42): "the **boundary between what is autonomous and what needs your approval has to be clear**"; "real Ledger integrations that make sense"; "**we do need to be able to try it. We will try it. We will run the code**"; explain **before/after**: "how did Ledger make your product better"; include **documentation feedback** ("doesn't have to be very long, a simple page would do").

### 4.2 From the ETHOnline page the video points to (VERIFIED)

"Shared bar": real user value, not generic chatbot wrappers; clear boundary autonomous vs explicit approval; concrete use of Ledger primitives, not just wallet branding. Extra: practical demo of why device-backed trust matters for AI; something judges can run without the team present (clonable repo or recorded walkthrough); for continuity, a clear before/after. DX feedback "weighed as heavily as code"; bonus for tutorial ideas, navigation fixes, "time-saver" suggestions, screenshots or PRs.

Our N3XT brief's "What they like" list is a near-verbatim copy of this page, so the video's criteria are the N3XT criteria (INFERRED, but the overlap is word-for-word).

### 4.3 Reading between the lines (INFERRED)

- The team's stated favourite is **Key Ring experimentation**, especially **remote/headless**. Note that since the video, Ledger shipped **Ledger Agent Intent** (beta; wallet-cli 2.9.0 has `agent-intent enroll|list|show|send`) which is their own answer to "remote agent proposes, I approve on device later". A hackathon project that just rebuilds Agent Intent is now redundant; one that uses it, or does the Key Ring-on-a-VPS problem well, is on-message.
- Non-crypto framing appears **three times** in 28 minutes (Key Ring "beyond crypto", OpenPGP/FIDO2 "beyond crypto", DMK "non-crypto use cases"). The N3XT brief's "Non-finance ideas count" is the same signal.
- They care that judges can **run it**. Windows-only or device-specific demos need a recorded walkthrough as fallback.
- The demo's weakest moment was the audience catching the plaintext-in-context issue. A project that **provably** keeps the secret out of the agent's context (pipe-only, no file, show the transcript grep) would land well with exactly this team.

## 5. ETHOnline projects that used the stack (context, VERIFIED from ETHGlobal showcase)

Prize results are not shown on the showcase pages, so these are examples of what builders did, not confirmed winners.

| Project | Ledger tool used | Idea |
| --- | --- | --- |
| **Klaxon** (https://ethglobal.com/showcase/klaxon-s492r) | Key Ring, enrolled on a Nano, **restored headlessly on a GitHub-hosted runner** | CI secret split in two; share A encrypted under LKRP in the repo, share B released by a witness against a Hedera payment + GitHub OIDC; every release logged. Directly answers "Key Ring on hosts without USB". |
| **Agentry** (https://ethglobal.com/showcase/agentry-qp8ab) | Key Ring only | Purchase agent on Hedera x402; operator key `ring encrypt`ed at rest and decrypted right before settlement. The page honestly notes this "is a gate on the key, not a hardware-produced signature". |
| Quorly (https://ethglobal.com/showcase/quorly-yd6dy) | none (World ID Selfie Check + Privy) | Face-approved invoice payouts with amount thresholds. Relevant to our "face scan" idea: a competitor did biometrics without Ledger; the Ledger angle would be making the hardware tap the final gate and the face only a risk signal. |

## 6. Gaps, contradictions, things to distrust

- **Transcript quality**: auto-captions only. Names, "Blockaid/Cyvers", "x402" ("X42"), "Hermes" ("airmes") and "Nano X" answers are reconstructions. No slide text is captured; the pre-recorded demo has no narration of exact commands.
- **"Never sees the key" vs the demo**: see 3.2. The talk's own Q&A exposes it.
- **Docs drift**: the ledger-cli page shows `wallet-cli v2.1.0`; npm latest is **2.9.0 (2026-10-05)** with `agent-intent` commands and prebuilt `windows-x64`, `linux-x64/arm64`, `darwin-arm64` binaries (VERIFIED, registry). No `darwin-x64`. `engines` not declared.
- **Windows**: docs say "macOS, Linux, Windows (WSL recommended)". A native windows-x64 binary exists but the password examples are macOS `security` / Linux `secret-tool` only; no Windows Credential Manager recipe. USB passthrough from WSL2 needs usbipd, which the docs don't mention. (INFERRED risk; test on day 1.)
- **agent-skills README** tells you to install `wallet-cli-usage` from `LedgerHQ/developer-ai-skills` while the docs say `LedgerHQ/agent-skills`; repo rename not fully propagated (VERIFIED mismatch). Repo has 6 stars, 35 commits: young.
- **"Decentralised" trust chain**: the talk says decentralised; the Ledger Live engineering post describes a Ledger-run backend with CRUD API plus client-side encryption under device-derived keys. INFERRED: "decentralised" is marketing; the accurate claim is "end-to-end encrypted, Ledger cannot read it, but availability depends on Ledger's backend and on network access at every decrypt".
- **Key rotation footgun**: removing a Ledger Sync member rotates the key and strands old ciphertext (VERIFIED, docs). Matters if a demo adds/removes machines.
- **Transaction Check device support**: talk says touchscreen only (Stax, Flex, Nano Gen 5). Our Nano S Plus will clear-sign but show no simulation result.
- **Ring init uses the Ledger Sync device app**; Agent Intent docs require Ledger Sync app >= 1.3.0 and list Nano S Plus and Flex as supported (VERIFIED). INFERRED: both our devices can `ring init`.
- No ETHOnline Ledger winners list could be found (showcase filter ignores the `prizes=ledger` param). Unknown which approach the team actually rewarded.
- The Ian Rogers / Ledger X threads about Agent Stack were not readable (HTTP 402).

## 7. Implications for our 3-day build (INFERRED)

- Use the video's vocabulary in the pitch: "agent proposes, human approves, hardware signs"; name the autonomous/approved boundary on one slide.
- Pick one primitive and implement it visibly: `ring` for secrets, `send`/`earn`/DMK/Agent Intent for per-action approval. Don't mix them up in the narrative (the team will notice; they corrected an attendee on exactly this).
- Flex for anything that shows Transaction Check or NFC/BLE; Nano S Plus as the "it also works on the cheap device" fallback.
- Record a walkthrough video regardless; "we will run the code" plus Windows-first hardware is a risk.
- Ship the DX feedback page; the talk asks for it twice and the brief makes it mandatory.

## 8. Sources

Primary (read directly):
- https://www.youtube.com/watch?v=328z0_foOi4 (page metadata: title, description, chapters, length, publish date)
- https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=328z0_foOi4&format=json (title, channel)
- YouTube innertube `youtubei/v1/player` + `api/timedtext` English ASR track (transcript, Appendix A)
- https://developers.ledger.com/ethonline
- https://ethglobal.com/events/ethonline2026/prizes/ledger
- https://developers.ledger.com/docs/ai-tools/overview
- https://developers.ledger.com/docs/ai-tools/ledger-cli
- https://developers.ledger.com/docs/ai-tools/ledger-dmk-skills
- https://developers.ledger.com/docs/ai-tools/agent-intent
- https://raw.githubusercontent.com/LedgerHQ/agent-skills/main/skills/wallet-cli/wallet-cli-usage/SKILL.md
- https://github.com/LedgerHQ/agent-skills
- https://registry.npmjs.org/@ledgerhq/wallet-cli
- https://www.ledger.com/blog-preview-ledger-agent-stack
- https://www.ledger.com/how-we-used-ledger-key-ring-protocol-in-ledger-live
- https://ethglobal.com/showcase/agentry-qp8ab
- https://ethglobal.com/showcase/klaxon-s492r
- https://ethglobal.com/showcase/quorly-yd6dy
- https://ethglobal.com/showcase?events=ethonline2026&prizes=ledger (pages 1-2; filter not honoured)

Failed / not readable:
- https://www.npmjs.com/package/@ledgerhq/wallet-cli (403; used the registry JSON instead)
- https://x.com/iancr/status/2064722216533512393 (402)
- https://developers.ledger.com/ethglobalnyc (404)

Search-only (not relied on for facts): forklog.com, quasa.io, thebigwhale.io coverage of Agent Stack and Key Ring Protocol; https://github.com/LedgerHQ/ledger-key-ring-protocol-whitepaper (named in the Ledger Live post, not fetched).

## Appendix A: cleaned auto-transcript, grouped by chapter

Auto-generated captions with filler words removed; speaker switches marked `>>`. Names and product names are as the ASR heard them (see section 6 for corrections). Treat wording as approximate.

**[00:00] Introduction to Ledger Agent Security**

Hello everyone and welcome to the Ledger

**[00:11] Meet Etienne Waldron and Oscar Chaix**

workshop. we are Eten Walden, myself and Oscar Sheeks next to me. We're both product managers at Ledger and working on the AI initiatives for Ledger. so yeah, let's let's dive in. so here's briefly the agenda for today. We'll talk a little bit about Ledger, not too much. we'll talk about trust for agents right after that. Oscar here will present some of the tools that we have that are available for you to try. and we'll present the tracks at the end, the ones you'll be hacking on during the whole duration of this hackathon.

**[00:44] Ledger Hardware and Secure Elements**

so a bit about Ledger first. Ledger is a French company was created in France in 2014. we make hardware devices that help you secure your cryptocurrencies. today we secure roughly 20% of the world's crypto assets and we have sold over 8 million of these devices so far. the title here says secure by design and if you look at the image on the right here you can see that there's a chip inside the device called the secure element and we have the screen that sits immediately on top of this chip. So what this means is the data that is shown on your on your ledger device is cannot be tampered with and what you see is essentially what you sign and this will be meaningful for the rest that we'll see today. so I'm sure you're very familiar with our set of products and you know they are used to secure cryptocurrencies but it turns out the architecture and the way we do our devices is also very appropriate for the agentic era. so ledger actually is also the trusted infrastructure for the agentic era the one we we're in right now.

**[01:51] Security Risks in the Agentic Era**

and this is quite a powerful sentence at the top here but you know anything that can act for you can also be turned against you and this is this is obviously very important in in today's times. obviously we have prompt injections that are possible. models can of course hallucinate even though they tend to hallucinate less and less and your secrets that may be stored in plain text environment files can also be leaked. So a lot of things to worry about in the agentic era and we'll see a bit how how Ledger can be a solution to all of this.

**[02:27] Human Approval and Hardware Signing**

so essentially the way we believe at leger should be done is that agents should propose actions but you as a human should be approving them. The hardware signs. So obviously the private key never should leave the secure element never leaves your device. and you should be able as a human to understand what you're about to sign on the screen. and everything you know everything that matters that that's critical needs a human a physical confirmation from a human. So that's kind of the model here that we're talking about. and Oscar now is going to talk about the whole stack behind what I just mentioned.

**[03:06] Ledger Wallet CLI for AI Agents**

>> Yep. Thank you and hey everyone. so on the agentic side of things we've released a few products already and and I'm going to describe them just now. The first one is CLI. So they allow you to essentially interact with our platforms whether it be ledger wallet or ledger enterprise services or even enterprise multisig but directly from your preferred agent. So if you're using codeex or using cloud code or any other agent that has access to a terminal you're able to use that to automate certain things you will do by hand on our apps and also trade with your device security. So a few example here you can ask your agent to read your portfolio and and then ask it to lock 20% of it in in a in a bitcoin by clear signing on the device. if you have certain targets for for each assets you can you can provide those targets to the AI and as it has access to those different positions it can propose optimized swaps to you as the as the user. you just have to plug and and confirm on your device. Or you can also do things that are a bit outside of what we usually do in our apps. You can check for the re recipients unchange history. You can also optimize perhaps gas fees by asking your agent to crunch numbers that you know you you wouldn't want to do on your own. So that's what we started to release in May. Since then, we've added a few capabilities I'm going to demo in in the next in the next slide. you can also teach an

**[04:42] Device Management Kit Skills**

agent to sign. So that's the second pillar. that's a bit broad but in in a in a nutshell we have a an SDK called the device management kit and we have now created skills that allows any agent to essentially integrate it in your app or on any form of a of a of page or workflow that that you can think of. So you know something that used to take days if not weeks currently takes 10 minutes. Just ask your agent read those skills and please integrate ledger to to my to my wallet or require ledger confirmation before my bot sends anything. you can also think about non-crypto use cases for that one because it it comes with the support of applications like ledger security key which is essentially a 502 2FA directly on your ledger signer. And finally and and that's that's one that's relatively new and and it's probably the one we want the most you know experimentation with at

**[05:45] Keyring CLI for Agent Secrets**

this point is the key ring CLI. and essentially it allows us to to to go beyond crypto as a as a developer you can provision your your machine with your ledger hardware and allow your agents to encrypt and decrypt secrets secrets like API keys or or or other secrets it needs to access to perform actions for you. so that's quite convenient. It allows you to go from having a secrets in clear in a N file to something more secure and encrypted directly via ledger. It's also recoverable via ledger. So if you lose your ledger, you can access again those those those secrets which are stored on a decentralized protocol that's called the the ledger trust chain. so on on on this one essentially you know any any form of hacks or experimentation to extend the limits of this feature or make it available on on more setups for example remote agent setups will be will be quite interesting for us. that's one of the things that that we have released. I'm going to demo it in a second but there's two other apps that

**[07:03] OpenPGP and FIDO2 Applications**

are beyond cry crypto. They're called open PGP. So that allows you to essentially use your ledger as a as a an encrypting machine and a smart card. And there's the Fed2 device app I just discussed which is a security key. So I think there's a lot of promising things to to to do with those different primitives if you have an agentic workflow that needs to access certain websites or secrets or API keys. all right. So that's for the general presentation and I'm going to walk you through the the video. Let me just refresh this one. Okay, cool. So here's the video.

**[07:52] Agent Portfolio and Yield Demo**

Oops. Let me press play. All right. We we did it in 2x speed because with a with the AI taking some time sometimes to answer it's easier. So here I'm I'm asking my code to essentially check my my balances with the ledger wallet CLI and also determine if there's any yield opportunities for me. so it's it's doing that now. At this point I have my Ledger device plugged in. I have the Solana and Ethereum apps available so it can check those balances. It found 15 USDC on my first account and a few yield opportunities. So you know what's interesting here is that it gives a few recommendations. I don't have a lot of test funds. So you know essentially it's recommendation is not necessarily to stake everything, but I I'm still going to go ahead and st directly through the CLI. I chose to go with their recommendation. And so here essentially what I what I'm

**[09:03] Clear Signing and Transaction Checks**

doing is is confirming on the device. There's two device screens. One to approve the the authorization to to deposit and then the actual deposit flow. And those two transactions on my device come with both clear signing so I can read exactly what I'm approving and they come with transaction check which is a simulation service. we have in the in the back end that checks that there's no fraudulent smart contracts involved and that you know the what I can expect from this operation is actually going to happen and so here I validate both on my device the approve and deposit are are confirmed and checked on the blockchain by the by the AI. so that shows you just one example of what you can do with the CLI and now the second part which is

**[09:49] Encrypting an Anthropic API Key**

the encryption part. So I ask it, okay, now I want you to encrypt my anthropic API key. and so that's using the ledger key ring on the CLI. it tells me that there's no key ring yet on this machine. How can I provide this this API key? And here there's actually quite a few ways to do it. the AI will already recommend you to use your clipboard so that it never sees the the API key itself. but there's other ways to do it. actually as you'll see. So here it provisioned my CLI. I don't have to get really into the technicalities as a user. I just asked it to to encrypt my API key. it tells me to copy it on my clipboard and actually in this instance I have it in a in a file in clear so I just tell it it's in this file and it goes ahead and encrypts it thanks to the decryption key and encryption keys it has access to it deletes the original file and from now on I don't really need my ledger device. My agent can you know decrypt and encrypt access tokens as as it sees. password is also protected in the matching key chain here. So that's an extra layer of of security. and I just asked it for the purpose of the demo to show that it hasn't compromised that entropic API key or or consumed it in any shape or form. so here it goes thinking before it gives an answer. decrypts the secret and if all goes well, it shows that essentially the the agent is able to decrypt decrypt this securely. Okay. Boom. So it it did get the 200 status from Enthropic. So it was able to authenticate and use that API key and and temporarily use that secret without ever you know reading it or or consuming it or leaking it. so I ask it to prove it again just by running this this command above and it does confirm that indeed it's not in in the history or or the or the memory of the agent. So essentially it was able to use that encrypted secret securely by decryptting on the trust chain and and not consuming it's its plain text version.

**[12:52] Why Secure Secrets Matter for Agents**

That's it for the demo. It's it's quite straightforward here because I'm I'm proactively talking to my cloud code agent for for the purpose of the demo. But you know when it gets really interesting is when your agent does autonomous work for you. So you can imagine open claw or or grockbot or airmes they will need to access those secrets on a on a on a more regular basis and and accessing and using the secrets on a on a in a secure way is is ever more relevant today. All right.

**[13:27] Ledger Hackathon Tracks**

>> So yeah and this brings us to the tracks for for this hackathon. So as you know there's two tracks. So we have one called AI agents X ledger. So it's about starting something new during the hackathon. Pretty straightforward. And we have a continuity track which is basically extending a project you have already but finding use cases for the agent stack and the tooling Oscar just showed you. so here are a few examples. We do have a page as well which is linked at the end of this deck. on the developer portal at ledger the documentation for developers. you have a brand new page with all of this inside.

**[14:04] Giving Agents Access Without Keys**

essentially the key message here is that you want to bring use cases where you know agents don't store passwords directly because we saw that agents can get compromised and you don't want a compromised agent giving out all your passwords for every service you ever use. So the idea is like what can you build during this hackathon where you give the agent permission to use your keys without giving it your keys directly. so this one is highlighted here. on the right top right we have you know obviously key ring sorry obviously ledger devices need to be plugged into your to your machine in order to work. so the idea is to

**[14:44] Remote Agents and Hosted Machines**

implement key ring basically in a machine where you can't. So this can be a VPS you know a CI runner anything hosted that doesn't have direct access to your device. This is also very interesting. we have the more traditional use cases on the bottom. you know agents that pay for APIs tools. So you may be familiar with X42 for example. so the idea here is that how can you you know how can you add ledger in the flows for autonomous payments or payments under certain conditions. This is also very useful and and interesting. And the last one which is more of a global one is it kind of summarizes the whole idea here is that you know the

**[15:24] Keeping Humans in the Loop**

core message is human in the loop like you want the agentic world to continue doing it thing but you want the human in the loop for approving high-risk actions moving funds. So there's many ideas here too. You can imagine some thresholds you know having a platform where after a certain threshold or amount you know you get in the loop and as a human you validate certain actions. It's voluntarily global at this slide. We don't want to get too much into detail because you know giving creativity its own place, but there's a lot that can be done with a ledger device. Always keeping the human in the loop when it matters most. so for this track here,

**[16:01] New-Project Track Prizes**

we have $2,000 for the first place and and five no one $1,000 for the second place and 500 for the third place. So three winners here. and

**[16:13] Continuity Track and Integrations**

this brings us to the second track which is continuity. we have two prices here 1,500. so this is more like you know continuing what you what you've built. for example you may have a product and you want to add ledger to it. also very interesting but there's device management skill device management kit skills that can allow you to very easily connect Ledger devices to your existing apps. we've made things simple for you to really integrate Ledger easily. So you know if you look at hackathons a year or two years three years back it was more of a challenge for developers. Nowadays it's so simple not only because of AI but because of the things we allow you to do with AI and the libraries we put into your hands like like Oscar showed you for the wallet for the key ring and and so forth. so you know make wallet CLI ring the key back end for the environment. We we talked about this you know having not having the passwords and all your credentials in the end files but protecting them. we also have things you know device confirmation when it matters of in typical flows of your product. And finally, feel free to look at the repos we have. We have many public repos. You know, you can publish a PR on any pretty much anything we do that you think would be useful. And this also is part of this. It's continuity for us for for the ledger packages, but it doesn't have to be only Europe. You can you can of course participate in the open source initiatives we we do.

**[17:42] Judging Criteria and Documentation**

so what we like in general this is more general but obviously the the boundary between what is autonomous and what needs your approval has to be clear because we're talking about agentic with human in the loop flows you know real ledger integrations and that that makes sense essentially and we do need to be able to try it. We will try it. We will render code. and if you can also explain when you pitch you know what the before and after like what Ledger did in your product. How did Ledger make your product better? make it easy for us to understand the added value of Ledger here. we do request if you can to submit a documentation feedback too because we have a the developer portal as I mentioned the developer for documentation for developers that we continuously improve and your feedback is so useful for improving this. So if you can share a bit of experience, doesn't have to be very long, a simple page would do, but you know, how did you find using the tools Oscar just presented? Are there any gaps? Did you struggle with this or that? basically anything. Feel free to do pull requests as I mentioned before. But yeah, if you can include the documentation feedback or some feedback, it would be nice for us to improve for the for the future hackers.

**[18:53] Developer Resources and Quick Links**

and yeah, I did mention a QR code. So the all the info we presented here is on the page here developers.ledger.com/eonline. The QR code will take you there. It has the tracks, all the prizes and quick links to the right sections of the documentation. So very practical. You have all the commands that you need. Pretty much everything to get started here. Thank you very much. Amazing. Thank you for this very very nice workshop. There are a few questions in the chat. Sure.

**[19:27] Fraudulent Contract Check Q&A**

>> Can read them out for you if it makes it easier. How does fraudulent smart contract check work from Alex? 
>> Yes. great question. So I think you're referring to transaction check. it's a it's a service we launched in in May of last year. and essentially what it does is it uses a a few thirdparty providers including blockade and cyers to simulate the transaction. There's a bunch of other things that happen in the background like checking if if the if certain addresses are are somehow linked to fraudulent addresses. but it's actually the the one of the core feature that the those providers offer is is a scanning the blockchain and checking for any potential fraudulent behavior. There's a there's a bunch of rules that they put in their own algorithms. But what we do on the ledger side is is quite unique because we offer first of all multiple provider simulations in parallel which is I think unique in this industry. Usually you would rely on on one provider. So if any of the provider fails you know the other one can can can can show the and flag a thread for the other and the second thing which is important is that those simulation results are not shown on the software side but on the hardware side. So you know it makes it much more secure and cannot be tempered with if you imagine very sophisticated attack scenarios. you know sometimes the front ends are are hacked by those same hackers to say that the transaction itself. Well in this instance it goes directly to the ledger device your you know your surfer because if there's actually a threat it will show there and not on your smartphone or your computer. And it's yeah just to add to that it's also an optional feature and it's very nice because you can also see the reasons why something has been flagged as malicious and you can choose you know do I want to continue despite the risk or do I want to reject you know so we give control to the user and you always in control of whether you sign or not it's just an added information of like okay wow I'm I'm about to interact with something that was flagged as malicious 
>> y all optional and and it's only for comfort of the users. Yeah, one final thing on this one. It's only available on our latest devices, so touchcreen devices like the Ledger Stacks, Ledger Flex, the Ledger Nano Gen 5, not on Nanos if you're using a nano, but you can also simulate this through different toolings, playgrounds, software simulators. Okay, awesome. Yes.

**[22:07] API Key and Bug Report Questions**

>> Next question. was that API key retrieval demo based on Mari from can this year? I'm not familiar with Macki from CAN. Are you a 
>> No, I'm not. I'm not so familiar with this. 
>> no, but I look it up. 
>> Yeah, it might have been like a hackathon project for the CA hackathon. Okay. Anorak is asking where is the where's the right place for Ledger keyring protocol questions and bug reports, GitHub issues, leedger live, discord or security contact. I have two reproducible findings in the permission handlings. 
>> Okay. yeah so actually in the page that you see here in the background with the QR code there is a a group chat at the bottom. I think this is I mean of course direct direct message is also possible but this is kind of like the the the the place to to talk to the whole team that will that will help you guys. So yeah I think starting from here would be would be very nice actually. But thank you. 
>> Cool. 
>> I think ROM reactor might have a question.

**[23:11] Nano X and Keyring Security Q&A**

>> yes. Can you guys hear me by by the way? 
>> Yes. Yeah. 
>> Cool. Cool. yes. So, I just have like one simple question and kind of a followup just u get a more like understanding of the project I want. But the simple question is would the Ledger Nano X be capable to initialize the ring CLI and the the encryptions and decryptions? 
>> Okay. So, that's good. and then the follow-up question is I also during this hackathon this was one of the ideas we were trying to build. Obviously you know like having agents access to your keys is is a serious security issue and I just wanted to get like a more understanding of how the ring CLI is able to encrypt and decrypt because at the end of the day it kind of looked like at the presentation you showed me that clot still kind of had access to the raw text of the within its context file to initiate initiate or is that wrong? Is it does it never does the API never go to the context of the the cloud while it's generating or reasoning or whatever? 
>> So so here I'd say both the ring CLI and open PGP device apps are two primitives to encrypt and decrypt secrets. They do work differently. I'm I'm talking about Open PGP because it's the device app you can find in the developer settings that allows you to ensure that you know everything is only decrypted or encrypted if you have your ledger plugged in and and sometimes if you approve on your device and all that can be configured through the app. and that's and that's quite useful for certain types of secrets but the the ring CLI in itself works very differently. It works on the the keying protocol that we also use at ledger to essentially encrypt ledger account information on on ledger wallet. and that doesn't happen with a device plugged in and and and formal

**[25:07] Trust Chain Authorization Model**

validations on the device. It happens you know through through the trust chain with a with a simple web connection. so what actually happens is that you use your device to provision a certain machine with the rights to encrypt decrypt those those secrets whatever they are. And so your ledger hardware serves as the root for that for that authorization. But then once you're initialized you know the agent in effect can can decrypt or encrypt autonomously and it's more fitted for an agentic workflow and and things that are that you want to protect but are relatively I mean they're less sensible than transactions like accessing API keys to to do a request with cloud or something like that. the one thing I'll add is that on top of that there's like a number of additional layers of security we've added. And so for your agent to access that and to essentially decrypt a secret, there's also like a a password that's tied to your machine's OS. so you know there's a there's a number of things there, but I'll let you also test on your own. So in in summary, so the like basically the agent contacts a computer server somewhere. That computer has the CLI ring built in into it connecting with the trust chain. So the the agent is simply just asking the machine like hey here I have the approval from the user to do something. here's like the signature I received from the le ledger or it could be like a world ID selfie check whatever that machine then does the ledger encryption decryption does whatever the agent requested sends in like a response like okay here we sent on the user with you know with the user's approval we sent on his behalf by USDC to stake or whatever and the agent just only receives that response and kind of gets back to the user saying like hey I did what you asked me to do obviously I never seen your didn't see any of your secrets because I I was just interacting with machine that has all that encrypted right in some way. That's kind of 
>> Yeah, 
>> correct. Yeah, that is also what was here, I think. And 
>> yeah, on the on the top left. Yeah, definitely. and and I I guess you know one other point is that that that server so the trust chain is actually decentralized and and and because your secrets are are encrypted via your ledger on your machine they're not you know accessible through that trust chain directly you're let's say you're a bit more like self-custodial on your secrets in that way it's all linked to your ledger hardware it's accessible through the machines that you you're self-provisioning with your edger hardware but it's not itself accessible outside of that. 
>> Awesome. Cool. Thank you guys. 
>> Yep. 
>> So very useful.

**[28:12] Closing and Final Device Notes**

>> Happy hacking. 
>> Yeah, happy hacking. And I see there was one last question on the fraudulent smart contract. it's only for ledger users. Yes. because the the simulation is on the hardware itself or the results are on the hardware itself should I say. and as I said, it's only for the latest touchscreen devices.
