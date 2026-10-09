# Development plan — Group 16 Neuroprosthetic

> Due with the proposal. Revisit it at **every sprint review** and change what
> is not working — a plan nobody revises is a plan nobody uses.

## 1. Team charter

### External goals

Beyond the grade, we want BridgeWatch to be a portfolio piece each of us can
demonstrate and explain: an open, explainable detector with a measured
false-alarm rate, built on a real sponsor's data. We also want a working
relationship with SonarX that could lead to a reference. Each member wants
hands-on experience with blockchain data, a real web dashboard, and a
reviewed, tested codebase. When time runs short, we protect the two
measurements the sponsor named — the baseline of normal and the false-alarm
rate — over extra features.

### Attendance

| | Our rule |
|---|---|
| Expected meetings | The sprint meeting with the instructor every other Thursday at 7:00 PM (Section 05), plus one weekly team meeting |
| Acceptable excuse | Illness, a work shift, or a family matter — told in the group chat before the meeting |
| Unacceptable | A silent no-show |
| In an emergency | Tell the team lead in the group chat; push work in progress to your feature branch so someone else can pick it up |

### Accountability — with numbers

| Concern | Trigger (measurable) | Consequence |
|---|---|---|
| Missing meetings | Misses 2 or more team meetings in one sprint | Raised at the next sprint meeting; a second time in the semester → the instructor is told |
| Not contributing code/docs | Fewer than 2 merged pull requests in a sprint | Pairs with a teammate on a story in the next sprint and owns at least one story's PR |
| Work quality | A pull request sent back twice for the same missed acceptance criterion | Pairs with the reviewer on the fix before re-requesting review |
| Not reviewing | Reviews no pull request in a sprint | Takes the reviewer rotation for the whole next sprint |
| Going dark | No response in the group chat for 3 days | The team lead calls; after 5 days the instructor is told |

### Quality assurance

Each sprint, one person owns the harness being green, the board matching
reality, and the sprint review being written (the "harness owner" in
`docs/aidlc/loop-engineering.md` §8). The role rotates so everyone does it once.

| Sprint | QA / harness owner |
|---|---|
| 1 | Samuel, Gary Bennet (@garybs16) |
| 2 | Bowen, Jake (@JakeBowen2005) |
| 3 | Jaglan, Avni (@Avnijaglan19) |
| 4 | Acuna, Isaac (@1600isad) |

### Decision making

We decide by consensus after everyone has spoken. If we still disagree after
one meeting, we take a majority vote; on a tie, the owner of the affected
story decides. No decision stays open longer than one week. Decisions that
change a goal, an objective or a target go into proposal §2 through a pull
request, and targets marked "to be confirmed with the mentor" are confirmed
with the SonarX mentor first.

## 2. Workflow

- Branching, PRs, review and CI: [`git-workflow.md`](git-workflow.md).
- Issues, labels, sprints and the board: setup guide §4.
- **Working agreements we set for ourselves** (recommended defaults, not
  course requirements — see setup guide §8): every member
  makes at least **2 merged contributions per sprint**; pull requests stay
  under **10 files / 500 lines** except by agreement; and we treat
  **unmerged work as unfinished** — if it is not merged by the sprint
  boundary it carries over.

## 3. Use of AI and LLMs

We use assistants (currently Claude, through Claude Code) to brainstorm
approaches, find and summarize sources, draft documents and code, write
tests, and review diffs. Every use is disclosed in the pull request and in
the proposal's AI Usage section.

The course rules are in [`aidlc/hitl-gates.md`](aidlc/hitl-gates.md); the
prompts are in [`aidlc/prompt-library.md`](aidlc/prompt-library.md). Every
deliverable carries a disclosure, and every PR says what was verified.

Our own additions:

- Nobody merges generated code or text they cannot explain at the sprint
  meeting.
- A team member reads every cited source before it goes into the proposal;
  a claim we cannot verify is left out.
- The reviewer spot-checks at least two facts or numbers in every
  AI-assisted pull request.
- The proposal prose is written in our own words; the assistant may suggest
  structure and check facts.
- Every AI-assisted commit carries an `Assisted-by:` trailer.

## 4. Risk register

Review and update at every sprint boundary. Likelihood and impact: H / M / L.
R1–R4 come from proposal §4, Table 8.

| # | Risk | L | I | Early warning sign | What we will do about it | Owner |
|---|---|---|---|---|---|---|
| R1 | SonarX data access is late | M | H | No answer to the first mentor questions (#28) within a week | Keep building on public Ethereum nodes; the design isolates the data source in one step | Samuel, Gary Bennet |
| R2 | Too many false alarms | M | H | Replays of normal days alert more than once per bridge per week | Tune the alert level against whale withdrawals; report the rate openly | Owner of Objective 2.3 (#18) |
| R3 | Too few labeled hacks for testing | M | M | Fewer than five past hacks with usable Ethereum vault data | Use the hacks in proposal Table 1 and simulated attacks | Owner of Objective 2.2 (#17) |
| R4 | Team is new to blockchain data | H | M | A story stalls for a week on how to read transfer records | Schedule learning tasks early and review each other's work | QA / harness owner of the sprint |
| R5 | A member drops the course | L | H | Missed meetings, per the charter triggers | Re-scope to the objectives and tell the instructor early | Samuel, Gary Bennet |

## 5. Technology and environment

From proposal §4, Table 6. The detail lives in the proposal; this is the
working list.

| Item | What we use | Setup owner |
|---|---|---|
| Bridge data | SonarX transfer, balance and price data; real-time stream | Samuel, Gary Bennet (mentor contact) |
| Interim data | Public Ethereum nodes | Bowen, Jake |
| Language and server | Python 3.12, FastAPI | Bowen, Jake |
| Storage | SQLite | Jaglan, Avni |
| Dashboard | A web page with charts | Jaglan, Avni |
| Alerts | Slack messages | Acuna, Isaac |
| Testing and CI | pytest; GitHub Actions on every pull request | Acuna, Isaac |
| Hosting | Docker; host not chosen | To be decided |
