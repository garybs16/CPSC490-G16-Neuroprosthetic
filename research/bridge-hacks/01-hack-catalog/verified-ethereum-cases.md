> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Verified first-theft cases (for the on-chain data agent)

How these were verified (2026-10-07): each tx hash comes from a public post-mortem (rekt.news, DeFiHackLabs, Blockaid, or a project report). Its block number, UTC timestamp, sender/receiver and ERC-20 Transfer logs were then re-read from public JSON-RPC nodes (1rpc.io, cloudflare-eth, rpc.mevblocker.io, BSC/Base/Arbitrum public RPCs). "vault" is the contract or address that the transfers in that tx came from, or that emitted the release event.

Caveats:
- "first_theft" means the earliest theft tx that we could confirm. Where a source says it is only an example tx, the notes say so.
- `ETH` means native ether (an internal transfer, or a WETH unwrap inside the tx).
- Rows on non-Ethereum chains are listed separately at the end.

```
name | chain | vault | tokens | first_theft_block | first_theft_tx
ChainSwap-1 (2021-07) | ethereum | 0x7fe68fc06e1a870dcbee0acae8720396dc12fc86 | 0xad4f86a25bbc20ffb751f2fac312a0b4d8f88c64 | 12751488 | 0x5c5688a9f981a07ed509481352f12f22a4bd7cea46a932c6d6bbe67cca3c54be
THORChain-2 (2021-07) | ethereum | 0xf56cba49337a624e94042e325ad6bc864436e370 | ALCX,XRUNE,USDC,SUSHI,YFI,USDT | 12878653 | 0x10352e6ec052771a92f05f93e037e066873f64bb502d4488726697987f054595
Poly Network (2021-08) | ethereum | 0x250e76987d838a75310c34bf422ea9f1ac4cc906 | ETH,USDC,WBTC,DAI,UNI,SHIB,renBTC,USDT,WETH,FEI | 12996671 | 0xad7a2c70c958fcd3effbf374d0acf3774a9257577625ae4c838e24b0de17602a
Multichain approvals (2022-01) | ethereum | n/a (user allowances to router 0x6b7a87899490ece95443e979ca9485cbe7e71522 lineage; vault not drained) | WETH | 14037237 | 0xe50ed602bd916fc304d53c4fed236698b71691a95774ff0aeeb74b699c6227f7
Qubit (2022-01) | ethereum | 0x20e5e35ba29dc3b540a1aee781d0814d5c77bce6 | none on ETH (zero-value deposit; theft on BSC) | 14090170 | 0xac7292e7d0ec8ebe1c94203d190874b2aab30592327b6cc875d00f18de6f3133
Wormhole (2022-02) | ethereum | 0x3ee18b2214aff97000d974cf647e7c347e8fa585 | WETH/ETH | 14128223 | 0x4d5201dd4a377f20e61fb8f42e6f929ec16bcec918f0584e39241d15b254a80f
LI.FI (2022-03) | ethereum | n/a (user allowances to 0x5a9fd7c39a6c488e715437d7b1f3c823d5596ed1; vault not drained) | USDT,USDC,MATIC,others | 14420687 | 0x4b4143cbe7f5475029cf23d6dcbb56856366d91794426f2e33819b9b1aac4e96
Ronin (2022-03) | ethereum | 0x1a2a1c938ce3ec39b6d47113c7955baa9dd454f2 | WETH/ETH,USDC | 14442835 | 0xc28fad5e8d5e0ce6a2eaf67b6687be5d58113e16be590824d6cfa1a94467d0b7
Harmony Horizon (2022-06) | ethereum | 0xf9fb1c508ff49f78b60d3a96dea99fa5d7f3a8a6;0xfd53b1b4af84d59b20bf2c20ca89a6beeaa2c628;0x2dccdb493827e15a5dc8f8b72147e6c4a5620857 | ETH,BUSD,ERC20s | 15012646 | 0x27981c7289c372e601c9475e5b5466310be18ed10b59d1ac840145f6e7804c97
Nomad (2022-08) | ethereum | 0x88a69b4e698a4b090df6cf5bd7b2d47325ad30a3 | WBTC,WETH,USDC,USDT,DAI,others | 15259101 | 0xb1fe26cc8892f58eb468f5208baaf38bac422b5752cca0b9c8a871855d63ae28
Rubic (2022-12) | ethereum | n/a (user allowances; vault not drained) | USDC | 16260581 | 0x9a97d85642f956ad7a6b852cf7bed6f9669e2c2815f3279855acf7f1328e7d46
Multichain Fantom bridge (2023-07) | ethereum | 0xc564ee9f21ed8a2d8e7e76c085740d5e4c5fafbe | USDC,WBTC,WETH,DAI,LINK,USDT,CRV,YFI,TUSD,others | 17635954 | 0xde3eed5656263b85d43a89f1d2f6af8fde0d93e49f4642053164d773507323f8
HECO bridge (2023-11) | ethereum | 0xa929022c9107643515f5c777ce9a910f0d1e490c | USDT,ETH,HBTC,SHIB,UNI,USDC,LINK,TUSD | 18626540 | 0xbb6fe88427c2f3bc179075109d47a805dcfedab0e475eaca0d979311873e131b
Orbit Bridge (2023-12) | ethereum | 0x1bf68a9d1eaee7826b3593c20a0ca93293cb489a | DAI,WBTC,ETH,USDC,USDT | 18908035 | 0xafdc36278fcef8d54824b09ec019147cfe2afd995abf6754e52d273a2c1b07ca
Socket/Bungee (2024-01) | ethereum | n/a (user allowances to gateway 0x3a23f943181408eac424116af7b7790c94cb97a5; gateway not drained) | USDC,WETH,WBTC,DAI,MATIC | 19021454 | 0xc6c3331fa8c2d30e1ef208424c08c039a89e510df2fb6ae31e5aa40722e28fd6
XBridge (2024-04) | ethereum | 0x47ddb6a433b76117a98fbeab5320d8b67d468e31 | STC,SRLTY,Mazi,others | 19723706 | 0x903d88a92cbc0165a7f662305ac1bff97430dbcccaa0fe71e101e18aa9109c92
LI.FI (2024-07) | ethereum | n/a (user allowances to LiFiDiamond 0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae) | USDT,USDC,DAI | 20318963 | 0xd82fe84e63b1aa52e1ce540582ee0895ba4a71ec5e7a632a3faa1aff3e763873
Ronin (2024-08) | ethereum | 0x64192819ac13ef72bf6b5ae239ac672b43a9af08 | ETH,USDC | 20468679 | 0x2619570088683e6cc3a38d93c3d98899e5783864e15525d5f5810c11189ba6cb
Force Bridge (2025-06) | ethereum | 0x63a993502e74828ddba5710327afc6dc78d661b2 | USDC,WBTC,USDT,DAI,ETH | 22608306 | 0x6b6fbd9d6beef56d2a4f0d14852beea381764b962d7d73ecd216b9fd991299a1
Anyswap legacy router permit (2025-07) | ethereum | n/a (user allowance to router 0x6b7a87899490ece95443e979ca9485cbe7e71522) | WETH | 23026900 | 0xae79fdcfd7c36ed654d11b352b495340bd3cc47d0849c35ac6ffa1e4859098ec
Shibarium bridge (2025-09) | ethereum | 0x6aca26bfce7675ff71c734bf26c8c0ac4039a4fa | SHIB,KNINE,LEASH,ROAR,TREAT,USDC,USDT,others; WETH | 23348858 | 0xe882a83afb92d6070b848ef025ae699ec043b7c2f31b21d2a08c94306f9b817e
IoTeX ioTube (2026-02) | ethereum | 0xc2e0f31d739cb3153ba5760a203b3bd7c27f0d7a | USDT,USDC,WETH,WBTC,DAI,PAXG,IOTX,BUSD,UNI | 24501938 | 0x1b5772b2a0e1f71327e227ed4ff3ef9fbdc63a47cc8a7fb8995aab41dc7d7c3d
Hyperbridge (2026-04) | ethereum | 0xfd413e3afe560182c4471f4d143a96d3e259b6de | WETH (TokenGateway); bridged DOT 0x8d010bf9c26881788b4e6bf5fd1bdc358c8f90b8 minted | 24868029 | 0xeff151ef58d57d6523874a7b97344fcd1ce3c7c6880cfc26a93da17f82062d59
KelpDAO rsETH (2026-04) | ethereum | 0x85d456b2dff1fd8245387c0bfb64dfb700e98ef3 | rsETH 0xa1290d69c65a6fe4df752f95823fae25cb99e5a7 | 24908285 | 0x1ae232da212c45f35c1525f851e4c41d529bf18af862d9ce9fd40bf709db4222
Adshares (2026-05) | ethereum | n/a (unbacked mint of wADS 0xcfcecfe2bd2fed07a9145222e8a7ad9cf1ccd22a) | wADS | 25102963 | 0x8844b4ec371c4b13d7fac701b5d546a7c2fba12621a9596dd14b662b14408789
Verus-Ethereum (2026-05) | ethereum | 0x71518580f36feceffe0721f06ba4703218cd7f63 | ETH,tBTC,USDC | 25118335 | 0x6990f01720f57fc515d0e976a0c4f8157e0a9529194c4c15d190e98d087eb321
MAP Protocol (2026-05) | ethereum | n/a (unbacked mint of MAPO 0x66d79b8f60ec93bfce0b56f5ac14a2714e509a99) | MAPO | 25137572 | 0x31e56b4737649e0acdb0ebb4eca44d16aeca25f60c022cbde85f092bde27664a
Gravity Bridge (2026-05) | ethereum | 0xa4108aa1ec4967f8b52220a4f7e94a8201f2d906 | USDC,USDT,WETH,PAXG | 25205201 | 0xfce883a8f9a4f3479cce1368b99287973ab40451ac092f5a41e1e09eecab5044
Aztec Connect (2026-06) | ethereum | 0xff1f2b4adb9df6fc8eafecdcbf96a2b351680455 | ETH,DAI,wstETH,yvDAI,yvWETH,LUSD,yvLUSD | 25315715 | 0x074ec9317d8336db37e8c348fbdd7515573ff4088239c77ab429f522509aeeb1
Verus-Ethereum (2026-07) | ethereum | 0x71518580f36feceffe0721f06ba4703218cd7f63 | ETH,tBTC,USDC,USDT,MKR,EURC,scrvUSD; DAI minted | 25592836 | 0xa1f1e65c1cea4dba4ae439cd4dcdba6cc2dbda0ed1228e61f29ae9c9324eb099
```

## Non-Ethereum verified rows (same method)

```
name | chain | vault | tokens | first_theft_block | first_theft_tx
ChainSwap-2 (2021-07) | bsc | unknown (unbacked mint) | WILD and ~20 tokens | 9042275 | 0x83b4adaf73ad34c5c53aa9b805579ed74bc1391c5297201e6457cde709dff723
Qubit (2022-01) | bsc | unknown (QBridge handler; qXETH minted) | qXETH -> BNB | 14742312 | 0x50946e3e4ccb7d39f3512b7ecb75df66e6868b9af0eee8a7e4b61ef8a459518e
BNB Token Hub (2022-10) | bsc | 0x0000000000000000000000000000000000002000 (cross-chain system contract; BNB minted, no vault) | BNB | 21957793 | 0xebf83628ba893d35b496121fb8201666b8e09f3cbadf0e269162baa72efe3b8b
Allbridge Core (2023-04) | bsc | pool contracts (address unknown) | BUSD,USDT | 26982068 | 0x7ff1364c3b3b296b411965339ed956da5d17058f3164425ce800d64f1aef8210
Force Bridge (2025-06) | bsc | 0x8215c949f2025b84629041903ade8394f0a080c6 | BEP20s | 50679681 | 0x4c7e83126e9327fe62cb8e3dab72121062eaf213852fd581e7ada43c93ea58a4
AFX bridge (2026-07) | arbitrum | 0xcb3b9a3e5668afe84dc7a864b36b845dce062e67 | USDC 0xaf88d065e77c8cc2239327c5edb3a432268e5831 | 486658838 | 0x50d0b3ec6c3f5fce0f10abf81540bbb508f421494aa2b3480c4a264b0436547b
Allbridge CCTP router (2026-08) | base | router (address unknown) | USDC | 50157345 | 0x9f906fcd8fceaa6745e8d1c004861dcfa9b5e6a893fe1e8c5d0013a4e982e6a8
```

## Useful context transactions (not thefts)

| Incident | What | Block | Tx |
|---|---|---|---|
| Poly Network 2021 | keeper public-key replacement (admin/validator-set change), 09:48:40 UTC | 12996659 | 0xb1f70464bd95b774c6ce60fc706eb5f9e35cb5f06e6cfe7c17dcda46ffd59581 |
| Nomad 2022 | faulty Replica initialisation, 2022-06-21 13:15:16 UTC (41 days before) | 15002481 | 0x53fd92771d2084a9bf39a6477015ef53b7f116c79d98a21be723d06d79024cad |
| Orbit 2023 | last theft 21:25:35 UTC | 18908123 | 0xd8ca42941a0a2c25669267ad8d61f7f9f4118252cb502316602fe16624b80ac8 |
| Orbit 2023 | bridge deactivated 22:21:35 UTC | 18908403 | 0xedfcdeb97c57a106067315afd364af361b20f0cf1a10070db57241a5e11913f4 |
| Multichain 2023 | first large drain (27.65M USDC) 18:10:35 UTC | 17636491 | 0xbd29fe07555c28527fb0207aa0ac2b67d4afef0426793c35b76d005613477fc4 |
| Socket 2024 | route added (3 days before) | 18996162 | 0x1df44e224c7a715da25fa33dcad2ca3a930d1a4dafd263e61c07b52673d505f4 |
| Socket 2024 | patch 19:25:47 UTC (14 min after) | 19021526 | 0xac75adcc1cb3fef158c4f200c48fcbcbb9b6ce3250bdf3751d6231d41a9e604b |
| Ronin 2024 | proxy upgrade, 08:48:47 UTC (~49 min before) | 20468438 | 0x855dd3b1194e3b889f4667b6a0996220e350e034d35d3eab29b4f23bc205767e |
| IoTeX 2026 | Validator ownership transfer 01:07:35 UTC | 24501847 | 0xe9e7f33ebfe2230c147e6e0321f5f2c7de1b89fe9fc08830fc3f8ac5845bc9f0 |
| IoTeX 2026 | Validator upgrade 01:20:35 UTC | 24501912 | 0xc9c53b28a2aec4f8641394d2ba086a4d0b0a93e40d0a86c578c7fc20ab6351b8 |
| Hyperbridge 2026 | bridged-DOT mint 03:55:23 UTC | 24868295 | 0x240aeb9a8b2aabf64ed8e1e480d3e7be140cf530dc1e5606cb16671029401109 |
| KelpDAO 2026 | emergency pause 18:21:59 UTC (46 min after) | 24908516 | 0x4f52256ab6c8ab95d30cf994e0264f1de27e089764bb011824d5ddd47d9a1698 |
| Gravity 2026 | last drain (USDT) 02:31:11 UTC | 25205217 | 0x469274f4edd45ec3284bf60de8eb30086222745f8f8c8b6a955137feed41281d |
| AFX 2026 (arbitrum) | withdrawal request 21:26:55 UTC (200 s dispute window) | 486657995 | 0x217c45c1272550e0439e53243f2987b7fb3f58b1d33c222597bbb71851b93f74 |
