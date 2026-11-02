import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import rails_check as rc

ADDR = "nano_3aysuejus8iy1hhw6doc7syzg1aaa6hgpec91xcc36mf6hp6thy7u6ymkgfm"   # feeless402's payTo, live 402 on 2026-11-02


class T(unittest.TestCase):
    def test_registration_file_wallet_service(self):
        d = {"services": [{"name": "A2A", "endpoint": "https://x/a2a"},
                          {"name": "wallet", "endpoint": "nano:" + ADDR, "version": "v1", "network": "nano:mainnet", "min_raw": "100000000000000000000000000"}]}
        r = rc.rails(d)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["problems"], [])

    def test_a2a_card_extension(self):
        d = {"capabilities": {"extensions": [{"uri": "u", "params": {"payments": {"nano": {"address": ADDR, "network": "nano-mainnet"}}}}]}}
        self.assertEqual(rc.rails(d)[0]["problems"], [])

    def test_bad_checksum_network_and_min_raw_are_reported(self):
        bad = ADDR[:-1] + ("1" if ADDR[-1] != "1" else "3")
        d = {"services": [{"name": "wallet", "endpoint": "nano:" + bad, "network": "eip155:8453", "min_raw": "0.0001"}]}
        p = rc.rails(d)[0]["problems"]
        self.assertEqual(len(p), 3)

    def test_other_wallets_and_empty_documents_declare_nothing(self):
        self.assertEqual(rc.rails({"services": [{"name": "wallet", "endpoint": "eip155:1:0xabc"}]}), [])
        self.assertEqual(rc.rails({}), [])


if __name__ == "__main__":
    unittest.main()
