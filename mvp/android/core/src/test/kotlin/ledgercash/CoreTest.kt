package ledgercash

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

// Vectors from tools/vector.mjs (viem 2.57.4, see NOTES.md). Keys are anvil's public test keys.
class CoreTest {
    private val payerKey = Hex.decode("ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
    private val payeeKey = Hex.decode("59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d")
    private val payer = Hex.decode("f39Fd6e51aad88F6F4ce6aB8827279cffFb92266")
    private val payee = Hex.decode("70997970C51812dc3A010C7d01b50e0d17dc79C8")
    private val token = Hex.decode("5FbDB2315678afecb367f032d93F642f64180aa3")
    private val body92 = ByteArray(92) { it.toByte() }

    @Test fun sizes() {
        assertEquals(92, Protocol.REQ_BODY_LEN); assertEquals(157, Protocol.REQ_LEN); assertEquals(161, Protocol.AUTH_LEN)
    }

    @Test fun addressesMatchViem() {
        assertArrayEquals(payer, Eth.address(payerKey)); assertArrayEquals(payee, Eth.address(payeeKey))
    }

    @Test fun requestSigMatchesViem() { // cash.c: personal_sign over keccak256(body)
        val h = Eth.eip191(Eth.keccak(body92))
        assertEquals("93d71f19eff89addd970eb0d82e1abcfb004836e87b4aaca2444a2df70083deb", Hex.encode(h))
        val sig = Eth.sign(h, payeeKey)
        assertEquals("7c1ca790ac429786ba62ba60771cfcf0d09194c559b0f548594138fcfdc067d875de3445d1dcf106f15b8c2cef5a91c19d8be0b35afbd26a89c327b99c1543361c", Hex.encode(sig))
        assertArrayEquals(payee, Eth.recover(h, sig))
    }

    @Test fun eip712MatchesViem() {
        val nonce = Eth.keccak(body92)
        assertEquals("7fea2a75041518f5fe548a415dd378a67dee9cf8e2f191e7828404abcaba8ca5", Hex.encode(nonce))
        val d = Eth.eip712TransferWithAuthorization(31337, token, payer, payee, 1234567, 0, 2000000000, nonce)
        assertEquals("a9457d92cd57d129e61830d4578fd8f1e889018566323d0161ca7747e64abf55", Hex.encode(d))
        assertEquals("7fd3d68b852d28e545730645c2b2f5f1a7e34cc6d00e442215c4f1ed149d80e272ffd7df6c06e23a297b01dc11a2624617e456fadc3639bee0508593405520f81c", Hex.encode(Eth.sign(d, payerKey)))
    }

    @Test fun requestRoundtrip() {
        val r = Request(31337, token, payee, 2_500_000, 2000000000, 0x01020304, "coffee").signed(payeeKey)
        val enc = r.encode()
        assertEquals(157, enc.size)
        val d = Request.decode(enc)
        assertEquals(31337L, d.chainId); assertEquals(2_500_000L, d.value); assertEquals(0x01020304, d.reqNonce); assertEquals("coffee", d.label)
        assertArrayEquals(enc, d.encode())
        assertArrayEquals(payee, d.signer())
        enc[50] = (enc[50] + 1).toByte()                       // tamper value
        assertEquals(false, Request.decode(enc).signer()?.contentEquals(payee) ?: false)
    }

    @Test fun payeeFlow() {
        val stored = mutableListOf<Auth>()
        val p = Payee(payeeKey) { stored += it }
        val getReq = Hex.decode("E011000000")
        val selectOurs = byteArrayOf(0, 0xA4.toByte(), 4, 0, 12) + Protocol.AID // what cash.c's reader sends (no Le)
        assertArrayEquals(Protocol.SW_OK, p.handle(selectOurs))
        assertArrayEquals(Protocol.SW_WRONG_LENGTH, p.handle(selectOurs + byteArrayOf(0))) // cash.c's apdu_parser: no Le
        assertArrayEquals(Protocol.SW_FILE_NOT_FOUND, p.handle(Hex.decode("00A4040007D2760000850101")))
        assertArrayEquals(Protocol.SW_NO_REQUEST, p.handle(getReq))
        assertNull(runCatching { p.arm(31337, token, 1_000_000, "café", 2000000000, 7) }.getOrNull()) // non-ASCII label refused

        p.arm(31337, token, 1_000_000, "tea", -1L, 7) // what the app arms: validBefore = u64 max, as cash.c
        val resp = p.handle(getReq)
        assertArrayEquals(Protocol.SW_OK, resp.copyOfRange(157, 159))
        val req = Request.decode(resp.copyOf(157))
        assertArrayEquals(payee, req.signer())
        assertEquals("tea", req.label)

        // what the Flex does (cash.c pay_sign): validAfter 0, validBefore and value from the request, nonce = keccak(body)
        fun auth(value: Long = req.value, validAfter: Long = 0): ByteArray {
            val a = Auth(payer, req.payTo, value, validAfter, req.validBefore, req.nonce(), 0, ByteArray(32), ByteArray(32))
            val s = Eth.sign(a.digest(req.chainId, req.token), payerKey)
            return Auth(a.from, a.to, a.value, a.validAfter, a.validBefore, a.nonce, s[64].toInt(), s.copyOf(32), s.copyOfRange(32, 64)).encode()
        }
        fun put(data: ByteArray) = p.handle(byteArrayOf(0xE0.toByte(), 0x23, 0, 0, data.size.toByte()) + data)

        val good = auth()
        assertArrayEquals(Protocol.SW_BAD_AUTH, put(auth(value = 999_999)))     // wrong amount
        assertArrayEquals(Protocol.SW_BAD_AUTH, put(auth(validAfter = 1)))       // validAfter must be 0
        val forged = good.copyOf().also { it[100] = (it[100] + 1).toByte() }     // flip a bit of r
        assertArrayEquals(Protocol.SW_BAD_AUTH, put(forged))
        assertArrayEquals(Protocol.SW_WRONG_LENGTH, put(good.copyOf(160)))
        assertEquals(0, stored.size)

        val ack = put(good)
        assertEquals(68, ack.size); assertEquals(1, ack[0].toInt())
        assertArrayEquals(Protocol.SW_OK, ack.copyOfRange(66, 68))
        assertArrayEquals(payee, Eth.recover(Eth.eip191(Eth.keccak(good)), ack.copyOfRange(1, 66))) // receipt
        assertEquals(1, stored.size)
        assertArrayEquals(Protocol.SW_NO_REQUEST, put(good))   // paid once, like cash.c
        assertArrayEquals(Protocol.SW_NO_REQUEST, p.handle(getReq))
        assertEquals(1, stored.size)
        assertArrayEquals(good, Auth.fromJson(stored[0].toJson()).encode())
        assertEquals(true, stored[0].toJson().contains("\"validBefore\":\"18446744073709551615\"")) // settle.mjs BigInt()s this
    }

    @Test fun hidFraming5() = roundtrip(5, 1)

    @Test fun hidFraming300() = roundtrip(300, 6)  // 57 + 4*59 + 7

    private fun roundtrip(n: Int, reports: Int) {
        val apdu = ByteArray(n) { (it * 7).toByte() }
        val w = HidFraming.wrap(apdu)
        assertEquals(reports, w.size)
        w.forEach { assertEquals(64, it.size) }
        assertEquals("0101050000" + "%04x".format(n), Hex.encode(w[0].copyOf(7)))
        assertEquals("01010500" + "%02x".format(reports - 1), Hex.encode(w.last().copyOf(5)))
        val it = w.iterator()
        assertArrayEquals(apdu, HidFraming.unwrap { it.next() })
        assertNull(runCatching { HidFraming.unwrap(0x0202) { w[0] } }.getOrNull())
    }
}
