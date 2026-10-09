> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# What bridge hacks look like: recognised patterns

Research date: 2026-10-07. Evidence comes from:
- `../01-hack-catalog/` (54 confirmed incidents, 20 case pages);
- the 15 replay datasets (`../03-onchain-data/hacks/`, `prototype/bridgewatch/data/`);
- the per-case features in `features.csv`, computed by `experiments/features.py`.

Pattern totals come from `experiments/out/pattern-counts.csv`. Each incident is assigned to one primary pattern; the row-by-row assignment is in `experiments/out/pattern-assignment.csv`, so a reviewer can disagree with any single call. Defensive framing: this describes what a monitor can observe, not how any attack was done.

## 0. Summary

**Latency.** "Expected latency" assumes the recommended pipeline: 6 confirmations, 15 s polls. A release is seen 73–87 s after its block. The measured first alert came **1–13 s after the first theft's 6th confirmation** in all 14 replay cases.

**Signal names** are defined in `experiments.md` §1 and `implementation-recommendations.md` §2.

| # | Pattern | Confirmed incidents | Loss ($M, share) | Earliest observable moment | Signals that catch it | What an alert can still save |
|---|---|---:|---:|---|---|---|
| P1 | Key/keeper-authorised multi-asset sweep | 12 | 1,049 (29%) | Config/signer change, or a dust test release (minutes to hours ahead); else the first release | `size`/`huge`, `fresh`, `net1h`, `conc`; config watch | 28–83% of tracked theft in the replays: every asset after the first |
| P2 | One or two huge releases (single-tx full drain) | 11 | 1,308 (36%) | The first release, unless a config change preceded it (Ronin 2024: 49 min; Kelp: DVN downgrade weeks earlier) | `huge`/`size`, `fresh`; config watch; accounting | ~0% of the first hit; replays, follow-on targets and downstream freezes |
| P3 | Copycat crowd drain | 1 (Nomad) | 190 (5%) | The faulty upgrade 41 days earlier (forensic); then the first copycat releases | `spike`, `fresh`, `net1h`; `crowd` later | ~90% (floor 9.5%) |
| P4 | Forged/invalid-proof releases, tx pattern unknown | 9 | 354 (10%) | First release; on the far side, an unmatched message | as P1/P2, plus accounting | depends on tx count |
| P5 | Unbacked mint (escrow untouched) | 8 | 668 (18%) | A deposit *event* with no matching token inflow (Qubit), or a mint with no lock | accounting only; vault rules are blind | most of it: the cash-out takes minutes to hours |
| P6 | Approval drain through a router | 6 | 38 (1%) | Route/facet added (Socket 3 days, LI.FI 2024) | approval-spend monitor; config watch | the route can be disabled (Socket: 14 min) |
| P7 | Pool-pricing manipulation | 3 | 2.8 (<0.1%) | Flash-loan-sized pool interaction | pool net-flow; out of scope for v1 | — |
| P8 | Off-vault (solver, relayer, frontend) | 4 | 16 (0.4%) | Outside the bridge | not visible to a vault monitor; declare out of scope | — |
| C1 | *Cross-cutting:* native asset first or alongside | 6 of 14 replays | $92M of catalog loss is native ETH | Native ETH left 4.7–34 min before the first token (3 cases), or in the same tx (3) | traces / balance diffs | Poly 2021: 39% → 3.3% gone at alert; HECO: 73% → 24% |
| C2 | *Cross-cutting:* config/upgrade precursor | 12 | 1,136 (31%) | 2 min to 41 days before the theft | config-change monitor | warning before any loss in Ronin 2024 (49 min) and IoTeX (18 min) |
| C3 | *Cross-cutting:* dust "test" releases to the theft address | 2 of 14 replays | — | 27 min to 2 h 38 min before | 24 h watch-list of dust recipients | context; strengthens `fresh` |
| C4 | *Cross-cutting:* repeat attacks and long tails | Verus ×2, Aztec ×3, Hyperbridge follow-ons, Kelp replays | — | after the first incident | "post-incident" sensitivity; pause | the second incident entirely |

## 1. What every visible theft had in common

Measured on the 14 replay cases with a visible theft (`features.csv`). The tables give the facts per case; the summary bullets that follow are what to take from them.

### 1.1 Size, recipients, tokens and timing

| Case | First theft: % of tracked vault | First tx as % of tracked theft | Stolen / vault value before first theft | Recipients | Drain duration | First token |
|---|---:|---:|---:|---:|---:|---|
| xbridge-2024 | 100% | 100% | 100% | 1 | single tx | STC |
| kelp-2026 | 99.8% | 100% | 99.8% | 1 | single tx | rsETH |
| verus-2026 | 97.3% | 100% | 99% | 1 | single tx | tBTC (+ ETH, USDC) |
| ronin-2022 | 95.3% | 95.3% | ~100% | 2 | 1.9 min | WETH (unwrap) |
| heco-2023 | 64.3% | 64.4% | 99.8% | 1 | 16 min | USDT (after native ETH) |
| shibarium-2025 | 61.6% | 61.9% | 99.5% | 2 | 1.4 min | SHIB |
| harmony-2022 | 53.9% | 54.1% | 99.8% | 1 | 18 min | USDC |
| force-bridge-2025 | 51.6% | 72.4% | 91.8% | 1 | 6.2 min | USDC (+ ETH) |
| poly-2021 | 36.7% | 36.9% | 99.3% | 1 | 30 min | USDC (after native ETH) |
| poly-2023 | 30.2% | 45.9% | 65.8% | 3 | 11 min | USDT |
| multichain-2023 | 24.8% | 24.9% | 100% | 5 | 67 min | USDC |
| orbit-2023 | 14.4% | 16.7% | 85.9% | 4 | 18 min | DAI |
| ronin-2024 | 5.8% | 100% | 5.8% | 1 | single tx | USDC (after native ETH) |
| nomad-2022 | 1.4% | 1.4% | 100% | 294 | 126 min | WBTC |

**Inter-theft gaps.** In the multi-transaction sweeps the median gap between thefts was 150 s (HECO), 167 s (Harmony), 180 s (Orbit), 186 s (Force), 429 s (Poly 2021) and 534 s (Multichain). The longest single gap was 22 min (Multichain).

**Time of day.** First thefts fell at 07, 07, 09, 10, 10, 11, 13, 17, 18, 18, 18, 21, 21 and 23 h UTC. Five of 14 were on a weekend. Orbit was on New Year's Eve.

### 1.2 What this means for detection
- **Thieves empty the vault.** In 12 of 14 cases the thieves took ≥ 86% of the tracked vault. Ronin 2024 is the exception (a per-transaction cap held it to 5.8%), and so is Poly 2023 (66%). In normal traffic the largest 24 h drawdown of a non-pool vault was 16% (Multichain's MPC wallet, March 2023); everything else stayed under 12.3% (`normal-stats.csv`).
- **The first release is big.**
  - Median first-theft size was 53% of the vault; 12 of 14 were ≥ 10%.
  - In 76.5 bridge-weeks of non-pool legitimate traffic, no single release of ≥ $1M was ≥ 10% of the vault (`experiments.md` §3).
  - The largest legitimate ones were 7.5% (Harmony, 6 days before its hack), 5.4% (Nomad's $20M move on 25 Jul 2022) and 4.9% (Ronin gateway, a $0.5M vault).
- **Recipients are fresh.** Every first theft with a known recipient (13 of 13) went to an address with under $1,000 of history with the vault. In 8 of 13, one address took everything.
- **The order is "biggest liquid asset first".**
  - A stablecoin was the first tracked token in 8 of 14 cases.
  - Native ETH went first or in the same transaction in 6 of 14 (C1).
  - Rules must therefore price and watch every asset in the vault. Watching only USDC/USDT would have missed Kelp (rsETH), Shibarium (SHIB), Verus (tBTC) and XBridge (STC).
- **There is no time-of-day pattern.** Thefts are spread across the day and week, so **time of day must never be used to suppress an alert**. Hour-of-day baselines help only to judge whether a modest spike is unusual (P3).
- **Gaps are minutes long.** The 2.5–9 minute gaps mean that in a multi-transaction drain a human gets a few minutes per remaining asset. That is enough for a pause transaction or an issuer freeze request if the page arrives in seconds, and not enough if it waits for an hourly batch or for finality (`experiments.md` §2).

## 2. Patterns in detail

### P1. Key/keeper-authorised multi-asset sweep
- **Frequency and loss:** 12 confirmed incidents, $1,049M (29% of confirmed loss), median $10.7M.
  - Members: Anyswap V3, Poly 2021, Harmony, Multichain, HECO, Orbit, Force, Shibarium, IoTeX, Gravity, THORChain 2026 and Wanchain.
  - Root causes: key/signer compromise, keeper replacement, validator capture and insider custody. All of them produce *validly signed* releases.
- **Evidence:**
  - Orbit: 4 releases, one per asset, to 4 fresh addresses in 17.6 min (`cases/2023-12-orbit-bridge.md`; `orbit-2023.json`).
  - HECO: 7 assets to one address in 16 min, after 10,145 native ETH (`heco-2023.json` notes).
  - Harmony: 7 assets to one address in 18 min.
  - Poly 2021: native ETH, then USDC $96.4M, WBTC, UNI, USDT and WETH to one address over 35 min.
  - Multichain: a $2 test, then 7 releases to 5 addresses over 67 min.
- **Observable signature.**
  - A release that is a large share of the vault *and* of that token's balance (`tok_share` 0.48–1.0 for the first theft), to a fresh address.
  - Then one release per remaining asset, 2.5–9 minutes apart, usually to the same address.
  - Net outflow passes 10% of the vault on the first release.
  - The contract behaves exactly as designed. There is no failed call and no odd function; only size, recipient and pace give it away (`cases/2022-03-ronin.md`, "the contract behaved exactly as designed").
- **Earliest observable moment:**
  - (a) A signer, keeper, validator or owner change: Poly 2021, 2 min 22 s before; Shibarium, a stake shift in the same session; IoTeX, ownership transfer 18 min before.
  - (b) Dust test releases to the theft addresses: Orbit, 27 min to 2 h 38 min; Multichain, 1 h 49 min.
  - (c) Otherwise, the first release.
- **Signals:**
  - `huge`/`size` page alone on the first release in all 7 replay members (Poly 2021, Harmony, Multichain, HECO, Orbit, Force, Shibarium).
  - `fresh` + `net1h` + `conc` agree on the same release in all 7 (`experiments/out/per-case.csv`).
  - Config watch and the dust watch-list give context earlier.
- **Expected latency.** Block + 73–87 s. The current detector and REC both page on the first theft in every replay member.
- **What it saves.** Every later asset, *if* someone can pause or an issuer can freeze within minutes. In the replays, the share stolen after the first page was 83% (Orbit), 75% (Multichain), 63% (Poly 2021), 46% (Harmony), 36% (HECO), 38% (Shibarium) and 28% (Force).

### P2. One or two huge releases (single-transaction full drain)
- **Frequency and loss:** 11 confirmed incidents, $1,308M (36%), median $11.6M.
  - Members: Wormhole (ETH leg), Ronin 2022, Poly 2023, XBridge, Ronin 2024, Kelp, Verus ×2, Aztec ×2 and AFX.
  - Root causes: forged messages or proofs (Kelp, Verus, Wormhole), access control (XBridge), faulty upgrade (Ronin 2024), verification bugs (Aztec), key compromise (Ronin 2022, AFX).
- **Evidence:**
  - Kelp: 116,500 rsETH in one transfer, 99.8% of the adapter (`kelp-2026.json`).
  - Verus: tBTC, USDC and 1,625 ETH in one tx, 97% of tracked value.
  - XBridge: 100% of STC in one tx.
  - Ronin 2022: 95% in the first of 2 withdrawals.
  - Poly 2023: USDT and USDC in consecutive blocks, 98% gone before any 6-confirmation alert.
  - Ronin 2024: one capped USDC withdrawal plus 3,996 native ETH, 34 min earlier.
- **Observable signature.** One release of 30–100% of the vault (or exactly at a known per-transaction cap, as in Ronin 2024) to a fresh address, with nothing before it in the transfer data.
- **Earliest observable moment.** For Ronin 2024 and Kelp, a config change: Ronin's proxy upgrade 49 min before the theft, Kelp's DVN downgrade to 1-of-1 weeks before (`02-defenses/protocol-defenses.md` §2). Otherwise the release itself. For forged messages, an accounting check on the source chain fires at the same block or earlier (`02-defenses/techniques.md` T1).
- **Signals:**
  - `huge` (≥ 50% and ≥ $250K) pages alone.
  - `fresh` + `conc` catches capped or partial ones (Ronin 2024 at 5.8%).
  - Config watch and accounting can fire before the release.
- **Expected latency.** Block + 73–87 s. Measured: 1–13 s after confirmation.
- **What it saves.** Nothing of the first hit (floor 95–100%). Where it can still matter:
  - Replays and follow-ons: Kelp's 40,000 rsETH replay reverted 51 min later because of the pause.
  - Downstream freezes: Aave froze rsETH after 77 min.
  - The *next* attack on the same contract: Verus was drained again 15 days after it was refilled.
- **Honest consequence.** The proposal already states that monitoring cannot prevent a single-transaction theft (`proposal/snx3-proposal-kit.md` §3). These cases should be scored on latency and on what happens next, not on "share saved".

### P3. Copycat crowd drain
- **Frequency and loss:** 1 confirmed incident (Nomad), $190M (5%).
- **Evidence.** 435 thefts to 294 distinct recipients over 126 min. The first theft was 1.4% of the vault. Thefts were often round amounts (`nomad-2022.json`; `cases/2022-08-nomad.md`).
- **Observable signature.**
  - Many medium releases (each 0.1–2% of the vault) to fresh addresses.
  - 10-minute outflow far above that hour's norm.
  - Net outflow passes 10% only after several minutes.
- **Earliest observable moment.** The faulty initialisation 41 days earlier. This is a forensic anchor only; it would read as a routine upgrade. After that, the first copycat releases.
- **Signals.**
  - `spike` (z ≥ 10, $1M floor) + `fresh` reach the floor: 9.5% gone, 15 s later than today's detector.
  - Without `spike`, the page comes when net outflow passes 10%, at 13.9% gone.
  - `crowd` fires late. At ≥ 10 new recipients in 10 min it comes 74 min in, with 45.7% gone. At ≥ 5 it would reach the floor, but ≥ 5 pages 1.28 times per bridge-week on busy legitimate bridges (`experiments/out/single-signal.csv`).
  - This is the one pattern where the seasonal baseline earns its keep.
- **Note.** Only one case represents this pattern. In leave-one-out, holding Nomad out produced a config that caught it at 35.7% instead of 9.5% (`experiments.md` §6).

### P4. Forged or invalid-proof releases, transaction pattern unknown
- **Frequency and loss:** 9 confirmed incidents, $354M (10%).
  - Members: ChainSwap 1, THORChain ×2 (2021), pNetwork, Meter, TAC, Allbridge CCTP, Coreum and Liquid.
  - Most are on chains BridgeWatch does not ingest (BSC, TON, XRPL, Bitcoin).
- **Signature and signals.** The same as P1/P2 where an escrow pays out. Message matching or supply-vs-collateral fires first where it applies (`02-defenses/academic.md` A1/A2).
- **Lesson.** These widen chain coverage more than they change rules. Liquid ($320M) alone is 9% of confirmed loss and is a Bitcoin federation peg.

### P5. Unbacked mint (escrow untouched)
- **Frequency and loss:** 8 confirmed incidents, $668M (18%).
  - Members: BNB Token Hub ($570M face value), Qubit ($80M), Syscoin, ChainSwap 2, Hyperbridge, Sandbox OFT, Adshares and MAP.
  - The partial mints in Wormhole, Kelp, Liquid and IoTeX also belong here.
- **Evidence.** Qubit's Ethereum handler emitted a 190 ETH "deposit" while **no token moved**. `qubit-2022.json` has zero transfers, so the replay sees nothing; the $80M left on BSC.
- **Observable signature:**
  - on the source chain, a deposit event without the matching token inflow;
  - on the destination, a mint or credit with no lock behind it;
  - supply on chain B greater than collateral on chain A.
- **Earliest observable moment.** The fake deposit or the mint itself. The cash-out took 17 min (Qubit) to hours (BNB, where only ~$100–137M of 2M BNB left before the halt).
- **Signals.** Only cross-chain accounting: deposit↔release matching, and wrapped supply ≤ locked collateral. Vault-outflow rules are blind by construction. A cheap partial check that needs data from one chain only: "deposit event emitted, but the vault's balance of that token did not rise".
- **Expected latency.** The same block as the mint (provisional), if both chains are ingested.

### P6. Approval drain through a router
- **Frequency and loss:** 6 confirmed incidents, $38M (1%).
  - Members: Socket, LI.FI ×2, Transit Swap, Rubic and Multichain 2022.
- **Signature.** The router calls `transferFrom` on many unrelated user wallets and sends the tokens to an unknown address. The router's own balance does not move (`cases/2024-01-socket-bungee.md`).
- **Earliest observable moment.** The route or facet addition: Socket, 3 days earlier; LI.FI 2024, a new facet.
- **Signals.** An approval-spend monitor (spender = router, `from` = many distinct users, `to` = one new address within minutes), plus a config watch on the router. Out of scope for the vault monitor; state it in the threat model.

### P7 and P8. Pool-pricing manipulation; off-vault losses
- **P7** (3 incidents, $2.8M): Nerve and Allbridge ×2. A flash-loan-sized interaction skews pool pricing, then the pool pays out abnormally. A pool net-flow rule is the only vault-side view.
- **P8** (4 incidents, $16M): Celer's frontend, Garden's solver wallets ×2, and the Across Solana relayer. No bridge escrow moves.
- Both are low-loss. Declare them out of scope for v1 rather than counting them as misses (`01-hack-catalog/catalog.md` §6.6).

## 3. Cross-cutting patterns

### C1. Native asset first, or alongside
- Native ETH left **before** the first tracked token in Poly 2021 (4.7 min), HECO (4.8 min) and Ronin 2024 (34 min). It left in the **same tx** in Force, Shibarium and Verus (`03-onchain-data/README.md`; `experiments/out/floors.csv`).
- Native ETH is invisible to Transfer logs. With traces or balance diffs, the first alert would have come:
  - 4.8 min earlier for HECO, with the share gone at alert falling from 73% to 24%;
  - 4.8 min earlier for Poly 2021, from 39% to 3.3%;
  - 34 min earlier for Ronin 2024, from 100% to 83% (`experiments.md` §2).
- **Catalog estimate:** ~$92M of confirmed loss was native ETH from Ethereum vaults (`experiments/out/coverage.json`). Its value is larger than its dollar share, because it is often the *first* thing to leave.

### C2. Configuration or upgrade precursor
- 12 confirmed incidents ($1,136M) had an on-chain config change before the theft:
  - Poly 2021 (keeper swap, 2 min);
  - Nomad (bad initialisation, 41 days);
  - Socket (route, 3 days);
  - LI.FI 2024 (facet);
  - Ronin 2024 (proxy upgrade, 49 min);
  - Force (control change);
  - Shibarium (validator stake);
  - IoTeX (owner transfer 18 min, upgrade 5 min);
  - Kelp (DVN 1-of-1, weeks);
  - XBridge (attacker re-listed a token via `listToken`, minutes);
  - Gravity (new validator, 1 day, disputed);
  - Sandbox OFT (delegate change).
- Base rate: config events on a bridge are rare. A handful per year, mostly announced (`cases/2021-08-poly-network.md`, "False-alarm considerations").
- **This is the only signal family that has fired *before any loss* in the record.**

### C3. Dust "test" releases
- Orbit: 5 releases of $1–$514 went to the 4 later theft addresses, 27 min to 2 h 38 min before.
- Multichain: $2 to the first theft address, 1 h 49 min before.
- Dust releases to new addresses are routine: 76 per bridge-week. But "dust, then ≥ 1% of the vault to the same address within 24 h" happened only 3 times in 76.5 bridge-weeks (`experiments/out/dust-tests.json`).
- Use it as context and as a reason a recipient is still "fresh". Do not page on dust.

### C4. Repeat attacks and long tails
- Verus was drained again 15 days after the returned funds were redeposited (`cases/2026-05-verus.md`).
- Aztec was hit 3 times in 4 days.
- Hyperbridge had follow-on actions for ~70 min after detection.
- Kelp's replays came 51 min after the first theft.
- After an incident, a vault should stay in a **heightened state** until a human clears it:
  - page on any `fresh` release ≥ $100K;
  - never relearn the baseline from the refill.

### C5. Sparse, dormant or small vaults
- Aztec (deprecated), Force (being sunset), XBridge (thin), Verus (a few transfers a week), Shibarium and Poly 2023 (< 1 release a day).
- On these, any large release is anomalous, but ratio rules explode on tiny transfers. XBridge's pre-hack vault held ~$14K, so a $3K release was 78% of it.
- Rules therefore need an absolute USD floor ($250K in REC). A deprecated vault should stay monitored, because attackers target them.

## 4. What did NOT distinguish hacks in this data
- **Release count bursts.** `withdrawal_burst` fired on Nomad only, and late. Single-actor drains are a handful of transactions.
- **Time of day and weekday.** See §1.2.
- **Multi-token sweeps as a stand-alone signal.** They are present in P1 (Orbit, HECO, Harmony, Poly), but the first token alone is already conclusive, so the signal comes too late to matter (`experiments.md` §3). Keep it for alert *text* ("3 assets drained in 10 min").
- **Mean or standard-deviation anomalies.** Heavy tails make them noisy, and median/MAD is already the prototype's choice. The thresholds that separate thefts are relative to the *vault*, not to the hour's history.
