> Epic: #12 · Stories: #16, #17, #18

# On-chain datasets: more bridge hacks and normal periods

> Research for BridgeWatch (CPSC 490 G16, sponsor SonarX / SNX-3). Data collected 2026-10-07 from public, key-less Ethereum JSON-RPC.
> Builds on `prototype/bridgewatch/data/` (Orbit 2023, Nomad 2022, Harmony 2022, Ronin 2022 and Multichain 2023, plus five normal windows). Those files were not fetched again here, only replayed.

Every file uses the prototype's dataset format (`prototype/bridgewatch/data/orbit-2023.json`), so it loads with `FileSource`. Hack files run through `python -m bridgewatch.replay` and normal files through `python -m bridgewatch.evaluate --real`. Each file holds every ERC-20 Transfer of the tracked tokens into or out of the vault, plus WETH wrap/unwrap rows. Zero-amount spoof transfers are dropped. **Native ETH is not visible** in token logs, and for several hacks below that is a large part of the theft.

| File | Purpose |
|---|---|
| `fetch_more.py` | Reproducible key-less builder for every file here. It imports the chunked, cached getLogs code from `prototype/scripts/fetch_datasets.py` and adds its own case list, more tokens and more price sources. |
| `validate.py` | Re-checks every file against the chain. |
| `hacks/*.json` | 10 hack cases: 9 thefts plus 1 negative control. |
| `normal/*.json[.gz]` | 8 believed-normal windows and 2 stress-normal windows. |
| `sources.md` | Every address and transaction, with references and price sources. |

## Inventory

| File | Kind | Vault | Tokens | Blocks (dates UTC) | Transfers in / out | USD out in hack window | Escrow at start |
|---|---|---|---|---|---|---|---|
| `hacks/poly-2021.json` | hack | `0x250e7698…` LockProxy | USDT, USDC, DAI, WBTC, WETH, UNI, FEI, renBTC | 12,907,436–12,998,000 (2021-07-27 → 08-10) | 694 / 623 | $262,850,777 | $267.4M |
| `hacks/poly-2023.json` | hack | `0x250e7698…` LockProxy | USDT, USDC, DAI, WBTC, WETH | 17,501,409–17,602,500 (2023-06-17 → 07-01) | 14 / 6 | $5,772,876 | $8.6M |
| `hacks/heco-2023.json` | hack | `0xa929022c…` | USDT, USDC, DAI, WBTC, WETH, LINK, UNI, TUSD, SHIB, HBTC | 18,526,500–18,628,500 (2023-11-08 → 11-22) | 10 / 36 | $65,337,547 | $67.2M |
| `hacks/ronin-2024.json` | hack | `0x64192819…` gateway | USDC, WETH, USDT, DAI, WBTC | 20,368,379–20,470,500 (2024-07-23 → 08-06) | 117 / 207 | $1,998,047 | $35.3M |
| `hacks/force-bridge-2025.json` | hack | `0x63a99350…` | USDT, USDC, DAI, WBTC, WETH | 22,508,334–22,610,000 (2025-05-18 → 06-01) | 1 / 6 | $1,739,830 | $1.7M |
| `hacks/shibarium-2025.json` | hack | `0x6aca26bf…` ERC20Predicate | SHIB, KNINE, USDT, USDC, DAI, WBTC, WETH | 23,248,656–23,350,500 (2025-08-29 → 09-13) | 37 / 15 | $2,034,879 | $2.0M |
| `hacks/kelp-2026.json` | hack | `0x85d456b2…` rsETH OFT adapter | rsETH | 24,807,814–24,910,000 (2026-04-04 → 04-18) | 51 / 55 | $295,330,837 | $311.4M |
| `hacks/verus-2026.json` | hack | `0x71518580…` | tBTC, USDC, DAI, USDT, WETH | 25,017,890–25,120,000 (2026-05-03 → 05-18) | 6 / 15 | $8,243,329 | $8.4M |
| `hacks/xbridge-2024.json` | hack | `0x47ddb6a4…` | STC, USDT, USDC, WETH | 19,623,698–19,725,000 (2024-04-10 → 04-24) | 10 / 31 | $794,558 | <$0.1M (STC deposited mid-window) |
| `hacks/qubit-2022.json` | hack (negative control) | `0x17b7163c…` QBridge handler | USDT, USDC, DAI, WBTC, WETH | 13,999,613–14,096,000 (2022-01-13 → 01-28) | 0 / 0 | $0 | $0 (held ~199 native ETH only) |
| `normal/wormhole-portal-30d.json` | normal | `0x3ee18b22…` | USDT, USDC, DAI, WBTC, WETH | 25,924,973–26,140,000 (2026-09-07 → 10-07) | 451 / 629 | – | $344.0M |
| `normal/polygon-pos-erc20-30d.json` | normal | `0x40ec5b33…` | USDT, USDC, DAI, WBTC, WETH | 25,924,973–26,140,000 (2026-09-07 → 10-07) | 625 / 778 | – | $1,706.7M |
| `normal/usdt0-oft-adapter-30d.json` | normal | `0x6c96de32…` | USDT | 25,924,973–26,140,000 (2026-09-07 → 10-07) | 4,315 / 6,329 | – | $3,190.9M |
| `normal/stargate-v2-usdc-30d.json` | normal | `0xc0263958…` | USDC | 25,924,973–26,140,000 (2026-09-07 → 10-07) | 2,365 / 6,407 | – | $20.4M |
| `normal/celer-cbridge-30d.json` | normal | `0x5427fefa…` | USDT, USDC, WETH | 25,924,973–26,140,000 (2026-09-07 → 10-07) | 1,147 / 100 | – | $1.6M |
| `normal/across-spokepool-7d.json.gz` | normal (7 days only) | `0x5c7bcd6e…` | USDT, USDC, DAI, WBTC, WETH | 26,089,788–26,140,000 (2026-09-30 → 10-07) | 78,448 / 36,609 | – | $0.5M |
| `normal/ronin-gateway-30d.json` | normal | `0x64192819…` | USDC, WETH | 25,924,973–26,140,000 (2026-09-07 → 10-07) | 3 / 15 | – | $0.5M |
| `normal/kelp-rseth-adapter-prehack-30d.json` | normal (pre-hack) | `0x85d456b2…` | rsETH | 24,566,044–24,781,027 (2026-03-02 → 04-01) | 67 / 103 | – | $283.8M |
| `normal/polygon-pos-erc20-usdc-depeg-2023.json` | **stress-normal** | `0x40ec5b33…` | USDT, USDC, DAI, WBTC, WETH | 16,694,514–16,907,900 (2023-02-24 → 03-26) | 2,068 / 1,601 | – | $1,874.3M |
| `normal/wormhole-portal-ftx-2022.json` | **stress-normal** | `0x3ee18b22…` | USDT, USDC, DAI, WBTC, WETH | 15,821,369–16,036,116 (2022-10-25 → 11-24) | 2,808 / 4,800 | – | $109.4M |

All files are under 8 MB. Only Across is gzipped (6.1 MB): its 30-day window held 621,289 rows (33 MB gzipped), so it was cut to 7 days.

### Hack cases: first theft, coverage and references

`first_theft_tx` is the first theft the file can **see** (a tracked token leaving the vault). Where native ETH left earlier, that block is in `case.first_theft_any_block`, which is also the start of `hack_window`.

| Case | First tracked theft (block) | Earlier untracked theft | What the file cannot see | References |
|---|---|---|---|---|
| poly-2021 | `0x5a8b2152…4998` 96.39M USDC (12,996,694) | 2,857 native ETH at block 12,996,671, ~4.7 min earlier | 2,857 ETH, 259.7B SHIB (no SHIB feed in 2021), project tokens | DeFiHackLabs, rekt, CertiK |
| poly-2023 | `0x3a6e5d7e…f993` 2.65M USDT (17,601,076) | – | ~60 project tokens (face value only) | Odaily, Beosin |
| heco-2023 | `0x46f2ebab…b1e8` 42.11M USDT (18,626,564) | 10,145 native ETH at block 18,626,540, ~4.8 min earlier | ~$20M ETH; the HTX hot-wallet thefts the same day | CertiK, Cointelegraph |
| ronin-2024 | `0xbce5b854…0ad8` 1.998M USDC (20,468,848) | 3,996 native ETH at block 20,468,679, ~34 min earlier | ~$10M of ~$12M (the gateway holds ETH natively) | Three Sigma, rekt |
| force-bridge-2025 | `0x6b6fbd9d…99a1` USDC+USDT+DAI+WBTC (22,608,306) | 539 ETH in the same tx | 539 ETH; the BSC leg | rekt, Halborn, The Block |
| shibarium-2025 | `0xe882a83a…7e17` 92.6B SHIB (23,348,858) | 224.57 ETH in the same tx (EtherPredicate) | ETH, LEASH (non-standard accounting), small tokens | L2BEAT, The Block, Forklog |
| kelp-2026 | `0x1ae232da…4222` 116,500 rsETH (24,908,285) | – | nothing (the adapter holds only rsETH) | Blockaid, Galaxy, The Block |
| verus-2026 | `0x6990f017…b321` 103.57 tBTC + 147,659 USDC (25,118,335) | 1,625 ETH in the same tx | 1,625 ETH (~$3.4M of ~$11.6M) | DeFiHackLabs, Verus post-mortem |
| xbridge-2024 | `0x903d88a9…9c92` 482.6M STC (19,723,706) | – | SRLTY, Mazi (no defensible price) | DeFiHackLabs, Cyvers |
| qubit-2022 | `0xac7292e7…3133` is the fake deposit and moves **no tokens** (14,090,170) | – | everything: the theft happened on BSC | DeFiHackLabs, rekt, Qubit |

Full hashes, attacker addresses and URLs are in each file's `case` block (`first_theft_tx`, `attacker_addresses`, `references`, `notes`, `coverage`) and in `sources.md`.

### Pricing

- One USD price per token per file, taken at the theft block (hacks) or the window end (normal).
- Stablecoins are fixed at $1.
- Chainlink feeds (description checked): ETH, BTC, LINK, UNI, FEI, TUSD, TBTC, and SHIB/ETH × ETH/USD.
- rsETH = KelpDAO LRTOracle `rsETHPrice()` × ETH/USD.
- renBTC and HBTC are priced at BTC/USD (an upper bound, flagged).
- KNINE and STC come from Uniswap-V2 WETH pair reserves (a thin-market estimate, flagged).
- Every file's `price_note` says which source applied to each token.

## Validation (all 20 files PASS)

`python validate.py` re-reads the chain and checks each file:

- **schema:** the required keys are present.
- **rows:** every row is inside its block and time range, has amount > 0, and has usd = amount × price.
- **duplicates:** no repeated (tx, log_index, token, direction).
- **decimals:** `decimals()` on-chain matches the file for every token.
- **balance:** `balanceOf(vault, start_block)` equals `balances_at_start` for **every** token. Also, start balance + in − out equals `balanceOf(vault, end_block)` for every token, which proves no transfer is missing.
- **first theft:** the receipt is in `first_theft_block`, and the vault's release is one of the file's rows. For qubit, the check is instead that the receipt moves no tokens.

Convention to know: `balances_at_start` is the balance at the **end** of `start_block` (same as the prototype's `fetch_datasets.py`). Rows inside `start_block` are therefore already included in it. Across had such rows, and an earlier version of `validate.py` flagged a $502.90 USDC gap until the check was adjusted. The prototype files share this convention; nothing under `prototype/` was changed.

Two problems found by validation and fixed before the final build:
- **LEASH** (Shibarium): the logged Transfer amounts (32,083 out) exceed its `balanceOf` (11,092), so the token was dropped.
- **Across:** the 30-day window was too large, so it was cut to 7 days.

## Replay results: all 15 hack cases

Run from `prototype/`: `python -m bridgewatch.replay <file> --out <scratch>/replay-<key>.json`. The detector used the default config (z 6.0, drain_share 0.05, warm-up 3 days), on a simulated pipeline of 6 confirmations, 12 s blocks and 15 s polls. "Thefts" are outflows ≥ `theft_min_usd` inside `hack_window`.

| Case | Tracked theft | Thefts | First tracked theft (UTC) | First alert (rule) | Latency after confirm | Stolen before alert | Stolen after alert | Baseline false alarms (days) |
|---|---|---|---|---|---|---|---|---|
| orbit-2023 | $59,826,263 | 4 | 2023-12-31 21:07:59 | 21:09:15 (escrow_drain) | 4 s | $10,000,000 | $49,826,263 | 0 (14.0) |
| nomad-2022 | $168,750,471 | 435 | 2022-08-01 21:32:31 | 21:33:45 (outflow_spike) | 2 s | $16,091,408 | $152,659,063 | 19 (14.0) |
| harmony-2022 | $76,205,514 | 7 | 2022-06-23 11:08:01 | 11:09:15 (escrow_drain) | 2 s | $41,200,000 | $35,005,514 | 9 (14.0) |
| ronin-2022 | $539,564,295 | 2 | 2022-03-23 13:29:09 | 13:30:30 (escrow_drain) | 9 s | $514,064,295 | $25,500,000 | 1 (14.0) |
| multichain-2023 | $111,270,957 | 7 | 2023-07-06 18:10:35 | 18:12:00 (escrow_drain) | 13 s | $27,653,471 | $83,617,486 | 0 (14.1) |
| poly-2021 | $260,894,554 | 5 | 2021-08-10 09:55:44 | 09:57:00 (escrow_drain) | 4 s | $96,389,444 | $164,505,110 | **28** (14.0) |
| poly-2023 | $5,772,876 | 3 | 2023-07-01 18:47:47 | 18:49:00 (escrow_drain) | 1 s | $5,664,103 | $108,772 | 0 (14.0) |
| heco-2023 | $65,337,547 | 7 | 2023-11-22 10:04:23 | 10:05:45 (escrow_drain) | 10 s | $42,110,000 | $23,227,547 | 2 (14.0) |
| ronin-2024 | $1,998,047 | 1 | 2024-08-06 10:11:47 | 10:13:00 (escrow_drain) | 1 s | $1,998,047 | $0 | 0 (14.0) |
| force-bridge-2025 | $1,597,055 | 3 | 2025-06-01 07:16:47 | 07:18:00 (escrow_drain) | 1 s | $1,156,168 | $440,887 | 0 (14.0) |
| shibarium-2025 | $2,025,250 | 4 | 2025-09-12 18:44:47 | 18:46:00 (escrow_drain) | 1 s | $1,254,404 | $770,847 | 0 (14.0) |
| kelp-2026 | $294,213,759 | 1 | 2026-04-18 17:35:35 | 17:37:00 (escrow_drain) | 13 s | $294,213,759 | $0 | 3 (14.0) |
| verus-2026 | $8,243,322 | 2 | 2026-05-17 23:55:23 | 23:56:45 (escrow_drain) | 10 s | $8,243,322 | $0 | 0 (14.0) |
| xbridge-2024 | $794,558 | 1 | 2024-04-24 07:19:35 | 07:21:00 (escrow_drain) | 13 s | $794,558 | $0 | 5 (14.0) |
| qubit-2022 | $0 | 0 | – | **none**: nothing left the Ethereum vault | – | – | – | 0 |

"Latency" is measured from the first **tracked** theft's confirmation. Against the first real theft:
- **poly-2021:** native ETH left at 09:51:02, so the alert came ~6 min after the theft began.
- **heco-2023:** ETH left at 09:59:35, ~6 min before the alert.
- **ronin-2024:** ETH left at 09:37:23, ~36 min before the alert.

## False alarms on normal and stress-normal data

Run from `prototype/`: `python -m bridgewatch.evaluate --real --data ../research/bridge-hacks/03-onchain-data/normal --out <scratch>`. Every alert after the 3-day warm-up is counted as a false alarm. The target is ≤ 1 per bridge per week.

| Dataset | Weeks counted | Transfers | False alarms | Per week | By rule |
|---|---|---|---|---|---|
| wormhole-portal-30d | 3.86 | 1,080 | 1 | 0.26 | outflow_spike 1 |
| polygon-pos-erc20-30d | 3.86 | 1,403 | 1 | 0.26 | withdrawal_burst 1 |
| ronin-gateway-30d | 3.86 | 18 | 0 | 0.00 | – |
| celer-cbridge-30d | 3.86 | 1,247 | 10 | 2.59 | escrow_drain 10 |
| kelp-rseth-adapter-prehack-30d | 3.86 | 170 | 11 | 2.85 | outflow_spike 11 |
| usdt0-oft-adapter-30d | 3.86 | 10,644 | 19 | 4.93 | outflow_spike 17, large_withdrawal 1, withdrawal_burst 1 |
| stargate-v2-usdc-30d | 3.86 | 8,772 | 90 | 23.33 | outflow_spike 77, large_withdrawal 5, escrow_drain 4, withdrawal_burst 4 |
| across-spokepool-7d | 0.57 | 115,057 | 32 | 56.0 | escrow_drain 24, outflow_spike 7, large_withdrawal 1 |
| polygon-pos-erc20-usdc-depeg-2023 (stress) | 3.86 | 3,669 | 1 | 0.26 | outflow_spike 1 |
| wormhole-portal-ftx-2022 (stress) | 3.86 | 7,608 | 47 | 12.19 | outflow_spike 33, withdrawal_burst 9, large_withdrawal 4, escrow_drain 1 |
| **new total** | 35.31 | | 212 | **6.00** | |
| earlier 5 (prototype/bridgewatch/data/normal) | 19.3 | | 14 | 0.73 | OP/Base/Arbitrum 0, Orbit 0.26, Multichain 3.37 |

## What these numbers suggest (for the team to judge)

- **Detection was fast on every case with a visible outflow.** Every hack that moved tracked tokens alerted within 1–13 s of confirmation, almost always on `escrow_drain`.
- **Fast detection did not limit the loss in single-transaction drains.** In kelp, verus, ronin-2024 and xbridge (and ~98% of poly-2023), everything was gone before the first alert. An alert can only cut losses when the drain takes several transactions (Nomad, Orbit, Multichain, Poly 2021).
- **The rules would not have fired, or fired late, in these cases:**
  - **qubit:** nothing left the Ethereum vault.
  - **Native-ETH thefts:** in ronin-2024, heco, poly-2021, verus, force and shibarium, native ETH is invisible to Transfer logs. In three of these it left before any token did.
- **False alarms are the weak point on liquidity-pool and OFT-style vaults.** Stargate, Across, USDT0, Celer and the rsETH adapter run 2.6–56 alarms per week; canonical lock-box bridges run ≤ 0.26.
  - Poly Network's busy 2021 LockProxy produced 28 baseline alarms in 14 days.
  - Small vaults (XBridge, Across with ~$0.5M escrow) trip `escrow_drain` on $3k–$40k moves.
- **Stress windows split.** The USDC-depeg month on Polygon PoS stayed quiet (0.26 per week), but the FTX month on Wormhole Portal ran 12.2 per week, against 0.26 in a normal month.

## Not collected, and why

| Candidate | Reason |
|---|---|
| THORChain ETH router, Jul 2021 | Funds sat in rotating Asgard vault EOAs, and the router only forwards them. There is no single fixed vault, so it does not fit the one-vault format without more research. |
| ChainSwap, Jul 2021 | Exploited through each project's bridged-token contracts (mints or unlocks of dozens of small tokens). There is no single vault and no defensible prices. |
| Meter, Feb 2022 | The losses were on the BSC and Moonriver side. I could not confirm an Ethereum-side vault release (DeFiHackLabs itself flags the reference tx as doubtful). |
| CrossCurve, Feb 2026 | No public source gives the PortalV2 addresses or the Ethereum txs. The articles do not say Ethereum was hit. |
| Hyperbridge, Apr 2026 | Fake DOT was minted on Ethereum and dumped into DEX pools (a mint, not an escrow drain). *Reviewer correction:* the ~245 ETH taken from TokenGateway left as an ERC-20 **WETH** Transfer (tx `0xeff151ef…2d59`, block 24,868,029, 03:02:11 UTC; 245.93 WETH, unwrapped by the recipient in the same tx), so it is visible in Transfer logs. Not collected yet; a candidate to add. |
| Socket (Jan 2024), LI.FI (Jul 2024) | Approval drains: tokens were pulled from users' wallets through the router, not out of a vault. A vault monitor sees nothing, which is the same lesson as qubit. |
| AdsharesBridge (May 2026), AllbridgeCCTP and SandboxOFT (Aug 2026) | Adshares is a mint of the bridged token (no escrow outflow). The other two are on Base. |

## Reproduce

```sh
# from anywhere, with the prototype's Python env (httpx)
python research/bridge-hacks/03-onchain-data/fetch_more.py --list
python research/bridge-hacks/03-onchain-data/fetch_more.py              # all 20 files (~30 min)
python research/bridge-hacks/03-onchain-data/validate.py                # re-check against the chain
```

The live windows end at the fixed block 26,140,000 and the dated windows resolve to fixed blocks, so a rerun reproduces the same rows. The prices in the hack files are the same; `fetched` changes.
