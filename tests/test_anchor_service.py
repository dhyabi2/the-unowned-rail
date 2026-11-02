import hashlib, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import anchor_service as S, nano_anchor as NA

def leaves(n): return [hashlib.sha256(str(i).encode()).hexdigest() for i in range(n)]

class T(unittest.TestCase):
    def test_merkle_proofs_for_all_sizes(self):
        for n in (1, 2, 3, 5, 8, 9):
            L = leaves(n); root, paths = S.merkle(L)
            for l, p in zip(L, paths): self.assertTrue(S.prove(l, p, root), (n, l))
    def test_wrong_leaf_fails(self):
        L = leaves(4); root, paths = S.merkle(L)
        self.assertFalse(S.prove(leaves(5)[4], paths[0], root))
    def test_address_roundtrip(self):
        c, o = S.handle("GET", "/anchor/address?sha256=" + leaves(1)[0], {})
        self.assertEqual(c, 200); self.assertEqual(NA.decode(o["representative"]).hex(), leaves(1)[0])
    def test_bad_hash_400(self):
        self.assertEqual(S.handle("GET", "/anchor/address?sha256=zz", {})[0], 400)
    def test_verify_with_fake_node(self):
        L = leaves(3); c, b = S.handle("POST", "/anchor/batch", {"hashes": L}); root = b["root"]
        fake = lambda rpc, blk: {"confirmed": "true", "height": "7", "local_timestamp": "1", "block_account": "nano_x",
                                 "contents": {"type": "state", "representative": b["representative"]}}
        leaf = b["leaves"][1]
        c, o = S.handle("POST", "/anchor/verify", {"block": "AB" * 32, "leaf": leaf["sha256"], "proof": leaf["proof"], "root": root}, fetch=fake)
        self.assertTrue(o["anchored"]); self.assertEqual(o["height"], "7")
        c, o = S.handle("POST", "/anchor/verify", {"block": "AB" * 32, "leaf": L[0], "proof": leaf["proof"], "root": root}, fetch=fake)
        self.assertFalse(o["anchored"])
    def test_unconfirmed_is_not_anchored(self):
        h = leaves(1)[0]
        fake = lambda r, b: {"confirmed": "false", "contents": {"type": "state", "representative": NA.anchor_address(h)}}
        self.assertFalse(S.handle("POST", "/anchor/verify", {"block": "AB" * 32, "sha256": h}, fetch=fake)[1]["anchored"])
if __name__ == "__main__": unittest.main()
