package ledgercash

import org.junit.Assert.assertEquals
import org.junit.Test

// Replays InteropVectors (recorded from a Speculos Flex payer running cash.c, by
// mvp/ledger-cash/interop/android_payee_tap.py) through InteropMain.card, the PayeeService PHONE-mode code path.
// Every reply must match byte for byte: request, receipt (RFC 6979, deterministic) and every status word.
class InteropTest {
    @Test fun replaysRecordedTap() {
        assertEquals(3, InteropVectors.RUNS.size)
        for ((args, trace) in InteropVectors.RUNS) {
            val (_, card) = InteropMain.card(args)
            trace.forEachIndexed { i, (apdu, reply) -> assertEquals("$args #$i $apdu", reply, Hex.encode(card(Hex.decode(apdu)))) }
        }
    }
}
