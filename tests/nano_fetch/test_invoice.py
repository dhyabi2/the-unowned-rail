"""nano_fetch pays a private-token invoice quote (FRONTIER 106 (i)): create the invoice, pay its exact price once,
present the hash with the token. Loopback only: the seller below copies the three endpoints of
Daltonray625/pinnacle-url-check @ 107b978 (src/app.js: GET /v1/check -> 402 with `flow`; POST /v1/invoices -> 201
{invoice_id, invoice_token, pay_to, price_raw, expires_at}; POST /v1/result with Authorization: Bearer token ->
200 report, 202 while processing). No key, no network, the signer is a stub.

    python3 -m unittest tests/nano_fetch/test_invoice.py
"""
import http.server
import json
import os
import sys
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SKILL_DIR = os.path.join(HERE, "..", "..", "skills", "nano-fetch")  # the-unowned-rail: fetch.py, middleware.py
sys.path[1:1] = [SKILL_DIR, os.path.join(SKILL_DIR, "xno_buyer_plan")]  # plan, wallets, client_fit
import fetch as nf  # noqa: E402
import test_fetch as tf  # noqa: E402  (loopback guard, stub signer)
from plan import plan_402  # noqa: E402  (buyer_plan, put on sys.path by fetch)

RAW_PER_XNO = 10 ** 30
BASE = str(RAW_PER_XNO // 100)  # 0.01 XNO, pinnacle's base_price_raw, derived here
SUFFIX = 12345678901234567  # pinnacle adds a random suffix below 2**64 raw to bind the chain payment
PRICE = str(int(BASE) + SUFFIX)
PAY_TO = "nano_1u5zktci5e4jtrcf9poq66pc5wk6g4mnmruh5h3dg1bdac63nj5kck5w453x"  # 107b978 src/core.js PAY_TO
OTHER = tf.PAY_TO
TOKEN = "T" * 43  # the shape app.js checks (43 of A-Za-z0-9_-); not a real token
INV_ID = "0f8fad5b-d9cb-469f-a165-70867728950e"
NOW = 1795000000.0  # a fixed clock for the expiry checks
FLOW = ('Private-token invoice: POST /v1/invoices {"url":"https://www.gnu.org/"}; pay EXACT price_raw once; '
        'POST /v1/result with invoice_id,payment_hash and Authorization: Bearer invoice_token. '
        'Never use a public hash alone.')


def iso(t):
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t))


def quote_body(flow=FLOW, pay_to=PAY_TO):
    """The 402 body of 107b978 GET /v1/check (the `terms` object, trimmed to the fields a payer reads)."""
    return {"service": "Pinnacle URL Check", "network": "nano:mainnet", "asset": "XNO", "pay_to": pay_to,
            "base_price_nano": "0.01", "base_price_raw": BASE, "flow": flow, "status": "payment_required"}


class InvoiceSeller:
    def __init__(self, quote=None, invoice=None, busy=0, result_status=200):
        self.quote = quote or quote_body()
        self.invoice = dict({"invoice_id": INV_ID, "invoice_token": TOKEN, "network": "nano:mainnet",
                             "asset": "XNO", "pay_to": PAY_TO, "price_raw": PRICE,
                             "url": "https://www.gnu.org/", "expires_at": iso(NOW + 3600)}, **(invoice or {}))
        self.busy, self.result_status = busy, result_status  # answer 202 this many times first
        self.seen = []  # (method, path, headers, body)


def serve(seller):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, doc):
            b = json.dumps(doc).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _answer(self):
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else b""
            hdrs = {k.lower(): v for k, v in self.headers.items()}
            seller.seen.append((self.command, self.path, hdrs, body))
            if self.path == "/v1/check" and self.command == "GET":
                return self._send(402, seller.quote)
            if self.path == "/v1/invoices" and self.command == "POST":
                if json.loads(body) != {"url": "https://www.gnu.org/"}:
                    return self._send(400, {"error": "invalid_json_body"})
                return self._send(201, seller.invoice)
            if self.path == "/v1/result" and self.command == "POST":
                if hdrs.get("authorization") != "Bearer " + seller.invoice["invoice_token"]:
                    return self._send(401, {"error": "private_invoice_token_required"})
                doc = json.loads(body)
                if seller.busy:
                    seller.busy -= 1
                    return self._send(202, {"status": "processing", "retry_after_seconds": 5})
                if seller.result_status == 402:
                    return self._send(402, {"error": "confirmed_exact_payment_required"})
                return self._send(200, {"invoice_id": doc["invoice_id"], "payment_hash": doc["payment_hash"],
                                        "cached": False, "report": {"ok": True}})
            return self._send(404, {"error": "not_found"})

        do_GET = do_POST = _answer

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


ORDER = b'{"url": "https://www.gnu.org/"}'


class Base(tf.Base):
    def setUp(self):
        super().setUp()
        self.sleeps = []

    def run_seller(self, seller, signer=None, order=ORDER, cap=str(RAW_PER_XNO), **kw):
        srv = serve(seller)
        self.servers.append(srv)
        url = "http://127.0.0.1:%d/v1/check" % srv.server_address[1]
        self.signer = signer or tf.Signer()
        return self.fetch(url, signer=self.signer, journal_path=self.jpath, cap_raw=cap, invoice_body=order,
                          now=lambda: NOW, sleep=self.sleeps.append, **kw)


class Pays(Base):
    def test_pays_the_invoice_price_once_and_presents_hash_with_token(self):
        s = InvoiceSeller()
        r = self.run_seller(s)
        self.assertEqual((r.status, r.refusal), (200, None))
        self.assertEqual(json.loads(r.body)["report"], {"ok": True})
        self.assertEqual(self.signer.calls, [{"network": "nano:mainnet", "payTo": PAY_TO, "amount_raw": PRICE,
                                              "representative": None, "orderId": INV_ID}])
        self.assertEqual(r.paid, {"orderId": INV_ID, "blockHash": tf.HASH.upper(), "amount_raw": PRICE,
                                  "header": "Authorization"})
        paths = [(m, p) for m, p, _h, _b in s.seen]
        self.assertEqual(paths, [("GET", "/v1/check"), ("POST", "/v1/invoices"), ("POST", "/v1/result")])
        _m, _p, create_h, _b = s.seen[1]
        self.assertNotIn("authorization", create_h)
        _m, _p, h, b = s.seen[2]
        self.assertEqual(h["authorization"], "Bearer " + TOKEN)
        self.assertEqual(json.loads(b), {"invoice_id": INV_ID, "payment_hash": tf.HASH.upper()})
        rows = self.journal_rows()
        self.assertEqual([x["state"] for x in rows], ["intent", "paid"])
        self.assertEqual((rows[0]["invoice_token"], rows[0]["amount_raw"]), (TOKEN, PRICE))

    def test_processing_202_is_asked_again_with_the_same_hash_never_paid_again(self):
        s = InvoiceSeller(busy=2)
        r = self.run_seller(s)
        self.assertEqual(r.status, 200)
        self.assertEqual(len(self.signer.calls), 1)
        self.assertEqual(self.sleeps, [5, 5])
        bodies = [b for m, p, _h, b in s.seen if p == "/v1/result"]
        self.assertEqual(len(bodies), 3)
        self.assertEqual(len(set(bodies)), 1)

    def test_still_processing_after_three_tries_returns_202_with_the_payment_recorded(self):
        r = self.run_seller(InvoiceSeller(busy=9))
        self.assertEqual((r.status, len(self.signer.calls), len(self.sleeps)), (202, 1, 2))
        self.assertEqual(r.paid["orderId"], INV_ID)

    def test_result_402_after_paying_is_not_paid_again(self):
        r = self.run_seller(InvoiceSeller(result_status=402))
        self.assertEqual((r.status, r.refusal[0], len(self.signer.calls)), (402, "paid_retry_402", 1))


class Refuses(Base):
    def assertNothingSigned(self, r, code, seller=None):
        self.assertEqual(r.status, 402)  # the original 402 comes back: the command exits 3, not 0
        self.assertEqual(r.refusal[0], code)
        self.assertEqual(self.signer.calls, [])
        self.assertIsNone(r.paid)
        if seller is not None:
            self.assertFalse([p for _m, p, _h, _b in seller.seen if p == "/v1/result"])

    def test_off_without_an_invoice_body(self):
        s = InvoiceSeller()
        r = self.run_seller(s, order=None)
        self.assertNothingSigned(r, "invoice_flow")
        self.assertEqual([p for _m, p, _h, _b in s.seen], ["/v1/check"])
        self.assertEqual(self.journal_rows(), [])

    def test_invoice_paying_another_account(self):
        s = InvoiceSeller(invoice={"pay_to": OTHER})
        self.assertNothingSigned(self.run_seller(s), "invoice_pay_to", s)

    def test_invoice_on_another_network(self):
        s = InvoiceSeller(invoice={"network": "base"})
        self.assertNothingSigned(self.run_seller(s), "wrong_network", s)

    def test_invoice_below_the_base_price(self):
        s = InvoiceSeller(invoice={"price_raw": str(int(BASE) - 1)})
        self.assertNothingSigned(self.run_seller(s), "invoice_price", s)

    def test_invoice_over_the_cap(self):
        s = InvoiceSeller()
        self.assertNothingSigned(self.run_seller(s, cap=str(int(PRICE) - 1)), "over_cap", s)

    def test_invoice_price_not_digits(self):
        s = InvoiceSeller(invoice={"price_raw": "1e28"})
        self.assertNothingSigned(self.run_seller(s), "amount_ambiguous", s)

    def test_invoice_expiring_or_expired(self):
        for exp in (iso(NOW + 60), iso(NOW - 1), "tomorrow", None):
            with self.subTest(expires_at=exp):
                s = InvoiceSeller(invoice={"expires_at": exp})
                self.assertNothingSigned(self.run_seller(s), "invoice_expiry", s)

    def test_invoice_without_token_or_id(self):
        for bad in ({"invoice_token": None}, {"invoice_token": "short"}, {"invoice_id": "x"}):
            with self.subTest(bad=bad):
                s = InvoiceSeller(invoice=bad)
                self.assertNothingSigned(self.run_seller(s), "invoice_shape", s)

    def test_same_invoice_again_after_a_restart_is_refused(self):
        self.run_seller(InvoiceSeller())
        first = self.signer.calls
        s = InvoiceSeller()  # a new process: the journal is read again from the file
        r = self.run_seller(s)
        self.assertEqual(len(first), 1)
        self.assertNothingSigned(r, "replayed", s)

    def test_a_signer_without_hash_leaves_the_intent_and_presents_nothing(self):
        s = InvoiceSeller()
        r = self.run_seller(s, signer=tf.Signer(answer=None))
        self.assertEqual(r.refusal[0], "signer_no_hash")
        self.assertFalse([p for _m, p, _h, _b in s.seen if p == "/v1/result"])
        self.assertEqual([x["state"] for x in self.journal_rows()], ["intent"])

    def test_create_path_on_another_host_is_never_called(self):
        s = InvoiceSeller(quote=quote_body(flow="POST //elsewhere.example/v1/invoices then POST /v1/result"))
        self.assertNothingSigned(self.run_seller(s), "invoice_offsite", s)  # the loopback guard would fail a call

    def test_invoice_not_created(self):
        s = InvoiceSeller()
        r = self.run_seller(s, order=b'{"url": "https://other.example/"}')
        self.assertNothingSigned(r, "invoice_not_created", s)


class SellerOwn402(unittest.TestCase):
    def test_the_sellers_own_402_names_both_paths(self):
        p = plan_402({}, quote_body(), cap_raw=str(RAW_PER_XNO))
        self.assertEqual((p["dialect"], p["invoice_create"], p["invoice_result"], p["amount_raw"], p["payTo"]),
                         ("invoice", "/v1/invoices", "/v1/result", BASE, PAY_TO))


class Command(Base):
    def test_cli_invoice_body_needs_signer_and_an_object(self):
        err = open(os.devnull, "w")
        self.addCleanup(err.close)
        self.assertEqual(nf.main(["http://127.0.0.1:9/v1/check", "--journal", self.jpath,
                                  "--block-signer", "test_fetch.Signer", "--invoice-body", "{}"], err=err), 2)
        self.assertEqual(nf.main(["http://127.0.0.1:9/v1/check", "--journal", self.jpath,
                                  "--signer", "test_fetch.Signer", "--invoice-body", "[1]"], err=err), 2)


if __name__ == "__main__":
    unittest.main()
