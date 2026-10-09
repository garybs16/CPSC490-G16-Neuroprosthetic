> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# When legitimate activity looks like an attack: false-alarm patterns by bridge design

Research date: 2026-10-07.

**Data.** 29 windows, 76.5 bridge-weeks:
- the 15 normal and stress windows;
- the pre-hack baselines of the 14 hack files.

**Method.** Every false alarm raised by the *current* prototype detector (default `DetectorConfig`, counted after the 3-day warm-up) was mapped back to the release that triggered it (`experiments/out/fa-examples.csv`, 282 rule-level alerts). The same release was then judged by the recommended policy, REC (`implementation-recommendations.md` §2). Per-window statistics are in `normal-stats.csv`; the largest legitimate releases per window, with context, are in `experiments/out/largest-legit-outflows.csv`.

**Bottom line:**
- **Today:** 282 rule-level false alarms, 232 page incidents, **3.03 pages per bridge-week**.
- **Under REC:** 8 pages, **0.105 per bridge-week**. 51 of the old alarms become dashboard warnings; 223 disappear.
- **Hacks:** every hack is still caught at the same moment (`experiments.md` §4).
- **What is left:** the 8 remaining pages are all "a very large release to a fresh address" or pool net-flow swings. On transfer data alone, these cannot be told apart from a theft (§6).

## 1. Current false alarms by design and rule

Rule-level alerts, the prototype's own counting (`normal-stats.csv`):

| Design (windows) | Bridge-weeks | outflow_spike | withdrawal_burst | escrow_drain | large_withdrawal | Per week | Under REC (pages / week) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Lock-box, normal (Polygon PoS, Wormhole, Orbit Oct 2023, Ronin gateway) | 15.4 | 2 | 1 | 0 | 0 | 0.19 | **0** |
| Rollup gateways (Arbitrum, Base, OP) | 11.6 | 0 | 0 | 0 | 0 | 0 | **0** |
| Lock-box, stress (Wormhole FTX Nov 2022, Polygon USDC-depeg Mar 2023) | 7.7 | 34 | 9 | 1 | 4 | 6.2 | **0.13** |
| Lock-box, pre-hack baselines (12 files) | 18.8 | 28 | 12 | 6 | 7 | 2.8 | **0.16** |
| OFT adapter (USDT0, Kelp pre-hack month) | 7.7 | 28 | 1 | 0 | 1 | 3.9 | **0.13** |
| OFT adapter, pre-hack (Kelp) | 1.6 | 3 | 0 | 0 | 0 | 1.9 | **0** |
| Liquidity pool (Stargate, Across 7 d, Celer) | 8.3 | 84 | 4 | 38 | 6 | 15.9 | **0.36** |
| MPC custody (Multichain Mar 2023, pre-hack) | 5.4 | 10 | 0 | 1 | 2 | 2.4 | **0** |

Which rule causes the noise, and why:
- **`outflow_spike` causes 67% of all false alarms (189 of 282).**
  - Its spread floor is $100K and its baseline is the median of the same hour over 7 days.
  - On a vault that holds $3.2B (USDT0) or $284M (Kelp), a $3–80M release is routine. But it is 30–800 "spreads" above an hour whose median is near zero.
  - Its threshold is not scaled to the vault.
- **`escrow_drain` causes 16% (46).** Almost all of these are on vaults under $2M (Across $0.47M, Celer $1.6M, XBridge ~$14K pre-hack), where a 5% hourly net outflow is $25K–$80K.
- **`withdrawal_burst` (27) fires on busy bridges in busy minutes.** Nomad's pre-hack window had up to 22 releases in 10 min; Wormhole during FTX, 23.
- **`large_withdrawal` (20) fires on whale releases of 2–7.5% of a vault**, almost all to recipients the vault has seen before, or that deposited the same day.

## 2. Lock-box escrows (canonical, validator/multisig bridges)

**What normal looks like:**
- 0.1–230 releases per day. The median release ranges from $52 (Ronin gateway) to $87K (Polygon PoS).
- Largest single release ≤ 1% of the vault in normal months:
  - Polygon PoS 0.45% of $1.7B;
  - Wormhole 0.27% of $344M;
  - Orbit (Oct 2023) 0.95%;
  - Arbitrum, Base and OP ≤ 1.56%.
- Largest 24 h drawdown ≤ 2%.
- Busy pre-hack periods ran higher: Poly 2021 up to 3.7% in one release and 8% net in an hour; Harmony 7.5%; Nomad 5.4% and 11% net in an hour.

**Patterns that resemble an attack:**

| Pattern | Real example | Current rule | Why it is not an attack | Under REC |
|---|---|---|---|---|
| Whale withdrawal to a fresh address | Harmony, 2022-06-17 05:20:30. 6,999,898 USDC (7.5% of vault) to fresh `0xdfe4f07d1f36…`, tx `0x1a8ebd3284e5305707c85126574ce7dd047c4cfb6b349b72e93fb6f964f40495` | escrow_drain + outflow_spike + large_withdrawal | A single release, then no second asset and no further drain. Six days before the real hack | **page** (`fresh` + `conc`). One of the 8 remaining |
| Treasury or market-maker move split into several assets | Nomad, 2022-07-25 05:42–05:51. WBTC $4.58M (tx `0x9a88eb77a877ee723b467ef91c80eeb6703af7a345f29b24ed7eec17834a500f`), FRAX $5.98M (`0x4316051e9b30faff34e141380708d52b2124cfc406fe70ebff65f93e70ca20a5`), USDC $9.49M (`0xe8b990f8948b340d7622bd03d2b4f4224dd64d870521ccf5132d5d77c9e710c0`), all to `0x3c0fa0643322…`. The dataset notes flag it as a known false-alarm candidate | 3 rules | Shaped exactly like a P1 sweep (3 assets, one address, 9 min), but stopped at ~12% of the vault | **page**. Unavoidable on transfer data; needs an operator allowlist or source-chain matching |
| Busy-hour bursts | Nomad pre-hack: 12 `withdrawal_burst` alerts; up to 22 releases in 10 min. Polygon PoS, 2026-10-07 09:05:23: 7 releases in 10 min, tx `0xf5230092d198e702de006c04235ca33d85701e32c741f3c95207fdc3bd00cbec` | withdrawal_burst | Many users, small amounts, recipients with history | none |
| Same-recipient series of moderate releases | Wormhole, 2026-09-11 16:58–17:09. Four WBTC releases of ~$0.84–0.92M to `0xa28f81ad2ba9…` (tx `0x956c68fd1773ff8a13aa502260162736230b3dee28aa2e1506055a89b912e47c`) | outflow_spike | 0.27% of the vault each; the recipient was not fresh after the first | none |
| Large release from a busy vault | Poly 2021, 2021-08-04 02:05:21. $10.4M WETH (3.7%) to fresh `0xbe89dd35…`, tx `0xdd1212d04b0a3b69c358801d5be7ec5194a54d1d78b6decec11240e6ef2881ec`; 23 min later $9.96M WBTC, tx `0x991742216a269475ceac2737439e5042706222b515eb713adf59ad6d3d271027` | 28 alerts in 14 days | Normal for that era's LockProxy | **page** (`fresh` + `spike`). One of the 8 remaining |
| Tiny vault | XBridge pre-hack (~$14K): 2024-04-13 a $3,146 STC release was 78% of the vault, tx `0x5b5d2fe7ebe7acc2c95a8d580ad31fd54279326cd1e180fd7d48f35ed771c81c` | escrow_drain | Dollar size is trivial | none ($250K floor) |
| Stress exits (FTX, Nov 2022) | Wormhole Portal: 165 releases a day, net hourly outflow up to 8.7%, 24 h drawdown 11.5%. USDC $4.2M (3.45%) to fresh `0xff733d0d…` (tx `0xff733d0dc16999e9b55f823a9ab7ac321ea2357ddb8a56065262a56ba58003f6`); $4.0M then $2.0M to `0x584cd92b…` (tx `0x42790faa108cded479536b835f48a565db761c1804ae575f5332aed63558adb4`) | 47 alerts in the month (12.2 per week) | Many independent exits, each a small share; no single address takes most of the vault | 1 page (5 warnings across both stress windows) |
| Depeg stress (USDC, Mar 2023) | Polygon PoS: 10,000,000 USDT to a past depositor, 2023-03-11 19:22:23, tx `0x906e10aa7d0224388218646f816c4291c6bb672cb15e292a3d63bbcd53b236eb` | outflow_spike | 0.55% of a $1.9B vault; a known counterparty | warning |

**How to suppress without missing hacks:**
- **Scale every threshold to the vault, not the hour.** Page alone only on ≥ 10% of the vault and ≥ $1M, or ≥ 50% and ≥ $250K. No legitimate non-pool release in 76.5 bridge-weeks hit either. 12 of 14 first thefts did.
- **Require a second, independent signal for anything smaller**: fresh recipient, ≥ 10% net in an hour, ≥ 5% to one address, or an extreme seasonal spike.
- **Use the seasonal baseline as a second signal only.** Raise its spread floor from $100K to $1M and z from 6 to 10.
- **Never suppress by time of day or by "market is stressed".** FTX-month traffic paged once under REC, and real thefts happened at every hour (`patterns.md` §1). Show a stress banner instead (§7).

## 3. Rollup gateways (Arbitrum, Base, OP Mainnet)

- **Normal traffic:** 0.7–1.5 releases a day. The median release is large ($52–$126K), and the largest was ≤ 1.6% of the vault.
- **Current rules:** zero false alarms in 11.6 bridge-weeks. **REC:** zero pages, 1 warning.
- **The quiet is a risk too.** These vaults are so sparse that their hour-of-day baseline is mostly empty, so `outflow_spike` has nothing to compare against. A drain would be caught by the vault-share rules, not the baseline.
- **Their real protection is the 7-day proof window** (`02-defenses/protocol-defenses.md` §2). The best extra signal is a *proved but not finalised* withdrawal that would release ≥ 10% of the vault. That gives days of warning. It needs portal events from SonarX.

## 4. LayerZero OFT adapters (USDT0, Kelp rsETH)

**What normal looks like:**
- USDT0 holds $3.19B, makes 212 releases a day, and releases of $40–80M happen: $80M on 2026-09-14 02:50:23 (tx `0xc3d9cab44b62e6632e6793a1b0618768c5f73366953b2e080b429ca40b093a1f`, 2.5%).
- Kelp's adapter held $284M and made 3.6 releases a day of $2–4.5M (1–1.5%) to a few recurring addresses. Example: 2026-03-09 09:26:23, $4.5M rsETH to past depositor `0xf7462251c14d…`, tx `0x3f1393e24830ed648bfc3f8e587092e2b28d43d2cf1957ea1be2cea9b94f25b2`.

**Why current rules fire:**
- `outflow_spike` accounts for 28 of 30 alarms.
- The hourly median is near zero, the $100K spread floor is 0.003% of USDT0's vault, and one exchange-sized redemption is "100 spreads" above normal.

**Patterns that resemble an attack:**
- **Exchange-sized redemption to a fresh address.** USDT0, 2026-09-30 07:07:23: 45,000,000 USDT (1.3%) to fresh `0xd00e0079b8ca…`, tx `0x838abbc2d630106e200ebdcb2acdeb46ba6af47d8a7e808158057bb5ae444519`. **REC pages** (`fresh` + `spike`); one of the 8 remaining.
- **Restaking rotations to known Kelp contracts.** Not fresh, under 2% → REC: none.

**How to suppress:**
- Scale to the vault, as for lock-boxes.
- Every OFT release is the delivery of a LayerZero packet, so the adapter design offers the **cleanest downgrade path of all**: if the packet's GUID matches a send/burn on the source chain, downgrade to info.
- Kelp's theft was exactly a packet with no matching burn (`cases/2026-04-kelpdao-rseth.md`). That check removes the residual whale pages *and* is the strongest hack signal.

## 5. Liquidity pools and intent spoke pools (Stargate V2, Across, Celer cBridge)

**What normal looks like.** Pools *are supposed to* drain and refill:
- Stargate's $20M USDC pool: 192 releases a day; net hourly outflow up to 54%; 24 h drawdown up to 66%.
- Across's spoke pool held $0.47M with 5,089 releases a day. A single WETH release of $1.3M was 86% of the pool, to a relayer or LP that deposits too: 2026-10-05 07:27:11 to `0x07ae8551be97…`, tx `0x54d1a25774c5c5b4706c429e67ceb3648f80de1bfe198cbf770747e692ee633b`.
- Celer's $1.6M vault releases $200–250K (13–15%) to users: 2026-10-02 02:18:23, $249,965 USDC, tx `0xa2cda59481fae665913dd8652dfe30e24107d8ecd9f06be680741065e6abed99`.

**Why current rules fire:**
- Stargate: 90 alarms (77 `outflow_spike`).
- Across: 32 alarms in 4 days (24 `escrow_drain`).
- Celer: 10 alarms (all `escrow_drain`).
- The vault-share rules assume escrow should be stable. A pool's balance is inventory, not escrow.

**Patterns that resemble an attack:**

| Pattern | Example | Under REC |
|---|---|---|
| Relayer or LP pulling inventory (recipient also deposits) | Across `0x07ae8551…` above | warning (past depositor: excluded from size, fresh and concentration) |
| Large bridge-in to a fresh address | Stargate, 2026-09-11 15:32:11: 9,198,114 USDC (16% of pool) to fresh `0x05ff6964d21e…`, tx `0xdd729e51c398786474880ff29f9f3bb37d138b195d6efea70a601320e532e612` | warning (pool profile: net 1h was 16%, under 20%) |
| Imbalance swings (many users, one direction) | Stargate, 2026-09-13 01:25:23: net 1h outflow 20% ($13.0M), shortly after a 20-new-recipient burst (tx `0xa7d6dac756a155f7a84fc13eb70be57efc4cdfe9abf17fdb3dcbd598abaf2ba9`). 2026-09-29 04:53:59: net 1h outflow 20% ($28.5M) with 11 new recipients in 10 min (tx `0xfad21465fcabf9f8188214b52ac6b388c54443d3631db6bb197cc8fad32f4860`) | **page**. 2 of the 8 remaining |
| Tiny-pool proportions | Celer $200–250K = 13–15% | none (below the $1M strong-size floor; a fresh $250K release alone is only a warning) |

**How to suppress (pool profile, measured):**
- Releases to addresses that have deposited before (LPs, relayers, market makers) never count toward size, fresh or concentration.
- A pool pages only if net outflow over 1 h is ≥ 20% of the pool and ≥ $1M, *and* ≥ 2 signal families agree.

Result: 13.3 → 0.36 pages per bridge-week. Without the profile, 0.97; without LP exclusion as well, 2.53 (`experiments.md` §4).

**Caveat (the hack side of this trade-off):** no pool theft is in the replay set.
- A pool drained *to an address that has deposited before* would be down-weighted.
- Pools are where **deposit↔release matching** matters most. Across fills, Stargate deliveries and cBridge relays all carry IDs that can be matched against the source chain.
- Drawdown-based backstops do **not** work for pools. A 24 h drawdown of ≥ 50% and ≥ $1M occurred at 108 releases in Stargate's normal month (the maximum was 66%, a $104M swing from a 24 h high) and at 9,200 releases in Across's week (maximum 93%). Until matching exists, the pool profile's net-flow page is the only backstop, and its miss rate on a real pool theft is unknown.

## 6. MPC custody (Multichain, March 2023)

**What normal looks like:**
- An EOA vault with 42 releases a day.
- Large releases (up to 4% of the vault) go to counterparties that also deposit, often the same day. Example: 2023-03-11 10:30:11, $5.16M DAI to `0x82287cdd…`, which deposited $2.0M within 24 h; tx `0x2a11c835b03ee281f4985e1db070ecbf4e8ef575b876598c8f031e05029ec40c`.
- Another: 2023-03-12 00:03:23, $8.1M USDC (4.05%), tx `0xdf8449e03a92a42a7f61b166ba6b755f46a471c4fcaefec5b90c4c7468d0efba`.

**Current rules:** 13 alarms in 3.86 weeks (3.37 per week). **REC:** 0 pages, 2 warnings.
- These are market-maker round trips. The recipient is not fresh.
- The theft in July went to 5 fresh addresses and took 25% of the vault in its first release.

**Residual risk.** Multichain's ops were already irregular for weeks before the theft (`cases/2023-07-multichain.md`). A baseline learned from an abnormal period hides drift, which is a reason to keep vault-relative thresholds that do not learn.

## 7. The residual: what cannot be suppressed with transfer data alone

The 8 REC pages in 76.5 bridge-weeks (`experiments/out/rec-pages.csv`):

| Window | When (UTC) | What | Families |
|---|---|---|---|
| Poly 2021 pre-hack | 2021-08-04 02:05 | $10.4M WETH (3.7%) to a fresh address | fresh + spike |
| Harmony pre-hack | 2022-06-17 05:20 | $7.0M USDC (7.5%) to a fresh address | fresh + conc |
| Nomad pre-hack | 2022-07-25 05:50 | $20M in 3 assets to one address, 9 min | fresh + conc + spike |
| Wormhole FTX | 2022-11-09 16:55 | $6M in 2 releases to one fresh address | fresh + conc |
| USDT0 | 2026-09-30 07:07 | $45M USDT (1.3%) to a fresh address | fresh + spike |
| Stargate | 2026-09-13 01:25 and 2026-09-29 04:53 | net 1h outflow ≥ 20% of the pool | crowd/net1h + spike |
| Across | 2026-10-06 07:46 | net 1h outflow 78% of a $0.47M pool | conc + net1h |

Every one of them is either a large release to a never-seen address or a deep pool imbalance. On Ethereum transfer data they look exactly like the start of a P1 sweep or a P2 drain; they differ only in that nothing more followed. Three levers remove them without losing hacks:

1. **Source-chain matching or accounting** (recommendations §3.3). A whale's bridge-in has a matching deposit or burn on the source chain; a forged release does not. Matched → downgrade to info. Unmatched → page, even at 1% of the vault.
2. **An operator or treasury address registry with expiry.** It covers announced migrations and rebalances; Nomad's $20M and HECO's post-hack sweep to `0x18709e89…` are this kind. Rules for it:
   - only for *recipient* addresses;
   - only added by a human with a reason and an expiry date;
   - shown in the alert ("recipient is on the allowlist: Orbit ops wallet, added 2023-10-01 by …").
   - An allowlist is also an attack surface: Orbit's breach was blamed on an insider who weakened controls (`cases/2023-12-orbit-bridge.md`). Changes to it should themselves be logged and shown.
3. **A short "confirm or escalate" window.** For a P1-shaped page whose second asset never moves, an operator can mark it benign in one click. That feeds the reason-code statistics (§8).

## 8. False alarms that the replay data cannot show, but production will have

These are not in this data, because the files are clean and validated (`03-onchain-data/README.md`, "Validation (all 20 files PASS)"). In live operation they are the *largest* known source of false alerts. In the Count of Monte Crypto live audit on Wormhole, all 103 alerts came from the monitor's own bugs or RPC indexing errors (`02-defenses/academic.md` A2).

| Source | What it looks like | Guard |
|---|---|---|
| Missing blocks, or an ingest gap followed by catch-up | A burst of "releases" in one poll; a deposit missed, so net flow looks like an outflow | data-health gate: hold pages while gaps exist; label LATE (the prototype already labels catch-up alerts) |
| Price glitch (stale feed, depeg, thin DEX price) | A release suddenly "worth" 10× | price sanity: two sources; cap the move per poll; tokens with estimated prices (STC, KNINE) never page on value alone |
| Decimals or rebasing tokens | Balances drift; share-of-vault wrong | decimals checked on-chain (as `validate.py` does); exclude rebasing tokens from balance math |
| Reorg past the confirmation depth | A release appears, then vanishes | keep block hashes (the prototype stores them); retract and mark "retracted", not "false alarm" |
| Monitor input poisoning (Kelp: RPC nodes showed monitors correct data) | No alert when there should be one | two independent providers; alert on disagreement |
| Vault migration (escrow moved to a new contract) | 100% drain to one address | the operator registry, and announcements; the page is still correct to send, then marked "benign: migration" |

**Reason codes:** count every page as one of
- true positive;
- benign trigger (real behaviour, not an attack);
- detector error;
- data error.

These follow Alahmadi et al. (`02-defenses/academic.md` D1). SonarX's budget of ≤ 1 per bridge per week should be judged on benign triggers plus detector errors. Data errors are fixed in the pipeline, not the thresholds.
