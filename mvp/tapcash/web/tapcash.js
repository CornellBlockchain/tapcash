// Wire format shared with flex-app/src/app_main.c. Pure, so test.mjs can import it.

export const USDC = '0x036CbD53842c5426634e7929541eC2318f3dCF7e';
export const DOMAIN = { name: 'USDC', version: '2', chainId: 84532, verifyingContract: USDC };
export const TYPES = {
  TransferWithAuthorization: [
    { name: 'from', type: 'address' },
    { name: 'to', type: 'address' },
    { name: 'value', type: 'uint256' },
    { name: 'validAfter', type: 'uint256' },
    { name: 'validBefore', type: 'uint256' },
    { name: 'nonce', type: 'bytes32' },
  ],
};
const N = 0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141n;

const hex = b => '0x' + [...b].map(x => x.toString(16).padStart(2, '0')).join('');
const bytes = h => Uint8Array.from(h.slice(2).match(/../g), x => parseInt(x, 16));

// Key handle: to(20) | value(8, micro-USDC) | validBefore(4) | nonce(32)
export function buildRequest(to, value, validBefore, nonce) {
  const kh = new Uint8Array(64);
  const dv = new DataView(kh.buffer);
  kh.set(bytes(to), 0);
  dv.setBigUint64(20, value);
  dv.setUint32(28, validBefore);
  kh.set(bytes(nonce), 32);
  return kh;
}

// U2F response from WebAuthn: v rides in the counter's last byte; the signature field is
// DER(r, s) followed by the Flex's address (from).
export function parseResponse(authenticatorData, signature) {
  const a = new Uint8Array(authenticatorData), d = new Uint8Array(signature);
  let v = a[36];
  if (d[0] !== 0x30 || d[2] !== 0x02) throw new Error('bad DER');
  const rLen = d[3], r = d.slice(4, 4 + rLen);
  if (d[4 + rLen] !== 0x02) throw new Error('bad DER');
  const s = d.slice(6 + rLen, 6 + rLen + d[5 + rLen]);
  const from = hex(d.slice(2 + d[1], 2 + d[1] + 20));
  if (from.length !== 42) throw new Error('missing from');
  let sn = BigInt(hex(s));
  if (sn > N / 2n) { sn = N - sn; v ^= 1; }  // USDC rejects high-s; flipping s flips parity
  const pad = n => '0x' + n.toString(16).padStart(64, '0');
  return { from, v, r: pad(BigInt(hex(r))), s: pad(sn) };
}

export function parseRequest(kh) {
  const dv = new DataView(kh.buffer, kh.byteOffset);
  return { to: hex(kh.slice(0, 20)), value: dv.getBigUint64(20), validBefore: BigInt(dv.getUint32(28)), nonce: hex(kh.slice(32)) };
}
