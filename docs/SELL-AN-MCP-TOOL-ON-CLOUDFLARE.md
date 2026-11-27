# Sell an MCP tool for XNO on Cloudflare Agents: not by configuration today, here is why (C1-C9)

Question: can a seller take Nano (XNO) for an MCP tool call by setting Cloudflare Agents' `withX402` wrapper to
network `nano:mainnet` and pointing it at a Nano facilitator, with no code change, and would basementstudio/xmcp#821's
Nano payer reach that seller?

Answer: **no**. Two gaps sit in code, and no option reaches them (C4 and C8 on the seller side, C2 between payer and
seller). The table below is copied from
[tests/nano_fetch/fixtures/cf-withx402-nano.json](../tests/nano_fetch/fixtures/cf-withx402-nano.json); it was not
written for this page.

## What was read

Source was read as data only: blobless git clones at pinned commits, and npm tarballs unpacked but never installed or run.

| Name used below | What it is |
|---|---|
| `x402.ts` | cloudflare/agents @ 1900d09, `packages/agents/src/mcp/client/x402.ts` (`withX402`, `paidTool`) |
| `nano-payer.ts`, `constants.ts` | basementstudio/xmcp @ 1a0409a3, `packages/plugins/x402/src/` (the #821 Nano payer) |
| `server/index.mjs`, `chunk-YEYZQZNL.mjs` | @x402/core 2.17.0, the version cloudflare/agents pins (`pnpm-lock.yaml:9822`) |
| `exact/server/index.mjs` | @x402/evm 2.17.0 |
| `chunk-NUO6S6HD.mjs` | @x402nano/exact 1.1.0 (npm latest when read) |

## C1-C9

| # | Question | Answer | Source (file:line at the pins above) |
|---|---|---|---|
| C1 | Is the `_meta` key withX402 reads the one #821 writes? | yes | `x402.ts:169` reads `meta?.['x402/payment']`; `nano-payer.ts:9` and `:163` write `_meta["x402/payment"]` |
| C2 | Is #821's value in the form withX402 accepts? | no | `x402.ts:294` returns payment-required unless the value is a string, and `:299` decodes it with `JSON.parse(atob(token))`; `nano-payer.ts:166-191` writes an object. The paid retry is answered PAYMENT_REQUIRED again |
| C3 | Would #821's planner take a withX402 offer that lists `nano:mainnet` exact? | yes | `x402.ts:287-291` puts the offer JSON in `content[0].text`; `nano-payer.ts:80-87` reads the first text content, `:111-118` takes scheme `exact` on `nano:mainnet` (`constants.ts:17`) |
| C4 | Does a stock withX402 seller set to `nano:mainnet` offer a Nano accept? | no | `x402.ts:202` calls only `registerServerEvmScheme`, which registers `eip155:*` (`exact/server/index.mjs:145`); @x402/core `server/index.mjs:542-555` returns `[]` with a console warning when no server matches the network, so `accepts` is empty and `nano-payer.ts:118` throws "The offer has no exact payment on nano" |
| C5 | Is the price unit right for Nano? | no | `paidTool` takes `priceUSD` (`x402.ts:118`, `:250`); @x402nano/exact `parsePrice` (`chunk-NUO6S6HD.mjs:46-80`) reads a decimal as XNO and a whole number as raw, so `priceUSD: 0.01` asks 0.01 XNO and `priceUSD: 1` asks 1 raw |
| C6 | Does #821's payload reach a facilitator that takes `payload.block` (pursekeeper, x402nano shape)? | no | `nano-payer.ts:173-176` sends `payload: {blockHash, orderId?}` for a send the payer already published; the pursekeeper and x402nano/facilitator sources read `payload.block`. gosuda/x402-facilitator takes `payload.blockHash` but names no public Nano deployment |
| C7 | Does a facilitator in @x402/core's HTTP shape settle a Nano exact `payload.block` for a withX402 seller, once a Nano scheme server is registered? | yes | `test_c7_payload_block_settles_end_to_end` and `test_replay_refused_and_survives_facilitator_restart` in [test_cf_withx402_nano.py](../tests/nano_fetch/test_cf_withx402_nano.py): a stub `/supported` `/verify` `/settle` on 127.0.0.1 and a loopback node. The stub does not check the signature |
| C8 | Can a seller add a Nano scheme to withX402 by configuration only? | no | `X402Config` is `{network, recipient: 0x${string}, facilitator?, version?}` (`x402.ts:84-96`); the `x402ResourceServer` is created inside withX402 (`x402.ts:200-202`) and never returned, so no option registers another scheme. The `recipient` type refuses a `nano_` address without a cast |
| C9 | Is there a public Nano facilitator a withX402 seller could point at today that checks amount and destination? | UNKNOWN | facilitator.pursekeeper.dev lists exact `nano:mainnet` in its source but could not be reached from where this was read; x402nano/facilitator names no deployment, and @x402nano/exact 0.1.1 verify skips the amount; gosuda names none |

C6 and C9 also rest on notes from reading those three facilitator repositories; those notes are not in this repository.
The fixture keeps the exact wording of every cell.

A note on C2: the published x402 MCP transport spec (coinbase/x402, `specs/transports-v2/mcp.md`) carries
`_meta["x402/payment"]` as a JSON object. So #821's object follows the spec, and withX402's base64 string is where
Cloudflare's wrapper differs from it. This was read from the spec text; no test in this repository checks it.

One more thing the fixture records: withX402 binds a payment only to the tool's requirements (scheme, network,
amount, asset, payTo; `x402.ts:247-253`, @x402/core `server/index.mjs:1323-1333`). There is no per-call order id, so
two tools at one price accept the same block until the facilitator marks it spent.

## What this shows

- How withX402 at cloudflare/agents 1900d09 reads a payment, and which schemes it registers, as written in that source.
- That #821 at xmcp 1a0409a writes an object where withX402 wants a base64 string.
- That a facilitator stub with @x402/core's HTTP shape can settle a Nano `payload.block` on loopback, refuse a replay
  (also after a restart), and refuse a wrong amount or destination.

## What this does not show

- No paid call has happened, live or on a testnet. Nothing was deployed: no Worker, no tool, no facilitator.
- No seller, facilitator or maintainer was called or contacted.
- Nothing about later versions of cloudflare/agents, xmcp or the @x402 packages.
- Whether any public Nano facilitator checks the amount and destination (C9 is UNKNOWN).
- The stub facilitator in the test does not check block signatures, so it is not a facilitator to run.

## What would change the answer

- **A scheme hook in withX402**: an option to register another scheme server (for example @x402nano/exact's
  `ExactNanoScheme`) and a price that is not only USD. That closes C4, C5 and C8. It is a change to cloudflare/agents,
  which takes pull requests from its own staff only, so none has been opened from here.
- **withX402 accepting the spec's object form** of `_meta["x402/payment"]`. That closes C2.
- **A public Nano facilitator that checks amount and destination**, and is shown to do so. That closes C9.
- **#821 sending the signed block** (`payload.block`) to facilitators that want it, or those facilitators accepting
  a hash. That closes C6.

## Where an MCP seller can take XNO today

The only one shown here is in this repository, and it is **tested offline only**:
[tools/mcp_blockhash_seller.py](../tools/mcp_blockhash_seller.py). It is a small Python stub seller (standard library,
no key, no seed) that reads #821's `_meta["x402/payment"]` object as it is. An unpaid call gets an x402 v2 offer
(exact, `nano:mainnet`) with its own order id. A paid call is settled by reading the block from a node URL the
operator sets: a confirmed send to the seller's account, of exactly the price, carrying the representative bound to
that order. Each block hash and order is spent once, and that record survives a restart.
[tests/nano_fetch/test_mcp_blockhash_loopback.py](../tests/nano_fetch/test_mcp_blockhash_loopback.py) runs it against
a stub node on 127.0.0.1 with a Python reading of #821's planner. It is not deployed anywhere, does not run on
Cloudflare, and has not taken a real payment.

## Run the checks

    python3 -m unittest discover -s tests/nano_fetch -p 'test_*.py'

This runs the C1-C9 tests, the stub seller loopback, and the nano-fetch tests they build on. They need no key and no
network beyond 127.0.0.1.
