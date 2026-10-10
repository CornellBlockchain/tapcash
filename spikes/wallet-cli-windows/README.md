# Spike: @ledgerhq/wallet-cli natively on Windows 11

**Verdict: PASS for everything that does not need a device.** The npm package installs a native
`wallet-cli.exe` (Bun 1.4.2 single-file binary with libusb + WinUSB inside) and every no-device
command works from Git Bash and PowerShell. "WSL recommended" in the docs is not a hard
requirement. Device enumeration itself is **untested** (no Ledger plugged in); `device-smoke.ps1`
is ready for that.

Host: Windows 11 Enterprise 10.0.26200, Node v24.2.0, npm 12.2.0, Git Bash. Ledger Live not running.
Date: 2026-10-10. Package left installed.

## Install

```
npm i -g @ledgerhq/wallet-cli
# added 2 packages in 4s          <- tarball was already in the npm cache; cold download is ~104 MB
```

- `@ledgerhq/wallet-cli@2.9.0` + optional dep `@ledgerhq/wallet-cli-windows-x64@2.9.0`
  (registry `dist.unpackedSize` 108,260,902 bytes, published 2026-10-05T19:23:45Z).
- On-disk: `du -sh %APPDATA%\npm\node_modules\@ledgerhq` = **104M**.
- Binary: `%APPDATA%\npm\node_modules\@ledgerhq\wallet-cli\node_modules\@ledgerhq\wallet-cli-windows-x64\bin\wallet-cli.exe`
  (nested under `wallet-cli/node_modules`, not top-level), **108,226,560 bytes**,
  `PE32+ executable for MS Windows 6.00 (console), x86-64`. Strings inside: `Bun v1.4.2`,
  `bun-windows-x64`, `libusb_control_transfer` etc., `WinUSB`, `Credential Manager not available`,
  `windows-native-keyring-store`. No `node-hid`.
- `%APPDATA%\npm\wallet-cli` / `.cmd` / `.ps1` shims run `bin/wallet-cli` (Node launcher,
  `spawnSync(..., {stdio:"inherit"})`), so **Node is required at runtime** even though the CLI is Bun.
- Startup overhead: 1.2 to 3.2 s wall for `--version` (Node shim + 108 MB exe).

## Commands run and verbatim output (files `out-*.txt`)

| Command | Exit | Decisive output |
|---|---|---|
| `wallet-cli --version` | 0 | `{"ok":true,"data":{"type":"version","name":"wallet-cli","version":"2.9.0"}}` |
| `wallet-cli --help` | 0 | JSON `help` object listing `account agent-intent assets balances earn genuine-check operations receive ring send session skill swap` |
| `wallet-cli ring --help` | 0 | `init encrypt decrypt keys destroy` (no members/add/remove/rotate/backup; confirms research gap) |
| `wallet-cli agent-intent --help` | 0 | `enroll recover list show send sync` |
| `wallet-cli skill list` | 0 | `wallet-cli-usage  Official Ledger wallet-cli - ...` (one skill embedded) |
| `wallet-cli skill retrieve wallet-cli-usage` | 0 | 45,685 bytes -> `SKILL.md` (source of truth for 2.9.0) |
| `wallet-cli skill retrieve wallet-cli-usage --file references/business-logic.md` | 0 | 2,868 bytes -> `business-logic.md` |
| `wallet-cli skill doctor` | **1** | `wallet-cli-usage  missing  installed none -> shipped 2.9.0@39cea9e6  <cwd>\.claude\skills` then `1 skill(s) still drifting.` (command exists; exit 1 only means not installed in cwd) |
| `wallet-cli session view` | 0 | `No accounts in session. Run account discover first.` |
| `wallet-cli session reset` | 0 | `Session was already empty.` (this created the state dir, see below) |
| `wallet-cli ring keys` | 1 | JSON `CommandExecutionError`: `Ledger Key Ring not initialized. Run wallet-cli ring init first.` |
| `wallet-cli agent-intent list` | 0 | `No Agent Intent profiles. Run agent-intent enroll first.` |
| `wallet-cli --output human --help` | 1 | `"kind":"command-not-found" ... "message":"Command '--output human' not found"` (global flag before the command is rejected) |

### No-device error text (device commands run sequentially under `timeout 70`)

```
$ timeout 70 wallet-cli genuine-check --output json --device-timeout 15000
{"ok":false,"error":{"command":"genuine-check","code":"unknown","message":"No Ledger device found. Unlock the device and try again."}}
exit=1 seconds=61

$ timeout 70 wallet-cli genuine-check --device-timeout 10000
Connect and unlock your Ledger on the dashboard…
[✖] No Ledger device found. Unlock the device and try again.
exit=1 seconds=62

$ timeout 70 wallet-cli account discover ethereum --output json --device-timeout 10000
{"ok":false,"error":{"command":"account discover","code":"unknown","message":"No Ledger device found. Unlock the device and try again."}}
exit=1 seconds=61
```

Observations: the no-device wait is a **hard-coded 60 s** (`connectFirstUsbDevice`); `--device-timeout`
does not shorten it. Exit code is **1** with `code:"unknown"`, not the `3 = Ledger not detected`
the skill documents. The process did not hang (`timeout 70` never fired). libusb initialised fine on
native Windows (no DLL or driver error); it simply found no device.

## Where state lives on Windows

`%LOCALAPPDATA%\ledger-wallet-cli\State\` (created on first write, here by `session reset`):

```
first-run.json  {"nudgeShownAt":"2026-10-10T05:58:26.633Z","version":"2.9.0"}
session.yaml    {accounts: []}
```

`XDG_STATE_HOME` was unset; `~/.local/state/ledger-wallet-cli` was not created. Ring and agent-intent
secrets go to Windows Credential Manager (`@napi-rs/keyring`, service `ledger-wallet-cli`), not here.
`WALLET_CLI_NO_NUDGE=1` suppresses the `Tip: install the Ledger wallet-cli skill ...` banner that
otherwise prints to stdout on the first command.

## Output-format quirks (matter for agents parsing stdout)

- `--help` and `--version` print JSON when stdout is not a TTY (every `out-*.txt` shows this), while
  `skill list`, `skill doctor`, `session view`, `agent-intent list` print plain text. Inconsistent.
- `--output` is a per-command flag (`genuine-check --output json`), not global;
  `wallet-cli --output json <cmd>` fails with `command-not-found`.
- The first-run nudge goes to **stdout**, which breaks `wallet-cli ... | jq` once per machine.

## Driver situation

`Get-PnpDevice` shows **no device with `VID_2C97` has ever been enumerated on this machine**
(no phantom Ledger entries). Generic inbox `winusb.inf_amd64_...` is present in the driver store.
Ledger devices are WCID devices, so Windows should bind WinUSB automatically on first plug; libusb in
the exe then uses it. Untested here. If it fails, look for a yellow-bang Ledger entry in Device Manager;
Zadig is the last resort.

## Next steps with a device

1. Close Ledger Live. Plug in, unlock, stay on the dashboard.
2. `powershell -File spikes\wallet-cli-windows\device-smoke.ps1` (writes `device-smoke.log`):
   genuine-check -> account discover ethereum -> session view -> receive --no-verify.
3. Coexistence: start Ledger Live, re-run `wallet-cli genuine-check --output json`
   (research gap `gap-windows-hid-coexistence-ledger-live.md`).
4. Hot-plug: start `wallet-cli account discover ethereum` first, plug in after 5 s
   (exercises `WINDOWS_WEBUSB_DISCOVERY_POLL_INTERVAL_MS`).
5. Only once the device is found: `ring init` (needs Ledger Sync app) and `WALLET_PASS` from
   Credential Manager via `$(...)` in PowerShell. Not run in this spike.
6. If native USB fails: WSL2 + `usbipd-win` is plan B; everything else here already works natively.

## Files

- `install.log`, `out-*.txt`: verbatim outputs.
- `SKILL.md`, `business-logic.md`: embedded skill text from the 2.9.0 binary.
- `device-smoke.ps1`: ready-to-run device test.
