> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Ideas, open questions and risks

Research date: 2026-10-07. These are things the analysis turned up that fall outside the threshold work in `implementation-recommendations.md`. Most are proposals for the team to accept or drop. The questions in §6 are drafted for a human to send.

## 1. Response: an alert is only worth what someone does with it

The record shows detection is rarely the bottleneck:

| Incident | Detected | Contained |
|---|---|---|
| Hyperbridge | same minute | > 70 min |
| Kelp | — | paused at 46 min |
| Ronin 2024 | — | paused at 38 min |
| Ronin 2022 | 6 days | — |

Sources: `02-defenses/case-studies-stopped-or-limited.md`; `02-defenses/protocol-defenses.md` §3. In the replays, the value still savable after the first page was 28–83% of tracked theft in the multi-transaction drains, which the attackers took over the next **2.5–9 minutes per asset** (`patterns.md` §1). So:

- **Per-bridge response card.** For each monitored bridge, keep a card that says:
  - who holds the pause key (multisig address, its signers' public contact, the guardian set);
  - what can be paused (the contract, a route, the whole chain);
  - known per-transaction or daily caps;
  - which issuers can freeze the assets it holds: Circle (USDC), Tether (USDT), and token teams with blacklists (K9 Finance froze KNINE in Shibarium).

  Show the card inside every page. This is cheap and probably the highest-value non-detection feature.
- **Pause hooks, never pause actions.** BridgeWatch should not hold keys or send transactions. Safer integrations, in increasing order of effort:
  - (a) a webhook the bridge team points at its own automation;
  - (b) a pre-filled Safe (multisig) *proposal* the signers still have to approve;
  - (c) a signed, verifiable alert payload (tx hashes, block, rule, evidence), so the receiving side can check the alert was not forged.

  An auto-pause triggered by a false alarm is itself an outage, and an attacker who can trigger false alarms could use it as a denial-of-service.
- **Downstream routing.** Lending markets froze late: Aave froze rsETH 77 min after Kelp. Issuers froze ~$65M after Multichain. An opt-in feed for those parties (asset, amount, addresses) is a different audience from the bridge team.
- **Repeat-attack watch.** After an incident, keep the vault in heightened mode until a human closes it (recommendations S18). Verus was drained again 15 days after its funds were redeposited. Aztec was hit 3 times in 4 days.
- **Rehearse.** Run a monthly "game day": replay Orbit at real speed into a staging channel and time how long the on-call takes to acknowledge and find the pause contact. This doubles as Objective 3.2's user evaluation.

## 2. Alert message design

The proposal promises "one plain sentence". Make the sentence carry the decision, not the rule name.

| Part | Example | Why |
|---|---|---|
| Headline | "Orbit Bridge vault released $10.0M DAI (14% of the vault) to an unfamiliar address." | The number a human needs, in vault terms (`patterns.md` §1) |
| Why it is unusual | "Largest release in 30 days was 0.9%. This address had only received a $1 test release, 45 min ago." | Context makes alerts trusted (`02-defenses/academic.md` D1, "Explainable, Contextual") |
| What agreed | "Size + unfamiliar recipient + 14% net outflow in 1 h." | Shows it is not one noisy rule |
| What is normal now | "Normal for 21:00 UTC on this vault: ~$0.1M per 10 min." | Uses the hour-of-day baseline as context (Objective 1.2) |
| What to do | "Pause: Orbit ops multisig 0x… (3-of-5). DAI/USDC/USDT: issuers can freeze. Export addresses ⟶" | Cuts the human part of latency |
| Confidence and data state | "Data healthy (2 providers agree, lag 1 block)." or "DEGRADED DATA: provider lag 80 blocks." | Prevents acting on a data error |

Wording rules:
- **Say "unfamiliar address", not "attacker".** Most fresh-address pages in normal data were whales (`false-alarm-patterns.md` §7).
- Never put a person's name or off-chain identity in an alert.
- Use dollar amounts and percentages, not z-scores. Keep z-scores in the details panel.
- Escalation messages say what changed: "now 3 assets, 61% of the vault".

## 3. Operator experience and alert fatigue
- **Reason codes on every page:** true positive, benign trigger, detector error, data error, retracted. One click each, with a free-text note. This is how the false-alarm budget gets measured honestly (`false-alarm-patterns.md` §8).
- **Warnings go to a digest, not a feed.** At 0.98 warnings per bridge-week under REC, a 10-bridge deployment sees about 10 a week. Show them as a daily summary and a per-bridge timeline, and page nobody.
- **A visible "quiet" state.** Each bridge shows "normal", "watching" (an open warning), "incident" or "data degraded". A quiet dashboard should look intentionally quiet, not broken.
- **Snooze with expiry, never mute.** Snoozing a known migration needs a reason and an end time; the snooze is listed on the dashboard; S1 (≥ 50% of the vault) still pages.
- **Acknowledge time is a metric.** The prototype already has acknowledgement; add time-to-acknowledge and time-to-close per incident. These numbers are the honest answer to "is it fast?"
- **Keep a page budget per on-call person.** The relevant number for fatigue is pages per *person* per week across all bridges. At 0.1 per bridge-week, 20 bridges give about 2 a week. That is tolerable; 3.03 per bridge-week would be 60.

## 4. Data quality and health checks that gate alerts

Recommendations §3.3 gives the rule; this is the checklist. Most of it already exists in the prototype's `/api/health` (lag, stale prices).

| Check | Threshold (suggested) | Action |
|---|---|---|
| Ingest lag behind chain head | > 50 blocks, or > 10 min | pages labelled DEGRADED; ops alert |
| Missing block range | any gap | hold detection over the gap; backfill; send catch-up alerts labelled LATE |
| Two providers disagree on logs or balances for a vault | any mismatch over 1 block | ops alert; label pages; investigate (Kelp-style poisoning) |
| Reconciliation: start balance + flows ≠ on-chain `balanceOf` | > 0.1% or > $1K, every N blocks | ops alert; it means a missed transfer or a non-standard token |
| Price feed stale or jumped | stale > 10 min, or a move > 20% in one poll for a stablecoin | freeze the last good price; label estimated-price tokens; never page on value moved by a price change |
| Token anomalies (LEASH in Shibarium: Transfer sums ≠ balance) | reconciliation failure on one token | exclude that token from share math; show it |
| Reorg past the confirmation depth | block hash changed | retract affected alerts as "retracted" |
| Decoder error rate (when decoded events arrive) | > 0 per hour | ops alert |
| Synthetic canary | a labelled fake release injected into staging daily | if no page within 2 min, the pipeline is broken |

## 5. Privacy and ethics
- **Pseudonymous is not anonymous.** Addresses can be linked to people. Show addresses and on-chain facts only; never join them with off-chain identity, never speculate about who is behind one, and keep "unfamiliar address" neutral (§2).
- **Fresh-recipient pages hit legitimate users most.** Of the 8 residual pages, the large single releases (USDT0 $45M, Poly $10.4M, Harmony $7M) were almost certainly ordinary users or market makers. Pages and exports should be private to the bridge team, not public posts.
- **Don't tip attackers in real time.** A public live feed of "vault X is being drained" invites copycats; Nomad shows how fast a crowd forms. If anything is ever made public, delay it until the operator has acted.
- **Responsible disclosure.** If analysis finds a weakness (for example a 1-of-1 verifier config, or a deprecated vault still holding funds), report it privately to the team or through SEAL 911 before discussing it anywhere. Never test it.
- **No interaction with monitored contracts.** BridgeWatch only reads. That keeps the student project clear of any action that could move funds.
- **Retention.** Keep counterparty history long enough for "fresh" to work (≥ 30 days; the counterparty table in recommendations §8 is designed not to be pruned). Do not keep more than the detection needs. Document both in the design doc.
- **AI-use disclosure.** These documents and scripts were drafted with an AI assistant. The proposal's AI-usage section should say so (`CLAUDE.md`).

## 6. Questions for the SonarX mentor (draft; a human sends them)
1. **Scope.** Which bridges and vaults should BridgeWatch cover first, and on which chains? Are liquidity pools (Stargate, Across) in scope for v1, given they need a different profile?
2. **Native assets.** Can SonarX provide native-ETH movements per address (internal transfers from traces, or per-block balance diffs)? In 3 of 14 replayed hacks, ETH left 4.7–34 min before any token.
3. **Decoded events.** Are bridge admin events (upgrade, owner, signer-set, DVN config) and bridge message events (deposit and release with message ID or nonce) available decoded, or only raw logs? For which bridges?
4. **Both sides.** Can we get the source-chain side of the same bridges (deposits and burns) to build release↔deposit matching in CPSC 491?
5. **Latency and metadata.** What is SonarX's end-to-end lag from a block to our consumer? Does the stream expose head, gaps and reorgs?
6. **Prices.** Which price source does SonarX use, at what granularity? Is there a confidence flag for thin markets?
7. **Labels.** Are address labels (CEX deposit, bridge operator, mixer, known exploiter) available?
8. **What counts as a false alarm?** Any page, or pages plus warnings? Does an auto-retracted provisional alert count? Is ≤ 1 per bridge per week measured per bridge or pooled?
9. **Objective 2.2.** Would SonarX accept "every theft detected within 60 s of the first theft's 6th confirmation, with zero excess loss versus the physical floor" in place of "before half the funds leave in 4 of 5"? The latter is unreachable on the current replay set (`experiments.md` §2).
10. **Response path.** Who would receive pages in a real deployment: SonarX, the bridge teams, or both? Is a pause-hook integration in scope?
11. **History.** How much history can we backfill per vault (≥ 30 days helps the fresh-recipient signal)?
12. **Evaluation weeks.** Can SonarX hold out some recent weeks of data that the team does not see until thresholds are frozen?

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Thresholds overfit the 14 replay cases | M | H | Pattern-motivated rules, plateau defaults (`experiments.md` §6), frozen thresholds before held-out SonarX weeks, a growing replay suite |
| SonarX lacks native-asset or decoded admin data | M | M | Fall back to per-block `eth_getBalance` diffs and raw `Upgraded`/`OwnershipTransferred` logs over RPC (both work today) |
| Pool theft not recognised (pays a past depositor) | L–M | H | State the limit; prioritise S15 matching for pools in CPSC 491 |
| Live false alarms from data errors swamp the budget | H (literature) | H | Data-health gate (§4), reason codes, two providers |
| Monitor input poisoning (Kelp-style) | L | H | Two independent providers; reconciliation against `balanceOf` |
| Allowlist abuse (an insider adds an attacker address) | L | H | Recipient-only allowlist, expiry, audit log, shown in every alert; S1 still pages |
| Pages ignored (Ronin 2022: 6 days) | M | H | Low page rate, clear text, acknowledgement metrics, game days |
| Over-claiming in the proposal ("prevents hacks") | M | M | Use the floor framing: detection is at the physical limit; prevention needs in-protocol limits |
| Scope creep (mempool, ML, every chain) | M | M | Keep them as CPSC 491 stretch items behind the measured core |

## 8. More ideas worth considering
- **A static bridge-risk panel.** For each bridge, show signer threshold, verifier count (DVN 1-of-1?), challenge period, caps and upgrade delay, and flag weak settings. Kelp ran a 1-of-1 DVN and Hyperbridge a zero challenge period before their incidents (`02-defenses/protocol-defenses.md` §2). The panel changes rarely and needs no alerting.
- **Cross-bridge correlation.** Raise severity when the same recipient or funding address appears in another bridge's open incident. Harmony, Poly 2021 and Force were hit on several chains at once.
- **Shadow mode before cut-over.** Run REC beside the current rules on live data for 2 weeks and compare pages one by one before switching the pager.
- **Counterfactual replay in the dashboard.** "If this alert had paged the pauser at 21:09, what was still in the vault?" That makes the value of response time concrete for the user study (Objective 3.2).
- **ML as a scored feature, later.** Isolation forest or graph models (`02-defenses/academic.md` A4/A5) can feed the combiner as one more "family", never page alone. Evaluate them with the same harness.
- **Use the floor as a product metric.** Report "detected at the floor in N/N cases" rather than a raw share lost. It separates what the monitor controls from what only the protocol can prevent.

## 9. Open questions from this analysis
1. **Poly Network 2023 is labelled a mint ("no (unbacked mint)") in the catalog**, but `poly-2023.json` shows the Ethereum LockProxy released $5.77M of USDT, USDC and DAI. Should the catalog row be reclassified as a vault drain plus mint? (`experiments/coverage.py` treats it as an Ethereum vault drain.) *Resolved 2026-10-07 (`../05-review/review.md`): the catalog row is now `partial`, detectability V.*
2. **Orbit's dust test releases** ($10, $10, $4, $1 and $514 to the four theft addresses, 18:30–20:40 UTC) are not in `cases/2023-12-orbit-bridge.md`. Worth adding, with tx hashes from `orbit-2023.json`. *Resolved 2026-10-07: added to the case page's timeline.*
3. **Were the residual pages really benign?** Harmony's $7.0M USDC to a fresh address on 2022-06-17 (6 days before the hack) and Poly's $10.4M WETH on 2021-08-04 are assumed legitimate because nothing followed. A human could check them against public reports.
4. **Vault value includes native ETH in reality.** Share-of-vault thresholds were computed on tracked tokens only. For ETH-heavy vaults (Ronin, Wormhole, Orbit) the true denominator is larger, so true shares are lower. Re-check S1–S5 once native balances are ingested.
5. **Pool thefts.** None are in the replay set. Find one with a pool-style escrow on Ethereum (THORChain 2021 router? Allbridge on BSC?) to measure the pool profile's miss rate.
6. **Config-change base rate.** We estimate "a handful per bridge per year" from the case pages. Measure it: pull a year of `Upgraded`, `OwnershipTransferred` and signer-set events for the 3 live rollup gateways and 5 replay bridges.
7. **Combination window.** 10 min and 30 min performed the same here (0.091 vs 0.105 pages per bridge-week). Is there a slow-sweep incident (gaps over 10 min) that would decide it? Multichain's longest gap was 22 min.
