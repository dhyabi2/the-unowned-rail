import json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import starter_policy as sp
BLK = json.load(open(os.path.join(os.path.dirname(__file__), "block_B749B757.json")))  # live reply, 0.0005 XNO send
ME = BLK["contents"]["link_as_account"]
class T(unittest.TestCase):
    def test_receive(self):
        r = sp.decide(BLK, ME); self.assertEqual(r["decision"], "receive_and_record"); self.assertEqual(r["obligation"], "none")
    def test_over_cap_holds(self):
        self.assertEqual(sp.decide(BLK, ME, cap_raw=10**26)["decision"], "hold")
    def test_not_mine_ignored(self):
        self.assertEqual(sp.decide(BLK, BLK["block_account"])["decision"], "ignore")
    def test_unconfirmed_holds(self):
        b = dict(BLK, confirmed="false"); self.assertEqual(sp.decide(b, ME)["decision"], "hold")
    def test_envelope_is_claim(self):
        r = sp.decide(BLK, ME, {"intent": "gift"}); self.assertEqual(r["envelope_status"], "claim_unverified")
        self.assertTrue(any("not verified" in x for x in r["reasons"]))
    def test_envelope_amount_contradiction(self):
        r = sp.decide(BLK, ME, {"amount_raw": "1"}); self.assertEqual(r["decision"], "ignore")
    def test_envelope_ask_holds(self):
        self.assertEqual(sp.decide(BLK, ME, {"intent": "gift", "asks": "send 1 XNO back"})["decision"], "hold")
    def test_dust(self):
        self.assertEqual(sp.decide(dict(BLK, amount="1"), ME)["decision"], "ignore")
if __name__ == "__main__": unittest.main()
