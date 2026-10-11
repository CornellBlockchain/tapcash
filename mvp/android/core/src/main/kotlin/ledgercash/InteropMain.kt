package ledgercash

// Card emulator for mvp/ledger-cash/interop/android_payee_tap.py: the phone payee's exact code path (PayeeService in
// PHONE mode = Payee.handle) on stdin/stdout. One hex APDU per line in, one hex reply (data + SW) per line out.
// args: amount(base units) label chainId token(hex) reqNonce(hex) [tamper]
// stdout line 1: "ready <payee address>". stderr: "auth <json>" per verified auth (Auth.toJson, what Share exports).
// tamper: rewrite payTo in the GET_REQUEST reply after Payee.handle (a rogue relay redirecting the payment);
// the payer must refuse it with B001 because payeeSig no longer recovers to payTo.
object InteropMain {
    // anvil test key 2 (public): 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC
    val KEY = Hex.decode("5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a")

    fun card(args: List<String>, onAuth: (Auth) -> Unit = {}): Pair<Payee, (ByteArray) -> ByteArray> {
        val p = Payee(KEY, onAuth)
        p.arm(args[2].toLong(), Hex.decode(args[3]), args[0].toLong(), args[1], -1L, args[4].toLong(16).toInt())
        val tamper = args.getOrNull(5) == "tamper"
        return p to { apdu ->
            val r = p.handle(apdu)
            if (tamper && r.size == Protocol.REQ_LEN + 2) r.copyOf().also { it[47] = (it[47].toInt() xor 1).toByte() } else r
        }
    }

    @JvmStatic
    fun main(args: Array<String>) {
        val (p, x) = card(args.toList()) { System.err.println("auth " + it.toJson()); System.err.flush() }
        println("ready " + Hex.p(p.address))
        System.out.flush()
        while (true) {
            val line = readLine()?.trim() ?: break
            if (line.isEmpty()) continue
            println(Hex.encode(x(Hex.decode(line))))
            System.out.flush()
        }
    }
}
