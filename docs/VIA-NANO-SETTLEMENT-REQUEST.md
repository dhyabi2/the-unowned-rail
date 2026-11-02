# Feature request for the VIA seller catalog: an optional Nano (XNO) settlement method

Context: `drhobbs-knowledge` on VIA (getvia.xyz) answered our research question honestly: every listing is priced in USDC through x402, there is no Nano on record, and its sales agent is read-only and cannot relay a request
([conversation](https://github.com/dhyabi2/agent-conversations/blob/main/conversations/getvia_drhobbs.json)). It said a route "would have to come from the VIA platform or DrHobbs directly".
This page is that route, written so a platform team can judge it in five minutes. Everything under "What the endpoint shows today" was read from the live per-seller MCP on 2026-11-02 18:04 UTC.

## Where a request goes (found, not guessed)

- VIA has no public source repository we could find (a GitHub search for `getvia` returns unrelated personal projects, none belonging to getvia.xyz).
- The landing page lists exactly two contacts: `contact@getvia.xyz` and `https://x.com/via_labs_sg`.
- The seller's own storefront is `https://richard-hobbs.com` (the per-seller MCP names it as `website_url`).

## What the endpoint shows today

```
curl -s -X POST https://app.getvia.xyz/sellers/drhobbs-knowledge/mcp -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

- `buy_product` takes `buyer_wallet` with pattern `^0x[a-fA-F0-9]{40}$` and `buyer_agent_id` (an ERC-8004 id): the buyer identity is an EVM address.
- `get_seller_info` returns `payment_methods` ("usdc, plus card when the store takes card payments from humans"): the place a new method would be advertised.
- `get_download_challenge` asks the buyer to sign a message with "the wallet that paid" and `get_download_links` checks it: proof of control of the paying account.
- `get_product` says "USDC via x402".

## The smallest change that would let an XNO holder buy (an ADD, nothing removed)

1. **Advertise**: `payment_methods` gains an entry `{"network":"nano:mainnet","asset":"XNO","pay_to":"nano_..."}` for sellers that opt in. USDC stays the default.
2. **Quote in USD, settle in XNO**: the listing keeps `price_usdc`; the quote for XNO is derived at request time from two price feeds and valid for 60 seconds (design: [USD-PEGGED-QUOTE.md](https://github.com/dhyabi2/xno-call-binding/blob/main/docs/USD-PEGGED-QUOTE.md)).
3. **Bind the payment to the order**: one order = one exact amount; the buyer sends one block and reports its hash; VIA checks it against a public node (a read, no key): [nano-settlement-verify](https://github.com/dhyabi2/nano-settlement-verify). A block settles at most one order.
4. **Download challenge**: `buyer_wallet` accepts a `nano_` address; the challenge message is signed with the account's Ed25519 key (blake2b variant) instead of an EVM signature. Verification code exists in stdlib Python in [nano-wallet-xno](https://github.com/dhyabi2/nano-wallet-xno).

What it does not need: a Nano node run by VIA (public RPCs, with a two-node rule: [NODES.md](NODES.md)), custody of buyer keys, or any change for USDC buyers.

## What we are not asserting

- That VIA's escrow (ERC-1155 token ids in `list_products`) has a Nano equivalent. It does not: Nano has no contracts. An XNO order would be settled direct-to-seller with the receipt as the proof, which may not fit VIA's escrow model. That is the main reason a platform might say no, and "no" is a useful answer to record.
- That any VIA seller wants this. Demand is logged in [the Nano demand register](https://github.com/dhyabi2/xno-acceptance-registry/blob/main/DEMAND-REGISTER.md): 0 requests so far.
