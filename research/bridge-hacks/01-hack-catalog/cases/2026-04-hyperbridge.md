> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Hyperbridge token gateway, 2026-04-13

**Loss:** reported as $237K at first. It rose to about $806K once a separate contract's loss of about 245 ETH (about $561K) was added, and then to **about $2.5M** total realised across four chains. See `../open-questions.md` §3. · **Design:** messaging (token gateway) · **Root cause:** message/proof forgery · **Chains:** Ethereum, Base, BSC, Arbitrum · **Status:** confirmed

## Summary
A forged cross-chain message passed Hyperbridge's proof handling. As a result, the gateway minted 1 billion bridged DOT on Ethereum and released WETH. Liquidity for bridged DOT was thin, so only a small amount could be sold, but follow-on actions hit other tokens and chains. Hypernative says it flagged the main exploit in the same minute it happened. The freeze still came more than 70 minutes later.

## Timeline (UTC)
| Time | Event |
|---|---|
| 03:02:11 | First theft: WETH out of TokenGateway `0xfd413e3a…b6de` (block 24868029) |
| ~03:40 | Test transaction about 15 minutes before the main exploit (Hypernative) |
| 03:55:23 | 1B bridged DOT minted (block 24868295); Hypernative alert in the same minute |
| 04:20, 04:26, 04:33, 04:51, 05:07 | Follow-on actions against other tokens (Hypernative) |
| > 70 min after 03:55 | Gateway frozen |

## What failed
Message/proof forgery. Third-party analyses point to a missing check in proof handling and a challenge period set to zero.

## On-chain signature
- WETH outflow from the gateway.
- Then a 1B-token mint with no source-chain lock, dumped into small DEX pools.
- Repeated actions over about 2 hours.

## BridgeWatch rules that would fire
- `large_withdrawal` and `escrow_drain`: at 03:02:11 on the WETH release, if the gateway's WETH balance has a baseline.
- `accounting_mismatch`: at 03:55:23. The minted supply jumped by orders of magnitude.
- An alert with an acknowledgement step could have shortened the 70-minute gap in which follow-ons ran.

## False-alarm considerations
- Gateway balances are often small, so ratio-based rules fire easily on them. Use absolute-USD floors.
- Supply changes on wrapped tokens are routine. A billion-unit mint is not.

## Response and outcome
- Gateway frozen.
- Compensation proposed through a token backstop and a DOT recovery loan, under community discussion.
- Nothing has been reported as recovered from the attacker.

## References
- https://www.hypernative.io/blog/how-three-compounding-failures-let-an-attacker-mint-1-2b-in-bridged-tokens
- https://decrypt.co/364588/polkadot-ethereum-bridge-hack-losses-10x-worse-team-admits
- https://cointelegraph.com/news/hacker-steals-237k-1b-bridged-dot-hyperbridge
- https://range.org/blog/1-billion-tokens-minted-inside-the-hyperbridge-gateway-exploit
- https://forum.polkadot.network/t/updated-pre-proposal-discussion-dot-recovery-loan-to-hyperbridge-exploit-victims/17552
- https://blog.verichains.io/p/hyperbridge-incident-analysis
- `../verified-ethereum-cases.md`
