"""nano-fetch WebFetch hook - when a WebFetch call meets HTTP 402 with a Nano (XNO) price, pay it once and hand
the paid answer to the agent.

A Claude Code PostToolUse hook (hooks/hooks.json, matcher WebFetch). Standard library only, no key and no seed:
the payment is made by the operator's signer, the same contract as fetch.py. It reads the hook input JSON on
stdin:

    {"hook_event_name": "PostToolUse", "tool_name": "WebFetch", "tool_input": {"url": ...}, "tool_response": ...}

WebFetch's result carries no response headers, so the quote cannot be read from it. When the result names a
402, the hook requests the URL once more itself (fetch.fetch: the quote reader, the per-call cap, the budget
summed over the journal, an fsynced intent line before the signer, replay refused from the journal across
restarts) and, when paid, writes the paid body into `hookSpecificOutput.additionalContext`.

Off unless configured, from the environment (for example the `env` block of the operator's settings.json):

    NANO_FETCH_SIGNER   module.attr of the operator's signer (found on PYTHONPATH)
    NANO_FETCH_JOURNAL  the JSON-lines journal file, kept between sessions
    NANO_FETCH_CAP_RAW  per-call cap in raw (1 XNO = 10**30 raw); default: fetch.py's
    NANO_FETCH_BUDGET_RAW  total over the journal in raw; default 10 x the cap
    NANO_FETCH_MAX_CHARS   how much of the paid body goes into the context; default 20000

With the signer or the journal unset, a 402 is reported in one line, no request is made and nothing is paid.
Only bound orders (xno-binding/v1/rep) are paid; a send-hash quote is never paid from the hook.

Always exits 0: a hook error never blocks the session. Output: nothing, or one JSON object on stdout.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from fetch import fetch  # noqa: E402  (next to this file)
from middleware import DEFAULT_CAP_RAW, load_signer  # noqa: E402

# How a failed WebFetch names the status; a page that merely contains "402" is not a 402.
STATUS_402 = re.compile(r"status(?: code)?:? ?402\b|\b402 Payment Required\b|\bHTTP(?:/[0-9.]+)? 402\b", re.I)
DIGITS = re.compile(r"^[0-9]+$")


def met_402(tool_response):
    text = tool_response if isinstance(tool_response, str) else json.dumps(tool_response)
    return bool(STATUS_402.search(text or ""))


def same_scheme_as_webfetch(url):
    """WebFetch upgrades http to https, so the 402 it met came over https: ask the same place, never pay over
    plain http. Loopback stays as given (a seller on this machine, as in the tests)."""
    host = urllib.parse.urlsplit(url).hostname or ""
    if url.startswith("http://") and host not in ("127.0.0.1", "localhost", "::1"):
        return "https://" + url[len("http://"):]
    return url


def _context(text):
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}


def decide(event, env, opener=None):
    """The hook's answer for one event: None (say nothing) or the output object."""
    if not isinstance(event, dict) or event.get("hook_event_name") != "PostToolUse" \
            or event.get("tool_name") != "WebFetch":
        return None
    url = (event.get("tool_input") or {}).get("url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return None
    if not met_402(event.get("tool_response")):
        return None
    url = same_scheme_as_webfetch(url)
    spec, journal = env.get("NANO_FETCH_SIGNER"), env.get("NANO_FETCH_JOURNAL")
    if not spec or not journal:
        return _context("nano-fetch: WebFetch met HTTP 402 at %s. The hook is not configured "
                        "(NANO_FETCH_SIGNER and NANO_FETCH_JOURNAL), so nothing was requested or paid." % url)
    cap = env.get("NANO_FETCH_CAP_RAW") or DEFAULT_CAP_RAW
    budget = env.get("NANO_FETCH_BUDGET_RAW") or None
    for name, value in (("NANO_FETCH_CAP_RAW", cap), ("NANO_FETCH_BUDGET_RAW", budget)):
        if value is not None and not DIGITS.match(str(value)):
            return _context("nano-fetch: %s is not a raw amount in digits; nothing was paid." % name)
    try:
        signer = load_signer(spec)
    except Exception as e:  # noqa: BLE001 - an unloadable signer is never a payment
        return _context("nano-fetch: cannot load signer %r (%s); nothing was paid." % (spec, e))
    try:
        r = fetch(url, signer=signer, journal_path=journal, cap_raw=cap, budget_raw=budget, opener=opener)
    except (urllib.error.URLError, OSError, ValueError) as e:
        return _context("nano-fetch: the 402 at %s could not be requested again (%s); nothing was paid." % (url, e))
    if r.status != 402 and not r.paid:
        return None  # the URL no longer asks to be paid; WebFetch's own result stands
    if not r.paid:
        code, detail = r.refusal or ("not_paid", "")
        return _context("nano-fetch: HTTP 402 at %s not paid: %s (%s)." % (url, code, detail))
    head = "nano-fetch paid the HTTP 402 at %s: %s raw, block %s, proof in %s." % (
        url, r.paid["amount_raw"], r.paid["blockHash"], r.paid["header"])
    if r.status == 402:
        return _context(head + " The paid retry met 402 again; not paying twice. Report the block to the "
                        "operator.")
    try:
        limit = int(env.get("NANO_FETCH_MAX_CHARS") or 20000)
    except ValueError:
        limit = 20000
    text = r.body.decode("utf-8", "replace")
    cut = " (first %d characters)" % limit if len(text) > limit else ""
    return _context("%s The paid answer, HTTP %d%s, follows; WebFetch's result above is the unpaid 402.\n\n%s"
                    % (head, r.status, cut, text[:limit]))


def main(stdin=None, stdout=None, env=None, opener=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    env = os.environ if env is None else env
    try:
        event = json.loads(stdin.read() or "null")
    except ValueError:
        return 0
    try:
        out = decide(event, env, opener=opener)
    except Exception as e:  # noqa: BLE001 - never block the session
        out = _context("nano-fetch hook error: %s; nothing more was done." % e)
    if out is not None:
        stdout.write(json.dumps(out))
        stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
