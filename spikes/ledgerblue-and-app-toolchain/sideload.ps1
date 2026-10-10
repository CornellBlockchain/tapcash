# Build (Docker) and/or sideload app-boilerplate-rust. Device must be unlocked on the dashboard, Ledger Live closed.
#   .\sideload.ps1 -Device flex -Build          # needs: docker pull ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest (multi-GB)
#   .\sideload.ps1 -Device nanosplus -Load      # host-side ledgerblue over USB HID; --elfFile sets targetId (0x33100004 / 0x33300004)
#   .\sideload.ps1 -List                        # ledgerctl list (sanity check that HID works on this host)
param(
  [ValidateSet('nanosplus','flex')][string]$Device = 'nanosplus',
  [switch]$Build, [switch]$Load, [switch]$List
)
$ErrorActionPreference = 'Stop'
$app = Join-Path $PSScriptRoot 'app-boilerplate-rust'
$py  = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$img = 'ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest'

if ($Build) { docker run --rm -v "${app}:/app" $img cargo ledger build $Device }
if ($List)  { & (Join-Path $PSScriptRoot '.venv\Scripts\ledgerctl.exe') list }
if ($Load) {
  $elf = "$app\target\$Device\release\app-boilerplate-rust"
  if (-not (Test-Path "$elf.apdu")) { throw "missing $elf.apdu - run with -Build first" }
  & $py -m ledgerblue.runScript --elfFile $elf --fileName "$elf.apdu" --apdu --scp
}
