# Gap: Ledger's actual stance on biometrics, liveness, face, World, "Proof of You" / "Proof of Human"

Written 2026-10-10. Resolves the disagreement between `jury-and-ledger-strategy.md` (Proof of Human is "explicitly not biometric"), `prior-art-hackathon-projects.md` (Proof of Human has "added liveness verification") and `walkthrough-video.md` (Oscar Chaix "agreed" to a World ID selfie check). Every claim below is tagged VERIFIED (read in the named source) or INFERRED.

## 0. TL;DR

- No Ledger primary source (blog, shop, Academy, press release, Rogers' blog/podcasts) ever describes Proof of Human or Proof of You as biometric, face-based, or liveness-based. VERIFIED by absence across 12 Ledger-authored pages (section 2).
- The "not biometric, not social reputation, unlike World" line is DL News's paraphrase of Rogers, not a direct quote. Rogers' direct quotes are: "It links human attestation to the secure element inside a Ledger device", "Each attestation confirms that a unique, verified individual is authorising or controlling an agent's actions", "We're not trying to prove the identity of the whole world". VERIFIED. Direction of the jury note is right; its wording ("explicitly") overstates.
- The "added liveness verification" line comes from thirdweb's blog (author "Firekeeper", thirdweb staff), cites no Ledger source, and no Ledger page uses "liveness" for Proof of Human. The only Ledger use of "liveness" is a glossary definition meaning "acting in the present moment" (presence), not a camera check. VERIFIED. The prior-art note's "VERIFIED" tag on that fact is wrong: it verified that thirdweb said it, not that Ledger did.
- Rogers' own definition of Proof of Human, in his words: "Every time you connect a Ledger, it phones home to an HSM which checks: 'Is this the firmware I'm expecting? Is this the chip I'm expecting?' That gives you proof of human. It's the basis for our technology for proof of human." (Dialectic podcast, Aug 2026). VERIFIED. Proof of Human = genuine check + Secure Screen approval, i.e. "a physical human holding a specific device".
- Ledger Academy's own positioning is complementary to World, not hostile: "A Ledger signer is the presence-and-consent layer, not the uniqueness layer." World is described neutrally as establishing uniqueness "through iris biometrics". VERIFIED. No partnership with World found; no formal criticism beyond a 2025 Academy explainer that relays regulators' privacy concerns. VERIFIED by search.
- The Cambridge post lists "biometrics" as a fireside-chat topic without taking a position, and records a student's challenge ("renting proof-of-humanity to an agent") that "made me pause", with no answer. VERIFIED. The author (Ariel Wengroff) is not a juror.
- Oscar Chaix's "Yeah, correct" in the walkthrough Q&A answers the attendee's architecture summary (agent talks to a provisioned machine that holds the secrets). The attendee's "or it could be like a world ID selfie check whatever" is an aside inside that summary. Chaix is not a juror. Reading it as Ledger endorsing face checks is overreach. VERIFIED (transcript in `walkthrough-video.md` lines 340-350).

Verdict on framing: section 5.

## 1. What each disputed note got right and wrong

| Note | Claim | Status |
| --- | --- | --- |
| jury-and-ledger-strategy.md | Proof of Human is "explicitly not biometric and not social reputation" | Direction right, attribution wrong. It is DL News's paraphrase ("Rogers says..."), not a Rogers quote. Rogers' quoted words only say hardware-anchored + unique individual + "not trying to prove the identity of the whole world". |
| jury-and-ledger-strategy.md | Rogers "will likely be allergic to biometric-gating as proof of human" | INFERRED, still reasonable. Supported by: Ledger Academy calling biometric logins software "with weaknesses" that deepfakes "can in some cases... fool"; Rogers' repeated line that the only thing that counts is approval on secure hardware; HACKATHON.md: "in hardware rather than in software that can be rewritten remotely". |
| prior-art-hackathon-projects.md | Roadmap Proof of Human has "added liveness verification" (VERIFIED, thirdweb) | Mis-tagged. thirdweb said it; Ledger never did. Downgrade to INFERRED/third-party. |
| prior-art-hackathon-projects.md | Shop page lists "Proof of You" | VERIFIED. Shop text: "Proof of You (Coming Soon): Credentials to confirm human (and eventually agent) identities". No biometric wording. |
| prior-art-hackathon-projects.md | "A face-gated Ledger flow is on-strategy for the usefulness criterion" | Not supported. Face-gating is nowhere in Ledger's stated strategy; the strategy is hardware attestation. Face as a UX layer is tolerated at best (section 5). |
| walkthrough-video.md | Chaix agreed to an architecture that included a World ID selfie check | Transcript confirms the "Yeah, correct" is to the machine-does-the-decrypt summary. The note's own INFERRED caveat (line 74) is right. Not jury evidence. |

## 2. Primary sources, with quotes

### 2.1 Ledger blog: "Securing Your Agents With A Hardware Root of Trust: Ledger's 2026 AI Security Roadmap" (Ian Rogers, 2026-04-14)
https://www.ledger.com/blog-2026-ai-security-roadmap  — VERIFIED (read twice, full text)

- Roadmap: Q2 2026 Agent Identity, Agent Skills & CLI; Q3 2026 Agent Intents, Agent Policies; Q4 2026 Proof of Human.
- Proof of Human (Q4): "As agents become indistinguishable from humans, platforms need a way to verify the 'principal' behind the curtain." "We are delivering progressive attestation to prove that a real, unique individual is behind an agent interaction, preventing multi-accounting and bot-spam at the hardware level."
- Proof of You: "Five years ago we already knew at Ledger that crypto was the first step towards a greater journey", which Ledger "now call[s] Proof of You". Proof of You is the umbrella (identity beyond crypto); Proof of Human is the Q4 primitive under it.
- Developer questions: "Am I talking to the agent I think I'm talking to?" (Solved by Agent Identity). "How does my agent know it is actually me issuing a command?" (Solved by Proof of You/Human). "How can my agent work autonomously but keep me in the loop for what matters?" (Agent Intents). "How do I govern a fleet of agents?" (Agent Policies).
- Agent Identity: "your agent gets a real identity and wallet anchored to Ledger hardware", registered on-chain.
- Words absent from the whole post: biometric, liveness, face, selfie, World, Worldcoin, reputation, privacy (body).

Takeaway: "How does my agent know it is actually me issuing a command?" is exactly idea 1's question, and Ledger's answer is Proof of You/Human = hardware attestation, not a camera.

### 2.2 Shop page: Ledger Agent Stack
https://shop.ledger.com/pages/ledger-agent-stack  — VERIFIED

- "Proof of You" tile, labelled Coming Soon: "Credentials to confirm human (and eventually agent) identities".
- "Agent intent & policies" tile, Coming Soon: "Async, queued approvals. Bounded autonomy. Crypto first, then beyond".
- Tagline structure: "Agent -> Human -> Ledger signer"; "Agents propose / Humans approve / Hardware enforces".
- Security Key tile: "You, the human in the loop must open sessions".
- Absent: Proof of Human, biometric, liveness, face.

### 2.3 DL News: "Ledger now has a chief human agency officer to prove you're not AI" (Tim Craig, 2026-04-14)
https://www.dlnews.com/articles/people-culture/crypto-wallet-firm-ledger-unveils-ai-roadmap/  — VERIFIED

Direct Rogers quotes:
- "The biggest threats come from AI systems being granted too much access to sensitive credentials, wallets" [and financial decisions].
- "These agents are only growing in number and can act incredibly fast, which is great until something goes wrong."
- "If they're not tightly permissioned and authenticated, attackers can hijack them or trick them into doing the wrong thing."
- "It links human attestation to the secure element inside a Ledger device,"
- "Each attestation confirms that a unique, verified individual is authorising or controlling an agent's actions" [without exposing personal data].
- "We're not trying to prove the identity of the whole world,"

Reporter's framing (not quotes):
- "Ledger will also create a so-called Proof of Human system to separate AI agents from humans."
- "...designed to combat bot-spam and multi-accounting".
- "World, a crypto firm backed by OpenAI co-founder Sam Altman, has since 2019 worked on a system that uses biometric data"; "Several regulators worldwide have banned World from collecting biometric data".
- "Rogers says Ledger's Proof of Human is hardware-based and does not rely on biometrics or social reputation, unlike World's system." (paraphrase)

INFERRED: "the identity of the whole world" is a deliberate play on World. Rogers is distancing from World's goal (global uniqueness registry), not announcing a biometric alternative.

### 2.4 Forklog: "Ledger Unveils Security Roadmap for the Age of AI Agents" (2026-04-14)
https://forklog.com/en/?p=96178  — VERIFIED (secondary)
- "Proof of Human — a mechanism for confirming the unique identity behind an agent." "The goal: to combat bots and multi-accounting." "Certification is tied to the Secure Element and does not disclose personal data (planned for the fourth quarter)."
- No biometrics, no World.

### 2.5 The Block: roadmap (Yogita Khatri, 2026-04-14) and Agent Stack launch (Daniel Kuhn, 2026-07-16)
https://www.theblock.co/post/397284/crypto-ledger-ai-security-roadmap-agentic-economy-human-loop  — VERIFIED
https://theblock.co/post/408549/ledger-unveils-hardware-backed-agent-stack  — VERIFIED
- Rogers: "My goal is to ensure humans stay in the loop through a hardware root of trust, for all important decisions."
- Rogers: "For years, we have known agents are our future co-workers." "In 2026, this has become a consensus viewpoint."
- Q4: "proof of human" features verifying "that a real person is behind an AI agent", reduce bots and multi-accounting.
- July article: roadmap "will add tools for agent identity and execution, plus 'proof of human' attestation, in the coming months". Neither article mentions biometrics, liveness, World, or Proof of You.

### 2.6 thirdweb blog: "Ledger Agent Stack: Hardware-Gated Wallet Security for AI Agents" (Firekeeper, 2026-07-18)
https://blog.thirdweb.com/ledger-agent-stack-hardware-gated-wallet-security-for-ai-agents/  — VERIFIED (third-party)
- "Proof of Human is a complementary attestation that lets a counterparty cryptographically verify" [that a real person authorized an action, not just that a signer approved it].
- "while Proof of Human aims to add an additional layer of liveness verification" [contrasted with a signer that is physically present but coerced].
- "Together, Agent Identity and Proof of Human create a verifiable chain from agent to action to human."
- The article cites no Ledger source for the liveness claim. No mention of biometrics, Q3/Q4.

INFERRED: thirdweb's "liveness" is the author's gloss on "a real, unique individual is behind an agent interaction". It is not a Ledger commitment to camera liveness. Do not cite it as Ledger's position.

### 2.7 Ledger Academy: "Ledger's Guide to Agentic AI Security: Your Agents, Your Rules, Your Authority" (2026-05-20)
https://www.ledger.com/academy/topics/agentic-ai/agentic-ai-security-guide  — VERIFIED
- Proof of Human: "A verification primitive that produces cryptographic evidence that a specific action was reviewed and" "confirmed by a physical human holding a specific device, not an automated process."
- Secure Screen: "you produce something no AI agent can generate remotely: proof that a human in possession of the device reviewed and authorized the action."
- Agent Identity: "anchored to the Secure Element chip" "Rather than software credentials that can be stolen or spoofed".
- Agent Intents: "agents propose actions that you review on a Trusted Display".
- Section heading: "Human authority must be enforced at the hardware layer, not asserted in policy."
- Grok prompt-injection case (May 2026): "The system lacked any human-in-the-loop verification for a high-value, irreversible action."
- Absent: biometric, liveness, face, World.

### 2.8 Ledger Academy: "Proof of Personhood" (2026-05-22)
https://www.ledger.com/academy/topics/digital-identity/proof-of-personhood  — VERIFIED
- Key takeaway: a Ledger signer is a cryptographic "Proof of You"; Secure Element + Secure Screen "create a hardware-level root of trust" so only the owner can give digital consent.
- Section 3 title: "How a Ledger Signer Becomes Your Digital Fingerprint". The signer is "your digital fingerprint".
- On biometrics: "biometric logins" listed among software defenses with weaknesses; a deepfake "can in some cases... fool biometric systems"; AI can "generate your face from a handful of photos"; proving humanity once relied on "A face, a voice, a signature" (framed as no longer sufficient).
- Section 2 title: "Why Your Phone Screen Can't Verify Your Human Intent".
- Absent: World, Orb, iris, liveness.

Takeaway: Ledger's house content explicitly ranks face/voice below hardware and treats them as deepfake-able. A pitch that says "face = security" contradicts Ledger's own Academy.

### 2.9 Ledger Academy: "Bot-Proofing the Web: Why Proof of Personhood Is the New CAPTCHA" (2026-07-15)
https://www.ledger.com/academy/topics/agentic-ai/bot-proofing-web  — VERIFIED
- "personhood systems establish that one human equals one identity"; "a Ledger signer confirms that this specific human approved a given action."
- Liveness (glossary): "The property that a proof reflects a real person acting in the present moment." Presence: "the proof that a real person is acting in the moment."
- World establishes uniqueness "through iris biometrics"; Humanity Protocol uses palm recognition. Neutral tone.
- "A Ledger signer is the presence-and-consent layer, not the uniqueness layer."
- Absent: World ID, face, proof of human.

Takeaway: this is the most precise Ledger statement. Uniqueness (World, Humanity) and presence/consent (Ledger) are different layers. Ledger does not claim uniqueness today and does not attack biometric uniqueness providers. "Liveness" in Ledger's vocabulary = temporal presence, which the device tap already provides.

### 2.10 Ledger Academy glossary: "Proof of Humanity"
https://www.ledger.com/academy/glossary/proof-of-humanity  — VERIFIED
- Methods include "Biometric Proofs: Palm scans, facial recognition", "increasingly powered by zero-knowledge proofs".
- "biometric-heavy implementations like Worldcoin (iris scans)", "Humanode (facial recognition)", "often combined with zero-knowledge Proofs to preserve privacy".
- "Your signer (hardware wallet) anchors PoH credentials", "ensuring your unique human authority cannot be spoofed by software agents".
- "Agentic AI and autonomous agents can create thousands of digital profiles in seconds".

### 2.11 Ledger Academy glossary: "Agentic Identity"
https://www.ledger.com/academy/glossary/agentic-identity  — VERIFIED
- "an agentic identity is tethered to a human or organizational owner" via "a parent-child relationship between the agent's DID and the owner's primary identity".
- ERC-8004: Identity Registry "links the agent's unique identity to its human controller"; Reputation Registry = "portable, cryptographically signed feedback"; Validation Registry via ZK/TEE.
- No biometrics, no Ledger hardware mention.

### 2.12 Ledger Academy: "What Is Worldcoin?" (vineet.nair, 2025-06-25)
https://www.ledger.com/academy/topics/digital-identity/what-is-worldcoin  — VERIFIED
- Relays criticism: data "never truly deleted"; EU regulators' concerns about "Worldcoin's privacy and data practices"; "Unlike passwords, iris patterns are unique and unchangeable, making them a permanent identifier"; "this biometric database could be exploited for mass surveillance"; risk of exchanging "highly sensitive biometric data for crypto".
- Commercial angle: "for maximum security, it is recommended to store WLD on a hardware wallet like a Ledger device."
- No partnership, no formal Ledger position statement.

### 2.13 Ledger blog: "Ledger N3xt at Cambridge – New Laws of Financial Gravity" (Ariel Wengroff, EVP Marketing & Comms, 2026-05-15)
https://www.ledger.com/blog-ledger-n3xt-cambridge-university  — VERIFIED
- "We covered agentic AI, digital identity, biometrics, the tension between proof-of-humanity and proof-of-ownership." "The room followed every turn."
- George's question: whether Ledger is moving toward managing human identity, "And if so, is it more about protecting humanity, or controlling who has access to that identity in a decentralised world?" Wengroff: "sits at the exact intersection where Ledger actually operates".
- "Another student asked whether renting proof-of-humanity to an agent creates a structural vulnerability," "essentially asking whether Ledger's model survives the economics of identity markets." "That one made me pause." No answer recorded.
- "people building fractured digital selves" "that no single verification layer can reconcile."
- Wengroff is not on the jury. Biometrics is listed as a topic, with no stance.

Takeaway: the live question in Ledger's own circles is "can an agent rent a human's proof-of-humanity?", i.e. delegation and revocation of attestation. That is a far better hook for a hackathon project than "add a face scan".

### 2.14 Dialectic podcast #54 "Ian Rogers - Never a Spectator" (Jackson Dahl, 2026-08-11)
https://newsletter.dialectic.fm/p/ian-rogers (lessons page) and https://jacksondahl.com/dialectic/ian-rogers (transcript)  — VERIFIED
- 1:35:39: "Every time you connect a Ledger, it phones home to an HSM which checks: 'Is this the firmware I'm expecting? Is this the chip I'm expecting?'" "That gives you proof of human. It's the basis for our technology for proof of human."
- 1:35:39: "The fact that you have a secure screen... allows you to approve a complex transaction that an agent is signing."
- 1:30:37: "It's the same chip that's in your credit card or your passport." "The one in your passport protects the secrets of the government from you, by the way."
- 1:40:59: "Agents can only suggest, and every action needs to be approved". Lessons page: "An agent should suggest. A human should decide."
- 1:45:20: LLM "checked by a deterministic player in the mix, which is either a policy which has been set by a human or a human."
- 1:46:38: "AI is middle to middle. Humans are end to end." (attributed to Balaji)
- 1:57:46: "Prompt injection is a feature, not a bug." "You could do it in something like a Yubikey, which proves, 'I have possession of this Yubikey,' but it doesn't approve the transaction." "Approving on a secure screen, on secure hardware, means, 'I approved this transaction.'"
- "you get a transaction record of what was approved and by whom... Now you've got an audit trail."
- No biometrics, World, face, or passports-as-identity anywhere.

Takeaway: Rogers' mental model of Proof of Human is genuine-check (Ledger's HSM attestation that this is real Ledger silicon + firmware) plus Secure Screen approval. A webcam has no place in that model; it is "software".

### 2.15 Rogers on X (search-index snippets only; x.com, xcancel, nitter, oembed all blocked: 402/451)
- https://x.com/iancr/status/2102731008088973687 — snippet: "Ledger Wallet CLI has Ledger's 'genuine check' built in. Proof of Ledger is effectively Proof of Human today, and we will be building around this promise to make sure this stays true and Proof of Human is a primitive provided by all of Ledger's secure hardware. Point your ..." INFERRED (snippet truncated; post not read).
- https://x.com/iancr/status/2105396940599181782 — "Expanding a bit on my Bloomberg Businessweek Daily appearance yesterday." Search summary says it chains genuine check -> Proof of Ledger -> Proof of Human -> Proof of You. INFERRED (not read).
- https://x.com/iancr/status/2044050214986633324 — "Last October I stood on a stage and said 'An agentic future where we give agents our logins, credit cards, and identities is a security nightmare.' Silence. Stares. Six months later, every agent conversation comes with a security warning." INFERRED (snippet).

"Proof of Ledger is effectively Proof of Human today" is the single most useful juror line for a pitch: the device tap already is Ledger's proof of human. Anything you add in software is at most a UX layer.

### 2.16 Rogers' SXSW 2026 talk (fistfulayen.com, 2026-03-20)
https://fistfulayen.com/2026/03/20/my-talk-from-sxsw-2026/  — VERIFIED
- "That could be your logins, your data, your API keys, your identity, your money, your credit card, your crypto wallet."
- "If my agent is taking an action on my behalf, how does it know I am really me?"
- Ledger hardware is "designed to protect information, not share it".
- No biometrics, World, proof of human. Blog index (https://fistfulayen.com/) shows no 2026 post on proof of human; "Agent Payments with Ledger" (2026-02-07) opens "Agents propose. Humans sign. Your Ledger enforces." and is "a hackathon submission, not an official Ledger product". VERIFIED.

### 2.17 CEOWORLD interview (Francesco Pagano, 2026-07-24)
https://ceoworld.biz/2026/07/24/of-music-and-ai-interview-with-ian-rogers-ledgers-chief-human-agency-officer/  — VERIFIED
- "hardware at the service of people's safety, privacy and ownership." "Computers were not designed for security, so hardware matters." "machines may propose actions, but humans remain the final authority." "the question of who authorizes actions, and under what limits, will become central."
- No biometrics, identity in his answers.

### 2.18 Gen5 / OP3N 2025 press release (2025-10-23) and coverage
- BusinessWire original returned 403: https://www.businesswire.com/news/home/20251023549325/en/The-Next-Era-of-Ownership-Begins-with-the-All-New-Ledger-Nano-and-Ledger-Wallet
- Syndication read: https://www.digitalreviews.net/news/pressers/ledger-nano-gen5-wallet-enterprise-multisig-launch/  — VERIFIED: "building products to enable Proof of You and Proof of Authority at scale." Next sentence: "Ledger's secure devices, formerly known as hardware wallets, are now Ledger signers." Opening: as society moves to digital identities "challenged by AI", verifying what is true is critical. Gauthier: "The next generation of Ledger begins today." Rogers (then CXO): "Ledger's dedication to security and ownership hasn't wavered in eleven years." No deepfake or biometric wording.
- The Block (James Hunt, 2025-10-23) https://www.theblock.co/post/375102/ledger-nano-device-wallet-app  — VERIFIED: "Ledger's hardware wallets will now be known as Ledger signers" "aligns with their broader role in protecting digital identity"; section "Proof of Authority beyond the individual" (= Enterprise Multisig). No biometric.
- Bitcoin Magazine (Juan Galt, 2025-10-23) https://bitcoinmagazine.com/business/ledger-nano-gen5-debuts-affordable-hardware-security-for-ai-driven-digital-identities  — VERIFIED: reporter's words: "multiple image generation models have shown sufficient quality to fool identity systems"; "The only viable solution to the problem of digital identity is strong cryptography". Only Gauthier quoted, on the device, not identity.
- Hypebeast recap (2025-10-29) https://hypebeast.com/2025/10/ledger-op3n-2025-nano-gen5-wallet-unveiling-event-recap  — VERIFIED: no identity/biometric content at all; panels on "the future of Crypto, privacy, and AI in the real world".

Takeaway: "Proof of You" was coined at OP3N 2025 as the identity umbrella; "Proof of Authority" = multisig/enterprise. Neither was ever defined in biometric terms.

### 2.19 Walkthrough video Q&A (YouTube 328z0_foOi4, 23:11-28:04)
https://www.youtube.com/watch?v=328z0_foOi4  — VERIFIED via transcript captured in `research/walkthrough-video.md` (lines 340-350)
- Attendee: "the agent is simply just asking the machine like hey here I have the approval from the user to do something. here's like the signature I received from the ledger or it could be like a world ID selfie check whatever that machine then does the ledger encryption decryption ... and the agent just only receives that response". Chaix: "Yeah, correct." then continues about the trust chain being decentralised.
- Chaix (Ledger product, not a juror) is confirming the Key Ring architecture. The selfie aside is the attendee's. Nothing in the video positions Ledger on biometrics.

### 2.20 Developer docs overview
https://developers.ledger.com/docs/ai-tools/overview  — VERIFIED: no mention of Proof of Human, Proof of You, identity, biometric, liveness, genuine check. Proof of Human has no developer surface as of today. Agent Intent exists (beta, per `jury-and-ledger-strategy.md`).

## 3. Has Ledger partnered with or criticised World?

- Partnership: none found. Searches for "Ledger World ID partnership/integration", "Ledger Worldcoin 2025/2026" return only the Academy explainer and unrelated World infra partners (Alchemy). VERIFIED by search (absence).
- Criticism: no formal Ledger statement. The Academy "What Is Worldcoin?" article relays regulator and privacy criticism in a neutral-explainer voice and ends by recommending a Ledger for WLD storage. DL News attributes a contrast to Rogers (paraphrase); Rogers' quoted line is "We're not trying to prove the identity of the whole world". The July 2026 Academy article treats World as the uniqueness layer Ledger does not provide. VERIFIED.
- INFERRED net position: Ledger is deliberately not competing with World on uniqueness and is deliberately not adopting biometrics; it brands itself as the "presence-and-consent" layer underneath any personhood system. Hostile to biometrics as a defence (Academy), agnostic about biometrics as a uniqueness source elsewhere.

## 4. What "liveness" means in each source

| Source | Word | Meaning |
| --- | --- | --- |
| Ledger Academy bot-proofing (Ledger) | liveness | "a proof reflects a real person acting in the present moment" (temporal presence) |
| thirdweb (third party) | liveness verification | unexplained; implied anti-coercion/"real person right now" |
| prior-art note (ours) | liveness | read as camera liveness/face anti-spoof |
| Starter idea 1 | face scan | biometric identity + liveness |

Ledger's device tap already satisfies Ledger's own definition of liveness. A webcam liveness check duplicates it in software.

## 5. Verdict: how to frame (or drop) a face/liveness step

Do not gate the transaction on a face scan and do not call it proof of human, proof of you, biometric security, or liveness. Every Ledger primary source defines Proof of Human as hardware attestation ("a physical human holding a specific device", "phones home to an HSM", "Proof of Ledger is effectively Proof of Human today"), Ledger Academy explicitly ranks biometric logins as deepfake-able software, Rogers' whole thesis is that "software that can be rewritten remotely" cannot be the authority, and the brief repeats it. A face-gated flow invites three jury questions you cannot win: "how is this not World ID?", "what does the camera add that the Secure Screen tap doesn't?", and "what happens when the webcam is spoofed?" If a face step stays, demote it to a local, optional, clearly-labelled UX layer: it selects which enrolled user's contact book and spending policy the agent loads, personalises the voice session, and writes a line in the audit log ("face profile 2 requested, device approved at 14:04"); the Ledger tap remains the only consent and the only security claim, and the pitch says that sentence aloud. Better still, swap the face step for something in Ledger's own roadmap vocabulary: use the device genuine check / Agent Intent as your "Proof of Human" and spend the saved day on the Cambridge question Ledger admits it has no answer to, "can an agent rent a human's proof-of-humanity, and how does the human revoke it?" (bounded, time-limited, hardware-approved delegation with revocation). That is on-strategy, novel, and lets you quote Rogers back to Rogers instead of arguing with him.

Concrete pitch wording that is safe:
- "Your Ledger is the proof of human; Ledger's own words: 'Proof of Ledger is effectively Proof of Human today.'"
- "The camera is not security. It decides whose policy loads. Nothing moves without the Secure Screen tap."
- "We are the presence-and-consent layer, not the uniqueness layer" (Ledger Academy, July 2026).

Wording to avoid: "biometric authentication", "face-verified transactions", "proof of personhood", "like World ID but with Ledger", "liveness check secures the payment".

## 6. Gaps and contradictions

- Rogers' X posts could not be read (x.com 402, xcancel 451, nitter shut down 2026-10-10 by X cease-and-desist, threadreader empty, publish.x.com oembed 402). The "Proof of Ledger is effectively Proof of Human today" quote is from a search-engine snippet; a human with an X account should confirm the full text before quoting it on a slide.
- Bloomberg Businessweek Daily appearance (Rogers, mid-2026) not located.
- BusinessWire original press release 403; relied on two full-text syndications that agree verbatim.
- No Ledger source defines how Q4 Proof of Human will prove "unique" (vs merely "present"). Genuine check proves a real Ledger chip, not one-human-one-device; a person can own ten Ledgers. INFERRED risk: Ledger has not said how it will handle multi-device sybil, and the Cambridge "renting" question targets exactly this. Fair game to probe in a pitch, unfair to claim Ledger has solved it.
- DL News's "not biometric or social reputation" is paraphrase. Treat as reliable reporting of Rogers' stance, not as a quotation.
- thirdweb's "liveness verification" is unsourced. Our prior-art note should downgrade it.
- Walkthrough-video "World ID selfie" is an attendee's aside, not Ledger's.
- Ledger Academy agentic-ai topic hub was not enumerated beyond the three articles found; there may be further pages. Low expected value.

## 7. Sources

Ledger primary
- https://www.ledger.com/blog-2026-ai-security-roadmap
- https://shop.ledger.com/pages/ledger-agent-stack
- https://www.ledger.com/blog-ledger-n3xt-cambridge-university
- https://www.ledger.com/academy/topics/agentic-ai/agentic-ai-security-guide
- https://www.ledger.com/academy/topics/digital-identity/proof-of-personhood
- https://www.ledger.com/academy/topics/agentic-ai/bot-proofing-web
- https://www.ledger.com/academy/glossary/proof-of-humanity
- https://www.ledger.com/academy/glossary/agentic-identity
- https://www.ledger.com/academy/topics/digital-identity/what-is-worldcoin
- https://developers.ledger.com/docs/ai-tools/overview
- https://www.ledger.com/blog-ledger-agent-stack (404)

Rogers, first person
- https://fistfulayen.com/
- https://fistfulayen.com/2026/03/20/my-talk-from-sxsw-2026/
- https://fistfulayen.com/2026/02/07/agent-payments-with-ledger/
- https://newsletter.dialectic.fm/p/ian-rogers
- https://jacksondahl.com/dialectic/ian-rogers
- https://ceoworld.biz/2026/07/24/of-music-and-ai-interview-with-ian-rogers-ledgers-chief-human-agency-officer/
- https://x.com/iancr/status/2102731008088973687 (snippet only)
- https://x.com/iancr/status/2105396940599181782 (snippet only)
- https://x.com/iancr/status/2044050214986633324 (snippet only)

Press / third party
- https://www.dlnews.com/articles/people-culture/crypto-wallet-firm-ledger-unveils-ai-roadmap/
- https://forklog.com/en/?p=96178
- https://www.theblock.co/post/397284/crypto-ledger-ai-security-roadmap-agentic-economy-human-loop
- https://theblock.co/post/408549/ledger-unveils-hardware-backed-agent-stack
- https://www.theblock.co/post/375102/ledger-nano-device-wallet-app
- https://blog.thirdweb.com/ledger-agent-stack-hardware-gated-wallet-security-for-ai-agents/
- https://bitcoinmagazine.com/business/ledger-nano-gen5-debuts-affordable-hardware-security-for-ai-driven-digital-identities
- https://hypebeast.com/2025/10/ledger-op3n-2025-nano-gen5-wallet-unveiling-event-recap
- https://www.businesswire.com/news/home/20251023549325/en/The-Next-Era-of-Ownership-Begins-with-the-All-New-Ledger-Nano-and-Ledger-Wallet (403)
- https://www.digitalreviews.net/news/pressers/ledger-nano-gen5-wallet-enterprise-multisig-launch/
- https://www.youtube.com/watch?v=328z0_foOi4 (via transcript in research/walkthrough-video.md)

Blocked mirrors tried for X: https://xcancel.com/... (451), https://nitter.net/... (shutdown notice), https://threadreaderapp.com/thread/2102731008088973687.html (empty), https://publish.x.com/oembed (402).
