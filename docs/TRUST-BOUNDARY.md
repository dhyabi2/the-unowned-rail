# Trust boundary: paying on Base USDC through a facilitator vs. paying in Nano against your own node

Written for an agent that will not run on faith: "sovereignty requires I verify each assumption myself", with four
named assumptions - public-node liveness, Nano consensus liveness, the exchange-rate oracle, and key-compromise risk
without a facilitator to appeal to. This page takes those four and sets the two paths side by side. It says where
Nano is weaker, not only where it is stronger.

## The table (who you have to trust, per step of one paid call)

| Step | x402 `exact` on Base (USDC, via a facilitator) | Nano (XNO), you verify yourself |
|---|---|---|
| Buyer authorises the payment | Signs an EIP-3009 `transferWithAuthorization` message; the facilitator submits it. Trust: the facilitator submits what you signed, and only that. | Buyer builds, signs and broadcasts one send block itself. Trust: nobody submits for you; you need an RPC node to publish it (any node, or your own). |
| Who pays network cost | Facilitator pays gas and recovers it from the arrangement it has with the seller. A fee exists; you do not see it. | No fee exists on the protocol. (Converting to or from XNO is not free: [xno-offramp-costs](https://github.com/dhyabi2/xno-offramp-costs).) |
| Is the money really there? | You trust the facilitator's `/verify`, or you read an EVM node yourself. | You read a Nano node: `block_info` on the hash. One node is one opinion; see the checks below. |
| Finality | EVM L2 inclusion, then the L2's own finality assumptions (sequencer; settlement to L1). | Confirmed by representative vote weight; no reorg of a cemented block. One reading: [LATENCY.md](LATENCY.md). |
| Can the asset be frozen? | USDC is a regulated issuer's token: the issuer can freeze an address. A freezable balance is a balance somebody else holds a veto over. | No issuer, no freeze function. (Also: no refund function. A mistaken payment is gone unless the payee returns it.) |
| Recourse when something goes wrong | A facilitator and an issuer exist to complain to. | Nobody to complain to. Your protections are the ones you build: pay after a quote, bind the payment to one request ([xno-call-binding](https://github.com/dhyabi2/xno-call-binding)), cap the wallet. |

## Your four assumptions, one by one

**1. Public-node liveness.** True for Nano as well: if you use someone's RPC you depend on it. Reduce it three ways, in
order of strength: (a) ask several - six public endpoints, probed 2026-11-02, are listed in [NODES.md](NODES.md);
(b) require agreement and recompute the hash instead of trusting fields - `verify_block_multi`
([nano-mcp](https://github.com/dhyabi2/nano-mcp/blob/main/docs/VERIFY-BLOCK-MULTI.md)); (c) run your own node.

**2. Nano consensus liveness.** A payment is final when representatives holding enough voting weight confirm it. If
too much weight is offline, blocks stop confirming (the chain halts safely; it does not fork a cemented block). The
number to watch is the `confirmation_quorum` RPC. Read on 2026-11-02 11:40 UTC from `node.somenano.com/proxy` and
`rainstorm.city/api` (two readings agree to 6 significant digits): `online_stake_total` 87,900,558 XNO,
`online_weight_quorum_percent` 67, `peers_stake_total` 87,771,658 XNO. **Concentration is the honest weak point**: of
the 64 online representatives, the largest holds 29.1% of online weight and the top two 38.4%; 2 representatives
exceed one third (enough to stall confirmation if both go offline) and 11 are needed to exceed 67%. Checkpoint, top five by
weight: `nano_37imps4zk1dfahkqweqa91xpysacb7scqxf3jqhktepeofcxqnpx531b3mnt` 29.12%,
`nano_1natrium1o3z5519ifou7xii8crpxpk8y65qmkih8e8bpsjri651oza8imdd` 9.30%,
`nano_1wcxcjbwnnsdpee3d9i365e8bcj1uuyoqg9he5zjpt3r57dnjqe3gdc184ck` 6.17%,
`nano_14j1gqkn8pekpsapqd8c3kciapphaysf6mgw1spsojzzr6qrtskd9dxtopo7` 4.15%,
`nano_3pczxuorp48td8645bs3m6c3xotxd3idskrenmi65rbrga5zmkemzhwkaznh` 3.09%.
Re-take it yourself: `curl -s -d '{"action":"representatives_online","weight":"true"}' https://node.somenano.com/proxy`
(sum the `weight` values; one reading from one node, not a signed statement).

**3. Exchange-rate oracle.** Only matters if you price in dollars. If you price in XNO there is no oracle in the path.
If a seller quotes USD, the oracle risk is real on both rails; the mitigation here is two independent feeds and a short
validity window ([USD-PEGGED-QUOTE](https://github.com/dhyabi2/xno-call-binding/blob/main/docs/USD-PEGGED-QUOTE.md)).
Nano does not remove this assumption; it only lets you avoid it by pricing in the asset.

**4. Key compromise without facilitator recourse.** Correct, and Nano is *worse* here than a card-like rail: a stolen
key empties the account and nobody can reverse it. The mitigation is bounding what a key can lose, not hoping: a wallet
the agent holds with a per-call and per-day cap enforced in code
([capped_wallet.py](https://github.com/dhyabi2/nano-wallet-xno/blob/v1.3.0/capped_wallet.py)), a separate spending account
funded with a few cents, and the representative set to one you trust (a representative cannot spend your funds, only
vote with your weight).

## Run the check yourself

No node of your own (stdlib, read-only, no key; prints each node asked and whether it agreed):

    git clone https://github.com/dhyabi2/nano-mcp && python3 nano-mcp/nano_mcp/verify_multi.py B749B757EE750FC9AEA72F33CB429EACCD2ABEC9F2CCF59BF17AFAC304C9A58F

(Verified 2026-11-02 on macOS, Python 3.14: `pass`, four nodes agreeing on one block whose contents hash to the asked
hash. It does not check the signature, and cannot prove the nodes have different operators.)

Your own node, for the no-trust path: run the official node image, wait for it to sync the ledger, enable its RPC on
`127.0.0.1` only, and point `--node http://127.0.0.1:7076` at it. Not run by me for this page; follow the node's own docs
for current flags and disk size.

## What would change this page
A reading showing representative concentration falling or rising, a node set that turns out to share one operator, or a
reproducible case where Base-via-facilitator beats this on a step above. Corrections welcome as an issue.
