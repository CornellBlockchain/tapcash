# Ledger Flex & Nano S Plus: hardware, NFC, BLE, and the "tap Ledger to Ledger" question

Research note for the N3XT hackathon (deadline 2026-10-13 23:59 CEST). Written 2026-10-10. No hardware touched, nothing installed.

Legend: **VERIFIED** = read in a primary source (Ledger shop/docs/support, LedgerHQ GitHub, npm registry). **INFERRED** = derived from verified facts or from a search-engine snippet of a page I could not load. Gaps and contradictions are called out inline.

---

## 1. Bottom line first

- **"Tap Ledger to Ledger to send money" is not feasible in 3 days, and not demoable with the hardware on hand at all.** The Nano S Plus has no NFC, no BLE, no battery, so one of the two devices cannot participate in any wireless link. You would need two Flex/Stax/Gen5 units, a custom device app built with the C SDK's `ENABLE_NFC`/`ENABLE_NFC_READER` flags, sideloaded via a custom developer CA, plus a protocol of your own. None of that is documented beyond a header file and a Makefile.
- **The hardware does, surprisingly, support both NFC roles.** The secure SDK exposes `NFC_LEDGER_MODE_CARD_EMULATION` and `NFC_LEDGER_MODE_READER` to device apps on Stax/Flex/Apex+ (VERIFIED, see §5). Two Flexes could in principle talk NFC-to-NFC (one reader, one card). That is a research-grade project, not a hackathon one.
- **No host-side NFC transport exists.** Neither DMK (`@ledgerhq/device-transport-kit-*`) nor legacy ledgerjs (`@ledgerhq/hw-transport-*`) has an NFC transport (VERIFIED by enumerating the npm registry and the docs). The only things that talk to a Flex over NFC today are a phone's FIDO2 stack (Security Key app) and the Ledger Recovery Key card.
- **Honest architecture for a "wallet-to-wallet" demo:** host (Windows PC or phone) is the relay. Sender's Ledger signs a transaction over USB (Nano S Plus) or USB/BLE (Flex); the host broadcasts; the receiver's address is exchanged out of band (QR, or NFC tag read by a *phone*, not by the Ledger). The Ledger devices never talk to each other. Any "tap" UX in the demo is phone-to-phone or phone-to-tag, with the Ledger as the signer of record.

---

## 2. Device specs

### Ledger Flex (VERIFIED, shop.ledger.com product page + comparison page)

| Spec | Value |
|---|---|
| Screen | 2.8" E Ink touchscreen, 16 grayscale, 480 x 600 px, Gorilla Glass |
| Secure Element | ST33K1M5 (dev docs say ST33K1M5C), CC EAL6+ |
| MCU | STM32WB35 (dev docs hardware-architecture table) |
| OS | "Ledger OS" (marketing name for BOLOS) |
| USB | USB-C ("for desktop use") |
| Bluetooth | BLE 5.2, "for any smartphone (iOS or Android)" |
| NFC | Yes. Product page wording: **"NFC for Ledger Recovery Key & Security Key."** No other use named. |
| Battery | 200 mAh Li-ion (Academy FAQ), "10 hour battery autonomy" / "up to 10 hours or 150 transactions" |
| Dimensions / weight | 78.4 x 56.5 x 7.7 mm, 57.5 g |
| App storage | ~1.5 MB, roughly 10-17 apps (Academy FAQ) |
| Desktop | Windows 10/11 64-bit, macOS 12+, Ubuntu LTS 20.04/22.04 (no ARM), no Chromebook |
| Mobile | Android 10+; iOS 14+ (product page) vs iOS 15+ (comparison page). **Contradiction** between two Ledger pages; use 15+ to be safe. |

### Ledger Nano S Plus (VERIFIED, shop.ledger.com product page + comparison page)

| Spec | Value |
|---|---|
| Screen | 1.1" monochrome OLED, 128 x 64 px |
| Secure Element | ST33K1M5 / ST33K1M5C, CC EAL6+ |
| MCU | STM32F042 (dev docs) |
| USB | USB-C "for desktop and Android use" |
| Bluetooth | None |
| NFC | None |
| Battery | None, "battery-free connection" |
| Dimensions / weight | 62.4 x 17.4 x 8.2 mm, 21 g |
| iOS | **Not supported.** "Ledger Nano S Plus does not work with iOS devices." |
| Security Key app | "Limited to USB" (comparison page) |

### For context: Ledger Nano Gen5 (VERIFIED, comparison page + press)

Announced Oct 2025. USB-C, BLE 5.2, NFC, 2.8" monochrome E Ink (comparison page says 300 x 400; press release says 400 x 300), EAL6+ SE, Recovery Key included, Security Key "Full USB & NFC". Not on hand, but it means the NFC-capable fleet is now Stax, Flex, Gen5 (and Apex+ in the SDK targets).

---

## 3. What Flex NFC is used for today

### 3.1 Security Key app (FIDO2/U2F authenticator) — Flex is the NFC *card*

- VERIFIED (LedgerHQ/app-security-key README): implements FIDO U2F 1.2, CTAP 2.0-2.3, WebAuthn L2/L3. Supported targets per Makefile: `TARGET_NANOX TARGET_NANOS2 TARGET_STAX TARGET_FLEX TARGET_APEX_P`.
- VERIFIED (app-security-key Makefile): `ENABLE_NFC = 1`. Combined with the SDK's `Makefile.standard_app` (below), this is the production proof that a Ledger app ships with NFC enabled on Stax/Flex.
- VERIFIED (Ledger comparison page): Security Key support is "Full USB & NFC" on Gen5/Flex/Stax, "Limited to USB" on Nano S Plus / Nano X.
- VERIFIED (BusinessWire launch PR): "tap your Ledger Flex or Ledger Stax to your phone to login to supported services, or connect via USB to your laptop or PC."
- INFERRED (search snippet of support article 12350325732893, page itself is JS-rendered and could not be fetched by any route tried): NFC is **disabled by default** and enabled in device settings; **no NFC actions while the device is locked**; Android needs Android 14 + a 2024-03 Play system update, Chrome only; iOS works with Chrome/Safari/Firefox; Nano S/S Plus/X cannot use Security Key on iOS; Security Key does **not** work over Bluetooth even on Nano X.
- VERIFIED (nfc_ledger.c): the runtime gate is `OS_SETTING_FEATURES_NFC_ENABLED`, which matches the "disabled by default, toggle in settings" claim.
- Known limitations (VERIFIED, README): discoverable/resident credentials disabled (flash wiped on app/OS update), credential revocation counter disabled.

In this flow the **phone is the NFC reader** and the Flex is an ISO-DEP card presenting FIDO APDUs.

### 3.2 Ledger Recovery Key — Flex is the NFC *reader*

- VERIFIED (Ledger Academy "how to use ledger recovery key", Decrypt, The Block): a separate NFC smart card with its own Secure Element holding a PIN-protected backup of the seed. Setup: hold card to back of device, confirm card ID on screen, set a 4-8 digit PIN; 3 wrong PINs factory-reset the card. Restore: tap card to a new device, enter PIN. Included in the box with Flex/Stax/Gen5.
- VERIFIED (Academy): "The Ledger Recovery Key App runs on the device's secure touchscreen." Ledger CTO quoted saying it ships with "reviewable code and a whitepaper", but `github.com/LedgerHQ/app-recovery-key` returns 404 and I did not find the repo. **Gap.**
- INFERRED: this is the `NFC_LEDGER_MODE_READER` consumer. Reader mode is a first-class SDK mode, not an OS-only feature.

### 3.3 What NFC is NOT used for

- Not for pairing/connecting to Ledger Live / Ledger Wallet mobile. Phones connect via **BLE** (iOS/Android) or **USB** (Android). VERIFIED by the product page wording and the Academy FAQ setup steps ("pair via Bluetooth or USB-C").
- Not for signing transactions with the companion app. No Ledger page describes NFC transaction signing.
- Not for payments. Nothing from Ledger mentions tap-to-pay with the device.
- Not for Ledger Recover (the Coincover subscription service). That is a different product despite the similar name.

### 3.4 Ledger's stance on device payments: CL Card

- VERIFIED (ledger.com/ledger-card): the "CL Card" is a Visa/Mastercard debit card issued by Baanx (Monavate in EU/UK). **"You don't need a Ledger signer to get or use the CL Card."** Funds moved to the card are no longer self-custodied. Apple Pay supported; Google Pay not mentioned. The Ledger device is not involved in the tap.
- INFERRED: Ledger's answer to "pay with crypto by tapping" is a conventional card rail, not device NFC. There is no public Ledger stance on peer-to-peer device payments; I found zero Ledger material on "Ledger to Ledger" transfers.

---

## 4. Host transports: what can actually talk to each device

### 4.1 DMK (current, recommended) — VERIFIED via docs + npm registry (fetched 2026-10-10)

| Package | Version | Underlying API | Platform |
|---|---|---|---|
| `@ledgerhq/device-management-kit` | 1.11.0 | core | all |
| `@ledgerhq/device-transport-kit-web-hid` | 1.2.4 | WebHID (USB) | Chromium browsers, HTTPS/localhost |
| `@ledgerhq/device-transport-kit-web-ble` | 1.3.2 | Web Bluetooth | Chromium browsers |
| `@ledgerhq/device-transport-kit-node-hid` | 1.0.1 | node-hid (USB) | Node.js |
| `@ledgerhq/device-transport-kit-react-native-hid` | 1.0.4 | RN USB | Android |
| `@ledgerhq/device-transport-kit-react-native-ble` | 1.3.2 | react-native-ble-plx | iOS/Android |
| `@ledgerhq/device-transport-kit-speculos` | 1.2.1 | emulator | dev |
| `@ledgerhq/device-transport-kit-mockserver` | 1.1.2 | mock | dev |

No NFC transport. Confirmed by: the transports doc page (lists only the above), the registry search for `@ledgerhq/device-transport-kit` (50 results, zero NFC), and the ts-libs `libs/` listing (`hw-transport`, `hw-transport-mocker` only).

Snippet from the official Flex/Stax guide (VERIFIED, DMK >= 0.4.0):

```typescript
import { DeviceManagementKitBuilder } from "@ledgerhq/device-management-kit";
import { webBleTransportFactory } from "@ledgerhq/device-transport-kit-web-ble";
import { webHidTransportFactory } from "@ledgerhq/device-transport-kit-web-hid";

const dmk = new DeviceManagementKitBuilder()
  .addTransport(webBleTransportFactory)
  .addTransport(webHidTransportFactory)
  .build();
```

Speculos: `.addTransport(speculosTransportFactory("http://localhost:5000"))`.

### 4.2 Legacy ledgerjs — VERIFIED

`@ledgerhq/hw-transport` 6.36.0, `hw-transport-webhid` 6.36.0, `hw-transport-webusb` 6.35.0, `hw-transport-web-ble` 6.35.0, `hw-transport-node-hid` 6.33.5, `hw-transport-node-hid-singleton`, `hw-transport-node-hid-noevents`, `react-native-hw-transport-ble` 6.41.0, `hw-transport-node-speculos`, `hw-transport-mocker`. The ledger-live `libs/ledgerjs` README says these are **frozen/deprecated**; new work should use DMK. Flex/Stax need transport libs >= 8.3.0 per the BLE guide (which contradicts the 6.x versions on npm; the "8.3.0" in the doc looks like a typo or refers to a different package line. **Contradiction, unresolved.**)

```typescript
import TransportBLE from "@ledgerhq/hw-transport-web-ble";
import TransportUSB from "@ledgerhq/hw-transport-web-usb";
const transportBLE = await TransportBLE.create();
const transportUSB = await TransportUSB.create();
```

### 4.3 Windows host reality (this machine)

- Nano S Plus: USB only -> `node-hid` or WebHID in Chrome/Edge. VERIFIED transports exist; Windows support of node-hid is INFERRED (npm metadata lists prebuilds via `pkg-prebuilds`, README not fetched).
- Flex: USB via the same transports. BLE from a desktop: **Ledger Live desktop does not support Bluetooth** (VERIFIED for Nano X via support article 360019138694 snippet: "Bluetooth pairing with a desktop is currently not available"; INFERRED to apply to Flex since Ledger lists BLE as a smartphone feature). Web Bluetooth in Chrome on Windows would work in principle with the `web-ble` transport (INFERRED; Ledger's web-bluetooth tutorial only names Nano X and defers to caniuse).
- NFC from Windows: nothing. No transport, and typical laptops lack NFC readers.

---

## 5. On-device NFC API (the part nobody documents)

> **Correction (2026-10-10).** This section and the NFC conclusions elsewhere in this note are superseded by `nfc-reader-mode.md`. What was wrong:
> - Reader mode is not "documented beyond a header file" only. The SDK has a full app-level reader API (`io_nfc_reader_start` / `io_nfc_reader_send` / `io_nfc_reader_stop`, `CARD_DETECTED` / `CARD_REMOVED` events) in `io_legacy/`, added by PR #777 (2024-12-12) and fixed by #987 and #1044. No production app uses it (PR #1243).
> - The API only delivers events to an app that runs its own IO stack: build with `ENABLE_NFC=1 ENABLE_NFC_READER=1 DISABLE_OS_IO_STACK_USE=1`. Missing the last flag compiles fine and the callbacks never fire.
> - §1 bullets 1-2, the §6 table row ("zero precedent", two Flex units needed) and the §8 verdict ("not with this hardware") are wrong in their reasoning. The counterparty need not be a Ledger: one Flex in reader mode can talk to an Android HCE phone, a Type 4 tag, a JavaCard or a bank card. Only a true Ledger-to-Ledger demo still needs a second NFC Ledger.
> - §3.2: the Recovery Key reader flow runs in BOLOS, not through this app API, and the applet source is public (`LedgerHQ/applet-recovery-key`). §9 gap 2 is answered there.
> - §3.1: the SDK's factory default for the NFC feature bit is on (`include/os_settings.h:164`), so "disabled by default" is unconfirmed.

Source: `LedgerHQ/ledger-secure-sdk` master, all VERIFIED by reading raw files.

### 5.1 Build flags (`Makefile.standard_app`)

```makefile
ifeq ($(ENABLE_NFC), 1)
  ifeq ($(TARGET_NAME),$(filter $(TARGET_NAME), TARGET_STAX TARGET_FLEX TARGET_APEX_P))
    DEFINES += HAVE_NFC
    SDK_SOURCE_PATH += lib_nfc
  endif
endif

ifeq ($(ENABLE_NFC_READER), 1)
  ifeq ($(TARGET_NAME),$(filter $(TARGET_NAME), TARGET_STAX TARGET_FLEX TARGET_APEX_P))
    DEFINES += HAVE_NFC_READER
  endif
endif

ifeq ($(ENABLE_BLUETOOTH), 1)
  ifeq ($(TARGET_NAME),$(filter $(TARGET_NAME),TARGET_NANOX TARGET_STAX TARGET_FLEX TARGET_APEX_P))
    DEFINES += HAVE_BLE BLE_COMMAND_TIMEOUT_MS=2000 HAVE_BLE_APDU
  endif
endif
```

So: NFC is a per-app opt-in on Stax/Flex/Apex+ only; Nano S Plus (`TARGET_NANOS2`) silently gets nothing. Note `lib_nfc/doc/mainpage.dox` still says NFC "is only available on the Stax product" and is marked "to be completed" — **stale doc, contradicted by the Makefile**.

Oddity: `Makefile.defines` puts `HAVE_BATTERY` on `TARGET_NANOX TARGET_NANOS2` only, which is wrong for the S Plus (no battery) and omits Flex/Stax. Looks like a legacy define unrelated to real hardware. Do not trust it.

### 5.2 API (`lib_nfc/include/nfc_ledger.h`, (c) 2025)

```c
typedef enum {
    NFC_LEDGER_MODE_CARD_EMULATION = 0x00,
    NFC_LEDGER_MODE_READER         = 0x01,
} nfc_ledger_mode_e;

void NFC_LEDGER_init(uint8_t force_restart);
void NFC_LEDGER_start(uint8_t mode);  // nfc_ledger_mode_e
void NFC_LEDGER_stop(void);
int  NFC_LEDGER_rx_seph_apdu_evt(uint8_t *seph_buffer, uint16_t seph_buffer_length,
                                 uint8_t *apdu_buffer, uint16_t apdu_buffer_max_length);
uint32_t NFC_LEDGER_send(const uint8_t *packet, uint16_t packet_length, uint32_t timeout_ms);
```

`nfc_ndef.h` adds NDEF Text/URI parsing (`os_parse_ndef`, `os_ndef_to_string`, max text 215 bytes), adapted from ST's lib_NDEF.

### 5.3 Mechanics (`lib_nfc/src/nfc_ledger.c`)

- SEPROXYHAL commands: `SEPROXYHAL_TAG_NFC_POWER_ON_CE`, `SEPROXYHAL_TAG_NFC_POWER_ON_READER`, `SEPROXYHAL_TAG_NFC_POWER_OFF`, `SEPROXYHAL_TAG_NFC_RAPDU`. Packet types `OS_IO_PACKET_TYPE_NFC_APDU` (CE) / `OS_IO_PACKET_TYPE_NFC_APDU_RSP` (reader) fed to `LEDGER_PROTOCOL_*` (same chunking framework as BLE/USB).
- Start only powers the radio if `OS_SETTING_FEATURES_NFC_ENABLED` is set (user setting).
- Chunk buffer is 156+2 bytes with comment `// TODO_IO : BLE buffer size, can be changed though`; `timeout_ms` is `UNUSED`; a `TODO: status is never read?` comment on send. This is young code.
- The MCU (STM32WB35) owns the NFC radio; the SE app only sees APDUs via SEPROXYHAL (consistent with the hardware-architecture doc: "The SE is powerful but lacks inputs and outputs").
- Not in the file: ISO-14443/ISO-DEP/T4T details, MTU, device list. The reader-mode command set the app would send to a tag is undocumented. **Gap.**

### 5.4 Loading a custom app onto a Flex (VERIFIED, developers.ledger.com tools page)

- Sideloading is possible on Nano S Plus, Stax, Flex (Nano X cannot). Each unsigned install asks for the PIN unless a custom CA is installed.
- Custom CA flow: `python3 -m ledgerblue.genCAPair`, enter recovery mode (Flex: unplug, hold power, pick "recovery mode", enter PIN), `python3 -m ledgerblue.setupCustomCA --targetId <id> --public <key> --name dev`, then `SCP_PRIVKEY=...` when loading. Flex target id is `0x33300004`, Nano S Plus `0x33100004` (VERIFIED from `target/*/include/bolos_target.h`).
- Warning: a device with a custom CA fails Genuine Check and cannot install store apps until the CA and its apps are removed. Using the user's daily-driver Flex for this is a real cost.
- Rust alternative: `cargo ledger build flex` then `ledgerctl install -f target/flex/release/app_flex.json`.

---

## 6. Can two Ledger devices talk to each other?

| Channel | Verdict | Why |
|---|---|---|
| NFC Flex <-> Flex/Stax/Gen5 | Theoretically possible, zero precedent | SDK exposes both reader and CE modes to apps. Would need two NFC devices, two custom sideloaded apps, your own APDU protocol, UX for pairing. No doc, no example, no community project found. |
| NFC Flex <-> Nano S Plus | Impossible | S Plus has no NFC. |
| BLE Flex <-> anything Ledger | Not supported | Flex is a BLE peripheral serving the Ledger APDU GATT service; nothing in the SDK lets an app act as a BLE central. INFERRED from `lib_blewbxx` + `HAVE_BLE_APDU` being transport-only. S Plus has no radio anyway. |
| USB Nano S Plus <-> Flex | Impossible | Both are USB devices, neither is a USB host. |
| Via phone/PC relay | **Yes, and this is the only real path** | Host connects to each device with DMK (USB for S Plus; USB or BLE for Flex), devices sign, host moves bytes. |
| Ledger Sync / Key Ring Protocol | Not a device-to-device channel | Syncs Ledger Live instances through Ledger's cloud using device-derived keys (VERIFIED, Ledger blog). Both ends are Ledger Live, not devices. |

Nothing from Ledger (shop, Academy, press, support snippets, SDK) mentions device-to-device communication, "Ledger to Ledger", or offline device payments.

---

## 7. Standalone operation (no host)

- Flex has a battery and touchscreen; the Academy FAQ says you can navigate installed apps, review and sign transactions on-screen, customize lock-screen images, and run the Security Key app. VERIFIED.
- Flex **cannot show balances** without Ledger Live/Wallet ("Balances appear in Ledger Live on a computer or phone"). VERIFIED. It also cannot originate a transaction: an app receives an unsigned tx via APDU, displays it, signs it. It has no network.
- Security Key over NFC with a phone is the one genuinely host-free (no Ledger Live) interaction, but the phone is still the relying-party client.
- Settings on device: Bluetooth and NFC toggles exist (INFERRED from the support "settings" article title and `OS_SETTING_FEATURES_NFC_ENABLED`; article body not loadable).
- Nano S Plus: nothing without USB power and a host. VERIFIED (no battery).

---

## 8. Feasibility verdict for the two starter ideas

### Idea 2: "Swipe Ledger on Ledger over NFC to pay"

**Not in 3 days. Not with this hardware.** Minimum requirements you lack: a second NFC-capable Ledger; a custom C/Rust device app with `ENABLE_NFC_READER=1` on one side and `ENABLE_NFC=1` (card emulation) on the other; a custom CA on both (breaking Genuine Check); a protocol design; and a story for how a signed transaction gets broadcast when neither device has a network. Even if all that worked, the "receiving" device gains nothing: funds land on-chain at an address, the device just learns about it later from a host.

**Honest architecture if the pitch must keep the "tap" moment:**
1. Receiver's phone (or an NFC tag / QR) presents a payment request (address, amount, chain).
2. Sender's phone (Ledger Wallet-style app you write with DMK React Native BLE, or a web app on the Windows PC with WebHID/WebBLE) reads it.
3. Sender's Ledger (Flex over BLE/USB, or Nano S Plus over USB) clear-signs the transaction; human confirms on device.
4. Host broadcasts. Receiver's host sees the incoming tx.
The Ledgers are signers, the phones/PC are the wallet. That is exactly what Ledger's stack is built for, and it fits the hackathon's "clear boundary between autonomous agent and human approval" rubric.

Alternative that *does* use Flex NFC honestly: use the **Security Key app as-is** (FIDO2 over NFC to a phone) as the human-presence gate for an agent, e.g. the agent's payment service requires a WebAuthn assertion from the Flex tapped on a phone before it proceeds. No custom firmware, no new transport, real NFC tap in the demo. Nano S Plus can do the same over USB.

### Idea 1: Voice agent + face scan + Ledger confirm

Hardware-wise trivial: all signing goes through DMK over USB (either device) or BLE (Flex via phone). NFC is irrelevant. Face scan is a software layer on the host and does not involve Ledger. The Ledger confirmation on-screen is the real security step; the face scan is UX theatre unless it gates something the Ledger does not already gate. Be ready for that jury question.

---

## 9. Open gaps

1. Support articles 18934878523037 ("Ledger devices and NFC"), 12350325732893 (Security Key), 9774032283293 (touchscreen settings) are JS-rendered; four fetch routes (direct, /hc/ URL, Zendesk API JSON, r.jina.ai proxy) returned nothing. Claims from them above are from search snippets only. Someone with a browser should read them.
2. Recovery Key app source: Ledger says it is reviewable; repo not found. Would confirm reader-mode usage and show a complete NFC reader app to copy from.
3. Whether Ledger's app store would ever accept a third-party app with `ENABLE_NFC_READER`. No policy found.
4. Whether DMK `web-ble` actually works with a Flex in Chrome on Windows 11. Ledger's own web-bluetooth tutorial predates Flex.
5. The "transport libraries v8.3.0" line in the Flex/Stax BLE guide vs 6.x on npm.
6. iOS minimum (14+ vs 15+) across two Ledger pages.
7. Gen5 screen resolution orientation (300x400 vs 400x300).

---

## 10. Sources

Ledger shop / marketing
- https://shop.ledger.com/products/ledger-flex
- https://shop.ledger.com/products/ledger-nano-s-plus
- https://shop.ledger.com/pages/hardware-wallets-comparison (redirect target of https://www.ledger.com/compare)
- https://ledger.com/academy/topics/ledgersolutions/10-most-frequently-asked-questions-about-ledger-flex
- https://www.ledger.com/academy/topics/ledgersolutions/how-to-use-ledger-recovery-key
- https://www.ledger.com/en/ledger-card
- https://ledger.com/how-we-used-ledger-key-ring-protocol-in-ledger-live
- https://www.businesswire.com/news/home/20240726882083/en/Introducing-LEDGER-FLEX-Easy-Secure-Self-Custody-Free-From-Compromise
- https://www.businesswire.com/news/home/20251023549325/en/The-Next-Era-of-Ownership-Begins-with-the-All-New-Ledger-Nano-and-Ledger-Wallet

Ledger support (JS-rendered; snippets only)
- https://support.ledger.com/article/18934878523037-zd (Ledger devices and NFC)
- https://support.ledger.com/article/12350325732893-zd (Ledger Security Key app)
- https://support.ledger.com/article/9774032283293-zd (touchscreen device settings)
- https://support.ledger.com/article/360019138694-zd (Nano X Bluetooth; "desktop pairing not available")

Ledger developer docs
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/transports
- https://developers.ledger.com/docs/device-interaction/dmk-ts/integration/how_to/dmk
- https://developers.ledger.com/docs/device-interaction/beginner/ble_flex_stax
- https://developers.ledger.com/docs/device-interaction/dmk-ts/ledgerjs/integration/web-application/web-bluetooth
- https://developers.ledger.com/docs/transport/overview
- https://developers.ledger.com/docs/device-app/explanation/ledger-os/hardware-architecture
- https://developers.ledger.com/docs/device-app/references/tools
- https://developers.ledger.com/docs/device-app/develop/quickstart
- https://developers.ledger.com/docs/ai-tools/hardware-security/security-key

LedgerHQ GitHub (raw files read)
- https://github.com/LedgerHQ/ledger-secure-sdk
- https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/lib_nfc/include/nfc_ledger.h
- https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/lib_nfc/include/nfc_ndef.h
- https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/lib_nfc/src/nfc_ledger.c
- https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/lib_nfc/doc/mainpage.dox
- https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/Makefile.standard_app
- https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/Makefile.defines
- https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/target/flex/include/bolos_target.h
- https://raw.githubusercontent.com/LedgerHQ/ledger-secure-sdk/master/target/nanos2/include/bolos_target.h
- https://github.com/LedgerHQ/app-security-key and its develop/Makefile
- https://github.com/LedgerHQ/ledger-live/blob/develop/libs/ledgerjs/README.md
- https://api.github.com/repos/LedgerHQ/ts-libs/contents/libs
- https://github.com/LedgerHQ/app-recovery-key (404)

npm registry
- https://registry.npmjs.org/-/v1/search?text=%40ledgerhq%2Fdevice-transport-kit&size=50
- https://registry.npmjs.org/node-hid/latest

Press (secondary)
- https://decrypt.co/326759/ledger-introduces-physical-recovery-key-nfc-backup-for-wallets
- https://www.theblock.co/post/359217/ledger-recovery-key
- https://bitcoinmagazine.com/business/ledger-nano-gen5-debuts-affordable-hardware-security-for-ai-driven-digital-identities
- https://techcrunch.com/2024/07/26/ledger-launches-ledger-flex-a-mid-range-hardware-crypto-wallet
