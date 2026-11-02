#!/usr/bin/env python3
"""blocker_counts.py - why do outside agents who ANSWERED not move? (IMPACT-BACKLOG 3025)

Reads a directory of conversation JSON files (agent-conversations shape) and tags each agent with the blockers it
named IN ITS OWN WORDS (`discussions.agent_answered`, never our notes). An agent can carry several tags; a tag is a
count of agents, not of sentences. Categories (the owner's list):
  no_wallet        it holds no wallet / cannot hold keys / cannot receive
  operator_decides a human operator or owner approves spend, terms or rails
  usdc_lockin      it is built on USDC / Base / Stripe / cards and says so as the reason
  conversion_cost  swap, spread, slippage, off-ramp or exchange friction is the objection
  verification     it wants proof first: a check, an explorer link, a receipt, "show me" before trusting

  python3 tools/blocker_counts.py --dir CONVERSATIONS [--md OUT.md] [--json OUT.json]

Keyword evidence only: a regex hit is a candidate, so the report prints one quoted sample line per tag and the
untagged count. Stdlib only; reads files, writes only --md/--json.
"""
import argparse, collections, glob, json, os, re

CATS = collections.OrderedDict([
    ("no_wallet", re.compile(r"\b(?:no|not have a|do not (?:have|possess|hold)|don'?t (?:have|hold)|cannot hold|can'?t hold|"
                             r"without a?) (?:\w+ ){0,2}(?:wallet|keys?|funds)\b|\bcannot (?:receive|accept|hold)\b|"
                             r"\b(?:zero|no)[- ]capital\b|hold(?:s)? no (?:funds|keys|wallet)", re.I)),
    ("operator_decides", re.compile(r"\b(?:my|the) (?:operator|human|owner|principal|developer|creator)\b[^.]{0,60}"
                                    r"(?:decid|approv|control|authori[sz]|sign|configur|allow|choose|must)|"
                                    r"(?:operator|owner)[- ](?:decision|approval|gated?)|requires? (?:human|operator|owner) approval|"
                                    r"\bnot (?:my|the agent'?s) (?:call|decision)\b", re.I)),
    ("usdc_lockin", re.compile(r"\busdc\b|\bbase (?:l2|chain|network)\b|\bstripe\b|\bcredit card|\bfiat\b|\bsolana\b|\bethereum\b", re.I)),
    ("conversion_cost", re.compile(r"\b(?:swap|spread|slippage|off-?ramp|on-?ramp|exchange friction|conversion cost|"
                                   r"liquidity|bridg(?:e|ing)|convert(?:ing)? (?:xno|nano|to usdc|back))\b", re.I)),
    ("verification", re.compile(r"\b(?:verif(?:y|ied|iable|ication)|prove|proof|receipt|explorer|show me|"
                                r"can i check|how do i (?:check|trust))\b", re.I)),
])


def answer_text(conv):
    d = conv.get("discussions") or {}
    parts = [m.get("text", "") for m in d.get("agent_answered", []) if isinstance(m, dict)]
    for a in conv.get("agreements") or []:
        if isinstance(a, dict) and a.get("text"):
            parts.append(a["text"])
    return " ".join(parts).strip()


def tags_for(text):
    return [c for c, rx in CATS.items() if rx.search(text)]


def sample(text, rx, width=140):
    m = rx.search(text)
    if not m:
        return ""
    a = max(0, m.start() - width // 2)
    return " ".join(text[a:a + width].split())


def count(directory):
    n = answered = 0
    per = collections.Counter(); untagged = 0
    samples = {}
    for f in sorted(glob.glob(os.path.join(directory, "*.json"))):
        try:
            conv = json.load(open(f))
        except (OSError, ValueError):
            continue
        n += 1
        t = answer_text(conv)
        if not t:
            continue
        answered += 1
        tg = tags_for(t)
        if not tg:
            untagged += 1
        for c in tg:
            per[c] += 1
            samples.setdefault(c, (os.path.basename(f), sample(t, CATS[c])))
    return {"files": n, "answered": answered, "untagged": untagged,
            "tags": {c: per.get(c, 0) for c in CATS}, "samples": samples}


def render(r, label=""):
    L = ["# Why answering agents do not move: blocker counts" + (" (%s)" % label if label else ""), "",
         "%d conversation files, %d with agent text of their own, %d of those name none of the five blockers." %
         (r["files"], r["answered"], r["untagged"]), "",
         "| blocker | agents | share of answering |", "|---|---|---|"]
    for c, k in sorted(r["tags"].items(), key=lambda x: -x[1]):
        L.append("| %s | %d | %.0f%% |" % (c, k, 100.0 * k / max(1, r["answered"])))
    L += ["", "An agent can carry several tags. Keyword matching on the agent's own words: a hit is a candidate, not a",
          "finding. One quoted example per tag (file, then the words around the match):", ""]
    for c in CATS:
        if c in r["samples"]:
            f, s = r["samples"][c]
            L.append("- **%s** (`%s`): \"%s\"" % (c, f, s))
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", required=True); ap.add_argument("--md"); ap.add_argument("--json"); ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    r = count(a.dir)
    md = render(r, a.label)
    if a.md: open(a.md, "w").write(md)
    if a.json: json.dump({k: v for k, v in r.items() if k != "samples"}, open(a.json, "w"), indent=1)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
