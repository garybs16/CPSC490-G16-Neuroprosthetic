# Academic work relevant to BridgeWatch

> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

Research date: 2026-10-07. Each entry covers method, data, results, limitations, and what BridgeWatch can borrow. Source keys refer to `sources.md`. Where only the abstract was read, this is stated.

---

## A. Bridge-specific detection

### A1. XChainWatcher: Monitoring and Identifying Attacks in Cross-Chain Bridges (arXiv 2410.02029; Augusto, Belchior, Pfannschmidt, Vasconcelos, Correia; v1 Oct 2024, v3 Sep 2025) [A1][A1h]
- **Method.** A three-stage pipeline:
  1. decode events and transactions on each chain;
  2. turn them into Datalog facts;
  3. evaluate cross-chain rules.

  The rules split into two kinds:
  - **isolated** rules on one chain: a token transfer must match the bridge's deposit or withdraw event, in the right order;
  - **dependent** rules across chains: each deposit on the source chain must match exactly one release on the target chain, with the same parameters, and only **after source finality** (`src_ts + finality < dst_ts`).

  There are 30 rules in total; the repo is public.
- **Data.** Ronin (Ethereum↔Ronin, multisig) and Nomad (Ethereum↔Moonbeam, fraud proof). 81k cross-chain transactions across 3 EVM chains, worth about $4.2B.
- **Results.**
  - Found the $611M Ronin and $190M Nomad attack transactions. On Nomad, it beat a reputable security firm's analysis.
  - Found 37 cross-chain transactions the bridges should not have accepted, and failed exploit attempts on Nomad.
  - Found $7.8M locked but never released, and about $200K lost to user errors.
  - **Finality violations:** some Nomad transfers completed in about 87 s against a 30-minute fraud window, and some Ronin transfers in 11–66 s against 45 s finality.
  - **Speed:** Datalog evaluation took about 3.6 s for 1.57M tuples (Ronin) and median per-receipt processing was 0.35–0.78 s. Slow `debug_traceTransaction` calls dominated for native-value transfers.
- **False positives.**
  - A few beneficiary-address formatting cases.
  - 708 Ronin events that matched transactions before the data window, which is a data-boundary artefact.
- **Limitations.**
  - Rules are hand-written and break when event signatures change.
  - Only EVM ↔ sidechain bridges.
  - Short data windows.
  - Speed depends on RPC quality.
- **What BridgeWatch can borrow.**
  - The **deposit↔release matching invariant** with a per-bridge finality constant.
  - The **"released before source finality" rule**: a cheap, low-false-alarm detector.
  - Treating **unmatched releases** as the core alert.
  - Handling of **window-boundary artefacts**: do not alert on releases whose deposit predates your ingest window.

### A2. Count of Monte Crypto: Accounting-based Defenses for Cross-Chain Bridges (arXiv 2410.01107; Liu, Luo, Yan, Izhikevich, Grant, Stefan, Voelker, Savage, UCSD; v1 Oct 2024, v3 Apr 2026) [A2][A2h]
- **Method.** A per-transaction balance invariant: outflow = inflow − costs. Where fees are ambiguous, the rule falls back to "withdrawn ≤ deposited". Values come from bridge events and ERC-20 Transfer events. The paper then proposes **in-line enforcement** ("report-then-execute"): a reporter attests valid withdrawals, and the bridge reverts any withdrawal that was not reported or that breaks the invariant.
- **Data.** 11 bridges and 21 chains, including Ronin, Poly (2021/2023), BSC Token Hub, Wormhole, Nomad, Harmony, HECO, Qubit, Anyswap, Chainswap and Meter. About 10M bridge transactions, 12 attacks and about $2.6B stolen (2021–2023).
- **Results.**
  - 2,873 violating transactions (0.03%). 2,305 belong to known attacks.
  - The other 568 split into: 24 likely unreported Anyswap attacks, 129 test tokens, 248 implementation or invocation errors, 167 suspicious.
  - Retrospective alert rate: about **one alert every few weeks**.
  - **Live audit on Wormhole** (Oct 2024–Jun 2025): about 202k transactions (about 40% of withdrawals), **103 alerts, all caused by the monitor's own bugs or RPC indexing errors**. All 3 simulated attacks were caught.
  - In-line prototype: under 40 lines changed. Gas rose from about 270k to 380k per withdrawal (about $1).
- **Detection delay.** The live monitor processes only finalized blocks, so latency is bounded by finality (about 12 minutes on Ethereum).
- **Limitations.**
  - Out of scope: swap bridges, user deception, withdrawals smaller than deposits, and withdrawals that bypass the withdraw function.
  - Some bridges lack in-band transaction IDs, so pairing relies on external APIs.
  - Trust in the reporter; testnet-only enforcement.
- **What BridgeWatch can borrow.** This is **the most directly useful paper for SonarX's false-alarm target.**
  1. The invariant itself is the backbone detector.
  2. Their live false alarms came from **data quality, not attacks**. BridgeWatch should run **data-health checks** (RPC gaps, decoding failures, reorgs) as a separate, non-paging channel and suppress invariant alerts while data health is red.
  3. Allow-list "test token" and known-error classes.
  4. Their category labels (attack, test, error, suspicious) are a ready-made triage taxonomy for the dashboard.

### A3. Xscope: Hunting for Cross-Chain Bridge Attacks (arXiv 2208.07119; Zhang, Gao, Li, Chen, Guan, Chen; ASE'22 tool demo) [A3]
- **Method.** Defines security properties for three new bug classes and checks them at run time and offline. (Only the abstract was read; the full PDF lists the properties.)
- **Data.** Four popular bridges, not named in the abstract.
- **Results.** Claims to detect all known attacks plus some unreported suspicious ones. No false-positive numbers in the abstract.
- **Limitations.** A tool demo; small evaluation.
- **What BridgeWatch can borrow.** The property-based framing. Each property becomes a named rule with its own false-alarm budget.

### A4. BridgeGuard: Safeguarding Blockchain Ecosystem: Understanding and Detecting Attack Transactions on Cross-chain Bridges (arXiv 2410.14493; Wu, Lin, Lin, Zhang, Wu, Su; WWW 2025) [A4]
- **Method.** Builds a graph from each transaction's call structure. Two stages: global and local graph mining. Attack transactions have distinctive call structures compared with normal cross-chain business logic.
- **Data.** 49 bridge attacks (June 2021–Sept 2024); 203 attack transactions and 40k normal ones.
- **Results.** Recall 36.32% higher than prior tools. Detects unknown attacks. (The abstract gives no absolute precision or recall.)
- **Limitations.** Needs execution traces. Class imbalance means real-world precision is unknown.
- **What BridgeWatch can borrow.** The labelled-attack list is a candidate **evaluation set**. "Call-graph shape never seen before on this bridge" is a cheap novelty feature, the same idea as SphereX's allowlist.

### A5. BridgeShield: Risk-Aware Graph Modeling for Cross-Chain Bridge Attack Detection (arXiv 2508.20517; Lin, Lu, Liu, Wu, Fang, Su, Song, Xia, Zheng; v1 Aug 2025, v2 Sep 2026) [A5]
- **Method.** Builds cross-chain behavior graphs (source chain, off-chain relay, destination chain), selects differential meta-paths, and propagates risk hierarchically.
- **Results.** F1 of 92.6%. Beats rule-based and graph baselines and detects unseen incidents. (Abstract only.)
- **Limitations.** Offline ML on traces. At realistic base rates, even 92.6% F1 could mean many false alarms per week.
- **What BridgeWatch can borrow.** Its main idea is **combining risk across the three stages** (source, relay, destination) rather than scoring each chain alone. That supports the multi-signal design. Treat it as stretch work, not the MVP.

### A6. SoK: Cross-Chain Transaction Identification and Matching (arXiv 2608.17532; Zheng, Fu, Liu, Wang, Wang, Yuen; Aug 2026) [A6]
- Classifies matching into three mechanisms: deterministic IDs, field-constraint heuristics, and model-assisted matching.
- Finds that **fewer than half of published datasets and artifacts are still obtainable**.
- **Borrow:** choose deterministic-ID matching wherever the bridge exposes a nonce or message hash, and fall back to heuristics (amount ± fee, time window, recipient). Do not plan around downloading old academic datasets.

## B. Systematizations (SoKs)

### B1. SoK: Security of Cross-chain Bridges: Attack Surfaces, Defenses, and Open Problems (arXiv 2312.12573; Zhang, Zhang, Barbee, Zhang, Lin; Dec 2023) [P1]
- 12 attack vectors; 10 attack types, each with a Solidity example; a discussion of defenses.
- **Borrow:** a taxonomy for labelling alerts by likely attack class.

### B2. SoK: Cross-Chain Bridging Architectural Design Flaws and Mitigations (arXiv 2403.00405; Notland, Li, Nowostawski, Haro; Mar 2024) [P2]
- 60 bridges and 34 exploits; 13 components; 8 design flaws.
- **11 impact-reduction measures**:
  - stronger security for large transfers;
  - maximum transfer size;
  - longer fraud window;
  - pausing;
  - staff to monitor and react;
  - monitoring with automatic recovery;
  - pausing the chain;
  - freezing by validators, exchanges or token issuers;
  - blacklisting.
- **Borrow:** BridgeWatch is measure #5 ("monitor and react"). Its alerts should lead straight into #4 (pause) and #8–11 (freezes), for example a one-click attacker-address export.

### B3. SoK: A Review of Cross-Chain Bridge Hacks in 2023 (arXiv 2501.03423; Belenkov et al., Quantstamp; Jan 2025) [P3]
- Says Ronin "should have been detected straight away and not multiple days after."
- Recommends:
  - decentralized validators;
  - higher multisig thresholds (Harmony moved from 2-of-5 to 4-of-5);
  - key hygiene;
  - revoking stale permissions.
- Notes that Celer's delay, volume control and pause **were effective**.

## C. Other 2025–2026 bridge-monitoring work (not fully verified)
- **BADS:** real-time bridge anomaly detection and reporting using LLMs (IEEE CAISAIS 2025). **VeriBridge:** real-time attack detection via static-informed graph anomaly learning (IEEE VCRIS 2025). Both are known only from bibliography entries found in search [A7]. I could not read either paper. **Unverified.**

## D. Alert fatigue, false positives and scoring early detection

### D1. "99% False Positives": A Qualitative Study of SOC Analysts' Perspectives on Security Alarms (Alahmadi, Axon, Martinovic; USENIX Security 2022) [D1]
- **Method.** A survey of 20 practitioners, then interviews with 21 SOC practitioners.
- **Findings.**
  - Many "false positives" are actually **benign triggers**: the detector fired correctly on real but legitimate behavior.
  - Validating alerts is tedious and leads to burnout and desensitization.
  - Proposes 5 alarm qualities: **Reliable, Explainable, Analytical, Contextual, Transferable**.
- **Borrow.**
  - Track "benign trigger" (for example, a market-maker rebalancing) separately from "detector error".
  - Make each alert explain itself in one sentence with context, which matches the proposal's "one plain sentence" goal.
  - Learn from benign triggers by adding allowlists and seasonality.

### D2. FireEye/IDC "Voice of the Analyst" survey (2021) [D2]
- Industry survey of 350 analysts. They estimate **45% of alerts are false positives**, and **35% of in-house analysts admit ignoring alerts** when overloaded.
- This is a vendor survey; the figures are perceptions.
- **Borrow:** this is the motivation slide for SonarX's "at most 1 false alarm per bridge per week" target.

### D3. Numenta Anomaly Benchmark (NAB) (Lavin and Ahmad, ICMLA 2015; arXiv 1510.03336) [D3][D4]
- **Scoring.**
  - Each labelled anomaly gets a window.
  - The **earliest** detection inside a window earns a reward, weighted by a sigmoid so earlier is better.
  - Every false positive is penalized.
  - A missed window is penalized heavily.
  - Scores are normalized so a perfect detector gets the maximum and a null detector gets 0 [D4].
  - The NAB paper also defines "application profiles" that reweight the score toward low false positives or low false negatives. I know this from memory of the paper; it was not re-checked in this session.
- **Caveat.** Larger windows reward earlier detection, but they can also turn real false positives into true positives [D4].
- **Borrow:** use a NAB-style score (with a "low FP" profile) to evaluate BridgeWatch on replayed historical hacks. It captures both of SonarX's hard problems (speed and false alarms) in one number. Report alongside it the plain metrics: median time-to-detect and false alarms per bridge-week.

### D4. Forta contextual precision method [F4]
- Not peer-reviewed, but it is a written method.
- Count only alerts that touch the protocol's own addresses. Measure precision by sampling random protocols from DeFiLlama and recall on publicly disclosed attacks. Separately report **early** recall (alert during the preparation stage).
- **Borrow:** this method, applied to BridgeWatch's per-bridge evaluation.

## E. What BridgeWatch should take from the literature (summary)
1. **Accounting invariants (A1, A2) are the highest-precision bridge detector known.** Retrospective alert rate is about one every few weeks across 11 bridges [A2], and both papers caught every known attack in their data.
2. **The biggest live false-alarm source was the monitor's own data pipeline** [A2]. Budget engineering time for ingest health.
3. **Latency vs certainty.** Waiting for finality (about 12–15 min on Ethereum) costs speed. Alerting at inclusion with a "provisional" label, then confirming at finality, gives speed without paging on reorgs.
4. **ML graph models (A4, A5)** are promising, but they are evaluated offline with no base-rate false-alarm numbers. Keep them as a scored feature, not a pager.
5. **Evaluate with NAB-style scoring plus per-bridge false-alarm rate** (D3, D4).
