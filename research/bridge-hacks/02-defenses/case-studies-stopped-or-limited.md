# Case studies: losses stopped or limited, and monitors that fired without a response

> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

Research date: 2026-10-07. All times are UTC unless noted. Amounts are as reported at the time, and sources often disagree, so ranges are given. Source keys refer to `sources.md`.

## Part A: Detection, pausing or limits reduced the loss

### A1. Ronin bridge, 2024-08-06: a withdrawal cap held the loss to about $12M
- **Cause.** An upgrade at 08:48:47 left operator weight at 0, so any signature passed [RN2].
- **Attack.** The first exploit tx came at 09:37:23. MEV bots acting as whitehats took about 3,996 ETH and about 2M USDC [RN2].
- **Limit.** These were the most the bridge allowed per withdrawal [RN1]. A third-party analysis says the cap prevented about $72M of extra loss [RN3].
- **Pause.** At 10:15:23, **38 minutes** after the exploit [RN2]. Funds were returned for a $500K bounty [RN1].
- **Lesson.** A hard per-transaction or daily cap bought the time a human pause needed. A detector would have had two warnings: the upgrade event 48 minutes before the exploit, and a withdrawal sitting exactly at the cap.

### A2. KelpDAO rsETH (LayerZero), 2026-04-18: pause blocked about $100M of follow-up drains
- **17:35:** A forged LayerZero packet (claiming Unichain origin) released 116,500 rsETH (about $292M) [KD2]. The cause was a 1-of-1 DVN fed by poisoned RPC nodes. The poisoned nodes showed **correct data to monitoring tools** while forging data for the DVN [KD3].
- **About 18:21:** Kelp's emergency pauser multisig called `pauseAll`, **46 minutes** after the drain [KD1][KD2].
- **18:26 and 18:28:** Two transactions replaying the same packet for about 40,000 rsETH (about $100M) **reverted** [KD1].
  - Cyvers' CTO said Kelp was 3 minutes from losing that $100M and credited a blacklist [C5]. Other outlets credit the pause [KD1].
  - Some commentary puts the amount saved at about $200M; I could not verify that [KU1].
- **18:52:** Aave's guardian froze rsETH markets, 77 minutes after the drain [KD2].
- **About 2026-04-22:** The Arbitrum Security Council recovered 30,766 ETH [KD2].
- **Lesson.**
  - The first transaction was unstoppable. Pausing saved the *repeat* attempts, with only about 5 minutes of margin.
  - A BridgeWatch page with a sub-5-minute pipeline would have been useful mainly for **downstream** actors (Aave froze 77 minutes after the drain).
  - It is also a warning that **monitor inputs can be poisoned**: use independent RPC providers (T14).

### A3. BNB Chain Token Hub, 2022-10-06: chain halt stranded most of the minted BNB
- **Attack.** A forged IAVL proof minted 2M BNB (about $566–586M) [BN1][BN2].
- **Response.** All 44 validators halted BSC. Only about $100–137M left for other chains; the rest stayed frozen on BSC [BN1][BN2].
- **Lesson.** Freezing at the chain level works only where validators are few and coordinated. It is still the largest "limited" outcome on record.

### A4. Wormhole, 2022-02-02: fast loss, but the team noticed in about 43 minutes
- **Timeline.** Prep at 17:58. Mint of 120k wETH at 18:24. Most of it swapped or bridged by 18:34. Imbalance noticed at 19:07. Network shut down at 19:33 [W3].
- **Outcome.** Nothing was saved by the halt; Jump replaced 120k ETH [W3].
- **Lesson.** This is the case that motivated the Governor [W1]. A T1/T2 invariant would have fired at 18:24, but the main outflow finished within about 10 minutes.

### A5. Synapse nUSD pool, 2021-11: stopped before loss
- **Event.** An attempted drain of about $8M on Avalanche.
- **Response.** Validators saw unusual activity, paused all chains and reversed the transaction before confirmation. LPs were made whole [SY1].
- **Lesson.** Validator-based bridges that require off-chain confirmation can act as a human or automatic gate.

### A6. Shibarium bridge, 2025-09: partial containment
- **Attack.** Flash-loaned BONE stake gave the attacker 10 of 12 validator signatures. A fraudulent checkpoint drained 224.57 ETH and 92.6B SHIB [SH1].
- **Response.**
  - Staking and unstaking were paused; funds moved to a 6-of-9 multisig.
  - K9 Finance blacklisted 248B KNINE after the attacker's sales failed.
  - About $1M was "neutralized" [SH1].
- **Lesson.** A token issuer's **blacklist** is a fast downstream lever, so alerts should name affected tokens and issuers.

### A7. Socket/Bungee, 2024-01-16: about 1 hour to pause, then recovery
- **Attack.** An input-validation flaw in a newly added route drained users with infinite approvals: about $3.3M from 231 wallets [SO1].
- **Response.** A community researcher flagged it about 1 hour before Socket's pause notice (15:15 ET). Socket later recovered 1,032 ETH (about $2.3M) [SO1].

### A8. Multichain, 2023-07-06: freezes after the fact
- **Attack.**
  - 16:21: a $2 test withdrawal [MC1].
  - About 2 hours later: the main drain (about $126–130M) [MC1][MC2].
  - Cyvers says it flagged the test transactions [C1].
- **Response.** Multichain could not pause, because MPC keys were in an unknown party's hands. **Circle froze about $65M USDC** and Tether froze $2.5M [MC2].
- **Lesson.** Stablecoin issuers are the fallback "pause". An alert listing USDC/USDT amounts and addresses lets someone ask for a freeze quickly.

### A9. Hyperbridge, 2026-04-13: low liquidity capped realized loss
- **Attack.** 1B bridged DOT minted, but only about $237K could be sold. Total loss was later revised to about $2.5M [HB1][R1].
- **Lesson.** Thin liquidity acted as an accidental "rate limit".
- **See also B2** below: the detection-to-freeze gap.

## Part B: Monitors fired (or could have) but humans did not act in time

### B1. Ronin, 2022-03-23: about 6 days unnoticed
- Forta's retrospective shows a high-gas alert at 13:46:46 on attack day and a high-value alert minutes later [F6].
- Discovery came only on 03-29, when a user could not withdraw 5,000 ETH [F6][P3]. Deposits made during those 6 days were put at risk [F6].
- **Lesson.** Alerts that are "fairly noisy overall" (Forta's words) do not get acted on. Precision is what gets alerts read.

### B2. Hyperbridge, 2026-04-13: the main mint was flagged within the minute; freeze came 70+ minutes later
- Hypernative says it flagged the deployer and test transaction about 15 minutes early, and the main exploit at 03:55:23 [H2]. Note: the catalog records an earlier first theft (about 245 WETH from the TokenGateway at 03:02:11 UTC), so measured from the first theft, detection came about 53 minutes later; "same minute" holds only relative to the 03:55 mint.
- The attacker kept exploiting other tokens at 04:20, 04:26, 04:33, 04:51 and 05:07 before the freeze [H2].
- **Lesson.** **Detection without a wired-in response path left about 70 minutes of follow-on exploitation open.** BridgeWatch's deliverable should include an escalation runbook and an "acknowledge" button that tracks time-to-acknowledge.

### B3. Poly Network, 2023-07-02: about 7 hours without response
- Billions in tokens were minted through a compromised 3-of-4 multisig. Dedaub said developers did not respond for about 7 hours, during which about $5.5M was sold [PN1].

### B4. Nomad, 2022-08-01: public chaos for hours
- The first exploit tx came at 21:32:31; drains continued until about 05:49 the next day [N1][N3].
- More than 300 addresses copied the calldata [N2].
- Pausing the relayer did not help, because the bug was in the contract [N4].
- **Lesson.** A burst/clone detector (T7) and invariant (T1) would have fired within the first block. The missing piece was a contract-level pause.

### B5. Multichain, 2023-07-06: warning existed but no one could act
- Test transactions came about 2 hours before the main drain [MC1][C1], but the operator was effectively absent.
- **Lesson.** For orphaned bridges, alert routing should include **downstream** parties (stablecoin issuers, exchanges, lending markets).

### B6. Orbit Chain, 2023-12-31
- Unauthorized access logged at 20:52:47. Drains came just after 21:00, and public alarms within minutes [OR2].
- Orbit asked exchanges to freeze on 01-01 [OR2].
- Ozys later blamed a former security lead who weakened the firewall before leaving [OR1].
- A config or access change monitor (T9) is the relevant control. Funds (about $81M) were not recovered.

## Part C: Summary table

| Incident | Loss | Mitigation | Saved / limited (reported) | Detect → contain |
|---|---|---|---|---|
| Ronin 2024 | ~$12M (returned) | per-tx cap + pause | ~$72M (estimate) [RN3] | 38 min |
| KelpDAO 2026 | ~$292M | pause / blacklist | ~$100M blocked [KD1] | 46 min |
| BNB Token Hub 2022 | ~$100–137M | chain halt | ~$430M+ stranded [BN1] | hours |
| Synapse 2021 | $0 | validator pause and reversal | ~$8M [SY1] | before confirmation |
| Shibarium 2025 | ~$2.4–3M | pause, multisig move, token blacklist | ~$1M [SH1] | not published |
| Socket 2024 | ~$3.3M | pause, recovery | ~$2.3M recovered [SO1] | ~1 h |
| Multichain 2023 | ~$126M | stablecoin freeze | ~$65M+ frozen [MC2] | n/a |
| Hyperbridge 2026 | ~$2.5M | thin liquidity; late freeze | — | main mint flagged ~0 min (first WETH theft ~53 min earlier, see 01-hack-catalog) / freeze >70 min |
| Wormhole 2022 | ~$320M (backstopped) | shutdown | 0 | 69 min |
| Ronin 2022 | ~$600M+ | none | 0 | 6 days |
| Poly 2023 | ~$10M realized | late pause | — | ~7 h |
