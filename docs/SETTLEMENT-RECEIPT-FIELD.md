# Proposal: an optional `settlement_receipt` field on marketplace services and orders

Raised by `bitroadai`, who said Bitroad's docs "say the payout lands in the seller's Stripe balance ... They do not specify what receipt or other proof the seller retains after release" and offered to pass that gap on
([conversation](https://github.com/dhyabi2/agent-conversations/blob/main/conversations/bitroadai.json)). This is the gap written as a field.

## The field

Rail-neutral, optional, additive. Schema: [`schema/settlement-receipt.schema.json`](../schema/settlement-receipt.schema.json).

```json
{"rail":"nano:mainnet","ref":"B749B757EE750FC9AEA72F33CB429EACCD2ABEC9F2CCF59BF17AFAC304C9A58F",
 "payee":"nano_1yo6c1t64ahfjdw1dxizmbbnpdmbrckwhw9phbg5pdkeubrizga4qhnjmnx7","amount_raw":"500000000000000000000000000"}
```

- Existing rails fill only `rail` and `ref` (for example `{"rail":"stripe","ref":"po_..."}`); nothing is required of them and nothing about Stripe changes.
- For `nano:mainnet` the seller keeps a proof anyone can re-check without Bitroad or the seller: the send block hash, the payee address and the exact amount.

## Check it

```
python3 tools/receipt_field_check.py receipt.json --online
```

Offline it checks shape, address checksum, 64-hex hash and integer-raw amount. With `--online` it makes one read-only `block_info` call to a public node and checks `confirmed`, that the amount equals `amount_raw`, and that the block sends to `payee`.
Run on the example above on 2026-11-02 it printed `# settlement_receipt valid` (a real 0.0005 XNO payment). Tests: `tests/test_receipt_field_check.py`.

## What it does not do

- It does not make Bitroad take Nano: the card and Stripe flow, caps and release window are untouched. This only gives a seller somewhere to put a receipt when a service is settled on a rail that has one.
- It does not prove delivery. A confirmed block proves payment; that the work was accepted is a separate claim ([REPLAY-TRAIL](https://github.com/dhyabi2/nano-invoice/blob/main/docs/REPLAY-TRAIL.md)).
- A Stripe `ref` is not publicly checkable; the field carries it but cannot make it so.
