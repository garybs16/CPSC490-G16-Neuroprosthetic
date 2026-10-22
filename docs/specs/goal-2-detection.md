> Epic: #12 · Stories: #5, #16, #17, #18, #19

# Specification — Goal 2: catch hacks early with few false alarms

> Owner: Isaac Acuna · Sprint: 1 (started, carried), 2 (completing) · Status: draft

## Problem

Goal 2 answers problems **P2** and **P3** in proposal §1.2:

- **P2.** *"Hacks happen faster than people notice"* — a drain can empty a
  vault in a handful of withdrawals, and tomorrow’s report is too late.
- **P3.** *"Too many false alarms get the tool ignored"* — large honest
  withdrawals look like attacks; if the alarm rings too often, people stop
  listening.

Goal 1 builds the baseline of normal (Objectives 1.1 and 1.2). Goal 2 uses
that baseline to decide *whether* an alert fires, how fast it fires on a
real drain, and how often it fires on normal days. Goal 3 (epic #13) decides
whether the operator sees and understands the alert.

The five objectives, verbatim from proposal §2:

- **Objective 2.0** ([#5](https://github.com/garybs16/CPSC490-G16-Neuroprosthetic/issues/5)).
  Build a first prototype and demonstrate it on live Ethereum data and on
  one real past hack.
- **Objective 2.1** ([#16](https://github.com/garybs16/CPSC490-G16-Neuroprosthetic/issues/16)).
  Build three alert rules: a sudden jump in money leaving, an unusual burst
  of withdrawals, and the vault losing more than a set share of its money in
  one hour. Each alert explains itself in plain words.
- **Objective 2.2** ([#17](https://github.com/garybs16/CPSC490-G16-Neuroprosthetic/issues/17)).
  Replay five past hacks in which tokens left an Ethereum vault (for
  example, Orbit, Multichain and Harmony). For each, report the minutes from
  the first theft to the first alert and how much money was already gone,
  with the proposed target of alerting before half of the stolen funds had
  left in at least four of the five replays.
- **Objective 2.3** ([#18](https://github.com/garybs16/CPSC490-G16-Neuroprosthetic/issues/18)).
  Count false alarms per bridge over at least 30 normal days, and set the
  alert level to meet a proposed target of no more than one false alarm per
  bridge per week, to be confirmed with the mentor.
- **Objective 2.4 (stretch)** ([#19](https://github.com/garybs16/CPSC490-G16-Neuroprosthetic/issues/19)).
  Where SonarX provides data from both sides of a bridge, add the
  cross-chain accounting check and report how many replayed hacks it detects.

## Scope

**In scope.** The detector in `prototype/bridgewatch/detector.py`: its
hour-of-day baseline, the three proposal alert rules (plus any helpers the
prototype already uses), plain-words alert messages, the offline replay of
saved past hacks (`python -m bridgewatch.replay`), and the false-alarm
evaluation (`python -m bridgewatch.evaluate`). Live mode on public Ethereum
nodes for Objective 2.0. Slack (or webhook) delivery of alert text is part
of this goal’s pipeline (`BRIDGEWATCH_WEBHOOK_URL`); the dashboard that
*shows* alerts is Goal 3.

**Out of scope** for CPSC 490: pausing a bridge or freezing funds; choosing
which bridges SonarX calls “major” (mentor question on #28); a production
SonarX deployment; inventing detection numbers the mentor has not confirmed.
Objective 2.4 stays stretch until both-sides data exists. These are
candidates for CPSC 491 or for a later sprint after the mentor answers.

## The three alert rules (first draft)

Proposal Objective 2.1 names three rules. In the prototype they are
implemented under the names below in `detector.py` (checked on every
release). Defaults come from `DetectorConfig` and can be overridden per
bridge in `bridges.json`.

### 1. Sudden jump in money leaving → `outflow_spike`

| | |
|---|---|
| **Inputs** | Last-10-minute outflow in USD (`win_usd`); baseline median and spread for this hour of day (7-day median / MAD); current escrow; `z_threshold` (default 6); `min_escrow_share` (default 0.5% of escrow); `min_spread_usd` floor on the spread |
| **Fires when** | Outflow is at least `z_threshold` spreads above the hour’s normal **and** moves at least `min_escrow_share` of escrow. Needs a learned baseline (no baseline-based alerts during warm-up). |
| **Severity** | `critical` if the 10-minute outflow is ≥ 5% of escrow; otherwise `warning` |
| **Output (message shape)** | `"{amount} left {bridge} in the last 10 minutes; {normal at this hour}."` |

### 2. Unusual burst of withdrawals → `withdrawal_burst`

| | |
|---|---|
| **Inputs** | Count of releases in the last 10 minutes; baseline median release count and spread for this hour; `z_threshold`; `burst_min_count` (default 12) |
| **Fires when** | Release count is at least `z_threshold` spreads above normal **and** at least `burst_min_count` releases. Needs a learned baseline. |
| **Severity** | `warning` |
| **Output (message shape)** | `"{count} releases ({amount}) from {bridge} in the last 10 minutes; about {median} is normal at this hour."` |

### 3. Vault losing more than a set share in one hour → `escrow_drain`

| | |
|---|---|
| **Inputs** | Net outflow over the last hour (`net_hour`); escrow as it stood an hour ago; `drain_share` (default 5%) |
| **Fires when** | Net hourly outflow ≥ `drain_share` of that escrow. **No baseline required** — losing that share in an hour is treated as never normal. |
| **Severity** | `critical` |
| **Output (message shape)** | `"{bridge} lost {amount} net in the last hour: {share%} of its {escrow} escrow; losing more than {drain_share%} in an hour is never normal."` |

### Also in the prototype (not one of the three proposal rules)

| Rule | Role |
|---|---|
| `large_withdrawal` | One release ≥ `large_withdrawal_share` of escrow and ≥ `large_withdrawal_min_usd`. Helps catch a single huge honest-looking transfer; not counted as one of Objective 2.1’s three. |
| `unbacked_release` | Release with no matching deposit when message-matching data is available (`use_message_matching`). Candidate input for stretch Objective 2.4; off by default today. |

**Shared behaviour.** One live alert per bridge and rule per cooldown
(default 1 hour): repeats update the same alert instead of paging again.
Alerts on one bridge within the cooldown form one *incident*; the notifier
sends one message per incident. Every alert message names the bridge, the
amount (or count), the time window, and the comparison with normal (or why
no normal is needed), per Objective 2.1 and the tests in
`prototype/tests/test_bridgewatch.py`.

## Functional requirements

EARS form, so each becomes a test or a checkable report row.

| ID | Requirement | Story |
|---|---|---|
| FR-1 | When live Ethereum withdrawals are fed into the prototype, the system shall evaluate them with the detector and expose bridge state and alerts through the API. | #5 |
| FR-2 | When a saved past-hack dataset is replayed, the system shall run the same detector and write a result that names whether an alert fired. | #5 |
| FR-3 | When last-10-minute outflow is far above the hour’s normal and large enough relative to escrow, the system shall raise an `outflow_spike` alert whose message names the bridge, the amount, the window and the comparison with normal. | #16 |
| FR-4 | When last-10-minute release count is far above the hour’s normal and at least the burst minimum, the system shall raise a `withdrawal_burst` alert with the same plain-words fields. | #16 |
| FR-5 | When net outflow over the last hour exceeds the configured share of escrow, the system shall raise an `escrow_drain` alert with the same plain-words fields, without needing a baseline. | #16 |
| FR-6 | When each of five saved Ethereum-vault hacks is replayed, the system shall report minutes from first theft to first alert and the share of stolen funds already gone at that alert. | #17 |
| FR-7 | When at least 30 normal days per bridge are evaluated, the system shall report false alarms per bridge per week. | #18 |
| FR-8 | When SonarX provides both sides of a bridge, the system shall run a cross-chain accounting check and report how many of the replayed hacks it detects. | #19 |

## Non-functional requirements

| ID | Requirement | Why it matters here |
|---|---|---|
| NFR-1 | Baseline-based rules do not fire during warm-up before enough history exists. | Avoid a flood of nonsense alerts on day one (P3). |
| NFR-2 | Alert rate on normal days is measured and published; the proposed target is ≤ 1 false alarm per bridge per week until the mentor confirms another number. | Sponsor difficulty named in proposal §2 (Objective 2.3). |
| NFR-3 | Detection is evaluated within about one minute after a withdrawal’s block is confirmed six blocks deep (proposal §2 definition of *real time*). | P2: tomorrow’s report is too late. |
| NFR-4 | Replay and false-alarm evaluation run offline from `prototype/` with no paid API key required. | Teammates, the instructor and the sponsor can reproduce the numbers. |

## Acceptance criteria

### Objective 2.0 (#5)

Someone who did not write the prototype can check these from `prototype/`:

- [ ] `python run_bridgewatch.py --demo` (or live mode per the prototype README) starts and serves bridge state with the detector attached (FR-1).
- [ ] `python -m bridgewatch.replay` on at least one saved hack writes a result under `prototype/results/` that shows whether an alert fired (FR-2).
- [ ] Offline tests in `prototype/tests/` covering the detector pass under CI (*Prototype build & tests*).

*(Story #5 was completed in Sprint 1 via PR #36; these criteria document what “done” means so later changes cannot silently remove it.)*

### Objective 2.1 (#16)

- [ ] The three rules `outflow_spike`, `withdrawal_burst` and `escrow_drain` exist and match the input/output tables above (FR-3, FR-4, FR-5).
- [ ] Each of those three rules has an automated test that fails if the rule or its plain-words message shape is removed.
- [ ] Every alert message from those rules names the bridge, the amount (or count), the time window, and the comparison with normal (or why normal is not used for `escrow_drain`).
- [ ] Someone who did not write the detector can trigger each rule in demo or unit-test form and read the message without looking at the code.

*(Story #16 was completed in Sprint 1 via PR #54; keep the criteria so regressions are visible.)*

### Objective 2.2 (#17)

- [ ] Five saved past-hack datasets with Ethereum vault outflows are replayable (the prototype README currently lists Ronin, Harmony, Nomad, Multichain, Orbit).
- [ ] `python -m bridgewatch.replay` writes, for each case: minutes from first theft to first alert, and how much of the stolen funds had already left (FR-6).
- [ ] The write-up (linked from proposal §4 or a sprint review) states whether the proposed target — alert before half the stolen funds left, in at least four of five replays — was met, and if not, which cases missed and why.
- [ ] Numbers in that write-up match the JSON the command produced (no hand-waved figures).

### Objective 2.3 (#18)

- [ ] False alarms are counted over at least 30 normal days per bridge (FR-7), via `python -m bridgewatch.evaluate` (and `--real` when real windows are used).
- [ ] The report states false alarms per bridge per week, by rule.
- [ ] The alert level (`z_threshold` and related config) used for the reported rate is named in the write-up.
- [ ] The target “≤ 1 false alarm per bridge per week” is either met, or explicitly replaced by a mentor-confirmed target recorded on #28 / #18 — not silently lowered in the doc to match a worse rate.

### Objective 2.4 (#19) — stretch

- [ ] Preconditions are written down: which bridges have both-sides SonarX data, and what “matching deposit” means in that feed.
- [ ] With that data available, a cross-chain accounting check runs (FR-8) and a table reports how many of the replayed hacks it detects.
- [ ] If both-sides data never arrives in CPSC 490, the story is marked blocked with the mentor answer dated on #28 — not closed as done.

## Open questions

| Question | Owner | Needed by |
|---|---|---|
| Confirm the false-alarm target (≤ 1 per bridge per week) and the “half the stolen funds” replay target with the SonarX mentor. | Gary Samuel (mentor contact, #28); Isaac Acuna tracks the answer on #18 / #17 | Sprint 2 |
| Which three bridges count as “major” for ongoing live watch once SonarX access exists? | Gary Samuel (#28) | before Objective 1.1 / live SonarX work |
| Should `large_withdrawal` stay as a fourth helper rule, or be folded into how we describe Objective 2.1 to the sponsor? | Isaac Acuna, with the team | Sprint 2 planning |
| For Objective 2.4: does SonarX expose deposit↔withdrawal matching we can trust, or only separate per-chain feeds? | Gary Samuel (#28) | before starting #19 |
| Replay target missed on some cases today (see prototype README). Do we tune rules, change the target with the mentor, or accept a documented miss for CPSC 490? | Isaac Acuna | Sprint 3 (Objective 2.2 write-up) |
