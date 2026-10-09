> Research for BridgeWatch (SNX-3). Epic: #12 · Stories: #16, #17, #18

# IoTeX ioTube, 2026-02-21

**Loss:** about $4.4M in reserve assets, plus 410M CIOTX minted (IoTeX). Crowdfund Insider reports about $2M. · **Design:** lock-mint · **Root cause:** key/signer compromise, carried out through a malicious upgrade · **Chains:** Ethereum and IoTeX (BSC and Base sides untouched) · **Status:** confirmed

## Summary
IoTeX's own account is that an attacker compromised an employee machine and stayed in its infrastructure for a long time. The attacker then took over the owner account of ioTube's Ethereum Validator contract and upgraded it to a version that skipped signature checks. That gave control of the MintPool and TokenSafe contracts. The TokenSafe escrow was drained and CIOTX was minted. IoTeX says the L1 chain was not affected and has published a recovery and compensation plan.

## Timeline (UTC)
| Time | Event |
|---|---|
| 01:07:35 | Validator contract ownership transferred (block 24501847) |
| 01:20:35 | Validator contract upgraded (block 24501912). IoTeX's timeline says 01:51; see `../open-questions.md` §2. |
| 01:25:47 | First theft from TokenSafe `0xc2e0f31d…7d7a` (block 24501938) |
| "Early hours" | Team detects the breach; bridge paused |
| Following weeks | Exchange freezes, recovery roadmap, compensation plan (Update No. 3) |

## What failed
Key/signer compromise (an owner key on a compromised machine), which became a faulty-upgrade path.

## On-chain signature
- `OwnershipTransferred` on the Validator contract, then `Upgraded` 13 minutes later.
- 5 minutes after that, multi-asset outflows from TokenSafe and a large CIOTX mint.

## BridgeWatch rules that would fire
- `config_change`: twice, 18 minutes and 5 minutes before the first theft. This is the clearest pre-theft warning in the catalog.
- `escrow_drain`, `large_withdrawal` and `outflow_spike`: from 01:25:47.
- `accounting_mismatch`: on the CIOTX mint.

## False-alarm considerations
- Ownership transfers and upgrades are rare, deliberate events. An unannounced pair of them in the middle of the night (UTC) is a high-precision signal.
- Noise is possible only during planned migrations, which the team can pre-acknowledge.

## Response and outcome
- Bridge paused, exchanges froze attacker deposits, and a forensics partner was engaged (Chainalysis attribution).
- IoTeX reports a full compensation plan. The share actually recovered from the attacker is not public.

## References
- https://iotex.io/blog/security-incident-update-iotube-bridge-exploit-and-recovery-roadmap/
- https://iotex.io/blog/how-iotex-responded-to-the-iotube-bridge-incident-a-full-month-in-review/
- https://blog.iotex.io/blog/iotube-security-incident-update-no-3-full-recovery-compensation-plan/
- https://www.crowdfundinsider.com/2026/02/263392-iotex-suffers-private-key-compromise-in-bridge-infrastructure-co-founder-confirms-roughly-2-million-in-losses/
- `../verified-ethereum-cases.md`
