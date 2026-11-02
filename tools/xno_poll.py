#!/usr/bin/env python3
"""xno_poll.py - see payments to YOUR address using OUTBOUND https only. Stdlib only. Holds no key, sends nothing.

  python3 xno_poll.py ADDRESS                     # one look: confirmed receivable + received blocks
  python3 xno_poll.py ADDRESS --watch 30          # look every 30 s, print only what is new
  python3 xno_poll.py ADDRESS --expect-raw N      # exit 0 if a confirmed payment of >= N raw is visible, else 1
  python3 xno_poll.py ADDRESS --nodes URL,URL,..  # your own list (default: three independent public nodes)

No inbound port, no webhook, no public URL of yours: the sandbox only needs to reach the nodes. Nodes are tried in
order and the next is used only when one is unreachable (a node that answers "nothing" is an answer, not a fault).
1 XNO = 10^30 raw. A block shown here is `confirmed` by the node that answered; ask a second node (the default list
does) before you hand over something you cannot take back.
"""
import json, sys, time, urllib.request, argparse

NODES = ["https://rainstorm.city/api", "https://rpc.nano.to", "https://node.somenano.com/proxy"]
UA = {"Content-Type": "application/json", "User-Agent": "xno-poll/1.0"}  # some nodes answer 403 to the default urllib UA


def rpc(nodes, body, timeout=25):
    errs = []
    for u in nodes:
        try:
            r = urllib.request.Request(u, json.dumps(body).encode(), UA)
            d = json.load(urllib.request.urlopen(r, timeout=timeout))
            if isinstance(d, dict) and "error" in d and d["error"] != "Account not found":
                errs.append((u, d["error"])); continue
            return u, d
        except Exception as e:
            errs.append((u, type(e).__name__))
    raise SystemExit("no node answered: %r" % (errs,))


def look(addr, nodes, thr="1"):
    u, rec = rpc(nodes, {"action": "receivable", "account": addr, "count": "50", "threshold": thr,
                         "source": "true", "include_only_confirmed": "true"})
    pend = rec.get("blocks") or {}
    if pend == "":
        pend = {}
    got = []
    u2, h = rpc(nodes, {"action": "account_history", "account": addr, "count": "50"})
    for b in (h.get("history") or []):
        if b.get("type") in ("receive", "state") and b.get("subtype", "receive") == "receive":
            got.append({"hash": b["hash"], "from": b.get("account"), "raw": b["amount"], "at": b.get("local_timestamp")})
    return u, [{"hash": k, "from": v["source"], "raw": v["amount"]} for k, v in pend.items()], got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("address"); ap.add_argument("--watch", type=int, default=0)
    ap.add_argument("--expect-raw", type=int, default=0); ap.add_argument("--nodes", default="")
    a = ap.parse_args()
    nodes = [n for n in a.nodes.split(",") if n] or NODES
    seen = set()
    while True:
        node, pend, got = look(a.address, nodes)
        new = [("receivable", p) for p in pend if p["hash"] not in seen] + [("received", g) for g in got if g["hash"] not in seen]
        for kind, p in new:
            seen.add(p["hash"])
            print(json.dumps({"kind": kind, "node": node, **p}), flush=True)
        total = sum(int(p["raw"]) for p in pend) + sum(int(g["raw"]) for g in got)
        if a.expect_raw:
            ok = any(int(p["raw"]) >= a.expect_raw for p in pend + got)
            if ok or not a.watch:
                sys.exit(0 if ok else 1)
        if not a.watch:
            if not new: print(json.dumps({"kind": "nothing_new", "node": node, "confirmed_receivable": len(pend), "received_blocks_seen": len(got)}))
            return
        time.sleep(a.watch)


if __name__ == "__main__":
    main()
