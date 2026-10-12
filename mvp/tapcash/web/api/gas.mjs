// Gas tap: a new iPhone wallet with no ETH gets a small Base Sepolia top-up, so testers don't fund
// every new wallet by hand. Testnet only. Needs env GAS_FUNDER_KEY (a funded Base Sepolia key).
//   POST { address } -> { hash } | { skipped: 'has gas' }
import { createPublicClient, createWalletClient, http, isAddress, parseEther } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
import { baseSepolia } from 'viem/chains';

const DRIP = parseEther('0.0005');     // hundreds of Base Sepolia transactions
const ENOUGH = parseEther('0.0001');   // only top up wallets below this

export default async function handler(req, res) {
  if (!process.env.GAS_FUNDER_KEY) return res.status(503).json({ error: 'Gas tap not configured' });
  try {
    const address = req.body?.address;
    if (req.method !== 'POST' || !isAddress(address)) throw new Error('expected POST { address }');
    const pub = createPublicClient({ chain: baseSepolia, transport: http() });
    // ponytail: no per-address memory; a balance check stops repeats, not someone looping fresh addresses (testnet ETH)
    if (await pub.getBalance({ address }) >= ENOUGH) return res.json({ skipped: 'has gas' });
    const account = privateKeyToAccount(process.env.GAS_FUNDER_KEY);
    const wallet = createWalletClient({ account, chain: baseSepolia, transport: http() });
    const hash = await wallet.sendTransaction({ to: address, value: DRIP });
    await pub.waitForTransactionReceipt({ hash });
    res.json({ hash });
  } catch (e) {
    res.status(400).json({ error: e.shortMessage || e.message });
  }
}
