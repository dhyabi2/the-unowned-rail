"""Tests for nano_fetch. Loopback only: a local http.server answers the 402s, and any connection to a host
other than 127.0.0.1 fails the test. No key, no Scrapy, no install.

    python3 -m unittest tests/nano_fetch/test_fetch.py
"""
import base64
import http.server
import io
import json
import os
import socket
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, HERE)
SKILL_DIR = os.path.join(HERE, "..", "..", "skills", "nano-fetch")  # the-unowned-rail: fetch.py, middleware.py
sys.path[1:1] = [SKILL_DIR, os.path.join(SKILL_DIR, "xno_buyer_plan")]  # plan, wallets, client_fit
import fetch as nf  # noqa: E402
from plan import order_representative  # noqa: E402  (buyer_plan, put on sys.path by fetch)

FIXTURES = os.path.join(HERE, "client_fit_fixtures.json")
RAW_PER_XNO = 10 ** 30
PRICE = str(5 * RAW_PER_XNO // 4)  # 1.25 XNO, the gateway fixture's amount, derived here
HASH = "ab" * 32
PAY_TO = "nano_1111111111111111111111111111111111111111111111111111hifc8npp"
ORDER = "Hn4pY8sDk2Wj6eLx0RvT5g"


def gateway_fixture():
    with open(FIXTURES, encoding="utf-8") as f:
        d = json.load(f)
    items = d if isinstance(d, list) else d["fixtures"]
    return [x for x in items if x["id"] == "x402-gateway-0.18.2-rep"][0]


def v1_body(order=ORDER, amount=PRICE):
    """x402 v1: the quote is the JSON body, the amount is maxAmountRequired, the proof goes in X-PAYMENT."""
    return {"x402Version": 1, "error": "X-PAYMENT header is required",
            "accepts": [{"scheme": "exact", "network": "nano", "maxAmountRequired": amount,
                         "resource": "http://127.0.0.1/paid", "payTo": PAY_TO, "asset": "XNO",
                         "maxTimeoutSeconds": 300,
                         "extra": {"decimals": 30, "binding": "xno-binding/v1/rep", "orderId": order}}]}


def send_hash_body(nonce="n-0001"):
    return {"network": "nano:mainnet", "pay_to": PAY_TO, "amount_raw": str(RAW_PER_XNO // 1000),
            "retry_header": "X-Nano-Payment: <send hash>", "nonce": nonce}


class Seller:
    """Answers 402 until a request carries `paid_header`; records every request's headers."""

    def __init__(self, quote_headers, quote_body, paid_header, always_402=False, paid_redirect=None):
        self.quote_headers, self.quote_body = quote_headers, quote_body
        self.paid_header, self.always_402 = paid_header.lower(), always_402
        self.paid_redirect = paid_redirect  # a URL the paid request is sent on to with 302
        self.seen = []


def serve(seller):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _answer(self):
            hdrs = {k.lower(): v for k, v in self.headers.items()}
            seller.seen.append((self.command, self.path, hdrs))
            if self.path == "/free":
                return self._send(200, {}, b"free page")
            if seller.paid_header in hdrs and not seller.always_402:
                if seller.paid_redirect:
                    return self._send(302, {"Location": seller.paid_redirect}, b"")
                return self._send(200, {}, b"paid page")
            self._send(402, seller.quote_headers, seller.quote_body)

        def _send(self, code, headers, body):
            body = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            self.send_response(code)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = _answer

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class Signer:
    def __init__(self, answer=HASH):
        self.calls, self.answer = [], answer

    def __call__(self, order):
        self.calls.append(order)
        return self.answer


def decode(value):
    return json.loads(base64.b64decode(value))


class Base(unittest.TestCase):
    def setUp(self):
        self._cc = socket.create_connection

        def loopback_only(addr, *a, **k):
            if addr[0] not in ("127.0.0.1", "localhost"):
                raise AssertionError("non-loopback connection attempted: %r" % (addr,))
            return self._cc(addr, *a, **k)
        socket.create_connection = loopback_only
        self.dir = tempfile.mkdtemp()
        self.jpath = os.path.join(self.dir, "pay.jsonl")
        self.cap = str(2 * RAW_PER_XNO)
        self.servers = []
        os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"

    def tearDown(self):
        socket.create_connection = self._cc
        for s in self.servers:
            s.shutdown()
            s.server_close()

    def start(self, seller):
        srv = serve(seller)
        self.servers.append(srv)
        return "http://127.0.0.1:%d" % srv.server_address[1]

    def gateway_seller(self, **kw):
        f = gateway_fixture()
        return Seller({"PAYMENT-REQUIRED": f["headers"]["PAYMENT-REQUIRED"]}, f["body"], "PAYMENT-SIGNATURE", **kw)

    def journal_rows(self):
        if not os.path.exists(self.jpath):
            return []
        with open(self.jpath, encoding="utf-8") as f:
            return [json.loads(x) for x in f if x.strip()]

    def opener(self):
        import urllib.request
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def fetch(self, url, **kw):
        kw.setdefault("cap_raw", self.cap)
        kw.setdefault("opener", self.opener())
        return nf.fetch(url, **kw)


class OffByDefault(Base):
    def test_free_page_passes_through(self):
        s = Signer()
        base = self.start(self.gateway_seller())
        r = self.fetch(base + "/free", signer=s, journal_path=self.jpath)
        self.assertEqual((r.status, r.body, r.paid, r.refusal), (200, b"free page", None, None))
        self.assertEqual(s.calls, [])

    def test_402_without_signer_is_not_paid(self):
        base = self.start(self.gateway_seller())
        r = self.fetch(base + "/paid")
        self.assertEqual(r.status, 402)
        self.assertEqual(r.refusal[0], "not_configured")
        self.assertEqual(self.journal_rows(), [])


class PaysBoundOrders(Base):
    def test_v2_gateway_fixture_pays_once_and_retries(self):
        seller = self.gateway_seller()
        base = self.start(seller)
        s = Signer()
        r = self.fetch(base + "/paid", signer=s, journal_path=self.jpath)
        self.assertEqual((r.status, r.body), (200, b"paid page"))
        self.assertEqual(len(s.calls), 1)
        order = s.calls[0]
        self.assertEqual(order["amount_raw"], PRICE)
        self.assertEqual(order["payTo"], PAY_TO)
        self.assertEqual(order["orderId"], ORDER)
        self.assertEqual(order["representative"], order_representative(ORDER, PAY_TO, PRICE))
        proof = decode(seller.seen[-1][2]["payment-signature"])
        self.assertEqual(proof["x402Version"], 2)
        self.assertEqual(proof["payload"], {"orderId": ORDER, "blockHash": HASH.upper()})
        self.assertEqual(proof["accepted"]["network"], "nano")
        self.assertEqual([x["state"] for x in self.journal_rows()], ["intent", "paid"])

    def test_v1_body_quote_retries_with_x_payment(self):
        seller = Seller({}, v1_body(), "X-PAYMENT")
        base = self.start(seller)
        s = Signer()
        r = self.fetch(base + "/paid", signer=s, journal_path=self.jpath)
        self.assertEqual((r.status, r.body), (200, b"paid page"))
        self.assertEqual(len(s.calls), 1)
        self.assertEqual(s.calls[0]["representative"], order_representative(ORDER, PAY_TO, PRICE))
        proof = decode(seller.seen[-1][2]["x-payment"])
        self.assertEqual(proof, {"x402Version": 1, "scheme": "exact", "network": "nano",
                                 "payload": {"orderId": ORDER, "blockHash": HASH.upper()}})
        self.assertNotIn("payment-signature", seller.seen[-1][2])

    def test_proof_is_not_carried_to_a_redirect_target(self):
        other = self.gateway_seller()
        other_base = self.start(other)
        seller = self.gateway_seller(paid_redirect=other_base + "/free")
        base = self.start(seller)
        s = Signer()
        r = self.fetch(base + "/paid", signer=s, journal_path=self.jpath)
        self.assertEqual((r.status, r.body), (200, b"free page"))
        self.assertEqual(len(s.calls), 1)
        self.assertIn("payment-signature", seller.seen[-1][2])
        self.assertEqual(len(other.seen), 1)
        self.assertNotIn("payment-signature", other.seen[0][2])


class Guards(Base):
    def test_replay_refused_after_restart(self):
        base = self.start(self.gateway_seller())
        self.fetch(base + "/paid", signer=Signer(), journal_path=self.jpath)
        s2 = Signer()  # a new process: only the journal file carries over
        r = self.fetch(base + "/paid", signer=s2, journal_path=self.jpath)
        self.assertEqual((r.status, r.refusal[0]), (402, "replayed"))
        self.assertEqual(s2.calls, [])

    def test_over_cap(self):
        base = self.start(self.gateway_seller())
        s = Signer()
        r = self.fetch(base + "/paid", signer=s, journal_path=self.jpath, cap_raw=str(RAW_PER_XNO))
        self.assertEqual(r.refusal[0], "over_cap")
        self.assertEqual(s.calls, [])

    def test_over_budget_counts_the_journal(self):
        base = self.start(Seller({}, v1_body("Order-AAAAAAAAAAAAAAAAAAAAA"), "X-PAYMENT"))
        self.fetch(base + "/paid", signer=Signer(), journal_path=self.jpath, budget_raw=2 * RAW_PER_XNO)
        base2 = self.start(Seller({}, v1_body("Order-BBBBBBBBBBBBBBBBBBBBB"), "X-PAYMENT"))
        s = Signer()
        r = self.fetch(base2 + "/paid", signer=s, journal_path=self.jpath, budget_raw=2 * RAW_PER_XNO)
        self.assertEqual(r.refusal[0], "over_budget")
        self.assertEqual(s.calls, [])

    def test_signer_without_hash_leaves_intent_and_never_retries(self):
        seller = self.gateway_seller()
        base = self.start(seller)
        r = self.fetch(base + "/paid", signer=Signer(answer=None), journal_path=self.jpath)
        self.assertEqual((r.status, r.refusal[0]), (402, "signer_no_hash"))
        self.assertEqual(len(seller.seen), 1)
        self.assertEqual([x["state"] for x in self.journal_rows()], ["intent"])
        s2 = Signer()
        r = self.fetch(base + "/paid", signer=s2, journal_path=self.jpath)
        self.assertEqual(r.refusal[0], "replayed")
        self.assertEqual(s2.calls, [])

    def test_paid_retry_meeting_402_is_not_paid_again(self):
        seller = self.gateway_seller(always_402=True)
        base = self.start(seller)
        s = Signer()
        r = self.fetch(base + "/paid", signer=s, journal_path=self.jpath)
        self.assertEqual((r.status, r.refusal[0]), (402, "paid_retry_402"))
        self.assertEqual(len(s.calls), 1)
        self.assertEqual(len(seller.seen), 2)

    def test_zero_amount_is_refused(self):
        base = self.start(Seller({}, v1_body(amount="0"), "X-PAYMENT"))
        r = self.fetch(base + "/paid", signer=Signer(), journal_path=self.jpath)
        self.assertEqual(r.refusal[0], "no_amount")


class SendHash(Base):
    def test_refused_as_unbound_by_default(self):
        base = self.start(Seller({}, send_hash_body(), "X-Nano-Payment"))
        s = Signer()
        r = self.fetch(base + "/paid", signer=s, journal_path=self.jpath)
        self.assertEqual(r.refusal[0], "unbound")
        self.assertEqual(s.calls, [])
        self.assertEqual(self.journal_rows(), [])

    def test_paid_with_allow_unbound(self):
        seller = Seller({}, send_hash_body(), "X-Nano-Payment")
        base = self.start(seller)
        s = Signer()
        r = self.fetch(base + "/paid", signer=s, journal_path=self.jpath, allow_unbound=True)
        self.assertEqual((r.status, r.body), (200, b"paid page"))
        self.assertIsNone(s.calls[0]["representative"])
        self.assertEqual(s.calls[0]["amount_raw"], str(RAW_PER_XNO // 1000))
        self.assertEqual(seller.seen[-1][2]["x-nano-payment"], HASH.upper())


class Command(Base):
    def run_cli(self, argv):
        out, err = io.BytesIO(), io.StringIO()
        orig = nf.fetch

        def no_proxy_fetch(*a, **k):
            k.setdefault("opener", self.opener())
            return orig(*a, **k)
        nf.fetch = no_proxy_fetch
        try:
            code = nf.main(argv, out=out, err=err)
        finally:
            nf.fetch = orig
        return code, out.getvalue(), err.getvalue()

    def test_cli_pays_with_dotted_signer_and_writes_output(self):
        base = self.start(self.gateway_seller())
        dest = os.path.join(self.dir, "page.out")
        code, out, err = self.run_cli([base + "/paid", "--signer", "test_fetch.dotted_signer",
                                       "--journal", self.jpath, "--cap-raw", self.cap, "-o", dest])
        self.assertEqual(code, 0, err)
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), b"paid page")
        self.assertIn("paid %s raw" % PRICE, err)

    def test_cli_unpaid_402_exits_3(self):
        base = self.start(self.gateway_seller())
        code, out, err = self.run_cli([base + "/paid"])
        self.assertEqual(code, 3)
        self.assertIn("not_configured", err)

    def test_cli_signer_needs_journal(self):
        code, out, err = self.run_cli(["http://127.0.0.1:9/x", "--signer", "test_fetch.dotted_signer"])
        self.assertEqual(code, 2)

    def test_cli_cap_must_be_digits(self):
        code, out, err = self.run_cli(["http://127.0.0.1:9/x", "--cap-raw", "1.5"])
        self.assertEqual(code, 2)


class _StubAccount:
    """Key-free stand-in for nanopy.Account (28.0.1.post26 __init__.py:187-391): an address, a state and
    unsigned blocks. Nothing is signed; the block hash is buyer_plan's state_block_hash (so the hash
    cross-check pins the block FIELDS, not nanopy's hash), lower-cased as nanopy's hexdigest() is (:430)."""

    def __init__(self, log, addr):
        self.log, self.addr = log, addr
        self.frontier, self.raw_bal, self.rep = None, None, None

    @property
    def state(self):
        return self.frontier, self.raw_bal, self.rep

    @state.setter
    def state(self, value):
        self.frontier, self.raw_bal, self.rep = value

    def _block(self, rep, bal, link):
        import wallets
        b = {"type": "state", "account": self.addr, "previous": self.frontier, "representative": rep.addr,
             "balance": str(bal), "link": link}
        b["hash"] = wallets.state_block_hash(b).lower()
        self.frontier, self.raw_bal, self.rep = b["hash"], bal, rep
        return b

    def send(self, to, raw_amt, rep=None, work=""):
        import wallets
        self.log.append(("send", to.addr, raw_amt, rep.addr if rep else None))
        if not isinstance(raw_amt, int) or raw_amt <= 0 or self.raw_bal - raw_amt < 0:
            raise ValueError("amount")
        return self._block(rep or self.rep, self.raw_bal - raw_amt, wallets.key_from_account(to.addr).hex())

    def change_rep(self, rep, work=""):
        self.log.append(("change_rep", rep.addr))
        return self._block(rep, self.raw_bal, "0" * 64)


class _StubNode:
    """Key-free stand-in for nanopy.rpc.HTTP: account_info, process, block_info (confirmed is the string
    "true" on the second read, as rpc.py _Bool is a string enum :30)."""

    def __init__(self, log, account, frontier, balance, prior_rep):
        self.log = log
        self.info = {account: {"frontier": frontier, "balance": str(balance), "representative": prior_rep}}
        self.published, self.reads = [], {}

    def account_info(self, account, representative=False):
        self.log.append(("account_info", account, representative))
        return dict(self.info[account])

    def process(self, block, subtype=""):
        self.log.append(("process", subtype))
        self.published.append(dict(block))
        acct = self.info[block["account"]]
        acct.update(frontier=block["hash"], balance=block["balance"], representative=block["representative"])
        return {"hash": block["hash"]}

    def block_info(self, h):
        self.reads[h] = self.reads.get(h, 0) + 1
        self.log.append(("block_info", h))
        return {"confirmed": "true" if self.reads[h] >= 2 else "false"}


class NanopyRecipeOrder(Base):
    """buyer_plan/NANOPY-BOUND-SEND.md steps 2-5 as a signer hook, with key-free stubs in place of nanopy (a
    hand copy of the recipe, not its text): the order of calls, the arguments, the returned hash, the prior
    representative kept in a file across processes, and one restore after the last settled order."""

    ORDER2 = "Zq7tR2mVb9Kx4cNw1PsH8y"

    def recipe(self, log, node, payer_addr, prior_file):
        """One process's copy of the recipe module: sign_bound_send and restore, sharing only the file."""
        def acct(addr):
            return _StubAccount(log, "nano_" + addr[4:] if addr.startswith("xrb_") else addr)

        def confirmed(h):
            for _ in range(5):
                if node.block_info(h).get("confirmed") in ("true", "1"):
                    return True
            return False

        def read_prior(payer):
            import client_fit as cf
            with open(prior_file) as f:
                owner, prior = f.read().split()
            if not (cf.nano_checksum_ok(owner) and cf.nano_checksum_ok(prior)):
                raise ValueError("bad checksum")
            if owner != payer.addr:
                raise ValueError("prior-rep file belongs to another payer")
            return acct(prior)

        def write_prior(payer, rep_addr):
            tmp = prior_file + ".tmp"
            with open(tmp, "w") as f:
                f.write(payer.addr + " " + rep_addr + "\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, prior_file)
            dfd = os.open(os.path.dirname(prior_file), os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)

        import contextlib
        import fcntl

        @contextlib.contextmanager
        def locked():
            with open(prior_file + ".lock", "a") as lk:
                fcntl.flock(lk.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lk.fileno(), fcntl.LOCK_UN)

        def sign_bound_send(order):
            with locked():
                return _sign_bound_send(order)

        def _sign_bound_send(order):
            payer = acct(payer_addr)
            info = node.account_info(payer.addr, representative=True)
            rep = acct(order["representative"]) if order["representative"] else None
            if rep is not None:
                if os.path.exists(prior_file):
                    try:
                        read_prior(payer)
                    except (ValueError, OSError):
                        return None
                else:
                    write_prior(payer, info["representative"])
            payer.state = (info["frontier"], int(info["balance"]), acct(info["representative"]))
            send = payer.send(acct(order["payTo"]), int(order["amount_raw"]), rep=rep)
            h = node.process(send, subtype="send")["hash"]
            return h if confirmed(h) else None

        def restore():
            with locked():
                _restore()

        def _restore():
            if not os.path.exists(prior_file):
                return
            payer = acct(payer_addr)
            prior_rep = read_prior(payer)
            info = node.account_info(payer.addr, representative=True)
            payer.state = (info["frontier"], int(info["balance"]), acct(info["representative"]))
            if info["representative"] != prior_rep.addr:
                h = node.process(payer.change_rep(prior_rep), subtype="change")["hash"]
                if not confirmed(h):
                    return
            os.remove(prior_file)
        return sign_bound_send, restore

    def test_recipe_call_order_pays_two_bound_orders_and_restores_once(self):
        import client_fit as cf
        import plan as bp
        import wallets
        log = []
        payer_addr = cf.account_from_key(bytes(range(32)))
        prior = cf.account_from_key(bytes([7]) * 32)
        frontier = "%064X" % 0x1F
        balance = 10 * RAW_PER_XNO
        node = _StubNode(log, payer_addr, frontier, balance, prior)
        prior_file = os.path.join(self.dir, "prior-rep")

        # process 1: the v2 gateway order
        sign1, _ = self.recipe(log, node, payer_addr, prior_file)
        seller = self.gateway_seller()
        r = self.fetch(self.start(seller) + "/paid", signer=sign1, journal_path=self.jpath)
        self.assertEqual((r.status, r.body), (200, b"paid page"))
        bound = order_representative(ORDER, PAY_TO, PRICE)
        send_hash = node.published[0]["hash"]
        self.assertEqual(log, [("account_info", payer_addr, True), ("send", PAY_TO, int(PRICE), bound),
                               ("process", "send"), ("block_info", send_hash), ("block_info", send_hash)])
        proof = decode(seller.seen[-1][2]["payment-signature"])
        self.assertEqual(proof["payload"], {"orderId": ORDER, "blockHash": send_hash.upper()})
        self.assertEqual(self.journal_rows()[-1]["blockHash"], send_hash.upper())
        with open(prior_file) as f:
            self.assertEqual(f.read(), payer_addr + " " + prior + "\n")
        self.assertFalse(os.path.exists(prior_file + ".tmp"))
        # step 3's cross-check: buyer_plan's own unsigned send block has the same fields, so the same hash
        f = gateway_fixture()
        plan = bp.plan_402({"PAYMENT-REQUIRED": f["headers"]["PAYMENT-REQUIRED"]}, f["body"], self.cap)
        out = wallets.wallet_calls(plan, account={"account": payer_addr, "previous": frontier,
                                                  "balance": str(balance), "representative": prior})
        self.assertEqual(wallets.state_block_hash(out["unsigned_block"]), send_hash.upper())

        # process 2 (a restart): a second, v1 order; account_info now shows the FIRST bound rep, which must
        # not replace the prior rep kept in the file
        del log[:]
        sign2, _ = self.recipe(log, node, payer_addr, prior_file)
        r = self.fetch(self.start(Seller({}, v1_body(order=self.ORDER2), "X-PAYMENT")) + "/paid",
                       signer=sign2, journal_path=self.jpath)
        self.assertEqual((r.status, r.body), (200, b"paid page"))
        bound2 = order_representative(self.ORDER2, PAY_TO, PRICE)
        self.assertEqual(log[1], ("send", PAY_TO, int(PRICE), bound2))
        with open(prior_file) as f:
            self.assertEqual(f.read(), payer_addr + " " + prior + "\n")
        self.assertFalse(os.path.exists(prior_file + ".tmp"))

        # process 3: restore once, after the last settled order
        del log[:]
        _, restore = self.recipe(log, node, payer_addr, prior_file)
        restore()
        change_hash = node.published[2]["hash"]
        self.assertEqual(log, [("account_info", payer_addr, True), ("change_rep", prior), ("process", "change"),
                               ("block_info", change_hash), ("block_info", change_hash)])
        self.assertEqual(node.published[2]["previous"], node.published[1]["hash"])
        self.assertFalse(os.path.exists(prior_file))
        self.assertEqual(node.info[payer_addr]["representative"], prior)
        self.assertEqual(int(node.info[payer_addr]["balance"]), balance - 2 * int(PRICE))
        restore()  # nothing left to restore: no further call
        self.assertEqual(len(node.published), 3)

    def test_restore_waits_for_a_bound_send_in_progress(self):
        # reviewer finding (rail 207): restore() in another process must not change the rep and delete the
        # file while a bound send holds the lock between account_info and process
        import fcntl
        import threading
        import client_fit as cf
        log = []
        payer_addr = cf.account_from_key(bytes(range(32)))
        prior = cf.account_from_key(bytes([7]) * 32)
        node = _StubNode(log, payer_addr, "%064X" % 0x1F, 10 * RAW_PER_XNO, prior)
        node.info[payer_addr]["representative"] = order_representative(ORDER, PAY_TO, PRICE)
        prior_file = os.path.join(self.dir, "prior-rep")
        with open(prior_file, "w") as f:
            f.write(payer_addr + " " + prior + "\n")
        _, restore = self.recipe(log, node, payer_addr, prior_file)
        with open(prior_file + ".lock", "a") as held:   # a bound send of another process, mid-flight
            fcntl.flock(held.fileno(), fcntl.LOCK_EX)
            t = threading.Thread(target=restore)
            t.start()
            t.join(0.3)
            self.assertTrue(t.is_alive())
            self.assertEqual(log, [])
            self.assertTrue(os.path.exists(prior_file))
            fcntl.flock(held.fileno(), fcntl.LOCK_UN)
        t.join(5)
        self.assertFalse(t.is_alive())
        self.assertFalse(os.path.exists(prior_file))
        self.assertEqual(node.info[payer_addr]["representative"], prior)

    def test_two_bound_sends_on_one_host_wait_and_chain(self):
        # rail 209 (review of rail 207's lock): the same lock serializes two paying processes on one host, so
        # the second reads the first's new frontier instead of both building on the same one
        import fcntl
        import threading
        import client_fit as cf
        log = []
        payer_addr = cf.account_from_key(bytes(range(32)))
        prior = cf.account_from_key(bytes([7]) * 32)
        node = _StubNode(log, payer_addr, "%064X" % 0x1F, 10 * RAW_PER_XNO, prior)
        prior_file = os.path.join(self.dir, "prior-rep")
        orders = [{"representative": order_representative(o, PAY_TO, PRICE), "payTo": PAY_TO,
                   "amount_raw": PRICE} for o in (ORDER, self.ORDER2)]
        hashes = []
        threads = []
        with open(prior_file + ".lock", "a") as held:
            fcntl.flock(held.fileno(), fcntl.LOCK_EX)
            for o in orders:
                sign, _ = self.recipe(log, node, payer_addr, prior_file)
                threads.append(threading.Thread(target=lambda s=sign, o=o: hashes.append(s(o))))
                threads[-1].start()
            threads[-1].join(0.3)
            self.assertEqual(log, [])
            fcntl.flock(held.fileno(), fcntl.LOCK_UN)
        for t in threads:
            t.join(5)
            self.assertFalse(t.is_alive())
        self.assertEqual(len(node.published), 2)
        self.assertEqual(node.published[1]["previous"], node.published[0]["hash"])
        self.assertEqual(sorted(hashes), sorted(p["hash"] for p in node.published))
        with open(prior_file) as f:
            self.assertEqual(f.read(), payer_addr + " " + prior + "\n")

    def _bad_prior_file_sends_nothing(self, content):
        import client_fit as cf
        log = []
        payer_addr = cf.account_from_key(bytes(range(32)))
        prior = cf.account_from_key(bytes([7]) * 32)
        node = _StubNode(log, payer_addr, "%064X" % 0x1F, 10 * RAW_PER_XNO, prior)
        prior_file = os.path.join(self.dir, "prior-rep")
        with open(prior_file, "w") as f:
            f.write(content(payer_addr, prior))
        sign, restore = self.recipe(log, node, payer_addr, prior_file)
        r = self.fetch(self.start(self.gateway_seller()) + "/paid", signer=sign, journal_path=self.jpath)
        self.assertEqual(r.status, 402)
        self.assertEqual(node.published, [])
        self.assertEqual([x["state"] for x in self.journal_rows()], ["intent"])
        with self.assertRaises(ValueError):
            restore()  # never guesses a representative from a bad file
        self.assertEqual(node.published, [])
        self.assertTrue(os.path.exists(prior_file))

    def test_empty_prior_file_sends_nothing(self):
        # a crash between creating the file and writing it must not let a bound send through
        self._bad_prior_file_sends_nothing(lambda payer, prior: "")

    def test_prior_file_of_another_payer_sends_nothing(self):
        import client_fit as cf
        other = cf.account_from_key(bytes([9]) * 32)
        self._bad_prior_file_sends_nothing(lambda payer, prior: other + " " + prior + "\n")

    def test_prior_file_with_bad_checksum_sends_nothing(self):
        def broken(payer, prior):
            last = "1" if prior[-1] != "1" else "3"
            return payer + " " + prior[:-1] + last + "\n"
        self._bad_prior_file_sends_nothing(broken)

    def test_restore_keeps_the_file_when_the_change_is_not_confirmed(self):
        import client_fit as cf
        log = []
        payer_addr = cf.account_from_key(bytes(range(32)))
        prior = cf.account_from_key(bytes([7]) * 32)
        node = _StubNode(log, payer_addr, "%064X" % 0x1F, 10 * RAW_PER_XNO, prior)
        prior_file = os.path.join(self.dir, "prior-rep")
        sign, restore = self.recipe(log, node, payer_addr, prior_file)
        r = self.fetch(self.start(self.gateway_seller()) + "/paid", signer=sign, journal_path=self.jpath)
        self.assertEqual(r.status, 200)
        node.block_info = lambda h: {"confirmed": "false"}
        restore()
        self.assertTrue(os.path.exists(prior_file))
        with open(prior_file) as f:
            self.assertEqual(f.read(), payer_addr + " " + prior + "\n")

    def test_unconfirmed_send_is_not_a_hash(self):
        import client_fit as cf
        log = []
        payer_addr = cf.account_from_key(bytes(range(32)))
        node = _StubNode(log, payer_addr, "%064X" % 0x1F, 10 * RAW_PER_XNO, cf.account_from_key(bytes([7]) * 32))
        node.block_info = lambda h: {"confirmed": "false"}
        sign, _ = self.recipe(log, node, payer_addr, os.path.join(self.dir, "prior-rep"))
        r = self.fetch(self.start(self.gateway_seller()) + "/paid", signer=sign, journal_path=self.jpath)
        self.assertEqual(r.status, 402)
        self.assertEqual([x["state"] for x in self.journal_rows()], ["intent"])


def dotted_signer(order):
    return HASH


if __name__ == "__main__":
    unittest.main()
