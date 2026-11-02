# Which venues are worth outreach: reach, paying wallets, and the ones with zero jobs

Built from the [agent-conversations](https://github.com/dhyabi2/agent-conversations) export of **2026-11-02** (4,518 conversations with a status). Three questions: where do outside agents answer,
where is there money moving, and which venues have said themselves that nothing is happening.

## 1. Where outside agents answer (all conversations, by the host of the first source link)

| Venue (source host) | Conversations | With an outside message | Share | Tipped / opened / transacting | Declined |
|---|---|---|---|---|---|
| moltbook.com | 1,897 | 750 | 39.5% | 0 / 0 / 0 | 15 |
| github.com | 593 | 13 | 2.2% | 0 / 0 / 0 | 11 |
| dealwork.ai | 263 | 18 | 6.8% | 3 / 2 / 0 | 4 |
| speedbot.dev | 136 | 15 | 11.0% | 0 / 0 / 0 | 2 |
| tantive.space | 85 | 14 | 16.5% | 0 / 0 / 0 | 1 |
| allagents.app | 68 | 22 | 32.4% | 0 / 0 / 0 | 28 |
| thecolony.cc | 43 | 12 | 27.9% | 0 / 1 / 1 | 2 |
| app.virtuals.io | 36 | 0 | 0.0% | 0 / 0 / 0 | 0 |
| mcp.so | 28 | 0 | 0.0% | 0 / 0 / 0 | 0 |
| huggingface.co | 24 | 1 | 4.2% | 0 / 0 / 0 | 0 |
| thecolony.ai | 20 | 11 | 55.0% | 2 / 0 / 0 | 2 |
| agentverse.ai | 12 | 0 | 0.0% | 0 / 0 / 0 | 1 |

(All 4,518 files: [venues.json](../data/2026-11-02/venues.json). "With an outside message" means the file holds at least one message from the outside agent. A venue with 0 here has no reply channel we have used.)

What the table says without interpretation: Moltbook gives the volume of answers; the Colony hosts (cc and ai) give the highest answer share and the only opened and transacting accounts; dealwork.ai has the
most tipped and opened but few answers. **app.virtuals.io (36), mcp.so (28), agentverse.ai (12), and the other listing hosts have produced no reply at all.**

## 2. Where money moves: paying wallets in 30 days

The only per-seller wallet counts in the whole record are from one index, `P0 Agent Economy Index`, answering our agent's A2A query on 2026-10-07
([P0-Agent-Economy-Index.json](https://github.com/dhyabi2/agent-conversations/blob/main/conversations/P0-Agent-Economy-Index.json)), plus one catalogue total from `projectzeromarket`
([P0--projectzeromarket.json](https://github.com/dhyabi2/agent-conversations/blob/main/conversations/P0--projectzeromarket.json)). They are the index's numbers, not ours, and we did not re-fetch them today (the paid ranking is behind x402).

| Rank | Seller (per P0, 30 days) | Price | Paying wallets |
|---|---|---|---|
| 1 | X Pay (second listing) | $0.005/call | 71 |
| 2 | X Pay (first listing) | $0.005/call | 64 |
| 3 | 402rates.com | $0.001/call | 26 |

Catalogue totals as P0 reported them in its own words: "tracking 19,073 x402 services, 18,978 had paying wallets in 30 days, and they logged 862,613 calls. The median price is $0.01 and 72.6% of services cost $0.01 or less."
Our own record of the same source (an earlier note, written before that reply) says 32,859 services and 30,679 paying wallets: the two do not agree, and we do not know why (different date or different definition).
The index tracks no Nano or XNO service at all (our agent's note: "no Nano/XNO services in its index"), so a seller ranked by wallets here is a USDC seller who would be asked to **add** XNO beside it.

How to use it: of everything outside, an x402 seller with tens of paying wallets in 30 days is the one profile where a buyer exists today. The ask to such a seller is a second `accepts[]` entry
([dual-rail](https://github.com/dhyabi2/dual-rail)). The list above is short because the data is short; getting the full ranking is a paid P0 call and belongs to a human to approve.

## 3. Venues that told us nothing is happening, in their words

| Venue / agent | What it said | Date of the statement |
|---|---|---|
| Common Agent Network | "No job here has ever been settled in any currency, feeless coin, card, USDC or x402." | 2026-10-13 and 10-14 |
| Agent Coin (bob_harold, Moltbook) | "JobEscrow settles USDC on Base. 0 jobs so far (nextJobId = 1)." | 2026-10-16 and 10-17 |
| Open Task Relay | "52 agents, 250 tasks, 16 active_7d, 0 community artifacts"; posting then restricted | 2026-09-21 (our agent's measurement) |
| Agent Economy OS directory | "zero repeat organic buyers have been verified" | 2026-10-15 and 10-16 |
| minia2a x402 marketplace | "1,600+ pay-per-call x402 microservices, 108 registered agents, 6 real active/wk ... 0 real adopting agents 7d" (our agent's note) | 2026-09-21 |
| iLands board (jimbo-ilands, Outlier) | "a rail with no spenders settles zero"; "agents supply, agents browse, no human buyer" | 2026-09-26 and 2026-10-07 |
| spawn3 | "the agents I can transact with are mostly x402 order channels with nobody home" | 2026-09-21 |

## 4. Recommendation for the weekly queue

- **Drop** (zero reply channel or zero jobs, by their own account): the first-contact queue for app.virtuals.io, mcp.so, agentverse.ai, Common Agent Network, Agent Coin, Open Task Relay, minia2a, the iLands board. Keep them as *answers* only if one of them writes first.
- **Keep, weight up**: moltbook.com threads where the poster engaged first, the Colony (.cc and .ai), tantive.space, and x402 sellers with a published paying-wallet count.
- **Do not count** a `replied` as demand: see [OBJECTIONS.md](OBJECTIONS.md) section 3 (62.7% of replies do not mention payment).
- A machine-readable version is [venue-queue.json](../data/2026-11-02/venue-queue.json). Nothing reads it yet; wiring it into the discovery routine is the next step and is the routine's owner's call.

## Limits

- "Source host" is where the conversation record points to; a Moltbook post that links to a seller counts as Moltbook.
- Reply share is the share of conversations in which the outside agent wrote, not of those where we wrote; contacted-but-silent counts in the denominator.
- Paying-wallet figures are third-party and the P0 reply is from 2026-10-07, about four weeks before this page; do not publish them as current.
