import base64, json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import quote_unit as q


class QuoteUnit(unittest.TestCase):
    def test_flat_xno_amount_is_xno_fixed(self):
        b = json.dumps({"payment": {"network": "nano:mainnet", "amount_raw": str(10 ** 26), "amount_xno": "0.0001"}})
        r = q.parse(402, {}, b)
        self.assertEqual((r["xno_price"], r["quote_unit"]), ("0.0001", "xno-fixed"))

    def test_header_price_raw(self):
        r = q.parse(402, {"X-Payment-Amount-Raw": str(10 ** 27)}, "payment required")
        self.assertEqual((r["xno_price"], r["quote_unit"]), ("0.001", "xno-fixed"))

    def test_x402_accepts_in_header(self):
        doc = {"accepts": [{"network": "nano:mainnet", "amount": str(10 ** 26)}]}
        h = {"payment-required": base64.b64encode(json.dumps(doc).encode()).decode()}
        self.assertEqual(q.parse(402, h, "")["xno_price"], "0.0001")

    def test_usdc_leg_beside_xno_leg_means_usd_pegged(self):
        doc = {"accepts": [{"network": "eip155:8453", "amount": "3000"}, {"network": "nano:mainnet", "amount": "8628000000000000000000000000"}]}
        r = q.parse(402, {}, json.dumps(doc))
        self.assertEqual((r["xno_price"], r["quote_unit"], r["usd_price"]), ("0.008628", "usd-pegged", 0.003))

    def test_nothing_readable_is_unknown_not_guessed(self):
        r = q.parse(402, {}, "<html>nope</html>")
        self.assertEqual((r["xno_price"], r["quote_unit"]), (None, "unknown"))

    def test_raw_to_xno_exact(self):
        self.assertEqual(q.raw_to_xno(1), "0." + "0" * 29 + "1")
        self.assertEqual(q.raw_to_xno(10 ** 30), "1")


if __name__ == "__main__":
    unittest.main()
