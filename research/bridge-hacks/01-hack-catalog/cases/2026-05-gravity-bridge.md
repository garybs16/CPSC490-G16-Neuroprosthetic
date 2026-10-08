> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Gravity Bridge, 2026-05-30

**Loss:** about $5.4M (about 4.3M USDC, 274 WETH, 434K USDT, 14.164 PAXG) · **Design:** lock-mint (Cosmos validator-signed Ethereum contract) · **Root cause:** key/signer compromise per most reports. QuillAudits instead describes a fabricated token-mapping claim accepted by the bridge, so this is **disputed**. · **Chains:** Ethereum, Gravity Bridge (Cosmos) · **Status:** confirmed

## Summary
In about three minutes, the Ethereum contract of Gravity Bridge released four assets to one recipient. Early reports pointed to a compromised signing key. A later third-party analysis says a newly registered validator was involved and that a forged token-deployment claim was accepted. Validators halted the chain and orchestrators. No official post-mortem had appeared when this was written.

## Timeline (UTC)
| Time | Event |
|---|---|
| 05-29 | New validator registered (QuillAudits) |
| 02:27:59 | First theft from bridge `0xa4108aa1…d906` (block 25205201) |
| 02:31:11 | Last theft, USDT (block 25205217); drain took about **3.2 minutes** |
| Same day | On-chain analyst flags it; PeckShield confirms; validators halt |

## What failed
Signer or claim verification. See `../open-questions.md` §4.

## On-chain signature
- Four releases, one per asset, each draining most of that asset's balance, within 16 blocks.
- The recipient had no deposit history.

## BridgeWatch rules that would fire
- `large_withdrawal` and `escrow_drain`: at block 25205201.
- `withdrawal_burst`: by the second asset.
- `outflow_spike`: on the same block.
- The drain finished in about 3 minutes, so only a detector working at block level is useful here.

## False-alarm considerations
- Gravity Bridge's baseline outflow is low, so ratios explode on small transfers. Use USD floors.

## Response and outcome
- Bridge halted by validators.
- No recovery reported. Funds were partly routed through exchanges.

## References
- https://whale-alert.io/stories/dbbb01f14e3f8d/Gravity-Bridge-halts-Ethereum-Cosmos-bridge-after-reported-54M-exploit
- https://quillaudits.com/blog/hack-analysis/gravity-bridge-demon-mapping-poisoning
- https://blockchain.news/news/gravity-bridge-halts-54m-exploit
- https://regional-front.cointelegraph.com/news/cosmos-based-gravity-bridge-halts-bridge-after-reported-54m-exploit
- `../verified-ethereum-cases.md`
