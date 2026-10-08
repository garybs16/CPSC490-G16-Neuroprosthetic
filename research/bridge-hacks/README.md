> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Bridge hack research: how drains look, how to catch them fast, how to avoid false alarms

This folder collects everything the team learned about cross-chain bridge hacks,
so that people (and AI agents) can analyse it and design BridgeWatch's detection.
BridgeWatch has two goals that pull against each other: **catch a drain as fast
as possible** and **almost never page someone for nothing** (target: ≤ 1 false
alarm per bridge per week).

Compiled 2026-10-07 by several research agents working for Jake Bowen, then
checked by an independent review agent ([05-review/review.md](05-review/review.md)).
It is research input, not a design decision: the team decides what to build.

## Start here

0. **[PLAIN-ENGLISH-SUMMARY.md](PLAIN-ENGLISH-SUMMARY.md):** the short,
   plain-English version of everything here. New to crypto? Read this first.
1. **[04-analysis/implementation-recommendations.md](04-analysis/implementation-recommendations.md):**
   the proposed detection design (signals, thresholds, what pages a human,
   per-bridge profiles, the data needed from SonarX, and a roadmap).
2. **[04-analysis/patterns.md](04-analysis/patterns.md)** and
   **[04-analysis/false-alarm-patterns.md](04-analysis/false-alarm-patterns.md):**
   what real hacks look like, and what normal activity looks like when it
   resembles one.
3. **[01-hack-catalog/catalog.md](01-hack-catalog/catalog.md):** 102 bridge
   incidents from 2021 to 2026 (54 confirmed), grouped by cause, design and
   detectability.

## What is in each section

| Section | Contents |
|---|---|
| [01-hack-catalog/](01-hack-catalog/) | `hacks.csv` / `hacks.json` (102 incidents, with root cause, losses, timeline, on-chain signature and which rules would fire), `catalog.md` (tables and statistics), 20 detailed case pages in `cases/`, `verified-ethereum-cases.md` (30 Ethereum first-theft transactions re-checked on-chain), `sources.md`, `open-questions.md` |
| [02-defenses/](02-defenses/) | How others detect or limit bridge hacks: monitoring tools (`tools.md`), protocol safeguards such as rate limits and pauses (`protocol-defenses.md`), academic papers (`academic.md`), detection techniques and their trade-offs (`techniques.md`), real cases where detection or response helped (`case-studies-stopped-or-limited.md`), and `takeaways-for-bridgewatch.md` |
| [03-onchain-data/](03-onchain-data/) | Real Ethereum transfer data for **10 more hacks** (Poly Network 2021 and 2023, HECO, Ronin 2024, Force Bridge, Shibarium, KelpDAO, Verus, XBridge, plus Qubit as a "vault never moved" control) and **10 normal or stress windows** (Wormhole, Polygon PoS, USDT0, Stargate, Celer, Ronin gateway, Across, the KelpDAO adapter, the USDC-depeg and FTX weeks). Same format as `prototype/bridgewatch/data/`, so the prototype can load it. `fetch_more.py` re-downloads it without API keys; `validate.py` checks it, including balance reconciliation against the chain. |
| [04-analysis/](04-analysis/) | Patterns, false-alarm patterns, the recommended design, `features.csv` (one row per hack), `normal-stats.csv` (one row per normal window), and `experiments/` (scripts that reproduce every number; `run_all.sh`, about 3 minutes, from a copy of `prototype/`) |
| [05-review/](05-review/) | The independent review: what was checked, corrections made, remaining issues |

Together with the 5 hacks and 5 normal windows already in
`prototype/bridgewatch/data/`, the analysis covers **15 hacks with real on-chain
data** (14 replayable) and **29 normal or stress windows**.

## Headline findings

- **The prototype is already as fast as an outflow monitor can be.** It alerts
  on the first confirmed theft in all 14 replayable hacks, 1–13 s after the 6th
  confirmation. But 66% of stolen value had left before *any* such alert was
  possible, because many hacks take most of the money in the first one or two
  transactions.
- **The real problem is false alarms.** Today's rules page 3.03 times per
  bridge-week (13.3 on liquidity pools). The recommended policy (page on a huge
  single release, or when two independent signals agree, for example a large
  release to a never-seen address plus a large net outflow) measured **0.105
  pages per bridge-week with the same detection speed**. That number is
  in-sample; expect worse on new data.
- **The three gaps that matter most:**
  - **Native ETH.** It is not in token logs, and in three hacks it left
    5–34 minutes before any tracked token.
  - **Admin and config changes** (upgrades, signer or threshold changes). They
    came before 12 incidents ($1.14B), and this is the only signal that ever
    warned *before* a loss.
  - **Cross-chain accounting** (a release with no matching deposit, or minted
    supply above locked collateral). It catches the hacks where the vault
    never moves.
- **Response matters as much as detection.** In real incidents the gap between
  "a monitor fired" and "someone paused the bridge" ranged from 38 minutes to
  6 days.
- **Objective 2.2 needs a team and mentor decision.** "Alert before half the
  funds leave in 4 of 5 replays" cannot be met on the current cases by any
  outflow detector (Harmony's first transaction took 54% and Ronin's 95%).
  `implementation-recommendations.md` §7 suggests measurable alternatives.

## Ground rules for this folder

- **Defensive only.** It describes what failed and what a monitor can see, not
  how to attack. Articles are linked and summarised, never copied.
- **Every claim is sourced.** See each section's `sources.md`. Vendor accuracy
  figures are self-reported marketing and are labelled as such.
- **Known limitations:**
  - About 38 catalog incidents are single-source.
  - Shares of vault value exclude native ETH.
  - No liquidity-pool theft is in the replay set.
  - The replay files are clean, so live data errors are untested.
- **AI use (course rule):** this folder was researched and written by AI agents
  (Claude, via Claude Code). Facts were checked against the cited sources and
  the blockchain by a separate review agent. The team should read and verify
  before relying on any of it, and disclose it in the proposal's AI Usage
  section.
