// Gas tap: a new iPhone wallet with no ETH gets a small top-up, so users don't fund every new
// wallet by hand. Base Sepolia needs env GAS_FUNDER_KEY; Base mainnet needs its own
// GAS_FUNDER_KEY_MAINNET, so mainnet stays off until that key is set and funded.
//   POST { address, chain? } -> { hash } | { skipped: 'has gas' }    chain: 0 Base Sepolia (default), 1 Base
import { createPublicClient, createWalletClient, http, isAddress, parseEther } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
import { base, baseSepolia } from 'viem/chains';

const NETS = [
  { chain: baseSepolia, env: 'GAS_FUNDER_KEY', drip: parseEther('0.0005'), enough: parseEther('0.0001') },  // hundreds of txs
  // ~50 payments (~$0.10). ponytail: real ETH and no per-address memory, so someone looping fresh
  // addresses can drain the funder; keep only a few dollars in it. Add a KV of funded addresses, or
  // relay the payment server-side, if that ever happens.
  { chain: base, env: 'GAS_FUNDER_KEY_MAINNET', drip: parseEther('0.00003'), enough: parseEther('0.00001') },
];

export default async function handler(req, res) {
  const net = NETS[req.body?.chain ?? 0];
  const key = net && process.env[net.env];
  if (!key) return res.status(503).json({ error: 'Gas tap not configured' });
  try {
    const address = req.body?.address;
    if (req.method !== 'POST' || !isAddress(address)) throw new Error('expected POST { address }');
    const pub = createPublicClient({ chain: net.chain, transport: http() });
    // ponytail: no per-address memory; a balance check stops repeats, not someone looping fresh addresses
    if (await pub.getBalance({ address }) >= net.enough) return res.json({ skipped: 'has gas' });
    const account = privateKeyToAccount(key);
    const wallet = createWalletClient({ account, chain: net.chain, transport: http() });
    const hash = await wallet.sendTransaction({ to: address, value: net.drip });
    await pub.waitForTransactionReceipt({ hash });
    res.json({ hash });
  } catch (e) {
    res.status(400).json({ error: e.shortMessage || e.message });
  }
}
