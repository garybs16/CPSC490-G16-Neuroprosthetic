> Epic: #13 · Stories: #20, #21

# Specification — Goal 3: an operator dashboard they can act on

> Owner: Avni Jaglan · Sprint: 1 (started), 2 (completed) · Status: draft

## Problem

Goal 3 answers problem **P4** in proposal §1.2: *"A warning only helps if
someone understands it. The alert must reach a person who can act and say
clearly what happened."* Goals 1 and 2 decide *whether* an alert fires;
this goal decides whether the operator (proposal Table 2: "the person who
watches BridgeWatch and responds to alerts") sees it, understands it and
can tell the team someone is on it.

The two objectives, verbatim from proposal §2:

- **Objective 3.1** ([#20](https://github.com/garybs16/CPSC490-G16-Neuroprosthetic/issues/20)).
  Build a live dashboard showing each bridge's status, its money flow
  compared with normal, and a list of alerts the operator can mark as seen,
  which is useful for seeing activity at a glance.
- **Objective 3.2** ([#21](https://github.com/garybs16/CPSC490-G16-Neuroprosthetic/issues/21)).
  Test the dashboard with four users on a replayed hack, and record whether
  they notice and understand the alert within five minutes.

## Scope

**In scope.** One web page served by the prototype (`prototype/web/bridgewatch.html`,
served at `/` by `prototype/bridgewatch/app.py`) with three parts: bridge
status, money flow compared with normal, and the alert list with "mark as
seen". The same page in live mode (real Ethereum bridges), demo mode
(synthetic bridges) and on a replayed hack. A scripted user test of that
page with four people.

**Out of scope** for CPSC 490: user accounts and roles (the prototype has
one shared API token, `BRIDGEWATCH_API_TOKEN`); pausing a bridge or freezing
funds from the dashboard (the operator does that "using their own tools",
proposal §5); mobile apps; Slack message design (the alert *text* is
Objective 2.1, #16, and Slack delivery is part of the alert pipeline, not
this page). These are candidates for CPSC 491.

## The three dashboard parts (first draft)

What each part shows, and where the data comes from in the prototype API
(`prototype/API.md`).

### 1. Bridge status

One row per monitored bridge, from `GET /api/state` → `bridges[]`:

| Column | Field | Notes |
|---|---|---|
| Bridge | `name`, `chains` | e.g. "OP Mainnet bridge", Ethereum → OP Mainnet |
| Status | `status`, `worst_severity` | `ok`, `learning` (baseline not ready yet), or `alert`, shown as Warning or Critical |
| Escrow | `escrow_usd` | money currently held in the vault |

A bridge with an unseen alert is visually set apart (colour **and** text,
so it does not rely on colour alone), and the Monitor tab shows the
number of live alerts.

### 2. Money flow compared with normal

- In the bridge table: **Out, last hour** (`outflow_last_hour_usd`) next to
  **Normal, 1 h** (`normal_hour_usd`), with the ratio when it is above normal.
- For the selected bridge, a chart of 10-minute outflow over the last
  24 hours with the learned normal and the alert line
  (`GET /api/series/{bridge}` → `out_usd`, `normal_usd`, `alert_line_usd`),
  alerts marked on the chart, and the same data as a table for people who
  cannot read the chart.
- While the baseline is learning, "normal" says *Learning*, never $0.

### 3. Alert list with "mark as seen"

From `GET /api/alerts`, newest first. Each alert shows severity, time, the
bridge and rule, and its plain-words message (Objective 2.1, #16), plus the
worst point so far if it got worse. A **Mark as seen** button calls
`POST /api/alerts/{id}/ack`; afterwards the alert stays in the list, labelled
**Seen**, and no longer counts toward the bridge's status. In live mode this
needs the API token; without one the page explains why it cannot mark
alerts as seen instead of failing silently.

## Functional requirements

EARS form, so each becomes a test or a test-session check.

| ID | Requirement | Story |
|---|---|---|
| FR-1 | When the dashboard is open, the system shall show every monitored bridge with its status (OK, Learning, Warning or Critical) and its escrow. | #20 |
| FR-2 | When the dashboard is open and a bridge has a baseline, the system shall show that bridge's outflow over the last hour next to its normal outflow for that hour. | #20 |
| FR-3 | When the operator selects a bridge, the system shall chart its 10-minute outflow for the last 24 hours together with its normal range and the level at which an alert fires. | #20 |
| FR-4 | When the dashboard is open, the system shall list the alerts newest first, each with its severity, time, bridge and plain-words message. | #20 |
| FR-5 | When the operator marks an alert as seen, the system shall show that alert as seen and stop counting it toward the bridge's status. | #20 |
| FR-6 | While the dashboard is open, the system shall refresh bridge status and the alert list without the operator reloading the page. | #20 |
| FR-7 | When a replayed hack is shown to a test user, the team shall record whether the user noticed the alert, whether they understood it, and how long each took, up to five minutes. | #21 |

## Non-functional requirements

| ID | Requirement | Why it matters here |
|---|---|---|
| NFR-1 | Status is never shown by colour alone; every coloured state also has a text label. | A colour-blind operator must still see a Critical bridge. |
| NFR-2 | Marking an alert as seen in live mode needs the API token; the token is kept only in the browser tab. | Anyone who can reach the port could otherwise silence alerts. |
| NFR-3 | The page polls the API no more often than every 10 s (it polls every 10 s today). | `/api/state` is rebuilt about every 15 s in live mode, so faster polling adds load and shows nothing new (prototype/API.md). |
| NFR-4 | The page is one HTML file with no build step and no external scripts. | Anyone (teammates, the instructor, the sponsor) can run it from a plain checkout. |

## Acceptance criteria

### Objective 3.1 (#20)

Someone who did not build the page can check each of these by running
`python run_bridgewatch.py --demo` from `prototype/` and opening
<http://127.0.0.1:8001>:

- [ ] Every demo bridge appears with a status label and its escrow (FR-1).
- [ ] Each bridge with a baseline shows "Out, last hour" and "Normal, 1 h" (FR-2).
- [ ] Selecting a bridge shows its 24-hour outflow chart with the normal
      range and the alert level, and the same values as a table (FR-3).
- [ ] After "Simulate exploit on this bridge", within the next refresh the
      bridge's status turns Warning or Critical and its alert appears at the
      top of the list with a plain-words message (FR-4, FR-6).
- [ ] Clicking **Mark as seen** on that alert labels it **Seen**; once all of
      a bridge's alerts are seen, the bridge no longer shows an alert (FR-5).
- [ ] FR-1, FR-2, FR-4 and FR-5 each have an automated test in
      `prototype/tests/` that fails if the behaviour is removed.

### Objective 3.2 (#21)

- [ ] A written test script exists (in `docs/` before the sessions run)
      that names the replayed hack, what the user is told beforehand, what
      counts as "noticed" and "understood", and how time is measured.
- [ ] Four users each complete one session on the same replayed hack.
- [ ] For each user, the record states: noticed (yes/no, seconds),
      understood (yes/no, seconds, and their answer in their own words),
      both measured against the five-minute limit (FR-7).
- [ ] The results, including any user who did **not** notice or understand
      the alert within five minutes, are written up and linked from
      proposal §4.

## Open questions

| Question | Owner | Needed by |
|---|---|---|
| Who are the four users: teammates, other students, or people from SonarX? Teammates know the tool, which would bias the result. | Avni Jaglan, with the team | Sprint 3 planning |
| What counts as "understood"? Proposed: the user can say, in their own words, which bridge, roughly how much money and why it is unusual. To be agreed before the sessions, not after. | Avni Jaglan | before the test script is written |
| Which replayed hack is shown? The prototype replays five (README, "Real hack replay"); one with a clear first alert (e.g. Orbit) is simplest to explain. The dashboard does not yet play a replay back in real time, so this may need a small "replay into the dashboard" mode. | Avni Jaglan | Sprint 3 |
| Does SonarX want the dashboard on their own data/infrastructure, or is the prototype page enough for CPSC 490? | Gary Samuel (mentor contact, #28) | Sprint 2 |
| Should "seen" record *who* marked it? The prototype has one shared token and no user accounts. | Team | CPSC 491 |
