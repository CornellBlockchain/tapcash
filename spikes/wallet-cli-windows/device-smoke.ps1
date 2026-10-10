# Run when a Ledger is plugged in (native Windows, PowerShell). Close Ledger Live first.
# Device on dashboard (no app open) for genuine-check; Ethereum app installed for discover.
# Each device command blocks until the device answers; the 60 s discovery wait is hard-coded.
$env:WALLET_CLI_NO_NUDGE = "1"
$log = Join-Path $PSScriptRoot "device-smoke.log"
"=== $(Get-Date -Format o) wallet-cli $((wallet-cli --version | ConvertFrom-Json).data.version)" | Tee-Object $log

"--- genuine-check (dashboard, expect 'Allow Ledger Manager' on device)" | Tee-Object $log -Append
wallet-cli genuine-check --output json 2>&1 | Tee-Object $log -Append
"exit=$LASTEXITCODE" | Tee-Object $log -Append

"--- account discover ethereum (opens Ethereum app)" | Tee-Object $log -Append
wallet-cli account discover ethereum --output json 2>&1 | Tee-Object $log -Append
"exit=$LASTEXITCODE" | Tee-Object $log -Append

"--- session view + state file" | Tee-Object $log -Append
wallet-cli session view 2>&1 | Tee-Object $log -Append
Get-Content "$env:LOCALAPPDATA\ledger-wallet-cli\State\session.yaml" | Tee-Object $log -Append

"--- receive --no-verify (no device prompt; drop --no-verify to test Secure Screen address check)" | Tee-Object $log -Append
wallet-cli receive --account ethereum-1 --no-verify --output json 2>&1 | Tee-Object $log -Append
"exit=$LASTEXITCODE" | Tee-Object $log -Append

# Optional, with Ledger Live RUNNING, re-run genuine-check to test HID/WinUSB coexistence:
#   wallet-cli genuine-check --output json
# NOT run here: ring init (creates a trustchain), agent-intent enroll (beta, mainnet).
