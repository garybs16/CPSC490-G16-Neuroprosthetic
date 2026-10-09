> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Poly Network, 2021-08-10

**Loss:** about $611M (rekt; DefiLlama) · **Design:** messaging (keeper-signed cross-chain messages, LockProxy escrows) · **Root cause:** access control · **Chains:** Ethereum, BSC, Polygon · **Status:** confirmed

## Summary
At the time, this was the largest DeFi theft on record. A permissions flaw let the message-execution contract call a privileged contract and replace the keeper (signer) set. No key was stolen. With its own keeper installed, the attacker unlocked assets from the LockProxy escrows on three chains. Over the following weeks the attacker returned almost everything.

## Timeline (UTC)
| Time | Event |
|---|---|
| 09:48:40 | Keeper public-key replacement on Ethereum (block 12996659, tx `0xb1f70464…d59581`) |
| 09:51:02 | First Ethereum theft from LockProxy `0x250e7698…cc906` (block 12996671, tx `0xad7a2c70…7602a`) |
| Same day | Similar unlocks on BSC and Polygon; Poly publishes an appeal to the attacker; Tether freezes about 33M USDT |
| Following weeks | Attacker returns funds |

## What failed
Access control: a cross-chain message could reach a function that should only be callable by governance.

## On-chain signature
- A keeper/validator-set change event came 2 min 22 s before the first theft. This is the earliest observable signal.
- Then came very large unlocks from LockProxy across many tokens (USDC, WBTC, USDT, WETH and others) to one fresh address, repeated on three chains.

## BridgeWatch rules that would fire
- `config_change`: on the keeper-replacement tx, about 2 minutes before any loss.
- `large_withdrawal` and `escrow_drain`: within one Ethereum block of the first unlock. Single unlocks were orders of magnitude above the hourly baseline.
- `outflow_spike`: on the same block.

## False-alarm considerations
- Keeper rotations do happen in normal operation, but rarely: a handful per year, and announced. An unannounced rotation followed by large unlocks within minutes is unambiguous.
- Large single unlocks can be legitimate treasury or market-maker moves. Combining them with `config_change` removes most of that ambiguity.

## Response and outcome
Public appeal, exchange and issuer freezes, then negotiated return. About 100% returned. The attacker was offered a "chief security advisor" title and a bounty.

## References
- https://rekt.news/polynetwork-rekt
- https://slowmist.medium.com/the-root-cause-of-poly-network-being-hacked-ec2ee1b0c68f
- https://github.com/SunWeb3Sec/DeFiHackLabs
- `../verified-ethereum-cases.md` (blocks and tx hashes re-read from RPC)
