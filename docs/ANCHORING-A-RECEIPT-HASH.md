# Anchor a receipt hash in a Nano block

For a record-keeping agent whose receipt carries a date it set itself. Nano has no memo field, so the hash goes in
the one 32-byte field of a state block that the account owner chooses freely: the **representative**.

1. Hash the receipt: `sha256sum receipt.json` (64 hex characters).
2. Turn the hash into an address: `python3 tools/nano_anchor.py anchor-address <sha256>` prints a `nano_` address whose 32
   bytes are your hash.
3. Publish one **change block** on a small account of yours with that address as representative (any wallet that lets
   you set a representative; a change block moves no funds; a send or receive block with that representative works too).
   Signing is the account owner's step; this repo has no seed and sends nothing.
4. Publish the block hash next to the receipt.
5. Anyone re-checks, read-only: `python3 tools/nano_anchor.py check-file <block-hash> receipt.json`
   (exit 0 and `"anchored": true` with `height`, `confirmed` and the node's `local_timestamp`).

Why it is worth the step: the position of a block in its chain and the network's confirmation are not set by the
author or by any platform clock; the next pull of the same record can be anchored too, so the diff between two pulls
becomes a chain of dated hashes.

Limits (the tool prints them too): `local_timestamp` is the asked node's own first-seen time, not a signed time, so
read it on two nodes if the second matters; the representative of an account with balance carries voting weight, so
use a small account (an unknown key holds no votes); one hash per block, so anchor a Merkle root for a batch.

Checked 2026-11-02: addresses of three real accounts round-trip through `decode`/`encode` unchanged (11 tests,
`tests/test_anchor.py`), and `check-file` against a real confirmed block correctly answers `different_hash` with
its height and timestamp. **No anchoring block of ours exists yet**: publishing one needs a funded account's key, which
is the owner's step, so there is no sample block to point at.
