// Card mode and budget mode on Speculos. Card mode: the next payment, any amount, signs on the
// first tap, then turns off. Budget mode: payments within the Settings limits sign on the first tap.
// Start Speculos as in test.mjs (fresh, on the home screen), then
//   node test-modes.mjs
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
const press = async text => {  // wait until this label is on the current screen, then touch it
  let e;
  for (let i = 0; !(e = (await (await fetch(API + '/events?currentscreenonly=true')).json()).events.find(e => e.text === text)); i++) {
    assert.ok(i < 40, `no "${text}" on screen`);  // e.g. a "Rejected" status still showing
    await sleep(250);
  }
  await post('/finger', { action: 'press-and-release', x: 240, y: e.y + 18 });
  await sleep(1500);
};
press.home = async () => {  // wait out a status screen (e.g. "Rejected") until home is back
  for (let i = 0; !(await (await fetch(API + '/events?currentscreenonly=true')).json()).events.some(e => e.text === 'Quit app'); i++) {
    assert.ok(i < 40, 'home screen did not come back');
    await sleep(250);
  }
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

const touch = async (x, y) => { await post('/finger', { action: 'press-and-release', x, y }); await sleep(1500); };
const home = async () => (await events()).map(e => e.text).slice(-5).join();
async function assertReview(usdc) {
  assert.equal(await sign(req(usdc)), '6985');
  await sleep(1000);
  assert.match(await screen(), new RegExp(`${usdc} USDC on Base Sepolia`));
  await press('Reject');
  await press.home();
}
async function payOneTap(usdc) {
  const kh = req(usdc), resp = await sign(kh);
  await assertSigned(kh, resp);
  assert.equal(await sign(kh), resp);  // a retried tap gets the same reply without paying twice
  await sleep(1000);
  assert.match(await screen(), new RegExp(`Paid ${usdc} USDC`));
  await sleep(3500);  // status screen times out back to home
}

// Both modes off by default: review
await assertReview(1);

// Card mode: the next payment, any amount, on the first tap; then off
await press('Turn on card mode');
assert.match(await screen(), /Turn on card mode\?/);
await press('Turn on');
await sleep(2500);
assert.match(await home(), /Card mode is on/);
await payOneTap(1000);
assert.match(await home(), /Turn on card mode/);
await assertReview(2);

// Card mode can be turned off before paying
await press('Turn on card mode');
await press('Turn on');
await sleep(2500);
await press('Turn off card mode');
await sleep(2500);
await assertReview(3);

// Budget mode: a switch on the first settings page; home is current after going back
await touch(403, 75);
assert.match(await screen(), /Budget mode/);
await touch(420, 142);  // switch on
await touch(50, 48);    // back home
assert.match(await home(), /20 USDC left,for 10 more payments/);
await assertReview(6);  // over the 5 USDC default
await payOneTap(5);
assert.match(await home(), /15 USDC left,for 9 more payments/);

// Card mode wins while armed and doesn't spend the budget
await press('Turn on card mode');
await press('Turn on');
await sleep(2500);
await payOneTap(50);
assert.match(await home(), /15 USDC left,for 9 more payments/);

// Limits in settings: total and count restart a running budget
await touch(403, 75);
await touch(430, 552);  // per tap
await press('1 USDC per tap');
await touch(430, 552);  // total
await press('100 USDC in total');
await touch(430, 552);  // number of payments
await press('1 payment');
assert.match((await events()).map(e => e.text).slice(-6).join(), /1 payment/);  // still on that page
await touch(50, 48);
assert.match(await home(), /100 USDC left,for 1 more payment(?!s)/);
await assertReview(2);  // over the new 1 USDC cap
await payOneTap(1);
assert.match(await home(), /Hold your iPhone/);  // the only payment used: budget mode off

// Switching budget mode off in settings
await touch(403, 75);
await touch(420, 142);  // on
await touch(420, 142);  // off
await touch(50, 48);
assert.match(await home(), /Hold your iPhone/);
await assertReview(1);
// Card mode times out after one minute
await press('Turn on card mode');
await press('Turn on');
await sleep(2500);
assert.match(await home(), /Card mode is on for 1 minute/);
await sleep(60000);
assert.match(await screen(), /Card mode timed out/);
await sleep(3500);
assert.match(await home(), /Turn on card mode/);
await assertReview(4);
console.log('ok card + budget', flex);
