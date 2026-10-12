// Setup page's device command on Speculos: E0 02 P1=0 answers silently; P1=1 shows the EIP-55 address
// on the Flex and answers only after Confirm (9000 + address) or Cancel (6985).
// Start Speculos as in test.mjs (fresh, on the home screen), then  node test-setup.mjs
import assert from 'node:assert/strict';
import { getAddress } from 'viem';

const API = 'http://localhost:5001';
const post = (path, body) => fetch(API + path, { method: 'POST', body: JSON.stringify(body) }).then(r => r.json());
const apdu = async h => (await post('/apdu', { data: h })).data;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const touch = async (x, y) => { await post('/finger', { action: 'press-and-release', x, y }); await sleep(1500); };
const screen = async () => (await (await fetch(API + '/events')).json()).events.map(e => e.text).join('');

const silent = await apdu('e002000000');
assert.equal(silent.slice(-4), '9000');
const address = getAddress('0x' + silent.slice(0, 40));

// Confirm: the reply waits for the user
let reply = apdu('e002010000');
await sleep(1500);
assert.match(await screen(), /Verify TapCash address/);
await touch(430, 552);                                  // next page: the address
assert.match((await screen()).replace(/\s/g, ''), new RegExp(address.slice(2)));  // EIP-55, same as the page
await touch(240, 436);                                  // Confirm
assert.equal(await reply, address.slice(2).toLowerCase() + '9000');
await sleep(3500);

// Cancel
reply = apdu('e002010000');
await sleep(1500);
await touch(90, 552);                                   // Cancel
assert.equal(await reply, '6985');
await sleep(3500);
assert.equal(await apdu('e002000000'), silent);         // back to normal
console.log('ok setup', address);
