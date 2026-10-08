> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Shibarium Bridge, 2025-09-12

**Loss:** about $2.3–2.4M (The Block, ForkLog). DefiLlama lists $4.1M and rekt about $3M. · **Design:** lock-mint (validator-signed checkpoints) · **Root cause:** key/signer compromise (validator majority captured through borrowed stake) · **Chains:** Ethereum, Shibarium · **Status:** confirmed

## Summary
The attacker briefly controlled enough validator signing power, 10 of 12 signatures, to approve a fraudulent checkpoint. That checkpoint released 224.57 ETH and 92.6B SHIB from the Ethereum bridge escrow. The weakness was the bridge's trust in validator consensus; L2BEAT had flagged this risk before. Shiba Inu developers paused staking, moved funds to a multisig, and K9 Finance blacklisted the KNINE the attacker received.

## Timeline (UTC)
| Time | Event |
|---|---|
| 18:44:47 | First theft from escrow `0x6aca26bf…a4fa` (block 23348858) |
| Following hours | Staking and unstaking paused; escrow funds moved to 6-of-9 hardware multisig |
| 2025-09-16 | Project reports about $1M "neutralised" through the KNINE blacklist |

## What failed
Key/signer compromise in the sense of signer-set capture: the signatures were valid, but the signers were attacker-controlled.

## On-chain signature
- Validator stake and delegation changes, then a checkpoint signed by a new majority.
- Large ETH and SHIB releases from the escrow follow.

## BridgeWatch rules that would fire
- `large_withdrawal` and `escrow_drain`: on the first release.
- `config_change`: if validator-set or stake changes on the staking contract are watched.

## False-alarm considerations
- Validator-set churn is normal on PoS sidechains. Only a sudden, large stake shift right before a checkpoint is notable.

## Response and outcome
- Pause, custody move and token blacklist.
- About $1M neutralised. The rest was not recovered.

## References
- https://www.theblock.co/post/370536/shibarium-bridge-suffers-sophisticated-flash-loan-attack-with-2-4-million-drained
- https://news.shib.io/2025/09/16/2m-shibarium-bridge-exploit-crucial-response-now-limits-losses/
- https://alpha.rekt.news/shibarium-rekt
- https://forklog.com/en/shibarium-bridge-hacked-for-approximately-2-3-million/
- `../verified-ethereum-cases.md`
