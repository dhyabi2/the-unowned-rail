# Nano Payment Handler

* **Handler Name:** `io.github.dhyabi2.nano`
* **Version:** `2026-11-20`

## Introduction

This handler lets a UCP business accept payment by one confirmed Nano send block on `nano:mainnet`, for the exact
amount the business quoted on the checkout. The buyer's own wallet sends the block; the platform passes only the
block hash; the business reads the block from its own node and credits it once. Nano blocks settle without a fee and
confirm in about a second, which suits machine buyers that pay per checkout.

It is a self-hosted handler built on UCP's `payment_handler` and `payment_instrument` extension points, following
`docs/specification/payment/template.md` and the conformance checklist in `guide.md` (UCP main `1be6f77`). It needs
no change to UCP core.

### Key Benefits

* No processor account, no API key and no card data: the business needs only a Nano account and a node it trusts.
* Exact amounts in raw (1 XNO = 10^30 raw), compared as integers, so there is no rounding or tolerance.
* A block is credited to one checkout, once, in a durable store, so a block cannot pay twice, even across restarts.

### Integration Guide

| Participant  | Integration Section                           |
| :----------- | :-------------------------------------------- |
| **Business** | [Business Integration](#business-integration) |
| **Platform** | [Platform Integration](#platform-integration) |

---

## Participants

| Participant       | Role                                                        | Prerequisites                                    |
| :---------------- | :---------------------------------------------------------- | :----------------------------------------------- |
| **Business**      | Quotes `amount_raw`, verifies the block, records the credit | Yes — a Nano account and its own node RPC URL    |
| **Platform**      | Reads the quote, has the buyer's wallet pay, submits the hash | No                                              |
| **Buyer wallet**  | Signs and publishes one send block with the buyer's own key | Yes — a funded Nano account                      |

```text
+---------+        +--------------+        +----------+       +-----------+
|Platform |        | Buyer wallet |        |Nano node |       | Business  |
+----+----+        +------+-------+        +----+-----+       +-----+-----+
     |  checkout: response_config (amount_raw, pay_to, expires_at)  |
     |<-------------------------------------------------------------|
     |  pay amount_raw    |                     |                   |
     |  to pay_to         |                     |                   |
     |------------------->|  send block         |                   |
     |                    |-------------------->|                   |
     |  block hash        |                     |                   |
     |<-------------------|                     |                   |
     |  complete checkout: instrument nano_block (block_hash)       |
     |------------------------------------------------------------->|
     |                    |                     |  blocks_info      |
     |                    |                     |<------------------|
     |  checkout result                                             |
     |<-------------------------------------------------------------|
```

---

## Business Integration

### Prerequisites

Before advertising this handler, businesses **MUST** have:

1. A Nano account to receive payments (`pay_to`). Only its address is configured; its key never touches the handler.
2. The RPC URL of a Nano node the business trusts (its own, or one it chose). This URL is configuration on the
   business side only. It is never advertised, and a node named by a platform or buyer is never used.
3. A durable store for credited block hashes (`verify.py` uses SQLite).

**Prerequisites Output:**

| Field      | Description                                          |
| :--------- | :--------------------------------------------------- |
| `pay_to`   | The business's Nano account, checksum-valid          |
| node URL   | Private configuration of the processor, not in UCP   |

### Handler Configuration

Businesses advertise support for this handler in their UCP profile's `payment_handlers` registry.

#### Handler Schema

**Schema URL:** `https://raw.githubusercontent.com/dhyabi2/the-unowned-rail/main/ucp/nano-handler/schema.json`

| Config Variant    | Context            | Purpose                                                     |
| :---------------- | :----------------- | :---------------------------------------------------------- |
| `business_config` | Business discovery | Network and receiving account                               |
| `platform_config` | Platform discovery | None required                                               |
| `response_config` | Checkout responses | The per-checkout quote: exact `amount_raw`, `quote_id`, expiry |

The instrument is `instrument.json` (`nano_block`) and its credential is `credential.json` (`nano_send_block`).

#### Business Config Fields

| Field               | Type    | Required | Description                                                     |
| :------------------ | :------ | :------- | :-------------------------------------------------------------- |
| `network`           | string  | Yes      | Always `nano:mainnet`                                           |
| `pay_to`            | string  | Yes      | `nano_` account; processors **MUST** check its blake2b checksum |
| `min_confirmation`  | string  | No       | Always `confirmed` (default)                                    |
| `quote_ttl_seconds` | integer | No       | 60 to 86400, default 900                                        |

#### Response Config Fields

| Field        | Type   | Required | Description                                                                 |
| :----------- | :----- | :------- | :-------------------------------------------------------------------------- |
| `amount_raw` | string | Yes      | Exact amount in raw, digits only, unique among this business's open quotes  |
| `amount_xno` | string | No       | Display only, derived from `amount_raw`; never used for checking            |
| `quote_id`   | string | Yes      | Equals the checkout id                                                      |
| `expires_at` | string | Yes      | RFC 3339                                                                    |

The business config fields are repeated in the response config.

#### Example Handler Declaration

```json
{
  "ucp": {
    "payment_handlers": {
      "io.github.dhyabi2.nano": [
        {
          "id": "nano_mainnet_1",
          "version": "2026-11-20",
          "spec": "https://raw.githubusercontent.com/dhyabi2/the-unowned-rail/main/ucp/nano-handler/README.md",
          "schema": "https://raw.githubusercontent.com/dhyabi2/the-unowned-rail/main/ucp/nano-handler/schema.json",
          "available_instruments": [{ "type": "nano_block" }],
          "config": {
            "network": "nano:mainnet",
            "pay_to": "nano_16aj46aj46aj46aj46aj46aj46aj46aj46aj46aj46aj46aj46ajbtsyew7c",
            "min_confirmation": "confirmed",
            "quote_ttl_seconds": 900
          }
        }
      ]
    }
  }
}
```

(The `pay_to` above is a checksum-valid example account made from a public test key; use your own.)

### Processing Payments

Upon receiving a payment with this handler's instrument, businesses **MUST**, in this order (the first failing rule
decides; `verify.py` is the reference):

1. **Validate Handler:** `instrument.handler_id` names an advertised handler, `instrument.type` is `nano_block`,
   `credential.type` is `nano_send_block`, and `block_hash` matches `^[0-9A-F]{64}$`.
2. **Ensure Idempotency:** if `block_hash` already credited THIS checkout, return the earlier result unchanged.
3. **Read the block:** `blocks_info` (`json_block`, `source`) from the business's own node: the block exists,
   `subtype` is `send`, `confirmed` is `"true"`.
4. **Destination:** `contents.link_as_account` (or `contents.link` decoded) is `config.pay_to`.
5. **Amount:** `amount` (raw) equals the quote's `amount_raw` exactly, compared as integers, never as floats.
6. **Expiry:** the block's `local_timestamp` is not after `expires_at` plus 60 seconds.
7. **Replay:** `block_hash` is not credited to any other checkout (durable seen store).
8. **Record, then answer:** store `block_hash -> checkout id` before returning success.

Success result:

```json
{ "status": "succeeded", "network": "nano:mainnet", "block_hash": "<hash>", "amount_raw": "3000000000000000000000000000", "payer": "nano_..." }
```

Failures are UCP messages with `type: "error"` and `code: "payment_failed"`:

| Case                                | severity               | content                                                 |
| :---------------------------------- | :--------------------- | :------------------------------------------------------ |
| bad hash shape                      | `recoverable`          | "Nano block hash is not 64 hex characters."             |
| unknown handler / instrument type   | `recoverable`          | "Nano instrument does not name an advertised handler."  |
| block not found yet / not confirmed | `recoverable`          | "Nano block is not confirmed yet; retry."               |
| wrong destination or not a send     | `requires_buyer_input` | "Nano block does not pay this business's account."      |
| amount differs from quote           | `requires_buyer_input` | "Nano block amount does not match the quote exactly."   |
| quote expired                       | `requires_buyer_input` | "Nano quote expired; request a new checkout total."     |
| block already credited elsewhere    | `unrecoverable`        | "Nano block was already used for another checkout."     |
| own node unreachable or bad answer  | `recoverable`          | "Payment could not be checked right now; retry."        |

```python
from verify import NanoHandler, SeenStore, http_rpc, make_quote

handler = NanoHandler("nano_mainnet_1", config, http_rpc(OWN_NODE_URL), SeenStore("/var/lib/shop/nano-seen.sqlite"))
quote = make_quote(checkout["id"], amount_raw, expires_at, open_amounts_raw=amounts_of_open_quotes)
result = handler.verify(checkout, instrument, quote)
```

---

## Platform Integration

### Prerequisites

None. The buyer's own wallet holds the buyer's key; the platform never does.

### Handler Configuration

Platforms advertise support by listing `io.github.dhyabi2.nano` in their profile's `payment_handlers`. No
`platform_config` field is required.

#### Example Platform Handler Declaration

```json
{
  "ucp": {
    "payment_handlers": {
      "io.github.dhyabi2.nano": [
        {
          "id": "nano_mainnet_1",
          "version": "2026-11-20",
          "spec": "https://raw.githubusercontent.com/dhyabi2/the-unowned-rail/main/ucp/nano-handler/README.md",
          "schema": "https://raw.githubusercontent.com/dhyabi2/the-unowned-rail/main/ucp/nano-handler/schema.json",
          "available_instruments": [{ "type": "nano_block" }],
          "config": {}
        }
      ]
    }
  }
}
```

### Payment Protocol

#### Step 1: Discover Handler

The platform finds `io.github.dhyabi2.nano` in the business's `/.well-known/ucp` profile.

#### Step 2: Read the Quote

From the checkout's handler `response_config`, read `amount_raw`, `pay_to` and `expires_at`. Refuse if `network` is
not `nano:mainnet` or `expires_at` has passed.

#### Step 3: Pay

The buyer's wallet sends exactly `amount_raw` raw to `pay_to` in one send block and returns the block hash.

#### Step 4: Complete Checkout

```json
POST /checkout-sessions/{checkout_id}/complete
Content-Type: application/json

{
  "payment": {
    "instruments": [
      {
        "id": "instr_1",
        "handler_id": "nano_mainnet_1",
        "type": "nano_block",
        "credential": { "type": "nano_send_block", "block_hash": "<64 upper-case hex>" },
        "display": { "network": "nano:mainnet", "amount_xno": "0.003" }
      }
    ]
  }
}
```

A `recoverable` answer may be retried with the same instrument; a `requires_buyer_input` answer needs a new quote or
payment; an `unrecoverable` answer must not be retried with that block.

---

## Security Considerations

| Requirement            | Description                                                                                                                                                                                  |
| :--------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Binding required**   | The credential is bound to the checkout (`binding` type `checkout`, its `id`) by the business's own record `quote_id -> amount_raw`. A block can satisfy only the quote whose exact `amount_raw` it carries; Nano blocks carry no memo, so nothing else is claimed. |
| **Binding verified**   | The processor refuses a quote whose `quote_id` is not the checkout id, and `amount_raw` is unique among open quotes, so one block matches one open quote.                                    |
| **Single use**         | A block hash is credited once ever, in a durable store, recorded before success is returned. The store's primary key refuses a second credit even under concurrent requests.              |
| **Expiry**             | A block later than `expires_at` plus 60 seconds is refused; the buyer asks for a new total.                                                                                                |
| **Own node**           | The business verifies with a node it configured. A node URL from a platform or a buyer is never used, and none is advertised.                                                              |
| **No keys**            | The handler reads public blocks only. No key, seed or signature of the business or the buyer is handled.                                                                                   |
| **Data residency**     | No personal data is processed; a Nano account and a block hash are public ledger data.                                                                                                     |

---

## Files and tests

| File               | What it is                                                                       |
| :----------------- | :------------------------------------------------------------------------------- |
| `schema.json`      | Handler schema: `business_config`, `platform_config`, `response_config`, variants |
| `instrument.json`  | `nano_block` instrument, `allOf` UCP `payment_instrument.json`                   |
| `credential.json`  | `nano_send_block` credential, `allOf` UCP `payment_credential.json`              |
| `verify.py`        | Reference processor, Python standard library only                                |
| `tests/`           | Offline tests against recorded node answers and a pinned copy of UCP's schemas    |

```sh
pip install jsonschema          # only for the schema tests; the rest is standard library
python3 -m unittest discover -s tests -v
```

`tests/ucp-1be6f77/` is an unmodified copy of the schemas from Universal-Commerce-Protocol/ucp at commit `1be6f77`
(Apache License 2.0), used to resolve `$ref`s offline.

## References

* **Handler Spec:** `https://raw.githubusercontent.com/dhyabi2/the-unowned-rail/main/ucp/nano-handler/README.md`
* **Handler Schema:** `https://raw.githubusercontent.com/dhyabi2/the-unowned-rail/main/ucp/nano-handler/schema.json`
* **Nano RPC `blocks_info`:** `https://docs.nano.org/commands/rpc-protocol/#blocks_info`
