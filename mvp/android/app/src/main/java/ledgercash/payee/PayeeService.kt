package ledgercash.payee

import android.nfc.cardemulation.HostApduService
import android.os.Bundle
import java.util.concurrent.Executors
import ledgercash.Protocol

// HCE endpoint for AID F04C45444745524341534801 (res/xml/apduservice.xml). The Flex is the NFC reader.
class PayeeService : HostApduService() {
    private val usb = Executors.newSingleThreadExecutor()

    override fun onCreate() {
        super.onCreate()
        State.init(applicationContext)
    }

    override fun processCommandApdu(apdu: ByteArray, extras: Bundle?): ByteArray? {
        if (State.mode == State.Mode.PHONE) return State.payee.handle(apdu) // a few ms of secp256k1, fine inline
        // NANO: answer SELECT here (a Ledger app rejects CLA 00), forward E0 APDUs over USB, reply asynchronously.
        if (Protocol.isSelect(apdu)) return if (Protocol.isSelectOurs(apdu)) Protocol.SW_OK else Protocol.SW_FILE_NOT_FOUND
        val nano = State.nano ?: return Protocol.SW_NO_REQUEST.also { State.post("Flex tapped but no Nano connected") }
        usb.execute {
            val resp = try {
                nano.exchange(apdu).also { State.observeNano(apdu, it) }
            } catch (e: Exception) {
                State.post("Nano error: ${e.message}")
                Protocol.SW_UNKNOWN
            }
            sendResponseApdu(resp)
        }
        return null
    }

    override fun onDeactivated(reason: Int) {}

    override fun onDestroy() {
        usb.shutdown()
        super.onDestroy()
    }
}
