#!/usr/bin/env python3
"""xno_verify_quorum.py BLOCK_HASH EXPECT_RAW ACCOUNT [--nodes URL,URL,...] [--agree 2]

Read-only. Holds no key, sends nothing. Stdlib only. Asks public Nano nodes in order, skips one that cannot be reached
or read (failover), and answers SETTLED only when `agree` nodes report the same confirmed send of at least EXPECT_RAW
to ACCOUNT. Exit 0 settled, 1 refused (a node says it is not that payment), 2 not enough nodes answered (UNKNOWN, not "unpaid"),
3 nodes contradict each other. 1 XNO = 10^30 raw; compare integers.
"""
import json, sys, urllib.request, argparse

NODES = ["https://rainstorm.city/api", "https://rpc.nano.to", "https://node.somenano.com/proxy",
         "https://nanoslo.0x.no/proxy", "https://app.natrium.io/api", "https://rpc.nano-gpt.com"]


def ask(url, h):
    r = urllib.request.Request(url, json.dumps({"action": "block_info", "json_block": "true", "hash": h}).encode(),
                               {"Content-Type": "application/json", "User-Agent": "xno-verify-quorum/1.0"})
    d = json.load(urllib.request.urlopen(r, timeout=25))
    if "contents" not in d:
        return {"found": False, "err": str(d.get("error", d))[:60]}
    c = d["contents"]
    return {"found": True, "confirmed": d.get("confirmed") == "true", "subtype": d.get("subtype"),
            "amount": int(d["amount"]), "dest": c.get("link_as_account")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hash"); ap.add_argument("expect_raw", type=int); ap.add_argument("account")
    ap.add_argument("--nodes", default=""); ap.add_argument("--agree", type=int, default=2)
    a = ap.parse_args()
    nodes = [n for n in a.nodes.split(",") if n] or NODES
    ok, no, skipped = [], [], []
    for u in nodes:
        try:
            v = ask(u, a.hash)
        except Exception as e:
            skipped.append((u, type(e).__name__)); continue
        good = v["found"] and v["confirmed"] and v["subtype"] == "send" and v["dest"] == a.account and v["amount"] >= a.expect_raw
        (ok if good else no).append((u, v))
        if len(ok) >= a.agree:
            break
    print(json.dumps({"settled": len(ok) >= a.agree, "agreeing": [u for u, _ in ok], "refusing": [(u, v) for u, v in no],
                      "skipped_unreachable": skipped}))
    if len(ok) >= a.agree: sys.exit(0)
    if ok and no: sys.exit(3)
    if no and not ok and len(no) >= a.agree: sys.exit(1)
    sys.exit(2)


if __name__ == "__main__":
    main()
