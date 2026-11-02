#!/usr/bin/env python3
"""Nano cement-lag sampler. Stdlib only, read-only (block_count), holds no key, sends nothing.

Public RPCs do not allow confirmation_history, and we hold no wallet to send a probe block, so a true
send->confirm time is not measurable from outside. What IS measurable from outside, with read-only calls:

  cement lag (blocks)   = count - cemented, per node, per sample
  cement rate (blk/s)   = delta(cemented) / delta(time) between samples
  cement lag (seconds)  = lag_blocks / cement_rate   (Little's law: queue length / throughput)
  round trip (s)        = wall time of the HTTPS request, from this machine

Usage:
  python3 nano_latency.py --minutes 5 --interval 5 --out run.jsonl     # collect
  python3 nano_latency.py --report run.jsonl                           # p50/p90 per node
  python3 nano_latency.py --hours 24 --interval 30 --out day.jsonl     # the 24 h run (cron/tmux it)
"""
import argparse, json, sys, time, urllib.request, statistics, collections

NODES = ["https://rainstorm.city/api", "https://rpc.nano-gpt.com", "https://node.somenano.com/proxy",
         "https://app.natrium.io/api"]


def call(url, body, timeout=20):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "user-agent": "Mozilla/5.0 nano-latency/1"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    return d, time.time() - t0


def sample(nodes):
    rows = []
    for u in nodes:
        try:
            d, rtt = call(u, {"action": "block_count"})
            rows.append({"t": time.time(), "node": u, "count": int(d["count"]), "cemented": int(d["cemented"]),
                         "unchecked": int(d.get("unchecked", 0)), "rtt": round(rtt, 3)})
        except Exception as e:
            rows.append({"t": time.time(), "node": u, "error": str(e)[:80]})
    return rows


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def report(path):
    by = collections.defaultdict(list)
    for line in open(path):
        r = json.loads(line)
        by[r["node"]].append(r)
    out = {}
    for n, rs in by.items():
        ok = [r for r in rs if "error" not in r]
        lag_blocks = [r["count"] - r["cemented"] for r in ok]
        rtt = [r["rtt"] for r in ok]
        lag_s = []
        for a, b in zip(ok, ok[1:]):
            dt, dc = b["t"] - a["t"], b["cemented"] - a["cemented"]
            if dt > 0 and dc > 0:
                lag_s.append((b["count"] - b["cemented"]) / (dc / dt))
        out[n] = {"samples_ok": len(ok), "samples_total": len(rs),
                  "rtt_s_p50_p90": [pct(rtt, 50), pct(rtt, 90)],
                  "cement_lag_blocks_p50_p90": [pct(lag_blocks, 50), pct(lag_blocks, 90)],
                  "cement_lag_s_p50_p90": [pct(lag_s, 50), pct(lag_s, 90)],
                  "cement_rate_blk_s_median": (statistics.median(
                      [(b["cemented"] - a["cemented"]) / (b["t"] - a["t"]) for a, b in zip(ok, ok[1:]) if b["t"] > a["t"]]) if len(ok) > 1 else None)}
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float)
    ap.add_argument("--hours", type=float)
    ap.add_argument("--interval", type=float, default=10)
    ap.add_argument("--out")
    ap.add_argument("--report")
    ap.add_argument("--nodes")
    a = ap.parse_args()
    if a.report:
        return report(a.report)
    nodes = a.nodes.split(",") if a.nodes else NODES
    secs = (a.hours or 0) * 3600 + (a.minutes or 0) * 60
    if not secs or not a.out:
        sys.exit("need --minutes or --hours, and --out")
    end = time.time() + secs
    with open(a.out, "a") as f:
        while time.time() < end:
            for r in sample(nodes):
                f.write(json.dumps(r) + "\n")
            f.flush()
            time.sleep(a.interval)


if __name__ == "__main__":
    main()
