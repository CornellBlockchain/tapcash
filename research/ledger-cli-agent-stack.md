# Ledger CLI / "Agent Stack" — research note

Researched 2026-10-10 for the N3XT hackathon (deadline Oct 13 23:59 CEST). Desk research only: no hardware touched, nothing installed. Every fact is tagged **VERIFIED** (read in a primary source: Ledger docs, Ledger source code, npm registry, GitHub API) or **INFERRED** (my reading between the lines). Sources are numbered `[n]` and listed at the end.

## TL;DR

- "Ledger CLI" / "Agent Stack CLI" in the brief means the npm package **`@ledgerhq/wallet-cli`** (binary `wallet-cli`). "Ring CLI" / "Key Ring" means the **`wallet-cli ring`** subcommand group, not a separate tool. **VERIFIED** [2][7][13]
- Source lives in the **`LedgerHQ/ledger-live` monorepo at `apps/wallet-cli`**, Apache-2.0. The `LedgerHQ/agent-skills` repo holds only the Markdown skill files, not the CLI. **VERIFIED** [8][9][10]
- Latest release **2.9.0, published 2026-10-05** (five days ago). npm skipped 2.2–2.8 entirely: the previous public release was 2.1.0 on 2026-07-30. The docs page still says "v2.1.0". **VERIFIED** [11][12]
- Install: `npm i -g @ledgerhq/wallet-cli` (or pnpm/yarn/bun). It is a **compiled Bun binary (~108 MB) with a native Windows x64 build**; the npm launcher picks `@ledgerhq/wallet-cli-windows-x64/bin/wallet-cli.exe` on `win32:x64`. Docs say "Windows (WSL recommended)" but the code has Windows-specific WebUSB polling. No cargo/brew/binary download. **VERIFIED** [11][14][15][16]
- Transport is **USB only** (libusb via the `usb` npm package, "node-webusb" DMK transport). No Bluetooth, no NFC. The Flex's BLE/NFC is irrelevant to the CLI. **VERIFIED** [8][16][17]
- Devices: the CLI never lists models; it uses DMK, whose `DeviceModelId` enum covers Nano S, Nano S Plus, Nano X, Stax, Flex, Apex (Gen5). Key Ring needs the **Ledger Sync device app**, available for Nano S+, Nano X, Stax, Flex. Agent Intent docs explicitly list Nano S Plus and Flex as supported signers. **Both our devices should work** for every CLI command. **VERIFIED** for the enum/lists, **INFERRED** for "both work end to end" [18][19][20]
- "Secrets an agent cannot leak" means: (a) coin private keys never leave the Secure Element; the host only ever holds addresses/derivation paths in `session.yaml`; (b) Key Ring member credentials sit in the OS keychain, password-wrapped, and the AES keys derive from an LKRP root the device created; (c) Agent Intent gives the agent its own secp256k1 key in the OS keychain that can only *propose*, never sign. **VERIFIED** [8][13][21][22]
- Agents call it as a plain shell command. The skill (`wallet-cli skill install --agent claude|cursor|codex|agents`) is embedded in the binary. Claude Code needs `dangerouslyDisableSandbox: true` for USB and keychain commands. **VERIFIED** [8][13]

## 1. What the "Agent Stack" actually is

Ledger's umbrella brand, launched **2026-07-16** (SiliconANGLE, Ian Rogers quotes), first item on a 2026 roadmap published 2026-04-14 (Q2 skills+CLI, Q3 Agent Intents + Policies, Q4 Proof of Human). **VERIFIED** [4][5]

Components named on developers.ledger.com/docs/ai-tools/overview (the page says "four capabilities" then lists five): **VERIFIED** [1]

| Name in brief | Real thing | Where |
| --- | --- | --- |
| Agent Stack / Ledger CLI | `@ledgerhq/wallet-cli` | npm, source in `ledger-live/apps/wallet-cli` |
| Ring CLI / Key Ring | `wallet-cli ring init\|encrypt\|decrypt\|keys\|destroy` | same binary |
| DMK Skills | Markdown skills `ledger-dmk-implementation`, `dmk-intent-vocabulary`, `dmk-business-logic` | `LedgerHQ/agent-skills` |
| Agent Intent | `wallet-cli agent-intent …` + web app at `https://agent-intent.ledger-test.com/` (beta) | same binary + hosted frontend |
| Hardware security | OpenPGP app, Security Key (FIDO2) app | device apps, no CLI |

Also "available now" per shop.ledger.com: `ledger-enterprise-cli` and `les-multisig-cli` (institutional, separate products, not covered here). **VERIFIED** [3]

## 2. Source, package, versions, maturity

- **Source**: `https://github.com/LedgerHQ/ledger-live/tree/develop/apps/wallet-cli`. `package.json`: `"license": "Apache-2.0"`, `"engines": { "bun": ">=1.1.0" }`, built with Bunli (`bunli.config.ts` targets `darwin-arm64, linux-arm64, linux-x64, windows-x64`). Notably **no darwin-x64 (Intel Mac) target**. **VERIFIED** [8][15][16]
- **npm registry** (`registry.npmjs.org/@ledgerhq%2Fwallet-cli`): **VERIFIED** [11]
  - created 2026-05-11 (nightlies), `1.0.0` 2026-05-19, `1.1.0` 2026-07-03, `2.0.0` 2026-07-10 (adds `earn` + `ring`), `2.1.0` 2026-07-30 (adds `skill`), **`2.9.0` 2026-10-05** (adds `agent-intent`). No 2.2–2.8 on npm; CHANGELOG has them as internal releases.
  - `repository`/`homepage` fields are empty on npm, which is why web search can't find the source.
  - Platform packages: `@ledgerhq/wallet-cli-{darwin-arm64,linux-arm64,linux-x64,windows-x64}@2.9.0`. Windows package: `os: ["win32"], cpu: ["x64"]`, unpacked 108,260,902 bytes.
- **agent-skills repo**: created 2026-04-13, last push 2026-10-07, 6 stars, 4 forks, **no license file** (GitHub API `license: null`), 7 open issues/PRs. The wallet-cli skill there is auto-synced from the monorepo by a "chore: sync wallet-cli skill" bot PR (#27 open since 2026-10-07, so **the public skill may lag the 2.9.0 binary**). **VERIFIED** [9][23]
- **Maturity**: docs call it "early experimental development", Agent Intent is "beta… not a sandbox", skills "may have breaking changes". README calls v2 "stable" for USB flows. Active development: ~15 open wallet-cli PRs in the last 3 weeks (agent-intent cancel/status/intents/swap, SOL sends, speculos transport). **VERIFIED** [2][6][8][24]
- **Legal**: "AI-generated instructions may contain errors"; every tx needs physical confirmation; Ledger holds no assets. **VERIFIED** [2]

## 3. Install

Docs **VERIFIED** [2]:

```bash
pnpm add -g @ledgerhq/wallet-cli
npm i -g @ledgerhq/wallet-cli
yarn global add @ledgerhq/wallet-cli
bun add -g @ledgerhq/wallet-cli

wallet-cli --version     # docs show "wallet-cli v2.1.0"; npm latest is 2.9.0
wallet-cli --help
```

Not documented anywhere: cargo, Homebrew, standalone binary downloads, GitHub Releases. **VERIFIED (absence)** [2][8][9]

Prerequisites (docs): macOS, Linux, "Windows (WSL recommended)"; Ledger on USB with the relevant coin app installed. Monorepo README adds Linux build deps `libudev-dev libusb-1.0-0-dev` (only for building from source). **VERIFIED** [2][8]

### Windows reality check

- `bin/wallet-cli` is a Node launcher: `"win32:x64": ["@ledgerhq/wallet-cli-windows-x64", "bin/wallet-cli.exe"]`, then `spawnSync(executable, argv, { stdio: "inherit" })`. So **a Node.js install is required even though the CLI itself is a Bun binary.** **VERIFIED** [14]
- The USB layer is `usb@2.17.0` (libusb) wrapped as WebUSB (`src/device/node-webusb/NodeWebUsbTransport.ts`). It picks the vendor-class (0xFF) interface, configuration 1, endpoint 3, vendor id `0x2c97`. There is dedicated Windows code: `WINDOWS_WEBUSB_DISCOVERY_POLL_INTERVAL_MS = 1000` with `shouldUseWindowsDiscoveryPolling()` because "Windows hotplug can miss late WebUSB attach notifications". CHANGELOG 0.3.0: "Fix Windows WebUSB reconnect handling", "Fix Windows WebUSB discovery when devices are connected after wallet-cli startup". **VERIFIED** [16][17][12]
- **INFERRED**: Ledger devices expose a WebUSB interface bound to WinUSB via Microsoft OS descriptors, which is why libusb works without Zadig. Ledger Live (node-hid) holding the HID interface at the same time is a contention risk; close Ledger Live before running device commands.
- **INFERRED**: "WSL recommended" is likely a docs default, not a hard limit. WSL2 would need `usbipd-win` passthrough and would be *worse* for USB than native. Try native Windows first; fall back to WSL only if libusb fails.
- Session/state dir uses `@bunli/utils` `stateDir("ledger-wallet-cli")`, honoring `XDG_STATE_HOME` and, per a code comment, `LOCALAPPDATA` on Windows. Linux path from CHANGELOG: `~/.local/state/ledger-wallet-cli/session.yaml`. **VERIFIED** [25][12]; exact Windows path **INFERRED** as `%LOCALAPPDATA%\ledger-wallet-cli\session.yaml`.
- OS keychain via `@napi-rs/keyring` 1.3.0; skill text names "Windows Credential Manager" explicitly. **VERIFIED** [15][13]
- `WALLET_PASS` injection examples are macOS `security` / Linux `secret-tool` only; **no Windows recipe in docs**. **VERIFIED (absence)** [2][13]

## 4. Device support

- CLI code never hardcodes a model; it connects to the **first** DMK-discovered USB device (`connectFirstUsbDevice`, 60 s timeout, device id `wallet-cli-dmk`). Two Ledgers plugged in at once = undefined which one is used. **VERIFIED** [26]
- DMK `DeviceModelId`: `nanoS, nanoSP, nanoX, stax, flex, apexp`. **VERIFIED** [18]
- Ledger Sync device app (needed for `ring init`, Agent Intent approval): Nano S+, Nano X, Stax, Flex per Ledger's LKRP blog; Agent Intent docs require Ledger Sync app **1.3.0+** and list Nano Gen 5, Flex, Stax, Nano X, Nano S Plus (original Nano S excluded). **VERIFIED** [19][20]
- Coin apps that must be installed on the device, per command: Ethereum app (EVM accounts, `send`, `receive`, `earn deposit` also pulls the `Kiln` clear-signing plugin), Bitcoin app, Solana app, **Exchange app** for legacy swap providers, partner apps (Uniswap/1inch/Velora/OKX "embedded coin app" via Device Intent Executor) for DEX swaps, **Ledger Sync app** for `ring init`. `genuine-check` requires the **dashboard** (no app open) and asks "Allow Ledger Manager". **VERIFIED** [2][8][13][27]
- Nano S Plus vs Flex differences that matter: Transaction Check / simulation runs only on touchscreen devices (Stax, Flex, Gen5) per issue #21912; a Nano S Plus shows "Blind signing ahead" for undecoded `--data` calls and requires the app-wide blind-signing toggle. **VERIFIED (issue text)** [28]
- Speculos emulator transport exists as **unmerged PR #22763** (2026-09-30, `SPECULOS_API_PORT`/`SPECULOS_ADDRESS`, Stax default, `genuine-check` refuses). Not in 2.9.0, so no hardware-free dev path today unless we build from the PR. **VERIFIED** [29]

## 5. Full subcommand reference (2.9.0)

Device / Sandbox / TTY / Network columns copied from the skill's table. **VERIFIED** [8][13]

| Command | Device | Claude Code sandbox bypass | TTY | Network | Notes |
| --- | --- | --- | --- | --- | --- |
| `session view` / `session reset` | No | No | No | No | labels like `ethereum-1`, `bitcoin-native-1`, `ethereum-sepolia-1` |
| `account discover <bitcoin\|ethereum\|solana\|ethereum:sepolia\|bitcoin:testnet\|solana:devnet>` | Yes | Required | No | Yes | writes `session.yaml` |
| `receive <label> [--no-verify]` | Yes* | Required* | No | No | `--no-verify` skips device, then no bypass |
| `send <label> --to <addr> --amount '<n> <TICKER>' [--dry-run] [--fee-per-byte N --rbf] [--data 0x..] [--mode …] [--memo]` | Yes* | Required* | No | Yes | ticker mandatory; **always broadcasts** (no sign-only) |
| `balances <label>` | No | No | No | Yes | |
| `operations <label> [--limit N --cursor C]` | No | No | No | Yes | |
| `assets token <network> <contract>` / `assets token-by-id <id>` | No | No | No | No | |
| `swap quote --from --to --amount --from-account --to-account` | No | No | No | Yes | 12 providers queried in parallel |
| `swap execute … --provider <id> [--fee-strategy slow\|medium\|fast]` | Yes | Required | No | Yes | DEX providers EVM-only; RFQ falls back to Exchange app |
| `swap status --swap-id --provider` | No | No | No | Yes | |
| `earn yields [-n ethereum\|solana]` / `earn positions <label> [--fresh]` | No | No | No | Yes | |
| `earn deposit <label> --product <id> --amount [--dry-run]` / `earn withdraw …` | Yes* | Required* | No | Yes | ERC-4626 Kiln vaults, Solana staking (2-phase, `--finalize`) |
| `genuine-check` | Yes | Required | No | Yes | exit 4 if an app is open |
| `ring init [--name] [--unsecure-no-password]` | Yes | Required | Required (or `WALLET_PASS`) | Yes | Ledger Sync app |
| `ring encrypt\|decrypt --key <name> [-i f -o f]` | No | Required (keychain) | No | Yes | AES-256-GCM, stdin/stdout OK |
| `ring keys` | No | No | No | No | |
| `ring destroy` | No | Required | Required (`echo destroy \|`) | Yes | |
| `agent-intent enroll --profile <id> --name <n> [--environment staging\|production] [--expires-in 30m]` | No | Required (keychain + WebSocket) | No | Yes | **blocks** until human approves |
| `agent-intent recover --profile` / `list` / `show --profile` | No | Required / No / No | No | Yes/No/No | |
| `agent-intent sync --profile` | No | Required | No | Yes | imports Ledger Sync accounts |
| `agent-intent send --profile --account\|--from --to --amount [--token] [--description] [--fee-strategy] [--dry-run]` | No | Required | No | Yes | **Ethereum mainnet only**, never signs/broadcasts |
| `skill list` / `skill retrieve <name> [--file references/business-logic.md]` | No | No | No | No | |
| `skill install --agent claude\|cursor\|codex\|agents [--global] [--dir] [--force]` | No | No | No | No | writes `./.claude/skills/wallet-cli-usage/` |
| `skill doctor [--fix] [--force] [--global]` | No | No | No | No | exit non-zero on drift |

Global: `--output human|json`. Device commands emit a JSON event stream under `--output json` (e.g. `device-state … awaiting_approval … reason: unlock`). Broadcast prints a greppable `hash: <txHash>` line. Exit codes seen in the skill: 3 = Ledger not detected, 4 = wrong app. **VERIFIED** [8][13][12]

Unmerged (Oct 6–9 PRs): `agent-intent cancel|status|intents|swap`, native SOL `agent-intent send`, `--sign-only` is only an open issue (#22443). **VERIFIED** [24][30]

## 6. "Secrets an agent cannot leak": what that means concretely

### 6a. Coin keys (send / swap / earn)
- Device: holds the seed in the Secure Element; derives keys; renders tx fields on its trusted screen; signs only after a physical button/touch confirmation. Host receives a signature, not a key. **VERIFIED** (docs + architecture) [2][8]
- Host: `session.yaml` holds "addresses and derivation paths, not keys". `account discover` is deterministic from the seed, so a session is "not authorization, not signing material". **VERIFIED** [13][31]
- Host→device plumbing: `WalletCliDmkTransport.exchange()` sends raw APDUs through DMK `sendApdu` with a 120 s abort. Nothing cryptographic happens on the host for signing. **VERIFIED** [26]
- Caveat the skill admits: for `--data` contract calls "the CLI cannot verify the semantic correctness"; the device screen is "the last line of defense", and (issue #21912) without an ERC-7730 descriptor the device blind-signs. **VERIFIED** [13][28]

### 6b. Key Ring (`ring`) = Ledger Key Ring Protocol (LKRP), application id 17
What the code does (`src/key-ring/*`, `src/commands/ring/init.ts`): **VERIFIED** [21][22][32]
1. `ring init` prompts for a password (TTY) or reads `WALLET_PASS`; derives a wrapping key with **PBKDF2-HMAC-SHA256, 600,000 iterations, 16-byte salt** (salt stored in `session.yaml`).
2. `sdk.initMemberCredentials()` generates a **secp256k1 member keypair on the host**.
3. `sdk.getOrCreateTrustchain(deviceId, memberCredentials)` runs **on the device through the Ledger Sync app**: the device logs in (signs a backend challenge), creates or restores the trustchain root ("main secret… only the device can read"), and adds this host's public key as a member under application path 17. Device prompt text: "Connect device, open Ledger Sync app — provisioning your Ledger Key Ring…".
4. Member private key is saved **AES-GCM-wrapped under the password-derived key in the OS keychain** (`@napi-rs/keyring`); `--unsecure-no-password` stores it unwrapped. `session.yaml` gets `rootId` + `applicationPath`.
5. `ring encrypt/decrypt`: load member creds from keychain (needs password), call `sdk.restoreTrustchain()` against **`https://trustchain.api.live.ledger.com`** (network required, no device), get `walletSyncEncryptionKey`, then **HKDF-SHA256(salt="wallet-cli-domain-v1", info=<key name>) → AES-256-GCM** key. Wire format `[12-byte IV][ciphertext]`.
6. Removing any ring member (e.g. in Ledger Live's Ledger Sync settings) **rotates** the wallet-sync key → old ciphertext becomes undecryptable. Decrypt-and-re-encrypt first.

So the honest threat model: **the device is the root of trust at enrollment and recovery only**. Day-to-day, an attacker with (a) your host OS keychain session and (b) your `WALLET_PASS` and (c) network can decrypt everything without the Ledger. Ledger's own docs contrast this with OpenPGP, which needs the device for every decryption. The hackathon brief's "headless by design" is true *after* init; init itself needs the device and either a TTY or `WALLET_PASS`. **VERIFIED** facts [2][13][21]; threat-model framing **INFERRED**.

Headless gaps: member credentials live in the OS keychain, so a bare Linux CI runner needs a Secret Service provider (gnome-keyring). Agent Intent says this outright ("no file-based fallback by design"); for `ring` I did not read `keychain.ts`, so **INFERRED** that the same constraint applies. [13]

### 6c. Agent Intent (application ids 18 for the agent trustchain, 16 for Ledger Sync accounts)
- Agent has its **own secp256k1 key in the OS keychain**; `enroll` prints a signed URL + fingerprint and **blocks** waiting on an encrypted Trustchain relay (WebSocket) until the human approves on the web app with their Ledger (Ledger Sync app ≥1.3.0, Chrome/Edge/Brave WebHID or Web Bluetooth). Completion is verified via an App-18 Keycloak token and App-16 permission before anything is saved. **VERIFIED** [6][13]
- The key can only *sign proposals*; the human signs the real tx on-device with Clear Signing + Transaction Check. Revocation is two-step (Agent Intent app, then Ledger Wallet sync settings). **VERIFIED** [6]
- Backends: staging `trustchain-backend.api.aws.stg.ldg-tech.com`, production `trustchain.api.live.ledger.com`; frontend domain is `ledger-test.com` (**INFERRED**: beta infrastructure, could move). SDK is a **vendored closed tarball** `vendor/ledgerhq-agent-intent-sdk-0.0.0.tgz`. **VERIFIED** [15][22]
- Limits: Ethereum mainnet only (even on staging profile), send only (swap/SOL in open PRs), remote agents are the "recommended" target; local Claude Code/Cursor/Codex are "also supported". **VERIFIED** [6][13]

## 7. How an agent is meant to call it

- Plain shell. "Runs directly in a terminal or under any agent that can run shell commands (Claude Code, Cursor, or your own)". No MCP server exists; "MCP" appears nowhere in Ledger's docs. **VERIFIED (absence)** [1][2]
- Skill delivery: **VERIFIED** [8][2]
  ```bash
  wallet-cli skill install --agent claude      # -> ./.claude/skills/wallet-cli-usage/ (+ .wallet-cli-skill.json sidecar)
  wallet-cli skill install --agent codex       # -> ./.codex/skills
  wallet-cli skill install --agent agents --global   # -> ~/.agents/skills
  wallet-cli skill doctor --fix
  npx skills add LedgerHQ/agent-skills -s wallet-cli-usage   # without the binary
  ```
  First real command prints a one-time stderr nudge tailored to the detected agent (`WALLET_CLI_NO_NUDGE=1` disables). Agent detection lives in `src/shared/agent-detection.ts`.
- Skill rules an agent is told to follow (SKILL.md, ~45 KB): run `session view` first; never run two device commands in parallel (`[object Object]` / garbled APDU); don't kill a waiting device command; ask before retrying a device rejection; never type `WALLET_PASS` literally, only `$(…)` substitution; never print `ring decrypt` output; `--dry-run` before any `--data` send; refuse NFTs, testnet sends, L2s. **VERIFIED** [13]
- Claude Code specifics: USB and keychain are blocked by the sandbox, so the skill mandates `dangerouslyDisableSandbox: true` for every device or keychain command. Open issue agent-skills #24 argues this "normalises" sandbox-off and that `echo destroy | wallet-cli ring destroy` defeats the confirmation gate. **VERIFIED** [13][33]
- Third-party audit (Snyk via Tessl): Medium, "direct money access capability". **VERIFIED** [34]
- Ledger's own agent runs on the monorepo: `koda-apps` bot authored wallet-cli PRs; roadmap names "Koda" as Ledger's internal agentic dev tool. **VERIFIED** [12][5]

## 8. Documentation gaps and contradictions (feed these into the required DX write-up)

1. Docs show `wallet-cli v2.1.0` (and web search snippets show v1.0.1); npm is 2.9.0 and the `agent-intent` group is undocumented on the ledger-cli page except via the skill. **VERIFIED** [2][11]
2. Overview says "four capabilities", lists five. **VERIFIED** [1]
3. agent-skills README install line points at `LedgerHQ/developer-ai-skills`, a different repo name than the one you're reading. **VERIFIED** [9]
4. npm package has no `repository` field; the source is undiscoverable from npm or docs. **VERIFIED** [11]
5. "Windows (WSL recommended)" vs a shipped native `windows-x64` binary with Windows-specific hotplug code. No Windows `WALLET_PASS` recipe. **VERIFIED** [2][16][17]
6. Hackathon brief: "Headless by design" for Key Ring; reality: `ring init` needs device + TTY/`WALLET_PASS`, encrypt/decrypt need network + OS keychain + password. **VERIFIED** [13][21]
7. Skill says `--data` calls are "decoded on-device"; issue #21912 shows blind-signing without a descriptor, and no Transaction Check on Nano-class devices. **VERIFIED** [28]
8. `send` can't sign without broadcasting (#22443) and can't target a custom RPC / fork (#22444, only undocumented `EXPLORER` env). Testnet `send`/`swap` are declared out of scope by the skill even though `account discover ethereum:sepolia` works. Demoing a real signed tx therefore costs real mainnet gas. **VERIFIED** [13][30][35]
9. Agent Intent frontend is on `ledger-test.com`; beta, "not a sandbox", real funds. **VERIFIED** [6]
10. agent-skills repo has no LICENSE file. **VERIFIED** [23]
11. Swap API auth key is stored **unencrypted** in the OS keychain (`api-auth-key-<hash>`); README is candid about it. **VERIFIED** [8]
12. Analytics: wallet-cli wires `@segment/analytics-node` and `@shared/analytics` (ring init/complete, swap events are tracked). No opt-out documented on the docs page. **VERIFIED** dependency + events [15][12][32]; opt-out status **unknown**.

## 9. Implications for our hardware and the 3 remaining days

- **Nano S Plus**: every CLI command should work over USB-C. Ledger Sync app must be installed via Ledger Live for `ring init`. Expect blind-signing prompts for arbitrary `--data`. **INFERRED** from [18][19][28]
- **Flex**: same over USB-C. BLE/NFC unused by the CLI. Flex gets Transaction Check on device for sends, which makes a nicer demo. For an NFC or BLE story you must leave the CLI and use DMK (`web-ble`, `rn-ble`) or the Agent Intent web app (Web Bluetooth in Chrome). DMK has **no NFC transport** at all (`packages/transport`: mockserver, node-hid, rn-ble, rn-hid, speculos, web-ble, web-hid). **VERIFIED** [36]
- **Windows 11 host**: install Node + `npm i -g @ledgerhq/wallet-cli`, close Ledger Live before device commands, run from a native shell first. Have WSL2 + usbipd-win as plan B. **INFERRED**.
- **Claude Code as the agent**: works today via `skill install --agent claude`; expect to approve sandbox bypass per device command. Voice front-end would just be a layer that produces the same shell invocations; the device confirmation (and `receive` address verification) is the "face scan" equivalent Ledger actually offers, and Proof of Human is Q4 roadmap vapor as of today. **VERIFIED** roadmap [5]; the rest **INFERRED**.

## 10. Open questions (need hardware or a Ledger mentor)

1. Does the native Windows binary enumerate the Nano S Plus and Flex without a driver swap, and does it coexist with Ledger Live running? (Code says yes; untested.)
2. Exact Windows path of `session.yaml` and whether `WALLET_PASS` from `cmdkey`/Credential Manager via PowerShell `$(…)` is acceptable to the skill's "never literal" rule.
3. Does `ring encrypt/decrypt` on headless Linux (no Secret Service) fail like `agent-intent enroll` does, or does `keychain.ts` have a fallback? (Decides whether a "Key Ring without USB / in CI" project is even feasible as the brief suggests.)
4. Is the Agent Intent beta open to anyone, or allow-listed? Does enrolling from a local Claude Code session on Windows (keychain + WebSocket) actually complete?
5. Will the speculos transport PR (#22763) merge before Oct 13, giving a hardware-free CI demo path?
6. Does the public `agent-skills` skill match the 2.9.0 embedded skill (sync PR #27 still open)? Use `wallet-cli skill retrieve wallet-cli-usage` as the source of truth.
7. Can `EXPLORER` be pointed at an Anvil fork to demo a device-signed EVM tx without spending mainnet gas (issue #22444 says it's undocumented but exists)?

## Sources

1. https://developers.ledger.com/docs/ai-tools/overview
2. https://developers.ledger.com/docs/ai-tools/ledger-cli and the raw https://developers.ledger.com/docs/ai-tools/ledger-cli.md
3. https://shop.ledger.com/pages/ledger-agent-stack
4. https://siliconangle.com/2026/07/16/ledger-launches-agent-stack-keep-ai-agents-away-crypto-keys/
5. https://www.ledger.com/blog-2026-ai-security-roadmap
6. https://developers.ledger.com/docs/ai-tools/agent-intent
7. https://developers.ledger.com/ethonline (names "Key Ring CLI (`wallet-cli ring`)")
8. https://github.com/LedgerHQ/ledger-live/blob/develop/apps/wallet-cli/README.md
9. https://github.com/LedgerHQ/agent-skills
10. https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/package.json
11. https://registry.npmjs.org/@ledgerhq%2Fwallet-cli and https://registry.npmjs.org/@ledgerhq%2Fwallet-cli-windows-x64 (npmjs.com web pages return 403 to fetchers)
12. https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/CHANGELOG.md
13. https://raw.githubusercontent.com/LedgerHQ/agent-skills/main/skills/wallet-cli/wallet-cli-usage/SKILL.md
14. https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/bin/wallet-cli
15. https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/bunli.config.ts and package.json optionalDependencies
16. https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/embed-usb-native.ts
17. https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/device/node-webusb/NodeWebUsbTransport.ts and node-webusb-constants.ts
18. https://raw.githubusercontent.com/LedgerHQ/device-sdk-ts/develop/packages/device-management-kit/src/api/device/DeviceModel.ts
19. https://www.ledger.com/how-we-used-ledger-key-ring-protocol-in-ledger-live (2024-11-13)
20. https://developers.ledger.com/docs/ai-tools/agent-intent (Requirements table)
21. https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/key-ring/crypto.ts and load-key-ring.ts
22. https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/key-ring/constants.ts and lkrp-sdk.ts
23. https://api.github.com/repos/LedgerHQ/agent-skills and /issues
24. https://api.github.com/search/issues?q=repo:LedgerHQ/ledger-live+wallet-cli+in:title
25. https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/session/session-store.ts
26. https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/device/register-dmk-transport.ts and wallet-cli-dmk-transport.ts
27. https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/commands/genuine-check.ts
28. https://github.com/LedgerHQ/ledger-live/issues/21912
29. https://github.com/LedgerHQ/ledger-live/pull/22763
30. https://github.com/LedgerHQ/ledger-live/issues/22443
31. https://raw.githubusercontent.com/LedgerHQ/agent-skills/main/skills/wallet-cli/wallet-cli-usage/references/business-logic.md
32. https://raw.githubusercontent.com/LedgerHQ/ledger-live/develop/apps/wallet-cli/src/commands/ring/init.ts
33. https://github.com/LedgerHQ/agent-skills/issues/24
34. https://tessl.io/registry/skills/github/LedgerHQ/agent-skills/wallet-cli-usage/security
35. https://github.com/LedgerHQ/ledger-live/issues/22444
36. https://api.github.com/repos/LedgerHQ/device-sdk-ts/contents/packages/transport
37. https://developers.ledger.com/docs/ai-tools/ledger-dmk-skills
38. https://developers.ledger.com/docs/ai-tools/hardware-security/security-key and /open-pgp
39. https://www.skills.sh/ledgerhq/agent-skills/wallet-cli-usage
40. https://developers.ledger.com/llms.txt
