> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Bridge incident catalog for detection engineering (2021 – Oct 2026)

Research date: 2026-10-07. Times are UTC. This is a post-mortem catalog: for each incident it records what failed (as a category), what was lost, how the team responded, and what a vault monitor could have seen. It does not describe how any attack was carried out.

**Files in this folder**
- `hacks.csv` / `hacks.json`: the same 102 rows in two formats. Status counts: 54 `confirmed`, 38 `unconfirmed`, 10 `off-scope`.
- `cases/`: 20 incident pages, each with a timeline, the on-chain signature, the rules that would fire, and false-alarm notes.
- `verified-ethereum-cases.md`: first-theft transactions re-read from public RPC nodes. Written by an earlier agent and not changed here.
- `sources.md`: every URL used. `open-questions.md`: conflicts and claims not yet verified.

**Status definitions**
- `confirmed`: at least two independent sources, or one detailed source plus a transaction we checked on-chain.
- `unconfirmed`: listed only by DefiLlama, or by one source. Loss and cause are taken from that listing as-is.
- `off-scope`: not a bridge-vault theft. Examples are an L1 consensus mint, an impersonation scam, a non-bridge DeFi hack, or an attempt that was stopped.

**Block-number convention:** a bare number is an Ethereum block. Blocks on other chains are prefixed with the chain: `bsc:`, `base:` or `arbitrum:`.

**How rules were assigned:** `rules_that_fire` lists the BridgeWatch rules whose trigger condition the public facts satisfy. The detector has **not** been replayed on all of these. Only the Ethereum rows that have a first-theft block can be replayed today (30 confirmed rows).

## 1. Overview (confirmed incidents, by date)

Detectability is one of four values:
- **V** = vault-outflow rules see it.
- **A** = needs cross-chain accounting (unbacked mint, escrow untouched).
- **N** = not visible in vault data.
- **+C** = a config/upgrade event came before the theft.

| Date | Bridge | Design | Root cause | Loss ($M) | Vault drained | Detect. | Page |
|---|---|---|---|---:|---|---|---|
| 2021-07-03 | ChainSwap (1) | lock-mint | verification bug | 0.8 | partial | V | |
| 2021-07-10 | Anyswap V3 pools | mpc-custody | key/signer compromise | 7.9 | yes | V | |
| 2021-07-10 | ChainSwap (2) | lock-mint | verification bug | 4.4 | no (mint) | A | |
| 2021-07-15 | THORChain router (1) | liquidity-pool | message/proof forgery | 5.0 | partial | V | |
| 2021-07-22 | THORChain router (2) | liquidity-pool | message/proof forgery | 8.0 | partial | V | |
| 2021-08-10 | Poly Network | messaging | access control | 611.0 | yes | V +C | [page](cases/2021-08-poly-network.md) |
| 2021-09-19 | pNetwork pBTC | lock-mint | message/proof forgery | 12.7 | yes | V | |
| 2021-11-15 | Nerve Bridge pool | liquidity-pool | other | 0.54 | partial | V | |
| 2022-01-18 | Multichain router approvals | router/aggregator | user-approval abuse | 1.4 | no | N | |
| 2022-01-27 | Qubit QBridge | lock-mint | message/proof forgery | 80.0 | no (mint) | A | |
| 2022-02-02 | Wormhole | messaging | verification bug | 326.0 | partial | V | [page](cases/2022-02-wormhole.md) |
| 2022-02-05 | Meter Passport | lock-mint | message/proof forgery | 4.4 | yes | V | |
| 2022-03-20 | LI.FI | router/aggregator | user-approval abuse | 0.6 | no | N | |
| 2022-03-23 | Ronin | lock-mint | key/signer compromise | 624.0 | yes | V | [page](cases/2022-03-ronin.md) |
| 2022-06-23 | Harmony Horizon | lock-mint | key/signer compromise | 100.0 | yes | V | [page](cases/2022-06-harmony.md) |
| 2022-08-01 | Nomad | messaging | faulty upgrade/initialisation | 190.0 | yes | V +C | [page](cases/2022-08-nomad.md) |
| 2022-08-17 | Celer cBridge frontend | liquidity-pool | frontend/DNS | 0.24 | no | N | |
| 2022-10-02 | Transit Swap | router/aggregator | user-approval abuse | 21.2 | no | N | |
| 2022-10-06 | BNB Chain Token Hub | lock-mint | message/proof forgery | 570.0 | no (mint) | A | [page](cases/2022-10-bnb-token-hub.md) |
| 2022-12-25 | Rubic | router/aggregator | user-approval abuse | 1.41 | no | N | |
| 2023-04-01 | Allbridge Core (BSC) | liquidity-pool | other | 0.57 | partial | V | |
| 2023-07-01 | Poly Network (2023) | messaging | key/signer compromise | 5.0 | partial | V | |
| 2023-07-06 | Multichain | mpc-custody | insider/custody | 126.0 | yes | V | [page](cases/2023-07-multichain.md) |
| 2023-11-22 | HECO Bridge | lock-mint | key/signer compromise | 86.6 | yes | V | [page](cases/2023-11-heco-bridge.md) |
| 2023-12-31 | Orbit Bridge | lock-mint | key/signer compromise | 81.7 | yes | V | [page](cases/2023-12-orbit-bridge.md) |
| 2024-01-16 | Socket/Bungee | router/aggregator | user-approval abuse | 3.3 | no | N +C | [page](cases/2024-01-socket-bungee.md) |
| 2024-04-24 | XBridge | lock-mint | access control | 1.44 | partial | V | |
| 2024-07-16 | LI.FI (2024) | router/aggregator | user-approval abuse | 9.73 | no | N +C | |
| 2024-08-06 | Ronin (2024) | lock-mint | faulty upgrade/initialisation | 12.0 | partial | V +C | [page](cases/2024-08-ronin.md) |
| 2025-06-01 | Force Bridge | lock-mint | access control | 3.76 | yes | V +C | |
| 2025-09-12 | Shibarium | lock-mint | key/signer compromise | 2.4 | partial | V +C | [page](cases/2025-09-shibarium.md) |
| 2025-10-30 | Garden Finance solver | router/aggregator | key/signer compromise | 11.0 | partial (solver) | N | |
| 2026-02-21 | IoTeX ioTube | lock-mint | key/signer compromise | 4.4 | yes | V +C | [page](cases/2026-02-iotex-iotube.md) |
| 2026-04-13 | Hyperbridge | messaging | message/proof forgery | 2.5 | partial | V | [page](cases/2026-04-hyperbridge.md) |
| 2026-04-18 | KelpDAO rsETH | messaging | verifier/oracle/RPC manipulation | 292.0 | yes | V | [page](cases/2026-04-kelpdao-rseth.md) |
| 2026-05-11 | TAC TON-TAC | lock-mint | message/proof forgery | 2.86 | partial | V | |
| 2026-05-15 | THORChain Asgard vault | mpc-custody | key/signer compromise | 10.7 | partial | V | |
| 2026-05-15 | Adshares | lock-mint | message/proof forgery | 0.63 | no (mint) | A | |
| 2026-05-17 | Verus-Ethereum (1) | lock-mint | message/proof forgery | 11.58 | yes | V | [page](cases/2026-05-verus.md) |
| 2026-05-20 | MAP Protocol | burn-mint | verification bug | 0.11 | no (mint) | A | |
| 2026-05-30 | Gravity Bridge | lock-mint | key/signer compromise (disputed) | 5.4 | yes | V | [page](cases/2026-05-gravity-bridge.md) |
| 2026-06-07 | Syscoin | lock-mint | message/proof forgery | 10.0 | no (mint) | A | |
| 2026-06-14 | Aztec Connect | canonical-rollup | verification bug | 2.19 | yes | V | [page](cases/2026-06-aztec-connect.md) |
| 2026-06-17 | Aztec V1 escape hatch | canonical-rollup | verification bug | 2.2 | yes | V | (in Aztec page) |
| 2026-07-17 | Across (Solana relayer) | router/aggregator | verifier/oracle/RPC manipulation | 4.5 | no | N | |
| 2026-07-19 | Allbridge Core (Solana) | liquidity-pool | other | 1.65 | partial | V | |
| 2026-07-21 | Wanchain Cardano-BNB | lock-mint | verification bug | 9.0 | yes | V | |
| 2026-07-22 | AFX Trade (Arbitrum) | lock-mint | key/signer compromise | 24.15 | yes | V | [page](cases/2026-07-afx.md) |
| 2026-07-23 | Verus-Ethereum (2) | lock-mint | message/proof forgery | 7.53 | yes | V | [page](cases/2026-05-verus.md) |
| 2026-07-26 | Garden Finance (2) | router/aggregator | key/signer compromise | 0.45 | partial (solver) | N | |
| 2026-08-09 | Coreum-XRPL | lock-mint | other | 0.2 | partial | V | |
| 2026-08-19 | Allbridge CCTP router | router/aggregator | message/proof forgery | 0.19 | partial | V | |
| 2026-08-22 | Sandbox SAND OFT | messaging | access control | 0.68 | partial | A +C | |
| 2026-09-06 | Liquid Network peg | mpc-custody | verification bug | 320.0 | yes (~95%) | V | [page](cases/2026-09-liquid-network.md) |

`hacks.csv` also holds 38 unconfirmed rows (mostly DefiLlama-only, listed in `open-questions.md` §5) and 10 off-scope rows.

## 2. Grouped by root cause (confirmed, n = 54)

| Root cause | Count | Loss ($M) | Examples |
|---|---:|---:|---|
| key/signer compromise | 13 | 963.7 | Ronin 2022, Harmony, HECO, Orbit, Shibarium, IoTeX, Gravity*, AFX*, THORChain 2026 |
| message/proof forgery | 13 | 715.4 | Qubit, BNB Token Hub, Verus ×2, Hyperbridge, Syscoin, TAC |
| verification bug | 8 | 664.7 | Wormhole, Liquid, Aztec ×2, Wanchain, ChainSwap ×2, MAP |
| access control | 4 | 616.9 | Poly 2021, XBridge, Force Bridge, Sandbox OFT |
| verifier/oracle/RPC manipulation | 2 | 296.5 | KelpDAO (poisoned RPC behind a 1-of-1 verifier), Across Solana relayer |
| faulty upgrade/initialisation | 2 | 202.0 | Nomad, Ronin 2024 |
| insider/custody | 1 | 126.0 | Multichain |
| user-approval abuse | 6 | 37.6 | Multichain 2022, LI.FI ×2, Transit Swap, Rubic, Socket |
| other (pool pricing etc.) | 4 | 3.0 | Nerve, Allbridge ×2, Coreum |
| frontend/DNS | 1 | 0.2 | Celer cBridge |

\* The cause is disputed or comes from one outlet. See `open-questions.md`.

Two caveats about these categories:
- "Message/proof forgery" and "verification bug" overlap. In both, a check that should have rejected a release did not. We use **forgery** when the reports stress a fabricated message or event, and **verification bug** when they stress the checking code.
- Three upgrades were key compromises that showed up as a config change: IoTeX (owner key, then upgrade), Poly 2021 (keeper replacement) and Shibarium (signer-set capture). These are counted under their root cause, but they are also flagged **+C**.

## 3. Grouped by bridge design (confirmed)

| Design | Count | Loss ($M) | Observation |
|---|---:|---:|---|
| lock-mint (validator/multisig) | 24 | 1,659.9 | The most common design. The escrow is a single contract, so its outflows map directly to BridgeWatch's per-vault baseline. |
| messaging (generic message layer + token adapter) | 7 | 1,427.2 | Poly, Wormhole, Nomad, KelpDAO, Hyperbridge. Losses are huge per incident, and most of the value is often minted on the far side. |
| mpc-custody / federation | 4 | 464.6 | Anyswap, Multichain, THORChain 2026, Liquid. Thefts look like normal signed withdrawals, so only volume and pattern give them away. |
| router/aggregator | 10 | 53.8 | These are mostly user-allowance drains, so the escrow balance does not move. |
| liquidity-pool | 6 | 16.0 | Small, pool-pricing style losses. |
| canonical-rollup | 2 | 4.4 | Both were deprecated Aztec contracts that were immutable and could not be paused. |
| burn-mint | 1 | 0.1 | MAP Protocol, where unbacked supply appeared on Ethereum. |

## 4. Grouped by detectability

The buckets are computed from `rules_that_fire` and `vault_drained`:
- **V** applies if any outflow rule fires and the vault actually lost funds.
- **A** applies if the vault was not drained but supply was minted.
- **N** applies to user-allowance and solver-wallet losses.

| Bucket | Count | Loss ($M) | Incidents |
|---|---:|---:|---|
| **V: vault-outflow rules catch it** (`escrow_drain`, `outflow_spike`, `large_withdrawal`, `withdrawal_burst`) | 37 | ~2,906 | Ronin ×2, Poly 2021, Poly 2023, Wormhole (ETH leg), Harmony, Nomad, Multichain, HECO, Orbit, Force, Shibarium, IoTeX, KelpDAO, Verus ×2, Gravity, Aztec ×2, AFX, Liquid, THORChain ×3, … |
| **A: needs cross-chain accounting** (`accounting_mismatch`) | 7 | ~666 | BNB Token Hub, Qubit, ChainSwap 2, Syscoin, Adshares, MAP, Sandbox OFT |
| **C: config-change monitoring gives an early warning** (cross-cutting) | 9 flagged | — | Poly 2021 (2 min lead), Ronin 2024 (49 min), IoTeX (18 min), Nomad (41 days), Socket (3 days), Force, Shibarium, LI.FI 2024, Sandbox OFT |
| **N: not visible in vault data** | 10 | ~53 | Multichain 2022, LI.FI ×2, Transit Swap, Rubic, Socket, Celer frontend, Across relayer, Garden ×2 |

Several incidents straddle buckets. In Wormhole, Poly 2023, KelpDAO, Hyperbridge, Verus and Liquid, value was both minted and released from an escrow. Each is listed under V because an escrow did lose funds, but the accounting rule would also have fired.

## 5. Summary statistics (computed from `hacks.csv`, confirmed rows only)

| Metric | Value |
|---|---|
| Confirmed incidents | 54 (of 102 rows; 38 unconfirmed, 10 off-scope) |
| By year (count / $M) | 2021: 8 / 650 · 2022: 12 / 1,919 · 2023: 5 / 300 · 2024: 4 / 26 · 2025: 3 / 17 · 2026 (to Oct 7): 22 / 713 |
| Total reported loss | **$3.63B** (headline figures. These are not net of recoveries. BNB's $570M is minted value, of which only about $100–137M left BSC.) |
| Median loss | **$5.0M** (mean $67M; the top 5 incidents account for 68% of the total) |
| Key/signer compromise share | 13/54 incidents (**24%**) and $964M (**27%** of loss). Adding insider/custody (Multichain) gives 14/54 (26%) and $1.09B (30%). |
| Vault drained | yes 21 · partial 19 · no 14 |
| Drain duration (n = 10 with a public start and end) | median **~13 min**. Values: Ronin 2, Gravity 3.2, Wormhole ETH leg 7.5, Orbit 18, KelpDAO 0 and Aztec 0 (single tx), Celer 118 (victim thefts), Hyperbridge ~125, BNB 136, Nomad ~150 (main wave) |
| Drained in ≤ 1 hour | **6 of 10** with known duration, all within 20 minutes. The longer ones were copycats (Nomad), repeated mints or follow-on targets (BNB, Hyperbridge), or a frontend phishing window (Celer). |
| Time to detection or first response (21 with data) | ≤ 10 min: 8 (Multichain test, Orbit, Verus ×2, Gravity, Hyperbridge, AFX, Aztec) · 10–60 min: 3 (Ronin 2024 38 min, Wormhole ~43, KelpDAO 46) · 1–24 h: 8 (Socket ~1 h, BNB ~2 h, Nomad ~3 h, Poly 2023 ~7 h, Harmony >14 h, Poly 2021, HECO, IoTeX "hours") · > 1 day: 2 (Force ~1 day, Ronin 2022 ~6 days) · unknown: 33 |
| Funds recovered | Recovery data exists for only a minority of rows. The largest returns came from attacker negotiation (Poly 2021 ~100%, Liquid ~85%, Verus ~75%, TAC ~90%, Ronin 2024 ~96%) or from issuer freezes (Multichain ~50% frozen). |

Caveat on detection times: the column mixes "a security firm posted publicly" with "the operator paused". Those are different events. In Hyperbridge, the main 03:55 mint was flagged within the minute (about 53 minutes after the first ~245 WETH release at 03:02), but the freeze took more than 70 minutes more.

## 6. What this means for BridgeWatch

1. **The core rule set fits most of the money.** 37 of 54 confirmed incidents (about 80% of confirmed loss) emptied or partly emptied an escrow. `escrow_drain`, `large_withdrawal` and `withdrawal_burst` would have fired on the first or second theft transaction. Key compromises (the largest category) look like *validly signed* withdrawals, so volume and pattern are the only on-chain tells.
2. **Speed matters more than sophistication.** The median drain is about 13 minutes, and 6 of the 10 timed drains finished in under 20 minutes. Hourly baselines should be evaluated per block or per transaction, not hourly. An alert that arrives after the hour closes is a post-mortem.
3. **The first transaction is usually lost. Follow-ons are where an alert pays.** Repeat attempts or long tails followed the first theft in KelpDAO (2 reverted replays 5 minutes after the pause), Hyperbridge (5 follow-ons over 70 minutes), Nomad (hundreds of copycats) and Multichain (a $2 test about 2 hours before the main drain).
4. **Add a config-change watcher.** In 9 cases an upgrade, ownership transfer or signer/route change came before the theft, with lead times from 2 minutes (Poly 2021) to 41 days (Nomad). This is cheap to monitor (Upgraded, OwnershipTransferred, signer-set events) and has a very low base rate.
5. **Cross-chain accounting covers the next 7 cases** (BNB, Qubit, Syscoin and others), where the escrow never moves. This needs supply-vs-escrow reconciliation and is a CPSC 491 stretch goal, not a Goal 2 rule.
6. **Be honest about blind spots.** Allowance drains (routers, aggregators) and solver or relayer wallet losses (10 cases) never touch the escrow. BridgeWatch should say so in its threat model and not count them as misses.
7. **Route alerts downstream.** Stablecoin issuers (Multichain's ~$65M USDC freeze), lending markets (Aave froze rsETH 77 minutes after KelpDAO) and token issuers (KNINE blacklist in Shibarium) were often the most effective responders. An alert should name tokens, amounts and recipient addresses.
8. **Replay set.** 30 confirmed Ethereum rows have a first-theft block and tx hash (`verified-ethereum-cases.md`). That is enough to measure detection latency for stories #16–#18, together with the normal-traffic false-alarm rate.
