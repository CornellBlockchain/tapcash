/* Host checks for tangem.c.
 *   ./test_tangem          unit tests (vectors from the MIT-era Tangem SDK tests + constructed ones)
 *   ./test_tangem --flow   drive tg_next over stdin/stdout: prints "APDU <hex>", reads "<hex>" replies;
 *                          mock_tangem.py --harness runs this against the fake card.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "tangem.h"

static int fails;
#define CHECK(c)                                                 \
    do {                                                         \
        if (!(c)) {                                              \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c);  \
            fails++;                                             \
        }                                                        \
    } while (0)

static size_t unhex(const char *h, uint8_t *out, size_t cap) {
    size_t n = 0;
    unsigned b;
    while (h[0] && h[1] && n < cap && sscanf(h, "%2x", &b) == 1) out[n++] = (uint8_t) b, h += 2;
    return n;
}
static void hex(const char *pre, const uint8_t *b, size_t n) {
    printf("%s", pre);
    for (size_t i = 0; i < n; i++) printf("%02x", b[i]);
    printf("\n");
}
static int eqhex(const uint8_t *b, size_t n, const char *h) {
    uint8_t x[512];
    return unhex(h, x, sizeof x) == n && memcmp(b, x, n) == 0;
}

/* ---- test-only keccak-256 (the app passes cx_keccak_256_hash instead) ---- */
static uint64_t rol(uint64_t x, int s) { return (x << s) | (x >> (64 - s)); }
static void keccakf(uint64_t st[25]) {
    static const uint64_t RC[24] = {
        0x0000000000000001ULL, 0x0000000000008082ULL, 0x800000000000808aULL, 0x8000000080008000ULL,
        0x000000000000808bULL, 0x0000000080000001ULL, 0x8000000080008081ULL, 0x8000000000008009ULL,
        0x000000000000008aULL, 0x0000000000000088ULL, 0x0000000080008009ULL, 0x000000008000000aULL,
        0x000000008000808bULL, 0x800000000000008bULL, 0x8000000000008089ULL, 0x8000000000008003ULL,
        0x8000000000008002ULL, 0x8000000000000080ULL, 0x000000000000800aULL, 0x800000008000000aULL,
        0x8000000080008081ULL, 0x8000000000008080ULL, 0x0000000080000001ULL, 0x8000000080008008ULL};
    static const int R[24] = {1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 2, 14, 27, 41, 56, 8, 25, 43, 62, 18, 39, 61, 20, 44};
    static const int P[24] = {10, 7, 11, 17, 18, 3, 5, 16, 8, 21, 24, 4, 15, 23, 19, 13, 12, 2, 20, 14, 22, 9, 6, 1};
    for (int r = 0; r < 24; r++) {
        uint64_t bc[5], t;
        for (int i = 0; i < 5; i++) bc[i] = st[i] ^ st[i + 5] ^ st[i + 10] ^ st[i + 15] ^ st[i + 20];
        for (int i = 0; i < 5; i++) {
            t = bc[(i + 4) % 5] ^ rol(bc[(i + 1) % 5], 1);
            for (int j = 0; j < 25; j += 5) st[j + i] ^= t;
        }
        t = st[1];
        for (int i = 0; i < 24; i++) {
            uint64_t u = st[P[i]];
            st[P[i]] = rol(t, R[i]);
            t = u;
        }
        for (int j = 0; j < 25; j += 5) {
            for (int i = 0; i < 5; i++) bc[i] = st[j + i];
            for (int i = 0; i < 5; i++) st[j + i] ^= (~bc[(i + 1) % 5]) & bc[(i + 2) % 5];
        }
        st[0] ^= RC[r];
    }
}
static void keccak256(const uint8_t *in, size_t len, uint8_t out[32]) {
    uint64_t st[25] = {0};
    uint8_t blk[136];
    for (;;) {
        size_t n = len < 136 ? len : 136;
        memset(blk, 0, 136);
        memcpy(blk, in, n);
        if (n < 136) blk[n] ^= 0x01, blk[135] ^= 0x80;
        for (int i = 0; i < 17; i++)
            for (int b = 0; b < 8; b++) st[i] ^= (uint64_t) blk[8 * i + b] << (8 * b);
        keccakf(st);
        if (n < 136) break;
        in += 136, len -= 136;
        if (len == 0) { /* exact multiple: one more padding-only block */
            memset(blk, 0, 136), blk[0] = 0x01, blk[135] = 0x80;
            for (int i = 0; i < 17; i++)
                for (int b = 0; b < 8; b++) st[i] ^= (uint64_t) blk[8 * i + b] << (8 * b);
            keccakf(st);
            break;
        }
    }
    for (int i = 0; i < 32; i++) out[i] = (uint8_t) (st[i / 8] >> (8 * (i % 8)));
}

/* secp256k1 generator = public key of private key 1; its address is a well-known vector */
static const char *G_UNCOMP =
    "0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
    "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8";
static bool stub_decompress(const uint8_t in[33], uint8_t out[65]) {
    uint8_t g[65];
    unhex(G_UNCOMP, g, 65);
    if (in[0] != 0x02 || memcmp(in + 1, g + 1, 32) != 0) return false; /* only knows G (y even) */
    memcpy(out, g, 65);
    return true;
}
static uint8_t want_addr[20];
static bool stub_recover(const uint8_t z[32], uint8_t v, const uint8_t r[32], const uint8_t s[32], uint8_t a[20]) {
    (void) z, (void) r, (void) s;
    memset(a, 0xEE, 20);
    if (v == 28) memcpy(a, want_addr, 20);
    return true;
}

/* Recorded Read reply (fw 2.11r card, 2019) from tangem-sdk-android ResponseApduTest.kt @ cdf62aacbe (MIT) */
static const char *READ_V2 =
    "0108cb22000000027374200b534d4152542043415348000201028006322e31317200034104cf0bcebe87e7fe4141f30e311baedfab"
    "8f411408d9b5392d41e1232c26283fd471d3b5a18a761d4175e8cb52b85beca0b399f2c1348185e5f080bdfd98e6ea410a040000"
    "7e210c5a81020029820407e30502830754414e47454d00840345544886406f99308ed812991a9af4dab2a6f79e58d19ce81897ba"
    "b8065ea0b30b85e48a253f6bc9f517f40de987c124c546745b83debb1790061104cf44c81dd3510a61533041048196aa4b410ac4"
    "4a3b9cce18e7be226aea070acc83a9cf67540fac49af25129f6a538a28ad6341358e3c4f9963064f7e365372a651d374e5c23cdd"
    "37fd099bf2050a736563703235366b31000804000f424007010009020bb8604104d6fbd7ace9580256c18a85f6beae95bca36f2f"
    "5decaa4a1c15515deb84c79a371154bebcea807e9dbfcad63be7eb84053bf0b8493010e56790b70260cd29d6746204000f423463"
    "040000000d0f01009000";

static const uint8_t SW_OK[2] = {0x90, 0x00};

static void unit(void) {
    uint8_t a[512], b[512], h[32];
    size_t n;

    /* keccak self-check, then the privkey-1 address */
    keccak256((const uint8_t *) "", 0, h);
    CHECK(eqhex(h, 32, "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"));
    unhex(G_UNCOMP, a, 65);
    CHECK(tg_eth_address(a, 65, keccak256, NULL, b));
    CHECK(eqhex(b, 20, "7e5f4552091a69125d5dfcb7b8c2659029395bdf"));
    a[0] = 0x02; /* compressed form of G */
    CHECK(!tg_eth_address(a, 33, keccak256, NULL, b));
    CHECK(tg_eth_address(a, 33, keccak256, stub_decompress, b));
    CHECK(eqhex(b, 20, "7e5f4552091a69125d5dfcb7b8c2659029395bdf"));

    /* SELECT and Read: SDK CommandApduTest vector is 00F2 0000 000022 1020<sha256("000000")>; ours adds mode 1 */
    n = tg_apdu_select(a, sizeof a);
    CHECK(eqhex(a, n, "00a4040008a000000812010208"));
    n = tg_apdu_read_card(a, sizeof a, TG_DEFAULT_ACCESS_CODE_HASH);
    CHECK(eqhex(a, n, "00f20000000025102091b4d142823f7d20c5f08df69122de43f35f057a988d9619f6d3138485c9a203230101"));
    CHECK(tg_apdu_read_card(a, 40, TG_DEFAULT_ACCESS_CODE_HASH) == 0); /* does not fit */

    static const uint32_t eth[5] = {0x8000002C, 0x8000003C, 0x80000000, 0, 0};
    uint8_t cid[8] = {0xCB, 0x22, 0, 0, 0, 2, 0x73, 0x74};
    n = tg_apdu_read_wallet(a, sizeof a, TG_DEFAULT_ACCESS_CODE_HASH, cid, 0, eth, 5);
    CHECK(eqhex(a, n,
                "00f20000000048102091b4d142823f7d20c5f08df69122de43f35f057a988d9619f6d3138485c9a2030108cb2200000002"
                "7374230102650100"
                "6a148000002c8000003c800000000000000000000000"));
    memset(h, 0xAB, 32);
    n = tg_apdu_sign(a, sizeof a, TG_DEFAULT_ACCESS_CODE_HASH, TG_DEFAULT_PASSCODE_HASH, cid, 0, eth, 5, h);
    CHECK(n == 7 + 34 + 34 + 10 + 3 + 34 + 3 + 22 && a[1] == 0xFB && a[6] == n - 7);
    CHECK(eqhex(a + 41, 34, "11202ac9a6746aca543af8dff39894cfe8173afba21eb01c6fae33d52947222855ef"));
    CHECK(eqhex(a + 75, 13, "0108cb22000000027374510120"));
    n = tg_apdu_attest(a, sizeof a, TG_DEFAULT_ACCESS_CODE_HASH, cid, h);
    CHECK(n == 7 + 34 + 10 + 18 && a[1] == 0xF3 && a[51] == 0x16 && a[52] == 16);

    /* parse the recorded card */
    tg_card_t c;
    memset(&c, 0, sizeof c);
    n = unhex(READ_V2, a, sizeof a);
    CHECK(n == 375 && tg_status(a, n, NULL) == TG_OK);
    CHECK(tg_parse_read(a, n - 2, &c));
    CHECK(c.has_card_id && eqhex(c.card_id, 8, "cb22000000027374"));
    CHECK(c.status == 2 && c.fw_major == 2 && c.fw_minor == 11 && c.settings == 0x7e21);
    CHECK(strcmp(c.manufacturer, "SMART CASH") == 0);
    CHECK(c.secp256k1 && c.wallet_pubkey_len == 65 && c.wallet_pubkey[1] == 0xd6 && c.wallet_pubkey[64] == 0x74);
    CHECK(c.card_pubkey_len == 65 && c.card_pubkey[1] == 0xcf);
    CHECK(c.has_mfr_sig && c.mfr_sig[0] == 0x6f && c.mfr_sig[63] == 0x53);
    CHECK(!c.pin_is_default);

    /* tg_next on that fw < 4 card: the key comes with Read Card, no wallet-mode Read */
    static tg_session_t ss;
    uint8_t o[256];
    tg_session_init(&ss);
    CHECK(tg_next(&ss, NULL, 0, o, sizeof o) == 13 && ss.state == TG_ST_SELECT);
    CHECK(tg_next(&ss, SW_OK, 2, o, sizeof o) > 0 && ss.state == TG_ST_READ_CARD);
    CHECK(tg_next(&ss, a, n, o, sizeof o) == 0 && ss.state == TG_ST_DONE && ss.card.wallet_pubkey[1] == 0xd6);

    /* a wallet reply that says secp256k1 but carries no key must not reuse an earlier wallet's key */
    tg_session_init(&ss);
    tg_next(&ss, NULL, 0, o, sizeof o);
    tg_next(&ss, SW_OK, 2, o, sizeof o);
    uint8_t rc[] = {0x01, 0x08, 1, 2, 3, 4, 5, 6, 7, 8, 0x02, 0x01, 0x02, 0x80, 0x04, '6', '.', '3', '3',
                    0x0A, 0x04, 0x00, 0x20, 0x00, 0x00, 0x66, 0x01, 0x03, 0x90, 0x00};
    CHECK(tg_next(&ss, rc, sizeof rc, o, sizeof o) > 0 && ss.state == TG_ST_READ_WALLET);
    uint8_t w0[2 + 65 + 12 + 3 + 2];
    w0[0] = 0x60, w0[1] = 65;
    unhex(G_UNCOMP, w0 + 2, 65);
    memcpy(w0 + 67, "\x05\x0a" "secp256r1", 11), w0[78] = 0; /* a P-256 wallet with a 65-byte key */
    memcpy(w0 + 79, "\x65\x01\x00\x90\x00", 5);
    CHECK(tg_next(&ss, w0, sizeof w0, o, sizeof o) > 0 && ss.state == TG_ST_READ_WALLET);
    uint8_t w1[] = {0x05, 0x0A, 's', 'e', 'c', 'p', '2', '5', '6', 'k', '1', 0, 0x65, 0x01, 0x01, 0x90, 0x00};
    CHECK(tg_next(&ss, w1, sizeof w1, o, sizeof o) > 0 && ss.state == TG_ST_READ_WALLET); /* no key: next index */
    CHECK(ss.card.wallet_pubkey_len == 0 && ss.card.wallet_index == 2);

    /* 6A86 on Sign is a bad parameter, not an access-code prompt */
    ss.state = TG_ST_SIGN;
    CHECK(tg_next(&ss, (const uint8_t *) "\x6A\x86", 2, o, sizeof o) == 0 && ss.why == TG_ERR);

    /* untrusted input: every truncation of the body must be rejected or parse a prefix, never overrun */
    for (size_t cut = 1; cut < n - 2; cut++) {
        tg_card_t d;
        memset(&d, 0, sizeof d);
        (void) tg_parse_read(a, cut, &d); /* run under -fsanitize=address */
    }
    uint8_t bad[] = {0x60, 0x41, 0x04}; /* length 65, 1 byte present */
    CHECK(!tg_parse_read(bad, sizeof bad, &c));
    uint8_t ed[] = {0x60, 0x20, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22,
                    23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 0x05, 0x07, 'e', 'd', '2', '5', '5', '1', '9'};
    memset(&c, 0, sizeof c);
    CHECK(tg_parse_read(ed, sizeof ed, &c) && !c.secp256k1 && c.wallet_pubkey_len == 0); /* skipped, not fatal */
    uint8_t ext[4 + 300 + 3];
    memset(ext, 0, sizeof ext);
    ext[0] = 0x71, ext[1] = 0xFF, ext[2] = 0x01, ext[3] = 0x2C; /* 300-byte value, 3-byte length */
    ext[304] = 0x66, ext[305] = 0x01, ext[306] = 0x05;
    memset(&c, 0, sizeof c);
    CHECK(tg_parse_read(ext, sizeof ext, &c) && c.wallets_count == 5);
    uint8_t list[] = {0x68, 0x0C, 0x65, 0x01, 0x00, 0x05, 0x07, 'e', 'd', '2', '5', '5', '1', '9',
                      0x68, 0x32, 0x65, 0x01, 0x01, 0x05, 0x0A, 's', 'e', 'c', 'p', '2', '5', '6', 'k', '1', 0,
                      0x60, 0x21, 0x02, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21,
                      22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32};
    memset(&c, 0, sizeof c);
    CHECK(tg_parse_read(list, sizeof list, &c) && c.secp256k1 && c.wallet_index == 1 && c.wallet_pubkey_len == 33);

    /* status words */
    uint8_t sw[] = {0x1C, 0x02, 0x01, 0x2C, 0x97, 0x89};
    uint16_t pause = 0;
    CHECK(tg_status(sw, sizeof sw, &pause) == TG_RESEND && pause == 300);
    CHECK(tg_status((const uint8_t *) "\x90\x07", 2, NULL) == TG_OK);
    CHECK(tg_status((const uint8_t *) "\x69\x82", 2, NULL) == TG_NEED_ENCRYPTION);
    CHECK(tg_status((const uint8_t *) "\x6A\xF1", 2, NULL) == TG_NEED_ACCESS_CODE);
    CHECK(tg_status((const uint8_t *) "\x6A\x86", 2, NULL) == TG_NEED_ACCESS_CODE);
    CHECK(tg_status((const uint8_t *) "\x6A\x88", 2, NULL) == TG_WALLET_NOT_FOUND);
    CHECK(tg_status((const uint8_t *) "\x90", 1, NULL) == TG_ERR);

    /* low-s: n-1 -> 1, n/2 stays, n/2+1 -> n/2 */
    uint8_t sig[64] = {0};
    unhex("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364140", sig + 32, 32);
    tg_sig_low_s(sig);
    CHECK(eqhex(sig + 32, 32, "0000000000000000000000000000000000000000000000000000000000000001"));
    unhex("7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0", sig + 32, 32);
    tg_sig_low_s(sig);
    CHECK(eqhex(sig + 32, 32, "7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0"));
    unhex("7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a1", sig + 32, 32);
    tg_sig_low_s(sig);
    CHECK(eqhex(sig + 32, 32, "7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0"));

    uint8_t other[20];
    memset(want_addr, 0x42, 20);
    CHECK(tg_sig_v(h, sig, want_addr, stub_recover) == 28);
    memset(other, 0x01, 20);
    CHECK(tg_sig_v(h, sig, other, stub_recover) == 0);
}

/* stdin/stdout driver for mock_tangem.py --harness */
static int flow(void) {
    static tg_session_t s;
    uint8_t out[256], rsp[1024], addr[20];
    char line[2200];
    tg_session_init(&s);
    s.want_sign = s.want_attest = true;
    memset(s.digest, 0x5A, 32); /* stands in for the EIP-712 digest */
    memset(s.challenge, 0xC4, 16);
    const char *code = getenv("TG_ACCESS_CODE_SHA256");
    if (code) unhex(code, s.pin, 32);
    size_t n = tg_next(&s, NULL, 0, out, sizeof out);
    while (n) {
        hex("APDU ", out, n);
        fflush(stdout);
        if (!fgets(line, sizeof line, stdin)) return 2;
        size_t m = unhex(line, rsp, sizeof rsp);
        n = tg_next(&s, rsp, m, out, sizeof out);
        if (s.pause_cs) printf("# security delay %u cs\n", s.pause_cs), s.pause_cs = 0;
    }
    printf("STATE %d WHY %d\n", s.state, s.why);
    if (s.state != TG_ST_DONE) return 1;
    hex("CARD_ID ", s.card.card_id, 8);
    printf("FW %u.%u SETTINGS %08x WALLET_INDEX %u\n", s.card.fw_major, s.card.fw_minor, s.card.settings,
           s.card.wallet_index);
    hex("WALLET_PUBKEY ", s.card.wallet_pubkey, s.card.wallet_pubkey_len);
    if (tg_eth_address(s.card.wallet_pubkey, s.card.wallet_pubkey_len, keccak256, NULL, addr)) hex("ADDRESS 0x", addr, 20);
    hex("DIGEST ", s.digest, 32);
    hex("SIG ", s.sig, 64);
    hex("CARD_PUBKEY ", s.card.card_pubkey, s.card.card_pubkey_len);
    hex("CHALLENGE ", s.challenge, 16);
    hex("SALT ", s.salt, s.salt_len);
    hex("CARD_SIG ", s.card_sig, 64);
    return 0;
}

int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "--flow") == 0) return flow();
    unit();
    printf(fails ? "%d FAILED\n" : "PASS: tangem unit tests\n", fails);
    return fails != 0;
}
