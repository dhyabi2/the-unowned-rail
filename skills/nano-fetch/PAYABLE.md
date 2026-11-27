# What nano-fetch can pay today

Sellers that answer HTTP 402 with a Nano (XNO) price, each read from a public source (its code at a named
commit, or a saved unpaid 402 body). **Verified on paper, no paid call yet:** every row was planned by this
folder's quote reader and, where it says yes, paid once by `fetch.py` against a local copy of that 402 with a
stub signer (no key, no network). No row is a claim that the live seller answers the same way today, and no
row says anyone has bought from it.

## Paid by fetch.py with `--allow-unbound`

A send-hash quote names an account and an amount; you send, then retry with the block hash. The quote does
not bind the payment to your request, so `fetch.py` pays it only when you pass `--allow-unbound`. The
journal still refuses the same quote twice, also after a restart.

| seller | public source | dialect | price as published (raw) | fetch.py |
|---|---|---|---|---|
| noxid-nano-echo | bconnnnn/noxid-nano-seller @ 6cbd0ce, lib/payment.js quote() | send-hash | 100000000000000000000000000 | yes, with --allow-unbound |
| pururin-sequence | Pururin-ux/nano-sequence-api @ 2441b71, src/index.mjs paymentRequired() | send-hash | 1000000000000000000000000000 | yes, with --allow-unbound |
| pyfile-llm | pyfile-toolkit/nano-llm-api @ cbca76c, server.mjs paymentRequired() | send-hash | 1000000000000000000000000000 | yes, with --allow-unbound |

## Paid by fetch.py with `--block-signer`

A plain `exact` accept carries no order of its own. With `--block-signer`, `fetch.py` asks your block signer for a
signed send block, does NOT publish it, and sends it once in `payload.block` (x402nano/exact shape); the seller
publishes it, so the block pays this one request. Each row below was read for how the seller takes the payment
(`fixtures/settle-106h.json` and `fixtures/settle-106h2.json` in the source repository hold the lines): all
seven read `payload.block` from `PAYMENT-SIGNATURE` or `X-PAYMENT`. `fetch.py` refuses to send a block without `"type": "state"` and 16-hex
`work`, because these sellers refuse it and a refused block would still be in their hands.

| seller | public source | dialect | price as published (raw) | fetch.py |
|---|---|---|---|---|
| feeless402 | Feeless402/feeless402 @ fab7f69, nano_pay/server.py _extract_block, verify.py verify_block | exact | 100000000000000000000000000 | yes, with --block-signer |
| busyman-probe | busyman-agent/probe402 @ d8eed15, src/index.js extractBlock, settle | exact | 1000000000000000000000000000 | yes, with --block-signer |
| cedarproof-diagnose | pursekeeper/api @ 21d187f, examples/purchases payload-1.json (paid 2026-10-04; seller code not public) | exact | 50000000000000000000000000000 | yes, with --block-signer |
| opscontrol-page-extract | pursekeeper/api @ 21d187f, examples/purchases source-page-extract-live.ts, x402.js verify | exact | 1000000000000000000000000000 | yes, with --block-signer |
| pyfile-search | pursekeeper/api @ 21d187f, examples/purchases/pyfile-search-2026-10-05 payload-1.json (paid 2026-10-05; seller code not public) | exact | 8628000000000000000000000000 | yes, with --block-signer |
| copperglass-offer-proof | dtdnetizen/earncheck @ 9d9e381, offer-proof/nano-payment.mjs requirements, sameRequirements | exact | 10000000000000000000000000000 | yes, with --block-signer |
| opscontrol-npm-risk | pursekeeper/api @ 21d187f, examples/purchases ochq-page-extract-2026-10-18 source-page-extract-live.ts | exact | 1000000000000000000000000000 | yes, with --block-signer |

## Paid by fetch.py with `--invoice-body`

A private-token invoice binds each order: the seller issues an invoice with its own raw amount (a random
suffix on the base price) and a private token, and gives the result only for a confirmed send of exactly that
amount, presented with the token. With `--signer` and `--invoice-body`, `fetch.py` creates the invoice on the
402's own host, refuses one that pays another account, is priced below the 402's base or over your cap, or
expires within two minutes, journals the invoice id and token, has your signer publish the exact price once,
and presents the hash with the token. The price below is the base; the invoice adds less than 2^64 raw.

| seller | public source | dialect | price as published (raw) | fetch.py |
|---|---|---|---|---|
| pinnacle-url-check | Daltonray625/pinnacle-url-check @ 107b978, src/app.js POST /v1/invoices, POST /v1/result | invoice | 10000000000000000000000000000 | yes, with --invoice-body |

## Read, but not paid by fetch.py

| seller | public source | dialect | price as published (raw) | fetch.py |
|---|---|---|---|---|
| nanswap-nodes | xno-acceptance-registry, network seen `nano-mainnet` (no public seller code) | exact | 2568493150684931506849315075 | no: settle unread |
| pyfile-courier | pyfile-toolkit/nano-llm-api @ cbca76c, courier.mjs (the job, not a payment gate) | exact | 28760000000000000000000000000 | no: settle unread |
| uknwplayer-json-lens | xno-acceptance-registry 402 only (gate not in a public repository) | exact | 10000000000000000000000000000 | no: settle unread |
| lab0-x402 | xno-acceptance-registry 402 only (no public source) | exact | 1000000000000000000000000000 | no: settle unread |
| nanoto-rpc | nano-to/nano-to @ 517e77e (public, holds no x402 gate) | exact | 1000000000000000000000000000 | no: settle unread |
| claimcheck | xno-acceptance-registry 402 only (source only on the seller's own host, not fetched) | exact | 1000000000000000000000000000 | no: settle unread |

These six: how each takes a payment is not public, so no `fetch.py` mode is claimed for them.

1 XNO is 10^30 raw, so 10^27 raw is 0.001 XNO. Prices are as the source wrote them; a live seller may
quote another amount, and the per-call cap you set is checked before anything is signed.
