#!/usr/bin/env python3
"""receipt_field_check.py - validate an optional settlement_receipt object (schema/settlement-receipt.schema.json).

Offline (default): shape, nano_ address checksum, 64-hex hash, integer-raw amount.
--online: also one read-only block_info on a public node: confirmed, amount equals amount_raw, block links to payee.
Holds no key, sends nothing.

    python3 tools/receipt_field_check.py receipt.json [--online] [--node URL]
Exit 0 valid, 1 invalid or not confirmed, 2 node unreadable (never read that as invalid).
"""
import json, re, sys, urllib.request

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from rails_check import address_ok  # noqa: E402

NODE = "https://rpc.nano.to"
KEYS = {"rail", "ref", "payee", "amount_raw", "verify"}


def shape(r):
    p = []
    if not isinstance(r, dict):
        return ["not an object"]
    for k in r:
        if k not in KEYS:
            p.append("unknown field " + k)
    if r.get("rail") not in ("nano:mainnet", "stripe", "other"):
        p.append("rail must be nano:mainnet, stripe or other")
    if not r.get("ref"):
        p.append("ref missing")
    if r.get("rail") == "nano:mainnet":
        if not re.fullmatch(r"[0-9A-Fa-f]{64}", r.get("ref") or ""):
            p.append("ref must be a 64-hex block hash")
        if not address_ok(r.get("payee")):
            p.append("payee is not a valid nano_ address")
        if not re.fullmatch(r"[0-9]{1,40}", str(r.get("amount_raw", ""))):
            p.append("amount_raw must be an integer string")
    return p


def rpc(node, body, timeout=20):
    req = urllib.request.Request(node, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "user-agent": "Mozilla/5.0 receipt-field-check/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def online(r, node=NODE, call=rpc):
    d = call(node, {"action": "block_info", "json_block": "true", "hash": r["ref"]})
    if "error" in d:
        return ["node says: " + str(d["error"])[:60]]
    p = []
    if d.get("confirmed") != "true":
        p.append("block not confirmed (yet)")
    if str(d.get("amount")) != str(r["amount_raw"]):
        p.append("amount on chain %s differs from amount_raw" % d.get("amount"))
    link = (d.get("contents") or {}).get("link_as_account")
    if link != r["payee"]:
        p.append("block does not send to payee")
    return p


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    node = argv[argv.index("--node") + 1] if "--node" in argv else NODE
    if "--node" in argv:
        args.remove(node)
    r = json.load(open(args[0]))
    p = shape(r)
    if not p and "--online" in argv and r["rail"] == "nano:mainnet":
        try:
            p = online(r, node)
        except Exception as e:  # noqa
            print("# unreadable:", str(e)[:80]); return 2
    for x in p:
        print("PROBLEM", x)
    print("# settlement_receipt", "valid" if not p else "INVALID")
    return 1 if p else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
