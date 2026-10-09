# Takeaways for BridgeWatch: prioritized ideas

> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

Research date: 2026-10-07. These are **recommendations for the team to decide on**. Scope, design trade-offs and sponsor-facing commitments are human decisions under CLAUDE.md.

**Context.** The proposal's core is "learns how much money normally leaves each bridge vault at each hour of the day and alerts … when withdrawals jump far above normal, with a measured false-alarm rate". SonarX's targets are fast detection and at most 1 false alarm per bridge per week.

**Main finding.** A seasonal outflow baseline on its own is the *right dashboard* but the *wrong pager*. In the real incidents studied, the fastest, lowest-noise signal is an **accounting invariant**: released or minted on chain B without a matching deposit on chain A, or wrapped supply greater than collateral. It fired in the same block as the attack in every case where it applies [A1][A2]. The seasonal baseline then becomes **context and severity**. Paging needs either an invariant break or ≥2 correlated signals.

Effort scale (4 students, 2-week sprints): **S** ≈ under 1 student-sprint · **M** ≈ 1–2 student-sprints · **L** ≈ 3+ student-sprints.

| # | Idea | Speed impact | False-alarm impact | Effort | Data needed from SonarX | Evidence |
|---|---|---|---|---|---|---|
| 1 | **Vault-outflow monitor with a seasonal hour-of-week baseline (median + MAD), shown on the dashboard and fed into a severity score.** This is the existing proposal core. Use robust statistics, not mean/σ. Use a sliding 15–60 min window as well as hourly buckets so detection isn't delayed to the end of the hour | Medium (minutes) | **Raises** false alarms if it pages alone; neutral if used only as context | M | Per-vault outflow history (≥8–12 weeks), token USD prices, vault address lists | techniques T6; Osmosis legit spikes [R4] |
| 2 | **Single-transfer vs vault-share rule** (for example, one tx ≥ 5% of the vault, or ≥ a known per-tx cap) | **Instant** (one block) | Low once team/ops addresses are allowlisted | S | Vault balances per block; list of bridge-operator addresses | Wormhole, KelpDAO, Ronin 2022/2024, BNB [W3][KD2][RN1] |
| 3 | **Supply-vs-collateral solvency check per wrapped asset** (sum of destination supply ≤ source locked) | Instant to 1 block | **Very low**; failures are mostly decimals/rebasing bugs we can unit-test | M | Token contracts and vaults per bridge on each chain; decimals; known fee and rebasing behavior | Count of Monte Crypto [A2]; Agglayer pessimistic proof uses the same idea [AG1]; Hypernative's "mint without lock" [H1] |
| 4 | **Deposit↔release matching** (XChainWatcher-style) for 1–2 bridges with deterministic message IDs | Instant (provisional) to finality (confirmed) | Very low; the main risk is our own decoder or RPC bugs | L (per-bridge decoders) | Decoded bridge events on both chains (nonce, message hash, amount, recipient); finality constants | [A1][A2][A6] |
| 5 | **Admin/config change monitor**: owner, pauser, threshold, validator set, DVN/ISM, challenge period, rate-limit admin, proxy upgrade | Instant, and often **before** the exploit (Ronin 2024: 48 min; Kelp: weeks) | Low (rare events; acknowledge maintenance with a reason) | S | ABIs of admin events and proxy `Upgraded` / `AdminChanged` events per bridge | Nomad, Ronin 2024, KelpDAO, Hyperbridge, Orbit [N1][RN2][KD3][H2][OR1] |
| 6 | **Combiner / severity score**: page (P1) only on an invariant break, or on ≥2 correlated signals within a window (for example, rule 2 + rule 8, or rule 1 + rule 7) | Small delay (seconds to minutes) | **Largest reduction** in false alarms | M | Outputs of the other detectors; a labelled history for tuning | Forta combiner [F3][F5][F7]; Phalcon "risk + rules" [B1] |
| 7 | **Burst/clone detector**: N transactions with the same masked calldata or function from ≥M distinct fresh addresses within 10 min | Minutes (first few copycats) | Low–medium (airdrop claims); allowlist known batch relayers | S | Raw transaction input, sender first-seen time | Nomad copycats [N2][N3] |
| 8 | **Recipient/caller reputation multiplier**: new address (<24 h), privacy-mixer funded, freshly deployed unverified contract, known exploiter list | Instant | Increases false alarms if used alone, so use it **only** as a multiplier | S–M | Address age, funding source, labels (SonarX labels if available; otherwise public lists) | Forta Tornado/exploiter bots [F1]; Wormhole Tornado funding [W3]; Hyperbridge Railgun funding [R1] |
| 9 | **Data-health channel and suppression**: block lag, missing blocks, disagreement between 2 RPC providers, decoder failure rate. Hold or mark P1s "degraded" when data is unhealthy | Protects speed (we know when we are blind) | **Removes the biggest real-world false-alarm source** | S–M | Two RPC/stream sources per chain, or SonarX stream metadata (lag, gaps) | Wormhole live audit: 103/103 alerts were tooling errors [A2]; Tenderly lag and skipped blocks [T1]; Kelp RPC poisoning [KD3] |
| 10 | **Provisional-then-confirmed alerts**: alert at inclusion and confirm or auto-retract at finality | Saves about 12–15 min on Ethereum vs waiting for finality | Neutral, if retractions don't count as false alarms (decide and document) | S | Block and finality status from SonarX | [A2] (finality-bounded latency) |
| 11 | **Evaluation harness**: replay 8–10 historical hacks plus ≥4 quiet weeks per bridge. Report median time-to-detect, NAB-style score and **false alarms per bridge-week** with reason codes (detector error / benign trigger / data error) | n/a (measures speed) | Measures false alarms; required by the proposal | M | Historical blocks for those windows (Ronin 2024, Nomad, Wormhole 2022, Harmony, KelpDAO, Hyperbridge, Multichain, Orbit) | NAB [D3][D4]; Forta contextual precision [F4]; Alahmadi [D1] |
| 12 | **Alert content and routing**: one plain sentence, plus amount, vault, % of vault, matched or unmatched deposit, attacker addresses, affected tokens/issuers (for example, "USDC: Circle can freeze"), and links. Track time-to-acknowledge | Cuts the **human** part of latency (46 min Kelp, 70+ min Hyperbridge, 6 days Ronin) | Better context lowers perceived false alarms [D1] | S | Token issuer metadata (freezable?), protocol contact list | [H2][KD1][MC2][SH1] |
| 13 | **Probe/failed-transaction context**: reverted calls to bridge functions, tiny test transfers from new addresses | Can give 15 min to 2 h of early warning | High alone; use as a multiplier only | S | Failed transaction receipts/traces | Hyperbridge, Multichain, Nomad, KelpDAO [H2][MC1][N2][KD1] |
| 14 | **Known-limit awareness**: ingest each bridge's own caps (Wormhole Governor queue, CCIP buckets, Axelar flow limit) and flag withdrawals at or near the cap, plus changes to caps | Instant | Low | M | Per-bridge config (from contracts or APIs such as Wormholescan Governor) | [W1][CL1][AX1][RN1] |
| 15 | *(Stretch)* Mempool simulation or graph-ML scoring (BridgeShield-style) | Could be pre-inclusion | Unknown at real base rates | L | Mempool feed, traces | [A5][F1]; out of scope for CPSC 490 |

## Suggested order
1. **Sprint 1:** #2, #5, #9 (all small effort and low false alarms), plus the #1 dashboard baseline.
2. **Sprint 2:** #3 for 2–3 wrapped assets; #6 combiner v1; #10.
3. **Sprint 3:** #7, #8, #12, #13; start #11 replay harness.
4. **Sprint 4:** #11 full evaluation and false-alarm report; #4 for one bridge if time allows; #14.

## Questions to put to SonarX (a human sends these)
- Which bridges and vaults are in scope? Does SonarX already have decoded bridge events with message IDs, or only raw logs and transfers?
- Does SonarX expose stream lag, gap or reorg metadata, which we need for #9 and #10?
- Are address labels available (CEX deposit, mixer, exploiter, bridge-operator)?
- What counts as a "false alarm" for the target: any P1 page, or P1+P2? Does an auto-retracted provisional alert count?
- What latency target do they expect (block-level vs minute-level)?
