> Epic: #12 · Stories: #16, #17, #18

# Sources for the on-chain datasets

> Research for BridgeWatch (CPSC 490 G16, sponsor SonarX / SNX-3). Collected 2026-10-07.

Every vault address and first-theft transaction below was checked twice: once against
the reference listed, and once on-chain (the receipt of the first-theft tx shows the
tokens, or native ETH where noted, leaving that address at the reported time; see
`validate.py`). All chain data came from key-less public JSON-RPC
(`https://rpc.mevblocker.io`, `https://gateway.tenderly.co/public/mainnet`).
On-chain facts are labelled "on-chain"; everything else is what the cited source says.

## Hack cases (`hacks/`)

### poly-2021: Poly Network, 10 Aug 2021
- Vault: LockProxy `0x250e76987d838a75310c34bf422ea9f1ac4cc906`; manager EthCrossChainManager `0x838bf9e95cb12dd76a54c9f9d2e3082eaf928270`.
- Attacker `0xc8a65fadf0e0ddaf421f28feab69bf6e2e589963` (CertiK, rekt).
- On-chain: keeper swap tx `0xb1f70464...d59581` (block 12,996,659, cited by DeFiHackLabs); first native theft 2,857.49 ETH in `0xad7a2c70...602a` (block 12,996,671, 09:51:02 UTC, found by a binary search of the LockProxy ETH balance); first tracked theft 96,389,444 USDC in `0x5a8b2152...4998` (block 12,996,694).
- References: [DeFiHackLabs PoC](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2021-08/PolyNetwork_exp.sol), [rekt.news](https://rekt.news/polynetwork-rekt/), [CertiK](https://www.certik.com/resources/blog/7iLk3m8aamq1fe8rWxdrT3-poly-network-incident-analysis).

### poly-2023: Poly Network, 1 Jul 2023
- Vault: same LockProxy; unlocks went through EthCrossChainManager `0x14413419452aaf089762a0c5e95ed2a13bbc488c` (on-chain).
- Source says the attacker took ~3.01M USDC and ~2.65M USDT from the Ethereum Lock Proxy ([Odaily](https://www.odaily.news/en/post/5188161); [Beosin](https://beosin.com/resources/following-poly-network-attack-beosin-kyt-aml-keeps-tracing-)).
- On-chain: 2,651,957.23 USDT in `0x3a6e5d7e...f993` (block 17,601,076, 2023-07-01 18:47:47 UTC) and 3,012,146.20 USDC in `0x0a751cae...263d` (block 17,601,077); exact match to the reported amounts.

### heco-2023: HECO bridge, 22 Nov 2023
- Vault `0xa929022c9107643515f5c777ce9a910f0d1e490c`. Not named in the articles: identified on-chain because it released exactly the amounts CertiK lists (42,110,000 USDT, 489 HBTC, 346,867,120,000 SHIB, 173,200 UNI, 619,000 USDC, 42,399 LINK, 346,994 TUSD) to `0xfc146d1c...` on 22 Nov 2023, and its 10,145 ETH left in a tx sent by the operator CertiK names (`0x3d655889d197125fb90dcb72e4a287a8410ed1b9`).
- On-chain: native 10,145 ETH in `0xbb6fe884...131b` (block 18,626,540, 09:59:35 UTC); first tracked theft 42.11M USDT in `0x46f2ebab...b1e8` (block 18,626,564).
- References: [CertiK](https://www.certik.com/resources/blog/heco-bridge-exploit), [Cointelegraph](https://cointelegraph.com/news/heco-chain-bridge-hack-86-million-lost).

### ronin-2024: Ronin bridge, 6 Aug 2024
- Vault: proxy `0x64192819ac13ef72bf6b5ae239ac672b43a9af08` (implementation MainchainGatewayV3 `0xfc274ec9...20ee`); MEV bots `0x4ab12e7c...` (ETH) and `0x6980a47b...` (USDC). Both txs are named in [Three Sigma](https://threesigma.xyz/blog/ronin-network-12m-exploit-analysis); see also [rekt.news](https://rekt.news/roninnetwork-rektII).
- On-chain: 3,996 native ETH in `0x26195700...a6cb` (block 20,468,679); 1,998,046.875 USDC in `0xbce5b854...0ad8` (block 20,468,848). The gateway holds ETH natively (no WETH Withdrawal events), so only the USDC is visible in token logs.

### force-bridge-2025: Force Bridge (Nervos), 1 Jun 2025
- Vault `0x63a993502e74828ddba5710327afc6dc78d661b2`, attacker `0x1998c6d25212194ebf9bb919b87d40b2dc8aa8b9`, txs `0x6b6fbd9d...` and `0x9859b6cb...` ([rekt.news](https://rekt.news/force-bridge-rekt)); context from [Halborn](https://www.halborn.com/blog/post/explained-the-force-bridge-hack-june-2025) and [The Block](https://www.theblock.co/post/356535/hackers-drain-over-3-million-in-crypto-from-nervos-networks-force-cross-chain-bridge-say-security-analysts).
- On-chain: block 22,608,306 (07:16:47 UTC) moved 898,485 USDC, 257,683 USDT, 60,403 DAI, 0.79 WBTC and 539.09 native ETH; block 22,608,336 moved 4.23 WBTC.

### shibarium-2025: Shibarium bridge, 12 Sep 2025
- Vault: ERC20Predicate (escrow) `0x6aca26bfce7675ff71c734bf26c8c0ac4039a4fa`; EtherPredicate `0xc3897302ab4b42931cb4857050fa60f53b775870` ([L2BEAT Shibarium](https://l2beat.com/scaling/projects/shibarium), which also records the 12 Sep 2025 exploit); Etherscan names the contract ERC20PredicateProxy.
- Reported: 224.57 ETH and 92.6B SHIB, plus KNINE and ~15 more tokens; $2.4M-$4.1M ([The Block](https://www.theblock.co/post/373368/shiba-inu-shibarium-preps-bridge-restart-plans-user-refunds-after-4-million-exploit), [Forklog](https://forklog.com/en/news/shibarium-bridge-hacked-for-approximately-2-3-million)).
- On-chain: `0xe882a83a...7e17` (block 23,348,858, 18:44:47 UTC) moved 92,604,600,000 SHIB from the ERC20Predicate and 224.57 ETH from the EtherPredicate; `0x6df7dcb5...007a` (block 23,348,865) moved 248,989,400,000 KNINE, 29,167 LEASH (not tracked: its Transfer amounts do not reconcile with balanceOf), 21,094 USDC, 16,183 USDT and more. Attacker EOA `0x999e025a...`.

### kelp-2026: KelpDAO rsETH, 18 Apr 2026
- Vault: rsETH OFT adapter `0x85d456b2dff1fd8245387c0bfb64dfb700e98ef3`; attacker `0x1f4c1c2e610f089d6914c4448e6f21cb0db3adef`; delivery tx `0x1ae232da...4222` ([Blockaid](https://blockaid.io/blog/how-a-single-layerzero-dvn-compromise-drained-292m-from-kelpdao)); context [Galaxy](https://www.galaxy.com/insights/research/kelpdao-layerzero-exploit-defi), [The Block](https://www.theblock.co/post/397988).
- On-chain: block 24,908,285 (2026-04-18 17:35:35 UTC), 116,500 rsETH from the adapter to `0x8b1b6c9a...`.
- Price: no Chainlink rsETH/USD feed was found on-chain (a guessed rsETH/ETH feed address reverted); rsETH is priced at KelpDAO's LRTOracle `0x349a7344...020d` `rsETHPrice()` (1.0696 ETH at the theft block), confirmed as the oracle via LRTConfig `0x947cb493...5ec7` `getContract(keccak("LRT_ORACLE"))`, times Chainlink ETH/USD.

### verus-2026: Verus-Ethereum bridge, 17 May 2026
- Vault: bridge proxy `0x71518580f36feceffe0721f06ba4703218cd7f63`; attacker `0x5abb91b9...`; receiver `0x65cb8b12...` ([DeFiHackLabs PoC](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2026-05/VerusBridge_exp.sol), [Verus post-mortem on X](https://x.com/VerusCoin/status/2057465214975492358)).
- On-chain: `0x6990f017...b321` (block 25,118,335, 23:55:23 UTC) moved 103.5677 tBTC, 147,658.84 USDC and 1,625.37 native ETH, matching the PoC's constants.

### qubit-2022: Qubit QBridge, 27-28 Jan 2022 (negative control)
- Ethereum QBridge `0x20e5e35ba29dc3b540a1aee781d0814d5c77bce6`, handler (escrow) `0x17b7163cf1dbd286e262ddc68b553d899b93f526`, attacker `0xd01ae1a7...` ([DeFiHackLabs PoC](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2022-01/Qubit_exp.sol), [rekt.news](https://rekt.news/qubit-rekt/), [Qubit report](https://medium.com/@QubitFin/protocol-exploit-report-305c34540fa3)).
- On-chain: fake deposit `0xac7292e7...3133` (block 14,090,170) emits a Deposit event for 190 ETH and moves no tokens. The ~$80M was minted and borrowed on BSC.

### xbridge-2024: XBridge, 24 Apr 2024
- Vault `0x47ddb6a433b76117a98fbeab5320d8b67d468e31`, attacker `0x0cfc28d1...` ([DeFiHackLabs PoC](https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2024-04/XBridge_exp.sol), [Cyvers alert](https://twitter.com/CyversAlerts/status/1783045506471432610)).
- On-chain: 482,589,887 STC in `0x903d88a9...9c92` (block 19,723,706), then SRLTY and Mazi.
- Price: STC from its Uniswap-V2 WETH pair reserves (thin market). SRLTY (no V2 pair) and Mazi (empty pair) are left out.

## Normal and stress-normal windows (`normal/`)

| Key | Vault | Address source |
|---|---|---|
| wormhole-portal-30d, wormhole-portal-ftx-2022 | `0x3ee18b2214aff97000d974cf647e7c347e8fa585` | [Wormhole contract addresses](https://wormhole.com/docs/reference/contract-addresses/) |
| polygon-pos-erc20-30d, polygon-pos-erc20-usdc-depeg-2023 | `0x40ec5b33f54e0e8a33a975908c5ba1c14e5bbbdf` (ERC20PredicateProxy) | [Polygon mainnet index.json](https://static.polygon.technology/network/mainnet/v1/index.json) |
| usdt0-oft-adapter-30d | `0x6c96de32cea08842dcc4058c14d3aaad7fa41dee` | [USDT0 developer docs](https://docs.usdt0.to/technical-documentation/developer) |
| stargate-v2-usdc-30d | `0xc026395860db2d07ee33e05fe50ed7bd583189c7` | [Stargate V2 mainnet contracts](https://stargateprotocol.gitbook.io/stargate/v2-developer-docs/technical-reference/mainnet-contracts) |
| celer-cbridge-30d | `0x5427fefa711eff984124bfbb1ab6fbf5e3da1820` | [cBridge contract addresses](https://cbridge-docs.celer.network/reference/contract-addresses) |
| across-spokepool-30d | `0x5c7bcd6e7de5423a257d81b442095a1a6ced35c5` | [Across mainnet addresses](https://docs.across.to/reference/contract-addresses/mainnet-chain-id-1) |
| ronin-gateway-30d | `0x64192819ac13ef72bf6b5ae239ac672b43a9af08` | [Three Sigma](https://threesigma.xyz/blog/ronin-network-12m-exploit-analysis) (same proxy) |
| kelp-rseth-adapter-prehack-30d | `0x85d456b2dff1fd8245387c0bfb64dfb700e98ef3` | [Blockaid](https://blockaid.io/blog/how-a-single-layerzero-dvn-compromise-drained-292m-from-kelpdao) (same adapter) |

Every normal vault has contract code and holds the expected tokens on-chain at the window end (checked with `eth_getCode` / `balanceOf`). For the stress windows, the market context comes from [Circle's SVB update](https://www.circle.com/blog/an-update-on-usdc-and-silicon-valley-bank) (USDC depeg, 10-13 Mar 2023). The FTX window (25 Oct - 24 Nov 2022) is well-known context and has no specific citation here.

## Price sources

- Chainlink aggregators, read at the price block (the theft block for hacks, the window end for normal periods), with `description()` checked: ETH/USD `0x5f4eC3Df...8419`, BTC/USD `0xF4030086...E88c`, LINK/USD, UNI/USD `0x553303d4...`, FEI/USD `0x31e0a88f...`, TUSD/USD `0xec746eCF...`, TBTC/USD `0x8350b7De...`, SHIB/ETH `0x8dD1CD88...` (not deployed yet in Aug 2021).
- BTC-pegged wrappers with no feed (renBTC, HBTC) use BTC/USD and are flagged in `price_note`.
- Thin tokens (KNINE, STC) use Uniswap-V2 / ShibaSwap WETH pair reserves: an estimate, flagged in `price_note`. As a cross-check, KNINE comes out at ~$714k for the stolen 249B, against "approximately $700,000" in the reporting.
