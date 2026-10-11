# Prior art for ledger-cash (2026-10-11)

We ran three parallel searches: hackathon showcases, GitHub code, and products, industry and papers. Source texts and shallow clones of third-party repos are in `prior-art/`. They are read-only and nothing in them is ever run. The clones are gitignored; `prior-art/industry/` is committed. V = read in a primary source. I = inferred.

## 1. Products, pilots, standards, papers

| # | Name | Type | How offline value moves | How double spending is stopped | Sim (1-5) | Link | V/I |
|---|---|---|---|---|---|---|---|
| 1 | Visa OPS, "Towards a Two-Tier Hierarchical Infrastructure" (2020) | paper | Payer moves funds online into a TEE app (server-signed debit); payee sends a request with its certificate; TEE deducts, then signs; payee claims online later | Deduct inside the TEE before the signature leaves; attested TEE key certificates; monotonic counter in every message; server spent log at claim | 5 | https://arxiv.org/abs/2012.08003 | V |
| 2 | BIS Project Polaris offline handbook (2023) | standard | Fully offline / intermittently offline / **staged offline** (the payee cannot use the value until it settles online) | Tamper-resistant purses; online and offline balances kept separate; one-time acceptance; limits on value held, per payment, and count or total before going online; counterparty blocklist | 5 | https://www.bis.org/publications/project-polaris-handbook-offline-payments-cbdc.pdf | V |
| 3 | Crunchfish Digital Cash | product | Reserve, then pay offline (a trusted app signs L2 instructions), then settle centrally | Local cap = reserved funds; payee verifies against a root certificate | 5 | https://mb.cision.com/Public/14959/4300153/89af315b1150360d.pdf | V (vendor) |
| 4 | Keycard Payment Network (Status, 2019, never deployed) | open-source prototype | Keycard Cash applet signs an EIP-712 payment; POS taps over NFC; the KeycardWallet contract holds ERC20 and honours only that card's key | Contract escrow; per-token max per transaction; minimum block gap; signed block must be at most 10 blocks old, so effectively online | 4 | https://github.com/keycard-tech/payment-network-apps | V |
| 5 | Cashu Numo POS (Feb 2026) | product | Same NFC topology as ours: the merchant phone emulates a Type 4 tag holding a payment request; the payer's wallet reads it and writes back an ecash token | The mint's spent-secret set; Numo needs internet to reach the mint; offline DLEQ proves the mint signed, not that the token is unspent | 4 | https://github.com/cashubtc/Numo | V/I |
| 6 | ECB digital euro offline | pilot/design | Pre-fund, then pay device to device (phone or card); holding limits | Secure hardware, plus forgery checks at defunding (after the fact) | 3 | https://www.ecb.europa.eu/press/pr/date/2024/html/ecb.pr240624~7b3d7581e6.en.html | V/I |
| 7 | G+D Filia / Filia Unplugged | product | Wallet-to-wallet tokens over NFC or BLE; consecutive offline payments | Secure element plus a mutually authorised protocol; caps on holdings and on consecutive payments | 3 | https://www.gi-de.com/en/spotlight/currency-technology/how-to-manage-offline-cbdc-payments | V (claims) |
| 8 | IBM, "Secure and Privacy-preserving CBDC Offline Payments using a Secure Element" (ePrint 2024/1746) | paper | Tokens held under the secure element's control | Secure element deletes spent tokens; double spenders identifiable if it is broken | 3 | https://eprint.iacr.org/2024/1746 | V abstract |
| 9 | Chaum–Pedersen, "Wallet databases with observers" (CRYPTO '92); Brands; the CAFE project | paper | Coins split between the user's wallet and a tamper-resistant observer | Prevention, plus identification of the double spender if tamper resistance breaks | 3 | https://link.springer.com/doi/10.1007/3-540-48329-2_26 | I |
| 10 | Mondex | product | Card to card, fully offline | Tamper-resistant chip, unique IDs and sequence numbers, formally verified (ITSEC E6) | 3 | https://en.wikipedia.org/wiki/Mondex | I |
| 11 | e-CNY hardware wallets ("dual offline", NFC) | pilot | Security-chip cards and SIM wallets over NFC, both sides offline | Security chip plus caps | 3 | https://www.ledgerinsights.com/digital-rmb-yuan-cbdc-sim-card-wallet-offline-payments/ | I |
| 12 | RBA/DFCRC with Capgemini, ANZ and Thales: offline CBDC NFC cards (2023) | pilot | NFC cards paying campus merchants offline | Restricted to certain locations and merchants | 3 | https://www.hfsresearch.com/research/capgemini-cbdc-offline-pilot-program/ | I |
| 13 | Snappy (NDSS 2020) | paper | Fast acceptance (online) | Customer collateral sized to the settlement window; the merchant is repaid from it | 3 | https://arxiv.org/abs/2001.01278 | I |
| 14 | EMV offline risk management (LCOL/UCOL 9F14/9F23, ATC, floor limits) | standard | The card approves offline under a floor limit | Limits on consecutive count and cumulative amount force the card online; the ATC counter detects anomalies at clearing | 3 | https://emvlab.cs.ucl.ac.uk/emvtags/show/t9F23 | I |
| 15 | Kong Cash notes | product | A banknote with a secure element; its key is registered in a contract; the backing is claimable with the chip's signature | Contract escrow tied to the chip key; the bearer holds the note | 3 | (context) https://ethresear.ch/t/crypto-native-cash-bridging-physical-cash-and-defi/23876 | I |
| 16 | Bank of England digital pound offline experiment (2025) | pilot | Vendor designs assessed; nothing built | Secure elements; a breach is found only at reconciliation | 2 | https://www.theregister.com/2025/04/17/boe_cbdc_offline_payments/ | I |
| 17 | Teechain (SOSP '19) | paper | TEE "treasuries" for off-chain channels | TEE plus committee replication | 2 | https://arxiv.org/abs/1707.05454 | I |
| 18 | Bolt Card (NTAG424 DNA, LNURL-withdraw) | product/spec | The tap yields a SUN URL; the merchant's server pays from a Lightning node | AES-CMAC plus a monotonic counter checked by the server; online only | 2 | https://github.com/boltcard/boltcard/blob/main/docs/SPEC.md | V |
| 19 | Coinkite SATSCARD / Opendime | product | Bearer handover; balance needs a chain lookup | Key never exposed until an irreversible unseal | 2 | https://github.com/coinkite/coinkite-tap-proto | I |
| 20 | Tangem card / Note | product | Bearer handover; no card-to-card offline transfer found | Non-exportable key; only partial offline attestation | 2 | https://old.walletscrutiny.com/bearer/tangemnote | I |
| 21 | Arx HaLo / Burner card with Flexa Tap to Pay (ETHDenver 2025) | product | NFC chip signs EIP-191/712; the POS is online | Settled on-chain at payment time | 2 | https://www.businesswire.com/news/home/20250227736077/en | I |
| 22 | Kempen & Pouwelse, offline digital euro with Groth-Sahai proofs (2024) | paper | Offline-first ZK tokens | Detection only, no prevention | 2 | https://arxiv.org/abs/2407.13776 | V abstract |
| 23 | Guiraud et al., offline CBDC design principles (Dec 2025) | paper | Survey | Secure hardware against race attacks | 2 | https://arxiv.org/abs/2512.10636 | V abstract |
| 24 | JCB, IDEMIA and Soft Space (JCBDC) | pilot | Card and phone P2P offline | Not stated | 2 | https://thepaypers.com/crypto-web3-and-cbdc/news/jcb-idemia-and-soft-space-launch-jcbdc | I |
| 25 | Solana Pay NFC (Venta) | product | An NFC tag opens an online wallet transaction | On-chain | 1 | https://solanapay.com/solanapay101 | I |
| 26 | Ledger Flex/Stax NFC (Recovery Key, Security Key); Ledger CL Card | product | No offline payments | n/a | 1 | https://www.ledger.com/en/ledger-card | I |

Negative findings (from search only):
- No Circle offline or tap-to-pay USDC product.
- No Ripple offline or NFC CBDC pilot.
- The CoolWallet Go's NFC moves backups, not funds.
- The Shift USDC card's offline Bluetooth claim is unverified marketing.

### Design ideas to borrow, mapped to the cash ladder

1. **Name v0 "staged offline" (Polaris §4.4, §5.5.2).** The payee accepts the liability until settlement. That is a recognised design class, not a defect. *v0, wording.*
2. **Offline risk parameters (Polaris §4.6.1, EMV LCOL/UCOL, G+D).** Cap the number of payments and the cumulative amount per load. Add a per-payment cap and a small payee blocklist. The device refuses to pay until a new on-screen LOAD_CASH. *v0, cheap NVM counters.*
3. **Put a monotonic counter in the signed authorization (Visa OPS, Mondex, Bolt Card SUN, EMV ATC).**
   - Derive the EIP-3009 nonce from (cash key, load id, counter).
   - Gaps, duplicate counters, or totals above the load become portable proof that a device was cloned or broken. This gives detection after the fact.
   - *v0 for the evidence format; it pays off in v2.*
4. **Reserve funds before loading (Visa Deposit, Crunchfish Reserve, ECB pre-funding).** LOAD_CASH means USDC moved into an escrow contract, which releases only to authorizations from the registered device cash key. Keycard's KeycardWallet is a working template: an authorised key, a per-transaction maximum, a cooldown, and EIP-712. *v2.*
5. **Certify the key once at provisioning (Visa TA registration, Keycard factory registry).**
   - Register the cash key in the escrow contract at load time, instead of attesting each signature (we found per-signature attestation forgeable).
   - This holds only if nothing but ledger-cash can sign with that key. The OS lock on the derivation path must be verified on hardware.
   - *v2.*
6. **The payee keeps a snapshot of the escrow taken while online (Polaris counterparty-list sync).**
   - Offline, the payee can check that the payer's key is registered and was solvent at snapshot time.
   - Ideas 2 and 3 bound the spending since the snapshot.
   - *v2.*
7. **Bond plus slashing (Snappy, Chaum–Fiat–Naor, IBM identification).**
   - The escrow also holds a bond, paid to whoever submits an equivocation proof from idea 3.
   - Double spending becomes economically irrational even if the secure element is broken.
   - *v2+.*
8. **Expiry epochs (Polaris maximum time offline, Keycard's 10-block rule).**
   - Authorizations stay valid until the epoch ends plus a grace period. After that, the owner can reclaim the escrow.
   - This replaces `validBefore = 2^64-1`.
   - *v2.*
9. **Move value into the payee's secure element (Mondex, e-CNY, digital euro, Filia, Visa "Collect").** The payee's Ledger takes the authorization into its own cap and spends it onward offline. This needs real attestation and escrow. *v3, out of scope.*
10. **Not worth borrowing:**
    - bearer handover (Tangem, Satscard, Opendime, Kong), which makes the chip itself the money;
    - Cashu P2PK pre-locking, which locks a token to one payee and does not fit general merchant payments.

### Originality (industry view)

Every primitive already exists:
- the payer debits before signing, on a request the payee initiates (Visa OPS);
- reserve, pay offline, settle later (Crunchfish);
- an escrow contract gated to one card's key (Keycard);
- the merchant as an emulated NFC tag that the payer's wallet reads (Cashu Numo).

Polaris already names our model "staged offline". What we did not find anywhere:
- a screened consumer hardware wallet acting as the NFC **reader**;
- that reads a signed request from another device;
- reviews it on its own secure screen;
- and signs an EIP-3009 authorization.

Every card product is a passive tag with no screen. So the originality lies in the combination and in the trusted-display review on a stock Ledger Flex, settling in plain USDC. It does not lie in the offline-money mechanism.

The v1 negative result is that BOLOS endorsement can be forged by any app on the device. It matches the literature's warning that trusting the secure element alone is fragile, and it points v2 towards registering the key in escrow, plus counters and slashing.

## 2. Hackathon and showcase projects

**Bottom line:** no hackathon project makes a hardware wallet the payer in NFC reader mode. None signs an EIP-3009 authorization over a tap, and none caps spending inside a hardware wallet's secure element. The parts all exist separately, and two projects come close (similarity 4).

| # | Project (event, year) | What it is | Hardware | Offline? | Settlement | Links | Prize | Sim | Same / different |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Better Wallet** (ETHGlobal NYC 2026) V | DIY air-gapped hardware wallet with clear signing; NFC is the only link to the phone (2 taps) | Raspberry Pi 5 + PN532 **reader** + touchscreen; phone is a Kotlin `HostApduService` (HCE), custom AID, about 200-byte APDU chunks | signing offline | phone broadcasts a generic EVM/Solana tx | ethglobal.com/showcase/better-wallet-yvjdh, github.com/BetterWallet/betterwallet-nfc | Uniswap Best Stack Contribution | **4** | Same transport as our phone-HCE mode: a screened wallet reads a phone acting as a card, reviews on screen, and returns the signed payload by tap. Different: the phone is the owner's own and carries a generic tx; no payee request, no cap, no EIP-3009, no Ledger, two taps |
| 2 | **pnm** (ETHGlobal Buenos Aires, Nov 2025) V | "Offline-first hardware-backed payments over NFC"; USDC vouchers with a cumulative counter, expiry and slip ID; the merchant redeems later | Android Keystore P-256 (per the showcase) | yes | USDC Vault escrow; a hub verifies and calls redeem | ethglobal.com/showcase/pnm-w9vhk, github.com/mayur-samrutwar/pnm | Hyperlane x2 | **4** | Same offline voucher-then-settle USDC design, with a client-side offline limit and cumulative counter (`MonotonicCounterManager.kt`). Different: a phone, not a hardware wallet; on-chain escrow. **The repo does not match the showcase:** no NFC code at HEAD (payment is by QR against a localhost hub; Android Beam was removed in Android 14); `Vault.sol` checks EIP-191 secp256k1, not P-256 |
| 3 | **Emergency Cash** (ETHGlobal HackMoney 2026) V | NFC cards as USDC wallets for disasters; payment intents signed offline, settled later on Arc | STM32 + RC522 reader, UID cards | yes | Arc, EIP-191 intents | ethglobal.com/showcase/emergency-cash-5p77m, github.com/yigityektin/emergencydigitalcash | none | 3 | Same offline USDC tap, settled later. Different: the reader derives each card's key from UID plus a reader secret, so the merchant can sign for any card. Not self-custody, no secure screen |
| 4 | **RipPay / ColdTap** (HackKU26, Apr 2026) V | XRPL checkout: merchant Android HCE, buyer phone taps, a **Ledger Nano X** signs over BLE | Ledger Nano X + 2 phones | no | XRPL Payment, online | devpost.com/software/rippay, github.com/CalebMorse06/RipPay | none | 3 | **The only Ledger plus NFC hackathon entry found.** The NFC payload is just `SESSION:<id>`; the Ledger is not the reader; everything is online and server-verified |
| 5 | **Nelo** (Solana Mobile CLOCK IN, Oct 2026, results pending) V README | Offline vouchers; secp256r1 checked on-chain; 128-slot replay window; a double-spend freezes the vault; the offline limit is "bought" by staking | phone | yes | Solana vault holding USDC | github.com/Udoka-AM/nelo | n/a | 3 | Same offline voucher with a spending limit. Different: collateral vault, phone, probably QR (I) |
| 6 | **OverTheEther** (ETHGlobal Bangkok 2024) V | "Tap to pay … offline": buyer signs EIP-712, merchant claims later | phones, **ultrasound** (they abandoned iOS NFC) | yes | smart wallets | ethglobal.com/showcase/overtheether-cqxse | Dynamic, CDP, Morph, Polygon runner-up | 2 | Same sign-now, settle-later. Different: sound instead of NFC, no hardware wallet |
| 7 | **OffWallet / Shadow Protocol** (HACK NEXUS 2026) V README | Offline P2P payments with Android TEE/StrongBox keys, a hardware monotonic counter and a **configurable offline cap** | Android, BLE/QR | yes | backend sync | github.com/HARI-01-01/OffWallet | ? | 2 | Same device-enforced cap. Different: phone TEE, not NFC, not on-chain USDC |
| 8 | **OffGrid Pay** (ETHGlobal New Delhi 2025) V | ERC-20 transfers signed offline and passed over a BLE mesh; the first phone online submits | phones | yes | first online node | ethglobal.com/showcase/offgrid-pay-xu4jb | Flow Killer App 3rd | 2 | Same "anyone settles later". Different: BLE mesh, no cap |
| 9 | **OffChain** (Ripple CBDC Innovate 2022) V | Offline CBDC card, brought online later | ESP32 smart card, NFC | yes | XRPL | devpost.com/software/p2p-cbdc-p2p-loans-9idn1u | event winner | 2 | Same offline hardware cash card. Different: issuer model, issuer-held PIN recovery |
| 10 | Kiosk, NexusPay, Buddy, Taparoo (per-card spend rules), Zap Wallet, NFC wallet (ETHGlobal 2024–2026) V | NFC card / HaLo / HCE tap-to-pay for USDC | HaLo / NTAG / HCE | **online** | live on-chain or backend | ethglobal.com/showcase/... | various | 1–2 | Tap-to-pay USDC, but none is offline, none uses a secure screen or a payee-signed request |

Adjacent, not hackathon entries:
- **seeker-iou** (Solana Seeker): vault IOUs over NFC signed by the Seed Vault. Its own README says end-to-end NFC testing is still to do.
- **Walinox**: a Permit2 signature transfer signed offline from the user's own address; the merchant broadcasts it later; NFC is one of several channels; **no escrow**. This is the closest no-vault design to ours.
- **Numo / Cashu NUT-18**: same tap topology as ours, but it moves ecash bearer tokens.
- **Commercial or spec-only:** Flexa tap-to-pay on Burner cards, Lastmile SDK (Stellar offline vouchers), "NWC over NFC" draft.

Coverage:
- **ETHGlobal:** the showcase ignores its `?search=` parameter, so coverage came from site-limited web searches plus page fetches.
- **Devpost / Devfolio / DoraHacks:** a few entries each.
- **Encode Club / Colosseum:** nothing direct.
- **Ledger prizes:** still zero NFC projects.
- **GitHub API:** searches for "nfc transferWithAuthorization", "nfc eip-3009" and HostApduService plus transferWithAuthorization returned nothing.

Clones (read-only): `prior-art/betterwallet-nfc/`, `prior-art/pnm/` (each with SHOWCASE.md).

### Originality (hackathon view)

The claim holds, but narrowly:
- **Not new on their own:** offline settle-later stablecoin vouchers are common (pnm, Nelo, Emergency Cash, OverTheEther, OffGrid Pay, Walinox), and a screened wallet reading a phone's HCE card over NFC exists once (Better Wallet).
- **New, as far as we found:**
  - a **Ledger** as the **NFC reader**, taking a **payee-signed** request;
  - the **EIP-3009 authorization returned on the same tap**;
  - a **spending cap enforced inside a hardware wallet's secure element, behind its secure screen**;
  - Ledger-to-Ledger operation.
- **Do not claim** "first device-enforced offline cap": pnm (client-side limit and counter) and OffWallet (TEE counter with a cap) do that on phones.
- **Judges will ask about double spending.** pnm, Nelo and seeker-iou lock collateral because a signature cannot stop the owner spending the same USDC from another signer. ledger-cash's cap limits a stolen device, not the owner's other keys. The pitch answer: the payee carries the risk until settlement ("staged offline", Polaris), or small amounts settle quickly, and v2 escrow closes it.

## 3. GitHub and other code hosts

**Bottom line:** nothing rates a 5. In every NFC crypto-payment project found, the payer is the card or tag (Android HCE or a physical card) and the merchant is the reader. A hardware wallet acting as the reader did not turn up, and neither did EIP-3009 over NFC.

**Ledger NFC reader mode:**
- Code search for `io_nfc_reader_send/start`, `NFC_LEDGER_MODE_READER`, `HAVE_NFC_READER`, `ENABLE_NFC_READER`, `NFC_LEDGER_send` and `os_parse_ndef` hits only the SDK, Speculos, one SDK fork (`nadeem-magnus/ledger-secure-sdk`) and our own (private) repo. **No third-party app uses reader mode.** (V)
- `ENABLE_NFC` turns up in 74 Makefiles. It is active only in `LedgerHQ/app-security-key`; everywhere else it is commented out. (V)
- Rust: `structured-world/structured-passkeys`, and new: **`feeerix/app-tap`** (Apr 2026, 0 stars, Apache-2.0, "Specific Ledger device application for Hackathon Tap", Stax/Flex/Apex P).
  - It is a Rust boilerplate with an "NFC/USB" Echo handler, a 240-byte frame limit, a JSON `sign_tx` on 44'/60', and "Place device against phone with NFC turned ON".
  - It depends on a missing `../ledger-device-sdk-patched`.
  - Likely card emulation toward a phone, with no reader mode and no payment protocol (V, NFC use I). It is the only other payment-flavoured Ledger NFC app found.
- Codeberg: nothing. GitLab: two stale 2018 mirrors.

| # | Repo | Stars | Last push | What it is | Primitives | Sim | Same / different | V/I |
|---|---|---|---|---|---|---|---|---|
| 1 | CleanSky-labs/contactless (cloned, MIT) | 0 | 2026-03-11 | Android P2P NFC crypto payments | NDEF CBOR request; merchant `msig` (spec); EIP-712 `Pay(...)` to its own escrow; Keystore/StrongBox; relayer/4337 | 4 | Same flow: payee-signed request, payer review, offline EIP-712 signature, returned by NFC, settled later. Different: phone key; custom escrow, not EIP-3009; `merchantSig` is never verified in code; no HCE | V |
| 2 | dammygreene/BumpPay (cloned, no licence) | 0 | 2026-09-14 | Solana Mobile hackathon tap-to-pay | HCE AID `F0..BUMPPAY01`; INS 10/20/30/C0; `61XX` + GET RESPONSE chunking; capped session key | 4 | Same: one tap, request in and signature out; payer offline; hostile-terminal model. Different: the payer is the card; silent signing under a cap; unsigned request; Solana | V |
| 3 | ayushsaklani-min/offline-pay "OFFPAY" (cloned, no licence) | 0 | 2026-05-21 | Offline USDC vouchers, any relay settles | HCE AID `F0011AC0DE10AC1D`; INS C1 with payee address; personal_sign voucher; OfflineVault; ESP32 + RC522; Nearby mesh | 4 | Same: offline USDC authorization binding recipient, amount, expiry and id; settle later; payee is the reader. Different: phone HCE; needs a pre-lock vault; no payee-signed request or per-tap review; `unlock()` has no delay | V |
| 4 | feeerix/app-tap | 0 | 2026-04-10 | Ledger Rust app, "Hackathon Tap" | Rust SDK 1.34 + patched SDK; Echo/sign_tx; ETH path | 3 | Same device class and a custom Ledger app. Different: card emulation toward a phone; no payment protocol | V (NFC I) |
| 5 | CalebMorse06/RipPay | 0 | 2026-08-05 | XRPL checkout | Merchant HCE sends `SESSION:<id>`; Ledger Nano X over BLE | 3 | A Ledger signs an NFC-initiated payment, but NFC carries only a session id; online | V |
| 6 | SolWear/SolWear | 3 | 2026-09-22 | ESP32-S3 watch wallet with a screen | PN532; NDEF signing; on-watch approval | 3 | A screened signer approves NFC requests. A phone mediates; online; Solana | V README |
| 7 | cryptnox/cryptnox-pos | 1 | 2026-10-07 | Standalone USDC terminal on an ESP32 display | PN532 reads a Cryptnox card that signs EIP-1559 | 3 | A screened reader and USDC, but a card signs a normal tx online | V README |
| 8 | lastmile-protocol/lastmile-app | 3 | 2026-09-17 | Offline-first "cash" wallet PWA | Ed25519 vouchers; QR; SEP-7 | 3 | Sign offline, bank later. Phone, mostly QR, Stellar | V/I |
| 9 | lnflash/cashu-javacard | 1 | 2026-10-11 | JavaCard Cashu bearer card | APDU spec (B0 20 SPEND_PROOF); BIP-340; NUT-11 P2PK | 3 | Offline NFC bearer value. Ecash card, no screen | V |
| 10 | zeugmaster/nucula | 8 | 2026-10-02 | ESP32-C3 Cashu NFC wallet | Cashu, NFC | 2-3 | Offline ecash device; not EVM | I |
| 11 | Voltic-Pay/Voltic-App | 3 | 2026-10-10 | Arbitrum Android wallet | "Hybrid offline NFC" | 2 | Phone only; plain ETH tx | I |
| 12 | VelaPayments/vela-payments | 131 | 2026-10-06 | Stellar NFC payment requests | react-native-nfc-manager; expiring request | 2 | Unsigned, online, phone | V README |
| 13–16 | anuraggdubey/Tap-Pay, pcdkd/fastpay, nodeXbit/ethonline-2026, RonaldGaymer2002/RoutePay | 0-2 | 2026 | Address exchange / pull payments / access passes / Tangem-released escrow | — | 2 | Not the same data path | V |
| 17–18 | Satodime/Satochip applets, coinkite-tap-proto, boltcard, libhalo, keycard-pal, coolwallet-sdk | — | — | Passive cards read by a phone or POS | — | 1-2 | No device-to-device transfer anywhere | I |

Worth borrowing:
- **From BumpPay:** `61 XX` + GET RESPONSE chunking with a 255-byte cap and a maximum chunk count; wipe the buffer on SELECT and when the field drops; one status word per refusal reason.
- **From CleanSky:** request fields (invoice id, random bytes32 nonce, 5-minute expiry, payee display name plus domain/ENS) and its table of what works offline. Its merchant-signature check is unimplemented; ledger-cash actually verifies on-device, a contrast worth drawing.
- **From OFFPAY:** "the relay can't redirect funds because the recipient is signed", which EIP-3009 gives for free. Its no-delay `unlock()` is the same double-spend limitation we have; put it on the limitations slide.

Caveat: GitHub code search covers default branches only and skips most forks. Zero hits for `TransferWithAuthorization` combined with IsoDep / HostApduService / NfcAdapter / NDEFReader / PN532 means none found, not none exist.

Clones (read-only, gitignored, with NOTES.md): `prior-art/CleanSky-labs__contactless/`, `prior-art/dammygreene__BumpPay/`, `prior-art/ayushsaklani-min__offline-pay/`. The `CLAUDE.md`/`AGENTS.md` files inside clones were renamed to `*.untrusted` so no agent session auto-loads them.

## 4. Combined verdict

**Precise originality claim** (supported by all three searches): *the first payer-side hardware wallet in NFC reader mode. It reads a payee-signed request, reviews it on the secure screen, debits a device-enforced cap and returns an EIP-3009 USDC authorization on the same tap, Ledger to Ledger.*

**Do not claim:**
- "offline tap payments" (CleanSky, OFFPAY, BumpPay, pnm, Visa OPS, Crunchfish, digital euro);
- "first device-enforced offline cap" (pnm, OffWallet, Crunchfish);
- "first screened wallet over NFC" (Better Wallet).

**Cite on the prior-art slide:** Polaris ("staged offline"), Visa OPS, Keycard Payment Network, Cashu Numo, Better Wallet, pnm, CleanSky.

**Changes worth making before submission**, cheapest first:
1. "Staged offline" wording in the README and pitch.
2. Offline limits per load (count, total, per-payment cap).
3. A monotonic counter folded into the EIP-3009 nonce.
4. A request expiry and invoice id.
5. `61XX` chunking hardening.

v2 escrow design: register the key once (Keycard KeycardWallet template), expiry epochs, and a bond with slashing.
