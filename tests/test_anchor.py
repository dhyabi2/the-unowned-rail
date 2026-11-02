import hashlib, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import nano_anchor as na

# Real accounts read on the public ledger (2026-11-02): they must round-trip through decode/encode unchanged.
REAL = ["nano_1yo6c1t64ahfjdw1dxizmbbnpdmbrckwhw9phbg5pdkeubrizga4qhnjmnx7",
        "nano_3m8cz87zwxb1y16ob4bzp1eyek78qaig8ktohk7d45b18sh6u9exbowbnekr",
        "nano_1stofnrxuz3cai7ze75o174bpm7scwj9jn3nxsn8ntzg784jf1gzn1jjdkou"]
H = hashlib.sha256(b"92177 receipt bytes").hexdigest()


def block_with(rep, confirmed="true", typ="state"):
    return {"block_account": "nano_x", "height": "7", "local_timestamp": "1790150110", "confirmed": confirmed,
            "contents": {"type": typ, "representative": rep}}


class Codec(unittest.TestCase):
    def test_real_addresses_round_trip(self):
        for a in REAL:
            self.assertEqual(na.encode(na.decode(a)), a)

    def test_hash_survives_the_trip(self):
        self.assertEqual(na.decode(na.anchor_address(H)).hex(), H)

    def test_bad_checksum_refused(self):
        a = REAL[0][:-1] + ("1" if REAL[0][-1] != "1" else "3")
        with self.assertRaises(ValueError):
            na.decode(a)

    def test_short_hash_refused(self):
        with self.assertRaises(ValueError):
            na.anchor_address("abcd")

    def test_top_bits_set_hash_still_encodes_and_decodes(self):
        h = "ff" * 32
        self.assertEqual(na.decode(na.anchor_address(h)).hex(), h)


class Check(unittest.TestCase):
    def test_anchored(self):
        code, o = na.check("A" * 64, H, fetch=lambda r, b: block_with(na.anchor_address(H)))
        self.assertEqual((code, o["verdict"], o["height"]), (0, "anchored", "7"))

    def test_other_hash_is_not_this_anchor(self):
        code, o = na.check("A" * 64, H, fetch=lambda r, b: block_with(na.anchor_address("00" * 32)))
        self.assertEqual((code, o["verdict"]), (3, "different_hash"))

    def test_unconfirmed_is_not_anchored(self):
        code, o = na.check("A" * 64, H, fetch=lambda r, b: block_with(na.anchor_address(H), confirmed="false"))
        self.assertEqual((code, o["verdict"]), (3, "unconfirmed"))

    def test_unreachable_is_4_not_refusal(self):
        def boom(r, b): raise OSError("down")
        self.assertEqual(na.check("A" * 64, H, fetch=boom)[0], 4)

    def test_unknown_block(self):
        self.assertEqual(na.check("A" * 64, H, fetch=lambda r, b: {"error": "Block not found"})[1]["verdict"], "no_such_block")

    def test_limits_always_printed(self):
        self.assertTrue(na.check("A" * 64, H, fetch=lambda r, b: block_with(na.anchor_address(H)))[1]["limits"])


if __name__ == "__main__":
    unittest.main()
