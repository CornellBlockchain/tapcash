package ledgercash

// ALL ledger-cash APDU constants and wire layouts live in this file. Re-sync with mvp/ledger-cash/app/src/cash.c when it changes.
// Synced against cash.c's attestation build (Flex app.sha256 69873224...2acdb; see NOTES.md, "Sync with the C app").
// Sync check: python -u mvp/ledger-cash/interop/android_payee_tap.py (Speculos Flex payer vs Payee.handle; re-records InteropVectors.kt).
object Protocol {
    const val CLA = 0xE0
    val AID = Hex.decode("F04C45444745524341534801")      // F0 "LEDGERCASH" 01 (cash.c answers this SELECT 9000, else 6A82; its reader sends it first)
    const val INS_SET_REQUEST = 0x10   // value u64 || label (<=24 ASCII); approved on the device screen
    const val INS_GET_REQUEST = 0x11
    const val INS_SET_CONFIG = 0x12    // chainId u64 || token 20; approved on the device screen
    const val INS_PUT_AUTH = 0x23
    const val INS_PUT_ATTEST = 0x25    // v1, not implemented by the phone payee: answers 6D00, payer still ends PAID
    // Payer-side / host-only INS (not used by this app, listed so the set matches cash.c):
    const val INS_LOAD_CASH = 0x20     // value u64; approved on the device screen
    const val INS_GET_BALANCE = 0x21   // -> balance u64 || pay_counter u32 || address 20
    const val INS_PAY = 0x22
    const val INS_GET_AUTHS = 0x24     // P1 = index
    const val INS_TAP_TO_PAY = 0x30
    const val INS_TAP_STATUS = 0x31

    // request = chainId(u64) || token(20) || payTo(20) || value(u64) || validBefore(u64) || reqNonce(u32) || label(24) || payeeSig(65)
    // payeeSig = sign(EIP-191 personal_sign of the 32-byte keccak256(body)), prefix 0x19 "Ethereum Signed Message:" LF "32".
    const val LABEL_LEN = 24           // printable ASCII 0x20..0x7E, zero padded at the tail only (the payer rejects anything else)
    const val REQ_BODY_LEN = 8 + 20 + 20 + 8 + 8 + 4 + LABEL_LEN   // 92
    const val REQ_LEN = REQ_BODY_LEN + 65                           // 157
    // PUT_AUTH data = from(20)||to(20)||value(u64)||validAfter(u64)||validBefore(u64)||nonce(32)||v(1)||r(32)||s(32)
    // Payee checks: to == payTo, value == request value, validAfter == 0, validBefore == request validBefore,
    // nonce == keccak256(request body), EIP-712 signer == from. A request is paid once, then disarmed.
    const val AUTH_LEN = 20 + 20 + 8 + 8 + 8 + 32 + 1 + 32 + 32      // 161
    const val ACK_OK: Byte = 0x01
    // reply = 0x01 || receipt(65); receipt = sign(EIP-191 personal_sign of keccak256(161-byte auth)).
    const val RECEIPT_EIP191 = true
    // Signatures are r||s||v with v in {27,28} (USDC.sol and cash.c's ecrecover only accept 27/28).

    val SW_OK = Bytes.u16(0x9000)
    val SW_WRONG_LENGTH = Bytes.u16(0x6700)
    val SW_BAD_P1P2 = Bytes.u16(0x6A86)
    val SW_FILE_NOT_FOUND = Bytes.u16(0x6A82)   // SELECT of another AID (HCE only)
    val SW_INS_NOT_SUPPORTED = Bytes.u16(0x6D00)
    val SW_CLA_NOT_SUPPORTED = Bytes.u16(0x6E00)
    val SW_REJECTED = Bytes.u16(0x6985)       // user pressed Reject on the device
    val SW_BAD_DATA = Bytes.u16(0x6A80)
    val SW_NOT_FOUND = Bytes.u16(0x6A88)      // GET_AUTHS index out of range
    val SW_CRYPTO = Bytes.u16(0xB0FF)
    val SW_BAD_PAYEE_SIG = Bytes.u16(0xB001)  // payer-side SWs (cash.c), shown so a trace can be read against one file
    val SW_CONFIG = Bytes.u16(0xB002)         // request chainId/token != payer SET_CONFIG, or not configured
    val SW_INSUFFICIENT = Bytes.u16(0xB003)   // request value > payer's loaded cash
    val SW_REPLAY = Bytes.u16(0xB004)         // payer already paid this request
    val SW_BAD_AUTH = Bytes.u16(0xB005)
    val SW_NO_REQUEST = Bytes.u16(0xB006)
    val SW_BUSY = Bytes.u16(0xB007)           // a screen is up on the device
    val SW_CARD_GONE = Bytes.u16(0xB008)      // tap: card left the field
    val SW_NO_ANSWER = Bytes.u16(0xB009)      // tap: payee did not answer in time
    val SW_UNKNOWN = Bytes.u16(0x6F00)          // bridge: USB failure (not a cash.c code)

    fun labelOk(l: ByteArray) = l.size <= LABEL_LEN && l.all { it in 0x20..0x7E }

    fun isSelect(apdu: ByteArray) =
        apdu.size >= 5 && apdu[0] == 0.toByte() && apdu[1] == 0xA4.toByte() && apdu[2] == 0x04.toByte()

    fun isSelectOurs(apdu: ByteArray) = isSelect(apdu) && apdu.size >= 5 + AID.size &&
        (apdu[4].toInt() and 0xff) == AID.size && apdu.copyOfRange(5, 5 + AID.size).contentEquals(AID)
}

class Request(
    val chainId: Long, val token: ByteArray, val payTo: ByteArray, val value: Long,
    val validBefore: Long, val reqNonce: Int, val label: String, val sig: ByteArray = ByteArray(65),
) {
    fun body(): ByteArray {
        val l = label.toByteArray(Charsets.US_ASCII).copyOf(Protocol.LABEL_LEN)
        return Bytes.u64(chainId) + token + payTo + Bytes.u64(value) + Bytes.u64(validBefore) + Bytes.u32(reqNonce) + l
    }

    fun encode() = body() + sig
    fun nonce() = Eth.keccak(body())              // the EIP-3009 nonce the payer must use
    fun hash() = Eth.eip191(Eth.keccak(body()))  // what payeeSig signs
    fun signer() = Eth.recover(hash(), sig)
    fun signed(priv: ByteArray) = Request(chainId, token, payTo, value, validBefore, reqNonce, label, Eth.sign(hash(), priv))

    companion object {
        fun decode(b: ByteArray): Request {
            require(b.size == Protocol.REQ_LEN) { "request must be ${Protocol.REQ_LEN} bytes, got ${b.size}" }
            val raw = b.copyOfRange(68, 92)
            val label = raw.copyOf(raw.indexOf(0).let { if (it < 0) raw.size else it })
            return Request(Bytes.u64(b, 0), b.copyOfRange(8, 28), b.copyOfRange(28, 48), Bytes.u64(b, 48), Bytes.u64(b, 56),
                Bytes.u32(b, 64), String(label, Charsets.US_ASCII), b.copyOfRange(92, 157))
        }
    }
}

class Auth(
    val from: ByteArray, val to: ByteArray, val value: Long, val validAfter: Long, val validBefore: Long,
    val nonce: ByteArray, val v: Int, val r: ByteArray, val s: ByteArray,
) {
    fun encode() = from + to + Bytes.u64(value) + Bytes.u64(validAfter) + Bytes.u64(validBefore) + nonce + byteArrayOf(v.toByte()) + r + s
    fun sig() = r + s + byteArrayOf(v.toByte())
    fun digest(chainId: Long, token: ByteArray) =
        Eth.eip712TransferWithAuthorization(chainId, token, from, to, value, validAfter, validBefore, nonce)

    // Field names and formats that mvp/ledger-cash/settle/settle.mjs reads.
    fun toJson() = "{\"from\":\"${Hex.p(from)}\",\"to\":\"${Hex.p(to)}\",\"value\":\"${u(value)}\"," +
        "\"validAfter\":\"${u(validAfter)}\",\"validBefore\":\"${u(validBefore)}\",\"nonce\":\"${Hex.p(nonce)}\"," +
        "\"v\":\"$v\",\"r\":\"${Hex.p(r)}\",\"s\":\"${Hex.p(s)}\"}"

    companion object {
        private fun u(x: Long) = java.lang.Long.toUnsignedString(x)
        private fun pu(s: String) = java.lang.Long.parseUnsignedLong(s)
        private val FIELD = Regex("\"(\\w+)\":\"([^\"]*)\"")

        fun decode(b: ByteArray): Auth {
            require(b.size == Protocol.AUTH_LEN) { "auth must be ${Protocol.AUTH_LEN} bytes, got ${b.size}" }
            return Auth(b.copyOfRange(0, 20), b.copyOfRange(20, 40), Bytes.u64(b, 40), Bytes.u64(b, 48), Bytes.u64(b, 56),
                b.copyOfRange(64, 96), b[96].toInt() and 0xff, b.copyOfRange(97, 129), b.copyOfRange(129, 161))
        }

        fun fromJson(j: String): Auth {
            val m = FIELD.findAll(j).associate { it.groupValues[1] to it.groupValues[2] }
            fun f(k: String) = m[k] ?: error("missing $k")
            return Auth(Hex.decode(f("from")), Hex.decode(f("to")), pu(f("value")), pu(f("validAfter")), pu(f("validBefore")),
                Hex.decode(f("nonce")), f("v").toInt(), Hex.decode(f("r")), Hex.decode(f("s")))
        }
    }
}

object Bytes {
    fun u64(x: Long) = ByteArray(8) { (x ushr (56 - 8 * it)).toByte() }
    fun u32(x: Int) = ByteArray(4) { (x ushr (24 - 8 * it)).toByte() }
    fun u16(x: Int) = byteArrayOf((x ushr 8).toByte(), x.toByte())
    fun u64(b: ByteArray, o: Int) = (0 until 8).fold(0L) { acc, i -> (acc shl 8) or (b[o + i].toLong() and 0xff) }
    fun u32(b: ByteArray, o: Int) = (0 until 4).fold(0) { acc, i -> (acc shl 8) or (b[o + i].toInt() and 0xff) }
    fun u16(b: ByteArray, o: Int) = ((b[o].toInt() and 0xff) shl 8) or (b[o + 1].toInt() and 0xff)
}

object Hex {
    fun encode(b: ByteArray) = b.joinToString("") { "%02x".format(it) }
    fun p(b: ByteArray) = "0x" + encode(b)
    fun decode(s: String): ByteArray {
        val h = s.trim().removePrefix("0x").removePrefix("0X")
        require(h.length % 2 == 0) { "odd hex length" }
        return ByteArray(h.length / 2) { h.substring(2 * it, 2 * it + 2).toInt(16).toByte() }
    }
}
