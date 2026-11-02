#!/usr/bin/env python3
"""nano_anchor.py - anchor a document hash in a Nano block, and check someone else's anchor. Read-only; no seed.

Why: a receipt's date is only as good as the clock of whoever wrote it. A Nano block's position in an account chain
(height) and the network's confirmation are a date the author does not set. Nano has no memo field, so the hash rides
in the one 32-byte field a state block lets its owner choose freely: the REPRESENTATIVE. A 32-byte representative is an
account public key; any 32 bytes (a SHA-256) encodes to a valid-looking `nano_` address.

  anchor-address SHA256_HEX            -> the nano_ address to set as representative in a change block (or any state block)
  decode ADDRESS                       -> the 32 bytes (hex) inside an address
  check BLOCK_HASH SHA256_HEX [RPC]    -> reads the block; settled only if its representative decodes to that hash and the
                                          block is confirmed; prints height and the node's local_timestamp
  check-file BLOCK_HASH FILE [RPC]     -> same, hashing FILE with SHA-256 first

Honest limits, printed in the output as `limits`:
 - the owner of the anchoring account signs the block (this tool only reads: sending the block is a wallet step);
 - local_timestamp is when the node you asked first saw the block, not a signed time; the order of blocks (height and
   the frontier chain) is what cannot be backdated;
 - the representative of an account also carries weight in voting if it is online, so anchor from an account whose
   balance you accept delegating to an arbitrary key (a small throwaway account does: an unknown key holds no vote);
 - one anchor per block; to anchor many hashes, anchor the Merkle root of the batch.
Exit codes: 0 anchored, 3 not this hash / not confirmed-as-anchor, 4 node unreachable, 64 usage.
"""
import hashlib, json, sys, urllib.request, urllib.error

ALPHA = "13456789abcdefghijkmnopqrstuwxyz"
DEFAULT_RPC = "https://rpc.nano.to"
LIMITS = ["the account owner signs the anchoring block", "local_timestamp is the asked node's own first-seen clock",
          "representative carries voting weight if the account has balance", "one hash per block; anchor a Merkle root for many"]


def _checksum(pub):
    return hashlib.blake2b(pub, digest_size=5).digest()[::-1]


def _b32(n, length):
    return "".join(ALPHA[(n >> (5 * (length - 1 - i))) & 31] for i in range(length))


def encode(pub):
    if len(pub) != 32:
        raise ValueError("need 32 bytes")
    return "nano_" + _b32(int.from_bytes(pub, "big"), 52) + _b32(int.from_bytes(_checksum(pub), "big"), 8)


def decode(addr):
    if not (addr.startswith("nano_") or addr.startswith("xrb_")):
        raise ValueError("not a nano address")
    body = addr.split("_", 1)[1]
    if len(body) != 60 or any(c not in ALPHA for c in body):
        raise ValueError("bad address body")
    n = 0
    for c in body[:52]:
        n = n * 32 + ALPHA.index(c)
    if n >> 256:
        raise ValueError("bad address: top bits set")
    pub = n.to_bytes(32, "big")
    if encode(pub)[5:] != body:
        raise ValueError("checksum mismatch")
    return pub


def anchor_address(sha256_hex):
    h = sha256_hex.strip().lower()
    if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        raise ValueError("need 64 hex characters")
    return encode(bytes.fromhex(h))


def _rpc(rpc, block, opener=urllib.request.urlopen):
    body = json.dumps({"action": "block_info", "json_block": "true", "hash": block}).encode()
    req = urllib.request.Request(rpc, body, {"Content-Type": "application/json", "User-Agent": "nano-anchor"})
    with opener(req, timeout=15) as r:
        return json.load(r)


def check(block, sha256_hex, rpc=DEFAULT_RPC, fetch=_rpc):
    """Return (exit_code, dict)."""
    try:
        want = anchor_address(sha256_hex)
    except ValueError as e:
        return 64, {"anchored": False, "verdict": "usage", "detail": str(e)}
    try:
        info = fetch(rpc, block)
    except (urllib.error.URLError, OSError, ValueError):
        return 4, {"anchored": False, "verdict": "node_unreachable"}
    if "error" in info:
        return 3, {"anchored": False, "verdict": "no_such_block"}
    c = info.get("contents", {})
    out = {"block": block.upper(), "account": info.get("block_account"), "height": info.get("height"),
           "local_timestamp": info.get("local_timestamp"), "confirmed": info.get("confirmed") == "true",
           "expected_representative": want, "representative": c.get("representative"), "limits": LIMITS}
    if c.get("type") != "state" or c.get("representative") != want:
        out.update(anchored=False, verdict="different_hash")
        return 3, out
    if not out["confirmed"]:
        out.update(anchored=False, verdict="unconfirmed")
        return 3, out
    out.update(anchored=True, verdict="anchored")
    return 0, out


def main(argv):
    if len(argv) >= 3 and argv[1] == "anchor-address":
        try:
            print(anchor_address(argv[2])); return 0
        except ValueError as e:
            print(e, file=sys.stderr); return 64
    if len(argv) >= 3 and argv[1] == "decode":
        try:
            print(decode(argv[2]).hex()); return 0
        except ValueError as e:
            print(e, file=sys.stderr); return 64
    if len(argv) >= 4 and argv[1] in ("check", "check-file"):
        h = argv[3]
        if argv[1] == "check-file":
            try:
                h = hashlib.sha256(open(argv[3], "rb").read()).hexdigest()
            except OSError as e:
                print(e, file=sys.stderr); return 64
        code, out = check(argv[2], h, argv[4] if len(argv) > 4 else DEFAULT_RPC)
        print(json.dumps(out)); return code
    print(__doc__.split("\n\n")[0] + "\nusage: nano_anchor.py anchor-address|decode|check|check-file ...", file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv))
