/* tangem.c - see tangem.h. No dynamic memory, no SDK calls; the card is untrusted input. */
#include "tangem.h"

#include <string.h>

const uint8_t TG_AID[TG_AID_LEN] = {0xA0, 0x00, 0x00, 0x08, 0x12, 0x01, 0x02, 0x08};
const uint8_t TG_DEFAULT_ACCESS_CODE_HASH[32] = {
    0x91, 0xb4, 0xd1, 0x42, 0x82, 0x3f, 0x7d, 0x20, 0xc5, 0xf0, 0x8d, 0xf6, 0x91, 0x22, 0xde, 0x43,
    0xf3, 0x5f, 0x05, 0x7a, 0x98, 0x8d, 0x96, 0x19, 0xf6, 0xd3, 0x13, 0x84, 0x85, 0xc9, 0xa2, 0x03};
const uint8_t TG_DEFAULT_PASSCODE_HASH[32] = {
    0x2a, 0xc9, 0xa6, 0x74, 0x6a, 0xca, 0x54, 0x3a, 0xf8, 0xdf, 0xf3, 0x98, 0x94, 0xcf, 0xe8, 0x17,
    0x3a, 0xfb, 0xa2, 0x1e, 0xb0, 0x1c, 0x6f, 0xae, 0x33, 0xd5, 0x29, 0x47, 0x22, 0x28, 0x55, 0xef};

static const uint32_t ETH_PATH[5] = {0x8000002C, 0x8000003C, 0x80000000, 0, 0}; /* 44'/60'/0'/0/0 */

/* ---- status ------------------------------------------------------------ */
tg_status_t tg_status(const uint8_t *rsp, size_t len, uint16_t *pause_cs) {
    if (rsp == NULL || len < 2) return TG_ERR;
    uint16_t sw = (uint16_t) (rsp[len - 2] << 8 | rsp[len - 1]);
    if (sw >= 0x9000 && sw <= 0x9007) return TG_OK;
    switch (sw) {
        case TG_SW_NEED_PAUSE: {
            const uint8_t *v;
            size_t n;
            if (pause_cs) *pause_cs = 0;
            if (pause_cs && tg_find(rsp, len - 2, TG_TAG_PAUSE, &v, &n) && n >= 1 && n <= 2) {
                *pause_cs = n == 2 ? (uint16_t) (v[0] << 8 | v[1]) : v[0];
            }
            return TG_RESEND;
        }
        case TG_SW_NEED_ENCRYPTION: return TG_NEED_ENCRYPTION;
        case TG_SW_INVALID_ACCESS_CODE:
        case TG_SW_INVALID_PARAMS: return TG_NEED_ACCESS_CODE;
        case TG_SW_INVALID_PASSCODE: return TG_NEED_PASSCODE;
        case TG_SW_WALLET_NOT_FOUND: return TG_WALLET_NOT_FOUND;
        default: return TG_ERR;
    }
}

/* ---- TLV --------------------------------------------------------------- */
/* Read one TLV at *pos. False when the header or value would run past len. */
static bool tlv_next(const uint8_t *buf, size_t len, size_t *pos, uint8_t *tag, const uint8_t **val,
                     size_t *vlen) {
    size_t p = *pos;
    if (p + 2 > len) return false;
    *tag = buf[p];
    size_t n = buf[p + 1];
    p += 2;
    if (n == 0xFF) {
        if (p + 2 > len) return false;
        n = (size_t) buf[p] << 8 | buf[p + 1];
        p += 2;
    }
    if (n > len - p) return false;
    *val = buf + p;
    *vlen = n;
    *pos = p + n;
    return true;
}

bool tg_find(const uint8_t *buf, size_t len, uint8_t tag, const uint8_t **val, size_t *vlen) {
    size_t pos = 0;
    uint8_t t;
    while (pos < len) {
        if (!tlv_next(buf, len, &pos, &t, val, vlen)) return false;
        if (t == tag) return true;
    }
    return false;
}

static size_t tlv_put(uint8_t *out, size_t cap, size_t pos, uint8_t tag, const uint8_t *v, size_t n) {
    /* ponytail: values here are <= 32 bytes, so 1-byte lengths only */
    if (pos == 0 || n > 0xFE || pos + 2 + n > cap) return 0;
    out[pos] = tag;
    out[pos + 1] = (uint8_t) n;
    memcpy(out + pos + 2, v, n);
    return pos + 2 + n;
}

/* ---- APDUs ------------------------------------------------------------- */
/* Header + extended Lc (00 hi lo), as the SDK always sends. Lc patched by apdu_end. */
static size_t apdu_begin(uint8_t *out, size_t cap, uint8_t ins) {
    if (cap < 7) return 0;
    const uint8_t h[7] = {TG_CLA, ins, 0x00, 0x00, 0x00, 0x00, 0x00};
    memcpy(out, h, 7);
    return 7;
}

static size_t apdu_end(uint8_t *out, size_t pos) {
    if (pos < 7) return 0;
    out[5] = (uint8_t) ((pos - 7) >> 8);
    out[6] = (uint8_t) (pos - 7);
    return pos;
}

static size_t put_path(uint8_t *out, size_t cap, size_t pos, const uint32_t *path, size_t n) {
    uint8_t buf[4 * 8];
    if (path == NULL || n == 0) return pos;
    if (n > 8) return 0;
    for (size_t i = 0; i < n; i++) {
        buf[4 * i] = (uint8_t) (path[i] >> 24);
        buf[4 * i + 1] = (uint8_t) (path[i] >> 16);
        buf[4 * i + 2] = (uint8_t) (path[i] >> 8);
        buf[4 * i + 3] = (uint8_t) path[i];
    }
    return tlv_put(out, cap, pos, TG_TAG_WALLET_HD_PATH, buf, 4 * n);
}

size_t tg_apdu_select(uint8_t *out, size_t cap) {
    if (cap < 5 + TG_AID_LEN) return 0;
    const uint8_t h[5] = {0x00, 0xA4, 0x04, 0x00, TG_AID_LEN};
    memcpy(out, h, 5);
    memcpy(out + 5, TG_AID, TG_AID_LEN);
    return 5 + TG_AID_LEN;
}

size_t tg_apdu_read_card(uint8_t *out, size_t cap, const uint8_t pin[32]) {
    const uint8_t mode = TG_READ_MODE_CARD;
    size_t p = apdu_begin(out, cap, TG_INS_READ);
    p = tlv_put(out, cap, p, TG_TAG_PIN, pin, 32);
    p = tlv_put(out, cap, p, TG_TAG_INTERACTION_MODE, &mode, 1);
    return apdu_end(out, p);
}

size_t tg_apdu_read_wallet(uint8_t *out, size_t cap, const uint8_t pin[32], const uint8_t *card_id,
                           uint8_t index, const uint32_t *path, size_t path_len) {
    const uint8_t mode = TG_READ_MODE_WALLET;
    size_t p = apdu_begin(out, cap, TG_INS_READ);
    p = tlv_put(out, cap, p, TG_TAG_PIN, pin, 32);
    if (card_id) p = tlv_put(out, cap, p, TG_TAG_CARD_ID, card_id, 8);
    p = tlv_put(out, cap, p, TG_TAG_INTERACTION_MODE, &mode, 1);
    p = tlv_put(out, cap, p, TG_TAG_WALLET_INDEX, &index, 1);
    p = put_path(out, cap, p, path, path_len);
    return apdu_end(out, p);
}

size_t tg_apdu_sign(uint8_t *out, size_t cap, const uint8_t pin[32], const uint8_t pin2[32],
                    const uint8_t card_id[8], uint8_t index, const uint32_t *path, size_t path_len,
                    const uint8_t hash[32]) {
    const uint8_t hsize = 32;
    size_t p = apdu_begin(out, cap, TG_INS_SIGN);
    p = tlv_put(out, cap, p, TG_TAG_PIN, pin, 32);
    p = tlv_put(out, cap, p, TG_TAG_PIN2, pin2, 32);
    p = tlv_put(out, cap, p, TG_TAG_CARD_ID, card_id, 8);
    p = tlv_put(out, cap, p, TG_TAG_TX_HASH_SIZE, &hsize, 1);
    p = tlv_put(out, cap, p, TG_TAG_TX_HASH, hash, 32);
    p = tlv_put(out, cap, p, TG_TAG_WALLET_INDEX, &index, 1);
    p = put_path(out, cap, p, path, path_len);
    return apdu_end(out, p);
}

size_t tg_apdu_attest(uint8_t *out, size_t cap, const uint8_t pin[32], const uint8_t card_id[8],
                      const uint8_t challenge[16]) {
    size_t p = apdu_begin(out, cap, TG_INS_ATTEST_CARD_KEY);
    p = tlv_put(out, cap, p, TG_TAG_PIN, pin, 32);
    p = tlv_put(out, cap, p, TG_TAG_CARD_ID, card_id, 8);
    p = tlv_put(out, cap, p, TG_TAG_CHALLENGE, challenge, 16);
    return apdu_end(out, p);
}

/* ---- Read reply -------------------------------------------------------- */
static bool is_secp256k1(const uint8_t *v, size_t n) {
    while (n > 0 && v[n - 1] == 0) n--; /* strings may carry a trailing NUL */
    return n == 9 && memcmp(v, "secp256k1", 9) == 0;
}

static bool copy_key(uint8_t dst[65], size_t *dlen, const uint8_t *v, size_t n) {
    if (!((n == 65 && v[0] == 0x04) || (n == 33 && (v[0] == 0x02 || v[0] == 0x03)))) return false;
    memcpy(dst, v, n);
    *dlen = n;
    return true;
}

bool tg_parse_read(const uint8_t *buf, size_t len, tg_card_t *c) {
    size_t pos = 0, n, n2;
    uint8_t tag, t2;
    const uint8_t *v, *v2;
    while (pos < len) {
        if (!tlv_next(buf, len, &pos, &tag, &v, &n)) return false;
        switch (tag) {
            case TG_TAG_CARD_ID:
                if (n != 8) return false;
                memcpy(c->card_id, v, 8);
                c->has_card_id = true;
                break;
            case TG_TAG_STATUS:
                if (n != 1) return false;
                c->status = v[0];
                break;
            case TG_TAG_FIRMWARE: { /* "major.minor[r|d|s]" */
                size_t i = 0;
                unsigned maj = 0, min = 0;
                while (i < n && v[i] >= '0' && v[i] <= '9' && maj < 100) maj = maj * 10 + (v[i++] - '0');
                if (i < n && v[i] == '.') i++;
                while (i < n && v[i] >= '0' && v[i] <= '9' && min < 100) min = min * 10 + (v[i++] - '0');
                c->fw_major = (uint8_t) maj;
                c->fw_minor = (uint8_t) min;
                break;
            }
            case TG_TAG_SETTINGS_MASK:
                if (n == 0 || n > 4) return false;
                c->settings = 0;
                for (size_t i = 0; i < n; i++) c->settings = c->settings << 8 | v[i];
                break;
            case TG_TAG_CARD_PUBKEY:
                if (!copy_key(c->card_pubkey, &c->card_pubkey_len, v, n)) return false;
                break;
            case TG_TAG_PIN_IS_DEFAULT: c->pin_is_default = true; break;
            case TG_TAG_WALLETS_COUNT:
                if (n != 1) return false;
                c->wallets_count = v[0];
                break;
            case TG_TAG_MANUFACTURER_NAME: {
                size_t m = n < sizeof(c->manufacturer) - 1 ? n : sizeof(c->manufacturer) - 1;
                for (size_t i = 0; i < m; i++) c->manufacturer[i] = (v[i] >= 0x20 && v[i] < 0x7F) ? (char) v[i] : 0;
                c->manufacturer[m] = 0;
                break;
            }
            case TG_TAG_CARD_DATA:
                if (tg_find(v, n, TG_TAG_MFR_CARD_ID_SIG, &v2, &n2) && n2 == 64) {
                    memcpy(c->mfr_sig, v2, 64);
                    c->has_mfr_sig = true;
                }
                break;
            case TG_TAG_CURVE_ID: c->secp256k1 = is_secp256k1(v, n); break;
            case TG_TAG_WALLET_PUBKEY: /* other curves (ed25519, bls) have other sizes: keep 0 */
                if (!copy_key(c->wallet_pubkey, &c->wallet_pubkey_len, v, n)) c->wallet_pubkey_len = 0;
                break;
            case TG_TAG_WALLET_INDEX:
                if (n != 1) return false;
                c->wallet_index = v[0];
                break;
            case TG_TAG_CARD_WALLET: { /* WalletsList entry: take the first secp256k1 one */
                size_t p2 = 0;
                bool k1 = false;
                const uint8_t *pk = NULL, *idx = NULL;
                size_t pkn = 0;
                while (p2 < n) {
                    if (!tlv_next(v, n, &p2, &t2, &v2, &n2)) return false;
                    if (t2 == TG_TAG_CURVE_ID) k1 = is_secp256k1(v2, n2);
                    if (t2 == TG_TAG_WALLET_PUBKEY) pk = v2, pkn = n2;
                    if (t2 == TG_TAG_WALLET_INDEX && n2 == 1) idx = v2;
                }
                if (k1 && pk && !c->secp256k1) {
                    if (!copy_key(c->wallet_pubkey, &c->wallet_pubkey_len, pk, pkn)) return false;
                    c->wallet_index = idx ? idx[0] : 0;
                    c->secp256k1 = true;
                }
                break;
            }
            default: break;
        }
    }
    return true;
}

/* ---- crypto helpers ---------------------------------------------------- */
bool tg_eth_address(const uint8_t *pub, size_t len, tg_keccak_fn keccak, tg_decompress_fn decompress,
                    uint8_t addr[20]) {
    uint8_t full[65], h[32];
    if (len == 33) {
        if (decompress == NULL || !decompress(pub, full)) return false;
        pub = full;
    } else if (len != 65) {
        return false;
    }
    if (pub[0] != 0x04) return false;
    keccak(pub + 1, 64, h);
    memcpy(addr, h + 12, 20);
    return true;
}

static const uint8_t SECP_N[32] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                                   0xFF, 0xFF, 0xFF, 0xFF, 0xFE, 0xBA, 0xAE, 0xDC, 0xE6, 0xAF, 0x48,
                                   0xA0, 0x3B, 0xBF, 0xD2, 0x5E, 0x8C, 0xD0, 0x36, 0x41, 0x41};
static const uint8_t SECP_HALF_N[32] = {0x7F, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                                        0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x5D, 0x57, 0x6E, 0x73, 0x57, 0xA4,
                                        0x50, 0x1D, 0xDF, 0xE9, 0x2F, 0x46, 0x68, 0x1B, 0x20, 0xA0};

void tg_sig_low_s(uint8_t sig[64]) {
    uint8_t *s = sig + 32;
    if (memcmp(s, SECP_HALF_N, 32) <= 0) return;
    int borrow = 0;
    for (int i = 31; i >= 0; i--) {
        int d = SECP_N[i] - s[i] - borrow;
        borrow = d < 0;
        s[i] = (uint8_t) (d + (borrow ? 256 : 0));
    }
}

uint8_t tg_sig_v(const uint8_t z[32], const uint8_t sig[64], const uint8_t addr[20], tg_recover_fn recover) {
    uint8_t a[20];
    for (uint8_t v = 27; v <= 28; v++) {
        if (recover(z, v, sig, sig + 32, a) && memcmp(a, addr, 20) == 0) return v;
    }
    return 0;
}

/* ---- sequence ---------------------------------------------------------- */
void tg_session_init(tg_session_t *s) {
    memset(s, 0, sizeof(*s));
    memcpy(s->pin, TG_DEFAULT_ACCESS_CODE_HASH, 32);
    memcpy(s->pin2, TG_DEFAULT_PASSCODE_HASH, 32);
    s->path = ETH_PATH;
    s->path_len = 5;
}

static size_t fail(tg_session_t *s, tg_status_t why) {
    s->state = TG_ST_FAILED;
    s->why = why;
    return 0;
}

static size_t emit(tg_session_t *s, tg_state_t st, size_t n, uint8_t *out, size_t cap) {
    if (n == 0 || n > sizeof(s->last) || n > cap) return fail(s, TG_ERR);
    memcpy(s->last, out, n);
    s->last_len = n;
    s->state = st;
    return n;
}

static size_t after_wallet(tg_session_t *s, uint8_t *out, size_t cap) {
    tg_card_t *c = &s->card;
    if (s->want_sign)
        return emit(s, TG_ST_SIGN,
                    tg_apdu_sign(out, cap, s->pin, s->pin2, c->card_id, c->wallet_index,
                                 (c->settings & TG_SET_ALLOW_HD_WALLETS) ? s->path : NULL, s->path_len,
                                 s->digest),
                    out, cap);
    if (s->want_attest)
        return emit(s, TG_ST_ATTEST, tg_apdu_attest(out, cap, s->pin, c->card_id, s->challenge), out, cap);
    s->state = TG_ST_DONE;
    return 0;
}

static size_t read_wallet(tg_session_t *s, uint8_t index, uint8_t *out, size_t cap) {
    tg_card_t *c = &s->card;
    const uint32_t *path = (c->settings & TG_SET_ALLOW_HD_WALLETS) ? s->path : NULL;
    c->wallet_index = index;
    return emit(s, TG_ST_READ_WALLET,
                tg_apdu_read_wallet(out, cap, s->pin, c->card_id, index, path, s->path_len), out, cap);
}

size_t tg_next(tg_session_t *s, const uint8_t *rsp, size_t len, uint8_t *out, size_t cap) {
    tg_card_t *c = &s->card;
    if (rsp == NULL) {
        memset(&s->card, 0, sizeof s->card); /* new tap: nothing from the previous card survives */
        s->state = TG_ST_SELECT;
        return emit(s, TG_ST_SELECT, tg_apdu_select(out, cap), out, cap);
    }
    if (s->state == TG_ST_DONE || s->state == TG_ST_FAILED) return 0;

    tg_status_t st = tg_status(rsp, len, &s->pause_cs);
    if (st == TG_RESEND) { /* security delay: same APDU again, card counts down */
        if (s->last_len > cap) return fail(s, TG_ERR);
        memcpy(out, s->last, s->last_len);
        return s->last_len;
    }
    /* ponytail: plaintext only. TG_NEED_ENCRYPTION -> OpenSession 0xFF fast mode is the upgrade
     * (AES-256-CBC zero IV, key = sha256(keyA||keyB||pbkdf2_sha256(pin, uid, 50))); see research note. */
    if (s->state == TG_ST_READ_WALLET && st == TG_WALLET_NOT_FOUND) {
        if (c->wallet_index + 1u >= (c->wallets_count ? c->wallets_count : 8)) return fail(s, st);
        return read_wallet(s, (uint8_t) (c->wallet_index + 1), out, cap);
    }
    /* 6A86 means "access code" only on card-mode Read (SDK ReadCommand.mapError); elsewhere a bad parameter.
     * ponytail: on Sign, fw < 4 cards use 6A86 for a wrong PIN2 too; reported as TG_ERR, fw >= 4 answers 6AF2. */
    if (st == TG_NEED_ACCESS_CODE && len >= 2 && rsp[len - 2] == 0x6A && rsp[len - 1] == 0x86 &&
        s->state != TG_ST_READ_CARD)
        st = TG_ERR;
    if (st != TG_OK) return fail(s, st);
    const uint8_t *body = rsp, *v;
    size_t blen = len - 2, n;

    switch (s->state) {
        case TG_ST_SELECT:
            return emit(s, TG_ST_READ_CARD, tg_apdu_read_card(out, cap, s->pin), out, cap);
        case TG_ST_READ_CARD:
            if (!tg_parse_read(body, blen, c) || !c->has_card_id || c->status == 0 || c->status == 3 ||
                (c->fw_major < 4 && c->status != 2)) /* SDK assertStatus: only NotPersonalized/Purged are fatal */
                return fail(s, TG_ERR);
            if (c->fw_major < 4) { /* single-wallet card: key came with Read Card */
                if (!c->secp256k1 || !c->wallet_pubkey_len) return fail(s, TG_ERR);
                return after_wallet(s, out, cap);
            }
            c->wallet_pubkey_len = 0;
            c->secp256k1 = false;
            return read_wallet(s, 0, out, cap);
        case TG_ST_READ_WALLET: {
            uint8_t want = c->wallet_index, status = c->status, id[8];
            uint32_t settings = c->settings; /* wallet reply carries wallet-level status/mask */
            memcpy(id, c->card_id, 8);
            c->secp256k1 = false;
            c->wallet_pubkey_len = 0; /* never carry a key over from another wallet's reply */
            c->status = 0;            /* wallet Status (02) is mandatory in the reply */
            if (!tg_parse_read(body, blen, c) || c->wallet_index != want || memcmp(id, c->card_id, 8) != 0)
                return fail(s, TG_ERR); /* a different card mid-sequence is an error */
            uint8_t ws = c->status & 0x3F; /* SDK CardWallet: 2 = loaded; 0x40/0x80 are backup flags */
            c->status = status;
            c->settings = settings;
            if (c->secp256k1 && c->wallet_pubkey_len && ws == 2) return after_wallet(s, out, cap);
            if (want + 1u >= (c->wallets_count ? c->wallets_count : 8)) return fail(s, TG_WALLET_NOT_FOUND);
            return read_wallet(s, (uint8_t) (want + 1), out, cap);
        }
        case TG_ST_SIGN:
            if (!tg_find(body, blen, TG_TAG_WALLET_SIGNATURE, &v, &n) || n != 64) return fail(s, TG_ERR);
            memcpy(s->sig, v, 64);
            tg_sig_low_s(s->sig);
            s->want_sign = false;
            return after_wallet(s, out, cap);
        case TG_ST_ATTEST:
            if (!tg_find(body, blen, TG_TAG_CARD_SIGNATURE, &v, &n) || n != 64) return fail(s, TG_ERR);
            memcpy(s->card_sig, v, 64);
            if (!tg_find(body, blen, TG_TAG_SALT, &v, &n) || n == 0 || n > sizeof(s->salt)) return fail(s, TG_ERR);
            memcpy(s->salt, v, n);
            s->salt_len = n;
            s->state = TG_ST_DONE;
            return 0;
        default: return fail(s, TG_ERR);
    }
}
