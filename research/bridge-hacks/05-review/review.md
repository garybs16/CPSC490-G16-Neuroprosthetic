> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Independent review of `research/bridge-hacks/`

Reviewed 2026-10-07 by an independent agent that wrote none of sections 01–04. Nothing under `prototype/` was changed, and no git commands that change state were run.

## Verdict: ready to push, with fixes

The data checks out against the chain, and the experiments reproduce byte-for-byte. The two corrections the analyst flagged have been applied. One MUST item is left: a Hyperbridge contradiction between sections. It is wording only, and the push does not depend on it.

## What I checked (evidence)

**Data (03).**
- `validate.py` passes on **all 20 files**: schema, rows, duplicates, decimals, start and end balance reconciliation, and first theft. Commands were run with `-B`, so no `__pycache__` was written.
- I also wrote my own check, separate from `validate.py`, that reads the receipt directly. It covered 28 transfers: **2 per hack file and 1 per normal file**, chosen at random with seed 490. Each matched the receipt log at its `log_index` on token, amount, direction and block.
- The same check covered all 10 `first_theft_tx`. Each sits in the stated block with status 1 and a vault release; Qubit correctly releases nothing.
- Vault identities match the cited sources:
  - KelpDAO: adapter `0x85d456b2…` and tx `0x1ae232da…` match Blockaid.
  - Ronin 2024: `0x64192819…` and both exploit txs match Three Sigma.
  - Poly 2021: LockProxy `0x250e7698…` matches rekt.
  - HECO: CertiK names no vault. CertiK does name the operator `0x3d655889…`, and on-chain that operator sends the first-theft tx to `0xa929022c…`.
- Sizes: the largest file is the Across `.json.gz` at 5.8 MB (under 8 MB), and the folder is 18 MB in total.
- Secrets: a grep for `key=|apikey|infura.io/v3/|alchemy.com/v2/|token=` finds only `sorted(key=…)` in Python and a URL slug containing "private-key". `check_repo.py` G5 is clean.

**Catalog (01).**
- `hacks.csv` and `hacks.json` are field-identical: 102 rows, 0 mismatches.
- The summary statistics recompute from the CSV: 54 confirmed, $3,626M, median $5.0M, top 5 at 68%, every root-cause and design subtotal, and every year except 2024, which was fixed.
- I sampled 13 incidents from 2021 to 2026 against their cited sources for date, loss and cause: pNetwork, Anyswap, Qubit, Harmony, BNB Hub, Multichain, HECO, Force, Gravity, AFX, Liquid, KelpDAO and Ronin 2024. All are consistent. AFX and Gravity root causes are single-source and already marked `*`.
- Axelar-Secret and Secret Network: the possible duplicate is flagged, and both rows are unconfirmed, so neither affects the statistics.
- Defensive content:
  - No exploit steps, calldata or attacker tooling appear in 01, 02 or 04.
  - No attacker or theft-recipient addresses appear in 01, 02 or 04. I checked 326 addresses taken from every case block and theft row.
  - Attacker addresses do appear in `03-onchain-data/sources.md`, in `fetch_more.py` and in each hack JSON's `case.attacker_addresses`, as dataset provenance (see NICE below).

**Defenses (02).** I checked 9 claims against their URLs; all hold, except one that I removed (see edits):
- KelpDAO pause 46 min, about $100M blocked (The Block, Blockaid). On-chain, the pause tx is at 18:21:59 against a theft at 17:35:35.
- Ronin 2024 per-transaction cap and the pause at 10:15 (The Block).
- The "$72M saved" estimate (SolidityScan, which gives no method).
- Hyperbridge detection at 03:55:23 and follow-ons until 05:07 (Hypernative, labelled self-reported).
- Forta: 450 alerts, 100% precision, 70% and 40% recall.
- Axelar: net-flow limit, 6-hour epoch, `FlowLimitExceeded`.
- BlockSec: about 1% false positives.

`tools.md` labels vendor numbers as self-reported in its header and with "Claims" on each row.

**Analysis (04).**
- `run_all.sh` ran from scratch copies of `prototype/` and the research folder. Every output in `out/`, `features.csv` and `normal-stats.csv` is **byte-identical**; only absolute paths in two logs differ.
- I re-ran after my catalog edits, and the outputs are still identical.
- The headline numbers are confirmed in `combos.csv`, `loo.json` and `coverage.json`:

  | Metric | Current | REC |
  |---|---|---|
  | Pages per bridge-week | 3.032 | 0.105 |
  | NAB | −83.4 | 92.6 |
  | Hacks detected | 14/14 | 14/14 |

  - Leave-one-out: 14/14 detected, 13/14 at the floor.
  - Stolen value gone before any 6-confirmation alert was possible: 66.4%, value-weighted.
  - `outflow_spike` is 189 of 282 rule-level alarms, which is the 67% quoted.
- Objective 2.2: I recomputed the floors myself from the prototype JSONs. Harmony's first theft is 54.1% of tracked theft and Ronin 2022's is 95.3%, so at most 3 of 5 cases can be alerted before half the funds leave. The claim holds, **on tracked tokens**.
- Look-ahead and overfitting:
  - The detector is streaming and uses no look-ahead.
  - REC was chosen on all 14 cases, and `experiments.md` discloses this ("How much to trust this", §6 LOO and time split).
  - The time split honestly reports a miss on Ronin 2024.
- The `patterns.md` and `implementation-recommendations.md` figures I spot-checked match `features.csv` and `pattern-counts.csv`, and every recommendation row cites its evidence.

**Hygiene.**
- `python3 .github/scripts/check_repo.py` is **HARNESS GREEN**: links resolve and there are no secrets.
- My own check of relative links in `research/**/*.md` finds 0 broken.
- There is no `__pycache__`, `.db` or scratch log in the folder. `.DS_Store` files are present but gitignored.

## Edits made

| File | Before → after | Why |
|---|---|---|
| `01-hack-catalog/hacks.csv`, `hacks.json` (row `2023-07-poly-network`) | date `2023-07-02` → `2023-07-01 18:47:47`; vault_drained `no (unbacked mint)` → `partial`; vault, first-theft block and tx `unknown` → `0x250e7698…`, 17601076, `0x3a6e5d7e…f993`; added `escrow_drain`; signature notes the $5.77M unlock | Verified on-chain. The LockProxy released USDT, USDC and DAI. Times in the catalog are UTC, and the release was July 2 only in Beijing time |
| `01-hack-catalog/catalog.md` | Poly 2023 row `no (mint)/A` → `partial/V`; V 36/~2,901 → 37/~2,906; A 8/~670 → 7/~666; vault drained → `yes 21 · partial 19 · no 14`; §6 "36 of 54" → 37 and "next 8" → 7; replayable rows 29 → 30 (×2); 2024 `4 / 27` → `4 / 26` | Follows from the Poly 2023 fix; 2024 is $26.47M |
| `04-analysis/implementation-recommendations.md` §7.1 | "29 confirmed Ethereum rows" → 30 | Consistency with the catalog |
| `01-hack-catalog/cases/2023-12-orbit-bridge.md` | Added the five dust test releases (18:30–20:40 UTC, with tx hashes). Signature "all to the same recipient" → four different fresh recipients | Taken from `orbit-2023.json`; two dust txs re-checked on-chain. The old text was wrong |
| `04-analysis/ideas-and-open-questions.md` §9 items 1–2 | Marked resolved | The flags were acted on |
| `02-defenses/tools.md` (BlockSec row) | Removed "A backtest claims under 0.0001% [B1]" | The figure is not in B1 or B3 |
| `03-onchain-data/README.md` (Hyperbridge row) | "~245 ETH … the ETH is native" → a correction: it left as **WETH** (ERC-20) in tx `0xeff151ef…`, 03:02:11 | On-chain receipt: a 245.93 WETH Transfer out of the gateway |
| `03-onchain-data/README.md`, `sources.md`, `01-hack-catalog/verified-ethereum-cases.md` | Added the `> Epic: #12 · Stories: #16, #17, #18` header | Course rule; these were the only research docs without one |
| `04-analysis/experiments/out/features.log`, `normal_stats.log` | Removed the absolute `/Users/jakebowen/...` prefix | Local path leak |

## Remaining issues

**MUST**
1. **Hyperbridge timing contradiction.** The catalog's own first theft is the WETH release at **03:02:11**, 53 min before the 03:55:23 mint that Hypernative flagged. Three places still treat detection as about 0 minutes: catalog §5 ("detection took about 0 minutes"), `02-defenses/case-studies-stopped-or-limited.md` B2 ("detected in the same minute") and the `tools.md` Hypernative row. Reword them as "flagged the main mint within the same minute; an earlier 245 WETH release at 03:02 was not reported as detected." Also, `pattern-assignment.csv` puts Hyperbridge in P5 "escrow untouched", while the catalog says `partial`. One label should change (a team call).

**SHOULD**
2. In `implementation-recommendations.md` §0, say that REC's 0.105 and NAB 93 are **in-sample**. The validation is the LOO and time-split results, and those tested the grid-selection procedure, not REC itself.
3. Objective 2.2 rests on tracked tokens only. Harmony lost about 13,100 native ETH from a separate manager, so with ETH included its floor may differ. Add the caveat next to the claim.
4. Headers in `02-defenses/` read "Epic: not yet assigned", while 01, 03 and 04 cite #12/#16–18. A human should confirm the issue numbers.
5. Hyperbridge (WETH) is a feasible 11th hack dataset (see the 03 README).

**NICE**
6. Attacker addresses in `03-onchain-data/sources.md`, in `fetch_more.py` and in each hack JSON's `case.attacker_addresses` are public provenance and fine. Do not copy them into docs.
7. The Multichain `date_utc` is the $2 test (16:21), not the first theft (18:10). Consider a note.
8. The CertiK HECO total ($113.3M) includes the HTX hot wallets; the catalog uses $86.6M. A footnote would help.

## Reproducibility

```sh
cp -r prototype /tmp/bw-proto
BW_PROTOTYPE=/tmp/bw-proto PY=<venv python> sh research/bridge-hacks/04-analysis/experiments/run_all.sh   # ~3 min
python -B research/bridge-hacks/03-onchain-data/validate.py                                              # ALL PASS
```

Every output reproduced exactly. Validation needs the public RPCs, which rate-limit occasionally and retry.

## How to read this folder

Start with `04-analysis/implementation-recommendations.md` §0: the answer in eight points, each linked to evidence. `04-analysis/experiments.md` gives the method, the numbers and the overfitting checks. `patterns.md` and `false-alarm-patterns.md` explain *why* the rules separate thefts from normal traffic. `01-hack-catalog/catalog.md` covers the 54 confirmed incidents, with case pages for the major ones. `02-defenses/` covers what other monitors and protocols do, with vendor claims marked self-reported. `03-onchain-data/` holds the chain-verified datasets that every number is computed from.
