> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Aztec Connect and Aztec V1 bridge, 2026-06-14 and 2026-06-17

**Loss:** about $2.19M (06-14; SlowMist), about $88K follow-up (06-15; rekt), and about $2.2M (06-17, escape hatch; rekt, AMBCrypto) · **Design:** canonical-rollup (deprecated, immutable L1 contracts) · **Root cause:** verification bug (a mismatch between what a rollup proof covered and what the contract settled) · **Chains:** Ethereum · **Status:** confirmed

## Summary
Aztec Connect had been deprecated for years, but its Ethereum rollup contract still held user assets and could not be upgraded. On 14 June, one settlement transaction paid out many assets that no real deposits backed. A second actor took a small amount the next day. On 17 June, the V1 contract's permissionless escape hatch was used to drain another $2.2M. Aztec says the live network and the AZTEC token were unaffected.

## Timeline (UTC)
| Time | Event |
|---|---|
| ~12:20 | Blockaid sees on-chain preparation about 6 minutes before the theft |
| 12:26:23 | Single-tx drain of RollupProcessor `0xff1f2b4a…0455` (block 25315715) |
| later | Aztec Labs comments 74 minutes after CertiK's public flag (rekt) |
| 06-15 | Second actor repeats the flaw for about $88K |
| 06-17 | V1 escape-hatch drain, about $2.2M |

## What failed
Verification bug in settlement logic.

## On-chain signature
- One transaction moving ETH, DAI, wstETH, Yearn vault tokens and LUSD out of a contract that had seen almost no activity for a long time.

## BridgeWatch rules that would fire
- `escrow_drain` and `large_withdrawal`: on block 25315715.
- `accounting_mismatch`: payouts without matching rollup deposits.
- **Dormant-vault special case:** for a contract with an hourly outflow baseline near zero, *any* large outflow is anomalous. BridgeWatch should keep watching deprecated vaults, because attackers target them.

## False-alarm considerations
- Users legitimately exit deprecated systems through escape hatches. Those exits are small, per-user, and spread over time. One transaction that empties many assets is not.

## Response and outcome
- No pause was possible because the contracts are immutable. Nothing was recovered.

## References
- https://slowmist.medium.com/analysis-of-the-2-19-million-asset-theft-from-aztec-connect-d867c59b1fc6
- https://blockaid.io/blog/219m-drained-on-aztec-how-blockaid-flagged-an-exploit-before-it-happened
- https://rekt.news/aztec-connect-rekt
- https://alpha.rekt.news/aztec-bridge-rekt
- https://ambcrypto.com/aztec-network-attacked-twice-in-3-days-hacker-drains-2-21m-in-digital-assets/
- `../verified-ethereum-cases.md`
