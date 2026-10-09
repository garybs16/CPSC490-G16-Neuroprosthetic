> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Orbit Bridge, 2023-12-31

**Loss:** about $81.7M · **Design:** lock-mint, multisig · **Root cause:** key/signer compromise (a former insider is suspected of weakening access controls) · **Chains:** Ethereum, Orbit · **Status:** confirmed

## Summary
On New Year's Eve, signer-authorised withdrawals emptied Orbit Bridge's Ethereum escrow of USDT, USDC, ETH, WBTC and DAI in about 18 minutes. The bridge was deactivated about an hour later. Ozys, the operator, later said a former security lead had weakened firewall policy before leaving. Nothing was recovered.

## Timeline (UTC)
| Time | Event |
|---|---|
| 18:30:11 – 20:40:35 | Five dust "test" releases from the escrow ($9.71, $9.71, $3.92, $1.32 and $514) to the four addresses that later received the thefts: txs `0x5ee196af…7c6d`, `0x2f1c3133…2d1e`, `0x09c567d7…28b4`, `0xd082ca50…96a5`, `0x9e514aca…b589` (from `prototype/bridgewatch/data/orbit-2023.json`; two re-checked on-chain) |
| 20:52:47 | Unauthorised access logged (rekt) |
| 21:07:59 | First theft from escrow `0x1bf68a9d…b489a` (block 18908035) |
| 21:25:35 | Last theft (block 18908123); drain took about **18 minutes** |
| 22:21:35 | Bridge deactivated on-chain (block 18908403), **74 minutes** after the first theft |
| 2024-01-01 | Orbit asks exchanges to freeze funds |

## What failed
Key/signer compromise: the attacker obtained enough signer authority to release funds. It is reported to have been enabled by an insider's changes to access controls.

## On-chain signature
- Dust "test" releases to the future theft addresses 27 min to 2 h 38 min before the first theft.
- A short series of multisig-signed withdrawals, one per asset (DAI, WBTC, USDC, USDT), each to a different fresh address that had received a dust test release earlier.

## BridgeWatch rules that would fire
- `large_withdrawal` and `escrow_drain`: at 21:07:59, on the first transfer.
- `withdrawal_burst`: by the second or third asset.
- `outflow_spike`: the same hour.
- An alert at about 21:08 would have come roughly 73 minutes before the deactivation. Most value was already gone by 21:25, so the window that mattered was about 17 minutes.

## False-alarm considerations
- Holiday timing means low baseline traffic, so the rule needs a minimum absolute size, not just a ratio, to avoid noisy alerts on quiet days.

## Response and outcome
- Bridge deactivated and exchanges asked to freeze.
- Funds were not recovered.

## References
- https://www.rekt.news/orbit-bridge-rekt
- https://forklog.com/en/former-orbit-bridge-employee-suspected-of-aiding-80-million-attack/amp
- https://cointelegraph.com/news/cross-chain-protocol-orbit-bridge-suffers-exploit-hack
- `../verified-ethereum-cases.md`
