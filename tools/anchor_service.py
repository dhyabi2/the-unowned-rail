#!/usr/bin/env python3
"""anchor_service.py - a /anchor HTTP prototype for record-keeping agents. Stdlib, no seed, sends nothing.

The service never signs. It does the two parts that need no key and leaves the one that does to the account owner:
  GET  /anchor/address?sha256=HEX        -> the representative address to put in ONE state block (the anchor)
  POST /anchor/batch   {"hashes":[hex..]} -> Merkle root, the address for the root, and a proof per leaf
  POST /anchor/verify  {"block":HASH, "sha256":HEX | "leaf":HEX,"proof":[...],"root":HEX}
                                          -> free check: block confirmed, representative == hash (or == Merkle root and the
                                             proof links leaf to root), with height and the node's first-seen timestamp
Flow: agent hashes its record -> GET address -> publishes a change block on its own small account with that representative
-> POST verify with the block hash; anyone else can repeat the verify and gets the same answer without trusting us.
Run: python3 anchor_service.py [port]   (binds 127.0.0.1; put TLS in front)
Reuses nano_anchor.py for address encoding and the block check.
"""
import hashlib, json, os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nano_anchor as NA

HEX = set("0123456789abcdef")


def _h(b): return hashlib.sha256(b).digest()


def merkle(leaves_hex):
    """Root and proofs. Leaves are sha256 hex strings; node = sha256(0x01|left|right), leaf = sha256(0x00|bytes)."""
    if not leaves_hex: raise ValueError("no hashes")
    for x in leaves_hex:
        if len(x) != 64 or set(x.lower()) - HEX: raise ValueError("each hash must be 64 hex")
    level = [_h(b"\x00" + bytes.fromhex(x)) for x in leaves_hex]
    paths = [[] for _ in leaves_hex]
    idx = list(range(len(level)))              # position of each original leaf in the current level
    while len(level) > 1:
        if len(level) % 2: level = level + [level[-1]]
        for i, pos in enumerate(idx):
            sib = pos ^ 1
            paths[i].append({"side": "left" if sib < pos else "right", "hash": level[sib].hex()})
        level = [_h(b"\x01" + level[i] + level[i + 1]) for i in range(0, len(level), 2)]
        idx = [p // 2 for p in idx]
    return level[0].hex(), paths


def prove(leaf_hex, proof, root_hex):
    node = _h(b"\x00" + bytes.fromhex(leaf_hex))
    for step in proof:
        sib = bytes.fromhex(step["hash"])
        node = _h(b"\x01" + (sib + node if step["side"] == "left" else node + sib))
    return node.hex() == root_hex.lower()


def handle(method, path, body, fetch=NA._rpc, rpc=NA.DEFAULT_RPC):
    u = urlparse(path)
    try:
        if method == "GET" and u.path == "/anchor/address":
            h = parse_qs(u.query).get("sha256", [""])[0]
            return 200, {"representative": NA.anchor_address(h), "do": "publish one state/change block on your own small account with this representative, then POST /anchor/verify with its hash", "limits": NA.LIMITS}
        if method == "POST" and u.path == "/anchor/batch":
            root, paths = merkle(body["hashes"])
            return 200, {"root": root, "representative": NA.anchor_address(root),
                         "leaves": [{"sha256": h, "proof": p} for h, p in zip(body["hashes"], paths)], "limits": NA.LIMITS}
        if method == "POST" and u.path == "/anchor/verify":
            if "sha256" in body:
                code, out = NA.check(body["block"], body["sha256"], rpc, fetch)
                return 200, dict(out, exit_code=code)
            if not prove(body["leaf"], body["proof"], body["root"]):
                return 200, {"anchored": False, "verdict": "proof_does_not_reach_root"}
            code, out = NA.check(body["block"], body["root"], rpc, fetch)
            return 200, dict(out, exit_code=code, leaf=body["leaf"], via="merkle_proof")
        return 404, {"error": "unknown route"}
    except (ValueError, KeyError, TypeError) as e:
        return 400, {"error": str(e)}


class H(BaseHTTPRequestHandler):
    def _go(self, method):
        n = int(self.headers.get("Content-Length") or 0)
        try: body = json.loads(self.rfile.read(n) or b"{}") if method == "POST" else {}
        except ValueError: body = None
        code, out = (400, {"error": "bad json"}) if body is None else handle(method, self.path, body)
        data = json.dumps(out).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self): self._go("GET")
    def do_POST(self): self._go("POST")
    def log_message(self, *a): pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8409), H).serve_forever()
