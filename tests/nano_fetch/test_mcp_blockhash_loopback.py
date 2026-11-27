"""FRONTIER 110 (c): an MCP tools/call paid in xmcp#821's _meta['x402/payment'] blockHash shape settles against our
own stub seller (mcp_blockhash_seller.py), through a loopback node on 127.0.0.1. The payer side is plan_821 (the
Python reading of nano-payer.ts:103-158 kept honest by test_xmcp_821_planner.py) plus the payment object of
nano-payer.ts:166-191. No key, no seed, no outside network.

    python3 -m unittest tests/nano_fetch/test_mcp_blockhash_loopback.py
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SKILL_DIR = os.path.join(HERE, "..", "..", "skills", "nano-fetch")  # the-unowned-rail: fetch.py, middleware.py
sys.path[1:1] = [SKILL_DIR, os.path.join(SKILL_DIR, "xno_buyer_plan")]  # plan, wallets, client_fit
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))  # mcp_blockhash_seller.py
import mcp_blockhash_seller as ms  # noqa: E402
from test_xmcp_821_planner import plan_821  # noqa: E402

PAY_TO = "nano_3aysuejus8iy1hhw6doc7syzg1aaa6hgpec91xcc36mf6hp6thy7u6ymkgfm"
OTHER = "nano_1111111111111111111111111111111111111111111111111111hifc8npp"
PAYER = ms.account_from_key(bytes([1]) * 32)  # a test account encoded from a fixed public key, no secret
BLOCKS = {}


class Node(BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode())
        info = BLOCKS.get(req.get("hash", "").upper()) if req.get("action") == "block_info" else None
        body = json.dumps(info if info is not None else {"error": "Block not found"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def publish(hash_hex, pay_to, amount, rep, subtype="send", confirmed="true"):
    """What the payer's wallet leaves on the ledger, as the node's block_info (json_block) reports it."""
    BLOCKS[hash_hex.upper()] = {
        "block_account": PAYER, "amount": str(amount), "subtype": subtype, "confirmed": confirmed,
        "contents": {"type": "state", "account": PAYER, "link_as_account": pay_to, "representative": rep}}


class Loopback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = HTTPServer(("127.0.0.1", 0), Node)
        threading.Thread(target=cls.node.serve_forever, daemon=True).start()
        cls.url = "http://127.0.0.1:%d/" % cls.node.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.node.shutdown()

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = os.path.join(self.dir, "spent.json")
        self.seller = self.new_seller()
        self.n = 0

    def tearDown(self):
        shutil.rmtree(self.dir)

    def new_seller(self):
        return ms.Seller(PAY_TO, self.url, self.store, {"weather": ("0.001", lambda a: "sunny in %s" % a["city"])})

    def call(self, seller, payment=None):
        self.n += 1
        params = {"name": "weather", "arguments": {"city": "Oslo"}}
        if payment is not None:
            params["_meta"] = {ms.META_KEY: payment}
        return seller.handle({"jsonrpc": "2.0", "id": self.n, "method": "tools/call", "params": params})["result"]

    def pay(self, result, hash_hex, **override):
        """#821: plan the offer under a cap, the wallet publishes the bound send, the call is retried."""
        plan = plan_821(result, max_amount_raw=10 ** 28)
        rep = ms.bound_rep(plan["orderId"], plan["payTo"], plan["amountRaw"])
        publish(hash_hex, override.get("pay_to", plan["payTo"]), override.get("amount", plan["amountRaw"]),
                override.get("rep", rep), override.get("subtype", "send"), override.get("confirmed", "true"))
        return {"x402Version": plan["x402Version"], "resource": result["structuredContent"].get("resource"),
                "accepted": plan["accepted"], "payload": {"blockHash": hash_hex, "orderId": plan["orderId"]}}

    def h(self, c):
        return c * 64

    # --- the path that #821 pays ------------------------------------------------------------------
    def test_unpaid_call_is_an_offer_821_takes(self):
        r = self.call(self.seller)
        self.assertTrue(r["isError"])
        plan = plan_821(r, max_amount_raw=10 ** 28)
        self.assertEqual(plan["amountRaw"], str(10 ** 27))  # 0.001 XNO, derived from 10^30 raw
        self.assertEqual(plan["accepted"]["network"], "nano:mainnet")
        self.assertRegex(plan["orderId"], r"^[A-Za-z0-9_-]{22,128}$")
        self.assertNotEqual(plan["orderId"], plan_821(self.call(self.seller), 10 ** 28)["orderId"])

    def test_paid_call_settles_end_to_end(self):
        r = self.call(self.seller, self.pay(self.call(self.seller), self.h("a")))
        self.assertNotIn("isError", r)
        self.assertEqual(r["content"][0]["text"], "sunny in Oslo")
        receipt = r["_meta"]["x402/payment-response"]
        self.assertEqual((receipt["transaction"], receipt["payer"]), (self.h("A"), PAYER))

    def test_replay_refused_and_survives_restart(self):
        payment = self.pay(self.call(self.seller), self.h("b"))
        self.assertNotIn("isError", self.call(self.seller, payment))
        self.assertEqual(self.call(self.seller, payment)["structuredContent"]["error"], "replay-block")
        restarted = self.new_seller()
        self.assertEqual(self.call(restarted, payment)["structuredContent"]["error"], "replay-block")
        # the same block presented against a fresh order is still spent
        fresh = plan_821(self.call(restarted), 10 ** 28)
        again = dict(payment, accepted=fresh["accepted"], payload={"blockHash": self.h("b"), "orderId": fresh["orderId"]})
        self.assertEqual(self.call(restarted, again)["structuredContent"]["error"], "replay-block")

    # --- what a seller must refuse ------------------------------------------------------------------
    def refused(self, hash_char, **override):
        return self.call(self.seller, self.pay(self.call(self.seller), self.h(hash_char), **override))[
            "structuredContent"]["error"]

    def test_wrong_amount_destination_rep_and_state(self):
        self.assertEqual(self.refused("c", amount=10 ** 27 - 1), "wrong-amount")
        self.assertEqual(self.refused("d", amount=10 ** 27 + 1), "wrong-amount")
        self.assertEqual(self.refused("e", pay_to=OTHER), "wrong-destination")
        self.assertEqual(self.refused("f", rep=PAY_TO), "not-bound-to-order")
        self.assertEqual(self.refused("1", subtype="receive"), "not-a-send")
        self.assertEqual(self.refused("2", confirmed="false"), "not-confirmed")

    def test_block_bound_to_another_order_is_refused(self):
        first = plan_821(self.call(self.seller), 10 ** 28)
        second = self.call(self.seller)
        publish(self.h("3"), PAY_TO, first["amountRaw"], ms.bound_rep(first["orderId"], PAY_TO, first["amountRaw"]))
        plan2 = plan_821(second, 10 ** 28)
        pay = {"x402Version": 2, "accepted": plan2["accepted"], "payload": {"blockHash": self.h("3"), "orderId": plan2["orderId"]}}
        self.assertEqual(self.call(self.seller, pay)["structuredContent"]["error"], "not-bound-to-order")

    def test_unknown_order_missing_block_and_http_shape(self):
        payment = self.pay(self.call(self.seller), self.h("4"))
        bad = dict(payment, payload={"blockHash": self.h("4"), "orderId": "x" * 32})
        bad["accepted"] = dict(payment["accepted"], extra={"binding": ms.BINDING, "orderId": "x" * 32})
        self.assertEqual(self.call(self.seller, bad)["structuredContent"]["error"], "unknown-order")
        gone = dict(payment, payload={"blockHash": self.h("5"), "orderId": payment["payload"]["orderId"]})
        self.assertEqual(self.call(self.seller, gone)["structuredContent"]["error"], "block-not-found")
        # the HTTP sellers' shape (payload.block, no blockHash) is not what this seller reads
        http = dict(payment, payload={"block": {"type": "state"}, "orderId": payment["payload"]["orderId"]})
        self.assertEqual(self.call(self.seller, http)["structuredContent"]["error"], "no-blockhash")
        tampered = dict(payment, accepted=dict(payment["accepted"], amount="1"))
        self.assertEqual(self.call(self.seller, tampered)["structuredContent"]["error"], "accepted-differs-from-order")

    def test_config_and_amounts(self):
        self.assertEqual(ms.raw_of_xno("1"), 10 ** 30)
        self.assertEqual(ms.raw_of_xno("0.000001"), 10 ** 24)
        with self.assertRaises(ValueError):
            ms.Seller(PAY_TO[:-1] + "a", self.url, self.store, {})
        with self.assertRaises(ValueError):
            ms.Seller(PAY_TO, "", self.store, {})


if __name__ == "__main__":
    unittest.main()
