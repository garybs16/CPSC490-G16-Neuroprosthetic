# Protocol-level defenses that limit bridge damage

> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

Research date: 2026-10-07. Source keys refer to `sources.md`.

**Why this matters for BridgeWatch.** These controls set the **time budget** a monitor has. A 24-hour delay gives a human time to react to a page. A 1-of-1 verifier with instant release gives none. BridgeWatch should also **watch the configuration of these controls**, because weakening them is itself a warning sign: KelpDAO went from 2-of-2 to 1-of-1 DVNs, and Hyperbridge had a zero challenge period.

## 1. Rate limits, volume caps and delays

| Mechanism | How it works | Who controls it | Evidence it helped |
|---|---|---|---|
| **Wormhole Governor** | Two rules per chain. (1) A USD-denominated daily limit over a sliding 24-hour window. Small transfers go through while there is headroom and queue otherwise. (2) Transfers at or above a "big transaction" threshold always wait 24 hours. Prices take the higher of a hardcoded floor and CoinGecko. Only listed tokens count. 7 of 19 Guardians can delete a queued message, and 13 of 19 can release one early [W1]. Since 2024, stablecoin inflows offset outflows ("flow canceling") [W2] | Guardians; parameters set by governance | Designed after the Feb 2022 Wormhole hack, where 120k wETH was minted and mostly moved out within about 10 minutes [W3]. I found **no public case** of the Governor stopping a real exploit. Its main documented cost is congestion: several chains often sit near 100% of their limit [W2] |
| **Chainlink CCIP token-pool rate limits** | Token buckets per pool, per remote chain and per direction (capacity plus refill rate). A transfer larger than capacity is always rejected. Inbound limits are set 5–10% above outbound [CL1] | `rateLimitAdmin` role; changes take effect immediately [CL1] | No public exploit case. The limits are rejections, not queues |
| **CCIP Risk Management Network (RMN)** | Originally an independent Rust implementation, run by separate operators, that re-derived Merkle roots and could "curse" (halt) lanes [CL2]. As of CCIP 2.0 (Sept 2026), its automated off-chain role is **no longer active**. Only the on-chain curse switch remains, and institutions can add their own verifiers (CCVs) [CL3][CL4] | Chainlink / RMN contract owners | n/a. Shows that independent verification is expensive to keep running |
| **Axelar ITS flow limits** | Caps **net** flow (in minus out) per token per 6-hour epoch. A transfer that would break the cap reverts with `FlowLimitExceeded` [AX1]. Design aim: a compromised chain can't pull out more than was deposited [AX2] | Token operator / flow-limiter role | No public case found |
| **Osmosis IBC rate limits** (built with Range) | Net-flow quota as a % of channel value, over daily, weekly or monthly windows, per channel and denom [R2]. Added in Oct 2022 after the BNB Token Hub hack and the Dragonberry bug [R2] | 3-of-6 multisig [R3] | Historical charts show some **legitimate** inflows hitting daily quotas (USDC, STARS, CRO) [R4]. That is a direct false-alarm and friction lesson |
| **Circle CCTP V2 Fast Transfer allowance** | Circle attests at soft finality. The total of fast mints in flight is capped by a USD allowance, which refills at hard finality. Standard transfers wait for hard finality [CC1] | Circle | Not an exploit control as such, but caps exposure to reorgs |
| **Celer cBridge** | Epoch volume cap on the destination chain, plus a `DelayedTransfer` contract (threshold and delay period) [CE1] | Governance / pausers [CE2] | An academic SoK calls Celer's delay, volume control and pause "effective" [P3] |
| **Ronin bridge withdrawal limit** | Per-transaction / daily withdrawal cap | Ronin / Sky Mavis | **Aug 2024:** an uninitialized operator weight meant any signature passed. The attacker (a whitehat MEV bot) could take only about 4,000 ETH and 2M USDC. A third-party analysis estimates the limit saved about $72M [RN1][RN2] |
| **ERC-7265 circuit breaker (draft)** | A standard interface that halts or delays protocol-wide outflows when a percentage-based rate is exceeded. It can either revert or hold funds during a cooldown [E1] | Protocol admin. Critics asked for a timelock on admin powers [E1] | Proposal stage (2023). I could not confirm final status |

## 2. Verification-layer configuration (stop forged messages)

| Mechanism | Key facts | Lesson for BridgeWatch |
|---|---|---|
| **LayerZero DVNs** | Configured as X-of-Y-of-N: all required DVNs must sign, plus a threshold of the optional ones. The docs call 1-of-1 the weakest option. They recommend 2-of-3 for medium value and 3-of-3 plus 1-of-2 for critical assets [LZ1] | KelpDAO ran 1-of-1 (LayerZero Labs only) and lost about $292M on 2026-04-18 [KD1]. LayerZero says the app had moved down from 2-of-2. Kelp disputes this and blames defaults [KD3]. Reports suggest about 40–47% of LayerZero apps ran 1-of-1 [KD3]. LayerZero now refuses to sign for 1-of-1 apps [KD1]. **A DVN or threshold change event is a high-value monitor** |
| **Hyperlane ISMs** | Per-app Interchain Security Module. Options include Multisig (m-of-n validators), Aggregation (m-of-n ISMs) and Routing (ISM chosen per origin chain) [HY1] | Same lesson: monitor ISM address and threshold changes |
| **Across (UMA optimistic oracle)** | A dataworker proposes refund bundles. Anyone can dispute during a liveness window (about 1 hour per UMA; one guide says about 2 hours) [AC1][AC2] | Bundle proposals and disputes are on-chain events a monitor can track |
| **Optimistic rollup canonical bridges (OP Stack)** | 7-day proof maturity delay before finalizing a withdrawal. An extra finality delay after a dispute game resolves, during which the Guardian can blacklist the game. The Guardian can also pause the portal [OP1][OP2] | The 7-day window is the strongest time buffer in the ecosystem. Detection within hours is enough |
| **Agglayer pessimistic proofs** | A ZK proof that no chain withdraws more than it deposited into the unified bridge [AG1] | The same invariant BridgeWatch should check off-chain |
| **Hyperbridge** | A zero challenge period let a forged admin change take effect instantly [H2] | Monitor challenge-period and delay parameters for changes to zero |

## 3. Pausing: who can pause and how fast it has happened

| Incident | Attack start (UTC) | Pause / halt | Time to pause | Who paused | Source |
|---|---|---|---|---|---|
| Wormhole, 2022-02-02 | 17:58 (prep), 18:24 (mint) | 19:33 network shut down; imbalance noticed 19:07 | about 69 min after mint | Wormhole guardians/team | [W3] |
| BNB Token Hub, 2022-10-06 | forged proofs, 2M BNB minted | All 44 validators halted BSC | hours (exact time not found) | Validators | [BN1][BN2] |
| Nomad, 2022-08-01 | 21:32:31 | Relayer paused; Replica ownership removed. Drain ended about 05:49 next day | hours (exact pause time not found) | Nomad team | [N1][N2][N3] |
| Harmony Horizon, 2022-06-23 | 11:06:46 | Bridge "stopped" later that day | not published | Harmony | [K2][HA1] |
| Ronin, 2022-03-23 | attack | Paused after discovery on 03-29 | **about 6 days** | Sky Mavis | [F6] |
| Poly Network, 2023-07-02 | 3-of-4 multisig compromised | Paused | about **7 hours** with no response | Poly team | [PN1] |
| Multichain, 2023-07-06 | 16:21 ($2 test), about 18:21 main | Service "stopped"; no real pause possible (MPC keys) | n/a | n/a | [MC1][MC2] |
| Socket/Bungee, 2024-01-16 | exact start not published; a researcher flagged it about 1 h before the pause notice | Paused, announced 15:15 ET. Drain had stopped about 14:47 ET | about 1 h or more | Socket team | [SO1] |
| Ronin, 2024-08-06 | 09:37:23 | 10:15:23 | **38 min** | Ronin team | [RN2] |
| Shibarium, 2025-09 | flash-loaned stake gave 10 of 12 validator keys | Staking/unstaking paused; funds moved to a 6-of-9 multisig | not published | Shiba core team | [SH1] |
| Hyperbridge, 2026-04-13 | 03:55 | Frozen after 05:07 | **over 70 min** (detected in about 0 min) | Hyperbridge | [H2] |
| KelpDAO, 2026-04-18 | 17:35 | about 18:21 pauseAll via emergency multisig. Blocked follow-up attempts at 18:26 and 18:28 | **46 min** | Kelp emergency pauser multisig | [KD1][KD2] |
| Allbridge Core, 2026-07-19 | flash-loan manipulation (Solana) | Paused 07-20 | about 1 day | Allbridge | [AB1] |
| Synapse nUSD, 2021-11 | attempted $8M drain | Validators paused all chains and reversed the transaction **before confirmation** | before loss | Synapse validators | [SY1] |

**Patterns**
- **Pause latency on record runs from about 38 minutes to days.** Even "fast" human pauses (Ronin 2024: 38 min, KelpDAO: 46 min) arrive **after** the main drain, which is usually one or a few transactions.
- Pausing saves money in three situations:
  - when the attack is **repeatable**: Kelp's follow-up attempts, Hyperbridge's later transactions, Nomad's copycats;
  - when a **rate or per-transaction limit** already capped the first hit (Ronin 2024);
  - when the attacker needs **time to cash out** (BNB: about $100–137M left of about $570M minted [BN1]).
- So a BridgeWatch alert's value is mostly in **stopping the second through Nth transactions** and **triggering freezes downstream** (Aave froze rsETH 77 min after the drain [KD2]; Circle froze $65M after Multichain [MC2]). Paging has to reach the people who hold the pause key within minutes.

## 4. Take-aways for BridgeWatch
1. Treat **admin/config events** as top-severity signals:
   - pauser, owner or threshold changes;
   - DVN or ISM swaps;
   - challenge period set to 0;
   - rate-limit admin changes;
   - upgrades.

   They are rare (few false alarms) and preceded several big losses: Nomad's bad upgrade, Ronin 2024's bad upgrade 48 minutes before the exploit [RN2], and Kelp's DVN downgrade [KD3].
2. **Model each bridge's existing limits.** A withdrawal right at a known per-transaction cap (as with Ronin 2024's roughly 4,000 ETH) or a Governor queue entry is a strong feature.
3. Where a protocol has a delay (OP 7 days, Wormhole big transactions 24 hours, cBridge DelayedTransfer), BridgeWatch can **alert on the queued or proved transaction before release**. That is the only setting where an off-chain monitor actually *prevents* loss.
