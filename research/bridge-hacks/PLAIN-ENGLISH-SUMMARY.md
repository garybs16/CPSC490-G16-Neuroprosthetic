> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# BridgeWatch research, in plain English

**Date:** October 7, 2026 · **Prepared by:** Jake Bowen (with AI research help)

*A short version of everything in this folder, for people who are new to crypto.*

---

## 1. What we're building

**The problem.** Blockchains like Ethereum can't talk to each other. A **bridge**
is a service that lets people move money from one blockchain to another. To do
that, the bridge keeps everyone's money in one big digital safe, called the
**vault**. Some vaults hold hundreds of millions of dollars, so hackers love
them. Bridge hacks have cost billions.

**The good news.** Every transaction on a blockchain is public. When a vault is
being robbed, anyone watching can see the money leave in real time.

**Our project, BridgeWatch,** is an alarm system for these vaults. It learns
what a normal day looks like for each vault, watches for money leaving, and
sends an alert, like a text or Slack message, when something looks like a
robbery.

**The two hard parts** (our sponsor SonarX named both):

1. **Be fast:** raise the alarm as soon as a robbery starts.
2. **Don't cry wolf:** big, honest withdrawals happen every day. If the alarm
   goes off too often, people stop paying attention. Our goal is **no more than
   one false alarm per bridge per week.**

---

## 2. Words you'll see

| Word | What it means |
|---|---|
| **Vault** | The bridge's safe, where everyone's deposited money sits |
| **Release / withdrawal / outflow** | Money leaving the vault |
| **Drain** | A hacker emptying the vault |
| **Alert** | Anything BridgeWatch notices and shows on the dashboard |
| **Page** | The serious kind of alert, the one that texts a person to act now, like a phone ringing at 3 AM |
| **False alarm** | An alert or page when nothing bad is happening |
| **Baseline / normal** | What usual activity looks like for a vault at that time of day |
| **Signal** | One clue that something might be wrong, for example "a huge amount just left" |
| **Fresh recipient** | A wallet that has never received money from this vault before |
| **Liquidity pool** | A different kind of bridge where lots of money moves in and out all day as normal business, so it "looks busy" even on a quiet day |
| **Confirmations** | Waiting a few blocks (about 72 seconds) so we're sure a transaction is real and final before alerting |
| **Native ETH** | Ethereum's own coin. Our prototype currently only sees *tokens* (USDT, USDC, DAI, WBTC), not ETH itself. |
| **Replay** | Feeding real data from a past hack through our system, as if it were happening live, to test whether we'd catch it |

---

## 3. What we researched

We sent out several research "agents" (AI assistants) to:

- **Study past hacks.** We collected **102 bridge hacks** from 2021 to 2026, 54
  of them confirmed by solid sources: what happened, how much was stolen, and
  what it looked like from the outside.
- **Download real data.** We pulled the actual transaction history for **15
  real hacks** and **29 "normal" time periods** straight from the Ethereum
  blockchain. That includes the stressful but honest weeks, like the FTX
  collapse, when lots of people pulled money out at once.
- **Study other security tools** like Forta, Hypernative and CertiK, plus
  research papers, to see how professionals catch these hacks.
- **Test ideas** by replaying all of that data through our system and through
  improved versions of it.
- **Double-check everything** with a separate review agent that verified the
  facts against the sources and the blockchain.

---

## 4. What we found

### Finding 1: Our alarm is already as fast as it can be

When we replayed the real hacks, BridgeWatch caught **every single one (14 out
of 14) on the very first stolen transaction**, within seconds.

The catch: in many hacks, **the first transaction takes most of the money.**
Example: in the Ronin hack, 95% was gone in the first move. Across all the
hacks, **66% of the stolen money was already gone before *any* alarm could
possibly go off.** An alarm can't stop the first punch. It can only help stop
the follow-up punches.

### Finding 2: Our real problem is false alarms

Right now our system "pages" (texts someone) about **3 times per bridge per
week** for nothing. That's 3× over our goal. On the busy liquidity-pool bridges
it's about **13 times a week**, which is way too many.

The biggest troublemaker is our "unusual for this hour" rule. It causes **about
two thirds of the false alarms**, because busy bridges often have a big but
honest hour.

### Finding 3: Hacks share a few clear patterns

- **The thief usually takes a huge chunk at once.** The first theft was
  typically **about half of the whole vault**, and thieves usually ended up
  taking **86% or more**. Honest users almost never withdraw anything close to
  that.
- **The money goes to a brand-new wallet.** In **every hack** where we knew who
  received the money, it went to a wallet that had never used the bridge
  before.
- **Hacks happen at any hour,** including nights and weekends. We should never
  assume "it's 3 AM, so it's probably fine."
- **Some hacks are fast "sweeps":** the thief grabs one coin type, then
  another, a few minutes apart. Here a fast alarm really helps: it could save
  **28–83%** of the money if someone hits pause quickly.
- **Copycat hacks** (Nomad): once one hacker found the hole, hundreds of other
  people copied them. That looks like a sudden crowd of new wallets
  withdrawing.

### Finding 4: Some hacks we currently can't see at all

- **ETH itself.** In three hacks, the thief took ETH **5 to 34 minutes before**
  any of the tokens we watch. We'd have caught those much earlier if we tracked
  ETH too.
- **"Warning signs" before the hack.** In **12 hacks (about $1.1 billion)**,
  the bridge's settings were changed first: a software update, or new people
  given the keys. This is **the only clue that ever showed up *before* any
  money was lost.** We don't watch for it yet.
- **Fake money hacks.** Some hackers don't empty the vault. They trick the
  bridge into printing fake tokens on the other blockchain. To catch those, you
  have to check that *every withdrawal on one side has a matching deposit on
  the other side*. We don't do that yet.
- **Hacks that drain users' wallets instead of the vault** (Socket, LI.FI).
  Watching the vault will never catch these. That's fine, but we should say so
  honestly.

### Finding 5: Reacting matters as much as detecting

In real hacks, the time between "an alarm went off" and "someone actually
paused the bridge" ranged from **38 minutes to 6 days**. One company's tool
spotted a hack within seconds, but the attacker kept going for **70 more
minutes** because nobody pressed pause. Our alerts need to reach someone who
can act, and tell them clearly what to do.

---

## 5. The plan: how to make BridgeWatch the best it can be

### Step 1: Only page a human when we're really sure

Instead of paging on any single "unusual" thing, use **two simple rules**:

**Rule A: page right away if one withdrawal is huge,** either of:
- **half the vault or more** (and at least $250,000), or
- **10% of the vault or more** (and at least $1 million).

**Rule B: otherwise, page only when two clues agree within 30 minutes.** The
clues are:
1. A big withdrawal (1% of the vault or more, and at least $250K) going to a
   **brand-new wallet**.
2. **10% or more of the vault** leaving within one hour.
3. **5% or more of the vault** going to **one wallet** within one hour.
4. **10 or more brand-new wallets** withdrawing within 10 minutes (the copycat
   pattern).
5. An hour that's **wildly** busier than normal. This is the old rule, now
   much stricter and only allowed to *help* confirm, never to page on its own.

**Everything else just shows on the dashboard** as a warning, so nobody's phone
buzzes.

**Busy liquidity-pool bridges get their own, stricter settings.** Money going
back to people who deposited before doesn't count as suspicious, and a page
needs 20% leaving in an hour plus a second clue.

### What this would change

| | Today | With the new rules |
|---|---|---|
| Hacks caught at the first theft | 14 of 14 | **14 of 14** (one, Nomad, is 15 seconds slower) |
| False pages per bridge per week | about 3 | **about 0.1**, roughly one every 10 weeks |
| False pages on busy pool bridges | about 13 a week | **about 0.4 a week** |
| Time periods that broke our "1 per week" goal | 12 of 29 | **1 of 29** |

So it's **just as fast, with about 29 times fewer false alarms.** Of today's 282
false alarms, 223 disappear completely, 51 become quiet dashboard warnings, and
only 8 would still page someone.

**Honest caveat:** we tuned these rules on the same data we tested them on, so
real-world results will probably be a bit worse. We also only have 14 hacks to
learn from. We checked this by hiding one hack at a time and re-tuning on the
other 13: it still caught every hidden hack. That's a good sign, but not a
guarantee.

### Step 2: Fill the blind spots, in order of payoff

1. **Watch the bridge's settings.** Alert when someone updates the bridge's
   software or changes who holds the keys. This is our only early-warning
   signal, and it covered about $1.1B of past hacks.
2. **Track ETH, not just tokens.** That would have caught three hacks 5–34
   minutes earlier. In one case the share already stolen when we alerted drops
   from 73% to 24%.
3. **Check that deposits and withdrawals match** between the two blockchains.
   That catches the "fake money" hacks.
4. **A "data health" check.** If our data feed is late or broken, mark alerts
   as "unsure" instead of staying silent or raising false alarms.

Most of these need richer data, which is exactly what our sponsor **SonarX**
provides. That's a great reason to talk to our mentor.

### Step 3: Make alerts easy to act on

Every page should say, in one plain sentence, what happened, how much money,
and what to do next (who can pause the bridge, which coins can be frozen). The
dashboard should also track how long it took someone to respond.

### Step 4: Decide what to do about Objective 2.2

Our proposal says "alert before half the stolen money leaves, in 4 out of 5
replayed hacks." The research shows **this is impossible for any alarm** on our
current test hacks, because in Harmony and Ronin the very first transaction
took more than half. We should ask our professor and mentor to change it to
something achievable, for example: "catch every hack within 60 seconds of the
first theft."

---

## 6. Suggested next steps for the team

| When | What |
|---|---|
| **Sprint 2** | Add the "two clues must agree" paging rule and the "brand-new wallet" clue to the prototype, plus a scorecard that counts false pages per week |
| **Sprint 3** | Separate settings for pool-style bridges; the "data health" check; start watching bridge setting changes |
| **Sprint 4 / spring (CPSC 491)** | Track ETH; check deposits against withdrawals across chains using SonarX data; build the response checklist into the dashboard |
| **Now** | Ask our SonarX mentor the questions in `04-analysis/ideas-and-open-questions.md`, and discuss changing Objective 2.2 |

---

*Where to read more: the full design is in
`04-analysis/implementation-recommendations.md`, what hacks look like is in
`04-analysis/patterns.md`, and the list of all 102 hacks is in
`01-hack-catalog/catalog.md`. This research was gathered and written with AI
help (Claude). Read and verify it before relying on it, and mention it in the
proposal's AI Usage section.*
