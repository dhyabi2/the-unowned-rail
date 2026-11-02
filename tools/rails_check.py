#!/usr/bin/env python3
"""rails_check.py - read an agent identity document and list the Nano payment rail it declares, checking only what can be checked.

Works on (a) an ERC-8004 registration file (services[] entry named "wallet" whose endpoint is "nano:<address>") and
(b) an A2A agent card (capabilities.extensions[] entry whose params.payments.nano has an address). Offline, stdlib,
read-only. It validates the declaration's SHAPE (Nano address checksum, network spelling, min_raw integer string); it
cannot tell you the agent delivers anything - a declared address says where to pay, not that service follows.

    python3 tools/rails_check.py registration.json     # exit 0 = at least one valid nano rail, 1 = none/invalid
    python3 tools/rails_check.py --example             # the built-in sample, no file needed
"""
import hashlib, json, re, sys

ALPHA = "13456789abcdefghijkmnopqrstuwxyz"
NETWORKS = {"nano:mainnet", "nano-mainnet"}   # x402 sellers emit both spellings; accept both


def address_ok(a):
    m = re.fullmatch(r"nano_([13][%s]{51})([%s]{8})" % (ALPHA, ALPHA), a or "")
    if not m:
        return False
    n = 0
    for c in m.group(1):
        n = (n << 5) | _i(c)
    key = (n & ((1 << 256) - 1)).to_bytes(32, "big")
    chk = 0
    for c in m.group(2):
        chk = (chk << 5) | _i(c)
    return hashlib.blake2b(key, digest_size=5).digest()[::-1] == chk.to_bytes(5, "big")


def _i(c):
    return ALPHA.index(c)


def _rail(addr, network, min_raw, where):
    probs = []
    if not address_ok(addr):
        probs.append("address fails the Nano checksum")
    if network is not None and network not in NETWORKS:
        probs.append("network %r is not nano:mainnet" % network)
    if min_raw is not None and not (isinstance(min_raw, str) and re.fullmatch(r"[1-9][0-9]{0,40}", min_raw)):
        probs.append("min_raw must be a decimal integer string of raw")
    return {"where": where, "address": addr, "network": network or "nano:mainnet", "min_raw": min_raw, "problems": probs}


def rails(doc):
    out = []
    for s in doc.get("services") or doc.get("endpoints") or []:
        if isinstance(s, dict) and s.get("name") == "wallet" and str(s.get("endpoint", "")).startswith("nano:"):
            out.append(_rail(str(s["endpoint"])[5:], s.get("network"), s.get("min_raw"), "services[wallet]"))
    for e in (doc.get("capabilities") or {}).get("extensions") or []:
        n = (((e or {}).get("params") or {}).get("payments") or {}).get("nano")
        if isinstance(n, dict):
            out.append(_rail(n.get("address"), n.get("network"), n.get("min_raw"), "capabilities.extensions[%s]" % (e.get("uri") or "?")))
    return out


EXAMPLE = {"services": [{"name": "wallet", "endpoint": "nano:nano_3aysuejus8iy1hhw6doc7syzg1aaa6hgpec91xcc36mf6hp6thy7u6ymkgfm",
                         "version": "v1", "network": "nano:mainnet", "min_raw": "100000000000000000000000000"}]}

if __name__ == "__main__":
    # `--example` checks the built-in registration file (feeless402's live payTo), so one line runs with no input file.
    r = rails(EXAMPLE if sys.argv[1:] == ["--example"] else json.load(open(sys.argv[1])))
    print(json.dumps(r, indent=1))
    sys.exit(0 if any(not x["problems"] for x in r) else 1)
