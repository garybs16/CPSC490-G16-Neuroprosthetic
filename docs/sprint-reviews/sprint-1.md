# Sprint 1 review — Oct 8 – Oct 21

> One file per sprint, written at the sprint boundary (the setup guide's
> *The four sprints* section). This file, the board, and the merged PRs are
> what the sprint's **5%** (of the syllabus's 20% *Prototype & repository
> practice*) is assessed on — as they stand at the boundary.
> This is what makes **Transparency** and carry-over decisions visible at
> grading time — don't reconstruct it later.

**Written Oct 21, the last day of Sprint 1.** Numbers are from
`python scripts/sprint_report.py --sprint 1` on Oct 21.

## Progress this sprint — the substance

**Proposal moved:**

| Section | What changed | Where |
|---|---|---|
| Whole proposal, §0–§8 | The proposal submitted on Oct 4 is now `proposal/proposal.md`, in the course template's numbering, with every goal and objective in §2 linked to its issue | PR #24 (released to `main` in PR #33) |
| §0–§2 and §7 | Brought in line with Homework 5 as submitted on Oct 11: Related Work narrowed to three existing systems, references renumbered, two objectives worded as submitted, AI Usage updated for the prototype | PR #52 |
| Cover page | Cover-page table and clickable links to every filed issue | PR #37 |
| §2, §4, Table 7 | Typed issue references for the Word export; §4 tasks written as prose; Table 7 corrected to Group 16's sprint dates | PR #46 (released in PR #48) |
| Word export | `proposal/reference.docx` and `proposal/to-word.lua` from the course repository: one command turns `proposal.md` into the course Word template | PR #44 (released in PR #48) |
| `README.md` | Describes BridgeWatch, sponsor project SNX-3 and a summary | PR #25 (released in PR #32) |
| `docs/development-plan.md` | Team charter with quantified triggers, QA owner rotation, AI rules, risk register | PR #31 |
| `docs/sprint-reviews/sprint-1-start.md` | Sprint 1 starting story points | PR #40 (released in PR #48) |
| `docs/specs/goal-3-dashboard.md` | Goal 3 specification, our first: functional and non-functional requirements, acceptance criteria for Objectives 3.1 and 3.2, open questions | PR #53, merged Oct 21 |
| `docs/specs/goal-2-detection.md` | Not started; carried over (see below) | task #34 |

**Prototype moved:** at the start of Sprint 1, `prototype/` on `develop` held
only the course's starter. On Oct 9, BridgeWatch v0 was merged (Objective
2.0, story #5, PR #36, released to `main` in PR #38). Work on it began on a
branch before the sprint, with the first commit on Sep 28 and the datasets
and refactor on Oct 7. The detector learns an hour-of-day baseline per
bridge and raises alerts. It runs in four modes: live on Ethereum mainnet
through public nodes, a demo with synthetic bridges and an injectable
exploit, replay of five saved past hacks (Ronin, Harmony, Nomad, Multichain,
Orbit), and a false-alarm evaluation. Evidence: the CI job *Prototype build &
tests* is green on PR #36, and `python -m bridgewatch.replay` writes
`prototype/results/replay.json`.

Two further prototype changes were merged on Oct 21, each with a new test:
every alert message now names the bridge, the amount, the time window and
the comparison with normal (PR #54, completing Objective 2.1), and the
dashboard uses the objective's words, "mark as seen" (PR #55, under
Objective 3.1).

This is ahead of the course plan, which starts prototype work in Sprint 2.
It runs on public Ethereum nodes, not SonarX data. The first questions to
the SonarX mentor, including data access, have been sent (#28); SonarX
access is the first risk in proposal §4 Table 8.

## Velocity

| | Story points | Stories |
|---|---|---|
| Planned | 30 | 13 |
| Completed, work merged by Oct 21 | 27 | 11 |

*Planned* is the 14 points set at planning on Oct 8, plus task #45 (1) added
Oct 13, task #50 (2) added Oct 19, and two stories the team moved into
Sprint 1 on Oct 21 because they were finished inside this sprint: #5 (8),
done on Oct 9, and #16 (5), done by PR #54 on Oct 21. Task #56 sits under
story #20 and carries no points of its own.

`sprint_report.py` counts an issue as completed when it closes, and issues
close when the release reaches `main`. On Oct 21, before that release, it
reports 16 points closed. The release closes #16, #27, #30 and #50 (11
points), which makes 27 of 30 (90%). The 3 points left are #28 and #34
(see *Carried over*).

## Completed (merged PRs)

| Story | Owner | Points | PR |
|---|---|---|---|
| #5 Objective 2.0: first prototype | @JakeBowen2005 | 8 | #36 |
| #22 Put the submitted proposal into `proposal/proposal.md` and link the board | @garybs16 | 2 | #24, #37 |
| #23 Make the README describe BridgeWatch | @garybs16 | 1 | #25 |
| #26 Write the development plan | @garybs16 | 2 | #31 |
| #29 Set up the GitHub Projects board and link it from the README | @Avnijaglan19 | 1 | #41 (authored by @JakeBowen2005) |
| #39 Save the Sprint 1 starting story points | @garybs16 | 1 | #40 |
| #45 Typed issue references and sprint dates in the proposal | @garybs16 | 1 | #46 |
| #16 Objective 2.1: three alert rules that explain themselves (closes with the Oct 21 release) | @Avnijaglan19 | 5 | #54 |
| #27 Homework 5, Topic and Survey: on Canvas, and the proposal matches it (closes with the release) | @JakeBowen2005 | 3 | #52 |
| #50 Start the Goal 3 specification (closes with the release) | @Avnijaglan19 | 2 | #53 |
| #30 Write the Sprint 1 review (closes with the release) | @garybs16 | 1 | #47, #51, this PR |
| #56 "Mark as seen" wording on the dashboard, under story #20 (closes with the release) | @Avnijaglan19 | – | #55 |

Story #20 (Objective 3.1) stays open on purpose. PR #55 delivered one task
under it, and the Goal 3 specification sets stricter acceptance criteria for
3.1 than the issue's original two.

## Carried over — and why

| Story | Owner | Why not finished | Decision |
|---|---|---|---|
| #28 First questions to the SonarX mentor | @garybs16 | Sent; the mentor's reply has not arrived yet (the course guide says to allow 3–5 business days) | Moved to Sprint 2; answers are recorded on #28 with dates |
| #34 Start the Goal 2 specification | @1600isad | Not started; no PR by the boundary | Moved to Sprint 2, still owned by @1600isad, paired with a teammate under our charter |

## Loop health (docs/aidlc/loop-engineering.md §8)

| | This sprint |
|---|---|
| Iterations to green, average per PR | 1.4: 19 CI runs to first green across 14 feature PRs; release PRs from `develop` not counted |
| Harness rules added (rows in the harness log) | 0 |

All five red CI runs on feature PRs this sprint had one cause, and none was
the content of the change: the PR-discipline check found a template comment
(the HTML comment marker) in the PR body. That happened on PR #31 (once),
PR #44 (twice), PR #46 (once) and PR #51 (once, where the PR text quoted the
marker while describing this very problem). PRs #52–#55 were green on their
first run. Proposed for the harness log at this review: delete every template
comment from the PR body before opening the PR.

## Prototype increment

See *Prototype moved* above. At the end of Sprint 1, BridgeWatch v0 runs live,
in demo mode, as a replay of five past hacks, and as a false-alarm
evaluation. The Sprint 2 meeting (Oct 22) demo shows the proposal and the
board; the prototype demo follows at the Sprint 3 meeting (Nov 5).

## Feedback we received, and what we did about it

| Feedback (source) | What we changed | Issue / PR |
|---|---|---|
| Instructor, Sprint 1 meeting (Oct 8) | Not written down at the time, and the team could not recall specific points at the boundary, so nothing traceable changed because of it. From Sprint 2 on, we open an issue from `.github/ISSUE_TEMPLATE/advisor-meeting.md` during each instructor meeting and record the feedback there | |
| Instructor, PR #8: the sprint report should flag writing tasks without story points | Merged. Every standalone writing task carries its own `sp:` and a `Sprint 1` milestone | PR #8 |
| Instructor, PR #10: the harness G10 should let a writing task stand without a parent | Merged | PR #10 |
| Instructor, #42 and PR #43: one-command Word export; PR #43 was closed and teams asked to pull course files themselves | Pulled the latest course files, including `proposal/reference.docx` and `proposal/to-word.lua` | #42 / PR #44 |
| Instructor's repository status page (`docs/repo-readiness.md` in the course repository), Group 16 card: convert the bare issue links to typed references | Done; the Oct 20 card shows 22 of 22 links typed | #45 / PR #46 |
| Same card: the Sprint Board is not readable | Made the board public on Oct 19; the Oct 20 card shows it readable with 16 of 16 open issues | |
| Same card: assign the three epics | Assigned on Oct 13: Goal 1 to @garybs16, Goal 2 to @1600isad, Goal 3 to @Avnijaglan19 | #11, #12, #13 |
| Same card: a branch held work not in `develop` | Checked that every commit on `feature/5-bridgewatch-prototype` was already in `develop`, then deleted it (Oct 13) | |
| Same card: 6 direct commits to `main`/`develop`; turn on branch protection | Protection on both branches now also applies to administrators (Oct 13), so no one can push without a reviewed PR. The 6 earlier commits remain in the history | |
| Same card: review and merge the open pull requests | Merged on Oct 19 and 20 | PRs #44, #46, #47, #48, #51 |
| Same card (Oct 20): cite #50 in proposal §4 | Cited by PR #53, which adds the Goal 3 specification itself | #50 / PR #53 |
| Same card (Oct 20): close #34 and #30 | #30 closes with the Oct 21 release; #34 was not started and carries over (see above) | #30, #34 |
| Same card (Oct 20): start Objective 1.1 data collection against the SonarX stream | Planned for Sprint 2; it depends on SonarX access, which we asked the mentor about | #14, #28 |
| Our own check against the course setup guide (Oct 13): §2 and §4 cited issues untyped, §4 listed issues in a table, Table 7 showed another group's sprint dates | Fixed | #45 / PR #46 |
| Our own check (Oct 21): after PR #52 reworded Objectives 2.0 and 3.1 as submitted in Homework 5, the titles of #5 and #20 no longer matched proposal §2 | Retitled both issues to the §2 wording on Oct 21 | #5, #20 |
| Our own check (Oct 21): the Goal 3 specification's word-for-word quote of Objective 3.1 still carried the wording PR #52 removed | Aligned the quote with §2 in this PR | #50 |

## Contribution snapshot

Oct 8 – Oct 21. Merged PRs include release PRs (#32, #33, #38, #48). Reviews
count the PRs a member reviewed (approved or commented).

| Member | Meetings attended | Merged PRs | Issues closed | Reviews given |
|---|---|---|---|---|
| @garybs16 | All | 11 (#24, #25, #31, #32, #33, #40, #44, #46, #47, #48, #51) | 5 (#22, #23, #26, #39, #45); #30 with the release | 8 (#36, #37, #38, #41, #52, #53, #54, #55) |
| @JakeBowen2005 | All | 5 (#36, #37, #38, #41, #52) | 1 (#5); #27 with the release | 10 (#24, #25, #31, #32, #40, #44, #46, #47, #48, #51) |
| @Avnijaglan19 | All | 3 (#53, #54, #55) | 1 (#29, through a PR authored by @JakeBowen2005); #16, #50 and #56 with the release | 3 (#24, #25, #51) |
| @1600isad | All | 0 | 0 | 3 (#24, #32, #33) |

Everyone attended every meeting, but the work is uneven, and two members
were below our charter's trigger, "fewer than 2 merged pull requests in a
sprint" (`docs/development-plan.md` §1), for most of the sprint.
@Avnijaglan19 merged three PRs on the last day: our first specification
(Goal 3) and two prototype changes, each with a test, which completed
Objective 2.1. That puts @Avnijaglan19 above the trigger. @1600isad has no PR
this sprint, so the charter's consequence applies in Sprint 2: @1600isad
pairs with a teammate on a story and owns at least one story's PR. The team
names the partner at the Oct 22 meeting. Pairing shows up when commits carry
`Co-authored-by:`.

## What we change next sprint

- **Re-approve after every push.** On PR #25, @JakeBowen2005 approved and
  then pushed a commit to the branch, which dismissed the approval. The PR
  was merged with comments from @Avnijaglan19 but no current approval. From
  now on, nothing merges without a current approval from someone who did not
  commit to the branch.
- **Keep PRs reviewable.** PR #36 was 153 files and about 735,000 added
  lines, about 711,000 of them saved datasets (`research/bridge-hacks/` and
  `prototype/bridgewatch/data/`). That is far over our agreement of under 10
  files and 500 lines. Next time, datasets go in a PR of their own, separate
  from the code.
- **Rotate reviewers.** @JakeBowen2005 reviewed 10 of this sprint's PRs. Next
  sprint, each PR goes to the member who has reviewed the fewest so far.
- **Open PRs early.** Three PRs arrived on the boundary day, which leaves no
  time for review if something needs changing. Next sprint, open each PR as
  soon as there is something to review, as a draft if it is not finished.
- **Write instructor feedback down during the meeting.** The Oct 8 feedback
  was lost. At every instructor meeting, one person opens an issue from the
  advisor-meeting template and records what was said before the meeting ends.
