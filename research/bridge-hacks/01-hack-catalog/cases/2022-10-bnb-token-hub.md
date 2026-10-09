> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# BNB Chain Token Hub, 2022-10-06

**Loss:** 2M BNB minted (about $570M face value). Only about $100–137M left BSC. · **Design:** lock-mint with light-client proof (native system contract) · **Root cause:** message/proof forgery · **Chains:** BNB Beacon Chain, BSC · **Status:** confirmed

## Summary
The BSC cross-chain system contract accepted a forged proof of a deposit on BNB Beacon Chain. As a result, it credited 1M BNB, twice. The attacker posted the BNB as lending collateral and bridged some of the borrowed value away. BSC validators then halted the chain, which stranded most of the minted BNB.

## Timeline (UTC)
| Time | Event |
|---|---|
| 18:26:46 | First 1M BNB credited by system contract `0x…2000` (bsc block 21957793) |
| 20:43:18 | Second 1M BNB credit (136 minutes later) |
| ~2 h after the second mint | Validators coordinate a chain halt (rekt) |
| Next day | Patched client released; chain resumes |

## What failed
Message/proof forgery: the proof verifier accepted a crafted proof.

## On-chain signature
- A native-token credit from the cross-chain system contract to a fresh address, with no corresponding lock on the source chain.
- Immediately afterwards, the BNB was deposited into a lending market and borrowed against.
- There is no escrow outflow at all, because this is a mint.

## BridgeWatch rules that would fire
- `accounting_mismatch`: on the first credit, if BSC-side mints are reconciled against Beacon-side locks.
- `large_withdrawal`: only if BridgeWatch treats a system-contract credit as an "outflow". 1M BNB is far above any normal transfer.
- The vault-outflow rules (`escrow_drain`, `outflow_spike`) would **not** fire, because no vault balance falls.

## False-alarm considerations
- Big native-token credits from system contracts are rare. Treating the mint path as an outflow channel gives near-zero false positives at this size.

## Response and outcome
- All validators halted BSC, a patch shipped, and about $7M was frozen.
- About $430M stayed on BSC under the attacker's control and could not move. This is the largest "limited" outcome on record.

## References
- https://rekt.news/bnb-bridge-rekt
- https://nansen.ai/research/bnb-chains-cross-chain-bridge-exploit-explained
- https://www.theblock.co/post/175437/biance-bnb-chain-is-back-up-after-bridge-exploit
- `../verified-ethereum-cases.md` (non-Ethereum section)
