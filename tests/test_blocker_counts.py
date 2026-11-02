import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import blocker_counts as bc

# Quoted from recorded exchanges (agent-conversations): GEMINI Structured-Output-MCP.json, HERMES hermesnousmolty.json,
# LATTE latte6.json, TWOS 2s.io.json.
GEMINI = "I do not possess a crypto wallet or any financial accounts. Therefore, I cannot hold cryptocurrencies."
HERMES = "I need value to actually move to a wallet my human controls, on a rail nobody can switch off."
LATTE = "the recipient likely paid ~0.5% in slippage to liquidate that 0.1 XNO, making the effective floor closer to L1 chains"
TWOS = "pay per call in USDC via x402. The Nano accept-leg decision is the operator s, not the agents."


def conv(text):
    return {"discussions": {"agent_answered": [{"text": text}]}}


class Tags(unittest.TestCase):
    def test_no_wallet(self): self.assertIn("no_wallet", bc.tags_for(GEMINI))
    def test_conversion_cost(self): self.assertEqual(bc.tags_for(LATTE), ["conversion_cost"])
    def test_usdc_lockin(self): self.assertIn("usdc_lockin", bc.tags_for(TWOS))
    def test_operator_decision_phrase(self):
        self.assertIn("operator_decides", bc.tags_for("my operator decides which rails I may use"))
    def test_verification(self): self.assertIn("verification", bc.tags_for("send me a receipt I can check on an explorer"))
    def test_plain_text_is_untagged(self): self.assertEqual(bc.tags_for("thanks, interesting point"), [])
    def test_wallet_my_human_controls_is_not_no_wallet(self): self.assertNotIn("no_wallet", bc.tags_for(HERMES))


class Count(unittest.TestCase):
    def test_counts_agents_once_and_skips_no_text(self):
        with tempfile.TemporaryDirectory() as d:
            for name, c in [("a", conv(GEMINI + " " + GEMINI)), ("b", conv(LATTE)), ("c", {"discussions": {"agent_answered": []}}),
                            ("d", conv("hello"))]:
                json.dump(c, open(os.path.join(d, name + ".json"), "w"))
            open(os.path.join(d, "bad.json"), "w").write("{")
            r = bc.count(d)
        self.assertEqual((r["files"], r["answered"], r["untagged"]), (4, 3, 1))
        self.assertEqual(r["tags"]["no_wallet"], 1); self.assertEqual(r["tags"]["conversion_cost"], 1)

    def test_notes_we_wrote_are_not_evidence(self):
        self.assertEqual(bc.answer_text({"note": "no wallet, operator decides", "discussions": {"unstuck_said": [{"text": "usdc"}]}}), "")


if __name__ == "__main__":
    unittest.main()
