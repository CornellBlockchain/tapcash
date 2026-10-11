# Ledger Cash on real hardware: two checklists

Written 2026-10-11 (Sunday). Nothing in this file has been run on a real device yet. Every expected screen comes
from the emulator runs (`screens/`, `screens/nano/`) and from `app/src/cash.c`. **Your job is to find out where
real hardware differs, and to send back the evidence.**

| Who | Hardware | When | Checklist |
|---|---|---|---|
| Sahas | Nano S Plus (USB only), Tangem cards, iPhone, Windows 11 PC | Sunday 11 | [A](#a-sahas-nano-s-plus-windows) |
| Collaborator | Ledger Flex (NFC), Android phone, own laptop (Windows, macOS or Linux) | Sunday 11 / Monday 12 | [B](#b-collaborator-flex--android) |
| Both | Flex + Android + Nano S Plus together | Paris only | [C](#c-paris-only-android-bridge-to-the-nano-s-plus) |

Ledger mentors are available on Monday 12 and Tuesday 13. Bring them any NO-GO from Gate 1. Deadline: Tuesday 13,
23:59 CEST.

## Shared facts

**The tool.** Use `mvp/ledger-cash/hw.py`, which talks to the device over USB through `ledgerblue`. Every command
prints the APDU it sends, the reply, and the status word (SW) with its meaning. Run `python hw.py` with no arguments
for help. It was tested against emulated devices (2026-10-11):
- On a Speculos Nano S Plus: `setup anvil`, `selfpay`, `auths`, then `settle.mjs` on anvil, which printed
  `#0 success`, and a second settle printed `REJECTED already used`.
- On the patched Speculos Flex: `tap` and `status`. The tap ended `FAILED B006` against an unconfigured payee, as
  expected.

| Command | What it does |
|---|---|
| `hw.py version` | **Run on the dashboard, with no app open.** Prints the target ID and OS version: `0x33100004` is the Nano S Plus, `0x33300004` the Flex. |
| `hw.py setup anvil [usdc]` / `setup base [usdc]` | SET_CONFIG (approve on the device), then LOAD_CASH (default 10; `0` skips it), then prints the balance. |
| `hw.py balance` | Prints the cash, the pay counter and the device's **cash account** address (`44'/1279476051'/0'/0/0`). No stock Ledger chain app can sign for it (dedicated path; a sideloaded app declaring the same path or a seed import could); it is not any of your Ethereum app accounts. |
| `hw.py selfpay [usdc] [label]` | The device pays itself: SET_REQUEST, GET_REQUEST, PAY, PUT_AUTH, then the same PAY again, which must give `B004`. |
| `hw.py auths [file]` | Reads the payee's stored auths (GET_AUTHS) into a JSON file for `settle.mjs`. The default file is `device-auths.json`. |
| `hw.py tap` | **Flex only.** Sends TAP_TO_PAY, then polls TAP_STATUS and prints every state change until the tap ends. |
| `hw.py status` | **Flex only.** Sends one TAP_STATUS. If an auth was signed, it is also written to `tap-auth.json`. |
| `hw.py raw <hex>` | Sends any APDU. |

**TAP_STATUS states:** 0 idle, 1 waiting for card, 2 busy, 3 PUT_AUTH sent, 4 PAID, 5 FAILED, 6 SIGNED BUT NO RECEIPT.
TAP_STATUS stays in RAM until the next tap or until the app is closed. It is answered even while a review is on
screen, so you can always run `hw.py status` after a tap.

**Status words:**

| SW | Meaning |
|---|---|
| 9000 | ok |
| 6985 | rejected on the device |
| 6D00 | unknown INS (TAP_* on a Nano), or not allowed over NFC |
| 6E00 | wrong CLA (not `E0`) |
| 6700 | wrong length |
| 6A80 | bad data (amount 0, bad label, balance overflow) |
| 6A82 | unknown AID |
| 6A88 | no auth in that GET_AUTHS slot |
| B001 | bad payee signature |
| B002 | not configured, or the request is for another network |
| B003 | not enough cash |
| B004 | already paid |
| B005 | bad auth |
| B006 | payee has no request |
| B007 | busy (a review is on screen) |
| B008 | card removed |
| B009 | payee did not answer |
| B0FF | crypto failure on the device |
| 511F | the device OS is too old for this app |

**The cash account.** Both ledger-cash keys (payer, and the payee's request signer) are `44'/1279476051'/0'/0/0`
(coin type `0x4C434153`, "LCAS", not in SLIP-44). The app may derive only `44'/1279476051'`, and no stock Ledger app
may derive it (no stock Ledger chain app), so the address `hw.py balance` prints is a separate account that no stock Ledger chain app can sign for. It is a
normal Ethereum address: fund it with USDC on-chain, and `LOAD_CASH` sets how much of it the device spends offline.
The addresses in `screens/` are the emulator seeds' cash accounts; yours differ.

**Builds** (Docker SDK API_LEVEL 27, which needs **OS 1.7.0** on both the Flex and the Nano S Plus; `nanos+_1.4.1` is
API 24 and gives `0x511F`). Built with the pinned image
`ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools@sha256:8d3da9179dd1b241883c769c521ee9403352b60091c80405b5bef5801a003ba2`:

| Device | Artifact | `app.sha256` (contents of the file) | targetId |
|---|---|---|---|
| Flex | `ledger-cash-flex` | `9c8cfe79ceb043e3ef728eaa12f117e8a17d92e35cb639be3fb0a0887bfbcd57` | `0x33300004` |
| Nano S Plus | `ledger-cash-nanosplus` | `4733ab55e296422951864ea7843e98f723a47004c7295c1f42cd48faa1fa10de` | `0x33100004` |

The CI workflow `device-apps` (GitHub Actions, job `ledger-cash`) builds both on every push to `ledger-cash` that
touches `mvp/ledger-cash/app/**` (or the workflow file); the push that adds the dedicated cash path touches both, so it
starts the first run. The repo is **private**, so the collaborator must accept the invitation before they can clone the
repo or download artifacts. On the
first run, check that each artifact's `app.sha256` matches the table. The `.apdu` starts by deleting any app named
"Ledger Cash", so loading again replaces an older install without a manual uninstall.

**Networks:**

| Name | chainId | Token |
|---|---|---|
| `anvil` | 31337 | `0x5FbDB2315678afecb367f032d93F642f64180aa3` (the first deploy on a fresh anvil) |
| `base` (Base Sepolia) | 84532 | Circle USDC `0x036CbD53842c5426634e7929541eC2318f3dCF7e` |

The app hardcodes the EIP-712 domain `{name "USDC", version "2"}`. **Checked on 2026-10-11** against the live Base
Sepolia contract:
- `name()` = `"USDC"` and `version()` = `"2"`;
- on-chain `DOMAIN_SEPARATOR()` = `0x71f17a3b2ff373b803d70a5a07c046c1a2bc8e89c09ef722fcb047abe94c9818`, equal to the
  hash viem computes for that domain with chainId 84532.

So Base Sepolia settlement can work with the app as built. A dry run of `settle.mjs` against Base Sepolia reached the
real FiatTokenV2 contract and was refused with `invalid signature`, which is expected for an auth signed for chainId
31337.

Raw APDUs, in case `hw.py` is not at hand (CLA E0):
- SET_CONFIG anvil: `E01200001C0000000000007A695FBDB2315678AFECB367F032D93F642F64180AA3`
- SET_CONFIG Base Sepolia: `E01200001C0000000000014A34036CBD53842C5426634E7929541EC2318F3DCF7E`
- LOAD_CASH 10: `E0200000080000000000989680`
- GET_BALANCE: `E021000000`
- TAP_TO_PAY: `E030000000`
- TAP_STATUS: `E031000000`

---

## A. Sahas: Nano S Plus, Windows

Every command runs in **Windows PowerShell**, from the repo folder unless a step says otherwise.

### A0. Unblock the collaborator (5 min, do this first)
1. The collaborator (`hrishabhayush`) was invited on 2026-10-10 with write access. Check that they accepted (no output
   from the first command, and their login in the second):
   ```powershell
   gh api repos/Sahas266/ledger-op3n-n3xt-hackathon-26/invitations --jq '.[].invitee.login'
   gh api repos/Sahas266/ledger-op3n-n3xt-hackathon-26/collaborators --jq '.[].login'
   ```
   They need access to clone the repo, download the Flex and APK artifacts, and get `hw.py` and `settle/`.
2. Check that the orchestrator's push started the CI:
   ```powershell
   gh run list -R Sahas266/ledger-op3n-n3xt-hackathon-26 -b ledger-cash -L 5
   ```
   Expected: a `device-apps` run with status `completed success`, next to the `android` runs. If none is listed:
   `gh workflow run device-apps -R Sahas266/ledger-op3n-n3xt-hackathon-26 --ref ledger-cash` works once the workflow
   has run at least once on the branch. Before that, GitHub does not know the workflow yet; push any commit that
   touches `mvp/ledger-cash/app/**` instead. If the run failed, send `gh run view <id> --log-failed` to the
   orchestrator.
3. Send the collaborator the link to this file.

### A1. Quit Ledger Wallet fully
It keeps running in the system tray after you close its window.
```powershell
Get-Process | Where-Object ProcessName -like "Ledger*"
```
Expected: no output. If anything is listed, right-click the tray icon and choose Quit, or run
`Get-Process | Where-Object ProcessName -like "Ledger*" | Stop-Process`. Run the check again. Repeat this step
whenever you have used Ledger Wallet in between (for example in A2).

### A2. Check the Nano OS version (needs 1.7.0)
1. Open Ledger Wallet, plug in the Nano, unlock it, open **My Ledger** and allow it on the Nano. The OS (firmware)
   version is shown next to the device. If it is older than 1.7.0, update it there. Write down the version.
2. Quit Ledger Wallet again (A1). A cross-check without Ledger Wallet is at the end of A3.

If the Nano is not on 1.7.0 and cannot be updated, the install in A5 will fail with `511f`. Stop there, and ask the
mentors on Monday for an SDK build for the Nano's API level.

### A3. Python with ledgerblue
Reuse the venv from the toolchain spike (ledgerblue 0.1.58 is already installed):
```powershell
$py = "C:\Users\sahas\Github Repos\ledger-op3n-n3xt-hackathon-26\spikes\ledgerblue-and-app-toolchain\.venv\Scripts\python.exe"
& $py -c "import ledgerblue; print('ok')"
```
Expected: `ok`. If the venv is missing, create a fresh one:
`py -3 -m venv $HOME\lc-venv; $py = "$HOME\lc-venv\Scripts\python.exe"; & $py -m pip install ledgerblue`.
Set `$py` again in every new PowerShell window.

Cross-check of the OS version (A2), now that `$py` exists: with the Nano unlocked on the dashboard (no app open), run
`& $py mvp\ledger-cash\hw.py version`. Expected: `target 0x33100004, OS 1.7.0`. This command has not been run on a
device. If it errors, the Ledger Wallet reading is enough.

### A4. Get the Nano build
Use one of these, in this order:
1. **The local build**, which already exists: `mvp\ledger-cash\app\build\nanos2\bin\`. Check it:
   ```powershell
   Get-Content mvp\ledger-cash\app\build\nanos2\bin\app.sha256
   ```
   Expected: `4733ab55e296422951864ea7843e98f723a47004c7295c1f42cd48faa1fa10de`.
2. **The CI artifact**, once A0.2 is green:
   ```powershell
   gh run download -R Sahas266/ledger-op3n-n3xt-hackathon-26 -n ledger-cash-nanosplus -D $HOME\lc-nanosplus
   ```
   Then check `Get-Content $HOME\lc-nanosplus\app.sha256` against the same hash. A different hash means the build is
   not reproducible: note it and still use the CI artifact.
3. **A rebuild**, from Git Bash:
   ```bash
   MSYS_NO_PATHCONV=1 docker run --rm --memory 1g --name v1-build -v "$(pwd -W)/mvp/ledger-cash/app:/app" ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools@sha256:8d3da9179dd1b241883c769c521ee9403352b60091c80405b5bef5801a003ba2 make -C /app TARGET=nanos2 BOLOS_SDK=/opt/nanosplus-secure-sdk APP_DIR=/app -j4
   ```

### A5. Sideload
Plug in the Nano and unlock it. Stay on the dashboard. Ledger Wallet must be quit (A1).
```powershell
cd "C:\Users\sahas\Github Repos\ledger-op3n-n3xt-hackathon-26\mvp\ledger-cash\app\build\nanos2\bin"   # or $HOME\lc-nanosplus
& $py -m ledgerblue.runScript --scp --fileName app.apdu --elfFile app.elf
```
On the Nano, use the right button to page and both buttons to choose:
1. A prompt asks you to allow an unsafe manager ("Allow unsafe manager"). Page to the allow/accept choice and press
   both buttons.
2. An install confirmation for "Ledger Cash" follows. If it shows an identifier or hash, compare it with
   `app.sha256`. Accept with both buttons.
3. The command ends without a traceback, and "Ledger Cash" appears on the dashboard.

| Failure | Meaning |
|---|---|
| `Invalid status 511f` | The OS is too old for API 27 (A2). |
| `Invalid status 5515` | The device is locked. Unlock it and run again. |
| `Invalid status 6985` | Refused on the device. Run again and accept. |
| `No dongle found` | Ledger Wallet is still running, the device is still locked, or the cable is charge-only. |

For any other error, send back the full output and a photo of the screen.

### A6. Open the app
1. On the Nano, select "Ledger Cash" with both buttons.
2. The first launch shows a warning that the app is not genuine. Page through it and confirm opening the app with
   both buttons.
3. Expected home screen: "Cash: 0 USDC", the same as `screens/nano/01-payer-boot.png`.

Opening an app re-enumerates the USB device, so wait about 5 s before the next command.

### A7. USB flow (about 10 min), comparing with `screens/nano/`
From `mvp\ledger-cash`. Label note: the emulator run behind `screens/nano/` used the label
`coffee-and-croissant-x2` (it tests the 24-character limit), so its "For" pages wrap to two lines. With `coffee` the
same pages show one line; everything else matches.
```powershell
cd "C:\Users\sahas\Github Repos\ledger-op3n-n3xt-hackathon-26\mvp\ledger-cash"
& $py hw.py balance
& $py hw.py status
& $py hw.py setup anvil
& $py hw.py selfpay 5 coffee
& $py hw.py selfpay 1 tea
& $py hw.py balance
& $py hw.py auths nano-auths.json
```

1. **`hw.py balance`.** Expected: `SW 9000`, cash 0, pay counter 0, and the Nano's cash account address. It differs
   from the Nano's Ethereum app accounts: that is intended.
2. **`hw.py status`.** Expected: `SW 6D00`. That is correct: the Nano has no NFC, so the tap commands do not exist.
3. **`hw.py setup anvil`.** Approve twice.
   - SET_CONFIG pages, the same as screenshots 03-07:
     1. "Set USDC network"
     2. "Set US...ork (1/2) | Chain ID 31337 | USDC 0x5FBD…"
     3. "(2/2) …4180AA3"
     4. **Approve** (both buttons). The page after it is Reject.
   - LOAD_CASH pages, the same as screenshots 13-16: "Load 10 USDC as cash", then "Load 10... as cash | Cash after:
     10 USDC", then **Approve**.
   - Expected output: `SW 9000` twice, then `cash 10 USDC`.
4. **`hw.py selfpay 5 coffee`.** The Nano plays both roles.
   - Payee pages, the same as screenshots 17-20: "Request 5 USDC", then "Request 5 USDC | For: coffee", then
     **Approve**. The home screen then reads "Receive 5 USDC to 0x…" (screenshot 21).
   - Payer pages, the same as screenshots 30-36:
     1. "Pay with USDC cash"
     2. "Pay | 5 USDC"
     3. "To", with the full 42-character address on ONE page over 3 lines. It is the Nano's own cash account (the
        address `hw.py balance` printed).
     4. "For | coffee"
     5. "Cash left after | 5 USDC"
     6. **"Pay 5 USDC?"**: press both buttons to sign. There is no hold-to-sign on the Nano.
     7. "Transaction signed"
   - Then the PUT_AUTH status, the same as screenshot 37: "IOU 5 USDC from | 0x….. | Not settled yet".
   - Expected output:
     - `receipt ok`;
     - the second PAY gives `SW B004 already paid`;
     - `cash 5 USDC, pay counter 1`.
5. **`hw.py selfpay 1 tea`, reject check.** Approve the request. On the PAY review, press the right button past
   "Pay 1 USDC?" to **"Reject transaction"** and press both buttons, as in screenshots 22-29. Expected: PAY gives
   `SW 6985 rejected on device`, and the next `hw.py balance` still shows 5 USDC and counter 1.
6. **`hw.py auths nano-auths.json`.** Expected: `1 auth(s) -> nano-auths.json`, and slot 1 gives `6A88`.

On the first USB command after opening the app, if Windows does not find the device, unplug it and plug it back in,
reopen the app, and run the command again.

### A8. Settle the Nano's auth on anvil (about 5 min, Git Bash)
```bash
cd "/c/Users/sahas/Github Repos/ledger-op3n-n3xt-hackathon-26/mvp/ledger-cash/settle"
MSYS_NO_PATHCONV=1 docker run -d --rm --name v1-anvil --memory 512m -p 127.0.0.1:8545:8545 ghcr.io/foundry-rs/foundry@sha256:0c00cb0bda1ab1b91c9a6bf60f4c76c09c1a8870824b6d4718afbabacf6f9a17 "anvil --host 0.0.0.0" && sleep 3
npm ci
node deploy.mjs                          # token 0x5FbDB2315678afecb367f032d93F642f64180aa3 chainId 31337
node fund.mjs 0x<Nano address> 10
node settle.mjs ../nano-auths.json       # "#0 success"; from == to, so the balance stays 10 -> 10
node settle.mjs ../nano-auths.json       # "#0 REJECTED already used"
docker rm -f v1-anvil
git status --short .                     # deploy.json unchanged on a fresh anvil
```

These auths are bound to chainId 31337 and the anvil token, so they can never move funds on another chain. The Nano
signs from its cash account (`44'/1279476051'/0'/0/0`), not from your Ethereum app accounts, and that account holds only
what you send to it. Still, only ever approve the `anvil` or `base` configs on this device.

### A9. Tangem inventory on the iPhone (read-only)
Open the Tangem app and scan each card: hold it to the top of the back of the iPhone. **Do not** reset, create a
wallet, set or change an access code, start a backup, or send anything. If the app offers one of these, cancel. For
each card, write down:
- the card ID (printed on the card, and in the app's card settings);
- whether the scan asked for an access code (asked = an access code is set);
- the networks shown and the Ethereum address (token, then **Receive**);
- the number of linked or backup cards, if the app shows it;
- the firmware or card version, if shown.

Menu names differ between app versions: record what you see. Tangem stays out of `cash.c` until the licence decision.
This inventory is only for that decision.

### A10. Record results in WORKLOG.md
Add an entry at the bottom:
```markdown
## 2026-10-11: Nano S Plus hardware run (ledger-cash)
- Nano OS <version> (Ledger Wallet) / `hw.py version`: <output or "errored">
- Build: local / CI artifact, app.sha256 <first 8 chars> (CI matches local: yes/no)
- Sideload: <ok | Invalid status xxxx>, prompts seen: <list>
- USB flow (A7): balance <ok>; TAP_STATUS 6D00 <yes/no>; setup <ok>; selfpay <receipt ok, B004>; reject <6985, cash unchanged>; auths <n>
- Screens that differ from screens/nano/: <none | file + what differs>
- Anvil settle: <#0 success / REJECTED already used>
- Tangem: <card ID, access code y/n, ETH address, linked cards> per card
- Photos: <where>
```

### A11. Mark for Paris
Bridge mode (Android phone + OTG + your Nano as the payee) needs the collaborator's phone, so it is [C](#c-paris-only-android-bridge-to-the-nano-s-plus).
Bring the Nano, a USB-C OTG adapter and a **data** cable.

---

## B. Collaborator: Flex + Android

Commands are given for **Windows PowerShell** and for **macOS/Linux**. Every `hw.py` command runs in
`mvp/ledger-cash` of the cloned repo. `$py` (Windows) and `$PY` (macOS/Linux) are set in B3.

### B-1. Prerequisites
1. **Accept the repo invitation** (sent to `hrishabhayush` on 2026-10-10, write access):
   https://github.com/Sahas266/ledger-op3n-n3xt-hackathon-26/invitations. Until you do, cloning and
   `gh run download` fail with "not found".
2. **Install gh, git and Python 3** (and, for B8 Option A only, Node 20+ and Docker):
   ```powershell
   winget install --id GitHub.cli -e; winget install --id Git.Git -e; winget install --id Python.Python.3.12 -e
   winget install --id OpenJS.NodeJS.LTS -e     # B8 Option A only
   ```
   ```bash
   brew install gh git python@3.12 node                        # macOS (Homebrew)
   sudo apt update && sudo apt install -y gh git python3 python3-venv nodejs npm   # Debian/Ubuntu
   ```
   Open a new terminal afterwards so the new commands are on PATH. On Ubuntu older than 22.04, `gh` is not in apt:
   follow https://github.com/cli/cli/blob/trunk/docs/install_linux.md. Check with `gh --version`, `git --version` and
   `python --version` (`python3` on macOS/Linux).

### B0. Get the repo (after B-1)
```powershell
gh auth login; gh repo clone Sahas266/ledger-op3n-n3xt-hackathon-26 -- -b ledger-cash; cd ledger-op3n-n3xt-hackathon-26\mvp\ledger-cash
```
```bash
gh auth login && gh repo clone Sahas266/ledger-op3n-n3xt-hackathon-26 -- -b ledger-cash && cd ledger-op3n-n3xt-hackathon-26/mvp/ledger-cash
```
Plain `git clone -b ledger-cash https://github.com/Sahas266/ledger-op3n-n3xt-hackathon-26.git` also works.

### B1. Update the Flex to OS 1.7.0 and turn NFC on
1. In Ledger Wallet, open **My Ledger** with the Flex plugged in and unlocked, and allow it on the Flex. Its OS
   (firmware) version is shown there. Update it if it is older than **1.7.0**. Write the version down.
2. On the Flex, open **Settings** and turn **NFC on** (it may be under a connectivity section).

Send back: a photo of the version in My Ledger and of the NFC setting.

### B2. Quit Ledger Wallet fully
```powershell
Get-Process | Where-Object ProcessName -like "Ledger*"          # expected: no output; else quit from the tray, or:
Get-Process | Where-Object ProcessName -like "Ledger*" | Stop-Process
```
```bash
pgrep -ifl "ledger.?(live|wallet)"   # expected: no output; else quit the app (macOS: Cmd-Q), or: pkill -if "ledger.?(live|wallet)"
```
On macOS a running Ledger Wallet holds the device exclusively, so `hw.py` and `runScript` get `No dongle found`.

### B3. Python with ledgerblue
```powershell
py -3 -m venv $HOME\lc-venv; $py = "$HOME\lc-venv\Scripts\python.exe"; & $py -m pip install ledgerblue
```
```bash
python3 -m venv ~/lc-venv && PY=~/lc-venv/bin/python && $PY -m pip install ledgerblue
```
If `py` is not found on Windows, use `python -m venv $HOME\lc-venv` instead.

On **Linux** only, add Ledger's udev rules once, then unplug and replug the Flex:
```bash
wget -q -O - https://raw.githubusercontent.com/LedgerHQ/udev-rules/master/add_udev_rules.sh | sudo bash
```
Windows and macOS need no driver.

Cross-check of the OS version, with the Flex on the dashboard (no app open). This command has not been run on a
device:
```powershell
& $py hw.py version
```
```bash
$PY hw.py version
```
Expected: `target 0x33300004, OS 1.7.0`.

### B4. Download the Flex build and sideload it
```powershell
gh run download -R Sahas266/ledger-op3n-n3xt-hackathon-26 -n ledger-cash-flex -D $HOME\lc-flex; Get-Content $HOME\lc-flex\app.sha256
Push-Location $HOME\lc-flex; & $py -m ledgerblue.runScript --scp --fileName app.apdu --elfFile app.elf; Pop-Location
```
```bash
gh run download -R Sahas266/ledger-op3n-n3xt-hackathon-26 -n ledger-cash-flex -D ~/lc-flex && cat ~/lc-flex/app.sha256
(cd ~/lc-flex && $PY -m ledgerblue.runScript --scp --fileName app.apdu --elfFile app.elf)
```
- The hash must be `9c8cfe79ceb043e3ef728eaa12f117e8a17d92e35cb639be3fb0a0887bfbcd57`.
- If the download finds no artifact, CI has not run yet: ask Sahas to zip `mvp/ledger-cash/app/build/flex/bin/`
  (`app.apdu`, `app.elf`, `app.sha256`) and send it.
- During the sideload, the Flex asks to allow an unsafe manager ("Allow unsafe manager"). Approve it on the
  touchscreen, then approve the install of "Ledger Cash". The command ends without a traceback.
- Failures are the same as in A5: `511f` means the OS is too old, `5515` locked, `6985` refused, and
  `No dongle found` means Ledger Wallet is still running or the cable is charge-only.

### B5. Open the app and configure it (anvil)
1. Open **Ledger Cash** on the Flex and acknowledge the not-genuine warning.
2. Expected home screen: "Ledger Cash", "Cash: 0 USDC" and a **Pay by tap** button.
3. Wait about 5 s, then:
   ```powershell
   & $py hw.py balance; & $py hw.py setup anvil 10
   ```
   ```bash
   $PY hw.py balance && $PY hw.py setup anvil 10
   ```
4. On the Flex, approve:
   - "Set USDC network / Chain ID 31337 / USDC 0x5FBD…";
   - then "Load 10 USDC as cash / Cash after: 10 USDC".
5. Expected output: `SW 9000` twice, then `cash 10 USDC, pay counter 0, address 0x…`.

**Safety:** only approve a "Set USDC network" screen that shows Chain ID **31337** with token `0x5FBD…0AA3` (anvil) or
Chain ID **84532** with token `0x036C…CF7E` (Base Sepolia). Reject anything else.

That address is the Flex's **cash account** (`44'/1279476051'/0'/0/0`), not one of its Ethereum app accounts. Send it
to Sahas: it gets funded at settlement.

### B6. GATE 1: does the reader power on, and does CARD_DETECTED fire?
You need a **contactless bank card**. It answers ISO-DEP. A transit or hotel card may not.
1. Start the tap with USB connected:
   ```powershell
   & $py hw.py tap
   ```
   ```bash
   $PY hw.py tap
   ```
   Expected right away: `SW 9000`, then `tap state 1 = waiting for card`. The Flex shows **"Hold near the payee"**
   with **Cancel**.
2. Hold the bank card flat against the Flex. Where the Flex's antenna sits is not known: try the back first, then the
   screen side, and move slowly.
3. What the app does with a bank card, from `cash.c`:
   1. On CARD_DETECTED it shows a spinner, "Reading request".
   2. It sends `SELECT 00A404000C F04C45444745524341534801`.
   3. A bank card does not know this AID and answers an error SW, normally `6A82`.
   4. The app then shows the failure status **"Not a Ledger Cash payee"**, which closes by itself after a few seconds,
      and goes back home. The reader is switched off and card emulation is restored.
   5. `hw.py` prints `tap state 2 = busy`, then `tap state 5 = FAILED, tap SW 6A82` (or the card's own SW), and
      exits.

Read the result:

| `hw.py` / Flex screen | Meaning | Gate |
|---|---|---|
| State 5 FAILED, SW = the card's error (6A82 or other), "Not a Ledger Cash payee" | Reader on, CARD_DETECTED fired, one ISO-DEP round trip worked | **GO** (reader + framing) |
| State 5, SW 6E00 or other, "Payee refused" | The card answered 9000 to SELECT (unexpected), then refused `E011` | GO, but send the output |
| State 5, SW B009, "Payee did not answer / Nothing paid" | Card detected, no reply within 2 s | Reader GO, **framing doubt** |
| State 5, SW B008, "Card removed / Nothing paid" | Card detected, then lost | Retry holding still; GO if a retry gives 6A82 |
| Stays at state 1, screen stays "Hold near the payee" for 30 s, on both sides of the Flex | CARD_DETECTED never fired | **NO-GO**: NFC off, or the OS does not let a sideloaded app use the reader |
| `hw.py` errors, or prints nothing for 15+ s while the Flex screen has moved on | USB stopped working while the reader was on (USB + reader coexistence is only verified in SDK source) | Finding; use the steps below |

If USB fails with the reader on, or just as a second check:
1. Unplug USB. On the Flex, press **Pay by tap** on the home screen and tap the bank card.
2. Photograph the status screen.
3. Plug back in and run `hw.py status`, which reports the same state and SW.

Check the mode switch: after any result, run `hw.py balance` (must answer `9000`), then run `hw.py tap` again
(state 1 again) and press **Cancel** (state 5, SW 6985, "Tap cancelled").

**Send back:**
- the full `hw.py tap` and `hw.py status` output;
- photos of "Hold near the payee" and of the final status screen;
- the card brand, and which side of the Flex worked.

If the result is NO-GO, stop the NFC gates. Tell Sahas, ask the Ledger mentors (Monday) whether sideloaded apps may
power the reader, then go to [the fallback](#if-nfc-fails-on-the-real-flex).

### B7. GATE 2: Flex pays the Android phone (phone payee)
1. **Install the APK.** Download the artifact `ledger-cash-payee-debug-apk` from the `android` workflow:
   ```powershell
   gh run download -R Sahas266/ledger-op3n-n3xt-hackathon-26 -n ledger-cash-payee-debug-apk -D $HOME\lc-apk
   ```
   ```bash
   gh run download -R Sahas266/ledger-op3n-n3xt-hackathon-26 -n ledger-cash-payee-debug-apk -D ~/lc-apk
   ```
   You get `app-debug.apk`. Install it as in `mvp/android/README.md` "Get the APK": copy it to the phone and allow
   installs from that app, or use `adb install -r app-debug.apk`. **Never uninstall it later**: the phone payee key
   lives only in the app.
2. **Set up the phone.**
   1. Turn NFC on: **Settings → Connected devices → NFC**.
   2. Open **Ledger Cash Payee** and write down the "Phone payee address".
   3. Select **Phone payee**.
   4. Leave chainId `31337` and the token `0x5FbDB2315678afecb367f032d93F642f64180aa3` (the defaults; they must match
      B5).
   5. Enter amount `1.00` and label `coffee`, then tap **Arm payment request**.
   6. Expected status: `Armed: 1 USDC "coffee". Hold the Flex to the phone.`
   7. Keep the screen **on and unlocked**, with the app in front.
3. **Tap.** Run `hw.py tap` (or press **Pay by tap**). Lay the phone face down on the table and put the Flex on its
   NFC spot, screen up, using the side of the Flex that worked in B6. Slide it slowly to find the spot. **Keep the
   devices together until the Flex says "Paid".**
4. **Expected on the Flex**, as in the emulator screenshots (which show 5 USDC, cash 15 and the emulator payee):
   1. "Hold near the payee": `screens/13-payer-tap1-hold-near.png`
   2. "Reading request" (a spinner, not captured)
   3. "Pay with USDC cash": `screens/15-payer-tap1.png`
   4. "Pay 1 USDC / To 0x<phone payee address> / For coffee": `screens/17-payer-tap1.png`. **Check that To matches the
      phone.**
   5. "Cash left after 9 USDC": `screens/19-payer-tap1.png`
   6. "Pay 1 USDC?" with **Hold to sign**: `screens/21-payer-tap1.png`. Hold it.
   7. "Sending payment" (not captured)
   8. **"Paid 1 USDC to 0x…"**: `screens/23-payer-tap1-end.png`
5. **Expected on the phone:** a toast, and the status `Got authorization (unsettled IOU) for 1 USDC from
   0x<Flex address>`. The list gains one entry.
6. **Expected from `hw.py`:** `tap state 4 = PAID, tap SW 9000`, then `auth -> tap-auth.json`.
7. **Negative check.** Tap again without re-arming the phone. Expected: "Payee has no request", state 5, SW B006,
   and the cash stays 9.

| Result | Meaning, and what to do |
|---|---|
| Stays "Hold near the payee" (Gate 1 passed) | The phone's field was not seen. Check that NFC is on and the screen is on and unlocked, take off a thick case, look up the phone model's NFC location. |
| "Not a Ledger Cash payee" + SW | The phone answered, but Android did not route our AID to the app (app not installed, or not in front). Send the SW. |
| "Payee did not answer", B009 | The phone was too slow, or there is a framing difference. Send the output. |
| "Payee has no request", B006 | The phone is not armed. |
| "Wrong network or token", B002 | The phone's chainId or token differs from the Flex config. |
| "Payee signature invalid", B001 | A phone signing bug. Send a phone screenshot and the output. |
| "Not enough cash", B003 | Run `hw.py setup anvil 10` again. |
| "Card removed / Nothing paid", B008 during the review | The field dropped while you read or held to sign (hardware gate 5). Retry holding still. If it repeats, note after how many seconds. |
| State 6 "Signed 1 USDC / Card left after signing / Cash debited, no receipt" | Signed, but the phone never answered. `tap-auth.json` still holds a settleable auth. Send it. |
| State 6 "Signed … / Payee refused it" (SW B005 or other) or "Receipt invalid" | The phone refused the auth, or its receipt did not verify. Send the output and a phone screenshot. |

**Send back:**
- photos of the Flex review (the To page), of "Paid" and of the phone status;
- the full `hw.py tap` output;
- `tap-auth.json`.

### B8. GATE 3: settle what the phone received
On the phone, tap **Share received auths** and send the JSON to the laptop. Save it as
**`mvp/ledger-cash/settle/phone-auths.json`**: every command below runs in `mvp/ledger-cash/settle` and reads the file
from there. Then use one of two options.

**Option A, anvil (default).** Anyone can run it on a fresh anvil: Sahas on his PC, or you with Docker and Node 20+.
From `mvp/ledger-cash/settle`:
```powershell
docker run -d --rm --name lc-anvil -p 127.0.0.1:8545:8545 ghcr.io/foundry-rs/foundry@sha256:0c00cb0bda1ab1b91c9a6bf60f4c76c09c1a8870824b6d4718afbabacf6f9a17 "anvil --host 0.0.0.0"; Start-Sleep 3
npm ci; node deploy.mjs; node fund.mjs 0x<Flex address> 10; node settle.mjs phone-auths.json; node settle.mjs phone-auths.json; docker rm -f lc-anvil
```
```bash
docker run -d --rm --name lc-anvil -p 127.0.0.1:8545:8545 ghcr.io/foundry-rs/foundry@sha256:0c00cb0bda1ab1b91c9a6bf60f4c76c09c1a8870824b6d4718afbabacf6f9a17 "anvil --host 0.0.0.0" && sleep 3
npm ci && node deploy.mjs && node fund.mjs 0x<Flex address> 10 && node settle.mjs phone-auths.json; node settle.mjs phone-auths.json; docker rm -f lc-anvil
```
Expected output:
- `token 0x5FbDB2315678afecb367f032d93F642f64180aa3 chainId 31337`;
- then `#0 success tx 0x…`, with `from 0x<Flex> 10.000000 USDC -> 9.000000 USDC` and
  `to 0x<phone> 0.000000 USDC -> 1.000000 USDC`;
- the second settle prints `#0 REJECTED already used`.

Without Docker, `anvil` from Foundry (`foundryup`) works the same way: run `anvil` in a second terminal. If the token
address differs, anvil was not fresh: restart it.

**Option B, Base Sepolia (live testnet).** The domain is checked (see Shared facts). Steps:
1. **Make a relayer key.** It pays the gas. Never use the anvil keys here, because they are public. From
   `mvp/ledger-cash/settle`, after `npm ci`:
   ```
   node -e "import('viem/accounts').then(m=>{const k=m.generatePrivateKey();console.log(k, m.privateKeyToAccount(k).address)})"
   ```
   Keep the key out of git and out of chat.
2. **Fund the relayer with Base Sepolia ETH** from either faucet:
   - https://portal.cdp.coinbase.com/products/faucet
   - https://www.alchemy.com/faucets/base-sepolia
   - more are listed at https://docs.base.org/base-chain/tools/network-faucets

   The payer needs no ETH: EIP-3009 is gasless for the signer.
3. **Fund the Flex address with testnet USDC** at https://faucet.circle.com: pick **Base Sepolia** and paste the
   Flex address.
4. **Switch both devices to Base Sepolia.**
   - Flex: `hw.py setup base 0`, then approve "Set USDC network / Chain ID 84532 / USDC 0x036C…". The cash counter
     is kept. Keep it at or below the on-chain USDC.
   - Phone: chainId `84532`, token `0x036CbD53842c5426634e7929541eC2318f3dCF7e`. Arm 1 USDC again, tap as in B7,
     then share the auths again and save them as `mvp/ledger-cash/settle/base-auths.json`.
5. **Settle.** If the shared JSON still holds the anvil auth from B7, that one is refused with `invalid signature`,
   which is expected (exit code 1).
   ```powershell
   $env:RPC_URL="https://sepolia.base.org"; $env:TOKEN="0x036CbD53842c5426634e7929541eC2318f3dCF7e"; $env:RELAYER_KEY="0x<relayer key>"
   node balances.mjs 0x<Flex address> 0x<phone address>; node settle.mjs base-auths.json; node balances.mjs 0x<Flex address> 0x<phone address>
   ```
   ```bash
   export RPC_URL=https://sepolia.base.org TOKEN=0x036CbD53842c5426634e7929541eC2318f3dCF7e RELAYER_KEY=0x<relayer key>
   node balances.mjs 0x<Flex address> 0x<phone address>; node settle.mjs base-auths.json; node balances.mjs 0x<Flex address> 0x<phone address>
   ```
   - Expected: `#n success tx 0x…` for the Base Sepolia auth, and the balances move by 1 USDC.
   - The transaction is at `https://sepolia.basescan.org/tx/<hash>`.
   - `RPC_URL`, `TOKEN` and `RELAYER_KEY` are environment overrides in `settle/common.mjs`; without them it uses
     anvil.

| Failure | Meaning |
|---|---|
| `REJECTED ERC20: transfer amount exceeds balance` or similar | The Flex address has too little USDC. Use the faucet. |
| `REJECTED FiatTokenV2: invalid signature` on the Base Sepolia auth | The phone or Flex was still on anvil when you tapped. |
| An insufficient-funds error | The relayer has no ETH. |

**Send back:** the full settle output (it has no secrets) and the Basescan link.

---

## C. Paris only: Android bridge to the Nano S Plus

The phone is only an NFC antenna: it answers SELECT itself and forwards GET_REQUEST and PUT_AUTH to Sahas's Nano over
USB OTG. The Nano is the payee and the Flex pays. Since the Nano build exists, this is no longer blocked: the USB path
on the Nano accepts exactly the APDUs the bridge forwards. This was tested only in the emulator (A7 runs the same
APDUs).

Follow `mvp/android/README.md` section **B** ("Nano bridge") steps 1-6, with these corrections:
1. Nano: the app is installed (A5) and **open**, on its home screen. Plug it into the phone with the OTG adapter and a
   data cable, then accept the prompt that opens Ledger Cash Payee, or tap **Connect Nano (USB OTG)**.
2. Use the same chainId and token as the Flex config (anvil: 31337 / `0x5FbDB…0aa3`). Tap **Arm request on Nano
   (approve twice on the Nano)**. On the Nano, approve "Set USDC network" and then "Request 1 USDC | For: coffee".
3. On the Flex, start a tap (`hw.py tap` or **Pay by tap**) and tap the phone.
   - Expected on the Flex: the same review as B7, with **To = the Nano's address**, then "Paid 1 USDC to 0x…".
   - Expected on the Nano: **"IOU 1 USDC from | 0x…… | Not settled yet"**.
   - Expected on the phone: "Nano got authorization (unsettled IOU) for 1 USDC from 0x…".
4. Settle: share from the phone (save as `mvp/ledger-cash/settle/phone-auths.json`), or plug the Nano into a laptop
   and run `hw.py auths settle/nano-auths.json` from `mvp/ledger-cash`. Then use B8 Option A with that file.

Timing risk: the Flex waits 2 s for GET_REQUEST and 5 s for the receipt, and the bridge adds USB round trips. A
`B009` on the Flex means the bridge was too slow. If the Nano is showing a review when the Flex asks, the Flex gets
`B007`, so keep the Nano on its home screen.

---

## If NFC fails on the real Flex

The submission still stands on what is emulated, plus the USB-only flows once they run on the devices:
1. **The emulator video:** `mvp/ledger-cash/video/ledger-cash-demo.mp4`. It shows the full Ledger-to-Ledger tap on
   two emulated Flex devices (patched Speculos NFC reader, `demo.py` ALL PASS), including the refusals and the
   settlement on anvil. Say plainly that it is emulated.
2. **USB-only flows on both real devices:**
   - Nano S Plus: A7 + A8 (`hw.py setup anvil`, `hw.py selfpay`, `hw.py auths`, `settle.mjs`).
   - Flex: the same `hw.py setup anvil 10` then `hw.py selfpay 1 coffee`. This shows the real Flex Secure Screen
     review (Pay / To / For / Cash left after / Hold to sign), the debit, B004 on replay and the payee IOU screen.
     Then `hw.py auths flex-auths.json` and `settle.mjs` as in B8 Option A.
3. **What to show on stage:**
   - the real devices signing over USB;
   - the emulated tap in the video;
   - the gate result (for example "the OS did not deliver CARD_DETECTED to a sideloaded app"), as the honest
     hardware finding.
