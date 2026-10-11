// Pocket mode on Speculos: small payments sign on the first tap, larger or over-budget ones
// fall back to the two-tap review; limits change in Settings. Start Speculos as in test.mjs (fresh, on the home screen), then
//   node test-pocket.mjs
import assert from 'node:assert/strict';
import { recoverTypedDataAddress, serializeSignature, toHex } from 'viem';
import { DOMAIN, TYPES, buildRequest, parseRequest, parseResponse } from './web/tapcash.js';

const API = "http://localhost:5001";
const post = (path, body) => fetch(API + path, { method: 'POST', body: JSON.stringify(body) }).then(r => r.json());
const apdu = async h => (await post('/apdu', { data: h })).data;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const sign = kh => {
  const data = Buffer.concat([Buffer.alloc(64), Buffer.from([kh.length]), Buffer.from(kh)]);
  return apdu(Buffer.concat([Buffer.from([0, 2, 3, 0, data.length]), data, Buffer.from([0])]).toString('hex'));
};
const events = async () => (await (await fetch(API + '/events')).json()).events;
const screen = async () => (await events()).map(e => e.text).join('');
const press = async text => {  // touch the last button with this label
  const e = (await events()).findLast(e => e.text === text);
  assert.ok(e, `no "${text}" on screen`);
  await post('/finger', { action: 'press-and-release', x: 240, y: e.y + 18 });
  await sleep(1500);
};
const req = usdc => buildRequest('0x000000000000000000000000000000000000dEaD', BigInt(usdc * 1e6),
  Math.floor(Date.now() / 1000) + 3600, toHex(crypto.getRandomValues(new Uint8Array(32))));
const flex = '0x' + (await apdu('e002000000')).slice(0, 40);

async function assertSigned(kh, resp) {
  assert.equal(resp.slice(-4), '9000');
  const raw = Buffer.from(resp.slice(0, -4), 'hex');
  const { from, v, r, s } = parseResponse(Buffer.concat([Buffer.alloc(32), raw.subarray(0, 5)]), raw.subarray(5));
  const signer = await recoverTypedDataAddress({ domain: DOMAIN, types: TYPES, primaryType: 'TransferWithAuthorization',
    message: { from, ...parseRequest(kh), validAfter: 0n }, signature: serializeSignature({ r, s, v: BigInt(v) }) });
  assert.equal(signer.toLowerCase(), flex.toLowerCase());
}

// Off by default: a small payment still needs the review
const off = req(1);
assert.equal(await sign(off), '6985');
await sleep(1000);
await press('Reject');
await sleep(1500);

await press('Turn on pocket mode');
assert.match(await screen(), /Turn on pocket mode\?/);
await press('Turn on');
await sleep(2500);  // "Pocket mode on" status, then home
assert.match(await screen(), /20 USDC left/);

// Over the per-tap cap: review, as before
assert.equal(await sign(req(6)), '6985');
await sleep(1000);
assert.match(await screen(), /6 USDC on Base Sepolia/);
await press('Reject');
await sleep(1500);

// Under the cap: signed on the first tap; a retried tap gets the same reply without spending twice
const first = req(5);
const resp = await sign(first);
await assertSigned(first, resp);
assert.equal(await sign(first), resp);
await sleep(2500);
assert.match(await screen(), /Paid 5 USDC/);
for (const usdc of [5, 5, 4.5]) {
  const kh = req(usdc);
  await assertSigned(kh, await sign(kh));
}
await sleep(4000);  // status screen times out back to home
assert.match(await screen(), /0\.5 USDC left/);

// Budget spent: back to the review
assert.equal(await sign(req(1)), '6985');
await sleep(1000);
assert.match(await screen(), /1 USDC on Base Sepolia/);
await press('Reject');
await sleep(1500);

await press('Turn off pocket mode');
await sleep(2500);
assert.match(await screen(), /Turn on pocket mode/);

// Limits are picked in Settings (gear, then one page each): 1 USDC per tap, 1 payment
const touch = async (x, y) => { await post('/finger', { action: 'press-and-release', x, y }); await sleep(1500); };
await touch(403, 75);
await press('1 USDC per tap');
await touch(430, 552);  // next page: total
await touch(430, 552);  // next page: number of payments
await press('1 payment');
await touch(50, 48);    // back home
await press('Turn on pocket mode');
assert.match(await screen(), /Up to 1 payment of at most 1 USDC each/);
await press('Turn on');
await sleep(2500);
assert.match(await screen(), /20 USDC left\s*for 1 more payment(?!s)/);
assert.equal(await sign(req(2)), '6985');  // over the new 1 USDC cap
await sleep(1000);
await press('Reject');
await sleep(1500);
const one = req(1);
await assertSigned(one, await sign(one));
await sleep(1000);
assert.match(await screen(), /Paid 1 USDC/);
await sleep(3000);
assert.match((await events()).at(-1).text, /Turn on pocket mode/);  // the only payment used: off
console.log('ok pocket', flex);
