#ifdef HAVE_NFC_READER
#include "os.h"
#include "os_io_legacy.h"

// ponytail: compile/link gate only. Proves the app-level reader API is reachable from a standard C app.
static const uint8_t SELECT_NDEF_APP[] = {0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01, 0x00};

static void on_resp(bool error, bool timeout, uint8_t *data, size_t len) {
    PRINTF("nfc resp err=%d timeout=%d len=%d %.*H\n", error, timeout, (int) len, (int) len, data);
}

static void on_evt(enum nfc_event event, struct card_info *info) {
    PRINTF("nfc evt=%d tech=%d uid=%.*H\n", event, info->tech, (int) info->nfcid_len, info->nfcid);
    if (event == CARD_DETECTED) {
        io_nfc_reader_send(SELECT_NDEF_APP, sizeof(SELECT_NDEF_APP), on_resp, 2000);
    }
}

void nfc_probe_start(void) {
    io_nfc_reader_start(on_evt);
}
#endif
