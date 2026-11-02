#!/usr/bin/env python3
"""mutate_fixture.py - a public URL whose body really changes, with a log a tester can compare against.

Closes Copperglass QA's open gap on the URL-integrity checker: "No false change found; an actual mutation at the same URL
remains untested." The body of fixtures/mutating/body.txt changes each time this runs; the sha256 of every body ever
served is appended to fixtures/mutating/log.jsonl BEFORE the commit, so a tester can read the log and check that the
checker's content_hash equals the logged hash for the state it saw, and differs after a mutation.

    python3 tools/mutate_fixture.py            # write the next state and log it (then commit and push it)
    python3 tools/mutate_fixture.py --show     # print the current body hash and log length
Stdlib only; touches nothing outside fixtures/mutating/.
"""
import datetime, hashlib, json, os, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "mutating")
BODY, LOG = os.path.join(D, "body.txt"), os.path.join(D, "log.jsonl")


def log_rows():
    return [json.loads(l) for l in open(LOG)] if os.path.exists(LOG) else []


def step(now=None):
    rows = log_rows()
    n = len(rows) + 1
    stamp = (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = "mutating fixture state %d, written %s\n" % (n, stamp)
    row = {"state": n, "written_at": stamp, "sha256": hashlib.sha256(body.encode()).hexdigest(), "bytes": len(body.encode())}
    os.makedirs(D, exist_ok=True)
    open(BODY, "w").write(body)
    open(LOG, "a").write(json.dumps(row) + "\n")
    return row


def main(argv):
    if "--show" in argv:
        cur = hashlib.sha256(open(BODY, "rb").read()).hexdigest() if os.path.exists(BODY) else None
        rows = log_rows()
        print(json.dumps({"states_logged": len(rows), "body_sha256": cur, "matches_last_log": bool(rows and rows[-1]["sha256"] == cur)}))
        return 0
    print(json.dumps(step()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
