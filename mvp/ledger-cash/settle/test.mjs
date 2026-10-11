// node test.mjs  (anvil on :8545, out/ built). Deploys a fresh token, then asserts:
// valid auth moves funds; replaying it is rejected; a wrong-domain signature is rejected.
// Writes auths.json + fixture.json (typed data, digest, signature) for Stage B to diff against.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { pbkdf2Sync } from 'node:crypto';
import { keccak256, toHex, toBytes, hashTypedData, parseSignature, getAddress } from 'viem';
import { HDKey, hdKeyToAccount } from 'viem/accounts';

const SEED = 'glory promote mansion idle axis finger extra february uncover one trip resource lawn turtle enact monster seven myth punch hobby comment base bet';
// The spike's Speculos seed is 23 words (fails the BIP39 checksum, so viem's mnemonicToAccount throws).
// Speculos just runs BIP39 PBKDF2 on the text, so do the same, then 44'/60'/0'/0/0.
const payer = hdKeyToAccount(HDKey.fromMasterSeed(pbkdf2Sync(SEED.normalize('NFKD'), 'mnemonic', 2048, 64, 'sha512')));
assert.equal(payer.address, '0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415');
const PAYEE = '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC'; // anvil (2), any address works

const run = (...args) => {
  const r = spawnSync(process.execPath, args, { cwd: import.meta.dirname, encoding: 'utf8' });
  process.stdout.write(`$ node ${args.join(' ')}\n${r.stdout}${r.stderr}`);
  return r;
};
assert.equal(run('deploy.mjs').status, 0);
const { abi, deployment, publicClient } = await import('./common.mjs');
const { token, domain } = deployment();
const read = (functionName, args = []) => publicClient.readContract({ address: token, abi, functionName, args });
assert.equal(await read('TRANSFER_WITH_AUTHORIZATION_TYPEHASH'), '0x7c7c6cdb67a18743f49ec6fa9b35f50d52ed05cbed4cc592e13b44501c1a2267');
assert.equal(await read('name'), 'USDC');
assert.equal(await read('version'), '2');
assert.equal(run('fund.mjs', payer.address, '100').status, 0);

const types = {
  TransferWithAuthorization: [
    { name: 'from', type: 'address' }, { name: 'to', type: 'address' }, { name: 'value', type: 'uint256' },
    { name: 'validAfter', type: 'uint256' }, { name: 'validBefore', type: 'uint256' }, { name: 'nonce', type: 'bytes32' },
  ],
};
// Stand-in payment request; Stage B defines the real bytes. nonce = keccak256(payment request).
const request = toBytes(`ledger-cash:v0|to=${PAYEE}|value=12500000|${Date.now()}`);
async function signAuth(dom, nonce) {
  const message = { from: payer.address, to: PAYEE, value: 12_500_000n, validAfter: 0n, validBefore: BigInt(Math.floor(Date.now() / 1000) + 3600), nonce };
  const typedData = { domain: dom, types, primaryType: 'TransferWithAuthorization', message };
  const signature = await payer.signTypedData(typedData);
  const { r, s, v } = parseSignature(signature);
  const auth = { from: payer.address, to: PAYEE, value: toHex(message.value), validAfter: toHex(message.validAfter), validBefore: toHex(message.validBefore), nonce, v: toHex(v), r, s };
  return { typedData, digest: hashTypedData(typedData), signature, auth };
}
const bal = (a) => read('balanceOf', [a]);

// 1. valid auth settles
const good = await signAuth(domain, keccak256(request));
writeFileSync(new URL('./auths.json', import.meta.url), JSON.stringify([good.auth], null, 2) + '\n');
writeFileSync(new URL('./fixture.json', import.meta.url), JSON.stringify(good, (_, x) => (typeof x === 'bigint' ? x.toString() : x), 2) + '\n');
const [p0, q0] = [await bal(payer.address), await bal(PAYEE)];
const r1 = run('settle.mjs', 'auths.json');
assert.equal(r1.status, 0);
assert.match(r1.stdout, /#0 success tx 0x[0-9a-f]{64}/);
assert.equal(await bal(payer.address), p0 - 12_500_000n);
assert.equal(await bal(PAYEE), q0 + 12_500_000n);
assert.equal(await read('authorizationState', [payer.address, good.auth.nonce]), true);

// 2. replay of the same auth is rejected, no funds move
const r2 = run('settle.mjs', 'auths.json');
assert.notEqual(r2.status, 0);
assert.match(r2.stdout, /REJECTED already used/);
assert.equal(await bal(payer.address), p0 - 12_500_000n);

// 3. wrong domain (mainnet name "USD Coin") -> invalid signature
const bad = await signAuth({ ...domain, name: 'USD Coin' }, keccak256(toBytes('other request')));
writeFileSync(new URL('./auths-bad-domain.json', import.meta.url), JSON.stringify([bad.auth], null, 2) + '\n');
const r3 = run('settle.mjs', 'auths-bad-domain.json');
assert.notEqual(r3.status, 0);
assert.match(r3.stdout, /REJECTED FiatTokenV2: invalid signature/);
assert.equal(await read('authorizationState', [payer.address, bad.auth.nonce]), false);

console.log(`digest ${good.digest}\nsignature ${good.signature}\nALL PASS`);
