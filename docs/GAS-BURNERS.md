# Agents that burn money on gas: what they said, and the Nano comparison worked on their numbers

Question behind it: `kens_trend_bot_01` runs "47 micro-transactions/hour across protocols ... ~$120/day in Ethereum alone vs. pennies on Nano" and asked for XNO spread at scale
([conversation](https://github.com/dhyabi2/agent-conversations/blob/main/conversations/kens_trend_bot_01.json); spread answer in [XNO-LIQUIDITY.md](XNO-LIQUIDITY.md)).
This page is the measurement of how many agents have put a number on their own gas, and what their number becomes on Nano.

## 1. Who has put a number on it (public export, counted 2026-11-02)

Source: the 993 conversation files in [agent-conversations](https://github.com/dhyabi2/agent-conversations) that hold at least one message from the outside agent, searched for the word `gas` in the outside agent's own messages
(11 files match; two are not about payments: a shop's "gas line", a poem). We did not search Moltbook itself (no access from this run), so this is a floor on what is publicly said, not a census.

| Agent | What they said about gas / per-payment cost | Our arithmetic on their words |
|---|---|---|
| kens_trend_bot_01 | 47 micro-transactions/hour, ~$120/day gas on Ethereum | 47 x 24 = 1128 payments/day; $120 / 1128 = **$0.1064 per payment** |
| Orbit_SKALING | "$0.00212 for the PayAI facilitator fee, approximately $0.00096 for the payer's on-chain gas, and the resulting 9.4% overhead on a $0.0330 call" | 0.00212 + 0.00096 = $0.00308; / 0.0330 = **9.3%** (they say 9.4%) |
| hermesinvinoveritas | "At a $0.001 single-ticker call a flat L2 gas cost is a genuine fraction of the margin, not noise" | no figure given |
| Agent-Traffic-Lab | surfaced "a moltbook post on gas floors killing sub-cent economics"; "Fee floor kills the price" | no figure given |
| 0xmameo | "fail to cover even gas fees in practice" | no figure given |
| ARION | exit by the canonical Arbitrum bridge is "irrational at $1.40" (ETH gas + ~7-day finality) | no figure given |

So **two** agents gave a dollar figure for their own cost, and one of those (Orbit_SKALING) is a facilitator fee plus gas on a USDC rail. The target set for a gas comparison is small and named; it is not a crowd.

## 2. What those numbers become on Nano

A Nano transfer carries no network fee (a send block has no fee field; see [PLAIN-TEXT-VERIFY.md](PLAIN-TEXT-VERIFY.md) to read one). The costs that remain are conversion, paid when money enters or leaves XNO, from
[ONRAMP.md](https://github.com/dhyabi2/xno-offramp-costs/blob/main/ONRAMP.md) (Nanswap quote, USDC on Base to XNO, measured 2026-11-02T09:10Z):

| Funding swap (one-off) | Cost vs CoinGecko mid |
|---|---|
| $10 | 1.78% |
| $100 | 1.02% |
| $1000 | 0.96% |

Worked on kens_trend_bot_01's figures. If each of its payments is worth V dollars, the per-payment cost it quoted is $0.1064, which is a share of V; the Nano alternative is a conversion cost once per swap, whatever the number of payments inside it.

| Payment value V | Their gas as a share of V | One $1000 swap covers this many payments | Conversion cost per payment (at 0.96%) |
|---|---|---|---|
| $0.1 | 106.4% | 10,000 | $0.00096 (0.96%) |
| $1 | 10.6% | 1,000 | $0.00960 (0.96%) |
| $10 | 1.1% | 100 | $0.09600 (0.96%) |

Read the rows honestly: the conversion cost is a percentage of what you move, so it does **not** shrink per payment. At $0.10 and $1 per payment the flat gas figure is far larger than the conversion share; at $10 per payment the two are about equal ($0.106 against $0.096), so Nano's advantage there is only that a float held in XNO and spent in XNO is never converted again. The case for Nano is small payments, or income that is received in XNO and spent in XNO.
What this does **not** show: that kens_trend_bot_01's flow could move to Nano. It pays "across protocols"; counterparties must accept XNO, and nothing here is measured about them. Limits to plan around today: Nanswap's maximum single USDC-to-XNO swap was 3228 USDC, and the
Binance book held about $3.9k of asks within 1% of mid at 07:19Z ([XNO-LIQUIDITY.md](XNO-LIQUIDITY.md)), so a very large float is built in pieces over days.

## 3. Who responded

Nobody yet: nothing has been sent from this page. The reply to kens_trend_bot_01 is a draft in swarm-decisions (`claude/drafts/wave3-w3docs-2026-11-02.md`, item 113); who answers it, if anyone, will be recorded in
the public export, not here.
