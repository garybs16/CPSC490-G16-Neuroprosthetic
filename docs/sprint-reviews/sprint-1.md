# Sprint 1 review — Oct 8 – Oct 21

> One file per sprint, written at the sprint boundary (the setup guide's
> *The four sprints* section). This file, the board, and the merged PRs are
> what the sprint's **5%** (of the syllabus's 20% *Prototype & repository
> practice*) is assessed on — as they stand at the boundary.
> This is what makes **Transparency** and carry-over decisions visible at
> grading time — don't reconstruct it later.

**Status: draft, updated Oct 19 (day 12 of 14).** Everything below reflects
the repository on Oct 19. Cells marked *at the boundary* are filled in at the
Oct 21 close-out, and the numbers are re-run then.

## Progress this sprint — the substance

**Proposal moved:**

| Section | What changed | Where |
|---|---|---|
| Whole proposal, §0–§8 | The proposal submitted on Oct 4 is now `proposal/proposal.md`, in the course template's numbering, with every goal and objective in §2 linked to its issue | PR #24 (released to `main` in PR #33) |
| Cover page | Cover-page table and clickable links to every filed issue | PR #37 |
| §2, §4, Table 7 | Typed issue references for the Word export; §4 tasks written as prose; Table 7 corrected to Group 16's sprint dates | PR #46 (released in PR #48) |
| Word export | `proposal/reference.docx` and `proposal/to-word.lua` from the course repository: one command turns `proposal.md` into the course Word template | PR #44 (released in PR #48) |
| `README.md` | Describes BridgeWatch, sponsor project SNX-3 and a summary | PR #25 (released in PR #32) |
| `docs/development-plan.md` | Team charter with quantified triggers, QA owner rotation, AI rules, risk register | PR #31 |
| `docs/sprint-reviews/sprint-1-start.md` | Sprint 1 starting story points | PR #40 (released in PR #48) |
| `docs/specs/goal-2-detection.md` | Goal 2 specification started | task #34 — *at the boundary* |
| `docs/specs/goal-3-dashboard.md` | Goal 3 specification started | task #50 — *at the boundary* |

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
It runs on public Ethereum nodes, not SonarX data. On Oct 19, task #28 (the
first questions to the SonarX mentor, including data access) is still open;
SonarX access is the first risk in proposal §4 Table 8.

## Velocity

From `python scripts/sprint_report.py --sprint 1` on Oct 19; re-run at the
boundary.

| | Story points | Stories |
|---|---|---|
| Planned | 17: 14 at planning on Oct 8, plus task #45 (1) added Oct 13 and task #50 (2) added Oct 19 | 11 |
| Completed (as of Oct 19) | 8 | 6 |

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
| #29 Set up the GitHub Projects board and link it from the README | @Avnijaglan19 | 1 | #41 (authored by @JakeBowen2005) |
| #39 Save the Sprint 1 starting story points | @garybs16 | 1 | #40 |
| #45 Typed issue references and sprint dates in the proposal | @garybs16 | 1 | #46 |
| #5 Objective 2.0: first prototype (milestone `Sprint 2`, see Velocity) | @JakeBowen2005 | 8 | #36 |

## Carried over — and why

Open on Oct 19. Each row gets its reason and decision *at the boundary*.

| Story | Owner | Why not finished | Decision |
|---|---|---|---|
| #27 Homework 5, Topic and Survey | @JakeBowen2005 | Was due Oct 11; the issue is still open with its checklist unticked | *at the boundary* |
| #28 First questions to the SonarX mentor | @garybs16 | *at the boundary* | *at the boundary* |
| #30 This review | @garybs16 | Written at the boundary | Closes with this PR |
| #34 Start the Goal 2 specification | @1600isad | *at the boundary* | *at the boundary* |
| #50 Start the Goal 3 specification | @Avnijaglan19 | Filed Oct 19 | *at the boundary* |

## Loop health (docs/aidlc/loop-engineering.md §8)

| | This sprint |
|---|---|
| Iterations to green, average per PR | 1.4: 13 CI runs to first green across 9 feature PRs (#24, #31, #36, #37, #40, #41, #44, #46, #47); release PRs from `develop` not counted |
| Harness rules added (rows in the harness log) | 0 so far |

Every red CI run on a feature PR this sprint had the same cause, and it was
never the content of the change: the PR-discipline check failed on a
template comment (`<!-- -->`) left in the PR body. That happened four times,
on PR #31 (once), PR #44 (twice) and PR #46 (once). A rule worth adding to
the harness log at this review: delete every `<!-- -->` from the PR template
before opening the PR.

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
| Instructor's repository status page (`docs/repo-readiness.md` in the course repository), Group 16 card: convert the bare issue links to typed references | Done | #45 / PR #46 |
| Same card: the Sprint Board is not readable | Made the board public on Oct 19 | |
| Same card: assign the three epics | Assigned on Oct 13: Goal 1 to @garybs16, Goal 2 to @1600isad, Goal 3 to @Avnijaglan19 | #11, #12, #13 |
| Same card: a branch held work not in `develop` | Checked that every commit on `feature/5-bridgewatch-prototype` was already in `develop`, then deleted it (Oct 13) | |
| Same card: 6 direct commits to `main`/`develop`; turn on branch protection | Protection on both branches now also applies to administrators (Oct 13), so no one can push without a reviewed PR. The 6 earlier commits remain in the history | |
| Same card: review and merge the open pull requests | Merged on Oct 19 | PRs #44, #46, #47, #48 |
| Instructor, Sprint 1 meeting (Oct 8) | *at the boundary* | |
| Our own check against the course setup guide (Oct 13): §2 and §4 cited issues untyped, §4 listed issues in a table, Table 7 showed another group's sprint dates | Fixed | #45 / PR #46 |

## Contribution snapshot

Oct 8 – Oct 19; re-counted at the boundary. Merged PRs include release PRs
(#32, #33, #38, #48). Reviews count the PRs a member reviewed (approved or
commented).

| Member | Meetings attended | Merged PRs | Issues closed | Reviews given |
|---|---|---|---|---|
| @garybs16 | *at the boundary* | 10 (#24, #25, #31, #32, #33, #40, #44, #46, #47, #48) | 5 (#22, #23, #26, #39, #45) | 4 (#36, #37, #38, #41) |
| @JakeBowen2005 | *at the boundary* | 4 (#36, #37, #38, #41) | 1 (#5) | 9 (#24, #25, #31, #32, #40, #44, #46, #47, #48) |
| @Avnijaglan19 | *at the boundary* | 0 | 1 (#29, through a PR authored by @JakeBowen2005) | 2 (#24, #25) |
| @1600isad | *at the boundary* | 0 | 0 | 3 (#24, #32, #33) |

On Oct 19, @Avnijaglan19 and @1600isad are below our charter's trigger,
"fewer than 2 merged pull requests in a sprint" (`docs/development-plan.md`
§1). Neither has authored a change in Sprint 1; @Avnijaglan19's three
commits are the merge-button merges of PRs #24, #32 and #33. Each has a specification task
that ends in a PR, with step-by-step instructions on the issue: #34 (Goal 2)
for @1600isad and #50 (Goal 3) for @Avnijaglan19. If they are still below 2
at the boundary, the charter's consequence applies in Sprint 2: pair with a
teammate on a story and own at least one story's PR. Pairing shows up when
commits carry `Co-authored-by:`.

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
- **Rotate reviewers.** @JakeBowen2005 reviewed 9 of this sprint's PRs,
  including all four merged on Oct 19. Next sprint, each PR goes to the
  member who has reviewed the fewest so far.
