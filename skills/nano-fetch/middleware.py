"""A Scrapy downloader middleware that pays a bound Nano (XNO) x402 order and retries the page.

In the nano-fetch skill folder it is also the settle core of fetch.py (Scrapy optional). Off unless NANO_PAY_ENABLED is set:
with it unset the middleware is never loaded (NotConfigured) and a 402 reaches the spider as before.

What it does with a 402 (and nothing else; every other status passes through untouched):
  1. xno_buyer_plan.plan_402 reads the quote (PAYMENT-REQUIRED header or JSON body) and returns a plan or a
     named refusal. Only a bound order (dialect "rep-binding", xno-binding/v1/rep as profullstack/x402-gateway
     0.18.2 offers it) is paid: its send names a representative derived from the orderId, payTo and amount,
     so the payment is bound to this one request. A plain exact accept is refused here (unbound).
  2. Spend checks: the per-page cap (NANO_PAY_CAP_RAW) inside plan_402, then the crawl budget
     (NANO_PAY_BUDGET_RAW) summed over the journal, restarts included.
  3. The journal (NANO_PAY_JOURNAL, a JSON-lines file, flushed and fsynced) gets an "intent" line BEFORE the
     signer is called and a "paid" line with the block hash after. Every key in it - intent or paid - is a
     replay to plan_402, so one order is never handed to the signer twice, across a crash or a restart.
  4. The signer hook (NANO_PAY_SIGNER: a callable or "module.attr") receives the order - payTo, amount_raw,
     representative, orderId, network - and returns the 64-hex hash of a send it published AND saw
     confirmed. The key lives only inside the operator's signer; this module never sees a key or a seed and
     makes no network call of its own.
  5. The request is re-issued once (dont_filter) with PAYMENT-SIGNATURE (x402 v2) or X-PAYMENT (v1): base64
     JSON {x402Version, accepted, payload: {orderId, blockHash}}. A paid retry that meets 402 again is
     returned to the spider as is: never a second payment for one request.

Amounts are raw (1 XNO = 10**30 raw), parsed from the quote as integers, never floats.
"""
import base64
import calendar
import importlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
from xno_buyer_plan.plan import DEFAULT_CAP_RAW, plan_402  # the package next to this file
from xno_buyer_plan.wallets import key_from_account, state_block_hash

try:
    from scrapy.exceptions import NotConfigured
except ImportError:  # scrapy absent: the same name, so tests and from_crawler behave alike
    class NotConfigured(Exception):
        pass

RAW_PER_XNO = 10 ** 30
META_KEY = "nano_pay"
_HEX64 = re.compile(r"[0-9A-Fa-f]{64}")


class SignerError(Exception):
    """The signer returned something that is not a 64-hex block hash."""


def _text(x):
    if isinstance(x, (bytes, bytearray)):
        return x.decode("latin-1")
    return str(x)


def headers_dict(headers):
    """Scrapy Headers (bytes keys, list-of-bytes values) or a plain mapping -> {str: str} (first value)."""
    out = {}
    if headers is None:
        return out
    items = headers.items() if hasattr(headers, "items") else headers
    for k, v in items:
        if isinstance(v, (list, tuple)):
            v = v[0] if v else b""
        out[_text(k)] = _text(v)
    return out


def load_signer(spec):
    if spec is None or spec == "":
        return None
    if callable(spec):
        return spec
    mod, _, attr = str(spec).rpartition(".")
    if not mod:
        raise NotConfigured("NANO_PAY_SIGNER %r is not 'module.attr'" % spec)
    return getattr(importlib.import_module(mod), attr)


class Journal:
    """Append-only JSON-lines journal. Keys of every line (intent or paid) are replays; it is read once at
    start, so a restarted crawl refuses every order the earlier process handed to its signer."""

    def __init__(self, path):
        self.path = path
        self.entries = {}  # journal_key -> {"state", "amount_raw", "blockHash"?}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                        key = row["key"]
                    except (ValueError, KeyError, TypeError):
                        # a torn last line from a crash: keep reading, never pay on a guess
                        continue
                    prev = self.entries.get(key, {})
                    prev.update(row)
                    self.entries[key] = prev

    def __contains__(self, key):
        return key in self.entries

    def spent_raw(self):
        total = 0
        for row in self.entries.values():
            try:
                total += int(row.get("amount_raw", 0))
            except (TypeError, ValueError):
                pass
        return total

    def write(self, row):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        prev = self.entries.get(row["key"], {})
        prev.update(row)
        self.entries[row["key"]] = prev


def _quote_doc(headers, body):
    """The decoded PaymentRequired document the plan was made from: header first, then JSON body."""
    for k, v in headers.items():
        if k.lower() == "payment-required":
            try:
                return json.loads(base64.b64decode(v).decode("utf-8"))
            except (ValueError, UnicodeDecodeError, TypeError):
                return None
    try:
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except (ValueError, UnicodeDecodeError, TypeError, AttributeError):
        return None


def _nano_only(headers, body):
    """The same quote with only its Nano accepts, or None. Used only to name a refusal, never to pay."""
    doc = _quote_doc(headers, body)
    if not isinstance(doc, dict) or not isinstance(doc.get("accepts"), list):
        return None
    keep = [a for a in doc["accepts"] if isinstance(a, dict) and str(a.get("network", "")).startswith("nano")]
    if not keep or len(keep) == len(doc["accepts"]):
        return None
    doc = dict(doc, accepts=keep)
    if any(k.lower() == "payment-required" for k in headers):
        enc = base64.b64encode(json.dumps(doc).encode("utf-8")).decode("ascii")
        return {"PAYMENT-REQUIRED": enc}, b""
    return {}, json.dumps(doc).encode("utf-8")


def accepted_entry(doc, plan):
    """The raw accepts entry the plan was made from: same payTo, amount and extra.orderId."""
    if not isinstance(doc, dict) or not isinstance(doc.get("accepts"), list):
        return None
    for a in doc["accepts"]:
        if not isinstance(a, dict):
            continue
        extra = a.get("extra") if isinstance(a.get("extra"), dict) else {}
        amount = a.get("amount", a.get("maxAmountRequired"))
        if (a.get("payTo") == plan["payTo"] and str(amount) == plan["amount_raw"]
                and extra.get("orderId") == plan["orderId"]):
            return a
    return None


def payment_header(plan, accepted, block_hash):
    version = plan.get("x402Version") or 2
    doc = {"x402Version": version, "accepted": accepted,
           "payload": {"orderId": plan["orderId"], "blockHash": block_hash}}
    if version == 1:
        doc = {"x402Version": 1, "scheme": accepted.get("scheme"), "network": accepted.get("network"),
               "payload": doc["payload"]}
    name = "X-PAYMENT" if version == 1 else "PAYMENT-SIGNATURE"
    return name, base64.b64encode(json.dumps(doc, separators=(",", ":")).encode("utf-8")).decode("ascii")


_SIG128 = re.compile(r"[0-9A-Fa-f]{128}")
_WORK16 = re.compile(r"[0-9A-Fa-f]{16}")


def exact_accepted(doc, plan):
    """The raw accepts entry a plain exact plan was made from: scheme exact, same payTo and amount."""
    if not isinstance(doc, dict) or not isinstance(doc.get("accepts"), list):
        return None
    for a in doc["accepts"]:
        if not isinstance(a, dict) or a.get("scheme") != "exact":
            continue
        amount = a.get("amount", a.get("maxAmountRequired"))
        if a.get("payTo") == plan["payTo"] and str(amount) == plan["amount_raw"]:
            return a
    return None


def check_send_block(block, pay_to):
    """A block signer's answer -> (64-hex hash, None) or (None, words). The block must be a signed state
    block whose link is payTo's public key (link_as_account, when given, equal to payTo); its hash is
    computed here from the fields, never taken from the signer. The amount is not visible in one block
    (balance is the payer's new balance): the seller's facilitator checks it against the previous block."""
    if not isinstance(block, dict):
        return None, "block signer returned %r, not a block object" % (type(block).__name__,)
    # type is required, not defaulted: feeless402 (nano_pay/server.py _BLOCK_KEYS) and probe402 (src/index.js
    # extractBlock) refuse a block without "type": "state", and a refused block has still left this process
    if block.get("type") != "state" or block.get("subtype", "send") != "send":
        return None, "not a state send block (type %r, subtype %r)" % (block.get("type"), block.get("subtype"))
    # work is required here although a facilitator with a work source accepts none (pursekeeper x402.js): the
    # sellers that publish through a public node (feeless402 verify.py step 5, probe402 process) cannot add it
    if not isinstance(block.get("work"), str) or not _WORK16.fullmatch(block["work"]):
        return None, "block carries no 16-hex work"
    want = key_from_account(pay_to)
    link = block.get("link")
    if want is None or not isinstance(link, str) or not _HEX64.fullmatch(link) or bytes.fromhex(link) != want:
        return None, "block link is not payTo %s" % pay_to
    if "link_as_account" in block and block["link_as_account"] != pay_to:
        return None, "block link_as_account %r is not payTo" % (block["link_as_account"],)
    sig = block.get("signature")
    if not isinstance(sig, str) or not _SIG128.fullmatch(sig):
        return None, "block carries no 128-hex signature"
    try:
        return state_block_hash(block), None
    except (ValueError, KeyError, TypeError) as e:
        return None, "block fields do not encode: %s" % e


def _settle_exact(plan, headers, body, url, block_signer, journal):
    """A plain exact accept (x402nano/exact): the payer signs a send block and does NOT publish it; the
    block goes to the seller inside this one request and the seller's facilitator publishes it (it refuses a
    block that is already confirmed), so the block is spent on this request only."""
    accepted = exact_accepted(_quote_doc(headers, body), plan)
    if accepted is None:
        return {"ok": False, "error": "no_accepted", "detail": "the planned accept was not found again"}
    key = plan["journal_key"]
    journal.write({"key": key, "state": "intent", "amount_raw": plan["amount_raw"], "orderId": None,
                   "url": url})
    order = {"network": plan["network"], "payTo": plan["payTo"], "amount_raw": plan["amount_raw"],
             "work_threshold": plan.get("work_threshold")}
    block = block_signer(dict(order))
    block_hash, why = check_send_block(block, plan["payTo"])
    if block_hash is None:
        # the intent stays journalled: a block that may exist is never signed again for this quote
        return {"ok": False, "error": "signer_bad_block", "detail": why}
    journal.write({"key": key, "state": "signed", "amount_raw": plan["amount_raw"], "orderId": None,
                   "blockHash": block_hash})
    version = plan.get("x402Version") or 2
    doc = {"x402Version": version, "accepted": accepted, "payload": {"block": block}}
    if version == 1:
        doc = {"x402Version": 1, "scheme": accepted.get("scheme"), "network": accepted.get("network"),
               "payload": doc["payload"]}
    name = "X-PAYMENT" if version == 1 else "PAYMENT-SIGNATURE"
    value = base64.b64encode(json.dumps(doc, separators=(",", ":")).encode("utf-8")).decode("ascii")
    return {"ok": True, "header": (name, value), "plan": plan, "blockHash": block_hash}


def settle_402(headers, body, url, signer, journal, cap_raw, budget_raw, allow_unbound=False, block_signer=None):
    """One 402 -> a paid proof header, or a named refusal. Shared by this middleware and nano_fetch.

    headers: {str: str}; journal: a Journal. Returns {"ok": True, "header": (name, value), "plan": plan,
    "blockHash": hash} or {"ok": False, "error": code, "detail": words}. Order: plan (shape, network,
    checksum, amount, per-call cap, binding, replay), bound-or-allowed, budget, intent journalled (fsynced),
    signer, hash check, paid journalled. A send-hash quote (no binding) is paid only with allow_unbound;
    its signer gets representative None (keep the wallet's own). A plain exact accept is paid only with a
    block_signer ({network, payTo, amount_raw, work_threshold} -> signed, unpublished state send block)."""
    plan = plan_402(headers, body, cap_raw=cap_raw, seller_url=url, journal=journal)
    if not plan.get("ok") and plan.get("error") == "wrong_network":
        # plan_402 names the FIRST accept's refusal (a USDC entry on a mixed quote); name the Nano one
        nano = _nano_only(headers, body)
        if nano is not None:
            plan = plan_402(nano[0], nano[1], cap_raw=cap_raw, seller_url=url, journal=journal)
    if not plan.get("ok"):
        return {"ok": False, "error": plan.get("error"), "detail": plan.get("detail")}
    dialect = plan.get("dialect")
    if dialect == "invoice":
        # bound by the invoice's own amount and private token, but paid in two more requests (create the
        # invoice, then present the hash), which one retry of the 402 cannot make: see settle_invoice
        return {"ok": False, "error": "invoice_flow", "plan": plan,
                "detail": "an invoice quote needs its invoice created first (nano_fetch --invoice-body)"}
    exact = dialect == "exact" and block_signer is not None
    if not (dialect == "rep-binding" or exact or (dialect == "send-hash" and allow_unbound)):
        hint = {"send-hash": " (a send-hash quote needs allow_unbound)",
                "exact": " (a plain exact accept needs a block signer)"}.get(dialect, "")
        return {"ok": False, "error": "unbound", "detail": "dialect %s: only a bound order (xno-binding/v1/rep) "
                "is paid%s" % (dialect, hint)}
    if not exact and signer is None:
        return {"ok": False, "error": "no_signer", "detail": "dialect %s needs a signer that publishes a send"
                % dialect}
    amount = int(plan["amount_raw"])
    spent = journal.spent_raw()
    if spent + amount > int(budget_raw):
        return {"ok": False, "error": "over_budget", "detail": "%d raw spent + %d > budget %d raw"
                % (spent, amount, int(budget_raw))}
    if exact:
        return _settle_exact(plan, headers, body, url, block_signer, journal)
    accepted = None
    if dialect == "rep-binding":
        accepted = accepted_entry(_quote_doc(headers, body), plan)
        if accepted is None:
            return {"ok": False, "error": "no_accepted", "detail": "the planned accept was not found again"}
    key = plan["journal_key"]
    journal.write({"key": key, "state": "intent", "amount_raw": plan["amount_raw"],
                   "orderId": plan.get("orderId"), "url": url})
    order = {"network": plan["network"], "payTo": plan["payTo"], "amount_raw": plan["amount_raw"],
             "representative": plan.get("representative"), "orderId": plan.get("orderId")}
    block_hash = signer(dict(order))
    if not isinstance(block_hash, str) or not _HEX64.fullmatch(block_hash):
        # the intent stays journalled: an unknown outcome is never retried by this process or the next
        return {"ok": False, "error": "signer_no_hash", "detail": "signer returned %r" % (block_hash,)}
    block_hash = block_hash.upper()
    journal.write({"key": key, "state": "paid", "amount_raw": plan["amount_raw"],
                   "orderId": plan.get("orderId"), "blockHash": block_hash})
    if dialect == "send-hash":
        header = (plan["proof"]["header"], block_hash)
    else:
        header = payment_header(plan, accepted, block_hash)
    return {"ok": True, "header": header, "plan": plan, "blockHash": block_hash}


_INVOICE_ID = re.compile(r"[A-Za-z0-9_-]{8,128}")
_INVOICE_TOKEN = re.compile(r"[A-Za-z0-9_-]{16,256}")
_ISO_UTC = re.compile(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.\d+)?Z")


def _expiry(text):
    """'2026-11-26T19:00:00.000Z' -> seconds since the epoch, or None when it is not that shape."""
    m = _ISO_UTC.fullmatch(text) if isinstance(text, str) else None
    if not m:
        return None
    try:
        return calendar.timegm(tuple(int(x) for x in m.groups()) + (0, 0, 0))
    except (OverflowError, ValueError):
        return None


def settle_invoice(plan, invoice, url, signer, journal, cap_raw, budget_raw, now, margin_s=120):
    """An invoice quote's second step, with no network: the invoice the seller created -> the result request.

    plan: the 402's plan (dialect "invoice"), invoice: the created invoice (JSON object). The invoice must name
    the 402's own pay_to and network, an id and a private token, a price in digits no lower than the 402's base
    price and within the per-call cap, and an expires_at at least margin_s ahead of `now` (epoch seconds).
    Then the budget, an fsynced intent line (with the invoice id and token, so the paid invoice can be redeemed
    by hand after a crash), the signer (publishes the exact send, returns its confirmed hash), a paid line.
    Returns {"ok": True, "body": <JSON bytes {invoice_id, payment_hash}>, "auth": ("Authorization", "Bearer .."),
    "blockHash", "amount_raw", "invoice_id"} or {"ok": False, "error", "detail"}. One invoice id is handed to
    the signer once, across restarts."""
    if not isinstance(invoice, dict):
        return {"ok": False, "error": "invoice_shape", "detail": "the created invoice is not a JSON object"}
    inv_id, token = invoice.get("invoice_id"), invoice.get("invoice_token")
    if not (isinstance(inv_id, str) and _INVOICE_ID.fullmatch(inv_id)):
        return {"ok": False, "error": "invoice_shape", "detail": "invoice_id %r" % (inv_id,)}
    if not (isinstance(token, str) and _INVOICE_TOKEN.fullmatch(token)):
        return {"ok": False, "error": "invoice_shape", "detail": "no private invoice_token in the invoice"}
    if invoice.get("pay_to") != plan["payTo"]:
        return {"ok": False, "error": "invoice_pay_to", "detail": "the invoice pays %r, the 402 named %r"
                % (invoice.get("pay_to"), plan["payTo"])}
    if invoice.get("network") not in ("nano:mainnet", plan.get("network_seen")):
        return {"ok": False, "error": "wrong_network", "detail": "invoice network %r" % (invoice.get("network"),)}
    price = invoice.get("price_raw")
    if not (isinstance(price, str) and price.isascii() and price.isdigit()):
        return {"ok": False, "error": "amount_ambiguous", "detail": "invoice price_raw %r is not digits" % (price,)}
    if int(price) < int(plan["amount_raw"]):
        return {"ok": False, "error": "invoice_price", "detail": "invoice price %s raw is below the 402's base %s"
                % (price, plan["amount_raw"])}
    if int(price) > int(cap_raw):
        return {"ok": False, "error": "over_cap", "detail": "invoice price %s raw > cap %s raw" % (price, cap_raw)}
    expires = _expiry(invoice.get("expires_at"))
    if expires is None or expires < now + margin_s:
        return {"ok": False, "error": "invoice_expiry", "detail": "expires_at %r is not %d s ahead; not paying"
                % (invoice.get("expires_at"), margin_s)}
    # not keyed on the URL: the same invoice (account, exact price, id) reached by another address is one order
    key = "invoice|%s|%s|%s" % (plan["payTo"], price, inv_id)
    if key in journal:
        return {"ok": False, "error": "replayed", "detail": "this invoice is already in the journal: " + key}
    spent = journal.spent_raw()
    if spent + int(price) > int(budget_raw):
        return {"ok": False, "error": "over_budget", "detail": "%d raw spent + %s > budget %d raw"
                % (spent, price, int(budget_raw))}
    journal.write({"key": key, "state": "intent", "amount_raw": price, "orderId": inv_id,
                   "invoice_token": token, "url": url})
    block_hash = signer({"network": "nano:mainnet", "payTo": plan["payTo"], "amount_raw": price,
                         "representative": None, "orderId": inv_id})
    if not isinstance(block_hash, str) or not _HEX64.fullmatch(block_hash):
        return {"ok": False, "error": "signer_no_hash", "detail": "signer returned %r" % (block_hash,)}
    block_hash = block_hash.upper()
    journal.write({"key": key, "state": "paid", "amount_raw": price, "orderId": inv_id, "blockHash": block_hash})
    body = json.dumps({"invoice_id": inv_id, "payment_hash": block_hash}).encode("utf-8")
    return {"ok": True, "body": body, "auth": ("Authorization", "Bearer " + token), "blockHash": block_hash,
            "amount_raw": price, "invoice_id": inv_id}


class NanoPaymentMiddleware:
    """Settings: NANO_PAY_ENABLED (bool, default False), NANO_PAY_SIGNER (callable or 'module.attr'),
    NANO_PAY_JOURNAL (file path, required), NANO_PAY_CAP_RAW (per page, default buyer_plan's 10**29 raw),
    NANO_PAY_BUDGET_RAW (whole crawl, default 10 x the cap)."""

    def __init__(self, signer, journal_path, cap_raw=DEFAULT_CAP_RAW, budget_raw=None, logger=None):
        if signer is None or not callable(signer):
            raise NotConfigured("NANO_PAY_SIGNER is not set: nothing can pay")
        if not journal_path:
            raise NotConfigured("NANO_PAY_JOURNAL is not set: replay refusal must survive a restart")
        self.signer = signer
        self.journal = Journal(journal_path)
        self.cap_raw = str(int(cap_raw))
        self.budget_raw = int(budget_raw) if budget_raw is not None else 10 * int(self.cap_raw)
        self.logger = logger
        self.refusals = []  # (url, code, detail), for the spider's stats and for tests

    @classmethod
    def from_crawler(cls, crawler):
        s = crawler.settings
        if not s.getbool("NANO_PAY_ENABLED", False):
            raise NotConfigured("NANO_PAY_ENABLED is off")
        cap = s.get("NANO_PAY_CAP_RAW") or DEFAULT_CAP_RAW
        budget = s.get("NANO_PAY_BUDGET_RAW")
        return cls(load_signer(s.get("NANO_PAY_SIGNER")), s.get("NANO_PAY_JOURNAL"), cap, budget)

    def _refuse(self, request, response, code, detail):
        self.refusals.append((request.url, code, detail))
        if self.logger is not None:
            self.logger.info("nano-pay refused %s: %s (%s)", request.url, code, detail)
        return response

    def process_response(self, request, response, spider=None):
        if getattr(response, "status", None) != 402:
            return response
        if (getattr(request, "meta", None) or {}).get(META_KEY):
            return self._refuse(request, response, "paid_retry_402", "the paid retry met 402 again; "
                                "not paying twice for one request")
        r = settle_402(headers_dict(response.headers), getattr(response, "body", b""), request.url,
                       self.signer, self.journal, self.cap_raw, self.budget_raw)
        if not r["ok"]:
            return self._refuse(request, response, r["error"], r["detail"])
        name, value = r["header"]
        plan, block_hash = r["plan"], r["blockHash"]
        key = plan["journal_key"]
        new_headers = headers_dict(request.headers)
        new_headers[name] = value
        meta = dict(getattr(request, "meta", None) or {})
        meta[META_KEY] = {"orderId": plan["orderId"], "blockHash": block_hash, "journal_key": key}
        return request.replace(headers=new_headers, meta=meta, dont_filter=True)
