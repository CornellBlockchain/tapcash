# N3XT Hackathon @ OP3N 2026 — Brief

Source: Ledger / College.xyz hackathon brief (Google Doc, "Hackathon Brief" tab), captured 2026-10-10.

> Build before you land. Pitch live in Paris.

1-week remote build the week before OP3N, live finals at Ledger HQ on Friday 16 October. Every club fields one team. €5,000 cash prize across the top 3.

## The challenge

Build a project using the **Ledger Agent Stack and/or a Ledger Signer and/or Key Ring**. The project can be:

1. an AI agent,
2. an AI-powered product built on the Ledger Agent Stack, or
3. an AI-powered use case built around a Ledger Signer.

Use one or more of the Ledger tools below. Any AI model or provider works. **No tracks — one unified challenge.**

## Ways to build

Start here: https://developers.ledger.com/docs/ai-tools/overview

| Tool | What it's for | Docs |
| --- | --- | --- |
| **Agent Stack** (Ledger CLI) | Give your agent secrets it cannot leak — hardware-backed keys & credentials. | https://developers.ledger.com/docs/ai-tools/ledger-cli |
| **Ring CLI / Key Ring** | Encrypt secrets under keys derived from your Ledger seed. Headless by design — for CI & agents with no human at the keyboard. | https://developers.ledger.com/docs/ai-tools/ledger-cli#key-ring |
| **DMK Skills** | Plug a Ledger Signer into your AI agent so it can request device-backed approval. | https://developers.ledger.com/docs/ai-tools/ledger-dmk-skills |
| **Signer (DMK)** | Wire a Signer into your app so Ledger confirms high-risk actions — human-in-the-loop. | https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/how_to_use_a_signer · https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/dmk |

## Resources & docs

- Wallet integration → https://developers.ledger.com/docs/ledger-wallet-provider/overview
- Safe, readable signing → https://developers.ledger.com/docs/clear-signing/overview
- Device as a security key → https://developers.ledger.com/docs/ai-tools/hardware-security/security-key
- Encryption / signing with OpenPGP → https://developers.ledger.com/docs/ai-tools/hardware-security/open-pgp
- Discord group for questions (send organiser your Discord handle).

## Watch this first

Ledger Tools Walkthrough (Agent Stack, Ring CLI, Signer in action): https://www.youtube.com/watch?v=328z0_foOi4

Heads-up: the video was made for the public ETHOnline hackathon. Ignore its tracks, prizes and deadlines. Watch it for the tools, not the rules.

## Where this gets interesting

A signer proves that a specific human approved a specific action, in hardware rather than in software that can be rewritten remotely. That property isn't about crypto. It applies anywhere something needs to be provably authorised by a person — access, credentials, identity, an agent acting on someone's behalf, a decision that has to be attributable later.

Most existing work points the stack at wallets and transactions. The projects they haven't seen yet point it somewhere else. Non-finance ideas count.

## Project ideas (to spark yours)

- An agent that uses secrets it can never expose (hardware-backed keys via Ring CLI).
- A human-in-the-loop agent where a Ledger Signer approves any high-risk move.
- Bring Key Ring to environments without USB (headless / cloud / CI agents).
- Add a Signer or device confirmations to an app you've already shipped (disclose what existed before Oct 7 — undisclosed pre-existing code disqualifies).
- Agentic payments / agent wallets with device-backed authorization.
- A private agent end to end: a Ledger Signer for every action that matters, no secret ever leaving the device.

## What they like

- Real user value over a generic demo.
- A clear boundary between what the agent does autonomously and what a human approves — name it explicitly.
- A concrete Ledger primitive actually implemented, not mentioned.
- A practical demonstration that device-backed trust matters to your use case.
- Runnable code, or a recorded walkthrough if it won't run on someone else's machine.

## Teams

- One team per club, 2 to 4 members. Everyone from the club coming to Paris is on the team (cap 4). Leftover places can go to remote club members.
- Only two pitch, on behalf of the whole team, in the room. Remote members don't pitch and can't be dialled in. Whoever pitches answers the jury.
- Prize goes to the team, remote members included.

## Key dates (all CEST)

| Date | Milestone |
| --- | --- |
| Oct 7, 3:00 PM | Hackathon kickoff — build starts |
| **Oct 13, 11:59 PM** | **Submissions close** |
| Oct 14–15 | Review of submissions |
| Oct 15 | Finalists announced (exact time TBC) |
| Oct 16, 3:00 PM — Ledger HQ, Paris | Final pitches → winners announced right after |

## How to submit (all three required)

1. Submit through the form → https://forms.gle/TcmwuFQMGfyEcuNd6
2. Post the project on X or LinkedIn, from the club account, with **#LedgerN3XTCollab**, tagging **@Ledger**.
3. Include the GitHub repo link + a short demo video.

Form open from day one. One submission per team: edit the response rather than resubmitting. Prepare pitch slides in advance — finalists announced Oct 15, pitch Oct 16 afternoon.

## Judging & finals

Every submission scored out of 100%:

| Criterion | Weight |
| --- | --- |
| Technical execution | 25% |
| Usefulness and relevance for Ledger | 20% |
| Innovation / originality | 20% |
| User experience | 15% |
| New use cases possible for Ledger | 10% |
| Clarity, presentation and documentation | 10% |

Jury: **Ian Rogers** (Chief Human Agency Officer, Ledger), **Guillaume Mathias** (VP Product, Ledger), **Joshua Mo** (DevRel Lead @ Venice), **Drake Breeding** (Director, Ecosystem Arc @ Circle).

Finals pitch: 10 minutes — 5 min presentation, 5 min jury Q&A. Two presenters per team, both in Paris.

## Required: developer-experience feedback

Every submission includes a short write-up on what it was like to build on the stack: where the documentation lost you, which workflow was confusing, what context was missing, and one concrete suggestion. Be blunt — Dev Rel reads this first.

## Mentoring and support

~5 people from Ledger dev / product / Dev Rel on hand through build week, roughly an hour a day on working days. Mentors off Saturday and Sunday. Technical questions go to the dedicated Discord channel (ask there or open a ticket, not DMs). Weekend blockers: message the organiser on Telegram.

## IP

Team keeps ownership of everything built. Ledger takes no transfer or assignment of IP. Ledger asks for the right to show the work (project, code, description, demo video, pitch recording) on Ledger Academy and Ledger channels, credited to the team and club.

## Prizes

€5,000 across top three: **€2,500 / €1,500 / €1,000**. Paid after the event by College.xyz (same channel as travel reimbursement; may arrive as one payment itemised). Team handles distribution.

## Before you start

- Read the challenge and set up tools early — don't lose Day 1 to install issues.
- Full T&C, selection rubric and submission form "coming soon" via Discord and the brief doc.

## Our hardware

- Ledger Nano S Plus (USB-C only; no Bluetooth, no NFC, no battery).
- Ledger Flex (USB-C, Bluetooth, NFC; E Ink touchscreen; battery).
