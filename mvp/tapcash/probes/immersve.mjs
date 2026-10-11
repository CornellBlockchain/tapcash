// Probe Immersve's public sandbox (credentials published at docs.immersve.com/resources/public-sandbox-account
// for testnet use). Signs in with a throwaway wallet, creates a funding source, simulates a deposit, then tries
// to pass test KYC and issue a card. As of 2026-10-11 the card step stops at KYC; see CASHOUT.md.
//   cd mvp/tapcash && node probes/immersve.mjs
import { privateKeyToAccount, generatePrivateKey } from 'viem/accounts';

const page = await (await fetch('https://docs.immersve.com/resources/public-sandbox-account/')).text();
const flat = page.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/g, '').replace(/<[^>]+>/g, ' ')
  .replace(/&amp;/g, '&').replace(/\s+/g, '');
const grab = re => flat.match(re)[1];
const C = {
  client: grab(/ClientApplicationId([0-9a-f]{32})/), program: grab(/CardProgramId([0-9a-f]{32})/),
  channel: grab(/FundingChannelId\(simulatorstrategy\)([0-9a-f]{32})/),
  key: grab(/CardIssuerX-Api-Key(imm-key-test-[0-9a-f]+)/), secret: grab(/CardIssuerX-Api-Secret(imm-secret-test-[0-9a-f]+)/),
};

async function api(path, body, { token, method, issuer } = {}) {
  const headers = { 'content-type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (issuer) Object.assign(headers, { 'x-api-key': C.key, 'x-api-secret': C.secret });
  const r = await fetch('https://test.immersve.com' + path, { method: method || (body ? 'POST' : 'GET'), headers, body: body && JSON.stringify(body) });
  const t = await r.text();
  let j; try { j = JSON.parse(t); } catch { j = t; }
  console.log(path, r.status, JSON.stringify(j).slice(0, 300));
  return j;
}
const rnd = n => Math.random().toString(36).slice(2, 2 + n);

// 1. Sign in with the wallet (SIWE)
const wallet = privateKeyToAccount(generatePrivateKey());
const init = await api('/auth/login-init', { loginMethod: 'siwe', network: 'polygon-amoy', clientApplicationId: C.client,
  scopes: ['cardholder-partner'], address: wallet.address, url: 'http://localhost:3000', autoSignup: true });
const session = await api('/auth/login-complete', { loginRequestId: init.id,
  signature: await wallet.signMessage({ message: init.signingChallenge.message }) });
const token = session.accessToken, account = session.cardholderAccountId;

// 2. Funding source and a simulated 5 USDC deposit: works
const source = await api('/api/funding-sources', { accountId: account, fundingChannelId: C.channel, fundingAddress: wallet.address }, { token });
await api('/api/simulator/execute-deposit', { fundingSourceId: source.id, amount: '5' }, { token });

// 3. Test KYC (partner-conducted; the "passall" middle name passes in test): returns API_KEY_DISABLED
await api(`/api/accounts/${account}/partner-kyc-statement`, { idempotencyKey: 'kyc-' + rnd(12), region: 'NZ',
  claims: [{ claimType: 'DOB', attributes: { dateOfBirth: '1990-04-23' } },
    { claimType: 'FULL_NAME', attributes: { givenName: 'Tap' + rnd(6), middleName: 'passall', familyName: 'Cash' + rnd(6) } },
    { claimType: 'ADDRESS', attributes: { addressType: 'RESIDENTIAL', streetNumber: '73', streetName: 'Demo' + rnd(5), streetType: 'ROAD',
      suburb: 'Auckland CBD', town: 'Auckland', region: 'Auckland', state: 'AKL', postalCode: '1010', country: 'NZ' } }],
  evidence: [{ evidenceType: 'PASSPORT', documentId: 'LA' + Math.floor(1e6 + Math.random() * 8e6), country: 'NZ', expiry: '2031-01-01' }] },
  { method: 'PUT', issuer: true });

// 4. Prerequisites and card: KYC_REQUIRED while step 3 is blocked
await api('/api/spending-prerequisites', { fundingSourceId: source.id, spendableAmount: 5, spendableCurrency: 'USD',
  kycType: 'partner-conducted', cardProgramId: C.program }, { token });
await api('/api/cards', { cardProgramId: C.program, fundingSourceId: source.id }, { token });
