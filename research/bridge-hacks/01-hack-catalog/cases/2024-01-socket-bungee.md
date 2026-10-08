> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Socket / Bungee, 2024-01-16

**Loss:** about $3.3M from about 231 wallets · **Design:** router/aggregator · **Root cause:** user-approval abuse (a newly added route lacked input validation) · **Chains:** Ethereum and others · **Status:** confirmed

## Summary
Three days before the incident, Socket added a new route to its gateway. That route did not validate its inputs, so the gateway could be made to spend tokens that users had approved to it. The gateway's own balance was never the target. User wallets were. The route was disabled 14 minutes after the first theft, and most of the ETH was later recovered.

## Timeline (UTC)
| Time | Event |
|---|---|
| 2024-01-13 06:23:47 | New route added to gateway `0x3a23f943…7a5` (block 18996162) |
| 2024-01-16 19:11:23 | First theft (block 19021454) |
| 19:25:47 | Route disabled on-chain (block 19021526), 14 minutes later |
| ~1 h | Public pause notice (a community researcher flagged it earlier) |
| Following days | 1,032 ETH (about $2.3M) recovered |

## What failed
User-approval abuse, introduced by a faulty route addition.

## On-chain signature
- The gateway calls `transferFrom` on many unrelated user wallets.
- Tokens move from users to an unknown address.
- The gateway's own balance does not change.

## BridgeWatch rules that would fire
- **None of the vault-outflow rules.** No escrow was drained.
- `config_change`: on the route addition three days earlier. A reviewer might have caught the unvalidated route, but this is a weak signal on its own.
- This is a documented blind spot. Catching it needs approval-spend monitoring: watching `Transfer` events where `from` is a user and the spender is the gateway.

## False-alarm considerations
- Routers legitimately call `transferFrom` on users constantly. The anomaly is the *destination*: not a bridge, a DEX or the user.

## Response and outcome
- Route disabled within 14 minutes.
- About 70% recovered (1,032 ETH).

## References
- https://www.theblock.co/post/272986/socket-says-bungee-protocol-exploited
- https://www.theblock.co/post/273964/socket-ether-recovery-bungee-exploit
- https://defillama.com/hacks
- `../verified-ethereum-cases.md`
