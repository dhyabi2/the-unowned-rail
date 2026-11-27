"""Tests for nano_fetch paying a plain exact accept (x402nano/exact payload.block) with --block-signer.

Loopback only (test_fetch.Base refuses any other host). The block signer here is a stub: it returns a
fixed-shape state send block with a dummy signature; nothing is signed with a key and nothing is published.

    python3 -m unittest tests/nano_fetch/test_exact_block.py
"""
import base64
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SKILL_DIR = os.path.join(HERE, "..", "..", "skills", "nano-fetch")  # the-unowned-rail: fetch.py, middleware.py
sys.path[1:1] = [SKILL_DIR, os.path.join(SKILL_DIR, "xno_buyer_plan")]  # plan, wallets, client_fit
import test_fetch as tf  # noqa: E402
from client_fit import account_from_key  # noqa: E402  (buyer_plan, on sys.path through fetch)
from middleware import Journal, check_send_block  # noqa: E402  (scrapy_payer)
from wallets import key_from_account, state_block_hash  # noqa: E402

RAW_PER_XNO = tf.RAW_PER_XNO
PRICE = str(RAW_PER_XNO // 100)  # 0.01 XNO, derived
PAY_TO = account_from_key(bytes([7]) * 32)
PAYER = account_from_key(bytes([9]) * 32)
OTHER = account_from_key(bytes([11]) * 32)


def exact_accept(network="nano:mainnet", amount=PRICE, pay_to=PAY_TO):
    return {"scheme": "exact", "network": network, "amount": amount, "payTo": pay_to, "asset": "XNO",
            "maxTimeoutSeconds": 60, "extra": {}}


def v2_header(accepts):
    doc = {"x402Version": 2, "error": "payment required",
           "resource": {"url": "http://127.0.0.1/paid"}, "accepts": accepts}
    return {"PAYMENT-REQUIRED": base64.b64encode(json.dumps(doc).encode("utf-8")).decode("ascii")}


def v1_body():
    a = exact_accept()
    a["maxAmountRequired"] = a.pop("amount")
    return {"x402Version": 1, "error": "X-PAYMENT header is required", "accepts": [a]}


class BlockSigner:
    """Returns a send block to `to` (default: the order's payTo). Records each order."""

    def __init__(self, to=None, signature="5A" * 64, answer=None):
        self.calls, self.to, self.signature, self.answer = [], to, signature, answer

    def __call__(self, order):
        self.calls.append(order)
        if self.answer is not None:
            return self.answer
        to = self.to or order["payTo"]
        return {"type": "state", "account": PAYER, "previous": "C" * 64, "representative": PAYER,
                "balance": str(3 * RAW_PER_XNO - int(order["amount_raw"])),
                "link": key_from_account(to).hex().upper(), "link_as_account": to,
                "signature": self.signature, "work": "0" * 16}


def dotted_block_signer(order):
    return BlockSigner()(order)


class PlainExact(tf.Base):
    def seller(self, **kw):
        return tf.Seller(v2_header([exact_accept()]), {}, "PAYMENT-SIGNATURE", **kw)

    def test_refused_as_unbound_without_block_signer(self):
        base = self.start(self.seller())
        s = tf.Signer()
        r = self.fetch(base + "/paid", signer=s, journal_path=self.jpath)
        self.assertEqual(r.refusal[0], "unbound")
        self.assertIn("block signer", r.refusal[1])
        self.assertEqual((s.calls, self.journal_rows()), ([], []))

    def test_v2_pays_with_signed_block_and_retries_once(self):
        seller = self.seller()
        base = self.start(seller)
        bs, s = BlockSigner(), tf.Signer()
        r = self.fetch(base + "/paid", signer=s, journal_path=self.jpath, block_signer=bs)
        self.assertEqual((r.status, r.body), (200, b"paid page"))
        self.assertEqual(s.calls, [])  # the publishing signer is never used for a plain exact accept
        self.assertEqual(bs.calls, [{"network": "nano:mainnet", "payTo": PAY_TO, "amount_raw": PRICE,
                                     "work_threshold": None}])
        doc = tf.decode(seller.seen[-1][2]["payment-signature"])
        self.assertEqual(doc["x402Version"], 2)
        self.assertEqual(doc["accepted"]["payTo"], PAY_TO)
        self.assertEqual(doc["accepted"]["amount"], PRICE)
        block = doc["payload"]["block"]
        self.assertEqual(block["link_as_account"], PAY_TO)
        rows = self.journal_rows()
        self.assertEqual([x["state"] for x in rows], ["intent", "signed"])
        self.assertEqual(rows[1]["blockHash"], state_block_hash(block))
        self.assertEqual(r.paid["blockHash"], state_block_hash(block))
        self.assertEqual(len(seller.seen), 2)

    def test_v1_body_quote_uses_x_payment(self):
        seller = tf.Seller({}, v1_body(), "X-PAYMENT")
        base = self.start(seller)
        r = self.fetch(base + "/paid", journal_path=self.jpath, block_signer=BlockSigner())
        self.assertEqual(r.status, 200)
        doc = tf.decode(seller.seen[-1][2]["x-payment"])
        self.assertEqual((doc["x402Version"], doc["scheme"], doc["network"]), (1, "exact", "nano:mainnet"))
        self.assertIn("block", doc["payload"])

    def test_nano_accept_after_a_usdc_one_is_paid(self):
        usdc = {"scheme": "exact", "network": "eip155:8453", "amount": "10000", "payTo": "0x" + "1" * 40,
                "asset": "0x" + "2" * 40}
        seller = tf.Seller(v2_header([usdc, exact_accept()]), {}, "PAYMENT-SIGNATURE")
        base = self.start(seller)
        r = self.fetch(base + "/paid", journal_path=self.jpath, block_signer=BlockSigner())
        self.assertEqual(r.status, 200, r.refusal)
        doc = tf.decode(seller.seen[-1][2]["payment-signature"])
        self.assertEqual(doc["accepted"]["network"], "nano:mainnet")

    def test_block_to_another_account_is_refused_and_never_presented(self):
        seller = self.seller()
        base = self.start(seller)
        bs = BlockSigner(to=OTHER)
        r = self.fetch(base + "/paid", journal_path=self.jpath, block_signer=bs)
        self.assertEqual(r.refusal[0], "signer_bad_block")
        self.assertEqual(len(seller.seen), 1)
        self.assertEqual([x["state"] for x in self.journal_rows()], ["intent"])
        # the intent stays: the same quote is not handed to the signer again, after a restart too
        r2 = self.fetch(base + "/paid", journal_path=self.jpath, block_signer=bs)
        self.assertEqual(r2.refusal[0], "replayed")
        self.assertEqual(len(bs.calls), 1)

    def test_unsigned_block_is_refused(self):
        base = self.start(self.seller())
        r = self.fetch(base + "/paid", journal_path=self.jpath, block_signer=BlockSigner(signature=""))
        self.assertEqual(r.refusal[0], "signer_bad_block")

    def test_replay_refused_after_restart(self):
        base = self.start(self.seller())
        bs = BlockSigner()
        self.assertEqual(self.fetch(base + "/paid", journal_path=self.jpath, block_signer=bs).status, 200)
        r = self.fetch(base + "/paid", journal_path=self.jpath, block_signer=bs)
        self.assertEqual(r.refusal[0], "replayed")
        self.assertEqual(len(bs.calls), 1)

    def test_budget_counts_signed_blocks(self):
        base = self.start(self.seller())
        r = self.fetch(base + "/paid", journal_path=self.jpath, block_signer=BlockSigner(),
                       budget_raw=str(int(PRICE) - 1))
        self.assertEqual(r.refusal[0], "over_budget")
        self.assertEqual(self.journal_rows(), [])

    def test_block_signer_alone_does_not_pay_a_bound_order(self):
        base = self.start(self.gateway_seller())
        bs = BlockSigner()
        r = self.fetch(base + "/paid", journal_path=self.jpath, block_signer=bs)
        self.assertEqual(r.refusal[0], "no_signer")
        self.assertEqual((bs.calls, self.journal_rows()), ([], []))


class CheckSendBlock(unittest.TestCase):
    def good(self):
        return BlockSigner()({"payTo": PAY_TO, "amount_raw": PRICE})

    def test_good_block_hash_is_computed_not_taken(self):
        b = dict(self.good(), hash="0" * 64)
        h, why = check_send_block(b, PAY_TO)
        self.assertIsNone(why)
        self.assertEqual(h, state_block_hash(b))
        self.assertNotEqual(h, "0" * 64)

    def test_shapes_refused(self):
        for bad in (None, "block", [], dict(self.good(), type="send"), dict(self.good(), subtype="receive"),
                    dict(self.good(), link_as_account=OTHER), dict(self.good(), link="zz"),
                    dict(self.good(), balance="-1"), dict(self.good(), account="nano_bad"),
                    {k: v for k, v in self.good().items() if k != "type"},
                    {k: v for k, v in self.good().items() if k != "work"},
                    dict(self.good(), work=""), dict(self.good(), work="0" * 15), dict(self.good(), work="zz" * 8)):
            h, why = check_send_block(bad, PAY_TO)
            self.assertIsNone(h, bad)
            self.assertTrue(why)


class Command(tf.Base):
    run_cli = tf.Command.run_cli

    def test_cli_block_signer_needs_journal(self):
        code, out, err = self.run_cli(["http://127.0.0.1:9/x", "--block-signer",
                                       "test_exact_block.dotted_block_signer"])
        self.assertEqual(code, 2)

    def test_cli_pays_plain_exact_with_block_signer(self):
        base = self.start(tf.Seller(v2_header([exact_accept()]), {}, "PAYMENT-SIGNATURE"))
        code, out, err = self.run_cli([base + "/paid", "--block-signer", "test_exact_block.dotted_block_signer",
                                       "--journal", self.jpath])
        self.assertEqual(code, 0, err)
        self.assertEqual(out, b"paid page")
        self.assertEqual([x["state"] for x in Journal(self.jpath).entries.values()], ["signed"])


if __name__ == "__main__":
    unittest.main()
