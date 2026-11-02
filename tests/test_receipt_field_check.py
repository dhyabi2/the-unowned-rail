import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import receipt_field_check as rf

ADDR = "nano_3aysuejus8iy1hhw6doc7syzg1aaa6hgpec91xcc36mf6hp6thy7u6ymkgfm"
H = "B749B757EE750FC9AEA72F33CB429EACCD2ABEC9F2CCF59BF17AFAC304C9A58F"
R = {"rail": "nano:mainnet", "ref": H, "payee": ADDR, "amount_raw": "500000000000000000000000000"}


class T(unittest.TestCase):
    def test_good_and_stripe_without_nano_fields(self):
        self.assertEqual(rf.shape(R), [])
        self.assertEqual(rf.shape({"rail": "stripe", "ref": "po_123"}), [])

    def test_bad_shapes(self):
        self.assertTrue(rf.shape(dict(R, ref="abc")))
        self.assertTrue(rf.shape(dict(R, payee=ADDR[:-1] + "1")))
        self.assertTrue(rf.shape(dict(R, amount_raw="0.5")))
        self.assertTrue(rf.shape(dict(R, extra=1)))

    def test_online_checks_amount_link_and_confirmed(self):
        ok = lambda n, b: {"confirmed": "true", "amount": R["amount_raw"], "contents": {"link_as_account": ADDR}}
        self.assertEqual(rf.online(R, call=ok), [])
        bad = lambda n, b: {"confirmed": "false", "amount": "1", "contents": {"link_as_account": "nano_x"}}
        self.assertEqual(len(rf.online(R, call=bad)), 3)

if __name__ == "__main__": unittest.main()
