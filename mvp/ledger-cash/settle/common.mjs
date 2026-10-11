// Shared bits for the settle scripts. Anvil default keys (printed in anvil's startup log).
import { readFileSync } from 'node:fs';
import { createPublicClient, createWalletClient, http, defineChain } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';

export const RPC = process.env.RPC_URL ?? 'http://127.0.0.1:8545';
export const DEPLOYER_KEY = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'; // anvil (0)
export const RELAYER_KEY = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'; // anvil (1)
export const artifact = JSON.parse(readFileSync(new URL('./out/USDC.sol/USDC.json', import.meta.url)));
export const abi = artifact.abi;
export const deployment = () => JSON.parse(readFileSync(new URL('./deploy.json', import.meta.url)));

const pub = createPublicClient({ transport: http(RPC) });
export const chain = defineChain({ id: await pub.getChainId(), name: 'local', nativeCurrency: { name: 'ETH', symbol: 'ETH', decimals: 18 }, rpcUrls: { default: { http: [RPC] } } });
export const publicClient = createPublicClient({ chain, transport: http(RPC) });
export const wallet = (key) => createWalletClient({ account: privateKeyToAccount(key), chain, transport: http(RPC) });
export const fmt = (units) => `${(Number(units) / 1e6).toFixed(6)} USDC`; // ponytail: Number ok below 9e9 USDC
