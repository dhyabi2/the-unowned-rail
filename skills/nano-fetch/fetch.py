"""nano_fetch - fetch a URL; when it answers HTTP 402 with a Nano (XNO) quote, pay it once and retry.

A command-line payer for any agent that has a shell tool.
Standard library only. It never holds a key or a seed: the payment is made by a signer hook YOU supply
(`--signer module.attr`), the same contract as middleware.py:

    signer({"network", "payTo", "amount_raw", "representative", "orderId"}) -> 64-hex block hash

The signer publishes a send of amount_raw raw (1 XNO = 10**30 raw) to payTo, with `representative` as the
block's representative field when it is not None (the xno-binding/v1/rep order binding), waits until the
send is confirmed, and returns its hash.

Off unless configured: with no --signer (or --block-signer) and --journal a 402 is printed and the command exits 3; nothing is
paid. With both, the 402 goes through middleware.settle_402 (xno_buyer_plan's quote reader, the per-call cap,
the run budget summed over the journal, an fsynced intent line before the signer is called, replay refused
from the journal across restarts). Paid quotes:
  - x402 v2 bound order (PAYMENT-REQUIRED header, extra.binding xno-binding/v1/rep): retried with
    PAYMENT-SIGNATURE;
  - x402 v1 bound order (JSON body, maxAmountRequired): retried with X-PAYMENT;
  - a send-hash quote (pay first, present the hash in X-Nano-Payment or the header the quote names): only
    with --allow-unbound, since nothing in it binds the send to this one request;
  - a plain exact accept (x402nano/exact: payload.block, a signed send the seller's facilitator publishes):
    only with --block-signer, a second hook that signs and does NOT publish:

        block_signer({"network", "payTo", "amount_raw", "work_threshold"}) -> signed state send block (dict)

    The block's link must be payTo's key and it must carry a signature; its hash is computed here, not taken
    from the hook. The block reaches the seller inside this one request only.
  - a private-token invoice (the 402 names POST <create> and POST <result> paths on its own host): only with
    --signer and --invoice-body JSON, the order you are buying (e.g. '{"url": "https://www.gnu.org/"}'). It is
    POSTed to the create path; the invoice must name the 402's pay_to and network, a price no lower than the
    402's base and within the cap, a private token and an expires_at at least 2 minutes ahead. The signer
    publishes the exact price; then {invoice_id, payment_hash} is POSTed to the result path with
    Authorization: Bearer <token> (unredirected), again with the same invoice and hash on 202 or 503, at most
    3 times. The invoice id and token are journalled before the signer is called, so an invoice is never paid
    twice and a paid one can be redeemed by hand. Its own amount and token bind the payment to this order.
A paid retry that meets 402 again is returned as is (exit 4); one request never pays twice.

    python3 fetch.py URL [--signer mywallet.sign] [--journal pay.jsonl]
        [--cap-raw N] [--budget-raw N] [--allow-unbound] [--block-signer mywallet.sign_block]
        [--invoice-body JSON] [-X METHOD] [-H 'Name: value']... [-d DATA]
        [-o FILE] [--timeout S]

Exit: 0 a 2xx/3xx answer (paid or not), 1 any other HTTP status or a connection error, 2 usage,
3 a 402 not paid (refusal named on stderr), 4 the paid retry met 402 again.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
from middleware import DEFAULT_CAP_RAW, Journal, load_signer, settle_402, settle_invoice  # noqa: E402  (next to this file)


class Result:
    def __init__(self, status, headers, body, paid=None, refusal=None):
        self.status, self.headers, self.body = status, headers, body
        self.paid = paid          # {"orderId", "blockHash", "amount_raw", "header"} when a payment was made
        self.refusal = refusal    # (code, detail) when a 402 was not paid


def _request(url, method, headers, data, timeout, opener, proof=None):
    req = urllib.request.Request(url, data=data, method=method, headers=dict(headers))
    if proof is not None:
        # The payment proof goes to the URL that quoted the price and nowhere else: an unredirected header is
        # not copied onto a redirect (urllib copies ordinary headers to any host a 3xx names).
        req.add_unredirected_header(*proof)
    try:
        resp = opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:  # 402 and every other non-2xx arrive here
        body = e.read()
        return e.code, {k: v for k, v in e.headers.items()}, body
    with resp:
        return resp.status, {k: v for k, v in resp.headers.items()}, resp.read()


INVOICE_RESULT_TRIES = 3
JSON_HEADERS = {"Content-Type": "application/json"}


def _same_origin(a, b):
    x, y = urllib.parse.urlsplit(a), urllib.parse.urlsplit(b)
    return (x.scheme, x.netloc) == (y.scheme, y.netloc)


def _retry_after(body):
    try:
        s = json.loads(body).get("retry_after_seconds")
    except (ValueError, AttributeError):
        s = None
    return min(s, 10) if isinstance(s, int) and not isinstance(s, bool) and s > 0 else 5


def _pay_invoice(quote, url, plan, invoice_body, signer, journal, cap_raw, budget_raw, timeout, opener,
                 now, sleep):
    """An invoice quote: create the invoice, pay it once, present the hash. quote is the 402 (status,
    headers, body); it is what comes back, with the refusal, whenever nothing was paid."""
    create, result = plan.get("invoice_create"), plan.get("invoice_result")
    if not create or not result:
        return Result(*quote, refusal=("invoice_paths", "the 402 names no create and result paths"))
    create_url, result_url = urllib.parse.urljoin(url, create), urllib.parse.urljoin(url, result)
    if not (_same_origin(url, create_url) and _same_origin(url, result_url)):
        return Result(*quote, refusal=("invoice_offsite", "the invoice paths leave the host that quoted the price"))
    status, _rh, body = _request(create_url, "POST", JSON_HEADERS, invoice_body, timeout, opener)
    if status not in (200, 201):
        return Result(*quote, refusal=("invoice_not_created", "POST %s answered %d: %s"
                                       % (create, status, body[:200].decode("utf-8", "replace"))))
    try:
        invoice = json.loads(body)
    except ValueError:
        invoice = None
    s = settle_invoice(plan, invoice, url, signer, journal, cap_raw, budget_raw, now())
    if not s["ok"]:
        return Result(*quote, refusal=(s["error"], s["detail"]))
    paid = {"orderId": s["invoice_id"], "blockHash": s["blockHash"], "amount_raw": s["amount_raw"],
            "header": "Authorization"}
    for attempt in range(INVOICE_RESULT_TRIES):
        status, rh, body = _request(result_url, "POST", JSON_HEADERS, s["body"], timeout, opener, proof=s["auth"])
        if status not in (202, 503) or attempt == INVOICE_RESULT_TRIES - 1:
            break
        sleep(_retry_after(body))  # the same invoice and hash again: never a second payment
    refusal = None
    if status == 402:
        refusal = ("paid_retry_402", "the result request met 402 after paying; not paying twice for one invoice")
    return Result(status, rh, body, paid=paid, refusal=refusal)


def fetch(url, signer=None, journal_path=None, cap_raw=DEFAULT_CAP_RAW, budget_raw=None, method="GET",
          headers=None, data=None, timeout=30, allow_unbound=False, opener=None, block_signer=None,
          invoice_body=None, now=time.time, sleep=time.sleep):
    """Fetch url; pay one Nano 402 when a signer (or block_signer) and journal_path are given. Returns a Result."""
    opener = opener or urllib.request.build_opener()
    headers = dict(headers or {})
    status, rh, body = _request(url, method, headers, data, timeout, opener)
    if status != 402:
        return Result(status, rh, body)
    if (signer is None and block_signer is None) or not journal_path:
        return Result(status, rh, body, refusal=("not_configured", "a 402 needs --signer (or --block-signer) "
                                                 "and --journal to be paid; nothing was paid"))
    cap_raw = str(int(cap_raw))
    budget_raw = int(budget_raw) if budget_raw is not None else 10 * int(cap_raw)
    journal = Journal(journal_path)
    r = settle_402(rh, body, url, signer, journal, cap_raw, budget_raw,
                   allow_unbound=allow_unbound, block_signer=block_signer)
    if not r["ok"] and r["error"] == "invoice_flow" and invoice_body is not None and signer is not None:
        return _pay_invoice((status, rh, body), url, r["plan"], invoice_body, signer, journal, cap_raw,
                            budget_raw, timeout, opener, now, sleep)
    if not r["ok"]:
        return Result(status, rh, body, refusal=(r["error"], r["detail"]))
    name, value = r["header"]
    plan = r["plan"]
    paid = {"orderId": plan.get("orderId"), "blockHash": r["blockHash"], "amount_raw": plan["amount_raw"],
            "header": name}
    status, rh, body = _request(url, method, headers, data, timeout, opener, proof=(name, value))
    refusal = None
    if status == 402:
        refusal = ("paid_retry_402", "the paid retry met 402 again; not paying twice for one request")
    return Result(status, rh, body, paid=paid, refusal=refusal)


def _parse_header(text):
    name, sep, value = text.partition(":")
    if not sep or not name.strip():
        raise argparse.ArgumentTypeError("header %r is not 'Name: value'" % text)
    return name.strip(), value.strip()


def _digits(text):
    if not text.isascii() or not text.isdigit():
        raise argparse.ArgumentTypeError("%r is not a raw amount in digits (1 XNO = 10**30 raw)" % text)
    return text


def main(argv=None, out=None, err=None):
    out = out or sys.stdout.buffer
    err = err or sys.stderr
    ap = argparse.ArgumentParser(prog="nano_fetch", description=__doc__.split("\n\n")[0])
    ap.add_argument("url")
    ap.add_argument("--signer", help="module.attr of your signer; the key lives only there")
    ap.add_argument("--journal", help="JSON-lines journal file; replays are refused from it across runs")
    ap.add_argument("--cap-raw", type=_digits, default=DEFAULT_CAP_RAW, help="per-call cap in raw")
    ap.add_argument("--budget-raw", type=_digits, help="total over the journal in raw (default 10 x cap)")
    ap.add_argument("--allow-unbound", action="store_true", help="also pay a send-hash quote (no binding)")
    ap.add_argument("--block-signer", help="module.attr that signs (never publishes) a send block: pays a plain "
                    "exact accept")
    ap.add_argument("--invoice-body", help="JSON object: the order to buy from an invoice quote (with --signer)")
    ap.add_argument("-X", "--request", dest="method", default=None)
    ap.add_argument("-H", "--header", action="append", type=_parse_header, default=[])
    ap.add_argument("-d", "--data")
    ap.add_argument("-o", "--output")
    ap.add_argument("--timeout", type=float, default=30)
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if not a.url.startswith(("http://", "https://")):
        print("nano_fetch: only http:// and https:// URLs", file=err)
        return 2
    if bool(a.signer or a.block_signer) != bool(a.journal):
        print("nano_fetch: --signer (or --block-signer) and --journal go together (a payment without a journal "
              "could repeat)", file=err)
        return 2
    try:
        signer = load_signer(a.signer) if a.signer else None
        block_signer = load_signer(a.block_signer) if a.block_signer else None
    except Exception as e:  # noqa: BLE001 - an unloadable signer is a usage error, never a payment
        print("nano_fetch: cannot load signer %r: %s" % (a.signer or a.block_signer, e), file=err)
        return 2
    invoice_body = None
    if a.invoice_body is not None:
        try:
            ok = isinstance(json.loads(a.invoice_body), dict)
        except ValueError:
            ok = False
        if not ok or not a.signer:
            print("nano_fetch: --invoice-body is a JSON object and needs --signer (a send is published)", file=err)
            return 2
        invoice_body = a.invoice_body.encode("utf-8")
    data = a.data.encode("utf-8") if a.data is not None else None
    method = a.method or ("POST" if data is not None else "GET")
    try:
        r = fetch(a.url, signer=signer, journal_path=a.journal, cap_raw=a.cap_raw, budget_raw=a.budget_raw,
                  method=method, headers=dict(a.header), data=data, timeout=a.timeout,
                  allow_unbound=a.allow_unbound, block_signer=block_signer, invoice_body=invoice_body)
    except (urllib.error.URLError, OSError, ValueError) as e:
        print("nano_fetch: %s" % e, file=err)
        return 1
    if r.paid:
        print("nano_fetch: paid %s raw, hash %s, presented in %s"
              % (r.paid["amount_raw"], r.paid["blockHash"], r.paid["header"]), file=err)
    if r.refusal:
        print("nano_fetch: 402 not paid: %s (%s)" % r.refusal, file=err)
    if a.output:
        with open(a.output, "wb") as f:
            f.write(r.body)
    else:
        out.write(r.body)
        out.flush()
    if r.status == 402:
        return 4 if r.paid else 3
    return 0 if 200 <= r.status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
