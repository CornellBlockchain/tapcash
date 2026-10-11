# Tangem card protocol, as needed for a Ledger Flex reader app

Research note for N3XT @ OP3N 2026, written 2026-10-10. Purpose: let the collaborator's Ledger Flex, running the ledger-cash C app in NFC reader mode, read and use Sahas's Tangem cards. Code that uses these facts: `mvp/tangem/` (`tangem.c`, `mock_tangem.py`). Nothing here was run against a real Tangem card.

Each claim is marked VERIFIED (read in source; path and commit given) or INFERRED (reasoned, or about Sahas's specific cards and not checkable without hardware).

**Sources.** Unless stated otherwise, paths are relative to `tangem-sdk-core/src/main/java/com/tangem/` in `tangem/tangem-sdk-android` at **`cdf62aacbe3e4303c61cb22d7e48a4abb136aefa`** (2025-07-02). That is the last commit before the licence change, and its `LICENSE` is MIT. Cross-checks come from `tangem/tangem-sdk-ios` at **`05eabcc908a11c6cdbfeeba8576d99e36c843f14`** (2025-06-30, also MIT). Current heads, read only to confirm the licence: android `3eb79da284` (2026-09-13), ios `5a163f1aad` (2026-10-05).

## 0. Licence: a decision for Sahas before anything is published

- Both SDKs were MIT until July 2025. The licence changed in android `978fc7e353` (2025-07-16) and ios `43ff76aa1c` (2025-07-09). VERIFIED (`gh api repos/tangem/tangem-sdk-{android,ios}/commits?path=LICENSE`, and the `LICENSE` contents at each SHA). GitHub reports the new licence as `NOASSERTION`.
- The current licence is "Tangem Proprietary and Confidential". It defines "Protocol" as "the proprietary communication protocol, including the sequence of, data structures, and cryptographic methods used to interact with Tangem hardware". §4 reads, verbatim: *"Reverse-engineering, decompiling, or attempting to recreate the Protocol for use in unauthorized applications is strictly prohibited. Any interaction with Tangem hardware in commercial or distributed applications requires a separate commercial agreement with Tangem."* §2 allows personal, non-commercial use, including "Use the Software to interact with Tangem hardware for personal needs". VERIFIED (current `LICENSE` at android `3eb79da284`).
- What we did: every fact in this note and in `mvp/tangem/` comes from the MIT snapshots. The two test vectors we reuse are cited to that MIT commit, and no SDK code was copied. `tangem.c` and `mock_tangem.py` are written from the facts below.
- What we cannot settle: whether a hackathon submission (a public GitHub repo, a demo video, a post tagging @Ledger) counts as a "distributed application" under §4, and whether a protocol restriction binds anyone who never accepted the new licence. That is a legal question for Sahas, not something to decide in code. The options are: keep the Tangem track private and out of the submission, ask legal@tangem.com, or ship it and accept the risk. This is also a Ledger event showing a competitor's card, which is a separate question about how it looks. **Decision needed from Sahas.**

## 1. Bottom line for the demo

1. **Reading a Tangem card from the Flex is plain ISO 7816.** SELECT the AID `A000000812010208`, then send `Read` (INS `F2`) with the SHA-256 of the access code in a TLV. Without encryption it is three APDUs and about 200 bytes each way. VERIFIED (protocol). Whether a given card accepts plaintext is INFERRED; the card says so with status word `6982`.
2. **The address the Tangem app shows is not the card's master key.** Wallet 2.0 cards are HD wallets. The card derives keys itself when Read is sent in wallet mode with an HD path TLV, and the ETH address comes from `m/44'/60'/0'/0/0`. VERIFIED that the card does the derivation (`operations/read/ReadWalletCommand.kt:67`, `operations/derivation/DeriveWalletPublicKeyTask.kt`). That the Tangem app uses exactly this path for ETH is INFERRED (the app's source is a separate repo we did not read). Hardware check: the address on the Flex must equal the address in Sahas's iPhone Tangem app.
3. **The Tangem card can sign an EIP-712 digest.** Sign (`FB`) signs a raw 32-byte hash and returns `r||s` with no recovery id. The Flex finds `v` with the `ecrecover` that already exists in `cash.c`, and must normalise to low-s. VERIFIED (protocol). Plaintext sign and the security delay on Sahas's cards are INFERRED.
4. **Proof that a card is genuine is only partial offline.** AttestCardKey (`F3`) proves the card holds the private key for its card public key. Tangem's certificate for that key is fetched online from `verify.tangem.com`. Offline, the Flex can check a manufacturer signature over the card ID, but that signature can be copied to another card. VERIFIED.
5. **Risks that only hardware can settle:** reply size against the Flex's 271-byte reader limit; whether the Flex MCU handles extended-length Lc; plaintext versus `6982`; whether Read needs the access code.

## 2. Framing

| Item | Fact | Status |
|---|---|---|
| SELECT | `00 A4 04 00 08 A0 00 00 08 12 01 02 08`, no Le (`common/apdu/Apdu.kt:14,19`) | VERIFIED |
| SELECT reply | The SDK only checks that the transceive succeeded; it never parses the reply (`common/core/CardSession.kt:158,420-423`). Content (FCI or bare `9000`) unknown. | VERIFIED / content INFERRED |
| Command APDU | `CLA=00`, `INS`, `P1` = encryption mode (0 none, 1 fast, 2 strong), `P2=00`, then **always extended Lc `00 hi lo`**, then the TLV body; no Le (`common/apdu/CommandApdu.kt:42-62,84`) | VERIFIED |
| Extended length fallback | `Command.kt` handles `ExtendedLengthNotSupported` only by dropping terminal keys and retrying, so the framing stays extended (`operations/Command.kt:86-99`) | VERIFIED |
| Reply | TLV body followed by SW1 SW2 (`common/apdu/ResponseApdu.kt`) | VERIFIED |
| TLV | 1-byte tag. Length is 1 byte, or `FF hi lo` for lengths of 0xFF and up (`common/tlv/Tlv.kt:46-82,94-115`). An empty value is serialised as tag + `00`. | VERIFIED |
| Integers | Big-endian; uint8/16/32 by tag (`common/tlv/TlvTag.kt:161-198`, `common/extensions/Int.kt`) | VERIFIED |
| Strings | UTF-8; the recorded card pads with a trailing NUL (`"secp256k1\0"`, `"2.11r\0"`) | VERIFIED (vector) |
| Booleans | True if the tag is present; the decoder ignores the value (`common/tlv/TlvDecoder.kt:98-101`) | VERIFIED |
| HD path | `6A`: 4 bytes big-endian per node, hardened = index + `0x80000000` (`crypto/hdWallet/DerivationNode.kt:13,40`) | VERIFIED |
| `LegacyMode` tag `29` = 4 | Sent by iOS on "poor NFC quality" iPhones (iPhone 7 family) (`TangemSdk/Operations/Command.swift:33-39`, ios `05eabcc908`). Its effect on the card is not documented. A possible knob if long replies fail on the Flex. | VERIFIED sent / effect INFERRED |

## 3. Status words

From `common/apdu/StatusWord.kt` and `operations/Command.kt:139-205`. VERIFIED.

| SW | Meaning | What the reader should do |
|---|---|---|
| `9000` | success | |
| `9001`–`9007` | success; PIN 1/2/3 changed variants | treat as success |
| `9789` | NeedPause: security delay running. The reply carries `1C` Pause = time remaining | **resend the identical APDU** and keep the card in the field (`Command.kt:153-163`) |
| `6982` | NeedEncryption | the SDK escalates None → Fast → Strong, then gives up (`Command.kt:165-181`) |
| `6AF1` | invalid access code | ask for the access code |
| `6A86` | invalid params; on Read this means the access code is required (`operations/read/ReadCommand.kt:51-56`) | ask for the access code |
| `6AF2` | invalid passcode (PIN2) | |
| `6A88` | wallet not found | try the next wallet index |
| `6985` | invalid state | |
| `6A82` | file not found | |
| `6D00` | INS not supported | |
| `6A89` | wallet already exists | |
| `6286` | error processing command | |

The unit of Pause is **centiseconds**: iOS divides by 100 to get seconds (`Operations/Command.swift:199-209`, `remainingCs / 100`). Android names the value `ms` but passes it straight through. VERIFIED (iOS, explicit).

## 4. Commands we use

The access code is sent as `10` Pin = SHA-256(code as UTF-8). The default code is `"000000"`, and SHA-256 of it is `91b4d142823f7d20c5f08df69122de43f35f057a988d9619f6d3138485c9a203`. That hash is the same 32 bytes as in the SDK's own CommandApduTest READ vector. VERIFIED (`common/UserCode.kt:15-21`, `src/test/.../CommandApduTest.kt`, and `python -c "import hashlib;print(hashlib.sha256(b'000000').hexdigest())"`). The default passcode (PIN2) is `"000"`, SHA-256 `2ac9a674…55ef`. VERIFIED.

### 4.1 Read `F2`, card mode (`operations/read/ReadCommand.kt:65-71`)

Request TLVs: `10` Pin, `23` InteractionMode = `01`, and `5C` TerminalPublicKey only if a linked terminal is used (we do not use one). VERIFIED.

Reply TLVs. `common/deserialization/CardDeserializer.kt` decodes them; tag numbers are in `common/tlv/TlvTag.kt`. VERIFIED.

| Tag | Field | Notes |
|---|---|---|
| `01` | CardId | 8 bytes |
| `02` | Status | 0 not personalised, 1 empty, 2 loaded, 3 purged |
| `80` | Firmware | ASCII, e.g. `"6.33r"`; the letter is r/d/s |
| `03` | CardPublicKey | secp256k1, 65 bytes; the card's attestation key |
| `0A` | SettingsMask | big-endian. Bits: `0x1000` AllowUnencrypted, `0x2000` AllowFastEncryption, `0x200000` AllowHDWallets, `0x0800` SmartSecurityDelay, `0x0080` ProhibitDefaultPIN1 (`common/card/Card.kt:397-424`). Supported modes are always Strong, plus Fast or None if their bits are set (`Card.kt:382-386`). |
| `0C` | CardData | nested TLVs: `81` BatchId, `82` ManufactureDateTime, `83` IssuerName, `84` BlockchainName, `86` CardIdManufacturerSignature |
| `20` | ManufacturerName | |
| `30` | IssuerPublicKey | |
| `05` | CurveId | firmware below 4 only (one wallet) |
| `60` | WalletPublicKey | firmware below 4 only; on 4.x and later wallets come from wallet / wallets-list mode |
| `09` | PauseBeforePin2 | multiplied by 10 to give the security delay in ms (`CardDeserializer.kt` cardSettings) |
| `66` | WalletsCount | firmware 4 and later |
| `5A` / `59` | PinIsDefault / Pin2IsDefault | firmware 4.33 and later / 4.1 and later |
| `D0`, `D1`, `2F` | backup status, backup count, user settings | |

Firmware gates (`common/card/FirmwareVersion.kt`): MultiWallet 4.0, HD wallet 4.39, access-code status 4.33, backup 4.43, keys import 6.21. VERIFIED.

### 4.2 Read `F2`, wallet mode (`operations/read/ReadWalletCommand.kt:61-69`)

Request: `10` Pin, `01` CardId, `23` = `02`, `65` WalletIndex (uint8), and `6A` HD path if one is wanted. VERIFIED.
Reply: `01` CardId, `02` wallet Status (1 empty, 2 loaded, 3 purged, 0x81/0x82/0x83 backed-up variants, 0x42/0xC2 imported), `05` CurveId, `0A` wallet settings, `60` WalletPublicKey (**derived** when a path was sent), `6B` WalletHDChain, `63` SignedHashes, `65` WalletIndex (`common/deserialization/WalletDeserializer.kt`, `common/card/CardWallet.kt:78-113`). VERIFIED.
Wallets-list mode (`23` = `03`) returns repeated `68` CardWallet TLVs and pages with `65` WalletIndex = the number received so far (`operations/read/ReadWalletsListCommand.kt:48-71,72-80`). VERIFIED. We avoid it because the reply can be large (§6).

### 4.3 Sign `FB` (`operations/sign/SignCommand.kt:176-201`)

Request, in SDK order: `10` Pin, `11` Pin2, `01` CardId, `51` TransactionOutHashSize (1 byte, `20`), `50` TransactionOutHash (the hashes concatenated), `19` Cvc (not used), `65` WalletIndex, `57`/`5C` terminal signature and key (linked terminal; skipped for firmware 4.39 and later, `:253-258`), `6A` HD path. VERIFIED.
Reply: `01` CardId, `61` WalletSignature = `r||s` per hash, 64 bytes for secp256k1 with **no recovery id**, `63` total signed hashes (`:204-228`). VERIFIED. The card signs the 32 bytes it is given as-is (the SignHash method; there is a pre-check against `defaultSigningMethods`, `:100`). The SDK normalises secp256k1 signatures to low-s afterwards when `canonizeSecp256k1Signatures` is set (`:230-238`), which implies the card can return high-s. VERIFIED. USDC's ECRecover rejects high-s, so the Flex must normalise too.
The SDK always requires a passcode for Sign (`requiresPasscode() = true`, `:78`). Wallet 2.0 cards normally leave PIN2 at its default. INFERRED.

### 4.4 AttestCardKey `F3` (`operations/attestation/AttestCardKeyCommand.kt`)

Request: `10` Pin, `01` CardId, `16` Challenge (the SDK uses 16 random bytes, `:75`), and `23` mode only if backup is active. Reply: `01` CardId, `17` Salt, `04` CardSignature, plus `D6` linked backup card keys. Verification is ECDSA-secp256k1 by CardPublicKey over **SHA-256(challenge || salt)** (with `"BACKUP_CARDS" || keys` appended when the card has backups), in raw `r||s` form (`:42-48`, `crypto/Secp256k1.kt:47-59` uses `SHA256withECDSA`). VERIFIED.

### 4.5 OpenSession `FF` (encryption, not implemented)

- Request: `1A` SessionKeyA, with `P2` = mode. Reply: `1B` SessionKeyB, `0B` Uid (`operations/OpenSessionCommand.kt`). VERIFIED.
- Fast mode: keyA is 16 random bytes, and the secret is keyA || keyB. Strong mode: keyA is an ephemeral secp256k1 public key, and the secret comes from ECDH (`crypto/EncryptionHelper.kt`). VERIFIED.
- Session key: SHA-256(secret || PBKDF2-HMAC-SHA256(password = SHA-256(access code), salt = uid, 50 iterations, 32 bytes)) (`common/core/CardSession.kt:425-466`, `crypto/Pbkdf2.kt`). VERIFIED.
- Command body: AES-256-CBC with an all-zero IV and PKCS7 padding over `len(2 BE) || CRC16(0x6363 init, ITU-V.41) || TLVs`, sent with P1 = mode. Replies are decrypted the same way and the CRC is checked (`common/apdu/CommandApdu.kt:63-75`, `common/apdu/ResponseApdu.kt:39-62`, `crypto/CryptoUtils.kt:190-205,232`, `common/extensions/ByteArray.kt:76-79`). VERIFIED.
- A Ledger app could do all of this with `cx_sha256`, `cx_hmac_sha256`, `cx_aes` and (for strong mode) `cx_ecdh`. It has not been built. It is the next step if the card answers `6982` (§7).

## 5. Default behaviour of current cards

| Question | Answer | Status |
|---|---|---|
| Is encryption required by default? | The SDK starts every command in plaintext and escalates only when the card answers `6982`. Whether to accept plaintext is decided by the card, through the AllowUnencrypted bit. The SDK's own v4 personalisation test configs set `protocolAllowUnencrypted: true` and `protocolAllowStaticEncryption: true` (`src/test/resources/jsonRpc/Personalize_v4.json:30-31`). Production Wallet 2.0 configs are not public. | VERIFIED mechanism / INFERRED for Sahas's cards |
| Does Read need the access code? | The SDK always sends it. iOS has a comment saying "new read works without pin" for firmware 4.43 and later (`Operations/Command.swift:156`). | INFERRED; hardware gate |
| Security delay | Triggered by the card (`9789` + Pause). SmartSecurityDelay is set in the test configs. Read is unlikely to trigger it; Sign might. | INFERRED |
| Which wallet index is secp256k1 | Read wallet `i`, check CurveId, try the next index on another curve or on `6A88`. | INFERRED (Wallet 2.0 probably creates secp256k1 first) |
| CardId in Read wallet mode | The SDK always sends it. Whether the card requires it is unknown. Our flow gets it from Read card mode first. | INFERRED |

## 6. Size limits on the Flex

- The Flex reader path passes replies of up to **271 bytes**. Anything larger is dropped and shows up as a timeout (`research/nfc-reader-mode.md` §1.5). Raising the SEPH buffer (`ENABLE_ADDRESS_BOOK=1` → 447) is a ledger-cash Makefile change; it is a handoff item.
- The recorded firmware 2.11 Read reply is **375 bytes** (it includes the wallet key). A Wallet 2.0 card-mode Read has no wallet key but has CardData, the issuer key, backup fields and so on. It is roughly 200–300 bytes; our mock answers 198–201. INFERRED: **card-mode Read is the first thing to check on hardware.**
- Wallet-mode Read with an HD path is about 150 bytes, and Sign / AttestCardKey replies are under 120. VERIFIED by construction (`mock_tangem.py`) / INFERRED for the real card.
- Commands: Sign with an HD path is 147 bytes, using extended Lc. Whether the Flex MCU forwards extended-length APDUs in reader mode is unknown (`nfc-reader-mode.md` §9). INFERRED.

## 7. What the Flex can honestly do with a Tangem card

- **(a) PAY-TO-TANGEM: build first.** The Flex reads the card and shows "Pay X USDC to Tangem card AC79…3456, 0x1fb2…0173", then signs EIP-3009 from its own key to that address. The Tangem card works as a cash note that can be handed to someone. The address is the one the Tangem app shows (card-side derivation at `44'/60'/0'/0/0`). This only works if plaintext Read works, either with the default access code or with the payee typing their code on the payer's Flex, which is awkward. A card left on the default code works as a bearer note: whoever holds it can spend it. That suits a "cash" story, provided the risk is stated. **It is not a Read-only demo with the current app.** `cash.c` `pay_check` requires a `payeeSig` that recovers to `payTo`, and the auth goes to a payee device via `PUT_AUTH`; a card provides neither. Chosen route: a pay-to-address path in `cash.c` (address from the card Read, amount typed on the Flex, `payeeSig` check skipped on that path only) plus a USB-readable outbox for the signed auth so a laptop can settle. The alternative, the card signing `payeeSig` itself, needs the role-(b) Sign gates below. Handoff to the ledger-cash workflow: `mvp/tangem/README.md`, Wiring step 4.
- **(b) TANGEM-AS-PAYER: stretch.** The Flex shows the transfer, the user types the Tangem access code on the Flex, and the Flex sends Sign `FB` with the EIP-712 digest. It finds `v` through ecrecover and normalises to low-s, which gives a USDC `transferWithAuthorization` signature from the Tangem's address. The building blocks exist in `tangem.c` and pass against the mock. It depends on plaintext Sign and a tolerable security delay, both hardware gates. The card's signature can also stand in as a real `payeeSig` for the ledger-cash request format (Tangem signs eip191(keccak(body))), so `cash.c` would verify it unchanged.
- **(c) ATTEST: partial, and stated honestly.** Offline, the Flex can prove liveness (a fresh challenge signed by the card key) and can check CardIdManufacturerSignature `86` against Tangem's manufacturer key. That key is `02630EC6371DA464986F51346B64E6A9711C530B1DD5FC3A145414373C231F7862` for "TANGEM" (`operations/attestation/verification/ManufacturerPublicKey.kt:13`). Firmware below 6.21 always uses this key; later firmware selects by ManufacturerName (`ManufacturerPublicKeyProvider.kt`). VERIFIED. The signature covers SHA-256 of the **card ID as an ASCII hex string** in the SDK's own personalisation code (`operations/personalization/PersonalizeCommand.kt:135`, `cardId.toByteArray()`). Production cards may differ. INFERRED. That signature certifies the card ID, not the card key, and it can be copied. Binding the card key to Tangem needs the issuer and manufacturer certificates from `POST https://verify.tangem.com/card/verify-and-get-info` (`operations/attestation/api/TangemVerifyApi.kt:10`, `verification/OnlineAttestationVerifier.kt`): the manufacturer signs the compressed issuer key, and the issuer signs the card key. VERIFIED. On the Flex the claim has to be "a live card holding a key, with a card ID signed by Tangem", not "a genuine Tangem".

## 8. Test vectors used

- READ command, default access code: `00F20000000022 1020 91b4…a203` (tangem-sdk-android `src/test/java/com/tangem/common/apdu/CommandApduTest.kt`, MIT `cdf62aacbe`). Our Read also adds `23 01 01`, as `ReadCommand.serialize` does, so Lc = `25`.
- A recorded 375-byte Read reply from a firmware 2.11r card (CardId `CB22000000027374`, "SMART CASH", single secp256k1 wallet) (`src/test/java/com/tangem/common/apdu/ResponseApduTest.kt`, same commit). It exercises the TLV parser and trailing-NUL strings.
- secp256k1 private key 1 → address `0x7e5f4552091a69125d5dfcb7b8c2659029395bdf` (a widely used Ethereum vector). It checks the keccak hook end to end.

## 9. Open questions (hardware)

1. Does card-mode Read on Sahas's cards fit in 271 bytes, and does the Flex MCU pass extended Lc?
2. Plaintext or `6982`, and what are the mask bits `0x1000` / `0x2000`?
3. Does Read work with the default access code on a card where a code is set (firmware 4.43+ "read works without pin")?
4. Which wallet index is secp256k1, and is the derived key 65 or 33 bytes?
5. Does Sign trigger a security delay, and how long is it?
6. Does the `86` signature verify against `02630EC6…` over SHA-256 of the ASCII card ID?
