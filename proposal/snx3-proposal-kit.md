# SNX-3 proposal kit: working notes, not proposal text

> **What this is.** Raw material for writing `proposal/proposal.md`: facts,
> the sponsor's exact words, a problem-to-goal mapping, draft goals and
> objectives, and the evidence from prototype v0. It is deliberately in note
> form. The course template (§7) says *"the prose of this proposal must be
> your own writing"*, so the sentences in the proposal are the team's to
> write. Delete this file once the proposal is written.
>
> Drafted by an AI assistant (Claude) on 2026-09-28 for the team to check,
> change, and decide on. Anything marked **[TEAM]** is a decision or a fact
> only the team can supply. Anything marked **[VERIFY]** was not checked
> against a source and must be before it goes into the proposal.

---

## Blockers before writing

1. **[TEAM] Confirm the assignment is SNX-3** in Canvas (HW #3 / Sponsored
   Projects page). Everything below assumes it.
2. **[TEAM] Read the original SNX-3 sponsor document** in Canvas. The only
   sponsor text available here is the course's one-paragraph summary.
   `docs/sponsored-projects.md` says: *"A summary is a starting point, not a
   requirement set."* Anything the original adds or changes wins.
3. **[TEAM] Project title.** The template header still says "Phenoscope" and
   the group name "neuroprosthetic"; the prototype's working name is
   "BridgeWatch". Pick one.
4. **[TEAM] Mentor email** (team lead, cc the instructor): data access, which
   bridges count as "major", which past hacks to replay, a tolerable alert
   volume, and who operates the dashboard. Record answers with dates.

## The sponsor's words (verbatim from docs/sponsored-projects.md, SNX-3)

> Monitor cross-chain bridge activity across SonarX's 130-plus chains and
> detect the early signals of an exploit or drain **in real time**. Ingest
> bridge transaction data, establish baseline flow patterns for the major
> bridges, and build detection logic that fires the moment withdrawals or
> liquidity movements deviate. **Deliverable:** an alerting dashboard that
> could have caught recent bridge hacks as they unfolded. Note the two things
> that make this hard and belong in your objectives: a *baseline* of normal,
> and a false-alarm rate a human would tolerate.

And for every SonarX project: *"Every project consumes SonarX data and ends
in something a user operates — a dashboard or a framework — so 'the query
returns rows' is not the finish line; a person getting an answer is."*

Requirements that can be read directly off that text (each should appear in
§1.2 or §2):

| Sponsor phrase | Requirement it implies |
|---|---|
| "across SonarX's 130-plus chains" | Consume SonarX data; scope which chains/bridges first **[TEAM + mentor]** |
| "in real time" / "fires the moment" | Detection latency is a measured objective |
| "Ingest bridge transaction data" | A data pipeline from SonarX into a common event format |
| "establish baseline flow patterns for the major bridges" | Per-bridge baseline; "major" defined with the mentor |
| "withdrawals or liquidity movements deviate" | Rules on releases and on escrow/liquidity balance |
| "could have caught recent bridge hacks as they unfolded" | Replay real historical hacks and measure time-to-alert |
| "a *baseline* of normal" | Explicit objective, not an implementation detail |
| "a false-alarm rate a human would tolerate" | Explicit, measured objective with a target agreed with the mentor |
| "an alerting dashboard" / "a person getting an answer" | An operator-facing dashboard, evaluated with people |

## §1 Introduction: facts to build from

- Background a CS graduate may lack: what a cross-chain bridge is (lock or
  burn on one chain, release or mint on another); why its escrow is a single
  high-value target; why a drain is irreversible once funds leave.
- Motivation: large past bridge exploits. Candidates to research and cite,
  **[VERIFY] every name, date, and amount from a source you read**: Ronin
  (2022), Wormhole (2022), Nomad (2022), Harmony Horizon (2022), Multichain
  (2023). Do not put dollar figures in the proposal from memory.
- What v0 already showed (see "Evidence from v0" below): drains that play out
  over minutes to hours can be caught early by flow monitoring; single-
  transaction thefts cannot be stopped by monitoring alone.

## §1.1 Related work: candidates to find and read

None of these has been read for this kit. **[VERIFY] each exists and says
what you cite it for; drop any you can't read.**

| Candidate | Kind | Why it may be relevant |
|---|---|---|
| Forta Network | Product (decentralized detection bots) | On-chain threat alerts, including bridge monitoring |
| Hypernative; Hexagate | Products (commercial pre-exploit detection) | Real-time exploit detection; likely the closest competitors |
| CertiK Skynet; Chainalysis / TRM Labs | Products (monitoring, forensics) | Post-incident tracing, risk scores |
| "XScope: Hunting for Cross-Chain Bridge Attacks" (ASE 2022) | Paper | Rule-based detection of bridge attacks; compare approach |
| Academic surveys ("SoK") on cross-chain bridge security | Papers | Taxonomy of bridge attacks, to justify the exploit types |
| Anomaly detection with robust statistics (median/MAD) | Textbook / paper | Justifies the baseline method |

Comparison dimensions worth using in the required table: data coverage
(chains), latency, explainability of alerts, false-alarm handling, open vs.
commercial, and whether it detects before or after funds leave.

## §1.2 Problem statements: draft (note form)

- **P1 No baseline of normal.** A withdrawal can only be called abnormal
  relative to that bridge's normal flow, which varies by bridge, hour, and
  day; without a learned baseline every large transfer looks suspicious.
- **P2 Exploits unfold faster than people notice.** Detection has to happen
  while an attack is in progress, which needs streaming ingest and rules that
  evaluate on every release.
- **P3 Alerts nobody trusts get ignored.** Legitimate large transfers
  ("whales") look like attacks; too many false alarms and operators stop
  looking. The false-alarm rate has to be measured and bounded.
- **P4 Signals must reach a person who can act.** Detection output is only
  useful as an explained alert on a dashboard someone operates.

| Problem | Addressed by |
|---|---|
| P1 No baseline of normal | Goal 1 |
| P2 Detect in time | Goal 2 |
| P3 Tolerable false-alarm rate | Goal 2 |
| P4 A person must get the answer | Goal 3 |

## §2 Goals and objectives: draft

Each goal becomes an **Epic** issue, each objective a **User Story** issue;
put the real issue numbers in §2 once filed. Numeric targets are **[TEAM +
mentor]**: v0 numbers are shown only as a reference point.

- **Goal 1: Learn normal bridge behaviour from SonarX data**
  - 1.1 Ingest release and deposit transactions for **[TEAM: N]** major
    bridges from SonarX into the common event format, with ingest lag under
    **[TEAM: x] minutes** behind chain head.
  - 1.2 Compute a per-bridge, hour-of-day baseline of outflow and release
    count over a trailing 7-day window, and show that at least **[TEAM: y]%**
    of clean 10-minute windows fall inside the normal band.
- **Goal 2: Detect exploits early with a tolerable false-alarm rate**
  - 2.1 Implement detection rules for outflow spikes, release bursts, escrow
    drain, and (where SonarX data allows deposit matching) unbacked releases,
    each producing an explained alert.
  - 2.2 Replay **[TEAM: K]** historical bridge exploits through the detector
    and report time-to-first-alert and share of funds lost before the alert.
  - 2.3 Measure false alarms per bridge per day on at least **[TEAM: D]**
    clean bridge-days and choose the alert threshold that meets a target
    agreed with the mentor.
- **Goal 3: Deliver an alerting dashboard an operator can use**
  - 3.1 Build a live dashboard showing each bridge's status, flow against
    its baseline, and an alert feed with plain-language explanations and
    acknowledgement.
  - 3.2 Evaluate the dashboard with **[TEAM: n]** users (and the mentor) on
    a replayed exploit, recording whether they spot and understand the alert
    within **[TEAM: t]** minutes.

## §3 Approach: the argument, in notes

- **Chosen:** streaming, rule-based detection over robust statistical
  baselines (median and median absolute deviation per hour of day), plus an
  absolute escrow-drain rule that needs no baseline.
- **Why rules first:** explainable alerts ("$X left in 10 minutes; about $Y
  is normal"), which an operator can trust and act on; works with little
  labelled data (there are few real hacks to train on).
- **Alternatives considered:**
  - Supervised ML classifier: too few labelled exploits; opaque alerts.
  - Unsupervised ML (isolation forest, autoencoders): possible later layer
    to catch patterns rules miss; harder to explain; test against the same
    replay set.
  - Mean/standard-deviation baselines: skewed by whales and past incidents;
    v0 uses median/MAD for that reason.
- **Honest limit to state:** monitoring cannot prevent a single-transaction
  theft (v0: about 44% of funds gone at the first alert in the key-compromise
  scenario); prevention before signing is out of scope.
- Implementation details go in §4, not here.

## §4 Environment and resources: facts

- **Data:** SonarX (access pending, **[TEAM]** confirm the form: API, SQL,
  warehouse share). Until then, a synthetic source that produces the same
  event records; real data plugs in without changing the detector.
- **Prototype stack (as built):** Python 3.12, FastAPI, uvicorn, httpx,
  pytest; dashboard in plain HTML/JavaScript with inline SVG charts; GitHub
  Actions CI runs the tests on every pull request.
- **Hosting (optional, not decided):** a Dockerfile exists; Google Cloud Run
  was prepared but not used. **[TEAM]** decide.
- **Diagrams still to draw** (in `docs/design/`, both source and image):
  architecture (SonarX, ingest, detector, alert store, API, dashboard) and
  system context (SonarX, operator, mentor). **[TEAM]** verify every box
  against the code.
- **Skills needed:** blockchain data (bridge contracts, event logs), robust
  statistics, streaming systems, web UI, evaluation design.
- **Specification and design documents:** none yet; list them here as they
  are written.

## §5 Outcomes: v0 facts

- **What v0 is:** BridgeWatch, a thin end-to-end prototype on synthetic data:
  traffic generator, detector, evaluation, API, live dashboard.
- **How to run:** from `prototype/`, `python run_bridgewatch.py`, then open
  http://127.0.0.1:8001. Scorecard: `python -m bridgewatch.evaluate`.
- **What it demonstrates:** a learned baseline; alerts that fire during a
  simulated drain; a measured false-alarm rate and threshold trade-off.
- **Final deliverables (CPSC 491):** the system on SonarX data, the replay
  evaluation on real historical hacks, the dashboard, source code and tests
  in the repository, and a final report.

### Evidence from v0 (synthetic data only, 2026-09-28)

| Exploit type (simulated) | Caught | Median time to first alert | Median share stolen before alert |
|---|---|---|---|
| Mass drain | 12 / 12 | 8.2 min | 0.7% |
| Key compromise | 12 / 12 | 0 min | 43.8% |
| Slow bleed | 8 / 12 | 139.9 min | 16.9% |

**Real-data replay (Orbit Chain bridge, 31 Dec 2023; details in
`prototype/README.md`):** on 14 days of the vault's real Ethereum transfers,
0 false alarms; a critical alert on the first theft ($10M DAI), before a
further $49.8M left 3-17.6 minutes later. One case, and the vault identity
must be confirmed against a published incident report before citing. This is
the strongest evidence for §5 and for the feasibility argument in §3.

False alarms (synthetic): 0.32 per bridge per day on 44 clean bridge-days (13 of 14 from
legitimate whale transfers). State in the proposal that these describe
generated traffic, not real bridges.

## §6 Timeline (CPSC 491): skeleton

Hours and owners are **[TEAM]** estimates. Suggested build order:

| Task (objective) | Milestone | Depends on |
|---|---|---|
| 1.1 SonarX ingest | Real events flowing for the first bridge | SonarX access |
| 1.2 Baselines on real data | Normal band validated on clean history | 1.1 |
| 2.1 Rules on real data | Explained alerts on live data | 1.2 |
| 2.2 Historical replay | Time-to-alert on K past hacks | 1.1, historical data |
| 2.3 False-alarm tuning | Threshold chosen against agreed target | 2.1 |
| 3.1 Dashboard on real data | Operator view live | 2.1 |
| 3.2 User evaluation | Results written up | 3.1, 2.2 |

Assumptions to state: SonarX access by **[TEAM]** date; historical data for
the chosen hacks is available; mentor time for the target-setting meeting.

## §7 AI usage: factual record to disclose (the team writes the paragraph)

From this repository's history of the 2026-09-27/28 sessions with Claude
(Anthropic), used through Claude Code:

- **BridgeWatch prototype** (`prototype/bridgewatch/`,
  `web/bridgewatch.html`, `run_bridgewatch.py`, `tests/test_bridgewatch.py`,
  README section): generated by the AI in full, then run, tested (15 tests),
  and checked in a headless browser. **[TEAM]** review and state the
  fraction after your own edits.
- **ChainSentry** (earlier prototype; may be dropped): the AI added
  hardening (retries, caching, rate limiting, logging), the top-100 coin
  list, 43-chain support, UI fixes, Dockerfile, deploy workflow, and 26 of
  its 37 tests. **[TEAM]** state who wrote the original v0 and how.
- **This kit:** drafted by the AI; the proposal prose is the team's.
- **How it was verified:** automated tests (52 passing), live API checks,
  browser screenshots; the synthetic scorecard is reproducible with fixed
  seeds. Not verified: behaviour on real bridge data.

## §8 References

Only sources a team member has read. The candidates in §1.1 above are a
reading list, not references.
