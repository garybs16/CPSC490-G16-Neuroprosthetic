# CPSC 490 — Group 16 neuroprosthetic

**Project title:** BridgeWatch: Real-Time Detection of Cross-Chain Bridge Exploits
**Sponsor:** SNX-3 (SonarX)
**Section:** 05 (Thu)

## Team

| Name | GitHub | Role | Leader |
|---|---|---|---|
| Samuel, Gary Bennet | @garybs16 | 〈e.g. backend, docs lead〉 | ✅ |
| Bowen, Jake | @JakeBowen2005 | Detection rules and testing | |
| Jaglan, Avni | @Avnijaglan19 | front end, database | |
| Acuna, Isaac | @1600isad | 〈role〉 | |

**Contact person:** Gary Bennet Samuel — garysamuel@csu.fullerton.edu

## Links

- **Proposal:** [`proposal/proposal.md`](proposal/proposal.md)
- **Sprint Board (GitHub Project):** <https://github.com/users/garybs16/projects/2>
- **Issue board:** <https://github.com/garybs16/CPSC490-G16-Neuroprosthetic/issues>
- **Goals (epics):** [#11](https://github.com/garybs16/CPSC490-G16-Neuroprosthetic/issues/11) learn normal bridge activity ·
  [#12](https://github.com/garybs16/CPSC490-G16-Neuroprosthetic/issues/12) catch hacks early with few false alarms ·
  [#13](https://github.com/garybs16/CPSC490-G16-Neuroprosthetic/issues/13) operator dashboard
- **Specifications:** [`docs/specs/`](docs/specs/) · **Designs:** [`docs/design/`](docs/design/)
- **Prototype:** [`prototype/`](prototype/) — run instructions in its README
- **Sprint reviews:** [`docs/sprint-reviews/`](docs/sprint-reviews/)

## Project summary

Cross-chain bridges let people move cryptocurrency between blockchains, and
each bridge keeps everyone's deposits in one place, its vault, which makes
vaults a favourite target for hackers. Every blockchain transaction is
public, so a hack can be seen while it happens; the hard part is spotting it
quickly without raising a false alarm every time someone makes a large,
honest withdrawal. BridgeWatch learns how much money normally leaves each
bridge vault at each hour of the day, notices when withdrawals jump far
above normal, and sends an alert that explains the problem in one sentence.
We will test it by replaying real past hacks, such as the Orbit Chain hack,
and by measuring how often it raises false alarms on normal days. By the end
of CPSC 491 we will deliver a working alert dashboard for the major bridges
on SonarX data, tested on past hacks, with a measured false-alarm rate.

## How we work

- Sprints: four 2-week sprints (`Sprint 1`–`Sprint 4` milestones).
  Sprint boundary ritual every other Thursday.
- Every change lands by pull request; **the author never approves their own PR**.
- Every issue carries: assignee (owner), milestone (sprint), `priority:`,
  and a `sp:` story-point label.
- AI tools are used and disclosed — see the proposal's *AI Usage* section.
