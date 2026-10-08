> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# HECO Bridge, 2023-11-22

**Loss:** about $86.6M (PeckShield via The Block). Combined with HTX hot-wallet losses the same day, about $99–110M. · **Design:** lock-mint (operator-controlled) · **Root cause:** key/signer compromise (suspected) · **Chains:** Ethereum, HECO · **Status:** confirmed

## Summary
The HECO bridge's Ethereum escrow was emptied by transfers that were "confirmed by the operator", which pointed to a compromised operator key. The first alert flagged a single 10,145 ETH transfer. HTX exchange hot wallets showed matching outflows shortly after. The operator promised compensation.

## Timeline (UTC)
| Time | Event |
|---|---|
| 09:59:35 | First theft from escrow `0xa929022c…e490c` (block 18626540) |
| Following minutes to hours | ETH, USDT, HBTC, SHIB, UNI, USDC, LINK, TUSD released to one address |
| Same day | PeckShield and others flag it publicly; HTX suspends deposits and withdrawals |

## What failed
Key/signer compromise: the operator key authorised the withdrawals.

## On-chain signature
- One large ETH transfer (about 10,145 ETH), then each other asset in turn, all to one recipient that had never used the bridge.

## BridgeWatch rules that would fire
- `large_withdrawal`: on the first transfer.
- `escrow_drain`: as each asset balance collapses.
- `withdrawal_burst`: multiple assets within a short window.
- `outflow_spike`: within the first hour.
- Expected latency: one block.

## False-alarm considerations
- Operator-key bridges sometimes sweep escrow to new custody. These sweeps go to known operator addresses and are often pre-announced. An allow-list of operator addresses cuts this noise.

## Response and outcome
- Operator (Justin Sun / HTX) said losses would be covered.
- Recovery details are not public.

## References
- https://www.theblock.co/post/264271/heco-bridge-appears-to-have-been-drained-of-86-6-million
- https://cointelegraph.com/news/heco-chain-bridge-hack-86-million-lost
- https://forklog.com/en/news/analysts-estimate-losses-from-htx-and-heco-bridge-hack-at-110-million
- `../verified-ethereum-cases.md`
