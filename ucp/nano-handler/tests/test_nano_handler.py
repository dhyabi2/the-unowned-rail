"""Offline tests for the io.github.dhyabi2.nano handler.

Run from the handler directory:
    python3 -m unittest discover -s tests -v

Tests 1-2 need `jsonschema` (pip install jsonschema) and are skipped without it;
every other test uses the standard library only. Node answers are recorded
JSON under tests/fixtures/; nothing goes to the network.
"""

import copy
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HANDLER_DIR = os.path.dirname(HERE)
sys.path.insert(0, HANDLER_DIR)

import verify  # noqa: E402

FIX = os.path.join(HERE, "fixtures")
UCP_PIN = os.path.join(HERE, "ucp-1be6f77")
OWN_BASE = "https://raw.githubusercontent.com/dhyabi2/the-unowned-rail/main/ucp/nano-handler/"


def load(name):
    with open(os.path.join(FIX, name)) as f:
        return json.load(f)


CFG = load("config.json")
HASH = CFG["hash_send"]
EXPIRES = "2026-11-18T11:06:40Z"  # == local_timestamp 1795000000 of the fixtures

DECLARATION = {
    "id": "nano_mainnet_1",
    "version": "2026-11-20",
    "spec": OWN_BASE + "README.md",
    "schema": OWN_BASE + "schema.json",
    "available_instruments": [{"type": "nano_block"}],
    "config": {
        "network": "nano:mainnet",
        "pay_to": CFG["pay_to"],
        "min_confirmation": "confirmed",
        "quote_ttl_seconds": 900,
    },
}


def instrument(block_hash=HASH, handler_id="nano_mainnet_1"):
    return {
        "id": "instr_1",
        "handler_id": handler_id,
        "type": "nano_block",
        "credential": {"type": "nano_send_block", "block_hash": block_hash},
        "display": {"network": "nano:mainnet", "amount_xno": "0.003"},
    }


class FakeNode:
    """Answers blocks_info from a recorded fixture; counts calls."""

    def __init__(self, answer=None, exc=None):
        self.answer = answer
        self.exc = exc
        self.calls = 0

    def __call__(self, payload):
        self.calls += 1
        assert payload["action"] == "blocks_info"
        if self.exc is not None:
            raise self.exc
        return copy.deepcopy(self.answer)


def with_block(**changes):
    answer = load("blocks_info_send_confirmed.json")
    answer["blocks"][HASH].update(changes)
    return answer


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "seen.sqlite")
        self.store = verify.SeenStore(self.db)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def handler(self, node):
        return verify.NanoHandler("nano_mainnet_1", DECLARATION["config"], node, self.store)

    def quote(self, checkout_id="chk_1", amount_raw=None, expires_at=EXPIRES):
        return verify.make_quote(checkout_id, amount_raw or CFG["amount_raw"], expires_at)

    def severity(self, result):
        self.assertEqual(result["status"], "failed")
        message = result["messages"][0]
        self.assertEqual(message["type"], "error")
        self.assertEqual(message["code"], "payment_failed")
        return message["severity"]


# 1 and 2: schemas -----------------------------------------------------------

try:
    import jsonschema
    from referencing import Registry, Resource
    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover
    HAVE_JSONSCHEMA = False


def registry():
    resources = []
    for root, _, files in os.walk(UCP_PIN):
        for name in files:
            if name.endswith(".json"):
                with open(os.path.join(root, name)) as f:
                    doc = json.load(f)
                resources.append((doc["$id"], Resource.from_contents(doc)))
    for name in ("schema.json", "instrument.json", "credential.json"):
        with open(os.path.join(HANDLER_DIR, name)) as f:
            doc = json.load(f)
        resources.append((doc["$id"], Resource.from_contents(doc)))
    return Registry().with_resources(resources)


@unittest.skipUnless(HAVE_JSONSCHEMA, "jsonschema not installed")
class T01SchemasAgainstUcp(unittest.TestCase):
    def validator(self, ref):
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$ref": ref}
        return jsonschema.Draft202012Validator(schema, registry=registry())

    def test_files_are_valid_2020_12_schemas(self):
        for name in ("schema.json", "instrument.json", "credential.json"):
            with open(os.path.join(HANDLER_DIR, name)) as f:
                jsonschema.Draft202012Validator.check_schema(json.load(f))

    def test_instrument_example_valid_and_also_a_ucp_payment_instrument(self):
        inst = instrument()
        self.validator(OWN_BASE + "instrument.json").validate(inst)
        self.validator("https://ucp.dev/schemas/common/types/payment_instrument.json").validate(inst)
        self.validator(OWN_BASE + "credential.json").validate(inst["credential"])

    def test_instrument_refuses_lower_case_hash_and_other_type(self):
        v = self.validator(OWN_BASE + "instrument.json")
        self.assertFalse(v.is_valid(instrument(block_hash=HASH.lower())))
        bad = instrument()
        bad["type"] = "card"
        self.assertFalse(v.is_valid(bad))

    def test_response_config_example_valid(self):
        response = dict(DECLARATION)
        response["config"] = dict(DECLARATION["config"], **self_quote())
        self.validator(OWN_BASE + "schema.json#/$defs/io.github.dhyabi2.nano/response_schema").validate(response)


def self_quote():
    q = verify.make_quote("chk_1", CFG["amount_raw"], EXPIRES)
    return q


@unittest.skipUnless(HAVE_JSONSCHEMA, "jsonschema not installed")
class T02Declaration(unittest.TestCase):
    def validator(self):
        ref = OWN_BASE + "schema.json#/$defs/io.github.dhyabi2.nano/business_schema"
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$ref": ref}
        return jsonschema.Draft202012Validator(schema, registry=registry())

    def test_declaration_valid_as_business_schema(self):
        self.validator().validate(DECLARATION)

    def test_declaration_valid_as_ucp_business_schema(self):
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                  "$ref": "https://ucp.dev/schemas/payment_handler.json#/$defs/business_schema"}
        jsonschema.Draft202012Validator(schema, registry=registry()).validate(DECLARATION)

    def test_wrong_network_refused(self):
        bad = copy.deepcopy(DECLARATION)
        bad["config"]["network"] = "nano:testnet"
        self.assertFalse(self.validator().is_valid(bad))

    def test_pay_to_one_checksum_digit_off_fails(self):
        good = DECLARATION["config"]["pay_to"]
        last = good[-1]
        swapped = "3" if last != "3" else "4"
        bad_address = good[:-1] + swapped
        bad = copy.deepcopy(DECLARATION)
        bad["config"]["pay_to"] = bad_address
        # The pattern still matches; the checksum is what refuses it.
        self.assertTrue(self.validator().is_valid(bad))
        self.assertFalse(verify.is_valid_account(bad_address))
        with self.assertRaises(ValueError):
            verify.NanoHandler("nano_mainnet_1", bad["config"], FakeNode(), None)


class Accounts(unittest.TestCase):
    def test_genesis_account_round_trip(self):
        # Public genesis account of the Nano ledger.
        key = bytes.fromhex("E89208DD038FBB269987689621D52292AE9C35941A7484756ECCED92A65093BA")
        account = "nano_3t6k35gi95xu6tergt6p69ck76ogmitsa8mnijtpxm9fkcm736xtoncuohr3"
        self.assertEqual(verify.account_from_public_key(key), account)
        self.assertEqual(verify.public_key_from_account(account), key)

    def test_fixture_accounts_valid(self):
        for k in ("pay_to", "payer", "other"):
            self.assertTrue(verify.is_valid_account(CFG[k]))


# 3-10: processing -----------------------------------------------------------

class T03Success(Base):
    def test_confirmed_exact_send_succeeds(self):
        node = FakeNode(load("blocks_info_send_confirmed.json"))
        result = self.handler(node).verify({"id": "chk_1"}, instrument(), self.quote())
        self.assertEqual(result, {
            "status": "succeeded", "network": "nano:mainnet", "block_hash": HASH,
            "amount_raw": CFG["amount_raw"], "payer": CFG["payer"]})
        self.assertEqual(self.store.count(), 1)


class T04Idempotency(Base):
    def test_same_block_same_checkout_returns_same_result(self):
        node = FakeNode(load("blocks_info_send_confirmed.json"))
        h = self.handler(node)
        first = h.verify({"id": "chk_1"}, instrument(), self.quote())
        second = h.verify({"id": "chk_1"}, instrument(), self.quote())
        self.assertEqual(first, second)
        self.assertEqual(self.store.count(), 1)
        self.assertEqual(node.calls, 1)


class T05Replay(Base):
    def test_same_block_other_checkout_unrecoverable(self):
        node = FakeNode(load("blocks_info_send_confirmed.json"))
        h = self.handler(node)
        h.verify({"id": "chk_1"}, instrument(), self.quote("chk_1"))
        result = h.verify({"id": "chk_2"}, instrument(), self.quote("chk_2"))
        self.assertEqual(self.severity(result), "unrecoverable")
        self.assertEqual(result["reason"], "replay")

    def test_replay_refused_after_restart(self):
        node = FakeNode(load("blocks_info_send_confirmed.json"))
        self.handler(node).verify({"id": "chk_1"}, instrument(), self.quote("chk_1"))
        self.store.close()
        self.store = verify.SeenStore(self.db)  # a fresh process opens the same file
        result = self.handler(node).verify({"id": "chk_2"}, instrument(), self.quote("chk_2"))
        self.assertEqual(result["reason"], "replay")
        again = self.handler(node).verify({"id": "chk_1"}, instrument(), self.quote("chk_1"))
        self.assertEqual(again["status"], "succeeded")


class T06ExactAmount(Base):
    def test_one_raw_more_or_less_refused(self):
        amount = int(CFG["amount_raw"])
        for sent in (amount + 1, amount - 1):
            node = FakeNode(with_block(amount=str(sent)))
            result = self.handler(node).verify({"id": "chk_1"}, instrument(), self.quote())
            self.assertEqual(self.severity(result), "requires_buyer_input")
            self.assertEqual(result["reason"], "wrong_amount")
        self.assertEqual(self.store.count(), 0)


class T07BigIntegers(Base):
    def test_one_xno_plus_one_raw(self):
        one_xno = str(verify.RAW_PER_XNO)
        self.assertEqual(one_xno, "1" + "0" * 30)
        big = str(verify.RAW_PER_XNO + 1)
        self.assertEqual(big, "1000000000000000000000000000001")
        node = FakeNode(with_block(amount=big))
        ok = self.handler(node).verify({"id": "chk_1"}, instrument(), self.quote(amount_raw=big))
        self.assertEqual(ok["status"], "succeeded")
        self.assertEqual(ok["amount_raw"], big)
        node2 = FakeNode(with_block(amount=one_xno))
        other = instrument(block_hash=HASH)
        self.store.close()
        self.store = verify.SeenStore(os.path.join(self.tmp.name, "other.sqlite"))
        refused = self.handler(node2).verify({"id": "chk_9"}, other, self.quote("chk_9", amount_raw=big))
        self.assertEqual(refused["reason"], "wrong_amount")

    def test_display_is_derived(self):
        self.assertEqual(verify.raw_to_xno_display(CFG["amount_raw"]), "0.003")
        self.assertEqual(verify.raw_to_xno_display(str(verify.RAW_PER_XNO)), "1")


class T08NotConfirmedOrNotSend(Base):
    def test_unconfirmed_recoverable(self):
        node = FakeNode(load("blocks_info_send_unconfirmed.json"))
        result = self.handler(node).verify({"id": "chk_1"}, instrument(), self.quote())
        self.assertEqual(self.severity(result), "recoverable")
        self.assertEqual(result["reason"], "not_confirmed")

    def test_not_found_recoverable(self):
        node = FakeNode(load("blocks_info_not_found.json"))
        result = self.handler(node).verify({"id": "chk_1"}, instrument(CFG["hash_missing"]), self.quote())
        self.assertEqual(self.severity(result), "recoverable")

    def test_receive_block_requires_buyer_input(self):
        node = FakeNode(load("blocks_info_receive.json"))
        result = self.handler(node).verify({"id": "chk_1"}, instrument(CFG["hash_receive"]), self.quote())
        self.assertEqual(self.severity(result), "requires_buyer_input")

    def test_send_to_other_account_refused(self):
        node = FakeNode(with_block(contents=dict(
            load("blocks_info_send_confirmed.json")["blocks"][HASH]["contents"],
            link_as_account=CFG["other"])))
        result = self.handler(node).verify({"id": "chk_1"}, instrument(), self.quote())
        self.assertEqual(result["reason"], "wrong_destination")

    def test_bad_hash_and_unknown_handler(self):
        node = FakeNode(load("blocks_info_send_confirmed.json"))
        h = self.handler(node)
        self.assertEqual(h.verify({"id": "chk_1"}, instrument(HASH.lower()), self.quote())["reason"], "bad_hash")
        self.assertEqual(h.verify({"id": "chk_1"}, instrument(handler_id="other"), self.quote())["reason"],
                         "unknown_handler")
        self.assertEqual(node.calls, 0)


class T09Expiry(Base):
    def test_61_seconds_late_expired_59_accepted(self):
        node = FakeNode(load("blocks_info_send_confirmed.json"))  # block at 1795000000
        h = self.handler(node)
        late = h.verify({"id": "chk_1"}, instrument(), self.quote(expires_at="2026-11-18T11:05:39Z"))
        self.assertEqual(late["reason"], "expired")
        self.assertEqual(self.severity(late), "requires_buyer_input")
        ok = h.verify({"id": "chk_1"}, instrument(), self.quote(expires_at="2026-11-18T11:05:41Z"))
        self.assertEqual(ok["status"], "succeeded")


class T10NodeFailure(Base):
    def test_http_500_recoverable_nothing_recorded(self):
        node = FakeNode(exc=verify.NodeUnavailable("HTTP Error 500"))
        result = self.handler(node).verify({"id": "chk_1"}, instrument(), self.quote())
        self.assertEqual(self.severity(result), "recoverable")
        self.assertEqual(result["reason"], "node_unavailable")
        self.assertEqual(self.store.count(), 0)

    def test_invalid_json_recoverable(self):
        import http.server
        import threading

        class Bad(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"not json")

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Bad)
        threading.Thread(target=server.handle_request, daemon=True).start()
        rpc = verify.http_rpc("http://127.0.0.1:%d/" % server.server_port, timeout=5)
        result = self.handler(rpc).verify({"id": "chk_1"}, instrument(), self.quote())
        server.server_close()
        self.assertEqual(result["reason"], "node_unavailable")
        self.assertEqual(self.store.count(), 0)


class Quotes(unittest.TestCase):
    def test_amount_unique_among_open_quotes(self):
        a = CFG["amount_raw"]
        q = verify.make_quote("chk_3", a, EXPIRES, open_amounts_raw=[a, str(int(a) + 1)])
        self.assertEqual(q["amount_raw"], str(int(a) + 2))
        self.assertEqual(q["quote_id"], "chk_3")

    def test_quote_of_another_checkout_is_a_caller_error(self):
        store = verify.SeenStore(":memory:")
        h = verify.NanoHandler("nano_mainnet_1", DECLARATION["config"], FakeNode(), store)
        with self.assertRaises(ValueError):
            h.verify({"id": "chk_1"}, instrument(), verify.make_quote("chk_2", CFG["amount_raw"], EXPIRES))

    def test_config_without_valid_pay_to_refused(self):
        with self.assertRaises(ValueError):
            verify.NanoHandler("nano_mainnet_1", {"network": "nano:mainnet"}, FakeNode(), None)


if __name__ == "__main__":
    unittest.main()
