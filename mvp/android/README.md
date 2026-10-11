# Ledger Cash Payee (Android)

The phone the Ledger Flex taps. The Flex runs the ledger-cash app in NFC **reader** mode; this app answers as an
NFC card (Android HCE, AID `F04C45444745524341534801`). The Flex reads a signed payment request, shows it on its screen,
signs a USDC EIP-3009 `TransferWithAuthorization`, and hands it back. Settlement happens later with
`mvp/ledger-cash/settle/settle.mjs`.

Two modes, one screen:

1. **Phone payee.** The phone is the shop. It holds its own software secp256k1 key (made on first launch, stored in app-private storage), signs the request, checks the Flex's authorization (EIP-712 signer = `from`, `to` = this phone, amount, nonce = keccak of the request), stores it, and replies with a signed receipt. Shows "Got authorization (unsettled IOU) for X USDC from 0x…". That is a signed promise, not money yet (see Risks).
2. **Nano bridge (see B; uses the `ledger-cash-nanosplus` build).** The phone is only an NFC antenna for a Ledger Nano S Plus on a USB OTG cable. The Nano runs the same ledger-cash app as the payee; the phone answers the NFC SELECT itself and passes every other APDU to the Nano over USB HID, then sends the Nano's answer back over NFC. This makes the Flex-to-Nano tap possible even though the Nano has no NFC.

Both modes list received authorizations and have a **Share** button that exports them as JSON
(`[{from,to,value,validAfter,validBefore,nonce,v,r,s}, …]`), the format `settle.mjs` reads.

## Get the APK

The APK is built by GitHub Actions (`.github/workflows/android.yml`) on every push that touches `mvp/android/**`.

1. On GitHub: **Actions → android →** latest green run **→ Artifacts → `ledger-cash-payee-debug-apk`**. It downloads as a zip; unzip it to get `app-debug.apk`.
2. Get the APK onto the phone (USB file copy, Drive, or a message to yourself).
3. Open it from the phone's Files app. Android asks to allow installs from that app: **Settings → Apps → Special app access → Install unknown apps →** (your Files/Drive app) **→ Allow**. Then install. Play Protect may warn about an unknown developer: **Install anyway**.
4. Or with a PC and USB debugging on: `adb install -r app-debug.apk`.
5. If an APK built before 2026-10-10 20:10 (per-run CI key) is already installed, uninstall it once; later APKs install over each other.

It is a debug build signed with a fixed, public debug key (`app/debug.keystore`, password `android`), so every newer APK installs **over** the old one and keeps the phone payee key and the stored auths. **Do not uninstall:** settled USDC sits on the phone payee address, whose key lives only in the app's private storage (`files/payee.key`, excluded from backups). Uninstalling or clearing app data loses those funds for good. To export the key (debug build, USB debugging on): `adb shell run-as ledgercash.payee cat files/payee.key` (64 hex chars, import into any wallet as a private key).

## Before any test (laptop + Flex on USB, once)

The Flex has no on-device menu for its network or its cash: `SET_CONFIG` and `LOAD_CASH` are USB APDUs from a laptop,
each approved on the Flex screen. Without them the Flex refuses every tap with `B002` (no/other config) or `B003`
(not enough cash). Without on-chain USDC on the Flex address, `settle.mjs` reverts later.

1. Chain: start anvil (`anvil`, or the docker line in `mvp/ledger-cash/settle/NOTES.md`), then in `mvp/ledger-cash/settle`:
   `npm ci && node deploy.mjs`. On a **fresh** anvil this prints token `0x5FbDB2315678afecb367f032d93F642f64180aa3`,
   chainId `31337`, which are the phone app's defaults. Otherwise use the values from `settle/deploy.json` everywhere below.
2. Flex: NFC on in its Settings; ledger-cash sideloaded and **open**; plugged into the laptop by USB; **Ledger Wallet (formerly Ledger Live) closed** (it holds the USB interface). `pip install ledgerblue`,
   then run this and approve "Set USDC network", then "Load 10 USDC as cash", on the Flex:
   ```
   python -c "from ledgerblue.comm import getDongle; d=getDongle(True); [d.exchange(bytes.fromhex(a), 60000) for a in ('E01200001C0000000000007A695FbDB2315678afecb367f032d93F642f64180aa3', 'E0200000080000000000989680')]; print('Flex address 0x' + bytes(d.exchange(bytes.fromhex('E021000000')))[12:32].hex())"
   ```
   The printed address is the Flex's **cash account** (`44'/1279476051'/0'/0/0`), which no stock Ledger chain app can sign for (dedicated derivation path),
   not one of its Ethereum app accounts. Bytes: `E0 12 00 00 1C` + chainId u64 BE (`31337` = `0000000000007A69`) + token (20). `E0 20 00 00 08` + amount u64 BE in
   6-decimal units (10 USDC = `0000000000989680`). `E0 21 00 00 00` answers balance u64 ‖ pay counter u32 ‖ address (bytes 12..31).
   Not run against a device (no Flex here); these are the same APDUs `mvp/ledger-cash/demo.py` sends to the emulated Flex.
3. Fund that address on chain: `node fund.mjs 0x<Flex address> 10`. The Flex's cash counter and its on-chain USDC are
   separate; keep cash ≤ on-chain balance or settlement reverts.
4. Phone: **NFC on** (Settings → Connected devices → NFC). If Settings has "Contactless payments / Default payment app", it does not matter here: our AID is category `other`, not payment.
   Type the **same chainId and token** into the phone as in step 2.

## Hardware test steps (collaborator: Flex + Android)

**A. Phone payee (no Nano needed)**

1. Install the APK, open **Ledger Cash Payee**. Note the "Phone payee address" (0x…).
2. Select **Phone payee**. Enter amount `1.00` and label `coffee` (plain ASCII, max 24 characters). Tap **Arm payment request**. The status line says "Armed: 1 USDC "coffee"…".
3. Keep the phone **unlocked with the screen on**. On the Flex, open ledger-cash, start "pay by tap" (the reader flow), and hold the Flex against the phone's NFC spot (see Risks).
4. The Flex should show Pay 1 USDC, To = the phone address, For = coffee. Approve on the Flex. Keep the devices together until the Flex says done.
5. The phone shows a toast and status line "Got authorization (unsettled IOU) for 1 USDC from 0x<Flex address>"; the list gains one entry.
6. Tap **Share received auths**, send the JSON to the laptop, save it as `auths.json`, then in `mvp/ledger-cash/settle`: `node settle.mjs auths.json`. Expect `#0 success tx 0x…` and the balances moving.
7. Negative checks: tap again without re-arming → the Flex gets SW `B006` and shows "Payee has no request" (the phone disarms a paid request; a Nano payee in mode B does the same, because a successful `PUT_AUTH` drops its request, so the Nano answers `GET_REQUEST` with `B006` too). Change the amount on the phone after the Flex has read the request → the Flex's auth is refused with `B005`.

**B. Nano bridge (Flex + Android + Sahas's Nano S Plus)**

The Nano build exists: CI artifact `ledger-cash-nanosplus` (`device-apps` workflow), sideloaded as in
`mvp/ledger-cash/HARDWARE.md` A5. On the Nano the tap code is compiled out (`TAP_TO_PAY`/`TAP_STATUS` answer `6D00`),
and its USB path accepts exactly what the bridge forwards: `GET_REQUEST` and `PUT_AUTH` (the phone answers SELECT
itself). Tested only on two emulated Nano S Plus (`mvp/ledger-cash/app/test_nano.py`), not through a phone. Steps:

1. Nano S Plus: unlock it, install and open the ledger-cash app (`ledger-cash-nanosplus`).
2. Plug the Nano into the phone with a **USB OTG adapter** (USB-C phone → USB-C/A to the Nano cable). Android offers to open Ledger Cash Payee for the device: accept (this also grants USB access). Or tap **Connect Nano** and allow the permission dialog, then tap **Connect Nano** again.
3. Status: "Nano connected: … Mode: Nano bridge."
4. Enter chainId, token, amount, label. Tap **Arm request on Nano**. On the Nano approve **Set USDC network**, then **Request 1 USDC**. Status: "Nano armed."
5. Tap the Flex to the phone as in A3–A4. The Nano shows "IOU 1 USDC from 0x…… Not settled yet"; the phone shows "Nano got authorization (unsettled IOU) for 1 USDC from 0x…".
6. Share and settle as in A6. (The Nano also keeps the last 8 auths; `GET_AUTHS 0x24` over USB from a laptop reads them.)

**If nothing happens on tap:** check the phone's NFC is on and the screen unlocked; check that the Flex's reader sends `SELECT 00 A4 04 00 0C F04C45444745524341534801` (Le optional; cash.c sends none) before its `E0` commands (Android routes by that SELECT only); move the Flex slowly over the back of the phone to find the antenna.

## Build it yourself

- CI does: `./gradlew testDebugUnitTest assembleDebug` on ubuntu-latest with JDK 17.
- Locally with the Android SDK: same command; APK in `app/build/outputs/apk/debug/`.
- Without the Android SDK (only a JDK 17+): `./gradlew -p core test` runs the protocol, crypto and HID framing tests.
- Test vectors: `node tools/vector.mjs` (needs `npm ci` in `../ledger-cash/settle`).

## Risks

- **"Got authorization" is an IOU, not money.** The phone only checks that the auth is validly signed by `from` for
  this request. Offline it cannot check that `from` holds the USDC, or that the payer is a genuine Ledger running
  ledger-cash (no attestation; `LOAD_CASH` is a counter the Flex owner approves). Any NFC reader with an empty key gets
  a signed receipt. The payment is final only when `settle.mjs` succeeds; the payer can be unfunded or double-spend.
- **Requests never expire** (`validBefore` = 2^64-1, same as cash.c), because settlement happens later, offline. An
  armed request stays payable until it is paid once or re-armed.

- **HCE needs the screen on** (Android docs), and on some phones unlocked, even though `requireDeviceUnlock=false`. Battery savers may also interfere (not checked). Keep the app in the foreground during the demo.
- **NFC position.** The phone's antenna is a small area on its back; where depends on the model (search "<model> NFC location"). Where the Flex's antenna sits was not checked: find it by sliding the Flex slowly over the phone's NFC spot. A thick or metal case can block it.
- **The tap must last.** The Flex reads the request, then waits for the user to approve on its screen, then sends `PUT_AUTH`. If the devices separate in between, Android ends the HCE session; the next contact starts a new one (the Flex must SELECT again). The phone keeps the armed request across sessions.
- **OTG power and data.** The phone must support USB host/OTG and power the Nano (most USB-C phones do). Some phones turn OTG off after a few minutes idle (Settings → OTG). Use a data cable, not a charge-only one.
- **Nano timing.** GET_REQUEST and PUT_AUTH run without a button press on the Nano, so the bridge adds only USB round-trips (tens of ms). If the Nano is showing a screen that blocks (`SW_BUSY B007`) or is on its dashboard, the Flex gets an error SW. The bridge waits up to 60 s for a USB reply (`NanoBridge.READ_TIMEOUT_MS`), longer than the Flex's reader will wait.
- **USB interface choice.** Android cannot read the HID usage page, so the bridge picks the first HID-class interface (interface 0 on Ledger devices). If a firmware puts U2F first, change `NanoBridge.open`.
- **Phone payee key is a software key** in app storage (backups off), readable on a rooted phone or via `run-as` on this debug build. Funds settled to it are lost if the app is uninstalled or its data cleared. Demo only.
- **iPhone cannot be the payee.** iOS HCE needs an entitlement we do not have. The iPhone can only be a reader.
- Debug APK, sideloaded; nothing here was run on a phone yet.
