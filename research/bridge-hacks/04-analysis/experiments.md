> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Detection experiments: thresholds, signal combinations and the speed / false-alarm trade-off

Research date: 2026-10-07. Every number below was produced by the scripts in `experiments/` against the 30 dataset files (15 hack cases, 15 normal or stress windows). The scripts import the prototype's `bridgewatch` package read-only and were run from a scratch copy of `prototype/`, so nothing under `prototype/` was changed. Raw outputs are in `experiments/out/`.

**How much to trust this.** There are 14 thefts the data can see, from 13 bridges. A threshold tuned on 14 points can fit them and still fail on the 15th. Section 6 tests this with leave-one-out and a time split. Treat every threshold here as a starting default to re-check on SonarX data, not a tuned constant.

## 1. Setup

### Data
| Set | Files | What counts |
|---|---|---|
| Hack cases | 10 in `03-onchain-data/hacks/` + 5 in `prototype/bridgewatch/data/` | 14 with visible thefts. `qubit-2022` is the negative control: nothing left the Ethereum vault. |
| Normal windows | 8 in `03-onchain-data/normal/` + 5 in `prototype/.../data/normal/` | Every page after the 3-day warm-up is a false alarm. |
| Stress windows | `wormhole-portal-ftx-2022`, `polygon-pos-erc20-usdc-depeg-2023` | Same as normal (real stress, no theft). |
| Pre-hack baselines | the ~14 days before each hack | From warm-up to 1 h before the first theft, counted as normal. |

Together that is **76.5 bridge-weeks** of false-alarm exposure across 5 designs: lock-box, rollup gateway, LayerZero OFT adapter, liquidity pool and MPC custody.

### Pipeline and scoring
- **Simulated pipeline.** Same as `bridgewatch.replay`: a transfer is seen at the first 15 s poll after 6 confirmations (72 s).
- **Theft.** Same definition as the replay: an outflow of at least `theft_min_usd` inside `hack_window`.
- **Stolen before alert.** Tracked theft whose block time is at or before the first page's `detected_at`.
- **Floor.** The stolen-before share for an ideal detector that pages on the first theft. No detector that watches outflows can do better at 6 confirmations.
- **Excess loss.** Stolen-before minus floor, summed over cases, in $M. This is the money a better rule could still have saved.
- **Pages.** Pages on one bridge less than an hour apart count as one incident, the way the notifier groups them. The prototype's `evaluate --real` counts per-rule alerts instead, so its numbers are higher. Both are reported where it matters.
- **Warnings.** Shown on the dashboard, never sent.
- **NAB-style score.** From `policy.Score.nab`. It uses the low-FP weights (TP 1, FP 0.22, FN 1). Each hack's window runs from the first theft to max(last theft, first theft + 10 min). It is normalised so 0 is the null detector and 100 is perfect.

### Candidate signals
All are computed per release, streaming, in `engine.py`.

| Family | Definition |
|---|---|
| `huge` | one release ≥ X% of the tracked vault value just before it, and ≥ $ floor |
| `size` | same, at a lower share (the prototype's `large_withdrawal` is size ≥ 2% and ≥ $1M) |
| `fresh` | release ≥ X% of TVL and ≥ $ floor to a **fresh recipient**: under $1,000 of prior flow with the vault (never seen, or only dust "test" releases) |
| `net1h`, `net10` | net outflow (out − in) over 1 h or 10 min ≥ X% of the vault value at the window start (`escrow_drain` is net1h ≥ 5%) |
| `dd24` | drawdown from the 24 h high |
| `conc` | outflow to one recipient within 1 h ≥ X% of TVL |
| `multi` | ≥ k tokens each with a release ≥ 20% of that token's balance in 10 min |
| `crowd` | ≥ k distinct never-seen recipients in 10 min |
| `spike`, `burst` | the prototype's hour-of-day median/MAD z-scores, with the spread floor varied |

Paging modes:
- **any:** any family pages. This is the prototype.
- **combo:** a "strong" family pages alone. Otherwise a page needs ≥ 2 distinct families firing within a window (default 30 min), which is the Forta-combiner idea (`02-defenses/techniques.md` T12). One family alone is a warning.

## 2. The physical floor: how much any outflow detector can save

From `out/floors.csv`. The value is the share of tracked theft gone by the time an ideal detector could page on the first theft, at k confirmations (12 s blocks, 15 s polls).

| Case | 0 conf | 6 conf | 12 conf | 64 conf (~finality) |
|---|---:|---:|---:|---:|
| nomad-2022 | 8.2% | 9.5% | 9.5% | 9.5% |
| orbit-2023 | 16.7% | 16.7% | 16.7% | 33.1% |
| multichain-2023 | 24.9% | 24.9% | 24.9% | 51.9% |
| poly-2021 | 36.9% | 36.9% | 55.1% | 55.6% |
| harmony-2022 | 54.1% | 54.1% | 70.1% | 92.6% |
| shibarium-2025 | 61.9% | 61.9% | 100% | 100% |
| heco-2023 | 64.4% | 64.4% | 64.4% | 98.5% |
| force-bridge-2025 | 72.4% | 72.4% | 72.4% | 100% |
| ronin-2022 | 95.3% | 95.3% | 100% | 100% |
| poly-2023 | 98.1% | 98.1% | 98.1% | 100% |
| kelp-2026, verus-2026, xbridge-2024, ronin-2024 | 100% | 100% | 100% | 100% |

Findings:
1. **The current detector is already at the floor in all 14 cases.** `bridgewatch.replay` and our re-implementation agree to the cent (`out/baseline-check.json`). Its first alert came 1–13 s after the first theft's 6th confirmation. On *speed*, there is nothing left to gain from outflow thresholds on this data. The work is on false alarms, coverage and earlier (pre-theft) signals.
2. **6 confirmations cost almost nothing here.** Alerting at inclusion (0 confirmations) instead of 6 changes only Nomad (9.5% → 8.2%).
   - Waiting 12 confirmations would cost Poly 2021, Harmony and Shibarium 16–38 points.
   - Waiting for finality (64) would roughly double the loss in Orbit and Multichain.
   - Keep 6, and do not wait for finality.
3. **66.4% of all tracked stolen value left before any 6-confirmation alert was possible.** That figure is value-weighted (`coverage.json`).
4. **Objective 2.2 ("alert before half the stolen funds leave in ≥ 4 of 5 replays") cannot be met on the prototype's 5 cases by any outflow detector.** Harmony's floor is 54% and Ronin 2022's is 95%, so the best possible result is 3 of 5. Across all 14 cases, only 4 have a floor below 50%: Nomad, Orbit, Multichain and Poly 2021. Section 7 of `implementation-recommendations.md` proposes a measurable replacement. Changing it is a team and mentor decision.
5. **Native ETH visibility moves the floor most.** In three cases, ETH left before any token:

   | Case | ETH left before the first token | Share gone at first alert, tokens only | With native ETH visible |
   |---|---|---:|---:|
   | heco-2023 | 4.8 min | 72.9% | **23.8%** |
   | poly-2021 | 4.7 min | 39.1% | **3.3%** |
   | ronin-2024 | 34 min | 100% | **83%** |

   Shares here are of tracked plus native theft.

## 3. Separability of single signals (each family paging alone)

From `out/single-signal.csv`.

Column key:
- "Hacks" means the hacks detected / the hacks detected at the floor.
- "Excess" is extra loss versus the floor.
- "Pages/bw" is pages per bridge-week over all 76.5 bridge-weeks, with non-pool and pool shown separately.

| Signal alone | Hacks | Excess $M | Pages/bw all | non-pool | pool | Worst non-pool window |
|---|---|---:|---:|---:|---:|---|
| **current (any of 4 rules)** | 14 / 14 | 0 | **3.03** | 1.79 | 13.3 | poly-2021 11.5 |
| `escrow_drain` alone (net 1h ≥ 5%) | 14 / 14 | 0 | 0.60 | 0.12 | 4.59 | nomad 1.28 |
| net 10 min ≥ 5%, ≥ $1M | 13 / 13 | 0 | 0.14 | 0.06 | 0.85 | nomad 1.28 |
| net 1h ≥ 10%, ≥ $1M | 12 / 11 | 7.4 | 0.11 | 0.02 | 0.85 | nomad 0.64 |
| size ≥ 2% & $1M (`large_withdrawal`) | 12 / 11 | 7.8 | 0.26 | 0.21 | 0.72 | harmony 1.92 |
| size ≥ 10% & $1M | 11 / 10 | 44.6 | 0.03 | **0.00** | 0.24 | none |
| size ≥ 5% & $0.25M | 14 / 13 | 44.2 | 0.21 | 0.03 | 1.69 | nomad 0.64 |
| **fresh recipient ≥ 1% & $0.25M** (unknown recipient = fresh) | **14 / 14** | **0** | **0.25** | 0.21 | 0.60 | poly-2021 3.83 |
| fresh ≥ 2% & $0.25M | 14 / 13 | 7.4 | 0.12 | 0.10 | 0.24 | poly-2021 1.28 |
| one recipient 1h ≥ 5% & $1M | 12 / 11 | 69.7 | 0.14 | 0.10 | 0.48 | nomad 1.28 |
| drawdown 24h ≥ 20% & $1M | 12 / 10 | 54.0 | 0.20 | **0.00** | 1.81 | none |
| ≥ 2 tokens drained in 10 min | 11 / 3 | 331.9 | 0.24 | 0.00 | 2.17 | none |
| ≥ 10 new recipients in 10 min | 1 / 0 | 444 | 0.24 | 0.21 | 0.48 | nomad 7.0 |
| `outflow_spike` z ≥ 6, $0.1M floor (prototype) | 14 / 14 | 0 | 2.47 | 1.54 | 10.1 | poly-2021 11.5 |
| `outflow_spike` z ≥ 10, $1M floor | 8 / 8 | 1.3 | 0.30 | 0.29 | 0.36 | usdt0 4.41 |
| `withdrawal_burst` z ≥ 6, n ≥ 12 (prototype) | 1 / 0 | 394 | 0.35 | 0.34 | 0.48 | nomad 7.7 |

What separates thefts from normal traffic:
- **Single-release size relative to the vault.**
  - Non-pool legitimate traffic never released ≥ 10% of a vault worth ≥ $1M in 76.5 bridge-weeks.
  - 12 of 14 first thefts did: median first-theft share 53%, range 1.4–100%. The two that did not are Nomad (1.4%) and Ronin 2024 (5.8%, held down by its per-transaction cap).
  - In pools it is different. Across released 86% of its $0.47M pool in one transfer, and Stargate 16% of $20M.
- **Recipient freshness.**
  - 13 of 13 first thefts with a known recipient went to a fresh address. For Ronin 2022 the recipient is not in the logs, because the ETH left by WETH unwrap.
  - In two of those (Orbit, Multichain) the address had already received a dust "test" release, which is why "fresh" means under $1,000 of history, not "never seen".
  - In normal traffic, 0–100% of all releases go to never-seen addresses (`normal-stats.csv`). Freshness only separates thefts when combined with size.
- **The seasonal baseline (`outflow_spike`) is the noisiest pager.** It produces 2.47 pages per bridge-week alone; per rule, it produced 77 of Stargate's 90 alarms, all 17 of USDT0's and all 11 of Kelp's (pre-hack window).
  - Its one unique contribution is Nomad: it reaches the floor (9.5%) where size and net-flow rules come late.
  - With a $1M spread floor and z ≥ 10, it catches Nomad and costs 0.30 pages per bridge-week alone.
  - Its value is as a **second signal and dashboard context**, not as a pager.
- **`withdrawal_burst` and `crowd` are not useful pagers on this data.** They fire on Nomad only, late, and on busy legitimate bridges early.

## 4. Combination policies

From `out/combos.csv`; per-window detail in `out/per-window.csv`, per-design in `out/per-design.csv`.

**REC** is the recommended policy:
- **Pages alone:** `huge` (one release ≥ 50% of TVL and ≥ $250K) or `size` (≥ 10% of TVL and ≥ $1M).
- **Otherwise pages on ≥ 2 within 30 min of:**
  - `fresh` (≥ 1% of TVL and ≥ $250K to a fresh recipient);
  - `net1h` (≥ 10% of TVL and ≥ $250K);
  - `conc` (one recipient ≥ 5% of TVL and ≥ $250K in 1 h);
  - `crowd` (≥ 10 new recipients in 10 min);
  - `spike` (z ≥ 10 with a $1M spread floor and ≥ 0.5% of TVL).
- **Pool profile:**
  - Releases to past depositors (LPs, relayers) never count toward size, fresh or concentration.
  - A pool pages only if net 1h ≥ 20% of TVL and ≥ $1M, *and* at least 2 families are active.

| Policy | Hacks | At floor | Excess $M | Pages/bw all | non-pool | pool | Warnings/bw | Windows > 1/wk | NAB |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| current (any rule pages) | 14 | 14 | 0 | 3.03 | 1.79 | 13.3 | – | 12 of 29 | −83 |
| current + $1M spread floor | 14 | 14 | 0 | 1.29 | 0.84 | 5.07 | – | 9 | 21 |
| current, z 10, $1M floor, burst n ≥ 30 | 14 | 14 | 0 | 0.99 | 0.50 | 5.07 | – | 9 | 39 |
| current rules, all thresholds raised | 13 | 13 | 0 | 0.38 | 0.31 | 0.97 | – | 3 | 69 |
| current rules, page only if ≥ 2 agree | 14 | 14 | 0 | 0.44 | 0.28 | 1.81 | 3.03 | 6 | 72 |
| fresh ≥ 1% & $250K alone | 14 | 14 | 0 | 0.25 | 0.21 | 0.60 | – | 1 | 84 |
| **REC** | **14** | **14** | **0** | **0.105** | **0.073** | **0.36** | 0.98 | 1 (Across: 1 page in 4 days) | **92.6** |
| REC without pool profile | 14 | 14 | 0 | 0.17 | 0.073 | 0.97 | | 1 | 88.7 |
| REC without pool profile or LP suppression | 14 | 14 | 0 | 0.34 | 0.073 | 2.53 | | | 78.5 |
| REC, 10-min combination window | 14 | 14 | 0 | 0.091 | 0.073 | 0.24 | | | 93.4 |
| REC, 60-min window | 14 | 14 | 0 | 0.13 | 0.088 | 0.48 | | | 91.0 |
| REC without fresh | 13 | 12 | 7.4 | 0.065 | 0.029 | 0.36 | | | 87.8 |
| REC without spike | 14 | 13 | 7.4 | 0.091 | 0.059 | 0.36 | | | 93.3 |
| REC with the prototype spike (z 6, $100K) | 14 | 14 | 0 | 0.25 | 0.22 | 0.48 | | | 84.0 |
| REC without concentration | 13 | 13 | 0 | 0.065 | 0.044 | 0.24 | | | 87.9 |
| REC + multi-token family | 14 | 14 | 0 | 0.12 | 0.073 | 0.48 | | | 91.8 |
| REC, fresh also pages alone | 14 | 14 | 0 | 0.22 | 0.21 | 0.36 | | | 85.5 |
| REC, net1h at 5% | 14 | 14 | 0 | 0.14 | 0.12 | 0.36 | | | 90.3 |

REC by design and role (`out/per-design.csv`), in pages per bridge-week:

| Design | Role | Bridge-weeks | Current | REC | REC warnings/bw |
|---|---|---:|---:|---:|---:|
| lock-box | normal | 15.4 | 0.19 | **0** | 0.13 |
| lock-box | stress (FTX, USDC depeg) | 7.7 | 4.67 | **0.13** | 0.65 |
| lock-box | pre-hack | 18.8 | 2.23 | **0.16** | 1.06 |
| rollup gateway | normal | 11.6 | 0 | **0** | 0.09 |
| OFT adapter | normal | 7.7 | 3.63 | **0.13** | 2.20 |
| OFT adapter | pre-hack | 1.6 | 1.92 | **0** | 0 |
| pool | normal | 8.3 | 13.3 | **0.36** | 3.38 |
| MPC | normal + pre-hack | 5.4 | 1.85 | **0** | 0.37 |

Findings:
- REC keeps every hack at the floor. Detection latency is the same as today in 13 cases, and 15 s later in Nomad with the same 9.5% loss share.
- REC cuts pages about **29×** (3.03 → 0.105 per bridge-week). Of the current detector's 282 rule-level false alarms, 8 still page under REC, 51 become dashboard warnings, and 223 disappear (`out/fa-examples.csv`).
- **Ablations show what earns its place.**
  - `fresh`, `conc` and `spike` each prevent a miss or a slower page. Without `fresh`, Ronin 2024 is missed and Nomad slips to 13.9%. Without `conc`, Ronin 2024 is missed. Without `spike`, Nomad slips to 13.9%.
  - `crowd`, `multi`, `huge`, the 5% vs 20% `size` choice, and the strong-signal path change nothing **on this data**. They are kept for robustness: small vaults, copycat swarms without a spike, and single-release drains whose recipient is unknown.
  - A team that wants the minimum could drop `crowd` and `multi` and lose nothing measurable here.
- **Pools need their own profile.** Without the pool profile, pools page 0.97 per bridge-week. Without LP suppression too, 2.53. Everything else is unchanged.

## 5. Pareto trade-off (speed vs false alarms)

`out/grid.csv` holds 1,728 REC-family configurations. They vary the size share, fresh share, net-1h share, crowd k, spike z, window length and USD floor. The pool profile is off in the grid, so pool pages run higher than REC's. `out/pareto.csv` keeps the non-dominated points on (pages per bridge-week, excess loss, misses). Read along the front:

| Pages/bw (all) | non-pool | Misses | Excess loss | What it gives up |
|---:|---:|---:|---:|---|
| 0.013 | 0.000 | 1 | $54.0M | Ronin 2024 missed (5.8% of TVL, no fresh signal); Nomad at 35.7% (floor 9.5%); Orbit at 33.1% (floor 16.7%) |
| 0.052 | 0.029 | 0 | $44.2M | Nomad at 35.7% (no spike or fresh signal) |
| 0.065 | 0.044 | 0 | $7.4M | Nomad at 13.9% (no spike) |
| **0.105** | **0.073** | **0** | **$0** | nothing: every case at the floor (the REC level; REC reaches 0.105 with the pool profile on) |
| 0.25 – 3.03 | | 0 | $0 | dominated: more pages, no faster |

A miss whose floor is 100% (Ronin 2024) adds no excess dollars, so read the misses column too.

**On this data, ~0.1 pages per bridge-week is the knee of the curve.** Below it, every reduction costs Nomad-type speed or a small-vault miss. Above it, extra pages buy nothing. One page per bridge every ~10 weeks is 10× inside SonarX's ≤ 1 per bridge per week budget, which leaves room for config-change and accounting signals (Section 8 of the recommendations).

## 6. Overfitting checks

**Leave-one-hack-out** (`out/loo.json`). For each of the 14 hacks:
- Choose the grid configuration on the other 13. The objective is fewest misses, then least excess loss.
- The constraint is pooled pages/bw ≤ 0.5 and no non-pool window above 1 per week, on all false-alarm windows except the held-out hack's own baseline.
- Then score the held-out case.

Result:
- **14 of 14 held-out hacks detected; 13 of 14 at the floor.**
- The exception is Nomad. When Nomad is held out, no other case needs the spike or fresh signals at sub-1%-of-TVL sizes. The chosen config drops them, and Nomad's held-out loss share is 35.7% against its 9.5% floor.
- Lesson: **the copycat-crowd pattern is represented by a single case.** Keep a crowd- or seasonal-type second signal even though only one case justifies it.

**Time split** (`out/time-split.json`): choose on 2021–2023 data, score on 2024–2026.
- Training: 8 hacks plus the 2022–2023 windows. Test: 6 hacks plus the 2026 windows.
- The chosen config had **no fresh-recipient signal**, because no training theft needed it.
- On the test set it **missed Ronin 2024**: $2M USDC, 5.8% of TVL, capped by the bridge's per-transaction limit. It caught the other 5 at the floor, with 0.33 pages per bridge-week (the grid has no pool profile).
- This is exactly the overfitting risk. **Recipient freshness is in REC because of what attacks look like** (13/13 fresh recipients), not because a threshold sweep picked it.

**Robustness to thresholds.** REC's results do not change when:
- strong size moves between 5% and 20%;
- fresh moves between 0.5% and 1%;
- net1h moves between 10% and 20%.

So the defaults sit on a plateau, not a knife-edge. Moving fresh to 2% and $1M, or dropping spike, costs Nomad's speed.

## 7. Pre-theft signals measured in the data

- **Dust "test" releases** (`out/dust-tests.json`).
  - Orbit: 5 dust releases ($1–$514) went to the 4 later theft recipients, 27 min to 2 h 38 min before the theft.
  - Multichain: a $2 test went to its first theft recipient 1 h 49 min before.
  - In normal traffic, dust releases to new addresses are common: 76 per bridge-week. But "dust, then a release ≥ 1% of TVL and ≥ $250K to the same address within 24 h" happened only 3 times in 76.5 bridge-weeks (0.04 per bridge-week; Stargate ×2, FTX-era Wormhole ×1).
  - Use: keep a 24 h watch-list of dust recipients. It strengthens `fresh` and makes the alert text concrete ("this address got a $10 test release 45 min ago"). It does not page earlier on its own.
- **Native ETH first** (Section 2): 4.7–34 min of earlier warning in 3 of 14 cases, if traces or balance diffs are ingested.
- **Config changes before the theft** are not in this transfer-only data. From the catalog:
  - 12 confirmed incidents ($1.14B) had one, with lead times from 2 min (Poly 2021) to 41 days (Nomad);
  - Ronin 2024's came 49 min ahead and IoTeX's 18 min ahead (`coverage.json`).

## 8. Coverage of the catalog's losses

From `out/coverage.json`. Each of the 54 confirmed incidents' $3.63B is split by what data is needed to see it. The split is a hand estimate, ± 10%.

| Layer (cumulative) | Adds | Cumulative share of confirmed loss |
|---|---:|---:|
| L0 today: ERC-20 outflows from Ethereum vaults | $1,980M | 54.6% |
| L1 + native ETH (traces or balance diffs) | $92M | 57.1% |
| L2 + long-tail token prices (DEX-derived, flagged) | $25M | 57.8% |
| L3 + cross-chain accounting (supply vs collateral, unbacked mints) | $740M | 78.2% |
| L4 + other EVM chains (same detector, more ingest) | $378M | 88.7% |
| L5 + non-EVM pegs (Bitcoin/Liquid, Solana, TON, Cardano, XRPL) | $357M | 98.5% |
| L6 + approval-spend and solver/relayer monitoring | $54M | 100% |

"Covered" means visible, not prevented. Section 2 shows that, on the cases we can measure, about two-thirds of visible value is gone before any outflow alert.

## 9. Reproduce

```sh
cp -r prototype /tmp/bw-proto      # a copy: importing bridgewatch writes __pycache__
cd research/bridge-hacks/04-analysis/experiments
BW_PROTOTYPE=/tmp/bw-proto PY=<python with the prototype's deps> sh run_all.sh   # ~3 min, no numpy/pandas
```

| Script | Output |
|---|---|
| `common.py` | loader, labels, designs, simulated pipeline |
| `engine.py` | per-release feature stream |
| `policy.py` | signal families, paging modes, scorer |
| `floors.py` | `out/floors.csv` (Section 2) |
| `features.py` | `../features.csv` |
| `normal_stats.py` | `../normal-stats.csv`, `out/largest-legit-outflows.csv`, `out/seasonality.json` |
| `sweep.py` | `out/single-signal.csv`, `combos.csv`, `per-case.csv`, `per-window.csv`, `per-design.csv`, `grid.csv`, `pareto.csv`, `loo.json`, `time-split.json`, `baseline-check.json` |
| `fa_examples.py` | `out/fa-examples.csv` (every current false alarm with tx and REC's verdict), `out/rec-pages.csv` |
| `coverage.py`, `pattern_counts.py` | catalog coverage and pattern totals |
| `dust_tests.py` | `out/dust-tests.json` |

## 10. Limits of these experiments

- **Native ETH is invisible.** Wherever native ETH matters, the "tracked" numbers understate both the theft and the vault value. Share-of-TVL thresholds will read lower on real balances that include ETH.
- **One price per token per file.** Real-time pricing errors (stale feeds, depegs) are not simulated. They would add false alarms; see `ideas-and-open-questions.md`.
- **"Fresh" history is short.** It is judged on ≤ 30 days of history (≤ 14 for hack files). On SonarX with months of history, fewer legitimate recipients will look fresh, which lowers false alarms. A theft recipient is fresh at any history length.
- **Pool coverage is thin.** It is 3 windows, and Across is only 7 days, so its "1 page in 4 days" is one event.
- **Config-change, accounting and mempool signals cannot be tested here.** The data has none of them. Their value is estimated from the catalog, not measured.
- **No thefts from pools or OFT adapters other than Kelp.** The pool profile's miss rate on a real pool theft is unknown. A pool drain that sends funds to a past depositor would be suppressed, which is why pools need deposit-release matching (recommendations §3.3).
