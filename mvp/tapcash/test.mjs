// End-to-end check: emulated Flex (Speculos) -> web/tapcash.js parsing -> USDC on Base Sepolia.
//   docker run --rm -d --name speculos -p 5001:5000 -v "$PWD":/app -w /app/flex-app \
//     ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest \
//     speculos --model flex --display headless --seed 3e0b8a61619162931b30148598fa4b3648e011bf0c9b9a8abf125c613ae1f5a6 build/flex/bin/app.elf
//   npm i && node test.mjs
// (custom seed: the default Speculos address has an EIP-7702 delegation on Base Sepolia,
// which makes USDC check signatures via ERC-1271 and reject them)
import assert from 'node:assert/strict';
import { createPublicClient, http, recoverTypedDataAddress, serializeSignature, toHex } from 'viem';
import { baseSepolia } from 'viem/chains';
import { USDC, DOMAIN, TYPES, buildRequest, parseRequest, parseResponse } from './web/tapcash.js';

const API = "http://localhost:5001";  // macOS AirPlay owns 5000
const post = (path, body) => fetch(API + path, { method: 'POST', body: JSON.stringify(body) }).then(r => r.json());
const apdu = async h => (await post('/apdu', { data: h })).data;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const sign = (kh, p1 = 3) => {
  const data = Buffer.concat([Buffer.alloc(64), Buffer.from([kh.length]), Buffer.from(kh)]);
  return apdu(Buffer.concat([Buffer.from([0, 2, p1, 0, data.length]), data, Buffer.from([0])]).toString('hex'));
};

const flex = '0x' + (await apdu('e002000000')).slice(0, 40);
const kh = buildRequest('0x000000000000000000000000000000000000dEaD', 1_500_000n,
  Math.floor(Date.now() / 1000) + 3600, toHex(crypto.getRandomValues(new Uint8Array(32))));

assert.equal(await apdu('00a4040008a0000006472f000100'), Buffer.from('U2F_V2').toString('hex') + '9000');
assert.equal(await apdu('00a4040007d276000085010100'), '6a82');   // NDEF probe ignored
assert.equal(await apdu('80100000010400'), '6d00');               // CTAP2 refused -> U2F fallback
assert.equal(await sign(Buffer.from('other site')), '6a80');      // not our key handle
assert.equal(await sign(kh, 7), '6985');                          // check-only: ours
assert.equal(await sign(kh), '6985');                             // tap 1: review shown
await sleep(1000);
const screen = (await (await fetch(API + '/events')).json()).events.map(e => e.text).join('');  // address wraps across lines
assert.match(screen, /1\.5 USDC on Base Sepolia/);
assert.match(screen, /000000000000000000000000000000000000DEAD/i);
await post('/finger', { action: 'press-and-release', x: 240, y: 460 });  // Approve
await sleep(1500);
const resp = await sign(kh);                                      // tap 2: signed authorization
assert.equal(resp.slice(-4), '9000');
assert.equal(await sign(kh), '6985');                             // single use
assert.equal(await apdu('0002030005aabb'), '6700');               // malformed

// Same parsing as the page: authenticatorData = rpIdHash(32) | flags(1) | counter(4)
const raw = Buffer.from(resp.slice(0, -4), 'hex');
const { from, v, r, s } = parseResponse(Buffer.concat([Buffer.alloc(32), raw.subarray(0, 5)]), raw.subarray(5));
assert.equal(from.toLowerCase(), flex.toLowerCase());
const req = parseRequest(kh);
const signer = await recoverTypedDataAddress({ domain: DOMAIN, types: TYPES, primaryType: 'TransferWithAuthorization',
  message: { from, ...req, validAfter: 0n }, signature: serializeSignature({ r, s, v: BigInt(v) }) });
assert.equal(signer.toLowerCase(), flex.toLowerCase());

// USDC checks the signature before the balance: "exceeds balance" means the chain accepted it.
const pub = createPublicClient({ chain: baseSepolia, transport: http() });
const abi = [{ name: 'transferWithAuthorization', type: 'function', stateMutability: 'nonpayable', outputs: [], inputs:
  ['address', 'address', 'uint256', 'uint256', 'uint256', 'bytes32', 'uint8', 'bytes32', 'bytes32'].map(type => ({ type })) }];
await assert.rejects(
  pub.simulateContract({ address: USDC, abi, functionName: 'transferWithAuthorization', account: flex,
    args: [from, req.to, req.value, 0n, req.validBefore, req.nonce, v, r, s] }),
  e => /exceeds balance/.test(e.message) || (console.error(e.shortMessage), false));
console.log('ok', flex);
