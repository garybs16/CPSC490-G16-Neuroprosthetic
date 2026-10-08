> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Liquid Network federation peg, 2026-09-06

**Loss:** about 4,000 BTC (about $320M), roughly 95% of the federation wallet. About 3,400 BTC was returned. · **Design:** mpc-custody (federated two-way peg) · **Root cause:** verification bug in node software. The sidechain could mint L-BTC that nothing backed, and that L-BTC was then pegged out for real BTC. No keys were compromised. · **Chains:** Liquid, Bitcoin · **Status:** confirmed

## Summary
Liquid's federation holds BTC that backs L-BTC on the sidechain. Investigators found a software bug in Elements, the sidechain's code, that allowed L-BTC to be minted with no BTC behind it. Liquid says the peg-outs went through SideSwap's authorisation key, though that key itself was never compromised. Through those peg-outs, about 4,000 BTC left the federation wallet. Self-described whitehats returned 3,400 BTC and kept about 598.5 BTC. A Ledger executive called that extortion.

## Timeline (UTC)
| Time | Event |
|---|---|
| 2026-09-06 | Unbacked L-BTC minted and pegged out; about 95% of the federation wallet leaves |
| Following day(s) | Bridge nodes disabled; exchanges asked to suspend L-BTC deposits and withdrawals |
| "Monday" after | 3,400 BTC returned |
| "Thursday" after | Block production resumes without transactions |

No minute-level times were found in public sources.

## What failed
Verification bug: the issuance rules on the sidechain.

## On-chain signature
- On Bitcoin: peg-out transactions from the federation wallet far above normal size, quickly removing most of its balance.
- On Liquid: L-BTC supply above the BTC held in the peg.

## BridgeWatch rules that would fire
These are conceptual. BridgeWatch's prototype is EVM-only.
- `escrow_drain` and `large_withdrawal` on the federation's Bitcoin addresses.
- `accounting_mismatch` on L-BTC supply versus the peg wallet.
- This incident is the strongest argument for adding non-EVM vaults later in CPSC 491.

## False-alarm considerations
- Federation wallet rotations move large balances between federation-controlled scripts. They need an allow-list of the federation's own addresses.

## Response and outcome
- Peg halted; about 85% returned.
- About 598.5 BTC (about $47M) was retained by the attackers.

## References
- https://securityaffairs.com/198697/cyber-crime/hackers-drain-320-million-from-liquid-network-then-return-most-of-it.html
- https://onrampbitcoin.com/resources/media/liquid-networks-320m-hack-explained
- https://oodaloop.com/briefs/cyber/bitcoin-network-used-by-exchanges-hit-by-320-million-exploit/
- https://www.bit.com/knowledge-hub/liquid-network-hack-2026
