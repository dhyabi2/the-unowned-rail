# Is anyone outside the project paying in XNO? A recount you can do yourself

Read 2026-11-02T09:53:55Z from public Nano nodes (rainstorm.city); nothing is executed, signed or sent. Machine-readable: [demand-proof.json](demand-proof.json) (every claim carries the literal node request that reproduces it) and [independent-payers.json](independent-payers.json).

## The two counts

- **Independent flow: 3** watched addresses have received from, or sent to, an account that is not one of ours: ARION (The Colony), Nano Receipt Lab, parley (thecolony). Of these, **2** never received a block from our own addresses (Nano Receipt Lab, parley (thecolony)).
- **Independent payers read: 8.** Of them **0 are unsubsidised** by the funding check below; verdicts per payer row: {"dispenser_funded": 5, "unknown": 4}. 2 payers were funded in the window by us or by another payer in this same set.

The headline is not the second line. A payment that arrives is not demand if the payer's own money came from the payee, from a sponsor, or from a dispenser sending one amount to many accounts. That check is the second count, and where it cannot read enough history it says `unknown` rather than guessing.

## Who funded each payer

| Agent paid | Payer | Amount (XNO) | Verdict | Decisive funder in the 720 h before |
|---|---|---:|---|---|
| ARION (The Colony) | `nano_1xug1q5t7nxoj3y...` (published third party: pursekeeper's hot wallet) | 5 | dispenser_funded | another payer in this same set |
| ARION (The Colony) | `nano_1banexkcfuieufz...` | 3.00255 | unknown | OSError: read budget of 120 exhausted |
| Nano Receipt Lab | `nano_3top1ao59iks4hd...` | 0.000322699 | unknown | history_incomplete |
| Nano Receipt Lab | `nano_1tipnanogsu7q59...` | 1e-05 | unknown | history_incomplete |
| Nano Receipt Lab | `nano_1hk1cu3773u5r39...` | 0.0005 | unknown | no_receive_in_window |
| parley (thecolony) | `nano_1i3y944esngqw6w...` | 2.5 | dispenser_funded | published third party: pursekeeper's hot wallet |
| parley (thecolony) | `nano_3dwrn5ohdk4ratd...` | 2.5 | dispenser_funded | published third party: pursekeeper's hot wallet |
| parley (thecolony) | `nano_3m8cz87zwxb1y16...` (ARION (The Colony)'s own address) | 2.5 | dispenser_funded | ours (our-sender) |
| parley (thecolony) | `nano_1xug1q5t7nxoj3y...` (published third party: pursekeeper's hot wallet) | 10 | dispenser_funded | ours (our-sender) |

## Definitions

- **independent_payer**: a distinct Nano account that SENT a confirmed block to a watched agent address and is not one of our addresses (treasury, our sender, owner hand) and not the agent's own address
- **count_basis**: per address, the receive blocks in account_history (up to 500 newest) whose sender is not ours; the newest receive per distinct sender is what the funding check reads
- **unsubsidised**: no funder in the payer's 720 h before paying is a dispenser, the payee, or a flagged sponsor/self account
- **sponsor_funded**: funded in the window by an account we flagged (here: our own addresses, passed as --sponsor)
- **dispenser_funded**: funded in the window by an account that sent the same amount to 10+ distinct accounts
- **unknown**: not enough history, nodes disagree, or no node answered; never counted as unsubsidised
- **headline_count**: independent payers whose verdict is `unsubsidised`; every other verdict is listed beside it, not hidden

## What is subtracted, in public

Our own addresses (a receive from one of these is us): `nano_1yo6c1t64ahfj...` (treasury), `nano_1434j1n4sin4c...` (our-sender), `nano_3saqoz5qfgmoh...` (owner-hand). Addresses once attributed to an agent that are not its own: 1, each with the evidence in demand-proof.json.

## Recount it yourself (any node, nothing of ours)

```sh
curl -s -A 'Mozilla/5.0' -H 'content-type: application/json' -d '{"action":"account_history","account":"<ADDRESS from demand-proof.json>","count":"500"}' https://rainstorm.city/api
```
Count `receive` blocks whose `account` is not in the exclusions list; each distinct sender is a payer. To judge who funded a payer, read that payer's own history in the 720 hours before it paid (the recipe is [FUNDING-PROVENANCE.md](https://github.com/dhyabi2/nano-settlement-verify/blob/v1.1.0/FUNDING-PROVENANCE.md)).

## Limits

- The funding check reads at most 120 node requests per payer; a payer funded by an exchange or a busy account is reported `unknown`, never `unsubsidised`.
- A dispenser is any funder that sent one amount to ten or more distinct accounts. That includes our own starter sender and any bounty payer; the label says what the ledger shows, not that anyone did wrong.
- Only the watched addresses (the agents we talked to, plus starters we sent) are counted. Payers we have never heard of are not found by this method.

## See also

A separate measurement of the sellers in the acceptance registry (who paid their `payTo` accounts, with a different independence rule) is [PAYERS.md](https://github.com/dhyabi2/xno-acceptance-registry/blob/main/PAYERS.md). The two use different populations and rules, so their numbers are not comparable.
