# mvp/android — build notes

Ledger Cash Payee: Android HCE app the Flex (NFC reader) taps. Two modes: phone payee, Nano bridge (NFC <-> USB OTG HID).
Nothing here has touched a phone, a Flex or a Nano. Everything below was run on the Windows 11 host, 2026-10-10.

## Layout

```
core/       pure JVM: Protocol.kt (ALL constants + wire structs), Eth.kt (keccak, secp256k1 sign/recover, EIP-191/712),
            HidFraming.kt (Ledger USB HID framing), Payee.kt (APDU handler). Tests: core/src/test/.../CoreTest.kt
app/        Android: MainActivity (one screen), PayeeService (HostApduService), State.kt (shared state + NanoBridge USB)
tools/vector.mjs   prints the viem test vectors hardcoded in CoreTest
../../.github/workflows/android.yml   CI: unit tests + debug APK artifact
```
`app/build.gradle.kts` compiles `core/src/main/kotlin` and `core/src/test/kotlin` into the app (`kotlin.directories.add`), so CI's `testDebugUnitTest` runs the same tests.

## Versions (verified 2026-10-10, pinned)

| What | Pin | Source |
|---|---|---|
| AGP | 9.4.1 | https://dl.google.com/dl/android/maven2/com/android/tools/build/gradle/maven-metadata.xml (latest = 9.4.1) |
| Gradle | 9.6.1 | AGP 9.4 table: "Gradle 9.6.0 / 9.6.0" (min/default), JDK 17/17, Build Tools 36.0.0, max API 37 — https://developer.android.com/build/releases/gradle-plugin. 9.6.1 = patch of the tested minor. |
| Kotlin | built into AGP 9 (no `org.jetbrains.kotlin.android`) | https://developer.android.com/build/migrate-to-built-in-kotlin ; jvmTarget follows compileOptions (17) |
| Kotlin (core standalone) | 2.4.21 | Maven Central kotlin-gradle-plugin metadata |
| BouncyCastle | bcprov-jdk18on 1.86 | Maven Central metadata `<release>1.86</release>` |
| Actions | checkout v7.0.1, setup-java v6.0.1, upload-artifact v7.0.2, gradle/actions v6.4.0 | `gh api repos/<r>/releases/latest` |

## Gradle wrapper (real binary, hash checked)

```
curl -sSLO https://services.gradle.org/distributions/gradle-9.6.1-bin.zip
curl -sSL https://services.gradle.org/distributions/gradle-9.6.1-bin.zip.sha256
9c0f7faeeb306cb14e4279a3e084ca6b596894089a0638e68a07c945a32c9e14
sha256sum gradle-9.6.1-bin.zip
9c0f7faeeb306cb14e4279a3e084ca6b596894089a0638e68a07c945a32c9e14 *gradle-9.6.1-bin.zip
gradle-9.6.1/bin/gradle wrapper --gradle-version 9.6.1 --distribution-type bin --no-daemon   # run in mvp/android
sha256sum gradle/wrapper/gradle-wrapper.jar
497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7 *gradle/wrapper/gradle-wrapper.jar
curl -sSL https://services.gradle.org/distributions/gradle-9.6.1-wrapper.jar.sha256
497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7
```
`distributionSha256Sum=9c0f7f...9e14` added to `gradle-wrapper.properties`. CI also runs `gradle/actions/wrapper-validation`.
Wrapper end to end (downloads the pinned zip, so it also checks `distributionSha256Sum`); `gradlew` has LF endings
(`grep -c $'
' gradlew` → 0) and `.gitattributes` pins `gradlew` to LF:
```
GRADLE_USER_HOME=<scratch>/gradle-home ./gradlew --version
Build time:    2026-06-26 14:25:50 UTC
Revision:      309d128bd9fe8c0b71311878fc660b9cbaa07c51
Launcher JVM:  23.0.2 (Oracle Corporation 23.0.2+7-58)
```
`gradlew` exec bit: Windows checkout has none, so CI does `chmod +x gradlew` (or run `git update-index --chmod=+x mvp/android/gradlew` before committing).

## Test vectors (viem 2.57.4 from ../ledger-cash/settle/node_modules, read-only)

`node tools/vector.mjs` (anvil key 0 = payer, anvil key 1 = payee, token 0x5FbDB2315678afecb367f032d93F642f64180aa3, chainId 31337,
value 1234567, validAfter 0, validBefore 2000000000, body = bytes 0..91):
```
payer 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 payee 0x70997970C51812dc3A010C7d01b50e0d17dc79C8
nonce 0x7fea2a75041518f5fe548a415dd378a67dee9cf8e2f191e7828404abcaba8ca5
digest 0xa9457d92cd57d129e61830d4578fd8f1e889018566323d0161ca7747e64abf55
sig 0x7fd3d68b852d28e545730645c2b2f5f1a7e34cc6d00e442215c4f1ed149d80e272ffd7df6c06e23a297b01dc11a2624617e456fadc3639bee0508593405520f81c
eip191 0x93d71f19eff89addd970eb0d82e1abcfb004836e87b4aaca2444a2df70083deb
sig191 0x7c1ca790ac429786ba62ba60771cfcf0d09194c559b0f548594138fcfdc067d875de3445d1dcf106f15b8c2cef5a91c19d8be0b35afbd26a89c327b99c1543361c
```
Signatures match byte for byte: BouncyCastle `HMacDSAKCalculator(SHA256)` is RFC 6979 like viem/noble, both low-s.
The Ledger SDK signs the same way (`CX_RND_RFC6979`, and `lib_cxng/src/cx_ecdsa.c:289-296` canonicalises s unless `CX_NO_CANONICAL`), so a device signature over the same hash with the same key is the same bytes.

## Sync with the C app (`mvp/ledger-cash/app/src/cash.c`)

The C app was still boilerplate when this track started; `cash.c` appeared at 2026-10-10 19:44 local (re-grep timestamp
`2026-10-10T19:44:06-04:00`). Differences from the spec text handed to this track, all now followed (cash.c wins):

| Item | Spec text | cash.c (now in Protocol.kt / Payee.kt) |
|---|---|---|
| payeeSig | "EIP-191-prefixed keccak256 of the preceding bytes" (ambiguous) | personal_sign of the 32-byte `keccak256(body)`: prefix `\x19Ethereum Signed Message:\n32` |
| receipt | "sig over keccak256(auth)" | `eip191(keccak256(auth))` → `RECEIPT_EIP191 = true` |
| PUT_AUTH checks | to, value, nonce, signer | also `validAfter == 0` and `validBefore == request.validBefore`; request disarmed after one payment |
| SWs | — | no request `B006`, bad auth `B005`, P1/P2 ≠ 0 `6A86`, wrong length `6700`, CLA `6E00`, INS `6D00` |
| label | 24 bytes | printable ASCII 0x20..0x7E, zero padded at the tail only (payer's `label_ok` rejects others) |
| extra INS | — | `SET_REQUEST 0x10` (value u64 ‖ label), `SET_CONFIG 0x12` (chainId u64 ‖ token 20), both need Approve on the device. Used by "Arm request on Nano". |
| payer config | — | Flex `pay_check` refuses a request whose chainId/token ≠ its SET_CONFIG (`B002`). Phone fields must match the Flex config. |

Re-synced 2026-10-10 against cash.c mtime `2026-10-10 19:52:36` (it changed after the 19:44 sync). Since then cash.c
has the reader side (`INS_TAP_TO_PAY 0x30`, `INS_TAP_STATUS 0x31`, SWs `B007` busy, `B008` card gone, `B009` no answer),
answers `SELECT` by AID itself (`9000` for `F04C45444745524341534801`, else `6A82`, cash.c:762-767), and its reader sends
the 17-byte `00 A4 04 00 0C F04C45444745524341534801` (no Le) before `E0 11` (cash.c:678-688). `Protocol.isSelectOurs`
accepts it with or without Le. Protocol.kt now also lists every other cash.c INS/SW (LOAD_CASH 0x20, GET_BALANCE 0x21,
PAY 0x22, GET_AUTHS 0x24, 6985, 6A80, 6A88, B001-B004, B0FF) so one file covers a full trace.
Re-sync: `grep -n 'INS_\|SW_\|eip191\|REQ_\|AUTH_' ../ledger-cash/app/src/cash.c` and diff against `core/src/main/kotlin/ledgercash/Protocol.kt`.

## HID framing source

`ledger-secure-sdk/protocol/src/ledger_protocol.c` (master, fetched 2026-10-10 via `gh api`): header struct
`channel_id u16 | tag u8 | seq_num u16 | size u16`, `TAG_APDU 0x05`, first chunk carries `U2BE(buffer, 2)` = total length,
later chunks `buffer[2..]`, padding trimmed by length. Channel 0x0101, 64-byte reports. Test: 300-byte APDU → 6 reports (57 + 4×59 + 7).

## Commands and decisive output

Core alone (no Android SDK needed; JDK 17+):
```
cd mvp/android && ./gradlew -p core test
CoreTest > requestSigMatchesViem PASSED
CoreTest > hidFraming300 PASSED
CoreTest > requestRoundtrip PASSED
CoreTest > addressesMatchViem PASSED
CoreTest > payeeFlow PASSED
CoreTest > sizes PASSED
CoreTest > eip712MatchesViem PASSED
CoreTest > hidFraming5 PASSED
BUILD SUCCESSFUL in 25s
```
(Run locally with the unzipped `gradle-9.6.1/bin/gradle` from the scratchpad, same version as the wrapper, JDK 23.)

Full Android build locally (Android cmdline-tools 16111833 in a scratch dir; the new `sdkmanager` wants `platforms/android-35`
and `build-tools/36.0.0`, slash syntax; `platforms;android-35` reports "Package platforms not found"):
```
ANDROID_HOME=<scratch>/android-sdk gradle --no-daemon testDebugUnitTest assembleDebug
BUILD SUCCESSFUL in 36s
testsuite name="ledgercash.CoreTest" tests="8" skipped="0" failures="0" errors="0"
app/build/outputs/apk/debug/app-debug.apk  3408989 bytes
aapt2 dump badging: package ledgercash.payee, minSdkVersion 26, targetSdkVersion 35, uses-permission NFC,
  uses-feature-not-required nfc.hce, usb.host; apduservice.xml aid-filter F04C45444745524341534801 category "other"
```
Fixes found by that local build: AGP 9 built-in Kotlin ignores `.kt` added with `java.srcDir`; `kotlin.srcDir` works but is
deprecated → `kotlin.directories.add(...)`.

## Fix stage (2026-10-10, after review)

Debug keystore (JDK 23 keytool, PKCS12):
```
keytool -genkeypair -keystore app/debug.keystore -storepass android -keypass android -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US"
```
```
./gradlew -p core test
CoreTest > requestSigMatchesViem PASSED
CoreTest > hidFraming300 PASSED
CoreTest > requestRoundtrip PASSED
CoreTest > addressesMatchViem PASSED
CoreTest > payeeFlow PASSED
CoreTest > sizes PASSED
CoreTest > eip712MatchesViem PASSED
CoreTest > hidFraming5 PASSED
BUILD SUCCESSFUL in 26s

ANDROID_HOME=<scratch>/android-sdk ./gradlew --no-daemon testDebugUnitTest assembleDebug
BUILD SUCCESSFUL in 34s
tests="8" skipped="0" failures="0" errors="0"
java -jar <build-tools>/lib/apksigner.jar verify --print-certs app/build/outputs/apk/debug/app-debug.apk
Signer #1 certificate DN: CN=Android Debug, O=Android, C=US
Signer #1 certificate SHA-256 digest: 9a8bc04dbdc98e05399f16478c60bf6152a9a5761c9721c2f7953c8f19e27903
keytool -list -v -keystore app/debug.keystore   ->  SHA256: 9A:8B:C0:4D:...:19:E2:79:03   (same key)
aapt2 dump xmltree ... AndroidManifest.xml  ->  allowBackup(0x01010280)=false
```

## Not verifiable here

- CI itself (no commits from this track). It relies on ubuntu-latest's preinstalled SDK + AGP auto-download of
  `platforms;android-35` / `build-tools;36.0.0`. If the first run fails on a missing SDK package, add
  `android-actions/setup-android@v4.0.4` before the Gradle step.
- Anything on a phone, Flex or Nano.

## Decisions

- Phone payee answers inside `processCommandApdu` (secp256k1 sign ≈ ms). Nano bridge returns `null` and calls `sendResponseApdu` from a single USB thread.
- Bridge answers SELECT itself and forwards only the rest. (cash.c now answers SELECT too, but over USB the Nano never needs it.)
- Bridge keeps a copy of auths that pass through (checked against the Nano's last GET_REQUEST + EIP-712 signer), so Share works in both modes.
- Phone key: 32 random bytes in `filesDir/payee.key` (app-private). Auths: `filesDir/auths.jsonl`. No Keystore: secp256k1 is not a Keystore curve.
- No AndroidX, no layouts: plain `Activity`, views in code. Only dependency: bcprov.
- Phone request `validBefore = UINT64_MAX` (`-1L`), same as cash.c (fix stage: `now + 1 h` made an auth unsettleable
  once the laptop settled more than an hour after the tap, after the Flex had already debited its cash). JSON writes it as
  `18446744073709551615`; settle.mjs does `BigInt(a.validBefore)`. Checked in `CoreTest.payeeFlow`.
- Received auths are worded "Got authorization (unsettled IOU) for X USDC": the phone cannot check funding or payer
  genuineness offline.
- Fixed debug signing key `app/debug.keystore` (public, demo only) so CI APKs update in place and the phone payee key
  (where settled USDC lands) is never wiped by an uninstall. `android:allowBackup="false"` keeps that key out of backups.
- `onAuth` (persist) runs in `runCatching`: a disk error must not stop the receipt after the payer already debited.
  `State.init` skips a corrupt `auths.jsonl` line instead of crashing the service on every start.

## Interop with cash.c (2026-10-10)

`core/src/main/kotlin/ledgercash/InteropMain.kt` runs the phone payee as a card on stdin/stdout (one hex APDU per line
in, one hex reply per line out). It calls `InteropMain.card(args)`, which is `Payee.handle` (the PayeeService
PHONE-mode path) with a fixed test key. `core/build.gradle.kts` gains the `application` plugin so that `installDist`
gives a runnable classpath:
```
sh ./gradlew -p core --no-daemon -q installDist
printf '00a404000cf04c45444745524341534801\ne011000000\n' | java -cp "core/build/install/core/lib/*" ledgercash.InteropMain 5000000 coffee 31337 5fbdb2315678afecb367f032d93f642f64180aa3 1c0ffee0
ready 0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc
9000
0000000000007a695fbdb2315678afecb367f032d93f642f64180aa33c44cdddb6a900fa2b585dd299e03d12fa4293bc00000000004c4b40ffffffffffffffff1c0ffee0636f...9000
```
`../ledger-cash/interop/android_payee_tap.py` taps it with a Speculos Flex payer running cash.c (see
../ledger-cash/NOTES.md, "Interop"). It found these mismatches, now fixed here (cash.c is the source of truth):

| Input | Phone before | cash.c / phone now | Fix |
|---|---|---|---|
| auth with v = 0/1 (same signature) | `01`+receipt, request paid | `B005` (USDC reverts v not in 27/28) | `Eth.recover`: v 27/28 only |
| `E0 24 01 00` (host INS, P1 != 0) | `6A86` | `6D00` (NFC allowlist before P1/P2) | `Payee.handle` order |
| SELECT with trailing Le | `9000` | `6700` (SDK `apdu_parser`: exactly 5 + Lc) | strict length first |
| `E0 11 00 00 01` (Lc 1, no data) | `B006` | `6700` | strict length first |
| SELECT our AID, P1 != 04 | `6E00` | `6A82` | any `00 A4` is a SELECT |

`Protocol.isSelect`/`isSelectOurs` stay lenient for the Nano-bridge path, where the Nano answers everything else
itself. `CoreTest.payeeFlow` now sends SELECT without Le, as cash.c's reader does, and checks that SELECT+Le gives 6700.
These are app code changes (`Payee.kt`, `Eth.kt` and `InteropMain.kt` are compiled into the APK), so CI rebuilds the
APK on push.

`core/src/test/kotlin/ledgercash/InteropVectors.kt` is GENERATED by that script. It holds 3 payee processes: the paid
tap plus the stranger-reader checks, the v-parity/high-s/re-receipt replay, and the tampered-request tap.
`InteropTest` replays it byte for byte. The vectors are embedded as Kotlin, not as a resource, because
`app/build.gradle.kts` only adds core's kotlin test dir.
```
sh ./gradlew -p core --no-daemon test        # JDK 23.0.2, Gradle 9.6.1, Kotlin 2.4.21
CoreTest > requestSigMatchesViem PASSED
CoreTest > hidFraming300 PASSED
CoreTest > requestRoundtrip PASSED
CoreTest > addressesMatchViem PASSED
CoreTest > payeeFlow PASSED
CoreTest > sizes PASSED
CoreTest > eip712MatchesViem PASSED
CoreTest > hidFraming5 PASSED
InteropTest > replaysRecordedTap PASSED
BUILD SUCCESSFUL in 11s
```
CI has a new `interop` job (temurin 17, `./gradlew -p core test`, no Android SDK). The `apk` job's
`testDebugUnitTest` runs the same tests. The full Android build (`assembleDebug`) was not run locally this time,
because this session's scratch has no SDK.
