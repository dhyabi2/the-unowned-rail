"""skill/PAYABLE.md says, per seller, what fetch.py does with its 402. This test holds every row to a fixture:
each listed seller must have one (client_fit_fixtures.json or fixtures/*.json), the quote reader must plan it,
the price column must be the planned raw amount, and the fetch.py column must be what fetch.py does against a
loopback copy of that 402 with a stub signer - by default, with allow_unbound, and with a stub block signer. A row
"yes, with --block-signer" also needs an entry in fixtures/settle-106h.json whose settle is payload.block (read
from the seller's code or a published paid call), and the header fetch.py sent must meet that entry's
`requires`. Loopback only, no key.

    python3 -m unittest tests/nano_fetch/test_payable.py
"""
import base64
import glob
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SKILL_DIR = os.path.join(HERE, "..", "..", "skills", "nano-fetch")  # the-unowned-rail: fetch.py, middleware.py
sys.path[1:1] = [SKILL_DIR, os.path.join(SKILL_DIR, "xno_buyer_plan")]  # plan, wallets, client_fit
import test_fetch as tf  # noqa: E402  (loopback seller, stub signer, loopback-only guard)
import test_exact_block as teb  # noqa: E402  (stub block signer: fixed-shape block, dummy signature, no key)
import test_invoice as ti  # noqa: E402  (loopback invoice seller: pinnacle 107b978's three endpoints)
from plan import plan_402  # noqa: E402  (buyer_plan, put on sys.path by fetch)

PAYABLE = os.path.join(SKILL_DIR, "PAYABLE.md")
SETTLE = os.path.join(HERE, "fixtures", "settle-106h.json")
HEX16 = re.compile(r"[0-9A-Fa-f]{16}")
CAP = str(10 ** 30)  # 1 XNO per call: above every listed price, so the cap never decides a row
ROW = re.compile(r"^\| ([a-z0-9-]+) \| (.+?) \| (exact|send-hash|invoice|rep-binding) \| (\d+) \| (.+?) \|$")


def fixtures():
    out = {}
    with open(tf.FIXTURES, encoding="utf-8") as f:
        for x in json.load(f):
            out[x["id"]] = x
    for path in sorted(glob.glob(os.path.join(HERE, "fixtures", "*.json"))):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        for x in d if isinstance(d, list) else [d]:
            if isinstance(x, dict) and "id" in x and "body" in x:
                out.setdefault(x["id"], x)
    return out


SETTLE_H2 = os.path.join(HERE, "fixtures", "settle-106h2.json")


def settles():
    """Settle reads by seller id: fixtures/settle-106h.json (rail run 253) and settle-106h2.json (pr agent 4 run 50).
    A seller read in both must be read the same way, or the table could not say which read it rests on."""
    out = {}
    for path in (SETTLE, SETTLE_H2):
        with open(path, encoding="utf-8") as f:
            for x in json.load(f)["settle"]:
                if x["id"] in out and out[x["id"]]["settle"] != x["settle"]:
                    raise ValueError("%s read two ways: %s / %s" % (x["id"], out[x["id"]]["settle"], x["settle"]))
                out.setdefault(x["id"], x)
    return out


def quote_doc(fx):
    """The 402 document a fixture holds: the PAYMENT-REQUIRED header (base64 JSON) or the body."""
    for k, v in fx["headers"].items():
        if k.lower() == "payment-required":
            return json.loads(base64.b64decode(v))
    b = fx["body"]
    return json.loads(b) if isinstance(b, str) else b


def header_faults(sent, requires, doc):
    """What the paid request's headers (lower-cased names) miss against a settle entry's `requires`."""
    names = [h for h in requires.get("headers", []) if h in sent]
    if not names:
        return ["none of %s sent" % requires.get("headers")]
    try:
        pay = json.loads(base64.b64decode(sent[names[0]]))
        block = pay["payload"]["block"]
    except (ValueError, KeyError, TypeError) as e:
        return ["%s is not base64 JSON with payload.block: %s" % (names[0], e)]
    out = []
    if "x402_version" in requires and pay.get("x402Version") != requires["x402_version"]:
        out.append("x402Version %r" % (pay.get("x402Version"),))
    if requires.get("accepted_from_402") and pay.get("accepted") not in doc.get("accepts", []):
        out.append("accepted is not an accepts entry of the 402")
    if requires.get("type_state") and block.get("type") != "state":
        out.append("block type %r" % (block.get("type"),))
    if requires.get("work16") and not (isinstance(block.get("work"), str) and HEX16.fullmatch(block["work"])):
        out.append("block work %r" % (block.get("work"),))
    missing = [k for k in requires.get("block_keys", []) if k not in block]
    if missing:
        out.append("block lacks %s" % missing)
    return out


def rows(text=None):
    if text is None:
        with open(PAYABLE, encoding="utf-8") as f:
            text = f.read()
    return [ROW.match(l).groups() for l in text.splitlines() if ROW.match(l)]


def expected_cell(default, unbound, block=None, settle=None, invoice=None):
    """The fetch.py cell for the loopback outcomes, each (status, refusal code, signer calls), and the seller's
    settle entry: a block-signer payment is a yes only where the seller is read to take payload.block, an
    invoice payment only where the seller's code is read as the invoice flow."""
    if default[0] == 200 and default[2] == 1:
        return "yes"
    if default[1] == "invoice_flow" and default[2] == 0:
        if (settle or {}).get("settle") == "invoice-flow" and invoice is not None and invoice[0] == 200 \
                and invoice[2] == 1:
            return "yes, with --invoice-body"
        return "no: invoice flow"
    if default[1] == "unbound" and unbound[0] == 200 and unbound[2] == 1:
        return "yes, with --allow-unbound"
    if default[1] == "unbound" and unbound[1] == "unbound" and unbound[2] == 0:
        how = (settle or {}).get("settle")
        if how == "payload.block" and block is not None and block[0] == 200 and block[2] == 1:
            return "yes, with --block-signer"
        if how == "UNKNOWN":
            return "no: settle unread"
        return "no: unbound"
    return "UNEXPECTED %r %r %r" % (default, unbound, block)


class Payable(tf.Base):
    def outcome(self, fx, proof_header, allow_unbound, block_signer=None):
        # a fresh journal each time: the default run must not leave a row that refuses the second as replayed
        self.jpath = os.path.join(self.dir, "pay-%d.jsonl" % len(self.servers))
        seller = tf.Seller(fx["headers"], fx["body"], proof_header)
        url = self.start(seller) + "/paid"
        if block_signer is not None:
            r = self.fetch(url, block_signer=block_signer, journal_path=self.jpath, cap_raw=CAP)
            self.last_seen = seller.seen
            return r.status, r.refusal and r.refusal[0], len(block_signer.calls)
        sig = tf.Signer()
        r = self.fetch(url, signer=sig, journal_path=self.jpath, allow_unbound=allow_unbound, cap_raw=CAP)
        return r.status, r.refusal and r.refusal[0], len(sig.calls)

    def invoice_outcome(self, fx):
        """fetch.py with --invoice-body against a loopback copy of pinnacle 107b978's invoice endpoints that
        answers the fixture's own 402 and issues an invoice on the fixture's pay_to."""
        seller = ti.InvoiceSeller(quote=fx["body"], invoice={"pay_to": quote_doc(fx).get("pay_to")})
        srv = ti.serve(seller)
        self.servers.append(srv)
        sig = tf.Signer()
        url = "http://127.0.0.1:%d/v1/check" % srv.server_address[1]
        r = self.fetch(url, signer=sig, journal_path=os.path.join(self.dir, "inv-%d.jsonl" % len(self.servers)),
                       cap_raw=CAP, invoice_body=ti.ORDER, now=lambda: ti.NOW, sleep=lambda s: None)
        return r.status, r.refusal and r.refusal[0], len(sig.calls)

    def block_outcome(self, fx, signer=None):
        """fetch.py with only a block signer; the seller serves on the x402 header of the quote's version."""
        hdr = "PAYMENT-SIGNATURE" if quote_doc(fx).get("x402Version") == 2 else "X-PAYMENT"
        return self.outcome(fx, hdr, False, block_signer=signer or teb.BlockSigner())

    def test_the_table_has_rows_and_no_key_or_seed(self):
        with open(PAYABLE, encoding="utf-8") as f:
            text = f.read()
        self.assertGreaterEqual(len(rows(text)), 9)
        self.assertIn("no paid call yet", text)
        self.assertIsNone(re.search(r"\b[0-9A-Fa-f]{64}\b", text))
        self.assertNotRegex(text.lower(), r"\bseed\b")

    def test_every_row_has_a_fixture_and_says_what_fetch_does(self):
        fx = fixtures()
        seen = set()
        for sid, _source, dialect, price, cell in rows():
            with self.subTest(seller=sid):
                self.assertNotIn(sid, seen, "listed twice")
                seen.add(sid)
                self.assertIn(sid, fx, "PAYABLE.md lists a seller with no fixture")
                f = fx[sid]
                p = plan_402(f["headers"], f["body"], cap_raw=CAP)
                self.assertTrue(p.get("ok"), p)
                self.assertEqual(p["dialect"], dialect)
                self.assertEqual(p["amount_raw"], price)
                self.assertEqual(p["network"], "nano:mainnet")
                hdr = (p.get("proof") or {}).get("header") or "X-PAYMENT"
                st = settles().get(sid)
                block = self.block_outcome(f) if dialect == "exact" else None
                inv = self.invoice_outcome(f) if dialect == "invoice" else None
                got = expected_cell(self.outcome(f, hdr, False), self.outcome(f, hdr, True), block, st, inv)
                self.assertEqual(cell, got)
                if cell == "yes, with --block-signer":
                    paid = [h for _m, _p, h in self.last_seen if "payment-signature" in h or "x-payment" in h]
                    self.assertEqual(len(paid), 1)
                    self.assertEqual(header_faults(paid[0], st["requires"], quote_doc(f)), [])

    def test_every_exact_or_invoice_row_has_a_settle_entry_with_a_source(self):
        st = settles()
        for sid, _source, dialect, _price, cell in rows():
            if dialect in ("exact", "invoice"):
                with self.subTest(seller=sid):
                    self.assertIn(sid, st, "an exact/invoice row with no settle read")
                    self.assertIn(st[sid]["settle"], ("payload.block", "invoice-flow", "UNKNOWN"))
                    self.assertGreater(len(st[sid]["source"]), 40)
                    if st[sid]["settle"] == "payload.block":
                        self.assertTrue(st[sid]["requires"].get("headers"))

    def test_a_block_signer_yes_without_a_settle_read_fails(self):
        f = fixtures()["feeless402"]
        p = plan_402(f["headers"], f["body"], cap_raw=CAP)
        hdr = (p.get("proof") or {}).get("header") or "X-PAYMENT"
        args = (self.outcome(f, hdr, False), self.outcome(f, hdr, True), self.block_outcome(f))
        self.assertEqual(expected_cell(*args, settle=settles()["feeless402"]), "yes, with --block-signer")
        self.assertEqual(expected_cell(*args), "no: unbound")
        self.assertEqual(expected_cell(*args, settle={"settle": "UNKNOWN"}), "no: settle unread")

    def test_an_invoice_yes_needs_the_settle_read_and_the_paid_loopback(self):
        f = fixtures()["pinnacle-url-check"]
        args = (self.outcome(f, "X-PAYMENT", False), self.outcome(f, "X-PAYMENT", True))
        inv = self.invoice_outcome(f)
        st = settles()["pinnacle-url-check"]
        self.assertEqual(expected_cell(*args, settle=st, invoice=inv), "yes, with --invoice-body")
        self.assertEqual(expected_cell(*args, settle={"settle": "UNKNOWN"}, invoice=inv), "no: invoice flow")
        self.assertEqual(expected_cell(*args, settle=st, invoice=(402, "invoice_pay_to", 0)), "no: invoice flow")

    def test_a_workless_block_never_reaches_the_seller(self):
        # feeless402 verify.py step 5 refuses it; a refused signed block would still sit with the seller
        f = fixtures()["feeless402"]
        bs = teb.BlockSigner(answer={k: v for k, v in teb.BlockSigner()({"payTo": quote_doc(f)["accepts"][0]["payTo"],
                                     "amount_raw": quote_doc(f)["accepts"][0]["amount"]}).items() if k != "work"})
        status, code, calls = self.block_outcome(f, bs)
        self.assertEqual((code, calls), ("signer_bad_block", 1))
        self.assertFalse([h for _m, _p, h in self.last_seen if "payment-signature" in h or "x-payment" in h])

    def test_header_faults_names_what_a_seller_refuses(self):
        req = settles()["feeless402"]["requires"]
        doc = {"accepts": []}
        blk = teb.BlockSigner()({"payTo": teb.PAY_TO, "amount_raw": "1"})
        enc = lambda d: base64.b64encode(json.dumps(d).encode()).decode()  # noqa: E731
        self.assertEqual(header_faults({"x-payment": enc({"payload": {"block": blk}})}, req, doc), [])
        self.assertTrue(header_faults({"x-payment": enc({"payload": {"block": dict(blk, type=None)}})}, req, doc))
        self.assertTrue(header_faults({"x-payment": enc({"payload": {"blockHash": "AB"}})}, req, doc))
        self.assertTrue(header_faults({"authorization": "x"}, req, doc))
        ops = settles()["opscontrol-page-extract"]["requires"]
        self.assertTrue(header_faults({"x-payment": enc({"x402Version": 1, "payload": {"block": blk}})}, ops, doc))

    def test_a_row_without_a_fixture_fails(self):
        fake = "| no-such-seller | nowhere | send-hash | 1000 | yes, with --allow-unbound |"
        (sid, *_rest), = rows(fake)
        self.assertNotIn(sid, fixtures())

    def test_a_wrong_cell_is_caught(self):
        # an exact unbound seller claimed as paid by default would fail the comparison above
        f = fixtures()["feeless402"]
        p = plan_402(f["headers"], f["body"], cap_raw=CAP)
        hdr = (p.get("proof") or {}).get("header") or "X-PAYMENT"
        self.assertNotEqual(expected_cell(self.outcome(f, hdr, False), self.outcome(f, hdr, True)), "yes")


if __name__ == "__main__":
    unittest.main()
