# Sprint 1 review — Oct 8 – Oct 21

> One file per sprint, written at the sprint boundary (the setup guide's
> *The four sprints* section). This file, the board, and the merged PRs are
> what the sprint's **5%** (of the syllabus's 20% *Prototype & repository
> practice*) is assessed on — as they stand at the boundary.
> This is what makes **Transparency** and carry-over decisions visible at
> grading time — don't reconstruct it later.

**Status: draft started Oct 13 (day 6 of 14).** Everything below reflects the
repository on Oct 13. Cells marked *at the boundary* are filled in at the
Oct 21 close-out, and the numbers are re-run then.

## Progress this sprint — the substance

**Proposal moved:**

| Section | What changed | Where |
|---|---|---|
| Whole proposal, §0–§8 | The proposal submitted on Oct 4 is now `proposal/proposal.md`, in the course template's numbering, with every goal and objective in §2 linked to its issue | PR #24 (released to `main` in PR #33) |
| Cover page | Cover-page table and clickable links to every filed issue | PR #37 |
| §2, §4, Table 7 | Typed issue references for the Word export; §4 tasks written as prose; Table 7 corrected to Group 16's sprint dates | PR #46 (open) |
| `README.md` | Describes BridgeWatch, sponsor project SNX-3 and a summary | PR #25 (released in PR #32) |
| `docs/development-plan.md` | Team charter with quantified triggers, QA owner rotation, AI rules, risk register | PR #31 |
| `docs/sprint-reviews/sprint-1-start.md` | Sprint 1 starting story points | PR #40 |
| `docs/specs/goal-2-detection.md` | Goal 2 specification started | task #34 — *at the boundary* |

**Prototype moved:** at the start of Sprint 1, `prototype/` on `develop` held
only the course's starter. On Oct 9, BridgeWatch v0 was merged (Objective
2.0, story #5, PR #36, released to `main` in PR #38). Work on it began on a
branch before the sprint, with the first commit on Sep 28 and the datasets
and refactor on Oct 7. The detector learns an hour-of-day
baseline per bridge and raises alerts. It runs in four modes: live on Ethereum
mainnet through public nodes, a demo with synthetic bridges and an injectable
exploit, replay of five saved past hacks (Ronin, Harmony, Nomad, Multichain,
Orbit), and a false-alarm evaluation. Evidence: the CI job *Prototype build &
tests* is green on PR #36, and `python -m bridgewatch.replay` writes
`prototype/results/replay.json`.

This is ahead of the course plan, which starts prototype work in Sprint 2.
It runs on public Ethereum nodes, not SonarX data. SonarX access has not been
requested yet (task #28 is open), which is the first risk in proposal §4
Table 8.

## Velocity

From `python scripts/sprint_report.py --sprint 1` on Oct 13; re-run at the
boundary.

| | Story points | Stories |
|---|---|---|
| Planned | 15 (14 at planning on Oct 8, plus 1 for task #45 added Oct 13) | 10 |
| Completed (as of Oct 13) | 5 | 3 |

Story #5 (Objective 2.0, `sp: 8`) was finished on Oct 9, inside Sprint 1,
but carries the `Sprint 2` milestone, so the report counts its 8 points
toward Sprint 2. *At the boundary*, the team decides whether to move it to
`Sprint 1` or leave it, and records why here. The course also reads `sp: 8`
as "too big, split it".

## Completed (merged PRs)

| Story | Owner | Points | PR |
|---|---|---|---|
| #22 Put the submitted proposal into `proposal/proposal.md` and link the board | @garybs16 | 2 | #24, #37 |
| #23 Make the README describe BridgeWatch | @garybs16 | 1 | #25 |
| #26 Write the development plan | @garybs16 | 2 | #31 |
| #5 Objective 2.0: first prototype (milestone `Sprint 2`, see Velocity) | @JakeBowen2005 | 8 | #36 |

Merged into `develop` and waiting for the next release to `main`, where
`Closes #n` takes effect: #29 (board, assigned to @Avnijaglan19, PR #41 by
@JakeBowen2005) and #39 (starting story points, @garybs16, PR #40).

## Carried over — and why

Open on Oct 13. Each row gets its reason and decision *at the boundary*.

| Story | Owner | Why not finished | Decision |
|---|---|---|---|
| #27 Homework 5, Topic and Survey | @JakeBowen2005 | Was due Oct 11; the issue is still open with its checklist unticked | *at the boundary* |
| #28 First questions to the SonarX mentor | @garybs16 | *at the boundary* | *at the boundary* |
| #30 This review | @garybs16 | Written at the boundary | Closes with this PR |
| #34 Start the Goal 2 specification | @1600isad | *at the boundary* | *at the boundary* |
| #45 Typed issue references and sprint dates in the proposal | @garybs16 | PR #46 in review | *at the boundary* |

## Loop health (docs/aidlc/loop-engineering.md §8)

| | This sprint |
|---|---|
| Iterations to green, average per PR | *at the boundary*, from `gh run list --workflow CI` |
| Harness rules added (rows in the harness log) | 0 so far |

Two of our red CI runs (PRs #44 and #46) came from the PR-discipline check,
not from the content of the change: both PRs were opened with a template
comment left in the body. The causes of the other red runs are counted
*at the boundary*. A rule worth adding to the harness log: delete every
`<!-- -->` from the PR template before opening.

## Prototype increment

See *Prototype moved* above. At the end of Sprint 1, BridgeWatch v0 runs live,
in demo mode, as a replay of five past hacks, and as a false-alarm
evaluation. The Sprint 2 meeting (Oct 22) demo shows the proposal and the
board; the prototype demo follows at the Sprint 3 meeting.

## Feedback we received, and what we did about it

| Feedback (source) | What we changed | Issue / PR |
|---|---|---|
| Instructor, PR #8: the sprint report should flag writing tasks without story points | Merged. Every standalone writing task carries its own `sp:` and a `Sprint 1` milestone | PR #8 |
| Instructor, PR #10: the harness G10 should let a writing task stand without a parent | Merged | PR #10 |
| Instructor, #42 and PR #43: one-command Word export; PR #43 was closed and teams asked to pull course files themselves | Pulled the latest course files, including `proposal/reference.docx` and `proposal/to-word.lua` | #42 / PR #44 |
| Instructor, Sprint 1 meeting (Oct 8) | *at the boundary* | |
| Our own check against the course setup guide (Oct 13): §2 and §4 cited issues untyped, §4 listed issues in a table, Table 7 showed another group's sprint dates | Fixed | #45 / PR #46 |

## Contribution snapshot

Oct 8 – Oct 13; re-counted at the boundary. Merged PRs include release PRs
(#32, #33, #38). Reviews count the PRs a member reviewed (approved or
commented).

| Member | Meetings attended | Merged PRs | Issues closed | Reviews given |
|---|---|---|---|---|
| @garybs16 | *at the boundary* | 6 (#24, #25, #31, #32, #33, #40) | 3 (#22, #23, #26) | 4 (#36, #37, #38, #41) |
| @JakeBowen2005 | *at the boundary* | 4 (#36, #37, #38, #41) | 1 (#5) | 5 (#24, #25, #31, #32, #40) |
| @Avnijaglan19 | *at the boundary* | 0 | 0 | 2 (#24, #25) |
| @1600isad | *at the boundary* | 0 | 0 | 3 (#24, #32, #33) |

On Oct 13, @Avnijaglan19 and @1600isad are below our charter's trigger,
"fewer than 2 merged pull requests in a sprint" (`docs/development-plan.md`
§1). Each has a Sprint 1 task that ends in a PR: #34 (Goal 2 specification)
for @1600isad, and #29 for @Avnijaglan19, whose board work landed through a
PR authored by @JakeBowen2005. If they are still below 2 at the boundary, the
charter's consequence applies in Sprint 2: pair with a teammate on a story
and own at least one story's PR. Pairing shows up when commits carry
`Co-authored-by:`.

## What we change next sprint

- **Re-approve after every push.** On PR #25, @JakeBowen2005 approved and
  then pushed a commit of his own to the branch, which dismissed the
  approval. The PR was merged with comments from @Avnijaglan19 but no
  current approval. From now on, nothing merges without a current approval
  from someone who did not commit to the branch.
- **Keep PRs reviewable.** PR #36 was 153 files and about 735,000 added
  lines, about 711,000 of them saved datasets (`research/bridge-hacks/` and
  `prototype/bridgewatch/data/`). That is far over our agreement of under 10
  files and 500 lines. Next time, datasets go in a PR of their own, separate
  from the code.
