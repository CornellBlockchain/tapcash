package ledgercash

// Phone-as-payee APDU handler, mirroring the payee half of mvp/ledger-cash/app/src/cash.c (same checks, same SWs).
// Pure JVM so the whole money path runs in unit tests. onAuth is called once per verified auth (persist it there).
class Payee(private val priv: ByteArray, private val onAuth: (Auth) -> Unit = {}) {
    val address: ByteArray = Eth.address(priv)

    @Volatile var request: Request? = null
        private set

    fun arm(chainId: Long, token: ByteArray, value: Long, label: String, validBefore: Long, reqNonce: Int): Request {
        require(value > 0) { "amount must be > 0" }
        require(Protocol.labelOk(label.toByteArray(Charsets.US_ASCII)) && label.all { it.code in 0x20..0x7E }) {
            "label must be at most ${Protocol.LABEL_LEN} plain ASCII characters"
        }
        return Request(chainId, token, address, value, validBefore, reqNonce, label).signed(priv).also { request = it }
    }

    @Synchronized
    fun handle(apdu: ByteArray): ByteArray {
        // Same checks in the same order as cash.c over NFC (checked by mvp/ledger-cash/interop/android_payee_tap.py):
        // SDK apdu_parser (4 bytes, or exactly 5 + Lc; no Le), SELECT, CLA, NFC allowlist, then P1/P2.
        if (apdu.size < 4 || apdu.size > 4 && apdu.size != 5 + (apdu[4].toInt() and 0xff)) return Protocol.SW_WRONG_LENGTH
        if (apdu[0].toInt() == 0 && apdu[1] == 0xA4.toByte()) {
            return if (Protocol.isSelectOurs(apdu)) Protocol.SW_OK else Protocol.SW_FILE_NOT_FOUND
        }
        if ((apdu[0].toInt() and 0xff) != Protocol.CLA) return Protocol.SW_CLA_NOT_SUPPORTED
        val ins = apdu[1].toInt() and 0xff
        if (ins != Protocol.INS_GET_REQUEST && ins != Protocol.INS_PUT_AUTH) return Protocol.SW_INS_NOT_SUPPORTED
        if (apdu[2].toInt() != 0 || apdu[3].toInt() != 0) return Protocol.SW_BAD_P1P2
        val data = if (apdu.size > 5) apdu.copyOfRange(5, apdu.size) else ByteArray(0)
        val req = request
        return when {
            ins == Protocol.INS_GET_REQUEST -> req?.encode()?.plus(Protocol.SW_OK) ?: Protocol.SW_NO_REQUEST
            data.size != Protocol.AUTH_LEN -> Protocol.SW_WRONG_LENGTH
            req == null -> Protocol.SW_NO_REQUEST
            else -> putAuth(req, Auth.decode(data))
        }
    }

    private fun putAuth(req: Request, a: Auth): ByteArray {
        val ok = a.to.contentEquals(address) && a.value == req.value && a.validAfter == 0L && a.validBefore == req.validBefore &&
            a.nonce.contentEquals(req.nonce()) && Eth.recover(a.digest(req.chainId, req.token), a.sig())?.contentEquals(a.from) == true
        if (!ok) return Protocol.SW_BAD_AUTH
        request = null // a request is paid once (as in cash.c)
        runCatching { onAuth(a) } // a storage failure must not cost the payer its receipt (auth is already debited)
        val h = Eth.keccak(a.encode())
        val receipt = Eth.sign(if (Protocol.RECEIPT_EIP191) Eth.eip191(h) else h, priv)
        return byteArrayOf(Protocol.ACK_OK) + receipt + Protocol.SW_OK
    }
}
