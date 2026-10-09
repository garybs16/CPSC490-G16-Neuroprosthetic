# Prototype: BridgeWatch (SNX-3)

A working slice of **SNX-3 · Cross-Chain Bridge Activity and Exploit
Detection** ([docs/sponsored-projects.md](../docs/sponsored-projects.md)).
It learns each bridge's normal flow, raises an alert the moment releases or
escrow movements deviate, and scores itself on the two things the sponsor
summary calls hard: a *baseline* of normal, and a *false-alarm rate* a person
would tolerate.

Four ways to run the same detector:

| Mode | Data |
|---|---|
| Live (default) | Real bridge contracts on Ethereum mainnet, read from public nodes |
| Demo (`--demo`) | Synthetic bridges with injectable exploits; nothing describes a real bridge |
| Replay | Saved on-chain data from 5 past bridge hacks (Ronin, Harmony, Nomad, Multichain, Orbit) |
| Evaluation | False alarms per bridge per week on 30-day believed-normal windows (real data), and a synthetic scorecard |

## Architecture

```
Source  ->  Detector  ->  Store  ->  Alerts  ->  Notifier (own thread, webhook)
                                            ->  API snapshot -> dashboard
```

| Piece | File | What it does |
|---|---|---|
| Source | `bridgewatch/source.py` | Yields `Batch`es of `Transfer`s. `RpcSource` reads confirmed blocks from a JSON-RPC node (live); `FileSource` reads a saved dataset (replay, evaluation, `load_data`). A SonarX source would be a third class with the same `batches(cursor)` method. `to_flow_event()` is the one place a `Transfer` becomes the detector's `FlowEvent`. |
| Detector | `bridgewatch/detector.py` | Hour-of-day median/MAD baseline over the past 7 days and the rules below. Pure Python, no I/O. |
| Store | `bridgewatch/store.py` | SQLite: transfers (key: chain + tx hash + log index; exact token units; USD priced at ingest), alerts, cursor. Schema version in `PRAGMA user_version`; older databases are migrated on open. |
| Live loop | `bridgewatch/live.py` | Backfill (committed chunk by chunk), then every 15 s: the detector sees each batch **before** it is committed with the cursor; if anything fails in between, the detector is rebuilt from the store. |
| Notifier | `bridgewatch/notify.py` | One webhook message per incident, on a background thread, with exponential backoff, `Retry-After`, an attempt cap, and LATE labels for alerts found while catching up. |
| API | `bridgewatch/app.py`, [API.md](API.md) | FastAPI. `/api/state` is a snapshot rebuilt after each poll; evaluation and replay results are JSON files written by the CLIs. |
| Config | `bridgewatch/config.py`, `bridgewatch/bridges.json` | Every `BRIDGEWATCH_*` variable is read in one place; one `DetectorConfig` is built from it. `bridges.json` lists chains, tokens and bridges, with optional per-bridge overrides. |

## How to run

```bash
cd prototype
pip install -r requirements.txt -r requirements-dev.txt   # once
python run_bridgewatch.py          # live: runs the tests, starts http://127.0.0.1:8001
python run_bridgewatch.py --demo   # demo: synthetic bridges, "Simulate exploit" button

python -m bridgewatch.replay               # replay every saved hack case -> results/replay.json
python -m bridgewatch.replay bridgewatch/data/orbit-2023.json   # one case
python -m bridgewatch.evaluate --real      # false alarms per bridge per week on real data -> results/evaluation-real.json
python -m bridgewatch.evaluate             # synthetic scorecard (~15 s) -> results/evaluation.json
python -m bridgewatch.load_data            # import every dataset into bridgewatch-datasets.db (idempotent; never the live DB)
python scripts/fetch_datasets.py --list    # the datasets, and how to re-download them from public RPCs
```

The dashboard's replay and evaluation panels show the saved `results/*.json`
files; run the commands above to create or refresh them (the Docker image runs
them at build time).

## How to test

```bash
cd prototype
python -m pytest -q        # 48 tests, all offline
```

CI runs these on every pull request (job **Prototype build & tests**).

## Live mode: real bridges on Ethereum mainnet

BridgeWatch watches the official Ethereum contracts of three rollup bridges
(addresses and sources in `bridgewatch/bridges.json`, each checked against the
project's own docs and on-chain on 2026-09-28) for USDT, USDC, DAI and WBTC:

| Bridge | Contract | Source |
|---|---|---|
| OP Mainnet | L1StandardBridgeProxy `0x99C9…4bE1` | Optimism superchain registry |
| Base | L1StandardBridge `0x3154…2C35` | docs.base.org |
| Arbitrum One | L1 ERC20 Gateway `0xa3A7…0EeC` | docs.arbitrum.io |

How it runs: on first start it reads 7 days of transfers from public Ethereum
nodes, committing every 2,000 blocks so an interrupted backfill resumes, then
polls every 15 seconds, counting a block only once it has 6 confirmations.
A restart resumes from the cursor and rebuilds the detector from stored
transfers (with the USD values they had when ingested), so nothing is
double-counted and no alert is re-sent. Measured on 2026-10-07: first start
live in about 65 s (96 RPC calls, 1 rerouted), 1,009 transfers in the 7-day
window, 0 alerts, cursor 6 blocks behind the head.

**Detection latency** (proposal: evaluated within 1 minute after 6
confirmations) is `detected_at − confirmed_at` of an alert, where
`confirmed_at` = block time + 6 × 12 s. Live mode records it on every alert
and exports the latest as `bridgewatch_last_detection_latency_seconds`.

### Operating it

All settings are environment variables, read in `bridgewatch/config.py`:

| Setting | Default | Notes |
|---|---|---|
| `BRIDGEWATCH_MODE` | `live` | `demo` for synthetic bridges |
| `BRIDGEWATCH_DB` | `bridgewatch.db` | SQLite file; keep it on a persistent volume |
| `BRIDGEWATCH_RPC_URLS` | 3 public endpoints | Comma-separated, tried in order. A private endpoint with an API key goes here (never in the repo); logs show only scheme://host |
| `BRIDGEWATCH_RPC_PAUSE` | 0.3 | Seconds between RPC calls (free tiers rate-limit) |
| `BRIDGEWATCH_POLL_SECONDS` | 15 | |
| `BRIDGEWATCH_CONFIRMATIONS` | from `bridges.json` (6) | More = safer against reorgs, slower alerts |
| `BRIDGEWATCH_HISTORY_DAYS` | 7 | Baseline window **and** first-run backfill (one setting) |
| `BRIDGEWATCH_Z_THRESHOLD` / `_MIN_SPREAD_USD` | 6 / 100000 | Detector thresholds (per bridge: `overrides` in `bridges.json`) |
| `BRIDGEWATCH_WEBHOOK_URL` / `_FORMAT` | off / `slack` | Secret. At-least-once, one message per incident |
| `BRIDGEWATCH_API_TOKEN` | off | Needed to acknowledge alerts. In live mode acknowledging is **disabled** until it is set |
| `BRIDGEWATCH_RESULTS_DIR` | `prototype/results` | Where the CLIs save JSON for the dashboard |

- `GET /api/health`: 200 when ingesting normally, 503 when degraded (no
  successful poll for 90 s or 3 polls, or more than 50 blocks behind). It also
  flags stale prices (`prices_stale`) and transfers stored without a price.
- `GET /metrics`: Prometheus text.
- Prices: stablecoins at $1; WBTC from Chainlink BTC/USD, refreshed every 10
  minutes. If the feed fails, the last good price is kept (also across
  restarts) and flagged stale; ingest never stops for it, and nothing is ever
  priced at $0.
- Notifications: alerts on one bridge within an hour of each other are one
  incident and one message (a second message only if it escalates to
  critical). Failed deliveries back off 5 s, 10 s, 20 s … up to 10 minutes and
  honor `Retry-After`; after 8 attempts the incident is marked `failed` and
  counted in `/api/health`. Alerts found in the very first backfill are history
  and never sent; alerts found while catching up after downtime are sent,
  labelled **LATE**.
- Retention: live transfers older than the baseline window + 1 day are
  pruned hourly; alerts and imported datasets are kept.
- Container: `docker build -f Dockerfile.bridgewatch -t bridgewatch .` (not
  built here; Docker isn't installed on the machine this was written on).
- Run exactly one instance per database: the live monitor is the only writer.

## Real hack replay (5 cases, real on-chain data)

Each case is about 14 days of the vault's ordinary traffic (the baseline) and
then the hack, fed transfer by transfer on a simulated clock: a transfer is
seen at the first 15-second poll after its 6th confirmation, which is when
live mode would have seen it. Results of `python -m bridgewatch.replay` on
2026-10-07 (default settings):

| Case | Thefts tracked | First alert | Latency after 1st theft confirmed | Stolen before / after the alert | False alarms in the 14-day baseline |
|---|---|---|---|---|---|
| Ronin, Mar 2022 | 2, $539.6M | escrow drain, on the 1st theft | 9 s | $514.1M / $25.5M | 1 |
| Harmony, Jun 2022 | 7, $76.2M | escrow drain, on the 1st theft | 2 s | $41.2M / $35.0M | 9 |
| Nomad, Aug 2022 | 435, $168.8M | outflow spike, on the 1st theft | 2 s | $16.1M / $152.7M | 19 |
| Multichain, Jul 2023 | 7, $111.3M | escrow drain, on the 1st theft | 13 s | $27.7M / $83.6M | 0 |
| Orbit, Dec 2023 | 4, $59.8M | escrow drain, on the 1st theft | 4 s | $10.0M / $49.8M | 0 |

"Stolen before" counts thefts whose block time is before the alert was raised
(so they could not have been acted on).

**Against the proposal's Objective 2.2 target** (alert before half of the stolen
funds had left, in at least 4 of the 5 replays): met for Nomad (9.5% gone),
Orbit (16.7%) and Multichain (24.9%); missed for Harmony (54%) and Ronin (95%).
That is **3 of 5, so the target is not met yet.** Both misses are hacks where
one or two huge first withdrawals took most of the money, which an
after-the-fact outflow alarm cannot prevent. The baseline false alarms on
Nomad and Harmony also need work. Ronin's first theft was most of the
money, so detection can't help much there; only prevention before signing can.
Data, sources and caveats per case are in each dataset file's `case` block
(vault, first-theft transaction, references); see `scripts/fetch_datasets.py`,
which re-downloads every dataset except `orbit-2023.json` (fetched earlier by
the original prototype; adding it to the script is a to-do).
Native ETH is not visible in token logs and is not tracked (WETH is, where it
was used). Five cases are evidence, not a benchmark.

## False alarms on real normal data (Objective 2.3)

`python -m bridgewatch.evaluate --real` runs the detector over 30-day windows
with no known incident and counts every alert after the 3-day warm-up as a
false alarm. Target: at most 1 per bridge per week. Results on 2026-10-07:

| Dataset | Weeks counted | False alarms | Per week |
|---|---|---|---|
| Arbitrum One gateway, 30 days | 3.86 | 0 | 0.00 |
| Base bridge, 30 days | 3.86 | 0 | 0.00 |
| OP Mainnet bridge, 30 days | 3.86 | 0 | 0.00 |
| Orbit vault, Oct 2023 | 3.86 | 1 | 0.26 |
| Multichain MPC address, Mar 2023 | 3.86 | 13 | **3.37** |

The three bridges BridgeWatch monitors meet the target in these windows; the
Multichain address (an MPC wallet with irregular large flows) does not, and
the hack baselines above show the same pattern for Harmony and Nomad. That is
the open problem to work on next (per-bridge overrides exist for it), not a
solved one.

## How it detects

| Rule | Fires when | Needs a baseline |
|---|---|---|
| Outflow spike | Last-10-minute outflow is 6 spreads above normal for that hour, and at least 0.5% of escrow. The spread is the median absolute deviation, never below $100K (`min_spread_usd`), so a release in an hour where usually nothing leaves isn't a 50-sigma event | yes |
| Release burst | Last-10-minute release count is 6 spreads above normal, and at least 12 releases | yes |
| Escrow drain | Net outflow over the last hour exceeds 5% of escrow | no |
| Large withdrawal | One release of at least 2% of escrow and at least $1M (critical from 5%) | no |
| Unbacked release | A release has no matching deposit (only when the data can tell; off for token-transfer data) | no |

The baseline is the median of the same hour of day over the past 7 days, so
the daily cycle and one-off whales don't read as anomalies. One alert per
bridge and rule per hour; repeats update the live alert instead of adding
more. Per-bridge settings go in `bridges.json`, e.g.
`"overrides": {"min_spread_usd": 250000, "large_withdrawal_share": 0.03}`.

## Synthetic scorecard (seeds 1-3, 2026-10-07)

| Exploit | Caught | Median time to first alert | Median share stolen before alert |
|---|---|---|---|
| Mass drain | 12 / 12 | 8.3 min | 0.7% |
| Key compromise | 12 / 12 | 0 min | 43.8% |
| Slow bleed | 7 / 12 | 123.9 min | 14.4% |

False alarms on 44 bridge-days of clean synthetic traffic: 0.045 per bridge
per day (0.32 before the $100K minimum spread). Synthetic numbers describe the
detector on generated traffic only.

## Not covered yet

Native ETH (held in the bridges' portal contracts, not visible in token
logs); chains other than Ethereum (the config has a `chains` block, but live
mode runs one chain per process); reorgs deeper than the confirmation count
(block hashes are stored, rollback is not implemented); a transfer between two
monitored vaults is stored once (the key is chain + tx + log index), so it
counts for one of them only; per-transfer historical prices for backfill (the
price at ingest is used); multiple replicas; user accounts beyond a single API
token; SonarX sources (they would implement `Source`).

## Layout

| Path | What it is |
|---|---|
| `bridgewatch/models.py` | `Bridge`, `FlowEvent`, `Alert`, `Incident` |
| `bridgewatch/source.py` | `Transfer`, `Batch`, `Source`; `RpcSource`, `FileSource` |
| `bridgewatch/detector.py` | Baseline and the rules |
| `bridgewatch/store.py` | SQLite schema, migrations, transfers, alerts, cursor |
| `bridgewatch/live.py` | Live monitor: backfill, confirmed-block polling, restart recovery, prices |
| `bridgewatch/notify.py` | Webhook delivery (Slack or JSON) on a worker thread |
| `bridgewatch/config.py`, `bridgewatch/bridges.json` | Settings from the environment; monitored chains, tokens, bridges |
| `bridgewatch/onchain.py` | Ethereum JSON-RPC client (retries, endpoint fallback), Chainlink prices |
| `bridgewatch/app.py`, `API.md` | FastAPI server and its endpoint reference |
| `bridgewatch/replay.py`, `bridgewatch/evaluate.py`, `bridgewatch/load_data.py` | Command-line tools |
| `bridgewatch/synthetic.py` | Synthetic traffic and injectable exploits (demo mode, synthetic scorecard) |
| `bridgewatch/data/` | Saved datasets: hack cases, and `normal/` 30-day windows |
| `scripts/fetch_datasets.py` | Re-downloads the datasets from public RPCs |
| `results/` | JSON written by replay / evaluate, read by the dashboard |
| `web/bridgewatch.html` | Alerting dashboard |
| `tests/` | 48 offline tests: detector, replay, live mode against a fake node, store migration, notifier, CLIs |
| `run_bridgewatch.py` | One-click launcher |
