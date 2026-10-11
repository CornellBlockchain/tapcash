package ledgercash.payee

import android.content.Context
import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbEndpoint
import android.hardware.usb.UsbInterface
import android.hardware.usb.UsbManager
import android.os.Handler
import android.os.Looper
import java.io.File
import java.math.BigDecimal
import java.security.SecureRandom
import ledgercash.Auth
import ledgercash.Eth
import ledgercash.Hex
import ledgercash.Payee
import ledgercash.Request

// Process-wide state shared by the activity and the HCE service.
object State {
    enum class Mode { PHONE, NANO }

    @Volatile var mode = Mode.PHONE
    @Volatile var nano: NanoBridge? = null
    @Volatile var nanoRequest: Request? = null     // last request the Nano answered, to check auths passing through
    var listener: ((String) -> Unit)? = null      // set by the activity, called on the main thread
    lateinit var payee: Payee
        private set
    val auths = mutableListOf<Auth>()             // guarded by synchronized(auths)
    private lateinit var store: File
    private val main = Handler(Looper.getMainLooper())

    @Synchronized
    fun init(ctx: Context) {
        if (::payee.isInitialized) return
        val keyFile = File(ctx.filesDir, "payee.key")
        if (!keyFile.exists()) keyFile.writeText(Hex.encode(ByteArray(32).also { SecureRandom().nextBytes(it) })) // ponytail: k >= n odds ~2^-128
        store = File(ctx.filesDir, "auths.jsonl")
        if (store.exists()) auths += store.readLines().mapNotNull { runCatching { Auth.fromJson(it) }.getOrNull() } // skip a corrupt line, never brick the app
        payee = Payee(Hex.decode(keyFile.readText())) { record(it, "Got authorization (unsettled IOU) for") }
    }

    fun record(a: Auth, verb: String) {
        synchronized(auths) {
            if (auths.any { it.nonce.contentEquals(a.nonce) && it.from.contentEquals(a.from) }) return
            auths += a
            store.appendText(a.toJson() + "\n")
        }
        post("$verb ${usdc(a.value)} USDC from ${Hex.p(a.from)}")
    }

    fun post(msg: String) = main.post { listener?.invoke(msg) }

    fun usdc(units: Long): String = BigDecimal.valueOf(units, 6).stripTrailingZeros().toPlainString()

    // Nano mode, before the tap: SET_CONFIG then SET_REQUEST over USB; each needs Approve on the Nano. Blocking: call off the UI thread.
    fun armNano(nano: NanoBridge, chainId: Long, token: ByteArray, value: Long, label: String) {
        fun send(ins: Int, data: ByteArray, what: String) {
            val r = nano.exchange(byteArrayOf(ledgercash.Protocol.CLA.toByte(), ins.toByte(), 0, 0, data.size.toByte()) + data)
            check(r.contentEquals(ledgercash.Protocol.SW_OK)) { "$what refused: SW ${Hex.encode(r.takeLast(2).toByteArray())}" }
        }
        send(ledgercash.Protocol.INS_SET_CONFIG, ledgercash.Bytes.u64(chainId) + token, "SET_CONFIG")
        send(ledgercash.Protocol.INS_SET_REQUEST, ledgercash.Bytes.u64(value) + label.toByteArray(Charsets.US_ASCII), "SET_REQUEST")
    }

    // Nano mode: the Flex's auth only passes through us; keep a copy if it checks out against the Nano's request.
    fun observeNano(cmd: ByteArray, resp: ByteArray) {
        val ok = resp.size >= 2 && resp[resp.size - 2] == 0x90.toByte() && resp[resp.size - 1] == 0.toByte()
        if (!ok || cmd.size < 5) return
        when (cmd[1].toInt() and 0xff) {
            ledgercash.Protocol.INS_GET_REQUEST -> runCatching { nanoRequest = Request.decode(resp.copyOf(resp.size - 2)) }
            ledgercash.Protocol.INS_PUT_AUTH -> {
                val req = nanoRequest ?: return
                val a = runCatching { Auth.decode(cmd.copyOfRange(5, cmd.size).copyOf(ledgercash.Protocol.AUTH_LEN)) }.getOrNull() ?: return
                if (resp[0] == ledgercash.Protocol.ACK_OK && Eth.recover(a.digest(req.chainId, req.token), a.sig())?.contentEquals(a.from) == true) {
                    record(a, "Nano got authorization (unsettled IOU) for")
                }
            }
        }
    }
}

// Ledger Nano over USB OTG, HID interface, Ledger HID framing (see core HidFraming).
class NanoBridge private constructor(
    private val conn: UsbDeviceConnection, private val iface: UsbInterface,
    private val inEp: UsbEndpoint, private val outEp: UsbEndpoint, val name: String,
) {
    @Synchronized
    fun exchange(apdu: ByteArray): ByteArray {
        for (r in ledgercash.HidFraming.wrap(apdu)) {
            check(conn.bulkTransfer(outEp, r, r.size, 2000) == r.size) { "USB write failed" }
        }
        return ledgercash.HidFraming.unwrap {
            val b = ByteArray(ledgercash.HidFraming.REPORT)
            val n = conn.bulkTransfer(inEp, b, b.size, READ_TIMEOUT_MS)
            check(n > 0) { "USB read timed out (is the ledger-cash app open on the Nano?)" }
            b.copyOf(n)
        }
    }

    fun close() {
        conn.releaseInterface(iface)
        conn.close()
    }

    companion object {
        const val LEDGER_VID = 0x2c97
        const val READ_TIMEOUT_MS = 60_000 // calibration knob: SET_CONFIG/SET_REQUEST wait for a button press on the Nano

        fun find(usb: UsbManager): UsbDevice? = usb.deviceList.values.firstOrNull { it.vendorId == LEDGER_VID }

        fun open(usb: UsbManager, dev: UsbDevice): NanoBridge {
            // Android cannot read the HID usage page (0xffa0); the APDU interface is the first HID one (interface 0 on Ledger devices).
            val iface = (0 until dev.interfaceCount).map { dev.getInterface(it) }
                .first { it.interfaceClass == UsbConstants.USB_CLASS_HID }
            val eps = (0 until iface.endpointCount).map { iface.getEndpoint(it) }
            val inEp = eps.first { it.direction == UsbConstants.USB_DIR_IN }
            val outEp = eps.first { it.direction == UsbConstants.USB_DIR_OUT }
            val conn = usb.openDevice(dev) ?: error("openDevice failed (USB permission?)")
            if (!conn.claimInterface(iface, true)) { conn.close(); error("claimInterface failed") }
            return NanoBridge(conn, iface, inEp, outEp, dev.productName ?: "Ledger %04x".format(dev.productId))
        }
    }
}
