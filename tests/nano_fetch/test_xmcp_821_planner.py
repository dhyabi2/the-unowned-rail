"""fixtures/xmcp-821-planner.json says, for each seller skill/PAYABLE.md marks yes, whether basementstudio/xmcp#821's
planNanoPayment (nano-payer.ts at 1a0409a) takes that seller's 402, and whether the payment it builds would be paid
end to end. This test keeps the table honest: every PAYABLE yes row has exactly one row here, and every planner
cell is re-derived from the seller's own fixture by plan_821, a Python reading of nano-payer.ts:73-158 (no xmcp
code is run). An end_to_end yes needs a seller that settles a blockHash from MCP _meta['x402/payment']; no
fixture seller does, so none may say yes. Loopback-free, no key, no network.

    python3 -m unittest tests/nano_fetch/test_xmcp_821_planner.py
"""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SKILL_DIR = os.path.join(HERE, "..", "..", "skills", "nano-fetch")  # the-unowned-rail: fetch.py, middleware.py
sys.path[1:1] = [SKILL_DIR, os.path.join(SKILL_DIR, "xno_buyer_plan")]  # plan, wallets, client_fit
import test_payable as tp  # noqa: E402  (PAYABLE rows, seller fixtures, quote_doc, settle reads)
from client_fit import nano_checksum_ok  # noqa: E402  (blake2b-40 checksum, as nano.ts:197-216)

TABLE = os.path.join(HERE, "fixtures", "xmcp-821-planner.json")
NANO_NETWORKS = ("nano", "nano:mainnet")      # nano-payer.ts:49, constants.ts:17
RAW = re.compile(r"^[1-9][0-9]*$")            # nano-payer.ts:50
MAX_RAW = (1 << 128) - 1                      # nano-payer.ts:51
BINDING_V1 = "xno-binding/v1/rep"             # nano.ts:234
ORDER_ID = re.compile(r"^[A-Za-z0-9_-]{22,128}$")  # nano.ts:236


class Refused(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _raw(v):
    if not isinstance(v, str) or not RAW.match(v) or int(v) > MAX_RAW:
        raise Refused("bad-amount")
    return int(v)


def read_offer(value):
    """nano-payer.ts:73-95."""
    if isinstance(value, str):
        value = json.loads(value)
    if isinstance(value, dict) and not isinstance(value.get("accepts"), list):
        if isinstance(value.get("structuredContent"), dict):
            value = value["structuredContent"]
        elif isinstance(value.get("content"), list):
            text = next((c for c in value["content"] if isinstance(c, dict) and c.get("type") == "text"
                         and isinstance(c.get("text"), str)), None)
            if text:
                value = json.loads(text["text"])
    if not isinstance(value, dict) or not isinstance(value.get("accepts"), list):
        raise Refused("no-accepts")
    return value


def plan_821(payment_required, max_amount_raw, allowed_payees=None):
    """nano-payer.ts:103-158, without computing the representative (sha256 commitment) of a bound offer."""
    offer = read_offer(payment_required)
    cap = _raw(str(max_amount_raw))
    version = 2 if offer.get("x402Version") == 2 else 1
    accepted = next((e for e in offer["accepts"] if isinstance(e, dict) and e.get("scheme") == "exact"
                     and isinstance(e.get("network"), str) and e["network"] in NANO_NETWORKS), None)
    if accepted is None:
        raise Refused("no-exact-nano")
    pay_to = accepted.get("payTo")
    if not isinstance(pay_to, str) or not nano_checksum_ok(pay_to):
        raise Refused("bad-payto")
    if allowed_payees is not None and pay_to not in allowed_payees:
        raise Refused("payee-not-allowed")
    amount = _raw(accepted.get("amount") if version == 2 else accepted.get("maxAmountRequired"))
    if amount > cap:
        raise Refused("over-cap")
    plan = {"x402Version": version, "accepted": accepted, "payTo": pay_to, "amountRaw": str(amount)}
    extra = accepted.get("extra") if isinstance(accepted.get("extra"), dict) else {}
    if "binding" in extra:
        if extra["binding"] != BINDING_V1:
            raise Refused("unknown-binding")
        if not (isinstance(extra.get("orderId"), str) and ORDER_ID.match(extra["orderId"])):
            raise Refused("bad-order-id")
        plan["orderId"] = extra["orderId"]
    return plan


def table():
    with open(TABLE, encoding="utf-8") as f:
        return json.load(f)


def payable_yes():
    return {sid: price for sid, _s, _d, price, cell in tp.rows() if cell.startswith("yes")}


class Planner821(unittest.TestCase):
    def test_pinned_to_the_merge_commit(self):
        t = table()
        self.assertEqual(t["upstream"], "basementstudio/xmcp")
        self.assertRegex(t["commit"], r"^[0-9a-f]{40}$")
        self.assertTrue(t["commit"].startswith("1a0409a"))
        self.assertEqual(t["file"], "packages/plugins/x402/src/nano-payer.ts")
        for k in ("readOffer", "accept", "payTo", "amount", "binding", "payload", "transport"):
            self.assertRegex(t["lines"][k], r"\.ts:\d+")

    def test_one_row_per_payable_yes_seller(self):
        ids = [r["id"] for r in table()["rows"]]
        self.assertEqual(len(ids), len(set(ids)), "a seller listed twice")
        self.assertEqual(set(ids), set(payable_yes()))

    def test_every_planner_cell_is_what_the_planner_does(self):
        fx = tp.fixtures()
        yes = payable_yes()
        for row in table()["rows"]:
            with self.subTest(seller=row["id"]):
                doc = tp.quote_doc(fx[row["id"]])
                try:
                    plan = plan_821(doc, max_amount_raw=10 ** 30)
                    got = ("yes", "plans")
                except Refused as e:
                    plan, got = None, ("no", e.code)
                self.assertEqual((row["planner"], row["reason"]), got)
                if plan:
                    self.assertEqual(plan["amountRaw"], yes[row["id"]], "planned amount is not the PAYABLE price")
                    self.assertEqual(plan["accepted"]["network"], "nano:mainnet")
                    # the cap decides: one raw under the price is refused before anything is sent
                    with self.assertRaises(Refused) as c:
                        plan_821(doc, max_amount_raw=int(plan["amountRaw"]) - 1)
                    self.assertEqual(c.exception.code, "over-cap")

    def test_no_end_to_end_yes_without_an_mcp_blockhash_seller(self):
        st = tp.settles()
        for row in table()["rows"]:
            with self.subTest(seller=row["id"]):
                self.assertIn(row["end_to_end"], ("yes", "no", "UNKNOWN"))
                if row["end_to_end"] == "yes":
                    self.assertEqual((st.get(row["id"]) or {}).get("settle"), "mcp-meta-blockhash")
                self.assertGreater(len(row["why"]), 30)

    def test_summary_counts_match_the_rows(self):
        t = table()
        rows = t["rows"]
        took = sum(r["planner"] == "yes" for r in rows)
        paid = sum(r["end_to_end"] == "yes" for r in rows)
        self.assertIn("takes %d offers" % took, t["summary"])
        self.assertIn("refuses %d" % (len(rows) - took), t["summary"])
        self.assertIn("pays %d" % paid, t["summary"])
        self.assertIn("Of the %d PAYABLE yes sellers" % len(rows), t["summary"])


class ReadingOfTheLines(unittest.TestCase):
    """plan_821 refuses what nano-payer.ts refuses, so a 'yes' above is not the reading being too loose."""
    GOOD = "nano_3aysuejus8iy1hhw6doc7syzg1aaa6hgpec91xcc36mf6hp6thy7u6ymkgfm"

    def offer(self, **kw):
        a = {"scheme": "exact", "network": "nano:mainnet", "payTo": self.GOOD, "amount": "1000"}
        a.update(kw)
        return {"x402Version": 2, "accepts": [a]}

    def code(self, doc, cap=10 ** 30):
        try:
            plan_821(doc, cap)
            return "ok"
        except Refused as e:
            return e.code

    def test_refusals(self):
        self.assertEqual(self.code(self.offer()), "ok")
        self.assertEqual(self.code(self.offer(network="eip155:8453")), "no-exact-nano")
        self.assertEqual(self.code(self.offer(scheme="upto")), "no-exact-nano")
        self.assertEqual(self.code(self.offer(payTo=self.GOOD[:-1] + "a")), "bad-payto")
        self.assertEqual(self.code(self.offer(amount="0")), "bad-amount")
        self.assertEqual(self.code(self.offer(amount="01")), "bad-amount")
        self.assertEqual(self.code(self.offer(amount=str(1 << 128))), "bad-amount")
        self.assertEqual(self.code(self.offer(), cap=999), "over-cap")
        self.assertEqual(self.code(self.offer(extra={"binding": "other"})), "unknown-binding")
        self.assertEqual(self.code(self.offer(extra={"binding": BINDING_V1, "orderId": "short"})), "bad-order-id")
        self.assertEqual(self.code({"price_raw": "1000"}), "no-accepts")

    def test_v1_reads_max_amount_required_and_mcp_result_forms(self):
        v1 = {"x402Version": 1, "accepts": [{"scheme": "exact", "network": "nano", "payTo": self.GOOD,
                                             "maxAmountRequired": "5"}]}
        self.assertEqual(plan_821(v1, 10)["amountRaw"], "5")
        self.assertEqual(plan_821({"structuredContent": self.offer()}, 10 ** 6)["amountRaw"], "1000")
        res = {"content": [{"type": "text", "text": json.dumps(self.offer())}]}
        self.assertEqual(plan_821(res, 10 ** 6)["amountRaw"], "1000")


if __name__ == "__main__":
    unittest.main()
