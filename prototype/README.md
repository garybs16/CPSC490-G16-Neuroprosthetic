# Prototype: BridgeWatch (SNX-3)

A working slice of **SNX-3 · Cross-Chain Bridge Activity and Exploit
Detection** ([docs/sponsored-projects.md](../docs/sponsored-projects.md)).
It learns each bridge's normal flow, raises an alert the moment releases or
escrow movements deviate, and scores itself on the two things the sponsor
summary calls hard: a *baseline* of normal, and a *false-alarm rate* a person
would tolerate.

Three ways to run the same detector:

| Mode | Data |
|---|---|
| Live (default) | Real bridge contracts on Ethereum mainnet, read from public nodes |
| Demo (`--demo`) | Synthetic bridges with injectable exploits; nothing describes a real bridge |
| Replay | Real saved on-chain data from the Orbit Chain bridge hack (31 Dec 2023) |

Real data from SonarX would plug in by producing the same `FlowEvent` records.

## How to run

```bash
cd prototype
python run_bridgewatch.py          # live: installs, tests, starts http://127.0.0.1:8001
python run_bridgewatch.py --demo   # demo: synthetic bridges, "Simulate exploit" button
python -m bridgewatch.replay       # the Orbit hack replay, printed (offline)
python -m bridgewatch.evaluate     # the synthetic scorecard (about a minute and a half)
```

In demo mode the dashboard plays traffic on a simulated clock (one minute per
second); pick a bridge and press **Simulate exploit** to watch one get caught.

## How to test

```bash
cd prototype
pip install -r requirements.txt pytest   # once
python -m pytest -q                      # 29 tests, all offline
```

CI runs these on every pull request (job **Prototype build & tests**).
`login.py` and `tests/test_login.py` are the course's v0 example, kept for now.

## Live mode: real bridges on Ethereum mainnet

`python run_bridgewatch.py` starts in live mode. BridgeWatch watches the
official Ethereum contracts of three rollup bridges (addresses and sources in
`bridgewatch/bridges.json`, each checked against the project's own docs and
on-chain on 2026-09-28) for USDT, USDC, DAI and WBTC:

| Bridge | Contract | Source |
|---|---|---|
| OP Mainnet | L1StandardBridgeProxy `0x99C9…4bE1` | Optimism superchain registry |
| Base | L1StandardBridge `0x3154…2C35` | docs.base.org |
| Arbitrum One | L1 ERC20 Gateway `0xa3A7…0EeC` | docs.arbitrum.io |

How it runs: on first start it reads 7 days of transfers from public
Ethereum nodes (about 40 requests, under a minute) to learn each bridge's
baseline, then polls every 15 seconds, counting a block only once it is 6
blocks deep. Transfers, alerts and the cursor live in SQLite; a restart
resumes from the cursor and rebuilds the detector from stored transfers, so
nothing is double-counted and no alert is re-sent. Alerts go to a webhook.

Measured on 2026-09-28: first start live in 38 s (40 RPC calls, 1 refused and
rerouted); restart live again in 10 s with 0 duplicate transfers; 1,101
transfers in the 7-day window and 0 alerts on them; the cursor held 6 blocks
behind the chain head. About $1.0B of escrow tracked across the three bridges.

### Operating it

| Setting | Default | Notes |
|---|---|---|
| `BRIDGEWATCH_MODE` | `live` | `demo` for synthetic bridges (`run_bridgewatch.py --demo`) |
| `BRIDGEWATCH_DB` | `bridgewatch.db` | SQLite file; keep it on a persistent volume |
| `BRIDGEWATCH_RPC_URLS` | 3 public endpoints | Comma-separated, tried in order; a private endpoint with an API key goes here (never in the repo) |
| `BRIDGEWATCH_POLL_SECONDS` / `_CONFIRMATIONS` | 15 / 6 | More confirmations = safer against reorgs, slower alerts |
| `BRIDGEWATCH_HISTORY_DAYS` | 7 | Baseline window and first-run backfill |
| `BRIDGEWATCH_WEBHOOK_URL` / `_FORMAT` | off / `slack` | Secret. At-least-once delivery, retried each poll until 2xx |
| `BRIDGEWATCH_API_TOKEN` | off | When set, acknowledging an alert needs `Authorization: Bearer <token>` |

- `GET /api/health`: 200 when ingesting normally, 503 when degraded (no
  successful poll for 90 s or 3 polls, or more than 50 blocks behind).
- `GET /metrics`: Prometheus text (ingest lag, RPC calls/errors, transfers,
  alerts by rule, escrow, notifications).
- Container: `docker build -f Dockerfile.bridgewatch -t bridgewatch .` (not
  built here; Docker isn't installed on the machine this was written on).
- Run exactly one instance per database: the live monitor is the only writer.

### Not covered yet

Native ETH (held in the bridges' portal contracts, not visible in token
logs); chains other than Ethereum; bridges beyond these three; reorgs deeper
than the confirmation count; per-transfer historical prices (backfilled
transfers use today's WBTC price); multiple replicas; user accounts beyond a
single API token. These are the next increments, and SonarX data would replace
the public-RPC ingest.

## Real hack replay: Orbit Chain bridge (real on-chain data)

```bash
python -m bridgewatch.replay           # replays the saved data, offline
python -m bridgewatch.replay --fetch   # re-downloads it from public Ethereum RPCs (a few minutes)
```

The detector is fed 14 days of the Orbit Chain bridge's Ethereum vault
(`0x1bf68a9d…b489a`) and then the hack of 31 Dec 2023, transfer by transfer,
as if live. Data: USDT, USDC, DAI and WBTC Transfer logs in and out of the
vault, blocks 18,808,000-18,912,443, read from public JSON-RPC nodes and saved
in `bridgewatch/data/orbit-2023.json`; WBTC priced with Chainlink's BTC/USD
feed at the hack (verified on-chain: `description()` = "BTC / USD").

| | Result |
|---|---|
| False alarms in the 14-day baseline | 0 (250 ordinary transfers) |
| First alert | critical, 21:07:59 UTC, on the first theft ($10M DAI) |
| Stolen after the alert | $49.8M of $59.8M tracked, 3-17.6 minutes later (WBTC, USDC, USDT) |

Caveats: the vault was identified from the on-chain record (four releases of
$10M DAI, 230.88 WBTC, $30M USDT and $10M USDC to fresh addresses within 18
minutes), which matches public reports of the Orbit hack; confirm it against
a published incident report before citing. Native ETH isn't in token logs, so
the ETH taken is not tracked. One real case is evidence, not a benchmark.

## How it detects

| Rule | Fires when | Needs a baseline |
|---|---|---|
| Outflow spike | Last-10-minute outflow is 6 spreads (median absolute deviations) above normal for that hour, and at least 0.5% of escrow | yes |
| Release burst | Last-10-minute release count is 6 spreads above normal, and at least 12 releases | yes |
| Escrow drain | Net outflow over the last hour exceeds 5% of escrow | no |
| Unbacked release | A release has no matching deposit (only when the data can tell) | no |

The baseline is the median of the same hour of day over the past 7 days, so
the daily cycle and one-off whales don't read as anomalies. One alert per
bridge and rule per hour; repeats update the live alert instead of adding
more.

## Synthetic scorecard (seeds 1-3, 2026-09-28)

| Exploit | Caught | Median time to first alert | Median share stolen before alert |
|---|---|---|---|
| Mass drain | 12 / 12 | 8.2 min | 0.7% |
| Key compromise | 12 / 12 | 0 min | 43.8% |
| Slow bleed | 8 / 12 | 139.9 min | 16.9% |

False alarms on 44 bridge-days of clean traffic: 0.32 per bridge per day
(13 outflow spikes from legitimate whale transfers, 1 release burst).
Lowering the threshold to 4 spreads doubles false alarms (0.61); raising it
to 8 barely reduces them (0.30).

What this shows: flow monitoring catches fast drains while little is lost,
but a key compromise has already moved most of its money in its first
transaction (only prevention before signing helps), and a slow bleed of
normal-sized releases is the weak spot.

## Layout

| Path | What it is |
|---|---|
| `bridgewatch/models.py` | `Bridge`, `FlowEvent`, `Alert`, `Incident` |
| `bridgewatch/synthetic.py` | Synthetic traffic and injectable exploits |
| `bridgewatch/detector.py` | Baseline and the four rules |
| `bridgewatch/evaluate.py` | Detection rate, time to alert, loss before alert, false alarms, threshold sweep |
| `bridgewatch/onchain.py` | Ethereum JSON-RPC client (retries, endpoint fallback), vault token flows, Chainlink prices |
| `bridgewatch/bridges.json` | Monitored bridges and tokens, with the source for every address |
| `bridgewatch/live.py` | Live monitor: backfill, confirmed-block polling, restart recovery |
| `bridgewatch/store.py` | SQLite: transfers, alerts, cursor |
| `bridgewatch/notify.py` | Webhook delivery (Slack or JSON) |
| `Dockerfile.bridgewatch` | Container for the live service |
| `bridgewatch/replay.py`, `bridgewatch/data/orbit-2023.json` | Real hack replay and its saved on-chain data |
| `bridgewatch/app.py` | FastAPI server: live and demo services, API, health, metrics |
| `web/bridgewatch.html` | Alerting dashboard |
| `tests/test_bridgewatch.py`, `tests/test_bridgewatch_live.py` | 25 tests: detector, replay, and live mode against a fake node, temp database and mocked webhook (all offline) |
| `run_bridgewatch.py` | One-click launcher |
