> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# How BridgeWatch should detect bridge hacks: implementation recommendations

Research date: 2026-10-07. These are **recommendations for the team and the SonarX mentor to decide on**. Under the repo's `CLAUDE.md`, scope, objectives, design trade-offs and anything sponsor-facing are human decisions. Each recommendation names its evidence:

| Evidence | Where |
|---|---|
| Measured results | `experiments.md` (scripts and outputs in `experiments/`) |
| Attack patterns | `patterns.md` |
| False-alarm analysis | `false-alarm-patterns.md` |
| Per-case and per-window numbers | `features.csv`, `normal-stats.csv` |
| Earlier research | `../01-hack-catalog/`, `../02-defenses/`, `../03-onchain-data/` |

The team's goal, in the user's words: **"track the hack fast, and also not set off a false alarm."**

## 0. The answer in eight points

1. **Speed is already at the physical limit for outflow data. False alarms are the problem.**
   - The current prototype pages on the first confirmed theft in all 14 replayable hacks, 1–13 s after the 6th confirmation (`experiments.md` §2).
   - No outflow rule can do better. On these cases, 66% of stolen value had already left before *any* 6-confirmation alert was possible.
   - What fails is the false-alarm rate: 3.03 pages per bridge-week overall and 13.3 on liquidity pools. 12 of 29 windows exceed SonarX's budget of ≤ 1 per bridge per week.
2. **Page on vault-relative size or on agreement between signals; never on one statistical anomaly.** The recommended policy (REC, §2) gives:
   - 14/14 hacks at the same moment as today;
   - **0.105 pages per bridge-week** (29× fewer);
   - 0 pages on normal lock-box and rollup windows;
   - 0.36 per bridge-week on pools;
   - NAB-style score −83 → 93 (`experiments.md` §4).
   - **These REC figures are in-sample:** the thresholds were chosen on the same 14 hacks and 29 windows they are scored on. Leave-one-out validated the threshold-picking method (14/14 held-out hacks detected), not these exact numbers; expect worse on new data.
3. **Add the fresh-recipient signal.** It is the single most useful new feature:
   - a release ≥ 1% of the vault and ≥ $250K to an address with under $1,000 of history with the vault;
   - it went to a fresh address in 13/13 first thefts with a known recipient;
   - it is the only signal that catches the capped Ronin 2024 theft (5.8% of the vault).

   The time-split test shows that tuning thresholds on older hacks would have dropped it and missed Ronin 2024 (`experiments.md` §6).
4. **Demote the hour-of-day baseline from pager to context and second signal.**
   - It causes 67% of today's false alarms.
   - It earns its place only on the copycat-crowd pattern (Nomad), and there only as a second signal (z ≥ 10, $1M spread floor).
   - It stays on the dashboard as "normal for this hour", which is Objective 1.2.
5. **Give liquidity pools their own profile.**
   - Releases to past depositors (LPs, relayers) never count.
   - A pool pages only on ≥ 20% net hourly outflow plus a second signal.
   - In CPSC 491, move pools to deposit↔release matching.
6. **The biggest remaining gains are new data, not new thresholds** (§6):
   - native-ETH outflows: 3 cases alerted 4.7–34 min late; HECO would go from 73% to 24% gone at the alert;
   - an admin/config-change monitor: 12 incidents, $1.14B, warned before any loss;
   - cross-chain accounting: +20% of confirmed catalog loss becomes visible.
7. **Detection is not response.**
   - In the replays, the value an alert can still save is the 2nd-to-Nth asset: 28–83% of tracked theft in multi-transaction drains, 0% in single-transaction drains.
   - Recorded human reaction times were 38 min to 6 days (`02-defenses/case-studies-stopped-or-limited.md`).
   - Pages must reach someone who can pause, or an issuer who can freeze, in minutes, with the information to act (§3.4, `ideas-and-open-questions.md`).
8. **Objective 2.2 needs rewording (a human decision).**
   - "Alert before half the stolen funds leave in ≥ 4 of 5 replays" is unreachable on the prototype's 5 cases by any outflow detector: Harmony's floor is 54% and Ronin 2022's is 95% (shares of *tracked* tokens; native ETH is not in the data).
   - §7.2 proposes measurable alternatives.

## 1. Design principles (and the evidence behind each)

| # | Principle | Evidence |
|---|---|---|
| D1 | Thresholds are relative to the **vault value**, with an **absolute USD floor**. They are not relative to the hour's history. | Non-pool legitimate traffic never released ≥ 10% of a vault in a ≥ $1M release (76.5 bridge-weeks); 12/14 first thefts did. Tiny vaults (XBridge ~$14K, Across $0.47M) trip ratio rules on $3K–$80K moves (`false-alarm-patterns.md` §1–2). |
| D2 | A page needs a **conclusive single signal** or **≥ 2 independent signals** within 30 min. Single weak signals are warnings. | The Forta combiner and BlockSec's "risk plus rules" (`02-defenses/tools.md` §3). Measured: "current rules, page only if ≥ 2 agree" alone cuts pages 3.03 → 0.44 with no speed loss (`experiments.md` §4). |
| D3 | **Evaluate on every release**, streaming, at 6 confirmations. Never batch by the hour; never wait for finality. | 0 vs 6 confirmations changes only Nomad (8.2% vs 9.5%). Waiting for 12 confirmations costs Poly 2021, Harmony and Shibarium 16–38 points; waiting for finality (64) doubles Orbit's and Multichain's loss (`experiments.md` §2). Theft gaps are 2.5–9 min (`patterns.md` §1). |
| D4 | **Watch every asset the vault holds, including native ETH**, priced in USD. | The first token was not a stablecoin in 6/14 cases. Native ETH left first in 3 cases and alongside in 3 more (`patterns.md` §1, C1). |
| D5 | **Recipient context** (fresh, past depositor, dust-tested, allowlisted) separates whales from thieves better than amount alone. | 13/13 known first-theft recipients were fresh. Past-depositor exclusion cuts pool pages 2.5 → 0.97 per bridge-week before the pool profile (`experiments.md` §4). |
| D6 | **Never suppress by time of day, weekday or "market stress".** | Thefts happened at 07–23 UTC, 5 of 14 on weekends, one on New Year's Eve. The FTX month pages once under REC without any stress suppression (`patterns.md` §1; `false-alarm-patterns.md` §2). |
| D7 | **Data health gates paging.** | The Count of Monte Crypto live audit found 103/103 alerts were tooling errors (`02-defenses/academic.md` A2). Kelp's RPC poisoning showed monitors correct data (`cases/2026-04-kelpdao-rseth.md`). |
| D8 | **Count false alarms per bridge per week, with reason codes**, and judge the budget on benign triggers plus detector errors. | SonarX's target; Forta's contextual precision; Alahmadi et al. (`02-defenses/academic.md` D1, D4). |

## 2. The signal set, with defaults

Every default below was tested offline unless marked *untested*. "Pages alone" means the signal is conclusive enough to page by itself. "Second signal" means it counts toward the ≥ 2-family rule. All signals are evaluated per release, on the simulated 6-confirmation pipeline.

### 2.1 Outflow signals (tested; implement in Sprint 2–3)

| ID | Signal | Definition | Default | Role | Warm-up | Evidence and measured effect |
|---|---|---|---|---|---|---|
| S1 | `huge` | one release ≥ X of the tracked vault value just before it, and ≥ $F | X = 50%, F = $250K | **pages alone** | none | Fires on the first theft of 8 cases (Kelp, Verus, XBridge, Ronin 2022, HECO, Shibarium, Harmony, Force). Catches small vaults (XBridge $0.79M) that $1M floors miss. 0 legitimate non-pool releases met it. |
| S2 | `size` | one release ≥ X of vault and ≥ $F | X = 10%, F = $1M | **pages alone** | none | Fires on the first theft in 10 of 14 cases (11 caught overall). 0 non-pool false pages; pools excluded by profile (`experiments.md` §3). Results are flat for X between 5% and 20%. |
| S3 | `fresh` | release ≥ X of vault and ≥ $F to a recipient with < $1,000 of total prior flow with this vault; unknown recipient (WETH unwrap, native) counts as fresh | X = 1%, F = $250K | second signal | 3 days of history (production: backfill ≥ 30 days) | 14/14 detected and at floor when paging alone (0.25 pages/bw). Without it, REC misses Ronin 2024 and Nomad slips from 9.5% to 13.9%. The $1,000 threshold covers Orbit's and Multichain's dust tests. |
| S4 | `net1h` | net outflow (out − in) over the last 60 min ≥ X of the vault value at the window start, and ≥ $F | X = 10%, F = $250K | second signal (pools: see §4) | none | Replaces `escrow_drain` (5%, no floor), which alone pages 0.60/bw, 4.6 on pools. Results are flat for X between 10% and 20%. |
| S5 | `conc` | outflow to one recipient in the last 60 min ≥ X of vault and ≥ $F | X = 5%, F = $250K | second signal | none | Needed for Ronin 2024 (removing it misses that case). |
| S6 | `spike` | the prototype's hour-of-day median/MAD z on 10-min outflow, with the spread floor raised | z ≥ 10, spread floor $1M, and window outflow ≥ 0.5% of vault | second signal; dashboard band | 3 days (current) | Alone it pages 2.47/bw at z 6 and $100K. As a second signal at z 10 and $1M it keeps Nomad at its floor; without it Nomad is 13.9%. |
| S7 | `crowd` | ≥ k distinct never-seen recipients in 10 min | k = 10 | second signal | 3 days | No measurable effect on this data (Nomad is caught earlier by S3+S6). Kept for copycat swarms that lack a seasonal baseline. At k = 5 it is noisy (1.28/bw alone). |
| S8 | `drawdown` | vault value down ≥ X from its 24 h high | 30% / 60% / 90% | **severity escalation only** (re-notify an open incident) | none | Non-pool legitimate maximum is 16% (Multichain MPC); 12/14 hacks took ≥ 86%. Useless as a pool pager: it fired 108 times in Stargate's normal month. |
| S9 | `multi-token` | ≥ 2 tokens each with a release ≥ 20% of that token's balance in 10 min | — | **alert text only** | none | Too late to matter (3 of 11 at floor alone) and noisy on pools. Useful words for the human: "3 assets drained in 10 min". |
| S10 | `burst` | the prototype's release-count z | — | **dashboard only** | 3 days | Caught Nomad only, late. Noisy on busy bridges (`experiments.md` §3). |
| S11 | dust watch-list | a release < $1,000 to a never-seen address puts it on a 24 h list | 24 h | context in alert text; keeps the recipient "fresh" | none | Orbit (5 dust releases, 27 min–2 h 38 min ahead) and Multichain ($2, 1 h 49 min ahead). The "dust then large" pair occurs 0.04 times per bridge-week in normal traffic (`experiments.md` §7). |

**The recommended paging policy (REC).** Page when S1 or S2 fires, or when ≥ 2 of {S3, S4, S5, S6, S7} have fired within 30 min on the same bridge. Otherwise any single firing is a warning. Measured results:

| | Current (any rule pages) | REC |
|---|---:|---:|
| Hacks detected / at floor | 14 / 14 | 14 / 14 |
| Median latency after 6th confirmation | 4.0 s | 6.5 s (Nomad +15 s; others identical) |
| Pages per bridge-week, all 29 windows | 3.03 | **0.105** |
| Non-pool / pool | 1.79 / 13.3 | 0.073 / 0.36 |
| Normal lock-box and rollup windows | 0.19 / 0 | 0 / 0 |
| Stress windows (FTX, USDC depeg) | 4.67 | 0.13 |
| Windows above 1 per week | 12 of 29 | 1 (Across: 1 page in 4 days) |
| Warnings (dashboard) per bridge-week | — | 0.98 |
| NAB-style score (low-FP profile) | −83 | 93 |

The 30-min combination window can be 10 min: 0.091 pages/bw, same detection. Thirty is recommended to cover slower, spaced-out sweeps like Multichain, which had a 22-min gap. A team that wants the minimum can drop S7 and S9 with no measurable loss here.

### 2.2 Signals that need new data (untested here; estimated from the catalog)

| ID | Signal | Default | Role | Data needed | Evidence and expected effect |
|---|---|---|---|---|---|
| S12 | **Native-asset outflow**: run S1–S5 on native ETH (and each chain's gas token) with vault value including the native balance | same as S1–S5 | as S1–S5 | traces (internal transfers) or per-block native balance diffs of the vault | Alerts 4.7 min earlier in Poly 2021 (39% → 3.3% gone) and HECO (73% → 24%); 34 min earlier in Ronin 2024 (100% → 83%) (`experiments.md` §2). ~$92M of catalog loss is native ETH. |
| S13 | **Admin/config change**: Upgraded, AdminChanged, OwnershipTransferred, threshold, signer/validator/keeper set, DVN/ISM config, pauser, rate-limit admin, challenge period, token listing/mapping | any change on a monitored bridge contract | **pages alone** unless pre-acknowledged as maintenance (then a warning) | decoded admin events, or raw logs plus per-bridge ABIs; the list of bridge contracts (not just vaults) | 12 confirmed incidents ($1.14B) had one before the theft, 2 min to 41 days earlier. It is the only family that warned **before any loss** (Ronin 2024: 49 min; IoTeX: 18 min). Expected rate: a handful per bridge per year, mostly announced (`patterns.md` C2). |
| S14 | **Escalation pairing**: any S1–S5 within 24 h after an S13 change on the same bridge pages, even at half the thresholds | — | **pages** | S13 | Ronin 2024: the upgrade, then capped withdrawals 49 min later. IoTeX: owner transfer, upgrade, then drain. Poly 2021: keeper swap, then unlocks 2 min later. |
| S15 | **Accounting break**: a release or mint on chain B with no matching deposit or burn on chain A, after the source's finality; or wrapped supply > locked collateral | any unmatched release ≥ $250K; supply excess ≥ 0.5% and ≥ $250K | **pages alone** (provisional at inclusion, confirmed at source finality) | both sides of the bridge (decoded send/receive events with message ID or nonce), token supplies, finality constants | Catches P5 unbacked mints ($668M) and fires at or before the first release in forged-message P2 cases (Kelp, Wormhole, Verus). The near-zero false-alarm rate is from the literature, not measured here (`02-defenses/academic.md` A1/A2). It also *downgrades* the residual whale pages: a matched release is info only (`false-alarm-patterns.md` §7). |
| S16 | **Deposit event without token inflow** (one chain only) | any | page | decoded deposit events plus Transfer logs of the same tx | Qubit: a 190 ETH "deposit" moved no tokens; $80M was minted on BSC (`qubit-2022.json`). It needs only Ethereum data. |
| S17 | **Release at a known cap, or a large pending/proved withdrawal** | ≥ 95% of a per-transaction cap; a proved/requested withdrawal ≥ 10% of the vault | warning; page if combined with S13 or S3 | per-bridge caps and limits; OP-portal proven withdrawals; AFX-style request events | Ronin 2024 withdrawals sat exactly at the cap. AFX's request was visible 200 s before execution. OP's 7-day window gives days of warning (`02-defenses/protocol-defenses.md` §1–2). |
| S18 | **Heightened mode after an incident**: after any page, until a human clears it, page on any S3 ≥ $100K, and do not let the baseline learn from the incident or a refill | — | page | none | Verus was drained again 15 days after refill; Aztec 3 times in 4 days; Kelp replays came at 51 min (`patterns.md` C4). |
| S19 | **Data-health gate** (§3.3) | — | ops only; suppresses or labels pages | stream lag, gaps, reorgs, 2 providers | `02-defenses/techniques.md` T14 |

## 3. Severity tiers and paging policy

### 3.1 Tiers

| Tier | What triggers it | Where it goes | Expected rate (measured where possible) |
|---|---|---|---|
| **PAGE** (the prototype's `critical`) | S1 or S2; ≥ 2 of S3–S7 in 30 min; S13 unacknowledged; S14; S15; S16; anything in heightened mode (S18) | phone/Slack page to the on-call, the dashboard banner, and the incident record | Outflow part: **0.105 per bridge-week** measured (one per bridge every ~10 weeks). S13 adds an estimated handful a year, mostly pre-acknowledged. |
| **WARNING** | any single S3–S7; S13 pre-acknowledged; S17; a dust watch-list hit | team channel (not paging) and dashboard | 0.98 per bridge-week measured (outflow part) |
| **INFO** | S6 band excursions below z 10; S9; S10; matched (S15-backed) whale releases; stress banner | dashboard only | unlimited |
| **OPS** | data health (S19) | team channel only; labels or holds pages | — |

### 3.2 Incident and escalation rules
- **One incident per bridge.** Signals within 60 min of each other join the open incident; the notifier sends one message per incident, as the prototype already does (`prototype/README.md`, notifications).
- **Re-notify only when the incident escalates.** That means a new tier, drawdown crossing 30%, 60% or 90% (S8), a new asset leaving, or an accounting break joining.
- **An open incident puts the bridge in heightened mode (S18)** until acknowledged *and* closed with a reason code.

### 3.3 Data health gates paging
- **If ingest for the chain is unhealthy, send pages but label them `DEGRADED DATA`.** Unhealthy means lag > 50 blocks, a missing block range, providers disagreeing on balance or logs, or a price feed stale for over 10 min. Never silently drop a page.
- **Catch-up alerts keep the prototype's `LATE` label.**
- **A reorg that removes the triggering release retracts the page.** A retraction is recorded as "retracted", not as a false alarm.
- **Measured basis:** none here; the replay files are validated (`03-onchain-data/README.md`). This is the largest live false-alarm source in the literature (`false-alarm-patterns.md` §8).

### 3.4 What a page must contain (so someone can act within minutes)
Write it as one plain sentence, then the facts. An example:

> "Orbit Bridge vault released $10.0M DAI (14% of the vault, 92% of its DAI) to an address that had never received more than $10 from it; that address got a $1 test release 45 min ago. Net outflow in the last hour: 14%."

Then:
- tokens, amounts, % of vault and % of token balance;
- recipient(s) and their history;
- which signals agreed;
- the tx link;
- the vault's normal for this hour (S6 band);
- **who can act**: the bridge's pauser contact, and "USDC/USDT: issuer can freeze" (Circle froze ~$65M after Multichain);
- one-click export of attacker addresses (`02-defenses/takeaways-for-bridgewatch.md` #12).

Track time-to-acknowledge as a metric (Objective 3.2).

## 4. Per-design profiles

`bridges.json` gets a `design` field; each profile overrides the defaults.

| Profile | Applies to (examples) | Differences from the default | Measured result | Evidence |
|---|---|---|---|---|
| **lockbox** (default) | Polygon PoS, Wormhole Portal, Ronin gateway, Orbit, Poly LockProxy, HECO, Nomad router | defaults as in §2 | 0 pages in 15.4 normal bridge-weeks; 0.13/bw stress; 0.16/bw pre-hack | `experiments/out/per-design.csv` |
| **rollup** | Arbitrum, Base and OP L1 gateways | defaults; add S17 on proved-but-not-finalised withdrawals ≥ 10% of the vault | 0 pages in 11.6 bridge-weeks | `false-alarm-patterns.md` §3 |
| **oft-adapter** (LayerZero lockbox) | USDT0, rsETH adapter | defaults. Priority: S15 by packet GUID (match each release to a source-chain send), and S13 on DVN/library/delegate config | 0.13/bw (one $45M USDT0 redemption to a fresh address) | `false-alarm-patterns.md` §4; Kelp and Sandbox OFT cases |
| **pool** (liquidity / intent) | Stargate, Across spoke pool, Celer cBridge | releases to past depositors never count for S1–S3 or S5. **Pages only if net 1h ≥ 20% of the pool and ≥ $1M, and ≥ 2 families active.** S1/S2 alone are warnings. No drawdown rule. CPSC 491: S15 per fill or delivery ID | 13.3 → **0.36**/bw | `false-alarm-patterns.md` §5. Unknown miss rate on a real pool theft: none is in the replay set |
| **mpc / EOA custody** | Multichain-style MPC wallets, THORChain vaults, federation pegs | defaults; also watch nonce gaps and outflows to non-user contracts; an operator registry is essential | 0 pages, 2 warnings | `false-alarm-patterns.md` §6 |
| **small or dormant vault** (any design, vault < $2M or < 1 release a day) | XBridge, Force, Verus, Aztec, Shibarium | S1 USD floor $250K keeps it working; S3 floor drops to max($100K, 5% of vault); deprecated vaults stay monitored | XBridge caught; 0 pages on its ~$14K pre-hack vault | `patterns.md` C5 |

## 5. Decision table: alert or not?

| Observed pattern | Decision | Why (evidence) |
|---|---|---|
| One release ≥ 50% of the vault (≥ $250K), any recipient except an allowlisted migration target | **PAGE** | 8 hacks; never in legitimate non-pool data |
| One release ≥ 10% of the vault and ≥ $1M | **PAGE** | 11 hacks; 0 legitimate non-pool |
| Release ≥ 1% of the vault (≥ $250K) to a fresh address, *and* the net hourly outflow is ≥ 10% or the same address got ≥ 5% | **PAGE** | the P1/P2 shape; Ronin 2024 is caught only this way |
| Release ≥ 1% to a fresh address, nothing else | **WARNING** | whales (USDT0 $45M, Poly $10.4M) look like this; 0.25/bw if paged |
| Large release to a past depositor (LP, market maker, relayer) | **INFO** (pools) / **WARNING** (others) | Across relayer and Multichain market-maker round trips |
| Hour-of-day spike, nothing else | **INFO** | 67% of today's false alarms |
| Many releases in 10 min, small amounts, recipients with history | **INFO** | busy hours (Nomad pre-hack, Polygon) |
| ≥ 10 new recipients in 10 min *and* an hourly spike or ≥ 10% net outflow | **PAGE** | P3 copycats |
| Pool net hourly outflow ≥ 20% and ≥ $1M plus another signal | **PAGE** | pool profile |
| Pool imbalance under that | **WARNING** | Stargate swings up to 54% net per hour |
| Dust (< $1,000) release to a new address | **INFO**; put it on the 24 h watch-list | 76 per bridge-week in normal data |
| A later large release to a dust-tested address | treat the recipient as fresh; say so in the page | Orbit, Multichain |
| Upgrade, owner, threshold, signer-set, DVN, pauser or rate-limit change, not pre-announced | **PAGE** | C2: the only pre-loss signal in the record |
| The same, pre-acknowledged maintenance | **WARNING**; enables S14 for 24 h | Ronin 2024: the upgrade was "planned" from the outside, but broke checks |
| Any outflow signal within 24 h of a config change | **PAGE** (half thresholds) | Ronin 2024, IoTeX, Poly 2021 |
| Release with no matching source-chain deposit or burn (≥ $250K) | **PAGE** | Kelp, Wormhole, Verus, Qubit, BNB (literature) |
| Release that matches a source-chain deposit | downgrade one tier | removes the residual whale pages (`false-alarm-patterns.md` §7) |
| Deposit event with no token inflow | **PAGE** | Qubit |
| Release exactly at a known per-transaction cap | **WARNING**; PAGE with S3 or S13 | Ronin 2024 |
| Native ETH leaving at S1–S5 sizes | same as tokens | C1 |
| Recipient on the operator allowlist (unexpired) | downgrade one tier and say why | migrations; the allowlist itself is audited |
| During market stress (depeg, exchange collapse) | **no change to thresholds**; show a stress banner | FTX month: 1 page under REC |
| Ingest unhealthy | send, labelled `DEGRADED DATA`; never drop silently | §3.3 |
| Second incident on a vault that was refilled after a hack | **PAGE** at lower thresholds (S18) | Verus July 2026 |
| Router pulling user approvals | out of scope for v1 (state it); CPSC 491 stretch | P6 |

## 6. Data needed from SonarX (in priority order)

| # | Data | Why | Unlocks |
|---|---|---|---|
| 1 | Token Transfer logs for each vault, **all tokens it holds**, from ≥ 30 days of history, streamed within ~1 min of 6 confirmations | S1–S7 need per-token balances and recipient history; 30 days makes "fresh" reliable | Objectives 1.1, 1.2, 2.1 |
| 2 | **Native-asset movements** of each vault: internal transfers from traces, or per-block balance diffs | Native ETH left first in 3 of 14 cases | S12 |
| 3 | **Decoded admin/config events** of each bridge's contracts (proxy, owner, signer set, DVN, pauser, limits), and the list of those contracts | The only pre-loss signal | S13, S14 |
| 4 | Vault **balances** per token at a block, and token decimals, for reconciliation | Drift checks; vault-share denominators; catching missed transfers | data health, S1–S5 |
| 5 | **USD prices** per token per minute, with the source named, including long-tail tokens with a "confidence" flag | XBridge (STC) and Shibarium (KNINE) needed DEX-derived prices | S1–S5 on every asset |
| 6 | **Both sides of each bridge**: send/deposit and receive/release events with message IDs or nonces, on the source and destination chains; token supply per chain | Accounting is the strongest signal and the best false-alarm downgrade | S15, S16 (CPSC 491) |
| 7 | Stream **metadata**: chain head, lag, gaps, reorg notices | Gate paging on data health | S19 |
| 8 | Address **labels** if available (CEX deposit, bridge operator, mixer, known exploiter) | Recipient context; allowlist seeds | S3 context, alert text |
| 9 | Failed (reverted) transactions to bridge contracts | Probe and rehearsal context (Force's failed attempt ~4 min earlier; Kelp's reverted replays) | context |
| 10 | Mempool / pre-confirmation data | Pre-inclusion warning; most attackers use private relays (`02-defenses/techniques.md` T11) | stretch only |

## 7. Evaluation protocol

### 7.1 What to run on every detector change (CI-friendly; ~3 min)
1. **Replay suite.**
   - Today: the 14 hack cases plus Qubit as a negative control.
   - Grow it from the 30 confirmed Ethereum rows with a first-theft block (`01-hack-catalog/verified-ethereum-cases.md`). Next to add: IoTeX (config-change benchmark), Gravity, Aztec Connect, the Wormhole ETH leg, Verus 2 and Hyperbridge's WETH.
   - Report per case: detected, latency after the 6th confirmation, stolen-before share, the floor, and which signals agreed.
2. **False-alarm suite.** All normal and stress windows plus pre-hack baselines (76.5 bridge-weeks today). Report pages and warnings per bridge-week, per window and per design, with reason codes.
3. **Headline numbers:**
   - (a) hacks at the floor out of N;
   - (b) excess loss versus the floor ($);
   - (c) pages per bridge-week, worst window, and the number of windows over budget;
   - (d) NAB-style score (low-FP profile).

   `experiments/` implements all four; porting `policy.py` and `sweep.py` into `bridgewatch.evaluate` is the natural route.
4. **Overfitting guards.**
   - Leave-one-hack-out (today 14/14 detected, 13/14 at the floor).
   - A **time split**: tune on incidents and windows before a cut-off date, report on those after.
   - Freeze thresholds before looking at SonarX's evaluation weeks.
   - Any new rule must be motivated by a pattern (`patterns.md`), not only by a sweep.

### 7.2 Proposed measurable targets (for the team and mentor to decide)

| Proposal objective | Current wording (`proposal/snx3-proposal-kit.md` §2) | Suggested measurable form |
|---|---|---|
| 2.2 speed | "report time-to-first-alert and share of funds lost before the alert"; team target "before half … in ≥ 4 of 5" | (a) **every replayed theft detected within 60 s of its first theft's 6th confirmation** (today: 14/14, max 13 s); (b) **zero excess loss versus the floor** (today: $0); (c) separately, the share of stolen value lost before the alert, reported against its floor |
| 2.3 false alarms | "≤ 1 false alarm per bridge per week" | **≤ 1 page per bridge-week on every non-pool window** and ≤ 0.25 pooled, over ≥ 50 bridge-weeks including ≥ 2 stress windows (today under REC: worst non-pool 0.64, pooled 0.105, 76.5 bridge-weeks). Pools reported separately until S15 exists |
| 1.2 baseline | "≥ y% of clean 10-minute windows fall inside the normal band" | keep as stated; the S6 band (z < 10, $1M floor) is the "normal band" |

## 8. Roadmap mapped to the objectives

Sprint dates assume the 2-week cadence of `docs/sprint-reviews/sprint-1.md` (Sprint 1: Sep 28 – Oct 11). Effort uses the scale from `02-defenses/takeaways-for-bridgewatch.md`: S = under one student-sprint, M = one to two, L = three or more.

| When | Work | Objective | Effort | Expected impact (evidence) |
|---|---|---|---|---|
| **Sprint 2** (≈ Oct 12–25) | Port S1–S6 and the REC combiner into `detector.py`. Add `DetectorConfig` fields and `bridges.json` `design`. Add a per-vault counterparty table (first seen, total in/out) that the 7-day transfer pruning does not delete. Add per-token balances. | 2.1 | M | Pages 3.03 → ~0.1 per bridge-week at the same speed (`experiments.md` §4) |
| Sprint 2 | Port the scorer (floor, excess, pages per bridge-week by design, NAB, reason codes) into `bridgewatch.evaluate`; add `experiments/` datasets to CI | 2.2, 2.3 | S | Makes every later change measurable |
| Sprint 2 | Draft the new 2.2/2.3 wording (§7.2) and the SonarX data questions (§6) for the mentor meeting | 2.2, 2.3 | S | Removes an unreachable target |
| **Sprint 3** (≈ Oct 26 – Nov 8) | Pool profile; dust watch-list; heightened mode (S18); incident escalation by drawdown (S8); alert text with "who can act" | 2.1, 3.1 | M | Pools 13.3 → 0.36/bw; faster human action |
| Sprint 3 | Config-change monitor (S13/S14) for the 3 live rollup gateways plus 2 replay bridges (Ronin 2024, IoTeX logs) | 2.1 | S–M | Pre-loss warning for the C2 pattern ($1.14B in the catalog) |
| Sprint 3 | Data-health gate (S19): lag, gaps, 2-provider check, stale price | 1.1 | S | Prevents the largest live false-alarm source |
| **Sprint 4** (≈ Nov 9–22) | Native-ETH visibility in RPC mode (balance diff per block for each vault, or traces) and replay of the 3 native-first cases | 1.1, 2.2 | M | HECO 73% → 24%; Poly 2021 39% → 3%; Ronin 2024 34 min earlier |
| Sprint 4 | Dashboard: tiers, reason-code buttons, time-to-acknowledge, the "normal band" per bridge | 3.1 | M | Objective 3.1/3.2 evidence |
| Sprint 4 | Final false-alarm report (≥ 50 bridge-weeks) and replay report against the §7.2 targets | 2.2, 2.3 | S | Proposal §5 evidence |
| **CPSC 491** (spring) | SonarX source class (`Source.batches`) for live data | 1.1 | M | real data |
| 491 | S15 accounting for 1–2 bridges with deterministic IDs (LayerZero OFT GUIDs, a canonical rollup), then supply-vs-collateral per wrapped asset | 2.1 | L | +20% of catalog loss visible (P5); downgrades residual whale pages |
| 491 | More EVM chains (BSC, Arbitrum, Base), then one non-EVM peg if SonarX covers it | 1.1 | M–L | +10% and +10% of catalog loss (`experiments.md` §8) |
| 491 | Pause/freeze hand-off integrations; user study with a replayed exploit | 3.2 | M | Cuts the human part of latency (38 min – 6 days on record) |

## 9. What this design will still miss (say it in the threat model)
- **Single-transaction drains.** They will be *detected* in seconds but not *prevented*: 11 incidents and 36% of confirmed loss. Prevention needs in-protocol controls: caps, delays, pause.
- **Unbacked mints, until S15 exists.** 18% of loss.
- **Approval drains and off-vault losses.** 1.4% of loss.
- **Chains not ingested.**
- **Pool thefts that pay a past depositor**, until matching exists.
- **Poisoned inputs**, if both providers are compromised.
- **Thresholds may not hold on SonarX data.** Everything above was tuned and tested on 14 thefts and 76.5 bridge-weeks. Re-check on SonarX data with thresholds frozen first.
