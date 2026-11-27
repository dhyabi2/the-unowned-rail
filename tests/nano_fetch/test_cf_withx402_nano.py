"""FRONTIER 111 (c): does xmcp#821's payer output reach a Cloudflare Agents `withX402` seller set to network
`nano:mainnet`, through a Nano facilitator? Read as data, never run: cloudflare/agents 1900d09
packages/agents/src/mcp/client/x402.ts, @x402/core 2.17.0 (the version its pnpm-lock.yaml resolves) and
@x402nano/exact 1.1.0 from the npm registry tarballs, basementstudio/xmcp 1a0409a nano-payer.ts.

The seller flow below is a Python reading of x402.ts:243-375 and of @x402/core's x402ResourceServer
(server/index.mjs:458-597, :1059-1075, :1323-1333) and HTTPFacilitatorClient (chunk-YEYZQZNL.mjs:856-990, response
schemas :774-805). The facilitator is a stub on 127.0.0.1 in that HTTP shape: GET /supported, POST /verify and
POST /settle with {x402Version, paymentPayload, paymentRequirements}. It settles a Nano exact payload.block
against a loopback node, keeps spent blocks in a file that survives a restart, and does NOT check the block
signature (a real facilitator must). No key, no seed, no outside network.

fixtures/cf-withx402-nano.json holds the yes/no/UNKNOWN table; Table below keeps it equal to what these tests show.

    python3 -m unittest tests/nano_fetch/test_cf_withx402_nano.py
"""
import base64
import copy
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SKILL_DIR = os.path.join(HERE, "..", "..", "skills", "nano-fetch")  # the-unowned-rail: fetch.py, middleware.py
sys.path[1:1] = [SKILL_DIR, os.path.join(SKILL_DIR, "xno_buyer_plan")]  # plan, wallets, client_fit
import fetch  # noqa: E402,F401  (puts buyer_plan and the payer tools on sys.path)
from client_fit import account_from_key  # noqa: E402
from middleware import check_send_block  # noqa: E402
from wallets import key_from_account  # noqa: E402
from test_xmcp_821_planner import plan_821  # noqa: E402

RAW_PER_XNO = 10 ** 30
NETWORK = "nano:mainnet"
PAY_TO = account_from_key(bytes([21]) * 32)
PAYER = account_from_key(bytes([22]) * 32)
OTHER = account_from_key(bytes([23]) * 32)
META_PAYMENT = "x402/payment"  # x402.ts:169 reads it; nano-payer.ts:9 and :163 write it
FIXTURE = os.path.join(HERE, "fixtures", "cf-withx402-nano.json")


# --- a Python reading of the scheme servers withX402 can hold --------------------------------------------------
class EvmExactStandIn:
    """registerExactEvmScheme (@x402/evm 2.17.0 exact/server/index.mjs:145): registered under 'eip155:*' only."""
    pattern = "eip155:*"


class NanoExactServer:
    """@x402nano/exact 1.1.0 ExactNanoScheme.parsePrice (chunk-NUO6S6HD.mjs:46-80): a number becomes a string;
    a whole-number string is raw units, a decimal string is XNO. enhancePaymentRequirements (:83-89) adds
    workOptional when the facilitator's kind says so. Not registered by withX402 at 1900d09 (x402.ts:202)."""
    pattern = NETWORK

    @staticmethod
    def parse_price(price):
        text = repr(price) if isinstance(price, float) else str(price)
        if re.fullmatch(r"\d+", text):
            return {"amount": text, "asset": "XNO", "extra": {}}
        if re.fullmatch(r"\d*\.\d+", text):
            return {"amount": str(int(Decimal(text) * RAW_PER_XNO)), "asset": "XNO", "extra": {}}
        raise ValueError("Invalid Price.")


def pattern_matches(pattern, network):
    """@x402/core networkMatchesPattern: '*' stands for any suffix."""
    return re.fullmatch(re.escape(pattern).replace(r"\*", ".*"), network) is not None


# --- HTTPFacilitatorClient (chunk-YEYZQZNL.mjs:856-990) ---------------------------------------------------------
class FacilitatorClient:
    def __init__(self, url):
        self.url = url.rstrip("/")

    def _call(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, data=data, method="GET" if body is None else "POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())

    def supported(self):
        doc = self._call("/supported")
        if not isinstance(doc.get("kinds"), list):
            raise ValueError("supported returned invalid data")
        return doc

    def verify(self, payload, requirements):
        doc = self._call("/verify", {"x402Version": payload.get("x402Version"), "paymentPayload": payload,
                                     "paymentRequirements": requirements})
        if not isinstance(doc.get("isValid"), bool):  # verifyResponseSchema :774-781
            raise ValueError("verify returned invalid data")
        return doc

    def settle(self, payload, requirements):
        doc = self._call("/settle", {"x402Version": payload.get("x402Version"), "paymentPayload": payload,
                                     "paymentRequirements": requirements})
        if not isinstance(doc.get("success"), bool) or not isinstance(doc.get("transaction"), str) \
                or not isinstance(doc.get("network"), str):  # settleResponseSchema :782-792
            raise ValueError("settle returned invalid data")
        return doc


# --- withX402(server, cfg).paidTool, read as data ---------------------------------------------------------------
class WithX402Seller:
    def __init__(self, network, recipient, facilitator_url, schemes=(EvmExactStandIn,)):
        self.network = network  # normalizeNetwork (x402.ts:76-78): a CAIP-2 string passes through unchanged
        self.recipient = recipient  # typed `0x${string}` (x402.ts:91); at run time any string reaches payTo
        self.client = FacilitatorClient(facilitator_url)
        self.schemes = list(schemes)
        self.supported = None

    def build_requirements(self, price_usd):
        """server/index.mjs:542-597: no registered server for the network -> [] with a console warning."""
        server = next((s for s in self.schemes if pattern_matches(s.pattern, self.network)), None)
        if server is None:
            return []
        kind = next((k for k in self.supported["kinds"] if k.get("x402Version") == 2
                     and k.get("network") == self.network and k.get("scheme") == "exact"), None)
        if kind is None:
            raise ValueError("Facilitator does not support exact on %s" % self.network)
        parsed = server.parse_price(price_usd)
        extra = dict(parsed["extra"])
        if (kind.get("extra") or {}).get("workOptional") is True and "workOptional" not in extra:
            extra["workOptional"] = True
        return [{"scheme": "exact", "network": self.network, "amount": parsed["amount"], "asset": parsed["asset"],
                 "payTo": self.recipient, "maxTimeoutSeconds": 300, "extra": extra}]

    @staticmethod
    def find_matching(requirements, payload):
        """server/index.mjs:1059-1075 and paymentRequirementsMatchAccepted :1323-1333."""
        accepted = payload.get("accepted") or {}
        if payload.get("x402Version") == 2:
            for req in requirements:
                core = {k: v for k, v in req.items() if k != "extra"}
                if core == {k: v for k, v in accepted.items() if k != "extra"} and all(
                        (accepted.get("extra") or {}).get(k) == v for k, v in req["extra"].items()):
                    return req
            return None
        if payload.get("x402Version") == 1:
            return next((r for r in requirements if r["scheme"] == accepted.get("scheme")
                         and r["network"] == accepted.get("network")), None)
        raise ValueError("Unsupported x402 version")

    def call(self, name, price_usd, tool, args, meta=None):
        """x402.ts:243-375 for one tools/call; `meta` is the request's _meta."""
        if self.supported is None:
            self.supported = self.client.supported()  # ensureInitialized -> resourceServer.initialize()
        try:
            requirements = self.build_requirements(price_usd)
        except ValueError:
            payload = {"x402Version": 2, "error": "PRICE_COMPUTE_FAILED"}
            return {"isError": True, "_meta": {"x402/error": payload},
                    "content": [{"type": "text", "text": json.dumps(payload)}]}
        resource = {"url": "x402://%s" % name, "description": name, "mimeType": "application/json"}

        def payment_required(reason="PAYMENT_REQUIRED", **extra):
            payload = dict({"x402Version": 2, "error": reason, "resource": resource, "accepts": requirements},
                           **extra)
            return {"isError": True, "_meta": {"x402/error": payload},
                    "content": [{"type": "text", "text": json.dumps(payload)}]}

        token = (meta or {}).get(META_PAYMENT)
        if not token or not isinstance(token, str):  # x402.ts:294
            return payment_required()
        try:
            payment = json.loads(base64.b64decode(token, validate=True))  # x402.ts:299, atob
        except ValueError:
            return payment_required("INVALID_PAYMENT")
        match = self.find_matching(requirements, payment)
        if match is None:
            return payment_required("INVALID_PAYMENT")
        try:
            vr = self.client.verify(payment, match)
        except (ValueError, OSError):
            return payment_required("INVALID_PAYMENT")
        if not vr["isValid"]:
            return payment_required(vr.get("invalidReason") or "INVALID_PAYMENT", payer=vr.get("payer"))
        result = {"content": [{"type": "text", "text": tool(args)}]}
        try:
            s = self.client.settle(payment, match)
        except (ValueError, OSError):
            return payment_required("SETTLEMENT_FAILED")
        if not s["success"]:
            return payment_required(s.get("errorReason") or "SETTLEMENT_FAILED")
        result["_meta"] = {"x402/payment-response": {"success": True, "transaction": s["transaction"],
                                                     "network": s["network"], "payer": s.get("payer")}}
        return result


# --- loopback node and stub facilitator -------------------------------------------------------------------------
LEDGER = {}  # hash -> block_info answer; the stub node's whole ledger


class Node(BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode())
        if req.get("action") == "block_info":
            answer = LEDGER.get(str(req.get("hash", "")).upper(), {"error": "Block not found"})
        elif req.get("action") == "process":
            block = req.get("block") or {}
            h, err = check_send_block(block, block.get("link_as_account") or "")
            LEDGER[h] = {"block_account": block["account"], "balance": block["balance"], "subtype": "send",
                         "confirmed": "false", "contents": block}
            answer = {"hash": h}
        else:
            answer = {"error": "unknown action"}
        body = json.dumps(answer).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def node_call(url, doc):
    req = urllib.request.Request(url, data=json.dumps(doc).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


class StubFacilitator(BaseHTTPRequestHandler):
    """Answers in @x402/core's facilitator shape. Proof: payload.block (pursekeeper and x402nano shape, LOG
    2026-11-27 12:3xZ and 12:4xZ). The amount is the previous block's balance minus this block's balance, read
    from the operator's node; the destination is the signed `link`, not link_as_account."""
    node_url = None
    store_path = None

    def spent(self):
        try:
            with open(self.store_path) as f:
                return set(json.load(f))
        except FileNotFoundError:
            return set()

    def mark_spent(self, h):
        done = self.spent() | {h}
        tmp = self.store_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(sorted(done), f)
        os.replace(tmp, self.store_path)

    def check(self, payload, req):
        block = (payload.get("payload") or {}).get("block")
        if req.get("scheme") != "exact" or req.get("network") != NETWORK:
            return None, "unsupported_scheme"
        if not isinstance(block, dict):
            return None, "no_block"
        h, err = check_send_block(block, req.get("payTo"))
        if h is None:
            return None, "wrong_destination" if "link" in err else "invalid_block"
        if h in self.spent():
            return None, "replay"
        prev = node_call(self.node_url, {"action": "block_info", "hash": block["previous"]})
        if "balance" not in prev:
            return None, "previous_not_found"
        if int(prev["balance"]) - int(block["balance"]) != int(req["amount"]):
            return None, "wrong_amount"
        return h, None

    def do_GET(self):
        self.answer({"kinds": [{"x402Version": 2, "scheme": "exact", "network": NETWORK, "extra": {}}],
                     "extensions": [], "signers": {}})

    def do_POST(self):
        doc = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode())
        payload, req = doc.get("paymentPayload") or {}, doc.get("paymentRequirements") or {}
        h, err = self.check(payload, req)
        payer = ((payload.get("payload") or {}).get("block") or {}).get("account")
        if self.path == "/verify":
            self.answer({"isValid": err is None, "invalidReason": err, "payer": payer})
        elif err is not None:
            self.answer({"success": False, "errorReason": err, "transaction": "", "network": NETWORK})
        else:
            block = payload["payload"]["block"]
            node_call(self.node_url, {"action": "process", "json_block": "true", "subtype": "send", "block": block})
            self.mark_spent(h)
            self.answer({"success": True, "transaction": h, "network": NETWORK, "payer": payer})

    def answer(self, doc):
        body = json.dumps(doc).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


# --- the payer: #821's plan and payment object, and a wallet stub that signs nothing ----------------------------
PREVIOUS = "D" * 64
START_BALANCE = 3 * RAW_PER_XNO


def send_block(pay_to, amount_raw, previous=PREVIOUS):
    """What a payer's wallet would hand over unsigned-by-us: a state send to pay_to. Dummy signature and work."""
    return {"type": "state", "account": PAYER, "previous": previous, "representative": PAYER,
            "balance": str(START_BALANCE - int(amount_raw)), "link": key_from_account(pay_to).hex().upper(),
            "link_as_account": pay_to, "signature": "5A" * 64, "work": "0" * 16}


def payment_821(offer_result, block_hash):
    """nano-payer.ts:166-191 for a v2 offer: {x402Version, resource, accepted, payload: {blockHash}}."""
    plan = plan_821(offer_result, max_amount_raw=RAW_PER_XNO)
    offer = json.loads(offer_result["content"][0]["text"])
    return plan, {"x402Version": 2, "resource": offer["resource"], "accepted": plan["accepted"],
                  "payload": {"blockHash": block_hash.upper()}}


def as_token(obj):
    return base64.b64encode(json.dumps(obj).encode()).decode()


class Loopback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = HTTPServer(("127.0.0.1", 0), Node)
        threading.Thread(target=cls.node.serve_forever, daemon=True).start()
        cls.node_url = "http://127.0.0.1:%d/" % cls.node.server_address[1]
        LEDGER[PREVIOUS] = {"block_account": PAYER, "balance": str(START_BALANCE), "confirmed": "true"}

    @classmethod
    def tearDownClass(cls):
        cls.node.shutdown()
        cls.node.server_close()

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = os.path.join(self.dir, "spent.json")
        self.fac, self.fac_url = self.start_facilitator()

    def tearDown(self):
        self.fac.shutdown()
        self.fac.server_close()
        shutil.rmtree(self.dir)

    def start_facilitator(self):
        handler = type("Fac", (StubFacilitator,), {"node_url": self.node_url, "store_path": self.store})
        server = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, "http://127.0.0.1:%d" % server.server_address[1]

    def seller(self, schemes=(EvmExactStandIn, NanoExactServer), url=None):
        return WithX402Seller(NETWORK, PAY_TO, url or self.fac_url, schemes)

    def weather(self, seller, meta=None, price="0.001"):
        return seller.call("weather", price, lambda a: "sunny in %s" % a["city"], {"city": "Oslo"}, meta)

    def block_payment(self, offer, **override):
        plan = plan_821(offer, max_amount_raw=RAW_PER_XNO)
        block = send_block(override.get("pay_to", plan["payTo"]), override.get("amount", plan["amountRaw"]))
        _, pay = payment_821(offer, "0" * 64)
        pay["payload"] = {"block": block}
        return pay

    # --- C1-C4: what #821 meets at a stock withX402 seller --------------------------------------------------
    def test_c1_meta_key_is_the_same(self):
        seller = self.seller()
        offer = self.weather(seller)
        _, pay = payment_821(offer, "A" * 64)
        meta = {META_PAYMENT: as_token(pay)}
        # the seller finds the token under #821's key: it gets past the PAYMENT_REQUIRED gate to verify
        r = self.weather(seller, meta)
        self.assertNotEqual(json.loads(r["content"][0]["text"])["error"], "PAYMENT_REQUIRED")

    def test_c2_821_writes_an_object_withx402_wants_a_base64_string(self):
        seller = self.seller()
        offer = self.weather(seller)
        _, pay = payment_821(offer, "A" * 64)
        r = self.weather(seller, {META_PAYMENT: pay})
        self.assertEqual(json.loads(r["content"][0]["text"])["error"], "PAYMENT_REQUIRED")

    def test_c3_821_reads_the_withx402_offer(self):
        plan = plan_821(self.weather(self.seller()), max_amount_raw=RAW_PER_XNO)
        self.assertEqual((plan["x402Version"], plan["accepted"]["network"], plan["payTo"]),
                         (2, NETWORK, PAY_TO))
        self.assertEqual(plan["amountRaw"], str(RAW_PER_XNO // 1000))  # "0.001" read as XNO by @x402nano/exact

    def test_c4_stock_withx402_offers_nothing_on_nano(self):
        stock = self.seller(schemes=(EvmExactStandIn,))
        offer = self.weather(stock)
        self.assertEqual(json.loads(offer["content"][0]["text"])["accepts"], [])
        with self.assertRaises(Exception):
            plan_821(offer, max_amount_raw=RAW_PER_XNO)

    def test_c5_price_usd_is_read_in_xno_units(self):
        self.assertEqual(NanoExactServer.parse_price(0.01)["amount"], str(RAW_PER_XNO // 100))
        self.assertEqual(NanoExactServer.parse_price(1)["amount"], "1")  # a whole number is raw, not 1 XNO

    def test_c6_blockhash_payload_meets_a_block_facilitator(self):
        seller = self.seller()
        _, pay = payment_821(self.weather(seller), "A" * 64)
        r = self.weather(seller, {META_PAYMENT: as_token(pay)})
        self.assertEqual(json.loads(r["content"][0]["text"])["error"], "no_block")

    # --- C7: the facilitator shape itself settles a Nano exact payload.block -------------------------------
    def test_c7_payload_block_settles_end_to_end(self):
        seller = self.seller()
        pay = self.block_payment(self.weather(seller))
        r = self.weather(seller, {META_PAYMENT: as_token(pay)})
        self.assertNotIn("isError", r)
        self.assertEqual(r["content"][0]["text"], "sunny in Oslo")
        receipt = r["_meta"]["x402/payment-response"]
        h, _ = check_send_block(pay["payload"]["block"], PAY_TO)
        self.assertEqual((receipt["transaction"], receipt["network"], receipt["payer"]), (h, NETWORK, PAYER))
        self.assertIn(h, LEDGER)

    def test_replay_refused_and_survives_facilitator_restart(self):
        seller = self.seller()
        pay = self.block_payment(self.weather(seller))
        self.assertNotIn("isError", self.weather(seller, {META_PAYMENT: as_token(pay)}))
        r = self.weather(seller, {META_PAYMENT: as_token(pay)})
        self.assertEqual(json.loads(r["content"][0]["text"])["error"], "replay")
        self.fac.shutdown()
        self.fac.server_close()
        self.fac, url = self.start_facilitator()
        again = self.weather(self.seller(url=url), {META_PAYMENT: as_token(pay)})
        self.assertEqual(json.loads(again["content"][0]["text"])["error"], "replay")

    def test_wrong_amount_and_destination_refused(self):
        seller = self.seller()
        offer = self.weather(seller)
        amount = RAW_PER_XNO // 1000
        for override, reason in (({"amount": amount - 1}, "wrong_amount"), ({"amount": amount + 1}, "wrong_amount"),
                                 ({"pay_to": OTHER}, "wrong_destination")):
            pay = self.block_payment(offer, **override)
            r = self.weather(seller, {META_PAYMENT: as_token(pay)})
            self.assertEqual(json.loads(r["content"][0]["text"])["error"], reason, override)

    def test_tampered_accepted_does_not_match(self):
        seller = self.seller()
        pay = self.block_payment(self.weather(seller))
        pay["accepted"] = dict(pay["accepted"], amount="1")
        r = self.weather(seller, {META_PAYMENT: as_token(pay)})
        self.assertEqual(json.loads(r["content"][0]["text"])["error"], "INVALID_PAYMENT")


class Table(unittest.TestCase):
    """The fixture's answers are the ones the tests above show; a changed reading must change both."""
    WANT = {"C1": "yes", "C2": "no", "C3": "yes", "C4": "no", "C5": "no", "C6": "no", "C7": "yes",
            "C8": "no", "C9": "UNKNOWN"}

    def test_fixture_matches(self):
        with open(FIXTURE) as f:
            doc = json.load(f)
        got = {c["id"]: c["answer"] for c in doc["cells"]}
        self.assertEqual(got, self.WANT)
        self.assertEqual(doc["overall"]["answer"], "no")
        for c in doc["cells"]:
            self.assertTrue(c["source"].strip(), c["id"])
            self.assertIn(c["answer"], ("yes", "no", "UNKNOWN"))
        self.assertEqual(doc["pins"]["cloudflare/agents"], "1900d09")
        self.assertTrue(doc["pins"]["basementstudio/xmcp"].startswith("1a0409a"))

    def test_no_key_or_seed_in_fixture(self):
        with open(FIXTURE) as f:
            text = f.read().lower()
        for word in ("seed", "private", "secret"):
            self.assertNotIn(word, re.sub(r"no key, no seed|accountprivatekey", "", text))


if __name__ == "__main__":
    unittest.main()
