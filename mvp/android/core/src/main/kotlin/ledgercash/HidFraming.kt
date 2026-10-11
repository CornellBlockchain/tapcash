package ledgercash

// Ledger USB HID framing (ledger-secure-sdk protocol/src/ledger_protocol.c, TAG_APDU path):
// each 64-byte report = channel(2 BE) || tag 0x05 || seq(2 BE) || payload, zero padded;
// the payload stream is apduLen(2 BE) || apdu, so report 0 carries 57 APDU bytes and the rest 59 each.
// The device answers on the same channel with the same framing. No HID report-ID byte (that is a node-hid/Windows thing).
object HidFraming {
    const val CHANNEL = 0x0101
    const val TAG_APDU = 0x05
    const val REPORT = 64
    private const val HEADER = 5

    fun wrap(apdu: ByteArray, channel: Int = CHANNEL): List<ByteArray> {
        val stream = Bytes.u16(apdu.size) + apdu
        return stream.toList().chunked(REPORT - HEADER).mapIndexed { seq, chunk ->
            (Bytes.u16(channel) + byteArrayOf(TAG_APDU.toByte()) + Bytes.u16(seq) + chunk.toByteArray()).copyOf(REPORT)
        }
    }

    /** Reassembles one APDU response from reports pulled by [next]. Throws on a framing mismatch. */
    fun unwrap(channel: Int = CHANNEL, next: () -> ByteArray): ByteArray {
        var out = ByteArray(0)
        var len = -1
        var seq = 0
        while (len < 0 || out.size < len) {
            val r = next()
            require(r.size >= HEADER + 2) { "short report (${r.size})" }
            require(Bytes.u16(r, 0) == channel && (r[2].toInt() and 0xff) == TAG_APDU) { "bad channel/tag ${Hex.encode(r.copyOf(3))}" }
            require(Bytes.u16(r, 3) == seq) { "bad sequence ${Bytes.u16(r, 3)}, expected $seq" }
            var body = r.copyOfRange(HEADER, r.size)
            if (seq == 0) { len = Bytes.u16(body, 0); body = body.copyOfRange(2, body.size) }
            out += body.copyOf(minOf(body.size, len - out.size))
            seq++
        }
        return out
    }
}
