# Bridge-exploit monitoring tools: comparison and notes

> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

BridgeWatch (CSUF CPSC 490, sponsor SonarX, SNX-3). Research date: 2026-10-07.
Every claim has a URL. Vendor numbers are **self-reported** unless marked otherwise. Full source list: `sources.md`.

## 1. Comparison table

| Tool | Main signals | Pre-attack or mempool? | Claimed latency | Published accuracy / false-alarm data | Openness / price | Documented bridge cases |
|---|---|---|---|---|---|---|
| **Forta** (Bridge Threat Detection Kit + Attack Detector) | Community bots: bridge balance difference, asset drained, large balance decrease, anomalous volume, ML token-transfer anomaly, Tornado-funded interaction, suspicious contract creation, privileged function/event watchers. An alert combiner groups these by address [F1] | Yes. Funding and preparation stages (contract deployment, Tornado funding) [F3] | Per block. No end-to-end figure published | Oct 2023: 450 alerts, "contextual" precision 100% and recall 70%. Early recall was 40% [F4]. 80–83% of attacked protocols had zero false alarms in the 60 days before their attack [F7][F5] | Bot code is open. Attack Detector premium feed costs $399/month [F5] | Ronin 2022: a retrospective says a high-gas alert fired at 13:46:46 UTC on the attack day. Nobody acted on it, and the hack stayed unnoticed for 6 days [F6]. I found no published Forta alert timeline for Nomad, Harmony or Ronin 2024 |
| **Hypernative** | Off-chain ML and heuristics. Balance and supply integrity (lock vs mint), message matching across source and destination, admin and upgrade changes, market and oracle signals [H1]. Guardian simulates transactions before signing [H3] | Yes. Flags suspicious deployers and contracts before the exploit [H2] | Claims a warning more than 2 minutes before the first exploit tx in 98% of cases [H1] | Claims 99.5–99.8% detection and under 0.001% false positives, with no methodology [H3] | Commercial and closed. No public price | Hyperbridge, 2026-04-13: flagged the main mint at 03:55:23 UTC, in the same minute (an earlier ~245 WETH release at 03:02:11 UTC preceded it; see 01-hack-catalog). The attacker kept going until at least 05:07 UTC before the freeze [H2] |
| **Hexagate** (Chainalysis, acquired Dec 2024) | Proprietary ML, a DSL for custom invariants, address and threshold rules [X1] | Claims most hacks flagged more than 2 minutes ahead [X1] | "Real-time"; no number given | Claims detection of about 98% of hacks with "tuned" false positives, with no false-positive rate given [X1][X2] | Commercial. Price undisclosed (deal estimated at about $60M) [X2] | Says it protects bridges, but no named case with timestamps [X1] |
| **BlockSec Phalcon** | AI risk grading of every transaction plus user trigger rules. Automated response, including front-running the attacker [B1] | Yes. Can block by front-running [B2] | Grading is "millisecond-level" [B1] | FAQ: about 1% false positives over 2 years of internal operation (self-reported) [B1] | Commercial | Claims 20+ blocked attacks and more than $20M rescued (Paraspace, Saddle and others; none are bridges) [B2][B3]. No bridge rescue found |
| **Cyvers** | AI/ML on transactions, plus a pre-signing API that blocks or warns [C2] | Yes. Flagged Multichain's $2 test transactions [C1] | Not published | Claims 95% "accuracy" in a grant submission [C3] | Commercial | Claims it was first to flag Multichain (2023-07-06) [C1]. Orbit 2023 [C4]. Its CTO said KelpDAO was 3 minutes from losing another $100M [C5] |
| **CertiK Skynet** | ML plus on-chain and off-chain signals. Public alert feed on X [K1] | Partly | Says threats can be flagged "within seconds" [K1] | None | Commercial. The alert feed is public | Harmony incident analysis gives a UTC timeline [K2] |
| **Hacken Extractor** | Default triggers: ownership transfer, upgrades, transfer thresholds, blacklisted and non-whitelisted counterparties. Integrates the Forta Attack Detector [HK1] | Through Forta | Not published | Forta says it caught 75% of major 2023 hacks, 42% before exploitation [HK2] | Commercial (beta in 2023) | None found |
| **OpenZeppelin Defender → OZ Monitor** | Event and function filters with expression matching. Alerts by Slack, Discord, email, Telegram, webhooks and scripts [OZ2] | No | Polls every block | None | Hosted Defender retired 2026-07-01. Monitor is now open source (AGPL v3, Rust, self-hosted) [OZ1] | None |
| **Tenderly Alerts / Web3 Actions** | Event, function, balance and state alerts that trigger serverless actions [T1] | Simulation is a separate product | Status page shows backlogs up to about 7 minutes (June 2026). In May 2025 four hours of blocks were skipped [T1] | None | Commercial SaaS | None. Lesson: a shared SaaS pipeline can lag exactly when chains are busy |
| **Guardrail** (now part of Rain) | Pre-built guards (oracle manipulation, flash loans, governance) plus custom invariant and permission guards. Auto-pause and PagerDuty integration [G1] | Partly | Claims sub-second detection [G1] | None | Commercial | None |
| **Venn / Ironblocks** | On-chain firewall. A network of operators screens transactions before execution [V1] | Yes, before execution | n/a | None found | Commercial or token-based | None |
| **SphereX** | On-chain allowlist of call-trace patterns. Anything not on the list reverts [S1] | Yes, inline | Inline (gas cost) | None | Commercial | None |
| **Range** | Risk API covering 300+ chains, address flagging, cross-chain fund tracing, IBC rate-limit dashboards and alerting for Osmosis [R1][R2] | Behavioral pre-attack signals (privacy-protocol funding, dormant wallets) [R1] | Not published | None | Commercial. Dashboards are public | Hyperbridge: flagged the attacker contracts after the fact, with no timestamp [R1]. Built the Osmosis IBC rate-limit tooling [R2] |
| **Chainalysis Incident Response / Alterya** | Human investigators and tracing. A 24/7 hotline [CH1] | No (after the fact) | Hours | n/a | Paid retainer | Generic. Alterya is a fraud-AI acquisition; no bridge link found |
| **TRM Beacon Network** | Shared flags: an investigator flags an address, funds are traced automatically, and participating exchanges are alerted [TR1] | No (cash-out stage) | "Real-time" alerts to exchanges | TRM's own examples: $1.5M frozen in one case [TR1] | Free for verified exchanges and law enforcement | General hacks. Founding members include Binance, Coinbase, Kraken and SEAL |

## 2. Per-tool notes

### Forta Network
- **Bridge kit.** 18 bots [F1]. The ones most relevant to BridgeWatch:
  - **Bridge Balance Difference** alerts when the two sides of a bridge drift out of balance. It is a Bot Wizard template that subscribes to deposit and withdraw bots on each chain through `handleAlert` [F1][F2].
  - **Asset Drained** and **Large Balance Decreases.** The latter was deployed for Ronin, Harmony, Multichain and others [F1].
  - **Anomalous Transaction Volume**, which counts both successful and failed transactions. Failed attempts are an early sign, as with Nomad's first attempt.
  - **Time Series Analyzer** template, for noisy series.
  - **Tornado Cash Funded Account Interaction.**
  - **Monitor Function Calls / Events** for privileged functions.
- **Attack Detector / alert combiner.** It maps alerts onto four attack stages: Funding, Preparation, Exploitation, Money Laundering. It raises a high-precision alert only when several stages line up under one address [F3][F5]. Version 2.0 adds BlockSec logic and uses positive reputation plus ML to cut false positives [F5].
- **False-alarm framing.** Raw volume was high: 450 alerts in Oct 2023. Forta argues the relevant figure is *contextual* precision, meaning only alerts that touch your own addresses [F4][F7]. Protocols whose addresses attackers use often (USDC, routers) still get frequent alerts. Protocols attackers ignore get almost none [F7]. **For BridgeWatch:** count false alarms per monitored bridge, not globally, which matches SonarX's target of at most 1 false alarm per bridge per week.
- **Real case.** Ronin, March 2022. A retrospective says a high-gas alert at 13:46:46 UTC on 2022-03-23 "could have" been a high-confidence signal, with a high-value alert minutes later. Forta itself calls those alerts noisy overall. The hack was discovered 6 days later [F6].

### Hypernative
- Its bridge monitoring categories map almost one-to-one onto the BridgeWatch backlog [H1]:
  - balance and supply integrity (lock vs mint, mint without lock)
  - message integrity (source and destination event matching, failed messages)
  - access and governance (ownership changes, upgrades)
  - market (price deviation, pool composition, large-holder exits)
  - operational health (executor balance, oracle staleness)
- **Hyperbridge 2026-04-13** [H2]:
  - About 15 minutes before the exploit, a test transaction was flagged (deployer and contract marked suspicious).
  - The main mint was detected at 03:55:23 UTC.
  - Further exploit transactions came at 04:20, 04:26, 04:33, 04:51 and 05:07 before the freeze.
  - **This is a textbook "monitor fired, response lagged" case.** The main mint was flagged within seconds, but containment took more than 70 minutes. (The catalog's first theft, a ~245 WETH release at 03:02:11 UTC, came ~53 minutes before that flag.)
- Accuracy claims (99.5–99.8% detection, under 0.001% false positives) appear only in marketing [H3].

### Hexagate (Chainalysis)
- Teams write invariants in a DSL, test them on testnet, then run them on mainnet. An example invariant: "users can't withdraw more than they deposit" [X1].
- Automated responses: pause, rate-limit functions, blocklist [X1].
- Claims about 98% of hacks detected, most of them ahead of time [X1][X2]. Not independently verified.

### BlockSec Phalcon
- Combines AI risk grading with user-defined rules. Its FAQ says matching risk level *with* custom rules drives false positives toward zero [B1].
- This is the same "combine two weak signals" idea as Forta's combiner.
- Its strongest feature is automated front-running and rescue. All public rescues are DeFi pools, not bridges [B2][B3].

### Cyvers
- **Multichain:** says it flagged three $2 test transactions about 2 hours before the main drain [C1].
- **KelpDAO:** its CTO said a blacklist stopped the second attempt with 3 minutes to spare [C5]. Other reports credit Kelp's pause instead (see case studies).
- Accuracy claims come from a grant application [C3].

### OpenZeppelin Monitor (formerly Defender Monitor)
- Hosted Defender shut down on 2026-07-01. The Monitor is now an open-source Rust service: it watches blocks, applies filter expressions, runs triggers and sends notifications [OZ1][OZ2].
- **Most relevant to BridgeWatch as a reference architecture** for the polling, filtering and notification pipeline. It keeps its block cursor between restarts.

### Tenderly
- Its value to BridgeWatch is mostly as a cautionary tale. Its public status page documents alert backlogs up to about 7 minutes during chain-wide volume surges, and one incident that **skipped** a 4-hour window of blocks [T1].
- **BridgeWatch should track its own ingest lag as a metric and alert on missing blocks.**

### Range
- Built the monitoring and anomaly detection for Osmosis IBC rate limits, plus public dashboards. The rate-limit controller is a 3-of-6 multisig [R2][R3].
- Most relevant if SonarX covers Cosmos/IBC.

### Venn/Ironblocks, SphereX, Guardrail
- These are prevention layers that sit inside or in front of the contract. They need the bridge team's cooperation, so they are out of scope for an external monitor like BridgeWatch.
- SphereX's allowlist of call-trace patterns [S1] is a useful idea though: "has this function-call shape ever been seen on this bridge?" is a cheap novelty feature.

### Recovery and intel networks (Chainalysis IR, TRM Beacon)
- These act after the drain, by freezing funds at exchanges [CH1][TR1].
- BridgeWatch can feed them by exporting attacker addresses fast, with one-click export from an alert.

## 3. What the vendor landscape tells BridgeWatch
1. **Every serious vendor combines signals.** Examples: Forta's combiner, Phalcon's risk level plus rules, Hypernative's multi-category scoring. Single-metric alerts are what produce alert noise [F7][B1].
2. **No vendor publishes an audited false-alarm rate.** Forta's "contextual precision" method [F4] is the only measurement approach with a written method. BridgeWatch can borrow it and publish its own per-bridge false-alarm rate, which would be a differentiator.
3. **Pre-attack signals (funding, deploy, test tx) gave 15 minutes to 2 hours of warning** in Hyperbridge [H2] and Multichain [C1]. But they fire on many benign deployers, so treat them as context that raises severity, not as pages on their own.
4. **Detection is rarely the bottleneck; response is.**
   - Hyperbridge: same-minute detection, more than 70 minutes to freeze [H2].
   - KelpDAO: about 46 minutes to pause [KD1].
   - Ronin 2022: 6 days to discover [F6].
