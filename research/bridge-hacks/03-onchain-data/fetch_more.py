"""
Fetch more BridgeWatch evaluation datasets (bridge hacks + believed-normal and
stress-normal periods) from public Ethereum JSON-RPC. No API keys.

Same file format as prototype/bridgewatch/data/orbit-2023.json, so every file here
loads with prototype/bridgewatch/source.py:FileSource and runs through
`python -m bridgewatch.replay` (hacks) and `python -m bridgewatch.evaluate --real`
(normal / stress-normal).

The heavy lifting (chunked, cached, resumable eth_getLogs; ERC-20 Transfer plus
WETH Deposit/Withdrawal rows; zero-amount spoof transfers skipped; gzip above
8 MB) is imported from prototype/scripts/fetch_datasets.py. This driver only adds
its own case list, more tokens, and more price sources:

  fixed        a constant (stablecoins at $1)
  chainlink    a Chainlink USD aggregator answer at the price block
  chainlink_x  a Chainlink X/ETH (or X/BTC) answer times the ETH/USD (BTC/USD) answer
  btc_proxy    a BTC-pegged token priced at Chainlink BTC/USD (flagged in price_note)
  lrt          KelpDAO LRTOracle.rsETHPrice() (rsETH in ETH) times Chainlink ETH/USD
  dexv2        Uniswap-V2-style pair reserves against WETH (deepest of the listed
               factories) times Chainlink ETH/USD: a thin-market estimate, flagged

Every token's decimals() is read on-chain at the price block and must match the
registry, or the build stops.

Already collected elsewhere (not refetched here): Orbit 2023, Nomad 2022, Harmony
2022, Ronin 2022, Multichain 2023 and the normal windows for OP / Base / Arbitrum
and pre-hack Orbit / Multichain, all under prototype/bridgewatch/data/.

Usage (any directory; uses the prototype's Python environment, needs httpx):
  python fetch_more.py --list
  python fetch_more.py                      # everything
  python fetch_more.py poly-2021 kelp-2026  # selected
  python fetch_more.py --rpc https://rpc.mevblocker.io,https://gateway.tenderly.co/public/mainnet

Resume-safe: finished getLogs chunks are cached under --cache-dir.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent                       # research/bridge-hacks/03-onchain-data/
PROTO = HERE.parents[2] / "prototype"
sys.path.insert(0, str(PROTO))
sys.path.insert(0, str(PROTO / "scripts"))
import fetch_datasets as fd                                    # noqa: E402
from bridgewatch.onchain import Rpc, _topic, redact            # noqa: E402

log = logging.getLogger("fetch_more")
RPCS = ("https://rpc.mevblocker.io", "https://gateway.tenderly.co/public/mainnet")

WETH_ADDR = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
ETH_USD = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
BTC_USD = "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c"
UNIV2_FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
SHIBASWAP_FACTORY = "0x115934131916C8b277DD010Ee02de363c09d037c"
KELP_LRT_ORACLE = "0x349A73444b1a310BAe67ef67973022020d70020d"   # LRTConfig(0x947c..).getContract(LRT_ORACLE)

# ---------------------------------------------------------------- tokens
# symbol -> (address, decimals, price spec)
TOKENS: dict[str, tuple[str, int, tuple]] = {
    "USDT":   ("0xdac17f958d2ee523a2206206994597c13d831ec7", 6, ("fixed", 1.0)),
    "USDC":   ("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", 6, ("fixed", 1.0)),
    "DAI":    ("0x6b175474e89094c44da98b954eedeac495271d0f", 18, ("fixed", 1.0)),
    "WBTC":   ("0x2260fac5e5542a773aa44fbcfedf7c193bc2c599", 8, ("chainlink", BTC_USD, "BTC / USD")),
    "WETH":   (WETH_ADDR, 18, ("chainlink", ETH_USD, "ETH / USD")),
    "LINK":   ("0x514910771af9ca656af840dff83e8264ecf986ca", 18, ("chainlink", "0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c", "LINK / USD")),
    "UNI":    ("0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", 18, ("chainlink", "0x553303d460EE0afB37EdFf9bE42922D8FF63220e", "UNI / USD")),
    "FEI":    ("0x956f47f50a910163d8bf957cf5846d573e7f87ca", 18, ("chainlink", "0x31e0a88fecB6eC0a411DBe0e9E76391498296EE9", "FEI / USD")),
    "TUSD":   ("0x0000000000085d4780b73119b644ae5ecd22b376", 18, ("chainlink", "0xec746eCF986E2927Abd291a2A1716c940100f8Ba", "TUSD / USD")),
    "tBTC":   ("0x18084fba666a33d37592fa2633fd49a74dd93a88", 18, ("chainlink", "0x8350b7De6a6a2C1368E7D4Bd968190e13E354297", "TBTC / USD")),
    "renBTC": ("0xeb4c2781e4eba804ce9a9803c67d0893436bb27d", 8, ("btc_proxy",)),
    "HBTC":   ("0x0316eb71485b0ab14103307bf65a021042c6d380", 18, ("btc_proxy",)),
    "SHIB":   ("0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce", 18, ("chainlink_x", "0x8dD1CD88F43aF196ae478e91b9F5E4Ac69A97C61", "SHIB / ETH", ETH_USD)),
    "rsETH":  ("0xa1290d69c65a6fe4df752f95823fae25cb99e5a7", 18, ("lrt", KELP_LRT_ORACLE)),
    "KNINE":  ("0x91fbb2503ac69702061f1ac6885759fc853e6eae", 18, ("dexv2", (UNIV2_FACTORY, SHIBASWAP_FACTORY))),
    "STC":    ("0x19ae49b9f38dd836317363839a5f6bfbfa7e319a", 9, ("dexv2", (UNIV2_FACTORY,))),
}
fd.TOKENS.update(TOKENS)    # fd.flows() looks tokens up in its own registry (address, decimals, _)

BASIC = ["USDT", "USDC", "DAI", "WBTC", "WETH"]

# ---------------------------------------------------------------- hack cases
# Every vault and first-theft tx was confirmed against >= 1 reference AND on-chain:
# the receipt of first_theft_tx shows tokens (or, where marked, native ETH) leaving
# the vault at the reported time. "anchor_block" = first theft of anything (incl.
# native ETH, which these files cannot see); first_theft_* = first TRACKED theft.
HACKS = [
    {
        "key": "poly-2021",
        "title": "Poly Network LockProxy, Ethereum, 10 Aug 2021",
        "vault": "0x250e76987d838a75310c34bf422ea9f1ac4cc906",
        "tokens": ["USDT", "USDC", "DAI", "WBTC", "WETH", "UNI", "FEI", "renBTC"],
        "anchor_block": 12_996_671,
        "end_block": 12_998_000,
        "first_theft_block": 12_996_694,
        "first_theft_tx": "0x5a8b2152ec7d5538030b53347ac82e263c58fe7455695543055a2356f3ad4998",
        "theft_min_usd": 1_000_000,
        "attacker_addresses": ["0xc8a65fadf0e0ddaf421f28feab69bf6e2e589963"],
        "references": [
            "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2021-08/PolyNetwork_exp.sol",
            "https://rekt.news/polynetwork-rekt/",
            "https://www.certik.com/resources/blog/7iLk3m8aamq1fe8rWxdrT3-poly-network-incident-analysis",
            "https://etherscan.io/tx/0xb1f70464bd95b774c6ce60fc706eb5f9e35cb5f06e6cfe7c17dcda46ffd59581",
        ],
        "notes": "Keeper swapped via EthCrossChainManager 0x838bf9e95cb12dd76a54c9f9d2e3082eaf928270 "
                 "(tx 0xb1f70464..., block 12,996,659), then forged unlocks. First theft is native: 2,857.49 ETH "
                 "left LockProxy in tx 0xad7a2c70c958fcd3effbf374d0acf3774a9257577625ae4c838e24b0de17602a "
                 "(block 12,996,671, 09:51:02 UTC). First tracked theft: 96,389,444 USDC (block 12,996,694). "
                 "Then WBTC, DAI, UNI, SHIB, renBTC, 33.4M USDT, 26,109 WETH, FEI, all to the attacker. Funds were returned.",
        "coverage": "Tracked: USDT, USDC, DAI, WBTC, WETH, UNI, FEI, renBTC. Not tracked: 2,857 native ETH (~$9M); "
                    "259.7B SHIB (no Chainlink SHIB feed existed in Aug 2021); small project tokens (MOZ, O3, STACK...). "
                    "Ethereum leg was ~$273M of the ~$611M multi-chain total.",
    },
    {
        "key": "poly-2023",
        "title": "Poly Network LockProxy, Ethereum, 1 Jul 2023 (forged cross-chain unlocks)",
        "vault": "0x250e76987d838a75310c34bf422ea9f1ac4cc906",
        "tokens": BASIC,
        "anchor_block": 17_601_076,
        "end_block": 17_602_500,
        "first_theft_block": 17_601_076,
        "first_theft_tx": "0x3a6e5d7e1b9386940b1db81d4e514cbaf5986963f3124dd7eb2a06989890f993",
        "theft_min_usd": 100_000,
        "attacker_addresses": ["0xddde20a5f569dfb11f5c405751367e939ebc5886", "0x8e0001966e6997db3e45c5f75d4c89a610255b2e",
                               "0x3def2aeee007d5ee5c62df4d34c4c49a67748929", "0xe0afadad1d93704761c8550f21a53de3468ba599"],
        "references": [
            "https://www.odaily.news/en/post/5188161",
            "https://beosin.com/resources/following-poly-network-attack-beosin-kyt-aml-keeps-tracing-",
            "https://etherscan.io/tx/0x3a6e5d7e1b9386940b1db81d4e514cbaf5986963f3124dd7eb2a06989890f993",
        ],
        "notes": "Unlocks through EthCrossChainManager 0x14413419452aaf089762a0c5e95ed2a13bbc488c: 2,651,957 USDT "
                 "(18:47:47 UTC, block 17,601,076), 3,012,146 USDC (block 17,601,077), 108,772 DAI (17,601,132), "
                 "plus dozens of project tokens to 0xe0afadad... (blocks 17,601,076-17,601,517). Odaily gives the time "
                 "in Beijing time; the on-chain block time is 2023-07-01 18:47:47 UTC.",
        "coverage": "Tracked: USDT, USDC, DAI, WBTC, WETH (~$5.77M of the stablecoins). Not tracked: ~60 project tokens "
                    "with face value far above their liquid value (FEI, sUSD, 8PAY, COW, STACK...).",
    },
    {
        "key": "heco-2023",
        "title": "HECO bridge (Ethereum vault), 22 Nov 2023",
        "vault": "0xa929022c9107643515f5c777ce9a910f0d1e490c",
        "tokens": ["USDT", "USDC", "DAI", "WBTC", "WETH", "LINK", "UNI", "TUSD", "SHIB", "HBTC"],
        "anchor_block": 18_626_540,
        "end_block": 18_628_500,
        "first_theft_block": 18_626_564,
        "first_theft_tx": "0x46f2ebab3a3195d2c790e45dfbb24bb38bb7886caafc8dfc6c844e844957b1e8",
        "theft_min_usd": 100_000,
        "attacker_addresses": ["0xfc146d1caf6ba1d1ce6dcb5b35dcbf895f50b0c4", "0x3d655889d197125fb90dcb72e4a287a8410ed1b9 (compromised operator)"],
        "references": [
            "https://www.certik.com/resources/blog/heco-bridge-exploit",
            "https://cointelegraph.com/news/heco-chain-bridge-hack-86-million-lost",
            "https://etherscan.io/tx/0x46f2ebab3a3195d2c790e45dfbb24bb38bb7886caafc8dfc6c844e844957b1e8",
        ],
        "notes": "Compromised operator 0x3d655889... called withdrawToken. First theft is native: 10,145 ETH in tx "
                 "0xbb6fe88427c2f3bc179075109d47a805dcfedab0e475eaca0d979311873e131b (block 18,626,540, 09:59:35 UTC). "
                 "First tracked theft: 42,110,000 USDT (block 18,626,564), then HBTC, SHIB, UNI, USDC, LINK, TUSD "
                 "within ~16 minutes, all to 0xfc146d1c..., amounts matching CertiK. The window ends before the "
                 "18,632,663+ transfers of the remaining tokens to 0x18709e89... (looks like an operator migration; "
                 "not labelled as theft by the references).",
        "coverage": "Tracked: USDT, USDC, DAI, WBTC, WETH, LINK, UNI, TUSD, SHIB, HBTC. Not tracked: 10,145 native ETH "
                    "(~$20M). HBTC priced at BTC/USD (it traded far below BTC by late 2023; treat its USD as an upper bound). "
                    "The HTX hot-wallet thefts the same day are a different custody and are not here.",
    },
    {
        "key": "ronin-2024",
        "title": "Ronin bridge (MainchainGatewayV3 proxy), Ethereum, 6 Aug 2024 (faulty upgrade, MEV whitehats)",
        "vault": "0x64192819ac13ef72bf6b5ae239ac672b43a9af08",
        "tokens": ["USDC", "WETH", "USDT", "DAI", "WBTC"],
        "anchor_block": 20_468_679,
        "end_block": 20_470_500,
        "first_theft_block": 20_468_848,
        "first_theft_tx": "0xbce5b8548db486c561948e8a177c8ccaa72810f972cee3909ea50af015a60ad8",
        "theft_min_usd": 1_000_000,
        "attacker_addresses": ["0x4ab12e7ce31857ee022f273e8580f73335a73c0b", "0x6980a47bee930a4584b09ee79ebe46484fbdbdd0",
                               "0x1a56abf4fe95e21c1704cbd5ffc79ea1effa3cc1", "0xfde0d1575ed8e06fbf36256bcdfa1f359281455a"],
        "references": [
            "https://threesigma.xyz/blog/ronin-network-12m-exploit-analysis",
            "https://rekt.news/roninnetwork-rektII",
            "https://etherscan.io/tx/0x2619570088683e6cc3a38d93c3d98899e5783864e15525d5f5810c11189ba6cb",
            "https://etherscan.io/tx/0xbce5b8548db486c561948e8a177c8ccaa72810f972cee3909ea50af015a60ad8",
        ],
        "notes": "Upgrade to MainchainGatewayV3 left the operator-weight threshold uninitialized. First theft is native: "
                 "3,996 ETH in tx 0x26195700... (block 20,468,679, 09:37:23 UTC) by MEV bot 0x4ab12e7c...; "
                 "first tracked theft 1,998,046.875 USDC (block 20,468,848) by 0x6980a47b.... Both were returned "
                 "(whitehat bounty).",
        "coverage": "Tracked: USDC (and WETH/USDT/DAI/WBTC, no theft). The gateway holds ETH natively, so the 3,996 ETH "
                    "(~$10M of ~$12M) is invisible here: only ~$2M of the theft is in this file.",
    },
    {
        "key": "force-bridge-2025",
        "title": "Force Bridge (Nervos), Ethereum vault, 1 Jun 2025",
        "vault": "0x63a993502e74828ddba5710327afc6dc78d661b2",
        "tokens": BASIC,
        "anchor_block": 22_608_306,
        "end_block": 22_610_000,
        "first_theft_block": 22_608_306,
        "first_theft_tx": "0x6b6fbd9d6beef56d2a4f0d14852beea381764b962d7d73ecd216b9fd991299a1",
        "theft_min_usd": 100_000,
        "attacker_addresses": ["0x1998c6d25212194ebf9bb919b87d40b2dc8aa8b9"],
        "references": [
            "https://rekt.news/force-bridge-rekt",
            "https://www.halborn.com/blog/post/explained-the-force-bridge-hack-june-2025",
            "https://www.theblock.co/post/356535/hackers-drain-over-3-million-in-crypto-from-nervos-networks-force-cross-chain-bridge-say-security-analysts",
        ],
        "notes": "Leaked validator keys (per later reports). Tx 0x6b6fbd9d... (07:16:47 UTC) took 898,485 USDC, 0.79 WBTC, "
                 "257,683 USDT, 60,403 DAI and 539.09 native ETH; tx 0x9859b6cb... (block 22,608,336) took 4.23 WBTC. "
                 "A failed attempt 0x69104f6b... (block 22,608,287) preceded it. The vault was being sunset (announced 31 May).",
        "coverage": "Tracked: USDT, USDC, DAI, WBTC, WETH. Not tracked: 539 native ETH (~$1.4M). The BSC leg is separate.",
    },
    {
        "key": "shibarium-2025",
        "title": "Shibarium bridge ERC20PredicateProxy, Ethereum, 12 Sep 2025",
        "vault": "0x6aca26bfce7675ff71c734bf26c8c0ac4039a4fa",
        "tokens": ["SHIB", "KNINE", "USDT", "USDC", "DAI", "WBTC", "WETH"],
        "anchor_block": 23_348_858,
        "end_block": 23_350_500,
        "first_theft_block": 23_348_858,
        "first_theft_tx": "0xe882a83afb92d6070b848ef025ae699ec043b7c2f31b21d2a08c94306f9b817e",
        "theft_min_usd": 10_000,
        "attacker_addresses": ["0x999e025a2a0558c07dbf7f021b2c9852b367e80a", "0xe9b854365ff0f4ce7a155f177f528cb37a737ab7"],
        "references": [
            "https://l2beat.com/scaling/projects/shibarium",
            "https://www.theblock.co/post/373368/shiba-inu-shibarium-preps-bridge-restart-plans-user-refunds-after-4-million-exploit",
            "https://forklog.com/en/news/shibarium-bridge-hacked-for-approximately-2-3-million",
        ],
        "notes": "Flash-loaned BONE stake gave 10/12 validator signatures for a malicious checkpoint. Tx 0xe882a83a... "
                 "(18:44:47 UTC) moved 92,604,600,000 SHIB from the ERC20Predicate and 224.57 native ETH from the "
                 "EtherPredicate 0xc3897302ab4b42931cb4857050fa60f53b775870; tx 0x6df7dcb5... (block 23,348,865) took "
                 "KNINE, LEASH, USDC, USDT and ~10 more tokens; more followed up to block 23,349,039.",
        "coverage": "Tracked: SHIB, KNINE, USDT, USDC, DAI, WBTC, WETH. KNINE is priced from its Uniswap-V2 WETH pair "
                    "reserves (thin-market estimate). LEASH is left out: its Transfer amounts (29,167 + 2,916 out) do not "
                    "reconcile with its balanceOf (~11,092 at start), so its accounting is non-standard. Not tracked: 224.57 native ETH (separate "
                    "EtherPredicate), BAD, ROAR, TREAT, SHIFU and other small tokens; the 4.6M BONE flash loan itself.",
    },
    {
        "key": "kelp-2026",
        "title": "KelpDAO rsETH LayerZero OFT adapter (escrow), Ethereum, 18 Apr 2026",
        "vault": "0x85d456b2dff1fd8245387c0bfb64dfb700e98ef3",
        "tokens": ["rsETH"],
        "anchor_block": 24_908_285,
        "end_block": 24_910_000,
        "first_theft_block": 24_908_285,
        "first_theft_tx": "0x1ae232da212c45f35c1525f851e4c41d529bf18af862d9ce9fd40bf709db4222",
        "theft_min_usd": 1_000_000,
        "attacker_addresses": ["0x1f4c1c2e610f089d6914c4448e6f21cb0db3adef", "0x8b1b6c9a6db1304000412dd21ae6a70a82d60d3b"],
        "references": [
            "https://blockaid.io/blog/how-a-single-layerzero-dvn-compromise-drained-292m-from-kelpdao",
            "https://www.galaxy.com/insights/research/kelpdao-layerzero-exploit-defi",
            "https://www.theblock.co/post/397988",
        ],
        "notes": "Forged LayerZero packet (1-of-1 DVN) delivered via EndpointV2 0x1a44076050125825900e736c501f859c50fe728c: "
                 "the adapter released 116,500 rsETH in one transfer (17:35:35 UTC) to 0x8b1b6c9a.... A second forged "
                 "packet (40,000 rsETH) was blocked by the pauser multisig ~46 minutes later.",
        "coverage": "Tracked: rsETH, the only token the adapter escrows. Priced at KelpDAO LRTOracle.rsETHPrice() x Chainlink "
                    "ETH/USD (no Chainlink rsETH/USD feed was found on-chain).",
    },
    {
        "key": "verus-2026",
        "title": "Verus-Ethereum bridge (delegator proxy), Ethereum, 17 May 2026",
        "vault": "0x71518580f36feceffe0721f06ba4703218cd7f63",
        "tokens": ["tBTC", "USDC", "DAI", "USDT", "WETH"],
        "anchor_block": 25_118_335,
        "end_block": 25_120_000,
        "first_theft_block": 25_118_335,
        "first_theft_tx": "0x6990f01720f57fc515d0e976a0c4f8157e0a9529194c4c15d190e98d087eb321",
        "theft_min_usd": 100_000,
        "attacker_addresses": ["0x5abb91b9c01a5ed3ae762d32b236595b459d5777", "0x65cb8b128bf6e690761044cceca422bb239c25f9"],
        "references": [
            "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2026-05/VerusBridge_exp.sol",
            "https://x.com/VerusCoin/status/2057465214975492358",
            "https://etherscan.io/tx/0x6990f01720f57fc515d0e976a0c4f8157e0a9529194c4c15d190e98d087eb321",
        ],
        "notes": "Insufficient validation in submitImports: one tx (23:55:23 UTC) released 1,625.37 native ETH, "
                 "103.5677 tBTC and 147,658.84 USDC to 0x65cb8b12....",
        "coverage": "Tracked: tBTC (Chainlink TBTC/USD), USDC, DAI, USDT, WETH: ~$8.2M of the ~$11.6M. Not tracked: 1,625 "
                    "native ETH. Ordinary traffic on this vault is very sparse (a few transfers a week).",
    },
    {
        "key": "qubit-2022",
        "title": "Qubit QBridge handler, Ethereum side, 27-28 Jan 2022 (fake deposits; theft happened on BSC)",
        "vault": "0x17b7163cf1dbd286e262ddc68b553d899b93f526",
        "tokens": BASIC,
        "anchor_block": 14_090_170,
        "end_block": 14_096_000,
        "first_theft_block": 14_090_170,
        "first_theft_tx": "0xac7292e7d0ec8ebe1c94203d190874b2aab30592327b6cc875d00f18de6f3133",
        "theft_min_usd": 100_000,
        "attacker_addresses": ["0xd01ae1a708614948b2b5e0b7ab5be6afa01325c7"],
        "references": [
            "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2022-01/Qubit_exp.sol",
            "https://rekt.news/qubit-rekt/",
            "https://medium.com/@QubitFin/protocol-exploit-report-305c34540fa3",
        ],
        "notes": "NEGATIVE CONTROL. The attacker called QBridge.deposit (0x20e5e35b...) with a resourceID whose token was "
                 "address(0); safeTransferFrom on address(0) did not revert, so a 'deposit' of 190 ETH was emitted with "
                 "no tokens moving. The BSC side then minted ~$80M of qXETH. first_theft_tx is that fake deposit: "
                 "it moves NO tokens on Ethereum, so this vault shows no anomalous outflow at all.",
        "coverage": "Tracked: USDT, USDC, DAI, WBTC, WETH. The handler held ~199.4 native ETH and none of these tokens, so the "
                    "file has ZERO transfers: nothing was stolen from this Ethereum vault and the replay is expected to find "
                    "no thefts. Kept to document what an Ethereum-vault monitor cannot see.",
    },
    {
        "key": "xbridge-2024",
        "title": "XBridge, Ethereum, 24 Apr 2024 (listToken logic flaw)",
        "vault": "0x47ddb6a433b76117a98fbeab5320d8b67d468e31",
        "tokens": ["STC", "USDT", "USDC", "WETH"],
        "anchor_block": 19_723_706,
        "end_block": 19_725_000,
        "first_theft_block": 19_723_706,
        "first_theft_tx": "0x903d88a92cbc0165a7f662305ac1bff97430dbcccaa0fe71e101e18aa9109c92",
        "theft_min_usd": 50_000,
        "attacker_addresses": ["0x0cfc28d16d07219249c6d6d6ae24e7132ee4caa7"],
        "references": [
            "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2024-04/XBridge_exp.sol",
            "https://twitter.com/CyversAlerts/status/1783045506471432610",
        ],
        "notes": "Attacker re-listed STC (tx 0xe09d350d...) then withdrew 482,589,887 STC (block 19,723,706), "
                 "1,372,522,851 SRLTY (19,723,805) and 18,450,672 Mazi (19,723,925).",
        "coverage": "Tracked: STC (priced from its Uniswap-V2 WETH pair: thin-market estimate), USDT, USDC, WETH. Not "
                    "tracked: SRLTY (no V2 pair) and Mazi (empty pair) - no defensible price. Small case (~$0.8M tracked).",
    },
]

# ---------------------------------------------------------------- normal / stress-normal
LIVE_END = 26_140_000          # same fixed end block as the prototype's live-bridge normal windows (~5 Oct 2026)
NORMAL = [
    {"key": "wormhole-portal-30d", "title": "Wormhole Portal token bridge, 30 believed-normal days",
     "vault": "0x3ee18b2214aff97000d974cf647e7c347e8fa585", "tokens": BASIC, "end_block": LIVE_END, "days": 30,
     "references": ["https://wormhole.com/docs/reference/contract-addresses/"]},
    {"key": "polygon-pos-erc20-30d", "title": "Polygon PoS ERC20PredicateProxy, 30 believed-normal days",
     "vault": "0x40ec5b33f54e0e8a33a975908c5ba1c14e5bbbdf", "tokens": BASIC, "end_block": LIVE_END, "days": 30,
     "references": ["https://static.polygon.technology/network/mainnet/v1/index.json"]},
    {"key": "usdt0-oft-adapter-30d", "title": "USDT0 OFT adapter (LayerZero lockbox for USDT), 30 believed-normal days",
     "vault": "0x6c96de32cea08842dcc4058c14d3aaad7fa41dee", "tokens": ["USDT"], "end_block": LIVE_END, "days": 30,
     "references": ["https://docs.usdt0.to/technical-documentation/developer"]},
    {"key": "stargate-v2-usdc-30d", "title": "Stargate V2 USDC pool (StargatePoolUSDC), 30 believed-normal days",
     "vault": "0xc026395860db2d07ee33e05fe50ed7bd583189c7", "tokens": ["USDC"], "end_block": LIVE_END, "days": 30,
     "references": ["https://stargateprotocol.gitbook.io/stargate/v2-developer-docs/technical-reference/mainnet-contracts"]},
    {"key": "celer-cbridge-30d", "title": "Celer cBridge pool-based Bridge, 30 believed-normal days",
     "vault": "0x5427fefa711eff984124bfbb1ab6fbf5e3da1820", "tokens": ["USDT", "USDC", "WETH"], "end_block": LIVE_END, "days": 30,
     "references": ["https://cbridge-docs.celer.network/reference/contract-addresses"]},
    # Across is busy (~21k tracked transfers/day; 30 days = 621k rows, 33 MB gzipped), so only 7 days.
    {"key": "across-spokepool-7d", "title": "Across Ethereum SpokePool, 7 believed-normal days (shortened: ~21k transfers/day)",
     "vault": "0x5c7bcd6e7de5423a257d81b442095a1a6ced35c5", "tokens": BASIC, "end_block": LIVE_END, "days": 7,
     "references": ["https://docs.across.to/reference/contract-addresses/mainnet-chain-id-1"]},
    {"key": "ronin-gateway-30d", "title": "Ronin bridge MainchainGatewayV3 proxy, 30 believed-normal days (2026)",
     "vault": "0x64192819ac13ef72bf6b5ae239ac672b43a9af08", "tokens": ["USDC", "WETH"], "end_block": LIVE_END, "days": 30,
     "references": ["https://threesigma.xyz/blog/ronin-network-12m-exploit-analysis (same proxy)"]},
    {"key": "kelp-rseth-adapter-prehack-30d", "title": "KelpDAO rsETH OFT adapter, 30 believed-normal days (Mar 2026, before the Apr 2026 hack)",
     "vault": "0x85d456b2dff1fd8245387c0bfb64dfb700e98ef3", "tokens": ["rsETH"], "end_date": "2026-04-01T00:00", "days": 30,
     "references": ["https://blockaid.io/blog/how-a-single-layerzero-dvn-compromise-drained-292m-from-kelpdao (same adapter)"]},
    # stress-normal: turbulent markets, no incident on the vault
    {"key": "polygon-pos-erc20-usdc-depeg-2023", "stress": True,
     "title": "Polygon PoS ERC20PredicateProxy, 30 days around the USDC depeg (24 Feb - 26 Mar 2023; SVB weekend 10-13 Mar)",
     "vault": "0x40ec5b33f54e0e8a33a975908c5ba1c14e5bbbdf", "tokens": BASIC, "end_date": "2023-03-26T00:00", "days": 30,
     "references": ["https://static.polygon.technology/network/mainnet/v1/index.json",
                    "https://www.circle.com/blog/an-update-on-usdc-and-silicon-valley-bank"]},
    {"key": "wormhole-portal-ftx-2022", "stress": True,
     "title": "Wormhole Portal token bridge, 30 days around the FTX collapse (25 Oct - 24 Nov 2022)",
     "vault": "0x3ee18b2214aff97000d974cf647e7c347e8fa585", "tokens": BASIC, "end_date": "2022-11-24T00:00", "days": 30,
     "references": ["https://wormhole.com/docs/reference/contract-addresses/"]},
]
STRESS_NOTE = ("stress-normal: no known incident on this vault, but a turbulent market window (depeg / exchange collapse), "
               "the hardest false-alarm test")


# ---------------------------------------------------------------- prices
def _call(rpc: Rpc, to: str, data: str, block: int) -> str:
    return rpc.call("eth_call", [{"to": to, "data": data}, hex(block)])


def onchain_decimals(rpc: Rpc, symbol: str, block: int) -> int:
    addr, dec, _ = TOKENS[symbol]
    got = int(_call(rpc, addr, "0x313ce567", block), 16)
    if got != dec:
        raise RuntimeError(f"{symbol} {addr}: decimals() = {got}, registry says {dec}")
    return got


def _chainlink(rpc: Rpc, feed: str, expect: str, block: int) -> float:
    desc, px = rpc.chainlink_price(feed, block)
    if desc != expect:
        raise RuntimeError(f"Chainlink feed {feed} describes itself as {desc!r}, expected {expect!r}")
    return px


def _dexv2_eth(rpc: Rpc, token: str, dec: int, factories: tuple, block: int) -> tuple[float, str]:
    """Price in ETH from the listed V2 factories' token/WETH pair with the most WETH in it."""
    best = None
    for f in factories:
        pair = "0x" + _call(rpc, f, "0xe6a43905" + _topic(token)[2:] + _topic(WETH_ADDR)[2:], block)[-40:]
        if int(pair, 16) == 0:
            continue
        r = _call(rpc, pair, "0x0902f1ac", block)
        r0, r1 = int(r[2:66], 16), int(r[66:130], 16)
        t0 = "0x" + _call(rpc, pair, "0x0dfe1681", block)[-40:]
        rt, rw = (r0, r1) if t0 == token.lower() else (r1, r0)
        if rt and (best is None or rw > best[1]):
            best = ((rw / 1e18) / (rt / 10 ** dec), rw, pair)
    if best is None:
        raise RuntimeError(f"no V2 WETH pair with reserves for {token}")
    return best[0], f"pair {best[2]} ({best[1] / 1e18:,.1f} WETH reserve)"


def prices_at(rpc: Rpc, symbols: list[str], block: int) -> tuple[dict, list[str]]:
    prices, notes = {}, []
    eth = _chainlink(rpc, ETH_USD, "ETH / USD", block)
    btc = _chainlink(rpc, BTC_USD, "BTC / USD", block)
    for s in symbols:
        addr, dec, spec = TOKENS[s]
        kind = spec[0]
        if kind == "fixed":
            prices[s] = spec[1]
            notes.append(f"{s} fixed ${spec[1]:g}")
        elif kind == "chainlink":
            prices[s] = _chainlink(rpc, spec[1], spec[2], block)
            notes.append(f"{s} at Chainlink {spec[2]} {prices[s]:,.6g}")
        elif kind == "chainlink_x":
            x = _chainlink(rpc, spec[1], spec[2], block)
            prices[s] = x * eth
            notes.append(f"{s} at Chainlink {spec[2]} {x:.6g} x ETH/USD {eth:,.2f}")
        elif kind == "btc_proxy":
            prices[s] = btc
            notes.append(f"{s} ASSUMED = Chainlink BTC/USD {btc:,.2f} (no own feed; BTC-pegged wrapper, upper bound)")
        elif kind == "lrt":
            rate = int(_call(rpc, spec[1], "0xb4b46434", block), 16) / 1e18     # rsETHPrice()
            prices[s] = rate * eth
            notes.append(f"{s} at KelpDAO LRTOracle {spec[1]} rsETHPrice {rate:.6f} ETH x ETH/USD {eth:,.2f}")
        elif kind == "dexv2":
            px_eth, where = _dexv2_eth(rpc, addr, dec, spec[1], block)
            prices[s] = px_eth * eth
            notes.append(f"{s} ESTIMATE from V2 {where}: {px_eth:.6g} ETH x ETH/USD {eth:,.2f} = ${prices[s]:.6g}")
        else:
            raise ValueError(kind)
    return prices, notes


# ---------------------------------------------------------------- build
def build(rpc: Rpc, cache: fd.ChunkCache, spec: dict, start: int, end: int, price_block: int, period: str) -> dict:
    symbols = spec["tokens"]
    decs = {s: onchain_decimals(rpc, s, price_block) for s in symbols}
    prices, pnotes = prices_at(rpc, symbols, price_block)
    balances = {s: rpc.balance_of(TOKENS[s][0], spec["vault"], start) / 10 ** decs[s] for s in symbols}
    rows = fd.flows(rpc, cache, spec["vault"], symbols, prices, start, end, spec.get("chunk", 20_000))
    case = {"key": spec["key"], "title": spec["title"], "chain": "ethereum", "vault": spec["vault"],
            "tokens": [[TOKENS[s][0], s, decs[s]] for s in symbols],
            "start_block": start, "end_block": end, "price_block": price_block, "period": period,
            "eth_usd_feed": ETH_USD, "btc_usd_feed": BTC_USD}
    if "anchor_block" in spec:
        case["hack_window"] = [spec["anchor_block"], end]
        case["first_theft_any_block"] = spec["anchor_block"]
    for k in ("first_theft_tx", "first_theft_block", "theft_min_usd", "attacker_addresses",
              "references", "notes", "coverage"):
        if k in spec:
            case[k] = spec[k]
    case.setdefault("coverage", "Tracked tokens: " + ", ".join(symbols) + ". Native ETH is not visible in token logs.")
    return {
        "case": case,
        "fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "source": "Ethereum mainnet via public JSON-RPC (" + ", ".join(redact(u) for u in rpc.urls) + "); "
                  "built by research/bridge-hacks/03-onchain-data/fetch_more.py",
        "prices_usd": prices,
        "price_note": "; ".join(pnotes) + f" (answers at block {price_block}). Native ETH is not included except "
                      "where it passed through WETH (rows with kind weth_wrap / weth_unwrap).",
        "start_ts": rpc.block_time(start),
        "end_ts": rpc.block_time(end),
        "balances_at_start": balances,
        "transfers": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keys", nargs="*", help="dataset keys (default: all)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--rpc", default=",".join(RPCS), help="comma-separated archive-capable endpoints, tried in order")
    ap.add_argument("--days", type=float, default=14, help="baseline days before a hack's first theft")
    ap.add_argument("--cache-dir", default=str(Path(tempfile.gettempdir()) / "bridgewatch-fetch-more-cache"))
    ap.add_argument("--out-dir", default=str(HERE))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    every = {c["key"]: ("hack", c) for c in HACKS} | {c["key"]: ("normal", c) for c in NORMAL}
    if args.list:
        for k, (kind, c) in every.items():
            print(f"{k:36} {'stress' if c.get('stress') else kind:7} {c['title']}")
        return
    rpc = Rpc(tuple(u.strip() for u in args.rpc.split(",") if u.strip()), timeout=120, pause=0.15)
    out = Path(args.out_dir)
    for key in args.keys or list(every):
        kind, spec = every[key]
        log.info("== %s", key)
        cache = fd.ChunkCache(Path(args.cache_dir) / key)
        if kind == "hack":
            anchor = spec["anchor_block"]
            start = fd.block_at(rpc, rpc.block_time(anchor) - int(args.days * 86_400), anchor - 200_000, anchor)
            data = build(rpc, cache, spec, start, spec["end_block"], anchor,
                         "hack: baseline before the incident, then the drain")
            path = fd.write(out / "hacks" / f"{key}.json", data)
        else:
            if "end_date" in spec:
                ts = int(dt.datetime.fromisoformat(spec["end_date"]).replace(tzinfo=dt.timezone.utc).timestamp())
                end = fd.block_at(rpc, ts)
            else:
                end = spec["end_block"]
            start = fd.block_at(rpc, rpc.block_time(end) - spec["days"] * 86_400, end - 400_000, end)
            period = STRESS_NOTE if spec.get("stress") else "believed-normal: no known incident on this vault in this window"
            data = build(rpc, cache, spec, start, end, end, period)
            path = fd.write(out / "normal" / f"{key}.json", data)
        log.info("   wrote %s (%d bytes): %s", path, path.stat().st_size, fd.summary(data))
    log.info("RPC calls %d, errors %d", rpc.calls, rpc.errors)


if __name__ == "__main__":
    main()
