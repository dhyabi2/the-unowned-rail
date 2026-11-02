#!/usr/bin/env python3
"""starter_policy.py - what to do when an UNSOLICITED Nano payment lands on your address. Read-only, stdlib only.

The decision is a function of the BLOCK (public, checkable) and the ENVELOPE (a claim, never proof). It never sends,
never replies, never signs. 1 XNO = 10**30 raw; every amount is an integer string.

  python3 starter_policy.py --address nano_... --block HASH [--envelope env.json] [--cap-xno 0.001] [--node URL,URL]
  python3 starter_policy.py --address nano_... --block-file block.json            # offline, a saved block_info reply

Outputs one JSON object: {"decision": ..., "reasons": [...], "envelope_status": ..., "obligation": "none"}.
Decisions:
  receive_and_record  confirmed send to you, at or under your cap: pocket it, write one ledger line, owe nothing.
  hold                valid but over the cap, or not yet confirmed, or the envelope asks for something: do nothing
                      until a person who owns the wallet decides.
  ignore              not a send to you, wrong amount for the claim, or below your own dust floor.
Rules that never change: (1) a payment creates no obligation; (2) an envelope field such as `intent: gift` is a CLAIM and is
reported as such, never as verified; (3) nothing is sent back automatically.
"""
import argparse, json, sys, urllib.request

NODES = ["https://rainstorm.city/api", "https://node.somenano.com/proxy", "https://nanoslo.0x.no/proxy"]
UA = {"Content-Type": "application/json", "User-Agent": "starter-policy/1.0"}
XNO = 10 ** 30
INTENTS = ("gift", "payment_for_behaviour", "reputation_seeding", "test")
DEFAULT_CAP_RAW = XNO // 1000   # 0.001 XNO: an amount you can absorb without a human
DEFAULT_DUST_RAW = XNO // 10 ** 8  # 0.00000001 XNO


def fetch_block(h, nodes):
    last = None
    for n in nodes:
        try:
            r = urllib.request.Request(n, json.dumps({"action": "block_info", "json_block": "true", "hash": h}).encode(), UA)
            d = json.load(urllib.request.urlopen(r, timeout=25))
            if "error" in d:
                last = d["error"]; continue
            return d
        except Exception as e:
            last = type(e).__name__
    raise RuntimeError("no node answered: %s" % last)


def decide(block, address, envelope=None, cap_raw=DEFAULT_CAP_RAW, dust_raw=DEFAULT_DUST_RAW):
    reasons = []
    c = block.get("contents") if isinstance(block.get("contents"), dict) else {}
    amount_s = str(block.get("amount", ""))
    if not amount_s.isdigit():
        return {"decision": "ignore", "reasons": ["amount missing or not an integer"], "envelope_status": "unchecked", "obligation": "none"}
    amount = int(amount_s)
    out = {"block_hash_amount_raw": amount_s, "sender": block.get("block_account"), "obligation": "none"}
    if block.get("subtype") != "send" or c.get("link_as_account") != address:
        return dict(out, decision="ignore", reasons=["not a confirmed-or-pending send whose link is your address"], envelope_status="unchecked")
    if amount < dust_raw:
        return dict(out, decision="ignore", reasons=["below your dust floor %d raw" % dust_raw], envelope_status="unchecked")
    env_status = "none_given"
    env_problems = []
    if envelope is not None:
        env_status = "claim_unverified"
        if envelope.get("amount_raw") not in (None, amount_s):
            env_problems.append("envelope amount_raw %s differs from the block's %s" % (envelope.get("amount_raw"), amount_s)); env_status = "contradicted_by_block"
        if envelope.get("recipient") not in (None, address):
            env_problems.append("envelope recipient is not your address"); env_status = "contradicted_by_block"
        if envelope.get("sender") not in (None, block.get("block_account")):
            env_problems.append("envelope sender differs from the block's block_account"); env_status = "contradicted_by_block"
        if envelope.get("intent") not in (None,) + INTENTS:
            env_problems.append("unknown intent %r; known: %s" % (envelope.get("intent"), ", ".join(INTENTS)))
        if envelope.get("asks") :
            env_problems.append("envelope asks for something (%s): a request is not a payment term" % envelope.get("asks"))
    out["envelope_status"] = env_status
    if env_status == "contradicted_by_block":
        return dict(out, decision="ignore", reasons=env_problems)
    if block.get("confirmed") != "true":
        return dict(out, decision="hold", reasons=["block not confirmed by the node that answered; ask again or a second node"] + env_problems)
    if amount > cap_raw or env_problems:
        return dict(out, decision="hold", reasons=(["amount %s raw is over your cap %d raw" % (amount_s, cap_raw)] if amount > cap_raw else []) + env_problems)
    reasons.append("confirmed send to your address, %s raw, at or under your cap" % amount_s)
    if envelope is not None:
        reasons.append("envelope intent %r is the sender's claim and is not verified by this check" % envelope.get("intent"))
    return dict(out, decision="receive_and_record", reasons=reasons)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--address", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--block"); g.add_argument("--block-file")
    ap.add_argument("--envelope"); ap.add_argument("--cap-xno", type=float)
    ap.add_argument("--node")
    a = ap.parse_args(argv)
    cap = DEFAULT_CAP_RAW if a.cap_xno is None else int(round(a.cap_xno * 10 ** 9)) * 10 ** 21
    blk = json.load(open(a.block_file)) if a.block_file else fetch_block(a.block, a.node.split(",") if a.node else NODES)
    env = json.load(open(a.envelope)) if a.envelope else None
    res = decide(blk, a.address, env, cap)
    print(json.dumps(res, indent=1))
    return 0 if res["decision"] == "receive_and_record" else 2


if __name__ == "__main__":
    sys.exit(main())
