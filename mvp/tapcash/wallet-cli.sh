#!/usr/bin/env bash
# TapCash shortcuts on top of Ledger's wallet-cli (@ledgerhq/wallet-cli). See SETUP.md, "Ledger Wallet CLI".
#
#   wallet-cli.sh balance                      USDC and ETH on the Flex (TapCash) address
#   wallet-cli.sh topup <from-label> <amount>  send USDC from another Ledger account to the Flex
#   wallet-cli.sh out <to-address> <amount>    send USDC from the Flex to any address
#
# Env:
#   TAPCASH_ACCOUNT  session label of the Flex address (find it with: wallet-cli session view)
#   TAPCASH_ADDRESS  the Flex address, 0x..., needed by topup
#   WALLET_CLI       command to run, default wallet-cli (e.g. "npx -y @ledgerhq/wallet-cli")
#   LIVE=1           really sign and broadcast; without it, sends are --dry-run only
set -euo pipefail
W=${WALLET_CLI:-wallet-cli}
TICKER=tUSDC  # wallet-cli's name for USDC on Base Sepolia
dry=--dry-run
[ "${LIVE:-}" = 1 ] && dry=

case "${1:-}" in
  balance|topup|out) : "${TAPCASH_ACCOUNT:?set TAPCASH_ACCOUNT to the Flex label from: wallet-cli session view}" ;;
  *) sed -n '2,12p' "$0" >&2; exit 2 ;;
esac
case "$1" in
  balance) $W balances "$TAPCASH_ACCOUNT" ;;
  topup)   [ $# -eq 3 ] || { echo "usage: $0 topup <from-label> <amount>" >&2; exit 2; }
           $W send "$2" --to "${TAPCASH_ADDRESS:?set TAPCASH_ADDRESS}" --amount "$3 $TICKER" $dry ;;
  out)     [ $# -eq 3 ] || { echo "usage: $0 out <to-address> <amount>" >&2; exit 2; }
           $W send "$TAPCASH_ACCOUNT" --to "$2" --amount "$3 $TICKER" $dry ;;
esac
