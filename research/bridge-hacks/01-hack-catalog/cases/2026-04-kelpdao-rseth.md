> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# KelpDAO rsETH (LayerZero adapter), 2026-04-18

**Loss:** about $292M (116,500 rsETH) · **Design:** messaging (LayerZero OFT adapter with escrow on Ethereum) · **Root cause:** verifier/oracle/RPC manipulation · **Chains:** Ethereum, Arbitrum, Unichain (claimed origin) · **Status:** confirmed

## Summary
Kelp's rsETH route depended on a single verifier (a 1-of-1 DVN). LayerZero's report says Kelp had downgraded from 2-of-2. That verifier was fed by RPC nodes that had been poisoned. The poisoned nodes showed correct data to monitoring tools while feeding forged data to the verifier. A forged packet released 116,500 rsETH from the Ethereum adapter. Kelp's emergency multisig paused everything 46 minutes later. Two replays of the same packet then reverted, which prevented about $100M more loss.

## Timeline (UTC)
| Time | Event |
|---|---|
| 17:35:35 | 116,500 rsETH released from adapter `0x85d456b2…8ef3` (block 24908285) |
| 18:21:59 | `pauseAll` by emergency multisig (block 24908516), **46 minutes** later |
| ~18:26 and ~18:28 | Two replay attempts for about 40,000 rsETH revert |
| ~18:52 | Aave guardian freezes rsETH markets (77 minutes after the release) |
| ~04-22 | Arbitrum Security Council recovers 30,766 ETH |

## What failed
Verifier/oracle/RPC manipulation: a single verification path, fed by data sources that had been compromised.

## On-chain signature
- One very large release of rsETH from the adapter escrow, against an inbound packet with no matching burn on the claimed source chain.
- Collateral deposits into lending markets followed quickly.

## BridgeWatch rules that would fire
- `large_withdrawal` and `escrow_drain`: on block 24908285. A single release of this size is far outside the normal flow.
- `accounting_mismatch`: if source-chain burns are checked through an **independent** RPC provider.
- An alert within 1–2 minutes would mainly have helped downstream parties (Aave froze after 77 minutes) and the pauser, who had a margin of about 5 minutes before the replays.

## False-alarm considerations
- Large rsETH moves happen during restaking rotations, but they go to known Kelp contracts.
- **Monitor input poisoning:** this case shows monitors can be fed false "normal" data. BridgeWatch should read Ethereum state from at least two independent providers.

## Response and outcome
- Pause and Aave freeze; follow-on replays blocked.
- 30,766 ETH recovered through the Arbitrum Security Council. The share of total loss is not stated in sources.
- Attribution reports name a DPRK-linked group (NK News).

## References
- https://www.theblock.co/post/397988
- https://www.galaxy.com/insights/research/kelpdao-layerzero-exploit-defi
- https://thedefiant.io/news/hacks/layerzero-s-incident-report-says-kelp-downgraded-from-2-of-2-to-1-of-1-before-usd292m-exploit
- https://www.coindesk.com/tech/2026/04/20/kelp-dao-claims-layerzero-s-default-settings-are-what-actually-caused-the-usd290-million-disaster
- https://nknews.org/pro/north-korean-hackers-linked-to-290m-heist-from-cryptocurrency-platform/
- `../verified-ethereum-cases.md`
