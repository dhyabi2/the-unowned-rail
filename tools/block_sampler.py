#!/usr/bin/env python3
"""Sample block_count of a public Nano RPC node on an interval and report whether
`unchecked` ever moves and whether count keeps pace with cemented. Read-only, stdlib.
  python3 block_sampler.py --samples 61 --interval 60 --out samples.jsonl
  python3 block_sampler.py --summarize samples.jsonl
"""
import argparse, json, time, urllib.request, datetime as dt

def read(node):
    req = urllib.request.Request(node, data=b'{"action":"block_count"}',
        headers={"content-type": "application/json", "user-agent": "block-sampler/1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

def summarize(rows):
    ok = [r for r in rows if "unchecked" in r]
    if not ok: return {"samples": len(rows), "ok": 0}
    u = [int(r["unchecked"]) for r in ok]; c = [int(r["count"]) for r in ok]; ce = [int(r["cemented"]) for r in ok]
    gap = [a - b for a, b in zip(c, ce)]
    return {"samples": len(rows), "ok": len(ok), "failed": len(rows) - len(ok),
            "first": ok[0]["t"], "last": ok[-1]["t"],
            "unchecked_min": min(u), "unchecked_max": max(u), "unchecked_distinct": len(set(u)),
            "unchecked_changed": len(set(u)) > 1,
            "count_start": c[0], "count_end": c[-1], "blocks_added": c[-1] - c[0],
            "count_minus_cemented_min": min(gap), "count_minus_cemented_max": max(gap)}

if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--node", default="https://rpc.nano.to"); a.add_argument("--samples", type=int, default=61)
    a.add_argument("--interval", type=float, default=60); a.add_argument("--out", default="samples.jsonl")
    a.add_argument("--summarize")
    o = a.parse_args()
    if o.summarize:
        print(json.dumps(summarize([json.loads(l) for l in open(o.summarize) if l.strip()]), indent=1)); raise SystemExit
    with open(o.out, "a") as f:
        for i in range(o.samples):
            t = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            try: r = read(o.node); r["t"] = t
            except Exception as e: r = {"t": t, "error": str(e)[:80]}
            f.write(json.dumps(r) + "\n"); f.flush()
            if i < o.samples - 1: time.sleep(o.interval)
