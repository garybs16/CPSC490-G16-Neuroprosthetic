> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# Multichain, 2023-07-06

**Loss:** about $126M (Unchained; CoinDesk says up to about $130M) · **Design:** MPC custody (router / lock-mint) · **Root cause:** insider/custody · **Chains:** Ethereum to Fantom, Moonriver and Dogechain bridges · **Status:** confirmed

## Summary
Multichain's MPC signing keys were effectively controlled by one person. Weeks earlier, the company had lost contact with its CEO. On 6 July, the escrow behind the Fantom bridge (and others) began paying out everything to fresh addresses, using validly signed MPC withdrawals. No one at Multichain could stop it, so stablecoin issuers became the only brake.

## Timeline (UTC)
| Time | Event |
|---|---|
| 16:21:23 | $2 USDC "test" withdrawal from Fantom bridge escrow `0xc564ee9f…afbe` (block 17635954). Cyvers says it flagged the test transactions. |
| 18:10:35 | First large drain: 27.65M USDC (block 17636491) |
| Following hours | WBTC, WETH, DAI, LINK, USDT, CRV, YFI and others released. Moonriver and Dogechain bridges also drained. |
| Following days | Circle freezes about $65M USDC; Tether freezes about $2.5M |

See `../open-questions.md` §1 for the test-versus-drain timing question.

## What failed
Insider/custody: custody of the MPC keys, not code. Whether this was theft by insiders or by outsiders who seized the keys is still unclear.

## On-chain signature
- A tiny test withdrawal, then about 2 hours of quiet, then multi-million releases of every asset in the escrow to new addresses.
- All releases were properly signed.

## BridgeWatch rules that would fire
- `large_withdrawal`: at 18:10:35 (27.65M USDC in one transfer).
- `escrow_drain` and `outflow_spike`: within the same hour.
- `withdrawal_burst`: as many tokens leave in quick succession.
- The 16:21 test would *not* trip a size-based rule. A "first-time recipient from the vault signer" heuristic could have, but at a high false-positive cost.

## False-alarm considerations
- Multichain had been rebalancing and slowing withdrawals for weeks, so the baseline was already abnormal. A detector trained on May–June data would see a noisy period.
- Full escrow migrations to a new contract look like a drain. They need an allow-list of the operator's own addresses.

## Response and outcome
- No operator response was possible.
- Issuer freezes covered roughly half the value. Those funds are frozen, not returned to users.
- Multichain later announced it was ceasing operations.

## References
- https://unchainedcrypto.com/hack-or-rugpull-multichain-sees-126-million-abnormal-outflows/
- https://coindesk.com/business/2023/07/06/multichain-bridges-experience-unannounced-outflows-of-over-130m-in-crypto/
- https://www.globalsecuritymag.fr/CyVers-Discovers-126M-Multichain-Hack.html
- `../verified-ethereum-cases.md`
