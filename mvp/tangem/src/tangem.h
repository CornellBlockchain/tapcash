/* tangem.h - talk to a Tangem card from a Ledger app in NFC reader mode.
 *
 * Pure C, no SDK dependency: builds the command APDUs, classifies status words,
 * walks the card's TLV replies, and runs the read/sign/attest sequence as a
 * step function the reader callback can drive. Crypto the app already has
 * (keccak, point decompression, ecrecover) comes in as function pointers.
 *
 * Every protocol constant lives in this file. Facts and sources:
 * research/tangem-protocol.md (MIT-era tangem-sdk-android @ cdf62aacbe).
 */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* ---- wire constants ---------------------------------------------------- */
#define TG_CLA 0x00 /* Tangem uses ISO CLA, not the ledger-cash 0xE0 */
#define TG_INS_READ 0xF2
#define TG_INS_ATTEST_CARD_KEY 0xF3
#define TG_INS_SIGN 0xFB
#define TG_INS_OPEN_SESSION 0xFF /* encryption handshake; not implemented */

/* SELECT 00 A4 04 00 08 <AID>, no Le (SDK Apdu.kt) */
#define TG_AID_LEN 8
extern const uint8_t TG_AID[TG_AID_LEN]; /* A0 00 00 08 12 01 02 08 */

/* sha256("000000") and sha256("000"): factory access code / passcode */
extern const uint8_t TG_DEFAULT_ACCESS_CODE_HASH[32];
extern const uint8_t TG_DEFAULT_PASSCODE_HASH[32];

/* TLV tags (1 byte). Length: 1 byte, or FF hi lo for >= 0xFF. */
#define TG_TAG_CARD_ID 0x01           /* 8 bytes */
#define TG_TAG_STATUS 0x02            /* card: 0 not personalized,1 empty,2 loaded,3 purged */
#define TG_TAG_CARD_PUBKEY 0x03       /* card attestation key, secp256k1 */
#define TG_TAG_CARD_SIGNATURE 0x04    /* AttestCardKey reply: r||s */
#define TG_TAG_CURVE_ID 0x05          /* ASCII, e.g. "secp256k1" (may be NUL-terminated) */
#define TG_TAG_SETTINGS_MASK 0x0A     /* big-endian, 2 or 4 bytes */
#define TG_TAG_CARD_DATA 0x0C         /* nested TLVs */
#define TG_TAG_PIN 0x10               /* sha256(access code) */
#define TG_TAG_PIN2 0x11              /* sha256(passcode) */
#define TG_TAG_CHALLENGE 0x16
#define TG_TAG_SALT 0x17
#define TG_TAG_PAUSE 0x1C             /* security delay remaining, centiseconds */
#define TG_TAG_MANUFACTURER_NAME 0x20
#define TG_TAG_INTERACTION_MODE 0x23  /* Read: 1 card, 2 wallet, 3 wallets list */
#define TG_TAG_TX_HASH 0x50
#define TG_TAG_TX_HASH_SIZE 0x51
#define TG_TAG_PIN_IS_DEFAULT 0x5A    /* bool = tag present (fw >= 4.33) */
#define TG_TAG_WALLET_PUBKEY 0x60
#define TG_TAG_WALLET_SIGNATURE 0x61  /* r||s per hash, no recovery id */
#define TG_TAG_WALLET_INDEX 0x65      /* uint8 */
#define TG_TAG_WALLETS_COUNT 0x66
#define TG_TAG_CARD_WALLET 0x68       /* nested TLVs, one per wallet (WalletsList) */
#define TG_TAG_WALLET_HD_PATH 0x6A    /* 4-byte big-endian nodes, hardened = +0x80000000 */
#define TG_TAG_WALLET_HD_CHAIN 0x6B
#define TG_TAG_FIRMWARE 0x80          /* ASCII, e.g. "6.33r" */
#define TG_TAG_MFR_CARD_ID_SIG 0x86   /* inside CARD_DATA */

#define TG_READ_MODE_CARD 0x01
#define TG_READ_MODE_WALLET 0x02

/* settings mask bits (Card.kt) */
#define TG_SET_ALLOW_UNENCRYPTED 0x00001000u
#define TG_SET_ALLOW_FAST_ENCRYPTION 0x00002000u
#define TG_SET_ALLOW_HD_WALLETS 0x00200000u

/* status words */
#define TG_SW_OK 0x9000           /* 0x9001-0x9007 are also success (PIN change variants) */
#define TG_SW_NEED_PAUSE 0x9789   /* security delay: resend the same APDU */
#define TG_SW_NEED_ENCRYPTION 0x6982
#define TG_SW_INVALID_PARAMS 0x6A86 /* on card-mode Read: wrong access code; TG_ERR elsewhere */
#define TG_SW_INVALID_ACCESS_CODE 0x6AF1
#define TG_SW_INVALID_PASSCODE 0x6AF2
#define TG_SW_WALLET_NOT_FOUND 0x6A88
#define TG_SW_INVALID_STATE 0x6985
#define TG_SW_INS_NOT_SUPPORTED 0x6D00

/* ---- building blocks --------------------------------------------------- */
typedef enum {
    TG_OK,
    TG_RESEND,           /* security delay tick: send the same APDU again */
    TG_NEED_ACCESS_CODE, /* ask the user, hash it with sha256, start over */
    TG_NEED_PASSCODE,
    TG_NEED_ENCRYPTION,  /* card refuses plaintext; see ponytail note in tangem.c */
    TG_WALLET_NOT_FOUND,
    TG_ERR,
} tg_status_t;

/* rsp = data || SW1 SW2. *pause_cs gets the remaining delay on TG_RESEND (may be NULL). */
tg_status_t tg_status(const uint8_t *rsp, size_t len, uint16_t *pause_cs);

/* Find the first TLV `tag` at the top level of buf. False if absent or malformed. */
bool tg_find(const uint8_t *buf, size_t len, uint8_t tag, const uint8_t **val, size_t *vlen);

/* Each returns the APDU length written to out, 0 if it does not fit. */
size_t tg_apdu_select(uint8_t *out, size_t cap);
size_t tg_apdu_read_card(uint8_t *out, size_t cap, const uint8_t pin[32]);
size_t tg_apdu_read_wallet(uint8_t *out, size_t cap, const uint8_t pin[32], const uint8_t *card_id,
                           uint8_t index, const uint32_t *path, size_t path_len);
size_t tg_apdu_sign(uint8_t *out, size_t cap, const uint8_t pin[32], const uint8_t pin2[32],
                    const uint8_t card_id[8], uint8_t index, const uint32_t *path, size_t path_len,
                    const uint8_t hash[32]);
size_t tg_apdu_attest(uint8_t *out, size_t cap, const uint8_t pin[32], const uint8_t card_id[8],
                      const uint8_t challenge[16]);

typedef struct {
    uint8_t card_id[8];
    bool has_card_id;
    uint8_t status;
    uint8_t fw_major, fw_minor;
    uint32_t settings;
    uint8_t card_pubkey[65];
    size_t card_pubkey_len;
    bool pin_is_default;
    uint8_t wallets_count;
    char manufacturer[24];
    uint8_t mfr_sig[64]; /* CardIdManufacturerSignature, from CARD_DATA */
    bool has_mfr_sig;
    /* wallet: top-level (fw < 4 Read, or Read Wallet reply) */
    uint8_t wallet_pubkey[65];
    size_t wallet_pubkey_len;
    uint8_t wallet_index;
    bool secp256k1;
} tg_card_t;

/* Parse a Read reply body (no SW). Merges into *c, so call it for Read Card then Read Wallet. */
bool tg_parse_read(const uint8_t *buf, size_t len, tg_card_t *c);

/* ---- crypto hooks ------------------------------------------------------ */
typedef void (*tg_keccak_fn)(const uint8_t *in, size_t len, uint8_t out[32]);
typedef bool (*tg_decompress_fn)(const uint8_t in[33], uint8_t out[65]);
typedef bool (*tg_recover_fn)(const uint8_t z[32], uint8_t v, const uint8_t r[32],
                              const uint8_t s[32], uint8_t addr[20]);

/* Ethereum address of a 65-byte (04..) or 33-byte (02/03..) secp256k1 key.
 * decompress may be NULL if the card returns uncompressed keys. */
bool tg_eth_address(const uint8_t *pub, size_t len, tg_keccak_fn keccak, tg_decompress_fn decompress,
                    uint8_t addr[20]);

/* s := n - s if s > n/2 (USDC's ECRecover rejects high-s). */
void tg_sig_low_s(uint8_t sig[64]);

/* Recovery id for a low-s r||s over z that must come from addr: 27, 28, or 0 if neither. */
uint8_t tg_sig_v(const uint8_t z[32], const uint8_t sig[64], const uint8_t addr[20], tg_recover_fn recover);

/* ---- the sequence ------------------------------------------------------ */
typedef enum {
    TG_ST_SELECT,
    TG_ST_READ_CARD,
    TG_ST_READ_WALLET,
    TG_ST_SIGN,
    TG_ST_ATTEST,
    TG_ST_DONE,
    TG_ST_FAILED,
} tg_state_t;

typedef struct {
    /* inputs, set before the first tg_next */
    uint8_t pin[32];          /* sha256(access code); TG_DEFAULT_ACCESS_CODE_HASH if unset */
    uint8_t pin2[32];         /* sha256(passcode); default "000" */
    const uint32_t *path;     /* HD path for HD cards, e.g. 44'/60'/0'/0/0 */
    size_t path_len;
    bool want_sign;
    uint8_t digest[32];       /* signed as-is (card SignHash) */
    bool want_attest;
    uint8_t challenge[16];
    /* outputs */
    tg_state_t state;
    tg_status_t why;          /* reason when state == TG_ST_FAILED */
    uint16_t pause_cs;        /* last security-delay tick, for the UI */
    tg_card_t card;
    uint8_t sig[64];          /* low-s r||s */
    uint8_t salt[32];
    size_t salt_len;
    uint8_t card_sig[64];     /* AttestCardKey: ECDSA(card key, sha256(challenge||salt)) */
    /* internal */
    uint8_t last[160];
    size_t last_len;
} tg_session_t;

/* Init with defaults (default codes, ETH path). */
void tg_session_init(tg_session_t *s);

/* Feed the previous reply (NULL/0 on the first call). Returns the next APDU length in out
 * (send it with io_nfc_reader_send), or 0 when state is TG_ST_DONE or TG_ST_FAILED. */
size_t tg_next(tg_session_t *s, const uint8_t *rsp, size_t len, uint8_t *out, size_t cap);
