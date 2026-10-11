#include <stdint.h>
#include <string.h>

#include "os.h"
#include "io.h"
#include "cx.h"
#include "crypto_helpers.h"
#include "format.h"
#include "read.h"
#include "nbgl_use_case.h"
#include "glyphs.h"

// TapCash speaks just enough U2F (FIDO over NFC) for Safari's WebAuthn to be the
// transport: no iOS app or paid Apple account needed. The web page puts the payment
// request in the credential ID (U2F key handle); the signed authorization rides back
// in the signature field.

#define CLA_ISO       0x00
#define INS_SELECT    0xA4
#define INS_U2F_SIGN  0x02
#define P1_CHECK_ONLY 0x07
#define CLA_TAPCASH   0xE0
#define INS_GET_ADDR  0x02

#define SW_OK             0x9000
#define SW_NOT_SATISFIED  0x6985  // U2F "user presence required": tells WebAuthn to retry
#define SW_WRONG_LEN      0x6700
#define SW_WRONG_DATA     0x6A80
#define SW_FILE_NOT_FOUND 0x6A82
#define SW_BAD_INS        0x6D00
#define SW_CRYPTO         0x6F00

static const uint8_t FIDO_AID[] = {0xA0, 0x00, 0x00, 0x06, 0x47, 0x2F, 0x00, 0x01};

// U2F sign request data: challenge(32) | application(32) | key handle length(1) | key handle
#define U2F_KH_LEN_OFFSET 64

// Payment request (key handle): to(20) | value(8, micro-USDC) | validBefore(4) | nonce(32)
#define REQ_LEN 64
// Address request (key handle): "ADDR". Lets the page fill in where to move funds to.
static const uint8_t ADDR_REQ[] = {'A', 'D', 'D', 'R'};

// USDC on Base Sepolia (0x036CbD53842c5426634e7929541eC2318f3dCF7e, chainId 84532).
// Both values checked against the contract's DOMAIN_SEPARATOR() and
// TRANSFER_WITH_AUTHORIZATION_TYPEHASH(). Signatures can't be replayed on another chain.
static const uint8_t DOMAIN_SEPARATOR[32] = {
    0x71, 0xf1, 0x7a, 0x3b, 0x2f, 0xf3, 0x73, 0xb8, 0x03, 0xd7, 0x0a, 0x5a, 0x07, 0xc0, 0x46, 0xc1,
    0xa2, 0xbc, 0x8e, 0x89, 0xc0, 0x9e, 0xf7, 0x22, 0xfc, 0xb0, 0x47, 0xab, 0xe9, 0x4c, 0x98, 0x18};
static const uint8_t TYPEHASH[32] = {
    0x7c, 0x7c, 0x6c, 0xdb, 0x67, 0xa1, 0x87, 0x43, 0xf4, 0x9e, 0xc6, 0xfa, 0x9b, 0x35, 0xf5, 0x0d,
    0x52, 0xed, 0x05, 0xcb, 0xed, 0x4c, 0xc5, 0x92, 0xe1, 0x3b, 0x44, 0x50, 0x1c, 0x1a, 0x22, 0x67};

static const uint32_t PATH[] = {0x8000002C, 0x8000003C, 0x80000000, 0, 0};  // m/44'/60'/0'/0/0

static enum { IDLE, REVIEW, APPROVED } state;
static uint8_t request[REQ_LEN];
static char review_text[80];
// user presence | counter (last byte = v) | DER(r, s) | from(20)
static uint8_t response[1 + 4 + 72 + 20];
static size_t response_len;

// Pocket mode: after one approval on the Flex, payments up to the per-tap cap are signed on the
// first tap, without review, until the total or the number of payments is used up, or the app
// closes (RAM only). All three limits are picked in Settings; defaults 5 USDC per tap,
// 20 USDC in total, 10 payments.
// ponytail: preset caps and no time limit (no clock on the Flex); a number keyboard if presets aren't enough.
#define USDC(n) ((uint64_t) (n) * 1000000)
#define NB_CAPS 4  // one settings page each
static const uint32_t PER_TAP_CAPS[NB_CAPS] = {1, 5, 10, 50};   // USDC
static const uint32_t TOTAL_CAPS[NB_CAPS] = {10, 20, 100, 500};  // USDC
static const uint32_t COUNT_CAPS[NB_CAPS] = {1, 5, 10, 25};       // payments
static uint8_t per_tap_idx, total_idx, count_idx;  // set in app_main: apps can't have initialized .data
static uint64_t pocket_left;          // 0 = off
static uint32_t pocket_taps_left;
static uint8_t pocket_paid[REQ_LEN];  // last one-tap (pocket or card) payment, so a retried tap gets the same reply
static bool pocket_paid_valid;        // false until a one-tap payment, and once `response` changes

// Card mode: turned on right before paying, it lets the next payment be signed on the first tap,
// without review and with no amount limit, like a card the merchant's terminal (the iPhone) charges.
// It turns off after that one payment, when turned off, or when the app closes (RAM only).
// ponytail: no timeout once on (no clock on the Flex); add one with an nbgl ticker if that matters.
static bool card_mode;
static char home_text[80];

static void app_quit(void) {
    os_sched_exit(-1);
}

static void format_usdc(char *out, size_t len, uint64_t micro) {
    memset(out, 0, len);  // SDK format_fpu64 doesn't NUL-terminate amounts >= 1
    format_fpu64_trimmed(out, len, micro, 6);
}

static void card_toggle(void);
static void settings_changed(int token, uint8_t index, int page);

enum { POCKET_TOKEN = FIRST_USER_TOKEN, PER_TAP_TOKEN, TOTAL_TOKEN, COUNT_TOKEN };

// Home and settings screens. All filled at runtime (apps can't have initialized .data). The SDK
// keeps pointers to these, so updating them in place shows the change when the user goes back
// home or reopens Settings; redrawing a settings page by number lands on the wrong page.
static nbgl_homeAction_t home_action;
static char per_tap_text[NB_CAPS][24], total_text[NB_CAPS][24], count_text[NB_CAPS][24];
static const char *per_tap_names[NB_CAPS], *total_names[NB_CAPS], *count_names[NB_CAPS];
static nbgl_contentSwitch_t pocket_switch;
static nbgl_content_t settings_contents[4];
static nbgl_genericContents_t settings;

static void ui_update(void) {
    pocket_switch.initState = pocket_left ? ON_STATE : OFF_STATE;
    settings_contents[1].content.choicesList.initChoice = per_tap_idx;
    settings_contents[2].content.choicesList.initChoice = total_idx;
    settings_contents[3].content.choicesList.initChoice = count_idx;
    if (card_mode) {
        snprintf(home_text, sizeof(home_text), "Card mode is on:\nthe next tap pays");
    } else if (pocket_left) {
        char left[24];
        format_usdc(left, sizeof(left), pocket_left);
        snprintf(home_text, sizeof(home_text), "Pocket mode: %s USDC left\nfor %u more payment%s",
                 left, (unsigned) pocket_taps_left, pocket_taps_left == 1 ? "" : "s");
    } else {
        snprintf(home_text, sizeof(home_text), "Hold your iPhone\nnear the screen");
    }
    home_action.text = card_mode ? "Turn off card mode" : "Turn on card mode";
}

static void ui_home(void) {
    for (int i = 0; i < NB_CAPS; i++) {
        snprintf(per_tap_text[i], sizeof(per_tap_text[i]), "%u USDC per tap", (unsigned) PER_TAP_CAPS[i]);
        snprintf(total_text[i], sizeof(total_text[i]), "%u USDC in total", (unsigned) TOTAL_CAPS[i]);
        snprintf(count_text[i], sizeof(count_text[i]), "%u payment%s", (unsigned) COUNT_CAPS[i],
                 COUNT_CAPS[i] == 1 ? "" : "s");
        per_tap_names[i] = per_tap_text[i];
        total_names[i] = total_text[i];
        count_names[i] = count_text[i];
    }
    memset(&pocket_switch, 0, sizeof(pocket_switch));
    pocket_switch.text = "Pocket mode";
    pocket_switch.subText = "One-tap payments within the limits on the next pages";
    pocket_switch.token = POCKET_TOKEN;
    pocket_switch.tuneId = NBGL_NO_TUNE;
    memset(settings_contents, 0, sizeof(settings_contents));
    settings_contents[0].type = SWITCHES_LIST;
    settings_contents[0].content.switchesList.switches = &pocket_switch;
    settings_contents[0].content.switchesList.nbSwitches = 1;
    settings_contents[0].contentActionCallback = settings_changed;
    settings_contents[1].type = CHOICES_LIST;
    settings_contents[1].content.choicesList.names = per_tap_names;
    settings_contents[1].content.choicesList.nbChoices = NB_CAPS;
    settings_contents[1].content.choicesList.token = PER_TAP_TOKEN;
    settings_contents[1].content.choicesList.tuneId = NBGL_NO_TUNE;
    settings_contents[1].contentActionCallback = settings_changed;
    settings_contents[2] = settings_contents[1];
    settings_contents[2].content.choicesList.names = total_names;
    settings_contents[2].content.choicesList.token = TOTAL_TOKEN;
    settings_contents[3] = settings_contents[1];
    settings_contents[3].content.choicesList.names = count_names;
    settings_contents[3].content.choicesList.token = COUNT_TOKEN;
    settings.callbackCallNeeded = false;
    settings.contentsList = settings_contents;
    settings.nbContents = 4;
    home_action.callback = card_toggle;
    home_action.style = SOFT_HOME_ACTION;
    ui_update();
    nbgl_useCaseHomeAndSettings(APPNAME,
                                &C_tapcash_64px,
                                home_text,
                                INIT_HOME_PAGE,
                                &settings,
                                NULL,
                                &home_action,
                                app_quit);
}

// The pocket switch starts or stops pocket mode. A new total or count restarts that part of a
// running pocket.
static void settings_changed(int token, uint8_t index, int page) {
    (void) page;
    if (token == POCKET_TOKEN) {
        if (index == ON_STATE) {
            pocket_left = USDC(TOTAL_CAPS[total_idx]);
            pocket_taps_left = COUNT_CAPS[count_idx];
        } else {
            pocket_left = 0;
        }
    } else if (index >= NB_CAPS) {
        return;
    } else if (token == PER_TAP_TOKEN) {
        per_tap_idx = index;
    } else if (token == TOTAL_TOKEN) {
        total_idx = index;
        if (pocket_left) {
            pocket_left = USDC(TOTAL_CAPS[total_idx]);
        }
    } else if (token == COUNT_TOKEN) {
        count_idx = index;
        if (pocket_left) {
            pocket_taps_left = COUNT_CAPS[count_idx];
        }
    }
    ui_update();
}

static void card_choice(bool confirm) {
    if (!confirm) {
        ui_home();
        return;
    }
    card_mode = true;
    nbgl_useCaseStatus("Card mode on", true, ui_home);
}

static void card_toggle(void) {
    if (card_mode) {
        card_mode = false;
        nbgl_useCaseStatus("Card mode off", true, ui_home);
        return;
    }
    nbgl_useCaseChoice(&C_tapcash_64px,
                       "Turn on card mode?",
                       "The next payment an iPhone asks for goes out on the first tap, "
                       "with no review and no limit, like tapping a card. Then card mode turns off.",
                       "Turn on",
                       "Cancel",
                       card_choice);
}

static bool get_address(uint8_t out[20]) {
    uint8_t pubkey[65], hash[32];
    if (bip32_derive_get_pubkey_256(CX_CURVE_256K1, PATH, 5, pubkey, NULL, CX_SHA512) != CX_OK ||
        cx_keccak_256_hash(pubkey + 1, 64, hash) != CX_OK) {
        return false;
    }
    memcpy(out, hash + 12, 20);
    return true;
}

// Minimal DER INTEGER: strip leading zeros, add 0x00 if the high bit is set.
static size_t der_int(uint8_t *out, const uint8_t v[32]) {
    size_t i = 0;
    while (i < 31 && v[i] == 0) {
        i++;
    }
    size_t pad = v[i] & 0x80 ? 1 : 0, n = 32 - i;
    out[0] = 0x02;
    out[1] = n + pad;
    out[2] = 0;
    memcpy(out + 2 + pad, v + i, n);
    return 2 + pad + n;
}

// EIP-712 digest of TransferWithAuthorization(from, to, value, validAfter=0, validBefore, nonce),
// signed with the device key.
static bool sign_request(void) {
    uint8_t from[20], buf[7 * 32], digest[32], r[32], s[32];
    uint32_t info = 0;
    pocket_paid_valid = false;  // `response` is about to change
    if (!get_address(from)) {
        return false;
    }
    memset(buf, 0, sizeof(buf));
    memcpy(buf, TYPEHASH, 32);
    memcpy(buf + 32 + 12, from, 20);
    memcpy(buf + 64 + 12, request, 20);              // to
    memcpy(buf + 96 + 24, request + 20, 8);          // value
                                                     // validAfter = 0
    memcpy(buf + 160 + 28, request + 28, 4);         // validBefore
    memcpy(buf + 192, request + 32, 32);             // nonce
    uint8_t msg[2 + 32 + 32] = {0x19, 0x01};
    memcpy(msg + 2, DOMAIN_SEPARATOR, 32);
    if (cx_keccak_256_hash(buf, sizeof(buf), msg + 34) != CX_OK ||
        cx_keccak_256_hash(msg, sizeof(msg), digest) != CX_OK ||
        bip32_derive_ecdsa_sign_rs_hash_256(CX_CURVE_256K1, PATH, 5, CX_RND_RFC6979 | CX_LAST,
                                            CX_SHA256, digest, 32, r, s, &info) != CX_OK) {
        return false;
    }
    // ponytail: v rides in the U2F counter; the web page normalizes s to low-s (USDC requires it)
    uint8_t *p = response;
    *p++ = 0x01;
    *p++ = 0;
    *p++ = 0;
    *p++ = 0;
    *p++ = 27 + ((info & CX_ECCINFO_PARITY_ODD) ? 1 : 0);
    uint8_t *seq = p;
    p += 2;
    p += der_int(p, r);
    p += der_int(p, s);
    seq[0] = 0x30;
    seq[1] = p - seq - 2;
    memcpy(p, from, 20);  // the EIP-712 message includes `from`, so the page can't recover without it
    p += 20;
    response_len = p - response;
    return true;
}

static void review_choice(bool confirm) {
    if (!confirm) {
        state = IDLE;
        nbgl_useCaseStatus("Rejected", false, ui_home);
    } else if (sign_request()) {
        state = APPROVED;
        nbgl_useCaseStatus("Signed\nTap your iPhone again", true, ui_home);
    } else {
        state = IDLE;
        nbgl_useCaseStatus("Signing failed", false, ui_home);
    }
}

static void start_review(const uint8_t *kh) {
    char amount[24];
    memcpy(request, kh, REQ_LEN);
    format_usdc(amount, sizeof(amount), read_u64_be(request, 20));
    size_t n = snprintf(review_text, sizeof(review_text), "%s USDC on Base Sepolia\nto 0x", amount);
    format_hex(request, 20, review_text + n, sizeof(review_text) - n);
    state = REVIEW;
    nbgl_useCaseChoice(&C_tapcash_64px, "Send payment?", review_text, "Approve", "Reject",
                       review_choice);
}

// One tap, no approval: an address is public. Shown on screen so the user can compare it with
// the page. Same layout as a payment response (minimal DER(1, 1) as the signature) so the page
// reuses its parser.
static void send_address(void) {
    static char text[64];
    uint8_t resp[13 + 20] = {0x01, 0, 0, 0, 0, 0x30, 0x06, 0x02, 0x01, 0x01, 0x02, 0x01, 0x01};
    if (!get_address(resp + 13)) {
        io_send_sw(SW_CRYPTO);
        return;
    }
    state = IDLE;  // replaces any pending review screen
    io_send_response_pointer(resp, sizeof(resp), SW_OK);
    size_t n = snprintf(text, sizeof(text), "Address sent\n0x");
    format_hex(resp + 13, 20, text + n, sizeof(text) - n);
    nbgl_useCaseStatus(text, true, ui_home);
}

// ISO 7816-4 command with data, short or extended Lc, optional Le.
// Returns the data length, or -1 if malformed. The SDK's apdu_parser rejects a trailing Le,
// which iOS sends.
static int parse_apdu(const uint8_t *buf, int len, const uint8_t **data) {
    int lc, hdr;
    if (len < 5) {
        return -1;
    }
    if (buf[4] != 0) {
        lc = buf[4];
        hdr = 5;
        if (len != hdr + lc && len != hdr + lc + 1) {
            return -1;
        }
    } else {
        if (len < 7) {
            return -1;
        }
        lc = (buf[5] << 8) | buf[6];
        hdr = 7;
        if (len != hdr + lc && len != hdr + lc + 2) {
            return -1;
        }
    }
    *data = buf + hdr;
    return lc;
}

static void handle_u2f_sign(uint8_t p1, const uint8_t *data, int lc) {
    if (lc < U2F_KH_LEN_OFFSET + 1 || lc != U2F_KH_LEN_OFFSET + 1 + data[U2F_KH_LEN_OFFSET]) {
        io_send_sw(SW_WRONG_LEN);
        return;
    }
    const uint8_t *kh = data + U2F_KH_LEN_OFFSET + 1;
    uint8_t kh_len = data[U2F_KH_LEN_OFFSET];
    bool is_addr = kh_len == sizeof(ADDR_REQ) && memcmp(kh, ADDR_REQ, sizeof(ADDR_REQ)) == 0;
    if (kh_len != REQ_LEN && !is_addr) {
        io_send_sw(SW_WRONG_DATA);  // "not our key handle"
        return;
    }

    // Check-only probe: "yes, this key handle is ours"
    if (p1 == P1_CHECK_ONLY) {
        io_send_sw(SW_NOT_SATISFIED);
        return;
    }

    if (is_addr) {
        send_address();
        return;
    }

    if (state == APPROVED && memcmp(kh, request, REQ_LEN) == 0) {
        state = IDLE;  // one approval = one signature
        io_send_response_pointer(response, response_len, SW_OK);
        nbgl_useCaseStatus("Sent to iPhone", true, ui_home);
        return;
    }

    // Checked first: the payment may have turned card or pocket mode off
    if (pocket_paid_valid && memcmp(kh, pocket_paid, REQ_LEN) == 0) {  // iOS retried a tap we already paid
        io_send_response_pointer(response, response_len, SW_OK);
        return;
    }

    // Card mode, then pocket mode: signed on this tap, without review. Not while a review is open.
    if ((card_mode || pocket_left) && state != REVIEW) {
        uint64_t value = read_u64_be(kh, 20);
        if (card_mode || (value <= USDC(PER_TAP_CAPS[per_tap_idx]) && value <= pocket_left)) {
            memcpy(request, kh, REQ_LEN);
            if (!sign_request()) {
                io_send_sw(SW_CRYPTO);
                return;
            }
            state = IDLE;  // an approved but uncollected review is dropped: its response was overwritten
            if (card_mode) {
                card_mode = false;  // one payment only; doesn't count against the pocket
            } else {
                pocket_left -= value;
                if (--pocket_taps_left == 0) {
                    pocket_left = 0;  // all payments used: pocket mode off
                }
            }
            memcpy(pocket_paid, kh, REQ_LEN);
            pocket_paid_valid = true;
            io_send_response_pointer(response, response_len, SW_OK);
            char amount[24];
            format_usdc(amount, sizeof(amount), value);
            size_t n = snprintf(review_text, sizeof(review_text), "Paid %s USDC\nto 0x", amount);
            format_hex(request, 20, review_text + n, sizeof(review_text) - n);  // not kh: the reply overwrote it
            nbgl_useCaseStatus(review_text, true, ui_home);
            return;
        }
    }

    io_send_sw(SW_NOT_SATISFIED);
    if (state != REVIEW) {
        start_review(kh);
    }
}

void app_main(void) {
    const uint8_t *data;

    io_init();
    per_tap_idx = 1;  // 5 USDC
    total_idx = 1;    // 20 USDC
    count_idx = 2;    // 10 payments
    ui_home();

    for (;;) {
        int len = io_recv_command();
        if (len < 0) {
            return;
        }
        uint8_t cla = G_io_apdu_buffer[0], ins = G_io_apdu_buffer[1], p1 = G_io_apdu_buffer[2];
        int lc = parse_apdu(G_io_apdu_buffer, len, &data);

        if (cla == CLA_TAPCASH && ins == INS_GET_ADDR) {
            // Silent, like other Ledger apps' get-public-key: the address is needed to fund it
            uint8_t addr[20];
            if (get_address(addr)) {
                io_send_response_pointer(addr, sizeof(addr), SW_OK);
            } else {
                io_send_sw(SW_CRYPTO);
            }
        } else if (cla == CLA_ISO && (ins == INS_SELECT || ins == INS_U2F_SIGN) && lc < 0) {
            io_send_sw(SW_WRONG_LEN);
        } else if (cla == CLA_ISO && ins == INS_SELECT) {
            // Readers probe other AIDs first (e.g. NDEF), only answer FIDO
            if (lc == sizeof(FIDO_AID) && memcmp(data, FIDO_AID, sizeof(FIDO_AID)) == 0) {
                io_send_response_pointer((const uint8_t *) "U2F_V2", 6, SW_OK);
            } else {
                io_send_sw(SW_FILE_NOT_FOUND);
            }
        } else if (cla == CLA_ISO && ins == INS_U2F_SIGN) {
            handle_u2f_sign(p1, data, lc);
        } else {
            // Includes CTAP2 (CLA 0x80): refusing it makes iOS fall back to U2F
            io_send_sw(SW_BAD_INS);
        }
    }
}
