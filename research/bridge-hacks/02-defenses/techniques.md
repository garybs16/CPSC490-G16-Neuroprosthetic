# Detection technique catalogue for BridgeWatch

> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

Research date: 2026-10-07. Source keys refer to `sources.md`. The "would have caught" column is **our own reasoning** from published incident facts; it was not tested by replay. Replaying these incidents should be a sprint task.

## 0. The false-alarm budget, in numbers

SonarX's target is **at most 1 false alarm per bridge per week**.
- Ethereum produces about 50,400 blocks per week (12 s slots).
- If a detector makes one independent yes/no decision per block, it needs a per-check false-positive rate of **about 2×10⁻⁵** to stay within budget.
- With 10 detectors each allowed equal shares, each needs about 2×10⁻⁶.
- Per-transfer checks on a busy bridge (thousands of transfers a day) need similar or tighter rates.

**Implication:** plain z-score thresholds (3σ gives about 1.3×10⁻³ false positives under a Gaussian, and real flows are heavy-tailed) will blow the budget. That leaves three options:
- **(a)** exact invariants, which have near-zero false positives by construction;
- **(b)** very high thresholds on robust statistics;
- **(c)** paging only when **two or more independent signals agree**. This is the Forta combiner idea [F3], and BlockSec's "risk level plus rules" [B1].

## 1. Catalogue

Legend:
- **FA risk** = false-alarm risk. Low means under 1 per bridge-month expected; Med means about weekly without tuning; High means daily or more without combination.
- **Latency** is measured from the attack transaction's inclusion.

| # | Technique | Signal | Catches | FA risk | Latency | Data needed | Would have caught (reasoned) |
|---|---|---|---|---|---|---|---|
| T1 | **Release-without-deposit invariant** (deposit↔release matching) | Each release or mint on chain B must match a deposit or burn on chain A: same token, amount ± fee, recipient, nonce or message hash, and after source finality [A1][A2] | Forged messages and proofs, compromised validators/keys, replay | **Low**. Live false alarms came from indexing bugs and RPC gaps [A2] | Seconds after inclusion (provisional); confirmed after finality | Both chains' bridge events plus Transfer logs; per-bridge decoder; finality constants | Wormhole 2022 (mint with no deposit) [W3]; Nomad (unbacked `process()` calls) [A1]; Ronin 2022 and 2024 [A1][RN2]; Harmony; BNB Token Hub (forged proof); Poly 2023; Hyperbridge (mint with no lock) [H2]; KelpDAO (forged packet, no Unichain burn) [KD2] |
| T2 | **Supply ≤ collateral (aggregate solvency)** | Wrapped supply on all destination chains ≤ locked collateral on the source, checked every block | Same as T1 plus slow leaks and salami slicing; robust to matching errors | **Low** (watch decimals, rebasing tokens, fees) | Per block | Total supply on each chain; vault balances | All of the above. KelpDAO ended with about 112k rsETH unbacked [KD2] |
| T3 | **Release before source finality / challenge window** | dst_ts < src_ts + finality, or challenge period | Fraud-window bypass; optimistic-bridge abuse | Low | Instant | Per-bridge finality and window constants | Nomad (87 s vs 30 min) [A1] |
| T4 | **Single transfer vs TVL / vault share** | Outflow ≥ X% of vault balance in one transaction, or ≥ a known per-transaction cap | One-shot drains | Low–Med (rebalancing by the team or market makers) | Instant | Vault balances; known operational addresses | Wormhole (120k wETH), KelpDAO (116.5k rsETH, about 18% of supply), Ronin 2022 (173.6k ETH), BNB (1M BNB ×2), Ronin 2024 (hit the cap) [RN1] |
| T5 | **Rate / velocity limit (sliding window)** | Net outflow per vault over 1 h / 6 h / 24 h exceeds a quota; Wormhole Governor-style USD pricing [W1]; net flow as with Axelar and Osmosis [AX1][R2] | Multi-transaction drains, copycat swarms | Med. Osmosis charts show legitimate spikes hitting daily quotas [R4] | Minutes | USD prices with a floor; vault flow history | Nomad (960 txs over hours) [N3]; Harmony (11 txs in about 18 min) [HA1]; Orbit; Multichain |
| T6 | **Seasonal baseline: hour-of-day / day-of-week robust z** | Outflow per hour vs median and MAD for that hour-of-week slot; EWMA for trend | Unusual volume relative to *this* bridge's rhythm (the proposal's core idea) | Med–High alone (heavy tails, launches, airdrops, market crashes) | 1 h bucket, or a rolling sub-hour window | 8–12 weeks of history per vault | Large drains yes. Small-bridge drains maybe. Gives context for others. Should never page alone |
| T7 | **Burst / clone detection** | Many transactions with near-identical calldata to the same function from many fresh addresses within minutes | Copycat free-for-alls | Low–Med (airdrop claims, batch relayers) | Minutes | Calldata hashes with recipient and amount masked; address age | Nomad: 300+ addresses copied the exploit calldata [N2][N3] |
| T8 | **Recipient reputation** | Release recipient or caller is new (under 24 h old), Tornado/Railgun-funded, a known exploiter, or a just-deployed unverified contract | Attacker-controlled destinations | High alone (privacy users, new wallets) → **use as a multiplier** | Instant | Address first-seen, funding source labels, sanction and exploiter lists (Forta bots, Range, TRM) [F1][R1][TR1] | Wormhole attacker funded via Tornado [W3]; Hyperbridge attacker funded via Railgun and Synapse 33 days earlier [R1] |
| T9 | **Admin / config change monitor** | Owner, pauser, threshold, validator-set, DVN/ISM, challenge period, rate-limit admin, implementation (upgrade) changes | Pre-conditions for exploits; key compromise; rug pulls | **Low** (rare events; known maintenance windows) | Instant | ABI of admin events per bridge; proxy `Upgraded` events | Nomad (bad upgrade set zero root) [N1]; Ronin 2024 (upgrade 48 min before exploit) [RN2]; Kelp DVN 2-of-2 → 1-of-1 [KD3]; Hyperbridge admin change with 0 challenge period [H2]; Orbit (firewall change by ex-employee) [OR1] |
| T10 | **Failed-transaction / probe detection** | Spike in reverted calls to bridge functions; tiny "test" transfers from new addresses | Attacker rehearsal | Med–High → use as context | Instant | Includes failed transactions (trace or receipt status) | Nomad first attempt failed ($350k gas) [N2]; Multichain $2 test transactions [C1][MC1]; Hyperbridge $500 test tx 15 min early [H2]; KelpDAO reverted retries at 18:26/18:28 [KD1] |
| T11 | **Mempool / pre-confirmation simulation** | Simulate pending transactions against state; flag ones that would break T1/T2/T4 | Detection before inclusion | Med | Before the block (if the attacker uses the public mempool) | Mempool access, fork simulation | Partial. Many attackers use private relays; Forta has a FlashBots-detector bot [F1]. Expensive for a student team |
| T12 | **Multi-signal correlation (combiner)** | Page only if severity score ≥ threshold, built from correlated signals on the same address, vault or time window | Cuts false alarms from T6/T8/T10 | **Lowest** for the medium-strength signals | Minutes | Output of the other detectors | Forta claims 80–83% of attacked protocols saw zero false alarms in 60 days [F7][F5] |
| T13 | **Cross-venue / downstream signals** | Wrapped-token depeg on DEXes, sudden lending deposits of the bridged token (rsETH into Aave), CEX deposit of bridged tokens | Cash-out stage | Med | Minutes | DEX prices, lending events, labelled CEX deposit addresses | KelpDAO rsETH borrowed against on Aave [KD2]; Hyperbridge DOT dumped on DEXes [H2] |
| T14 | **Data-health monitor** (not a security alert) | Block lag, missing blocks, RPC disagreement, decoder failure rate | Prevents false alarms and silent blind spots | n/a | Continuous | Two or more RPC providers per chain | Tenderly lag and skipped blocks [T1]; Wormhole live audit: all 103 alerts were tooling errors [A2]; KelpDAO's poisoned RPC showed correct data to monitors but forged data to the DVN [KD3] |

## 2. Severity tiers and paging policy (proposed)

| Tier | Trigger (examples) | Action | Expected rate |
|---|---|---|---|
| **P1 Critical (page now)** | T1/T2 violation ≥ $X (provisional at inclusion) **or** T4 ≥ 5% of vault **plus** any second signal (T8/T10/T9 within 24 h) | Phone/Slack page to on-call; plain-sentence summary; attacker addresses; one-click export for freeze requests | Under 1 per bridge per month |
| **P2 High (page in business hours, or immediately if another tier fires)** | T9 admin/config change; T5 quota breach; T7 burst | Slack channel plus dashboard banner | About 1 per bridge per week, mostly expected maintenance (acknowledge with a reason) |
| **P3 Info (no page)** | T6 seasonal anomaly alone; T8/T10 alone; T13 | Dashboard only; feeds the T12 score | Unlimited |
| **Ops (to the team, not the sponsor)** | T14 data health | Suppress P1/P2 from the affected chain until healthy; mark the dashboard "degraded" | — |

Rules:
1. A **single statistical signal never pages**. Only invariants, or ≥2 correlated signals.
2. **Provisional then confirmed.** Page at inclusion with "unconfirmed (pre-finality)". Auto-resolve if a reorg removes it.
3. **Count false alarms per bridge**, with a reason code for each: detector error, benign trigger, or data error (after Alahmadi et al. [D1] and Forta's contextual precision [F4]).
4. **Allowlist** the bridge team's own rebalancing and operations addresses, and known test tokens [A2].

## 3. Technique × incident coverage matrix (reasoned)

| Incident | T1 | T2 | T3 | T4 | T5 | T7 | T8 | T9 | T10 |
|---|---|---|---|---|---|---|---|---|---|
| Ronin 2022 (keys, $600M+) | ✔ | ✔ | | ✔ | ✔ | | | | |
| Wormhole 2022 (forged mint) | ✔ | ✔ | | ✔ | | | ✔ | | |
| Harmony 2022 (keys) | ✔ | ✔ | | | ✔ | | | | |
| Nomad 2022 (bad upgrade, copycats) | ✔ | ✔ | ✔ | | ✔ | ✔ | | ✔ | ✔ |
| BNB Token Hub 2022 (forged proof) | ✔ | ✔ | | ✔ | | | | | |
| Multichain 2023 (MPC keys) | ? (direct vault withdraws, not bridge releases) | ✔ | | ✔ | ✔ | | | | ✔ |
| Poly Network 2023 (3-of-4 multisig) | ✔ | ✔ | | | | | | | |
| Orbit 2023 (multisig/keys) | ? | ✔ | | ✔ | ✔ | | | ✔? | |
| Ronin 2024 (bad upgrade) | ✔ | ✔ | | ✔ (at cap) | | | | ✔ | |
| Hyperbridge 2026 (forged proof, admin) | ✔ | ✔ | | | | | ✔ | ✔ | ✔ |
| KelpDAO 2026 (1-of-1 DVN, RPC poison) | ✔ | ✔ | | ✔ | | | | ✔ (earlier DVN change) | ✔ |

**Note on key-compromise drains (Multichain, Orbit).** When the attacker signs a direct transfer out of a vault (an EOA, MPC or multisig vault) instead of calling the bridge's release function, T1 event-matching may not fire. The **vault-balance version** (T2, T4, T5) still does. **BridgeWatch should therefore monitor vault balances directly, not only bridge events**, which also matches the proposal's "money leaving each bridge vault" framing.
