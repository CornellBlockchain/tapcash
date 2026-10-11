/*
 * Ledger Cash v0: USDC as device-held cash, paid by EIP-3009 TransferWithAuthorization.
 * One file on purpose. Every handler takes raw bytes and answers with io_send_*. USB and NFC card
 * emulation share io_recv_command; over NFC only SELECT, GET_REQUEST and PUT_AUTH are accepted.
 * The reader side (TAP_TO_PAY: payer drives the payee over NFC) reuses pay_review()/pay_sign():
 *   SELECT AID -> GET_REQUEST -> review -> sign + debit -> PUT_AUTH -> verify receipt.
 *
 * Wire formats (all big-endian, fixed size):
 *   request (157) = chainId u64 | token 20 | payTo 20 | value u64 | validBefore u64 |
 *                   reqNonce u32 | label 24 (zero padded ASCII) | payeeSig r32 s32 v1
 *                   payeeSig = secp256k1 over EIP-191("\x19Ethereum Signed Message:\n32" ||
 *                   keccak256(request[0:92]))
 *   auth (161)    = from 20 | to 20 | value u64 | validAfter u64 | validBefore u64 | nonce 32 |
 *                   v1 r32 s32   (EIP-712 TransferWithAuthorization, domain USDC / "2")
 */
#include <stdint.h>
#include <string.h>

#include "os.h"
#include "cx.h"
#include "io.h"
#include "parser.h"
#include "read.h"
#include "write.h"
#include "format.h"
#include "crypto_helpers.h"
#include "nbgl_use_case.h"
#include "glyphs.h"

#if defined(TARGET_APEX_P)
#define ICON C_app_boilerplate_48px
#elif defined(TARGET_NANOS2) || defined(TARGET_NANOX)
#define ICON C_app_boilerplate_14px  // Nano: USB-only build (no HAVE_NFC), no tap
#else
#define ICON C_app_boilerplate_64px
#endif

#define CLA 0xE0
enum {
    INS_SET_REQUEST = 0x10,
    INS_GET_REQUEST = 0x11,
    INS_SET_CONFIG = 0x12,
    INS_LOAD_CASH = 0x20,
    INS_GET_BALANCE = 0x21,
    INS_PAY = 0x22,
    INS_PUT_AUTH = 0x23,
    INS_GET_AUTHS = 0x24,
    INS_TAP_TO_PAY = 0x30,
    INS_TAP_STATUS = 0x31,
};
// SELECT AID = "F0" + "LEDGERCASH" + "01" (proprietary RID range F0)
static const uint8_t AID[12] = {0xF0, 'L', 'E', 'D', 'G', 'E', 'R', 'C', 'A', 'S', 'H', 0x01};

#define SW_OK              0x9000
#define SW_REJECTED        0x6985
#define SW_WRONG_LENGTH    0x6700
#define SW_BAD_DATA        0x6A80
#define SW_NOT_FOUND       0x6A88
#define SW_BAD_P1P2        0x6A86
#define SW_BAD_INS         0x6D00
#define SW_BAD_CLA         0x6E00
#define SW_BAD_PAYEE_SIG   0xB001
#define SW_CONFIG          0xB002  // not configured, or request chain/token != config
#define SW_INSUFFICIENT    0xB003
#define SW_REPLAY          0xB004
#define SW_BAD_AUTH        0xB005
#define SW_NO_REQUEST      0xB006
#define SW_BUSY            0xB007
#define SW_CARD_GONE       0xB008  // tap: card left the field
#define SW_NO_ANSWER       0xB009  // tap: payee did not answer in time
#define SW_CRYPTO          0xB0FF

#define REQ_BODY  92
#define REQ_LEN   157
#define AUTH_BODY 96
#define AUTH_LEN  161
#define LABEL_LEN 24
#define SEEN_N    8
#define AUTHS_N   8

// request offsets
#define R_CHAIN  0
#define R_TOKEN  8
#define R_PAYTO  28
#define R_VALUE  48
#define R_VBEF   56
#define R_NONCE  64
#define R_LABEL  68
#define R_SIG    92
// auth offsets
#define A_FROM  0
#define A_TO    20
#define A_VALUE 40
#define A_VAFT  48
#define A_VBEF  56
#define A_NONCE 64
#define A_V     96
#define A_R     97
#define A_S     129

/* ---------------- NVM ---------------- */
// All-zero is the valid initial state (no balance, not configured), so no init step.
typedef struct {
    uint64_t balance;
    uint32_t pay_counter;
    uint8_t seen[SEEN_N][32];  // nonces of the last SEEN_N payments, refused on replay
} wallet_t;

typedef struct {
    uint8_t configured;
    uint64_t chain_id;
    uint8_t token[20];
    wallet_t wallet;  // always rewritten as one nvm_write
    uint32_t auth_count;
    // ponytail: ring of AUTHS_N, the 9th unsettled payment overwrites the oldest; host must
    // GET_AUTHS + settle first. Upgrade: refuse PUT_AUTH when full until a CLEAR_AUTHS.
    uint8_t auths[AUTHS_N][AUTH_LEN];
} storage_t;

const storage_t N_storage_real;
#define NV (*(volatile storage_t *) PIC(&N_storage_real))

/* ---------------- RAM state ---------------- */
static uint8_t g_req[REQ_LEN];  // payee: last approved request, served and payable only while g_req_valid
static bool g_req_valid;        // cleared by payment, by a new SET_REQUEST (even if rejected), by SET_CONFIG
static uint8_t g_pay[REQ_LEN];  // payer: request under review
static uint64_t g_value;        // value under review (LOAD_CASH / SET_REQUEST)
static uint8_t g_label[LABEL_LEN];
static uint8_t g_cfg[28];
static bool g_busy;  // a review is on screen: refuse other APDUs so the screen can't be swapped

static char s_amount[32], s_after[32], s_addr[43], s_label[LABEL_LEN + 1], s_msg[112], s_sub[96];
static char s_tagline[80];
enum { PAY_NONE, PAY_USB, PAY_TAP };  // who opened the review on screen
static uint8_t g_pay_src;

#ifdef HAVE_NFC_READER
static nbgl_homeAction_t g_home_action;
// payer tap state, reported by TAP_STATUS
enum { TAP_IDLE, TAP_WAIT, TAP_BUSY, TAP_SENT, TAP_PAID, TAP_FAILED, TAP_NO_RECEIPT };
static uint8_t g_tap;
static uint16_t g_tap_sw;
static uint8_t g_tap_auth[AUTH_LEN];     // last auth signed by a tap (kept if no receipt came back)
static uint8_t g_tap_cmd[5 + AUTH_LEN];  // PUT_AUTH command sent to the card
#endif

static const uint32_t PATH[] = {0x8000002C, 0x8000003C, 0x80000000, 0, 0};  // 44'/60'/0'/0/0

static void ui_home(void);
#ifdef HAVE_NFC_READER
static void tap_menu(void);
#endif

/* ---------------- crypto ---------------- */
static void keccak(const uint8_t *in, size_t len, uint8_t out[32]) {
    // cannot fail for a 256-bit digest with a valid buffer
    if (cx_keccak_256_hash(in, len, out) != CX_OK) memset(out, 0, 32);
}

static bool own_address(uint8_t out[20]) {
    uint8_t pk[65], h[32];
    if (bip32_derive_get_pubkey_256(CX_CURVE_256K1, PATH, 5, pk, NULL, CX_SHA512) != CX_OK) {
        return false;
    }
    keccak(pk + 1, 64, h);
    memcpy(out, h + 12, 20);
    return true;
}

// EIP-191 personal_sign digest of a 32-byte hash
static void eip191(const uint8_t h[32], uint8_t out[32]) {
    uint8_t buf[28 + 32];
    memcpy(buf, "\x19" "Ethereum Signed Message:\n32", 28);
    memcpy(buf + 28, h, 32);
    keccak(buf, sizeof(buf), out);
}

static bool sign_hash(const uint8_t h[32], uint8_t r[32], uint8_t s[32], uint8_t *v) {
    uint32_t info = 0;
    if (bip32_derive_ecdsa_sign_rs_hash_256(CX_CURVE_256K1,
                                            PATH,
                                            5,
                                            CX_RND_RFC6979 | CX_LAST,
                                            CX_SHA256,
                                            h,
                                            32,
                                            r,
                                            s,
                                            &info) != CX_OK) {
        return false;
    }
    *v = 27 + (info & CX_ECCINFO_PARITY_ODD);
    return true;
}

static const uint8_t SECP_N[32] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                                   0xFF, 0xFF, 0xFF, 0xFF, 0xFE, 0xBA, 0xAE, 0xDC, 0xE6, 0xAF, 0x48,
                                   0xA0, 0x3B, 0xBF, 0xD2, 0x5E, 0x8C, 0xD0, 0x36, 0x41, 0x41};
// n/2: USDC (Circle's ECRecover) rejects s above this, so the payee must too
static const uint8_t SECP_N_HALF[32] = {0x7F, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                                        0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x5D, 0x57, 0x6E, 0x73, 0x57, 0xA4,
                                        0x50, 0x1D, 0xDF, 0xE9, 0x2F, 0x46, 0x68, 0x1B, 0x20, 0xA0};
static const uint8_t SECP_GX[32] = {0x79, 0xBE, 0x66, 0x7E, 0xF9, 0xDC, 0xBB, 0xAC, 0x55, 0xA0, 0x62,
                                    0x95, 0xCE, 0x87, 0x0B, 0x07, 0x02, 0x9B, 0xFC, 0xDB, 0x2D, 0xCE,
                                    0x28, 0xD9, 0x59, 0xF2, 0x81, 0x5B, 0x16, 0xF8, 0x17, 0x98};
static const uint8_t SECP_GY[32] = {0x48, 0x3A, 0xDA, 0x77, 0x26, 0xA3, 0xC4, 0x65, 0x5D, 0xA4, 0xFB,
                                    0xFC, 0x0E, 0x11, 0x08, 0xA8, 0xFD, 0x17, 0xB4, 0x48, 0xA6, 0x85,
                                    0x54, 0x19, 0x9C, 0x47, 0xD0, 0x8F, 0xFB, 0x10, 0xD4, 0xB8};

// ecrecover: Q = r^-1 (s R - z G), address = keccak(Q)[12:]. Public data only, no secrets.
// ponytail: z is not reduced mod n (z >= n has probability ~2^-128).
static bool ecrecover(const uint8_t z[32], uint8_t v, const uint8_t r[32], const uint8_t s[32],
                      uint8_t addr[20]) {
    if (v != 27 && v != 28) return false;
    cx_err_t error;
    bool ok = false;
    int d;
    uint8_t u1[32], u2[32], xy[64], h[32];
    cx_bn_t n, br, bs, bz, rinv, t, zero;
    cx_ecpoint_t R, G, Q;

    if (cx_bn_lock(32, 0) != CX_OK) return false;
    CX_CHECK(cx_bn_alloc_init(&n, 32, SECP_N, 32));
    CX_CHECK(cx_bn_alloc_init(&br, 32, r, 32));
    CX_CHECK(cx_bn_alloc_init(&bs, 32, s, 32));
    CX_CHECK(cx_bn_alloc_init(&bz, 32, z, 32));
    CX_CHECK(cx_bn_alloc(&rinv, 32));
    CX_CHECK(cx_bn_alloc(&t, 32));
    CX_CHECK(cx_bn_alloc(&zero, 32));
    // 0 < r, s < n
    CX_CHECK(cx_bn_cmp(br, n, &d));
    if (d >= 0) goto end;
    CX_CHECK(cx_bn_cmp(bs, n, &d));
    if (d >= 0) goto end;
    CX_CHECK(cx_bn_cmp_u32(br, 0, &d));
    if (d == 0) goto end;
    CX_CHECK(cx_bn_cmp_u32(bs, 0, &d));
    if (d == 0) goto end;

    CX_CHECK(cx_bn_mod_invert_nprime(rinv, br, n));
    CX_CHECK(cx_bn_mod_mul(t, bs, rinv, n));
    CX_CHECK(cx_bn_export(t, u2, 32));  // u2 = s / r
    CX_CHECK(cx_bn_mod_mul(t, bz, rinv, n));
    CX_CHECK(cx_bn_mod_sub(t, zero, t, n));
    CX_CHECK(cx_bn_export(t, u1, 32));  // u1 = -z / r

    CX_CHECK(cx_ecpoint_alloc(&R, CX_CURVE_SECP256K1));
    CX_CHECK(cx_ecpoint_alloc(&G, CX_CURVE_SECP256K1));
    CX_CHECK(cx_ecpoint_alloc(&Q, CX_CURVE_SECP256K1));
    CX_CHECK(cx_ecpoint_decompress(&R, r, 32, v - 27));
    CX_CHECK(cx_ecpoint_init(&G, SECP_GX, 32, SECP_GY, 32));
    CX_CHECK(cx_ecpoint_double_scalarmul(&Q, &G, &R, u1, 32, u2, 32));
    CX_CHECK(cx_ecpoint_export(&Q, xy, 32, xy + 32, 32));
    keccak(xy, 64, h);
    memcpy(addr, h + 12, 20);
    ok = true;
end:
    cx_bn_unlock();
    return ok;
}

static void u256(uint8_t dst[32], const uint8_t *src, size_t len) {
    memset(dst, 0, 32);
    memcpy(dst + 32 - len, src, len);
}

// EIP-712 digest of TransferWithAuthorization(auth[0:96]) under the configured domain
static void auth_digest(const uint8_t *a, uint8_t out[32]) {
    static const char DOM_T[] =
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)";
    static const char TWA_T[] =
        "TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,"
        "uint256 validBefore,bytes32 nonce)";
    uint8_t buf[7 * 32], dom[32], st[32], cid[8];

    keccak((const uint8_t *) PIC(DOM_T), sizeof(DOM_T) - 1, buf);
    keccak((const uint8_t *) "USDC", 4, buf + 32);  // name: "USDC" on testnets/Arc, "USD Coin" on mainnets
    keccak((const uint8_t *) "2", 1, buf + 64);
    write_u64_be(cid, 0, NV.chain_id);
    u256(buf + 96, cid, 8);
    u256(buf + 128, (const uint8_t *) NV.token, 20);
    keccak(buf, 5 * 32, dom);

    keccak((const uint8_t *) PIC(TWA_T), sizeof(TWA_T) - 1, buf);
    u256(buf + 32, a + A_FROM, 20);
    u256(buf + 64, a + A_TO, 20);
    u256(buf + 96, a + A_VALUE, 8);
    u256(buf + 128, a + A_VAFT, 8);
    u256(buf + 160, a + A_VBEF, 8);
    memcpy(buf + 192, a + A_NONCE, 32);
    keccak(buf, 7 * 32, st);

    buf[0] = 0x19;
    buf[1] = 0x01;
    memcpy(buf + 2, dom, 32);
    memcpy(buf + 34, st, 32);
    keccak(buf, 66, out);
}

/* ---------------- formatting ---------------- */
static void fmt_usdc(char *dst, size_t n, uint64_t v) {
    char tmp[24] = {0};  // SDK format_fpu64 does not NUL-terminate, it relies on a zeroed dst
    if (!format_fpu64_trimmed(tmp, sizeof(tmp), v, 6)) tmp[0] = 0;
    snprintf(dst, n, "%s USDC", tmp);
}

static void fmt_addr(char *dst, const uint8_t a[20]) {
    dst[0] = '0';
    dst[1] = 'x';
    format_hex(a, 20, dst + 2, 41);
}

static bool label_ok(const uint8_t *l, size_t len) {
    bool end = false;
    for (size_t i = 0; i < len; i++) {
        if (l[i] == 0) {
            end = true;
        } else if (end || l[i] < 0x20 || l[i] > 0x7E) {
            return false;  // printable ASCII, zero padding only at the tail
        }
    }
    return true;
}

static void fmt_label(const uint8_t *l) {
    memcpy(s_label, l, LABEL_LEN);
    s_label[LABEL_LEN] = 0;
}

/* ---------------- UI helpers ---------------- */
static void choice_done(bool ok) {
    g_busy = false;
    nbgl_useCaseStatus(ok ? "Done" : "Rejected", ok, ui_home);
}

static void app_quit(void) {
    os_sched_exit(-1);
}

static void ui_home(void) {
    char amt[32], a[43];
    if (g_req_valid) {
        fmt_usdc(amt, sizeof(amt), read_u64_be(g_req, R_VALUE));
        fmt_addr(a, g_req + R_PAYTO);  // the payer matches this against the "To" on its review
        snprintf(s_tagline, sizeof(s_tagline), "Receive %s to\n%.*s...%s", amt, 6, a, a + 37);  // SDK snprintf: %.*s, not %.6s
    } else {
        fmt_usdc(amt, sizeof(amt), NV.wallet.balance);
        snprintf(s_tagline, sizeof(s_tagline), "Cash: %s", amt);
    }
#ifdef HAVE_NFC_READER
    g_home_action.text = "Pay by tap";
    g_home_action.callback = tap_menu;
    g_home_action.style = STRONG_HOME_ACTION;
    nbgl_useCaseHomeAndSettings(APPNAME, &ICON, s_tagline, INIT_HOME_PAGE, NULL, NULL, &g_home_action,
                                app_quit);
#else
    nbgl_useCaseHomeAndSettings(APPNAME, &ICON, s_tagline, INIT_HOME_PAGE, NULL, NULL, NULL, app_quit);
#endif
}

/* ---------------- SET_CONFIG ---------------- */
static void config_choice(bool ok) {
    if (ok) {
        storage_t *p = (storage_t *) &NV;
        uint8_t one = 1;
        nvm_write(&p->chain_id, (void *) &(uint64_t){read_u64_be(g_cfg, 0)}, 8);
        nvm_write(p->token, g_cfg + 8, 20);
        nvm_write(&p->configured, &one, 1);
        g_req_valid = false;  // a pending request was built (and is verified) under the old network
        io_send_sw(SW_OK);
    } else {
        io_send_sw(SW_REJECTED);
    }
    choice_done(ok);
}

static int set_config(const uint8_t *d, size_t len) {
    if (len != 28) return io_send_sw(SW_WRONG_LENGTH);
    memcpy(g_cfg, d, 28);
    char addr[43], cid[24] = {0};
    fmt_addr(addr, d + 8);
    if (!format_u64(cid, sizeof(cid), read_u64_be(d, 0))) return io_send_sw(SW_BAD_DATA);
    snprintf(s_sub, sizeof(s_sub), "Chain ID %s\nUSDC %s", cid, addr);
    g_busy = true;
    nbgl_useCaseChoice(&ICON, "Set USDC network", s_sub, "Approve", "Reject", config_choice);
    return 0;
}

/* ---------------- LOAD_CASH / GET_BALANCE ---------------- */
static void load_choice(bool ok) {
    if (ok) {
        wallet_t w;
        memcpy(&w, (const void *) &NV.wallet, sizeof(w));
        if (w.balance + g_value < w.balance) {
            io_send_sw(SW_BAD_DATA);
        } else {
            w.balance += g_value;
            nvm_write((void *) &NV.wallet, &w, sizeof(w));
            io_send_sw(SW_OK);
        }
    } else {
        io_send_sw(SW_REJECTED);
    }
    choice_done(ok);
}

static int load_cash(const uint8_t *d, size_t len) {
    if (len != 8) return io_send_sw(SW_WRONG_LENGTH);
    g_value = read_u64_be(d, 0);
    if (g_value == 0 || NV.wallet.balance + g_value < NV.wallet.balance) return io_send_sw(SW_BAD_DATA);
    fmt_usdc(s_amount, sizeof(s_amount), g_value);
    fmt_usdc(s_after, sizeof(s_after), NV.wallet.balance + g_value);
    snprintf(s_msg, sizeof(s_msg), "Load %s as cash", s_amount);
    snprintf(s_sub, sizeof(s_sub), "Cash after: %s", s_after);
    g_busy = true;
    nbgl_useCaseChoice(&ICON, s_msg, s_sub, "Approve", "Reject", load_choice);
    return 0;
}

static int get_balance(void) {
    uint8_t out[32];
    write_u64_be(out, 0, NV.wallet.balance);
    write_u32_be(out, 8, NV.wallet.pay_counter);
    if (!own_address(out + 12)) return io_send_sw(SW_CRYPTO);
    return io_send_response_pointer(out, sizeof(out), SW_OK);
}

/* ---------------- SET_REQUEST / GET_REQUEST (payee) ---------------- */
static void request_choice(bool ok) {
    if (!ok) {
        io_send_sw(SW_REJECTED);
        choice_done(false);
        return;
    }
    uint8_t *q = g_req, h[32], v;
    // ponytail: 32 random bits, so a reinstalled or second payee device does not repeat old requests
    // (a repeat would get an auth whose nonce is already used on-chain). Upgrade: widen the field.
    uint32_t nonce = cx_rng_u32();
    write_u64_be(q, R_CHAIN, NV.chain_id);
    memcpy(q + R_TOKEN, (const void *) NV.token, 20);
    write_u64_be(q, R_VALUE, g_value);
    // ponytail: the device has no trusted clock, so a request never expires (like cash).
    // Upgrade: host-supplied validBefore shown on screen.
    write_u64_be(q, R_VBEF, UINT64_MAX);
    write_u32_be(q, R_NONCE, nonce);
    memcpy(q + R_LABEL, g_label, LABEL_LEN);
    if (!own_address(q + R_PAYTO)) goto fail;
    keccak(q, REQ_BODY, h);
    eip191(h, h);
    if (!sign_hash(h, q + R_SIG, q + R_SIG + 32, &v)) goto fail;
    q[R_SIG + 64] = v;
    g_req_valid = true;
    io_send_sw(SW_OK);
    g_busy = false;
    ui_home();  // home tagline: "Ready to receive <amount>"
    return;
fail:
    io_send_sw(SW_CRYPTO);
    choice_done(false);
}

static int set_request(const uint8_t *d, size_t len) {
    if (len < 8 || len > 8 + LABEL_LEN) return io_send_sw(SW_WRONG_LENGTH);
    if (!NV.configured) return io_send_sw(SW_CONFIG);
    memset(g_label, 0, LABEL_LEN);
    memcpy(g_label, d + 8, len - 8);
    g_value = read_u64_be(d, 0);
    if (g_value == 0 || !label_ok(g_label, LABEL_LEN)) return io_send_sw(SW_BAD_DATA);
    g_req_valid = false;
    fmt_usdc(s_amount, sizeof(s_amount), g_value);
    fmt_label(g_label);
    snprintf(s_msg, sizeof(s_msg), "Request %s", s_amount);
    snprintf(s_sub, sizeof(s_sub), "For: %s", s_label);
    g_busy = true;
    nbgl_useCaseChoice(&ICON, s_msg, s_sub, "Approve", "Reject", request_choice);
    return 0;
}

/* ---------------- PAY (payer) ---------------- */
static nbgl_contentTagValue_t pairs[4];
static nbgl_contentTagValueList_t pair_list;

// Everything the payer checks before showing the review. Returns SW_OK or the refusal SW.
static uint16_t pay_check(const uint8_t *q) {
    uint8_t h[32], who[20];
    if (!NV.configured || read_u64_be(q, R_CHAIN) != NV.chain_id ||
        memcmp(q + R_TOKEN, (const void *) NV.token, 20) != 0) {
        return SW_CONFIG;
    }
    if (read_u64_be(q, R_VALUE) == 0 || !label_ok(q + R_LABEL, LABEL_LEN)) return SW_BAD_DATA;
    keccak(q, REQ_BODY, h);
    eip191(h, h);
    if (!ecrecover(h, q[R_SIG + 64], q + R_SIG, q + R_SIG + 32, who) ||
        memcmp(who, q + R_PAYTO, 20) != 0) {
        return SW_BAD_PAYEE_SIG;
    }
    if (read_u64_be(q, R_VALUE) > NV.wallet.balance) return SW_INSUFFICIENT;
    keccak(q, REQ_BODY, h);
    for (int i = 0; i < SEEN_N; i++) {
        if (memcmp((const void *) NV.wallet.seen[i], h, 32) == 0) return SW_REPLAY;
    }
    return SW_OK;
}

// Builds and signs the authorization for g_pay, then debits the cash in one NVM write.
// The signature exists only in RAM until the debit is persisted.
static uint16_t pay_sign(uint8_t a[AUTH_LEN]) {
    uint16_t sw = pay_check(g_pay);  // re-check: state may not change between review and sign
    if (sw != SW_OK) return sw;
    const uint8_t *q = g_pay;
    uint8_t h[32];
    wallet_t w;
    if (!own_address(a + A_FROM)) return SW_CRYPTO;
    memcpy(a + A_TO, q + R_PAYTO, 20);
    memcpy(a + A_VALUE, q + R_VALUE, 8);
    memset(a + A_VAFT, 0, 8);
    memcpy(a + A_VBEF, q + R_VBEF, 8);
    keccak(q, REQ_BODY, a + A_NONCE);
    auth_digest(a, h);
    if (!sign_hash(h, a + A_R, a + A_S, a + A_V)) return SW_CRYPTO;

    memcpy(&w, (const void *) &NV.wallet, sizeof(w));
    w.balance -= read_u64_be(q, R_VALUE);
    memcpy(w.seen[w.pay_counter % SEEN_N], a + A_NONCE, 32);
    w.pay_counter++;
    nvm_write((void *) &NV.wallet, &w, sizeof(w));
    return SW_OK;
}

#ifdef HAVE_NFC_READER
static void tap_choice(bool ok);
#endif

static void pay_choice(bool ok) {
    uint8_t src = g_pay_src;
    g_pay_src = PAY_NONE;
#ifdef HAVE_NFC_READER
    if (src == PAY_TAP) {
        tap_choice(ok);
        return;
    }
#endif
    if (src != PAY_USB) return;  // stale review (its tap already ended): nothing to answer
    g_busy = false;
    if (!ok) {
        io_send_sw(SW_REJECTED);
        nbgl_useCaseReviewStatus(STATUS_TYPE_TRANSACTION_REJECTED, ui_home);
        return;
    }
    uint8_t a[AUTH_LEN];
    uint16_t sw = pay_sign(a);
    if (sw != SW_OK) {
        io_send_sw(sw);
        nbgl_useCaseStatus("Payment failed", false, ui_home);
        return;
    }
    io_send_response_pointer(a, AUTH_LEN, SW_OK);
    nbgl_useCaseReviewStatus(STATUS_TYPE_TRANSACTION_SIGNED, ui_home);
}

// Checks request d and puts the payment review on screen. Sends nothing: the caller owns the channel.
static uint16_t pay_review(const uint8_t *d, uint8_t src) {
    uint16_t sw = pay_check(d);
    if (sw != SW_OK) return sw;
    memcpy(g_pay, d, REQ_LEN);
    g_pay_src = src;
    uint64_t v = read_u64_be(d, R_VALUE);
    fmt_usdc(s_amount, sizeof(s_amount), v);
    fmt_usdc(s_after, sizeof(s_after), NV.wallet.balance - v);
    fmt_addr(s_addr, d + R_PAYTO);
    fmt_label(d + R_LABEL);
    snprintf(s_msg, sizeof(s_msg), "Pay %s?", s_amount);
    pairs[0] = (nbgl_contentTagValue_t){.item = "Pay", .value = s_amount};
    pairs[1] = (nbgl_contentTagValue_t){.item = "To", .value = s_addr};
    pairs[2] = (nbgl_contentTagValue_t){.item = "For", .value = s_label};
    pairs[3] = (nbgl_contentTagValue_t){.item = "Cash left after", .value = s_after};
    pair_list = (nbgl_contentTagValueList_t){.pairs = pairs, .nbPairs = 4, .wrapping = true};
    g_busy = true;
    nbgl_useCaseReview(TYPE_TRANSACTION, &pair_list, &ICON, "Pay with\nUSDC cash", NULL, s_msg,
                       pay_choice);
    return SW_OK;
}

static int pay(const uint8_t *d, size_t len) {
    if (len != REQ_LEN) return io_send_sw(SW_WRONG_LENGTH);
    uint16_t sw = pay_review(d, PAY_USB);
    return sw == SW_OK ? 0 : io_send_sw(sw);
}

#ifdef HAVE_NFC_READER
/* ---------------- TAP_TO_PAY (payer = NFC reader, payee = card emulation) ----------------
 * Never answers over USB: the host polls TAP_STATUS. Every exit goes through tap_end().
 * Cash rule: the debit is persisted (pay_sign) before PUT_AUTH carries the signature out, so a card
 * that leaves after that point still costs the payer the amount; the auth stays readable over USB
 * through TAP_STATUS until the next tap or app exit (RAM only). A card that leaves before approval costs nothing. */
static void tap_end(uint8_t state, uint16_t sw, const char *msg) {
    io_nfc_reader_stop();
    os_io_nfc_cmd_start_ce();  // back to normal mode (card emulation); reader_stop does not do it
    g_tap = state;
    g_tap_sw = sw;
    g_pay_src = PAY_NONE;
    g_busy = false;
    nbgl_useCaseStatus(msg, state == TAP_PAID, ui_home);
}

// SW of the card's reply, or 0 if the exchange failed (the tap is then already ended)
static uint16_t tap_reply(bool error, bool timeout, const uint8_t *d, size_t n) {
    if (!error && !timeout && d != NULL && n >= 2) return U2BE(d, n - 2);
    uint16_t sw = error ? SW_CARD_GONE : SW_NO_ANSWER;
    if (g_tap == TAP_SENT) {
        fmt_usdc(s_amount, sizeof(s_amount), read_u64_be(g_pay, R_VALUE));
        snprintf(s_msg, sizeof(s_msg), "Signed %s\n%s\nCash debited, no receipt", s_amount,
                 error ? "Card left after signing" : "Payee did not confirm");
        tap_end(TAP_NO_RECEIPT, sw, s_msg);
    } else {
        tap_end(TAP_FAILED, sw, error ? "Card removed\nNothing paid" : "Payee did not answer\nNothing paid");
    }
    return 0;
}

static void tap_on_receipt(bool error, bool timeout, uint8_t *d, size_t n) {
    uint16_t sw = tap_reply(error, timeout, d, n);
    if (!sw) return;
    uint8_t r[66], h[32], who[20];
    fmt_usdc(s_amount, sizeof(s_amount), read_u64_be(g_pay, R_VALUE));
    if (sw != SW_OK || n != sizeof(r) + 2) {
        snprintf(s_msg, sizeof(s_msg), "Signed %s\nPayee refused it\nCash debited", s_amount);
        tap_end(TAP_NO_RECEIPT, sw == SW_OK ? SW_WRONG_LENGTH : sw, s_msg);
        return;
    }
    memcpy(r, d, sizeof(r));
    keccak(g_tap_auth, AUTH_LEN, h);
    eip191(h, h);
    if (r[0] != 1 || !ecrecover(h, r[65], r + 1, r + 33, who) || memcmp(who, g_pay + R_PAYTO, 20) != 0) {
        snprintf(s_msg, sizeof(s_msg), "Signed %s\nReceipt invalid\nCash debited", s_amount);
        tap_end(TAP_NO_RECEIPT, SW_BAD_AUTH, s_msg);
        return;
    }
    fmt_addr(s_addr, g_pay + R_PAYTO);
    snprintf(s_msg, sizeof(s_msg), "Paid %s\nto %s", s_amount, s_addr);
    tap_end(TAP_PAID, SW_OK, s_msg);
}

static void tap_choice(bool ok) {
    if (!ok) {
        tap_end(TAP_FAILED, SW_REJECTED, "Payment rejected\nNothing paid");
        return;
    }
    uint16_t sw = pay_sign(g_tap_auth);  // signs and persists the debit
    if (sw != SW_OK) {
        tap_end(TAP_FAILED, sw, "Payment failed\nNothing paid");
        return;
    }
    g_tap = TAP_SENT;
    g_tap_cmd[0] = CLA;
    g_tap_cmd[1] = INS_PUT_AUTH;
    g_tap_cmd[2] = g_tap_cmd[3] = 0;
    g_tap_cmd[4] = AUTH_LEN;
    memcpy(g_tap_cmd + 5, g_tap_auth, AUTH_LEN);
    nbgl_useCaseSpinner("Sending payment");
    io_nfc_reader_send(g_tap_cmd, sizeof(g_tap_cmd), tap_on_receipt, 5000);
}

static void tap_on_request(bool error, bool timeout, uint8_t *d, size_t n) {
    uint16_t sw = tap_reply(error, timeout, d, n);
    if (!sw) return;
    if (sw != SW_OK) {
        tap_end(TAP_FAILED, sw, sw == SW_NO_REQUEST ? "Payee has no request" : "Payee refused");
        return;
    }
    if (n != REQ_LEN + 2) {
        tap_end(TAP_FAILED, SW_WRONG_LENGTH, "Bad request from payee");
        return;
    }
    uint8_t q[REQ_LEN];
    memcpy(q, d, REQ_LEN);
    sw = pay_review(q, PAY_TAP);  // review on screen; tap_choice continues
    if (sw == SW_OK) return;
    tap_end(TAP_FAILED, sw,
            sw == SW_REPLAY          ? "Already paid\nNothing signed"
            : sw == SW_INSUFFICIENT  ? "Not enough cash\nNothing signed"
            : sw == SW_BAD_PAYEE_SIG ? "Payee signature invalid\nNothing signed"
            : sw == SW_CONFIG        ? "Wrong network or token\nNothing signed"
                                     : "Request refused\nNothing signed");
}

static void tap_on_select(bool error, bool timeout, uint8_t *d, size_t n) {
    static const uint8_t GET_REQ[] = {CLA, INS_GET_REQUEST, 0, 0, 0};
    uint16_t sw = tap_reply(error, timeout, d, n);
    if (!sw) return;
    if (sw != SW_OK) {
        tap_end(TAP_FAILED, sw, "Not a Ledger Cash payee");
        return;
    }
    io_nfc_reader_send(GET_REQ, sizeof(GET_REQ), tap_on_request, 2000);
}

static void tap_evt(enum nfc_event ev, struct card_info *info) {
    static const uint8_t SELECT[5 + sizeof(AID)] = {0x00, 0xA4, 0x04, 0x00, sizeof(AID), 0xF0,
                                                    'L',  'E',  'D',  'G',  'E',  'R',
                                                    'C',  'A',  'S',  'H',  0x01};
    UNUSED(info);  // ponytail: UID unused (may be stale with the own IO stack, see research note)
    if (ev == CARD_DETECTED) {
        if (g_tap != TAP_WAIT) return;
        g_tap = TAP_BUSY;
        nbgl_useCaseSpinner("Reading request");
        io_nfc_reader_send(SELECT, sizeof(SELECT), tap_on_select, 2000);
    } else if (g_tap == TAP_BUSY) {
        // removed while the review is on screen (a pending command is handled by tap_reply instead)
        tap_end(TAP_FAILED, SW_CARD_GONE, "Card removed\nNothing paid");
    }
}

static void tap_cancel(void) {
    tap_end(TAP_FAILED, SW_REJECTED, "Tap cancelled");
}

static uint16_t tap_start(void) {
    if (!NV.configured) return SW_CONFIG;
    g_tap = TAP_WAIT;
    g_tap_sw = 0;
    memset(g_tap_auth, 0, AUTH_LEN);
    g_busy = true;
    io_nfc_reader_start(tap_evt);
    nbgl_useCaseAction(&ICON, "Hold near the payee", "Cancel", tap_cancel);
    return SW_OK;
}

static void tap_menu(void) {
    if (tap_start() != SW_OK) nbgl_useCaseStatus("Set the USDC network first", false, ui_home);
}

static int tap_status(void) {
    uint8_t out[3 + AUTH_LEN];
    out[0] = g_tap;
    write_u16_be(out, 1, g_tap_sw);
    memcpy(out + 3, g_tap_auth, AUTH_LEN);
    return io_send_response_pointer(out, sizeof(out), SW_OK);
}
#endif  // HAVE_NFC_READER

/* ---------------- PUT_AUTH / GET_AUTHS (payee) ---------------- */
static int put_auth(const uint8_t *a, size_t len) {
    if (len != AUTH_LEN) return io_send_sw(SW_WRONG_LENGTH);
    if (!g_req_valid) return io_send_sw(SW_NO_REQUEST);
    const uint8_t *q = g_req;
    uint8_t h[32], who[20], out[1 + 65];
    keccak(q, REQ_BODY, h);
    if (memcmp(a + A_TO, q + R_PAYTO, 20) != 0 || memcmp(a + A_VALUE, q + R_VALUE, 8) != 0 ||
        read_u64_be(a, A_VAFT) != 0 || memcmp(a + A_VBEF, q + R_VBEF, 8) != 0 ||
        memcmp(a + A_NONCE, h, 32) != 0) {
        return io_send_sw(SW_BAD_AUTH);
    }
    if (memcmp(a + A_S, SECP_N_HALF, 32) > 0) return io_send_sw(SW_BAD_AUTH);  // high-s never settles
    auth_digest(a, h);
    if (!ecrecover(h, a[A_V], a + A_R, a + A_S, who) || memcmp(who, a + A_FROM, 20) != 0) {
        return io_send_sw(SW_BAD_AUTH);
    }
    // receipt: payee signs EIP-191(keccak(auth)), r||s||v; signed before storing so a failure stores nothing
    keccak(a, AUTH_LEN, h);
    eip191(h, h);
    out[0] = 0x01;
    if (!sign_hash(h, out + 1, out + 33, &out[65])) return io_send_sw(SW_CRYPTO);
    uint32_t n = NV.auth_count, next = n + 1;
    nvm_write((void *) NV.auths[n % AUTHS_N], (void *) a, AUTH_LEN);
    nvm_write((void *) &NV.auth_count, &next, 4);
    g_req_valid = false;  // a request is paid once
    fmt_addr(s_addr, a + A_FROM);
    fmt_usdc(s_amount, sizeof(s_amount), read_u64_be(a, A_VALUE));
    // Not "Received": any key can sign a matching auth; nothing here proves funds (README Honest limits)
#if defined(TARGET_NANOS2) || defined(TARGET_NANOX)
    // 128x64 status fits ~4 lines: short address (full one via GET_AUTHS), else "Not settled yet" is cut off
    snprintf(s_msg, sizeof(s_msg), "IOU %s from\n%.*s...%s\nNot settled yet", s_amount, 6, s_addr, s_addr + 37);
#else
    snprintf(s_msg, sizeof(s_msg), "Signed IOU for %s\nfrom %s\nNot settled yet", s_amount, s_addr);
#endif
    io_send_response_pointer(out, sizeof(out), SW_OK);
    nbgl_useCaseStatus(s_msg, true, ui_home);
    return 0;
}

static int get_auths(uint8_t i) {
    uint32_t n = NV.auth_count;
    if (i >= AUTHS_N || i >= n) return io_send_sw(SW_NOT_FOUND);
    return io_send_response_pointer((const uint8_t *) NV.auths[i], AUTH_LEN, SW_OK);
}

/* ---------------- dispatch + main loop ---------------- */
static int dispatch(const command_t *c) {
    if (c->cla == 0x00 && c->ins == 0xA4) {  // ISO SELECT by AID: the payer's first NFC command
        bool us = c->p1 == 0x04 && c->lc == sizeof(AID) && memcmp(c->data, AID, sizeof(AID)) == 0;
        return io_send_sw(us ? SW_OK : 0x6A82);
    }
    if (c->cla != CLA) return io_send_sw(SW_BAD_CLA);
    // Over NFC this app is only a payee card: anything else (balance, address, PAY/LOAD_CASH reviews,
    // TAP_TO_PAY) would be open to any reader in range.
#ifdef HAVE_NFC
    if (G_io_app.apdu_media == IO_APDU_MEDIA_NFC && c->ins != INS_GET_REQUEST && c->ins != INS_PUT_AUTH) {
        return io_send_sw(SW_BAD_INS);
    }
#endif
    // read-only status stays available while a screen is up (the host polls it during a tap)
    if (c->ins == INS_GET_BALANCE) return get_balance();
#ifdef HAVE_NFC_READER
    if (c->ins == INS_TAP_STATUS) return tap_status();
#endif
    if (g_busy) return io_send_sw(SW_BUSY);
    if (c->ins != INS_GET_AUTHS && (c->p1 || c->p2)) return io_send_sw(SW_BAD_P1P2);
    switch (c->ins) {
        case INS_SET_REQUEST: return set_request(c->data, c->lc);
        case INS_GET_REQUEST:
            return g_req_valid ? io_send_response_pointer(g_req, REQ_LEN, SW_OK)
                               : io_send_sw(SW_NO_REQUEST);
        case INS_SET_CONFIG: return set_config(c->data, c->lc);
        case INS_LOAD_CASH: return load_cash(c->data, c->lc);
        case INS_GET_BALANCE: return get_balance();
        case INS_PAY: return pay(c->data, c->lc);
        case INS_PUT_AUTH: return put_auth(c->data, c->lc);
        case INS_GET_AUTHS: return get_auths(c->p1);
#ifdef HAVE_NFC_READER
        case INS_TAP_TO_PAY: return io_send_sw(tap_start());
#endif
        default: return io_send_sw(SW_BAD_INS);
    }
}

void app_main(void) {
    command_t cmd;
    int len;
    io_init();
    ui_home();
    for (;;) {
        if ((len = io_recv_command()) < 0) return;
        if (!apdu_parser(&cmd, G_io_apdu_buffer, len)) {
            io_send_sw(SW_WRONG_LENGTH);
            continue;
        }
        if (dispatch(&cmd) < 0) return;
    }
}
