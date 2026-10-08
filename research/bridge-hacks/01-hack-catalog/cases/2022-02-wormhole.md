> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Wormhole Portal, 2022-02-02

**Loss:** about $326M (rekt; DefiLlama) · **Design:** messaging (guardian-signed messages) and lock-mint token bridge · **Root cause:** verification bug · **Chains:** Solana, Ethereum · **Status:** confirmed

## Summary
A flaw in Solana-side signature verification let a fake guardian approval through. As a result, 120,000 wETH was minted on Solana with no ETH locked on Ethereum. The attacker redeemed 93,750 of it for real ETH from the Ethereum token-bridge escrow and kept the rest on Solana. Jump Crypto replaced the 120k ETH within about a day, so users were made whole.

## Timeline (UTC)
| Time | Event |
|---|---|
| ~17:58 | Preparation on Solana (PostQuantum timeline) |
| ~18:24 | 120k wETH minted on Solana with no matching Ethereum lock |
| 18:26:03 | First ETH release from Ethereum token bridge `0x3ee18b22…a585` (block 14128223) |
| 18:33:32 | Last of the Ethereum redemptions (about 7.5 minutes of Ethereum-side outflow) |
| ~19:07 | Imbalance noticed |
| ~19:33 | Network shut down for maintenance |
| < 24 h | Jump Crypto deposits 120k ETH to restore backing |

## What failed
Verification bug: the guardian-signature check on Solana could be satisfied without real guardian signatures.

## On-chain signature
- On Solana: a mint with no Ethereum lock behind it.
- On Ethereum: two very large ETH releases from the token bridge within about 7 minutes, to an address that had never used the bridge before.

## BridgeWatch rules that would fire
- `large_withdrawal` and `escrow_drain`: within one block of 18:26:03. A single release of tens of thousands of ETH is far outside the per-hour baseline.
- `accounting_mismatch`: from 18:24, if Solana supply is reconciled against the Ethereum escrow. This would have fired before any Ethereum loss.
- `outflow_spike`: in the same block.

## False-alarm considerations
- Large ETH redemptions by market makers do happen, but releases of this size were well beyond any prior single withdrawal.
- On Ethereum alone, the theft looks like a valid redemption. Only the size gives it away until cross-chain accounting exists.

## Response and outcome
Network halted about 69 minutes after the mint. A $10M bounty was offered and not taken. Backing was restored by Jump, so user funds were 100% restored, but not from the attacker. This incident led Wormhole to build its "Governor" rate limiter.

## References
- https://rekt.news/wormhole-rekt
- https://postquantum.com/crypto-security/wormhole-bridge-hack/
- https://github.com/wormhole-foundation/wormhole/blob/main/whitepapers/0007_governor.md
- https://defillama.com/hacks
