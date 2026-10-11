package ledgercash.payee

import android.app.Activity
import android.app.PendingIntent
import android.content.Intent
import android.hardware.usb.UsbManager
import android.nfc.NfcAdapter
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.math.BigDecimal
import java.security.SecureRandom
import ledgercash.Hex

// One screen, views built in code (no AndroidX).
class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var list: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        State.init(applicationContext)
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(40, 40, 40, 40) }
        fun text(s: String, size: Float = 15f) = TextView(this).apply { text = s; textSize = size; setTextIsSelectable(true) }.also { col.addView(it) }
        fun field(hint: String, value: String, type: Int = InputType.TYPE_CLASS_TEXT): EditText {
            text(hint, 12f)
            return EditText(this).apply { this.hint = hint; setText(value); inputType = type }.also { col.addView(it) }
        }
        fun button(label: String, onClick: () -> Unit) = Button(this).apply { text = label; setOnClickListener { onClick() } }.also { col.addView(it) }

        text("Ledger Cash Payee", 22f)
        text("Phone payee address:\n${Hex.p(State.payee.address)}", 13f)
        val modes = RadioGroup(this).apply {
            addView(RadioButton(context).apply { id = View.generateViewId(); text = "Phone payee (this phone gets paid)"; tag = State.Mode.PHONE })
            addView(RadioButton(context).apply { id = View.generateViewId(); text = "Nano bridge (Nano S Plus on USB OTG gets paid)"; tag = State.Mode.NANO })
            check(getChildAt(State.mode.ordinal).id)
            setOnCheckedChangeListener { g, id -> State.mode = g.findViewById<View>(id).tag as State.Mode; refresh() }
        }
        col.addView(modes)

        val chainId = field("chainId", "31337", InputType.TYPE_CLASS_NUMBER)
        val token = field("USDC token address", "0x5FbDB2315678afecb367f032d93F642f64180aa3")
        val amount = field("Amount (USDC)", "1.00", InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL)
        val label = field("Label (24 bytes max)", "coffee")
        fun tokenBytes() = Hex.decode(token.text.toString()).also { require(it.size == 20) { "token must be 20 bytes" } }
        fun units() = BigDecimal(amount.text.toString()).movePointRight(6).longValueExact()
        button("Arm payment request (phone payee)") {
            try {
                val r = State.payee.arm(chainId.text.toString().toLong(), tokenBytes(), units(), label.text.toString(),
                    -1L /* u64 max: never expires, as cash.c (settled later, offline) */, SecureRandom().nextInt())
                State.mode = State.Mode.PHONE
                modes.check(modes.getChildAt(0).id)
                say("Armed: ${State.usdc(r.value)} USDC \"${r.label}\". Hold the Flex to the phone.")
            } catch (e: Exception) {
                say("Not armed: ${e.message}")
            }
        }
        button("Connect Nano (USB OTG)") { connectNano() }
        button("Arm request on Nano (approve twice on the Nano)") {
            val nano = State.nano ?: return@button say("Connect the Nano first.")
            try {
                val c = chainId.text.toString().toLong()
                val t = tokenBytes()
                val v = units()
                val l = label.text.toString()
                say("Approve \"Set USDC network\" then \"Request\" on the Nano...")
                Thread {
                    val msg = runCatching { State.armNano(nano, c, t, v, l) }
                        .fold({ "Nano armed. Hold the Flex to the phone." }, { "Nano arm failed: ${it.message}" })
                    runOnUiThread { say(msg) }
                }.start()
            } catch (e: Exception) {
                say("Not armed: ${e.message}")
            }
        }
        status = text("", 16f)
        button("Share received auths (JSON for settle.mjs)") {
            val json = synchronized(State.auths) { State.auths.joinToString(",\n", "[\n", "\n]") { it.toJson() } }
            startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, json), "Share auths"))
        }
        list = text("", 12f)

        setContentView(ScrollView(this).apply { fitsSystemWindows = true; addView(col) })
        refresh()
        handleUsbIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleUsbIntent(intent)
    }

    override fun onResume() {
        super.onResume()
        State.listener = { msg -> say(msg); Toast.makeText(this, msg, Toast.LENGTH_LONG).show(); refresh() }
    }

    override fun onPause() {
        State.listener = null
        super.onPause()
    }

    private fun handleUsbIntent(i: Intent?) {
        if (i?.action == UsbManager.ACTION_USB_DEVICE_ATTACHED) connectNano()
    }

    private fun connectNano() {
        val usb = getSystemService(UsbManager::class.java)
        val dev = NanoBridge.find(usb) ?: return say("No Ledger on USB. Use an OTG adapter, unlock the Nano, open the ledger-cash app.")
        if (!usb.hasPermission(dev)) {
            val flags = if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0
            usb.requestPermission(dev, PendingIntent.getBroadcast(this, 0, Intent("ledgercash.USB_PERMISSION").setPackage(packageName), flags))
            return say("Allow USB access, then tap Connect Nano again.")
        }
        try {
            State.nano?.close()
            State.nano = NanoBridge.open(usb, dev)
            State.mode = State.Mode.NANO
            refresh()
            say("Nano connected: ${State.nano?.name}. Mode: Nano bridge.")
        } catch (e: Exception) {
            State.nano = null
            say("Nano connect failed: ${e.message}")
        }
    }

    private fun say(s: String) { status.text = s }

    private fun refresh() {
        val nfc = NfcAdapter.getDefaultAdapter(this)
        val nfcState = when { nfc == null -> "NO NFC on this phone"; !nfc.isEnabled -> "NFC is OFF (turn it on in Settings)"; else -> "NFC on" }
        val auths = synchronized(State.auths) { State.auths.toList() }
        list.text = "Mode: ${State.mode}   $nfcState   Nano: ${State.nano?.name ?: "none"}\n\n" +
            "Received auths (${auths.size}):\n" + auths.reversed().joinToString("\n") {
                "${State.usdc(it.value)} USDC from ${Hex.p(it.from)}\n  to ${Hex.p(it.to)} nonce ${Hex.p(it.nonce).take(18)}..."
            }
    }
}
