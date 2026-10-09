> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Harmony Horizon Bridge, 2022-06-23

**Loss:** about $100M · **Design:** lock-mint, 2-of-5 multisig · **Root cause:** key/signer compromise · **Chains:** Ethereum, BSC, Harmony · **Status:** confirmed

## Summary
The Ethereum side of Horizon was guarded by a 2-of-5 multisig. Two signer keys were compromised. The same two signers then approved a series of withdrawals that emptied the ETH, BUSD and ERC-20 escrows, and the BSC side was hit as well. Harmony announced the incident many hours after the funds moved.

## Timeline (UTC)
| Time | Event |
|---|---|
| 11:06:46 | First theft from the Horizon ETH escrow (block 15012646, tx `0x27981c72…4c97`) |
| Following minutes | Further multisig-confirmed withdrawals from the BUSD and ERC-20 escrows |
| > 14 h later | Public announcement (rekt) |

## What failed
Key/signer compromise. A low 2-of-5 threshold made two keys enough.

## On-chain signature
- Multisig `confirmTransaction` calls by the same two signers, each followed immediately by a vault-sized transfer to one address.
- This happened across three escrow contracts (`0xf9fb1c50…a8a6`, `0xfd53b1b4…c628`, `0x2dccdb49…0857`).

## BridgeWatch rules that would fire
- `escrow_drain`: on each escrow's first large transfer.
- `large_withdrawal`: on each transfer.
- `withdrawal_burst`: several large releases from related contracts within minutes.
- `outflow_spike`: in the first block.
- Watching all three escrows as one "bridge" lets the burst rule correlate them.

## False-alarm considerations
- Operator rebalancing between escrows uses the same multisig path. It is announced and does not send funds to a fresh external address.

## Response and outcome
- Bridge halted, and a bounty was offered (rekt).
- No funds were reported recovered. Funds were later laundered through mixers.

## References
- https://rekt.news/harmony-rekt
- https://www.certik.com/skynet-report/harmony-incident-analysis
- https://cointelegraph.com/news/breaking-harmony-one-s-horizon-bridge-hacked-for-100m
- `../verified-ethereum-cases.md`
