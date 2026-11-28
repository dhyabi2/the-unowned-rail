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

MCP mode (`--mcp SERVER TOOL [--args JSON]`): the same payer for a paid MCP tool over the
Streamable HTTP transport. It sends initialize, notifications/initialized and tools/call to SERVER (JSON or
text/event-stream answers; the Mcp-Session-Id it is given is sent back). A tool result with isError true and
an x402 PaymentRequired (v1 or v2) in structuredContent or content[0].text is the 402. It is paid through the
same settle_402 (quote reader, cap, budget, journal, replay refusal), and the same tools/call is sent once more
with params._meta["x402/payment"] = the PaymentPayload as a JSON object (coinbase/x402 specs/transports-v2/
mcp.md): a bound order (extra.binding xno-binding/v1/rep) with --signer as payload {orderId, blockHash} of the
published send, a plain exact accept with --block-signer as payload {block}. xmcp >= 1.4.0 settles both
(verify.ts:284-292, fixtures/xmcp-loop.json L4-L6). xmcp's v1 offer names its network "nano"; that one name is
read as nano:mainnet only when the accept carries xmcp's own extra {name: XNO, decimals: 30}, and the payment
sent back keeps the seller's own name. Redirects are not followed in MCP mode, so the payment reaches SERVER only.

    python3 fetch.py URL [--signer mywallet.sign] [--journal pay.jsonl]
        [--cap-raw N] [--budget-raw N] [--allow-unbound] [--block-signer mywallet.sign_block]
        [--invoice-body JSON] [-X METHOD] [-H 'Name: value']... [-d DATA]
        [-o FILE] [--timeout S]
    python3 fetch.py --mcp SERVER TOOL [--args JSON] [--signer ...] [--journal ...]
        [--block-signer ...] [--cap-raw N] [--budget-raw N] [-H 'Name: value']... [-o FILE] [--timeout S]

Exit: 0 a 2xx/3xx answer (paid or not), 1 any other HTTP status or a connection error, 2 usage,
3 a 402 not paid (refusal named on stderr), 4 the paid retry met 402 again.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
from middleware import DEFAULT_CAP_RAW, Journal, load_signer, settle_402, settle_invoice  # noqa: E402  (next to this file)
from xno_buyer_plan.plan import MCP_PAYMENT_META, XMCP_NANO_EXTRA, mcp_payment_required, mcp_settlement


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


# --- MCP mode ---------------------------------------------------------------------------------------------
MCP_PROTOCOL_VERSION = "2025-06-18"
MCP_ACCEPT = "application/json, text/event-stream"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 3xx is an answer, not a new place to send the payment to."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _rpc_message(headers, body, rid):
    """The JSON-RPC message with id rid from a JSON or text/event-stream answer, or None."""
    ctype = next((v for k, v in headers.items() if k.lower() == "content-type"), "")
    text = body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else str(body)
    docs = []
    if "text/event-stream" in ctype.lower():
        for event in text.replace("\r\n", "\n").split("\n\n"):
            data = "\n".join(ln[5:].lstrip(" ") for ln in event.split("\n") if ln.startswith("data:"))
            if data:
                try:
                    docs.append(json.loads(data))
                except (ValueError, RecursionError):
                    continue
    else:
        try:
            docs.append(json.loads(text))
        except (ValueError, RecursionError):
            return None
    for d in docs:
        for m in (d if isinstance(d, list) else [d]):
            if isinstance(m, dict) and m.get("id") == rid and ("result" in m or "error" in m):
                return m
    return None


class McpSession:
    """One Streamable HTTP MCP session: POST JSON-RPC to one URL, keep the Mcp-Session-Id it hands out."""

    def __init__(self, url, headers=None, timeout=30, opener=None):
        self.url, self.timeout = url, timeout
        self.opener = opener or urllib.request.build_opener(_NoRedirect)
        self.headers = dict(headers or {})
        self.session_id = None
        self.next_id = 0

    def _post(self, doc):
        h = dict(self.headers, **{"Content-Type": "application/json", "Accept": MCP_ACCEPT,
                                  "MCP-Protocol-Version": MCP_PROTOCOL_VERSION})
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        status, rh, body = _request(self.url, "POST", h, json.dumps(doc).encode("utf-8"), self.timeout,
                                    self.opener)
        sid = next((v for k, v in rh.items() if k.lower() == "mcp-session-id"), None)
        if sid and self.session_id is None:
            self.session_id = sid
        return status, rh, body

    def request(self, method, params):
        """-> (status, headers, body, message or None)."""
        self.next_id += 1
        rid = self.next_id
        status, rh, body = self._post({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return status, rh, body, (_rpc_message(rh, body, rid) if 200 <= status < 300 else None)

    def notify(self, method):
        return self._post({"jsonrpc": "2.0", "method": method})[0]


class McpResult(Result):
    def __init__(self, status, headers, body, message=None, paid=None, refusal=None, settlement=None):
        super().__init__(status, headers, body, paid=paid, refusal=refusal)
        self.message = message        # the JSON-RPC answer to the (last) tools/call, or None
        self.settlement = settlement  # result._meta["x402/payment-response"] of a paid call

    @property
    def payment_required(self):
        return self.message is not None and mcp_payment_required(self.message)[0] is not None


def _xmcp_v1_nano(pr):
    """A copy of the PaymentRequired whose v1 accepts named "nano" with xmcp's own extra read as nano:mainnet
    (constants.ts NETWORKS.nano, verify.ts:96-109), and the names the seller wrote, by index."""
    accepts = pr.get("accepts") or []
    seen = [a.get("network") if isinstance(a, dict) else None for a in accepts]
    if pr.get("x402Version") != 1:
        return pr, seen
    out = []
    for a in accepts:
        extra = a.get("extra") if isinstance(a, dict) and isinstance(a.get("extra"), dict) else {}
        if (isinstance(a, dict) and a.get("network") == "nano"
                and all(extra.get(k) == v for k, v in XMCP_NANO_EXTRA.items())):
            a = dict(a, network="nano:mainnet")
        out.append(a)
    return dict(pr, accepts=out), seen


def _mcp_payment(header_value, pr, mapped, seen):
    """settle_402's base64 proof -> the PaymentPayload object for _meta, in the seller's own terms."""
    doc = json.loads(base64.b64decode(header_value).decode("utf-8"))
    if doc.get("x402Version") == 1:
        for a, name in zip(mapped.get("accepts") or [], seen):
            if isinstance(a, dict) and a.get("network") == doc.get("network") and name != a.get("network"):
                doc["network"] = name   # the seller's own name back ("nano" for xmcp v1)
                break
        return doc
    accepted = doc.get("accepted")
    for a, orig in zip(mapped.get("accepts") or [], pr.get("accepts") or []):
        if a == accepted:
            doc["accepted"] = orig
            break
    if "resource" in pr and "resource" not in doc:
        doc = dict({"x402Version": doc["x402Version"], "resource": pr["resource"]}, **doc)
    return doc


def mcp_call(server, tool, arguments=None, signer=None, journal_path=None, cap_raw=DEFAULT_CAP_RAW,
             budget_raw=None, headers=None, timeout=30, opener=None, block_signer=None):
    """Call one MCP tool; pay one Nano PaymentRequired when a signer (or block_signer) and journal are given."""
    s = McpSession(server, headers=headers, timeout=timeout, opener=opener)
    status, rh, body, msg = s.request("initialize", {
        "protocolVersion": MCP_PROTOCOL_VERSION, "capabilities": {},
        "clientInfo": {"name": "nano_fetch", "version": "0.2.0"}})
    if msg is None or "error" in msg:
        return McpResult(status, rh, body, message=msg)
    s.notify("notifications/initialized")
    params = {"name": tool, "arguments": dict(arguments or {})}
    status, rh, body, msg = s.request("tools/call", params)
    pr, _where = mcp_payment_required(msg) if msg is not None else (None, None)
    if pr is None:
        return McpResult(status, rh, body, message=msg)
    if (signer is None and block_signer is None) or not journal_path:
        return McpResult(status, rh, body, message=msg, refusal=(
            "not_configured", "a paid tool needs --signer (or --block-signer) and --journal; nothing was paid"))
    cap_raw = str(int(cap_raw))
    budget_raw = int(budget_raw) if budget_raw is not None else 10 * int(cap_raw)
    mapped, seen = _xmcp_v1_nano(pr)
    r = settle_402({}, json.dumps(mapped).encode("utf-8"), "mcp:%s#%s" % (server, tool), signer,
                   Journal(journal_path), cap_raw, budget_raw, block_signer=block_signer)
    if not r["ok"]:
        return McpResult(status, rh, body, message=msg, refusal=(r["error"], r["detail"]))
    payment = _mcp_payment(r["header"][1], pr, mapped, seen)
    plan = r["plan"]
    paid = {"orderId": plan.get("orderId"), "blockHash": r["blockHash"], "amount_raw": plan["amount_raw"],
            "header": "_meta[%s]" % MCP_PAYMENT_META}
    status, rh, body, msg = s.request("tools/call", dict(params, _meta={MCP_PAYMENT_META: payment}))
    res = McpResult(status, rh, body, message=msg, paid=paid,
                    settlement=mcp_settlement(msg) if msg is not None else None)
    if res.payment_required:
        res.refusal = ("paid_retry_402", "the paid tools/call asked for payment again; not paying twice")
    return res


def _mcp_exit(r):
    if r.message is None or "error" in r.message:
        return 1
    if r.payment_required:
        return 4 if r.paid else 3
    return 1 if (r.message.get("result") or {}).get("isError") is True else 0


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
    ap.add_argument("url", nargs="?")
    ap.add_argument("--mcp", nargs=2, metavar=("SERVER", "TOOL"),
                    help="call TOOL on the MCP server at SERVER (Streamable HTTP) instead of fetching a URL")
    ap.add_argument("--args", dest="tool_args", help="JSON object: the tool's arguments (with --mcp)")
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
    target = a.mcp[0] if a.mcp else a.url
    if (a.url is None) == (a.mcp is None):
        print("nano_fetch: give a URL, or --mcp SERVER TOOL, not both", file=err)
        return 2
    if not target.startswith(("http://", "https://")):
        print("nano_fetch: only http:// and https:// URLs", file=err)
        return 2
    arguments = None
    if a.mcp:
        try:
            arguments = json.loads(a.tool_args) if a.tool_args is not None else {}
        except ValueError:
            arguments = None
        if not isinstance(arguments, dict) or a.allow_unbound or a.invoice_body is not None \
                or a.data is not None or a.method is not None:
            print("nano_fetch: --mcp takes --args as a JSON object; --allow-unbound, --invoice-body, -d and -X "
                  "are for URLs", file=err)
            return 2
    elif a.tool_args is not None:
        print("nano_fetch: --args goes with --mcp", file=err)
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
        if a.mcp:
            r = mcp_call(a.mcp[0], a.mcp[1], arguments=arguments, signer=signer, journal_path=a.journal,
                         cap_raw=a.cap_raw, budget_raw=a.budget_raw, headers=dict(a.header), timeout=a.timeout,
                         block_signer=block_signer)
        else:
            r = fetch(a.url, signer=signer, journal_path=a.journal, cap_raw=a.cap_raw, budget_raw=a.budget_raw,
                      method=method, headers=dict(a.header), data=data, timeout=a.timeout,
                      allow_unbound=a.allow_unbound, block_signer=block_signer, invoice_body=invoice_body)
    except (urllib.error.URLError, OSError, ValueError) as e:
        print("nano_fetch: %s" % e, file=err)
        return 1
    if a.mcp:
        if r.paid:
            print("nano_fetch: paid %s raw, hash %s, presented in %s"
                  % (r.paid["amount_raw"], r.paid["blockHash"], r.paid["header"]), file=err)
        if r.refusal:
            print("nano_fetch: 402 not paid: %s (%s)" % r.refusal, file=err)
        body = r.body if r.message is None else (json.dumps(r.message, indent=1) + "\n").encode("utf-8")
        if a.output:
            with open(a.output, "wb") as f:
                f.write(body)
        else:
            out.write(body)
            out.flush()
        return _mcp_exit(r)
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
