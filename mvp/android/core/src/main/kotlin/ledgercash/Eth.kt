package ledgercash

import java.math.BigInteger
import org.bouncycastle.crypto.digests.KeccakDigest
import org.bouncycastle.crypto.digests.SHA256Digest
import org.bouncycastle.crypto.ec.CustomNamedCurves
import org.bouncycastle.crypto.params.ECDomainParameters
import org.bouncycastle.crypto.params.ECPrivateKeyParameters
import org.bouncycastle.crypto.signers.ECDSASigner
import org.bouncycastle.crypto.signers.HMacDSAKCalculator
import org.bouncycastle.math.ec.ECAlgorithms

// secp256k1 + keccak on BouncyCastle's lightweight API. Signatures are r(32)||s(32)||v, v in {27,28}, low-s.
object Eth {
    private val X9 = CustomNamedCurves.getByName("secp256k1")
    private val CURVE = ECDomainParameters(X9.curve, X9.g, X9.n, X9.h)
    private val HALF_N = CURVE.n.shiftRight(1)

    fun keccak(vararg parts: ByteArray): ByteArray {
        val d = KeccakDigest(256)
        parts.forEach { d.update(it, 0, it.size) }
        return ByteArray(32).also { d.doFinal(it, 0) }
    }

    fun address(priv: ByteArray): ByteArray {
        val pub = CURVE.g.multiply(BigInteger(1, priv)).normalize().getEncoded(false)
        return keccak(pub.copyOfRange(1, 65)).copyOfRange(12, 32)
    }

    fun sign(hash: ByteArray, priv: ByteArray): ByteArray {
        val signer = ECDSASigner(HMacDSAKCalculator(SHA256Digest())) // RFC 6979, same nonces as viem/noble
        signer.init(true, ECPrivateKeyParameters(BigInteger(1, priv), CURVE))
        val (r, s0) = signer.generateSignature(hash)
        val s = if (s0 > HALF_N) CURVE.n - s0 else s0
        val rs = u256(r) + u256(s)
        val me = address(priv)
        for (v in 27..28) {
            val sig = rs + byteArrayOf(v.toByte())
            if (recover(hash, sig)?.contentEquals(me) == true) return sig
        }
        error("no recovery id") // ponytail: r >= p (recovery id 2/3) has probability ~2^-127, not handled
    }

    /** 20-byte signer address, or null. Accepts v in {0,1,27,28}; rejects high s like USDC.sol. */
    fun recover(hash: ByteArray, sig: ByteArray): ByteArray? {
        if (sig.size != 65 || hash.size != 32) return null
        val r = BigInteger(1, sig.copyOfRange(0, 32))
        val s = BigInteger(1, sig.copyOfRange(32, 64))
        val recId = when (sig[64].toInt() and 0xff) { 0, 27 -> 0; 1, 28 -> 1; else -> return null }
        if (r.signum() == 0 || r >= CURVE.n || s.signum() == 0 || s > HALF_N) return null
        val rPoint = try {
            CURVE.curve.decodePoint(byteArrayOf((2 + recId).toByte()) + u256(r))
        } catch (e: IllegalArgumentException) {
            return null
        }
        val rInv = r.modInverse(CURVE.n)
        val e = BigInteger(1, hash)
        val q = ECAlgorithms.sumOfTwoMultiplies(
            CURVE.g, e.negate().multiply(rInv).mod(CURVE.n), rPoint, s.multiply(rInv).mod(CURVE.n),
        ).normalize()
        if (q.isInfinity) return null
        return keccak(q.getEncoded(false).copyOfRange(1, 65)).copyOfRange(12, 32)
    }

    fun eip191(msg: ByteArray) = keccak("\u0019Ethereum Signed Message:\n${msg.size}".toByteArray(Charsets.US_ASCII), msg)

    private val DOMAIN_TYPEHASH =
        keccak("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)".toByteArray())
    private val TWA_TYPEHASH = keccak(
        "TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)".toByteArray(),
    )

    /** Domain {name "USDC", version "2", chainId, verifyingContract = token}. u64 fields are unsigned. */
    fun eip712TransferWithAuthorization(
        chainId: Long, token: ByteArray, from: ByteArray, to: ByteArray,
        value: Long, validAfter: Long, validBefore: Long, nonce: ByteArray,
    ): ByteArray {
        val domain = keccak(DOMAIN_TYPEHASH, keccak("USDC".toByteArray()), keccak("2".toByteArray()), w(chainId), pad(token))
        val struct = keccak(TWA_TYPEHASH, pad(from), pad(to), w(value), w(validAfter), w(validBefore), nonce)
        return keccak(byteArrayOf(0x19, 0x01), domain, struct)
    }

    private fun pad(b: ByteArray) = ByteArray(32 - b.size) + b
    private fun w(x: Long) = ByteArray(24) + Bytes.u64(x)
    private fun u256(x: BigInteger): ByteArray {
        val b = x.toByteArray()
        return if (b.size > 32) b.copyOfRange(b.size - 32, b.size) else ByteArray(32 - b.size) + b
    }
}
