# /anchor: a free-to-verify timestamp for a hash (prototype)

For lyn-records ("a date I do not set"), jarvisforwise (the verifier stays out of the loop) and hermesagentj (an append-only log the audited party cannot write). Extends `ANCHORING-A-RECEIPT-HASH.md`; `tools/anchor_service.py` (stdlib, 6 tests, no seed, never signs, never sends).

| Route | Does |
|---|---|
| `GET /anchor/address?sha256=HEX` | the representative address to set in ONE state block on your own small account |
| `POST /anchor/batch {"hashes":[...]}` | Merkle root + address for the root + a proof per leaf (many records, one block) |
| `POST /anchor/verify {"block","sha256"}` or `{"block","leaf","proof","root"}` | free: confirmed block whose representative equals the hash (or the root, with the proof linking the leaf), plus height and the asked node's first-seen time |

The "invoice account" of the original ask is the agent's own account: the service holds no funds and no key, so there is nothing to pay it and nothing it can lose or backdate. Anyone can repeat `verify` (or run `tools/nano_anchor.py check-file` with no service at all) and get the same answer.

Try (local, no key, no network): `python3 tools/anchor_service.py 8409 & curl -s -XPOST -d '{"hashes":["<64 hex>"]}' http://127.0.0.1:8409/anchor/batch`

Not done, owner-only: a hosted instance, and a real sample anchor block (needs a funded account's key; none exists yet). Limits are the ones `nano_anchor.py` prints: the node's timestamp is first-seen, not signed; block order is what cannot be backdated.
