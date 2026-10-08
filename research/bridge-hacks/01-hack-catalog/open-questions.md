> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Open questions and conflicts in the hack catalog

Each item says what conflicts, what we checked, and what a human should decide. On-chain times come from block timestamps read on 2026-10-07. Every "unknown" in `hacks.csv` is a real gap. None were filled in by guessing.

## 1. Multichain 2023: test transaction or start of the drain?
- **Conflict:** The first outflow we found from the Fantom bridge escrow is a $2 USDC transfer at **16:21:23 UTC** (block 17635954). The first large drain, 27.65M USDC, is at **18:10:35 UTC** (block 17636491), 1 h 49 min later. Unchained and Cyvers call the $2 transfer a "test". `verified-ethereum-cases.md` lists the 16:21 tx as `first_theft_tx`.
- **Why it matters:** Drain duration and time-to-detection change by about 2 hours depending on which start is used. A size-based rule cannot fire on $2.
- **Proposed handling:** Use 18:10:35 as the start for latency measurement in stories #16–#18. Keep 16:21:23 as a "precursor" event in the replay data.

## 2. IoTeX 2026: upgrade at 01:20:35 (on-chain) or 01:51 (IoTeX timeline)?
- **Conflict:** On-chain, the Validator ownership transfer is at **01:07:35** (block 24501847), the upgrade at **01:20:35** (block 24501912), and the first TokenSafe theft at **01:25:47** (block 24501938). IoTeX's incident report puts the malicious upgrade at **01:51 UTC**. Crowdfund Insider says the exploit ran roughly 07:00–09:00 UTC.
- **Possible explanations:** IoTeX may be citing a later, second upgrade, or a different contract (MintPool), or a time zone slip. We did not trace every upgrade event that day.
- **Action:** Pull all `Upgraded` and `OwnershipTransferred` logs on ioTube's Ethereum contracts for 2026-02-21 before using this case as the `config_change` benchmark.
- **Loss figure:** IoTeX says about $4.4M; Crowdfund Insider, citing leadership, says about $2M. The CSV uses $4.4M.

## 3. Hyperbridge 2026: $237K, $806K or $2.5M?
- **$237K:** Hyperbridge's first estimate (Cointelegraph). This is what the bridged-DOT dump realised.
- **About $806K:** the $237K plus about 245 ETH (about $561K) taken from a separate contract "hours before" the minting (Decrypt). Our first-theft tx (03:02:11, WETH out of TokenGateway) is 53 minutes before the 03:55:23 mint, not "hours". Whether that 245 ETH is the same event is unverified.
- **About $2.5M:** total realised losses across Ethereum, Arbitrum, Base and BNB Chain, as stated in a Polkadot forum pre-proposal. That is a community document quoting Hyperbridge, and it matches DefiLlama.
- **CSV uses** $2.5M. Hypernative's "$1.2B minted" is face value, not loss.

## 4. Gravity Bridge 2026: key compromise or forged claim?
- Most outlets, and DefiLlama ("Validator Key Compromised"), report a compromised signing key. QuillAudits instead describes a newly registered validator plus a token-deployment claim that the bridge accepted without checking.
- No official post-mortem was found. The CSV uses `key/signer compromise`, and catalog.md marks it disputed.
- Revisit this when Gravity publishes a post-mortem.

## 5. Single-source (mostly DefiLlama-only) incidents needing a second source
These rows have `status = unconfirmed` in `hacks.csv`. Loss and category are DefiLlama's. Most need a project post-mortem or a rekt/SlowMist/The Block article before they can be confirmed.

| Date | Incident | DefiLlama loss | Note |
|---|---|---:|---|
| 2021-06-29 | THORChain (June) | $350K | possibly an early part of the July THORChain incidents |
| 2021-07-02 | XDX Swap (HECO) | $176K | |
| 2022-05-18 | QANX Bridge | $707K | |
| 2022-11-02 | Rubic (key) | $1.2M | distinct from the Dec 2022 Rubic router row |
| 2022-11-03 | pNetwork pGALA | $4.3M | |
| 2022-11-23 | Numbers Protocol | $13.8K | |
| 2023-02-15 | Multichain V4 router WETH permit | $130K | one search result mentions about 87 ETH |
| 2023-04-23 | FilDA | $700K | DefiLlama itself does not flag it as a bridge hack |
| 2024-05-16 | ALEX (Stacks) | $4.3M | |
| 2024-08-12 | Poly Network (2024) | $5M | technique "Unknown" in DefiLlama |
| 2024-12-29 | Fegex | $1.07M | |
| 2025-01-01 | NoOnes | $7.9M | P2P platform's Solana bridge |
| 2025-07-09 | ZKSwap | $5M | |
| 2025-07-10 | Kinto | $1.55M | may be token/proxy, not a bridge |
| 2025-07-29 | Anyswap legacy router permit | unknown | tx verified on-chain (block 23026900), but only DeFiHackLabs lists it; loss not published |
| 2025-09-23 | Seedify SFUND | $1.2M | |
| 2025-09-24 | GriffinAI | $3M | |
| 2025-10-27 | 402bridge | $17.7K | |
| 2026-02-01 | CrossCurve | $3M | |
| 2026-04-09 | Aethir | $400K | |
| 2026-04-27 | ZetaChain | $334K | |
| 2026-04-29 | Syndicate | $380K | DefiLlama lists funds returned |
| 2026-05-18 | Echo Bridge (Monad) | $821K | |
| 2026-05-30 | Alephium bridge | $815K | |
| 2026-06-10 / 06-19 | Axelar-Secret IBC / Secret Network | $4.67M each | **probably one incident counted twice** |
| 2026-06-19 | Namada shielded pools | $600K | |
| 2026-06-21 | Taiko bridge | $1.7M | one KuCoin blog post also mentions it |
| 2026-07-26 | ChainConnect | $650K | |
| 2026-08-08 | Oraichain | $1.0M | |
| 2026-08-18 | Maya Protocol | $1.7M | |
| 2026-08-23 | warp.green | $93K | |
| 2026-09-09 | Nomic | $3.15M | |
| 2026-09-10 | Symbiosis | $336K | |
| 2026-09-12 | Chainflip (Tron) | $736K | |
| 2026-09-19 | Fetch.ai bridge | $1.53M | |
| 2026-09-24 | Payy Network | $1.83M | |
| 2026-10-01 | NEAR Intents | $3.8M | |

## 6. Off-scope decisions (a human should confirm)
- **Harmony, Aug 2026:** about 4B ONE minted on Harmony L1 (about $3.2M at market). This is a chain-level mint, not a bridge escrow, and Harmony had not disclosed a root cause. DefiLlama tags it as a bridge hack. We list it as off-scope.
- **TAC, Aug 2026:** an exploit of TAC's Cosmos-based EVM chain that affected TAC token supply. Validators halted. This is distinct from the **May 2026** TON-TAC bridge exploit, which *is* in scope and confirmed. Note that DefiLlama dates the bridge incident 2026-05-11; the August event is a separate chain incident.
- **"Fake GIWA Bridge", Sep 2026:** a counterfeit chain and bridge reusing GIWA's chain ID drained about 766 ETH from about 1,335 addresses after a DEX listed it. No real bridge was compromised. It is an impersonation scam that vault monitoring cannot see by design.
- **Also off-scope:** Synapse 2021 (attempt stopped, $0 loss), Hector Lending, DIMO, Port3, DGLD, Stake DAO and BarnBridge (not bridge vaults).

## 7. Other unresolved figures
- **Nomad recovered share:** whitehat returns are widely reported but the exact total varies. The CSV says "partial".
- **Poly Network 2021:** detection time is "same day"; no minute-level public alert time was found.
- **ChainSwap 1 and 2, Multichain 2022:** the tx hashes are example txs from DeFiHackLabs proofs of concept. They may not be the first theft.
- **Wormhole recovery:** the CSV records 100% as "backstopped by Jump". Reported later recoveries from the attacker are not included because we did not verify them.
- **Ronin 2022 detection:** the ~6 days is time to discovery by the operator. Forta's retrospective shows automated alerts fired within about 17 minutes.
- **Drain durations:** known for only 10 confirmed incidents. More can be computed from the first and last theft blocks once full theft-tx lists are pulled (Harmony, HECO, Multichain, Verus, IoTeX).
- **Wanchain loss:** sources range from $6.5M to $13M; the CSV uses $9M and DefiLlama lists $10M.
- **Force Bridge loss:** sources range from $3.0M to $3.9M; the CSV uses $3.76M (Halborn).
