"""A stub MCP seller that settles a payment in the shape basementstudio/xmcp#821's payer sends (FRONTIER 110 (c)).

#821 (packages/plugins/x402/src/nano-payer.ts at 1a0409a, read as data, see fixtures/xmcp-821-planner.json) retries
an MCP tools/call with `_meta['x402/payment'] = {x402Version, resource?, accepted, payload: {blockHash, orderId?}}`
after the payer's wallet has published the send. No public seller reads that today (rail run 260: it pays 0 of 16).
This module is the smallest seller that does, so the shape is proven on paper end to end:

- an unpaid call to a priced tool returns an x402 v2 offer (exact, nano:mainnet) as the tool result, isError true;
  every offer carries its own orderId (xno-binding/v1/rep), so a payment is bound to THIS call's order;
- a paid call is settled by reading the block from a node URL the operator configures (`block_info`, json_block):
  a confirmed state send, link_as_account == payTo, amount == the order's price in raw exactly, representative ==
  the bound account of SHA-256("xno-binding/v1/rep|" + orderId + "|" + payTo + "|" + amountRaw);
- a block hash and an order are each spent once, and both are written to a JSON file before the tool runs, so a
  replay is refused after a restart too.

No key, no seed, no signing: the seller only reads. Stdlib only. Not wired to anything of ours that moves money.
"""
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "skills", "nano-fetch", "xno_buyer_plan"))  # client_fit.py
from client_fit import account_from_key, nano_checksum_ok

NETWORK = "nano:mainnet"
BINDING = "xno-binding/v1/rep"
META_KEY = "x402/payment"
RAW_PER_XNO = 10 ** 30
HASH = re.compile(r"^[0-9A-Fa-f]{64}$")
RAW = re.compile(r"^[1-9][0-9]*$")


class Refused(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def bound_rep(order_id, pay_to, amount_raw):
    """The representative a bound send must carry (client_fit.py:42, x402-gateway src/nano.js:166-189)."""
    digest = hashlib.sha256(("%s|%s|%s|%s" % (BINDING, order_id, pay_to, amount_raw)).encode()).digest()
    return account_from_key(digest)


def raw_of_xno(xno_text):
    """'0.001' -> raw as an int, derived from 1 XNO = 10^30 raw, exact (no float)."""
    whole, _, frac = str(xno_text).partition(".")
    if not whole.isdigit() or (frac and not frac.isdigit()) or len(frac) > 30:
        raise ValueError("not an XNO amount: %r" % xno_text)
    return int(whole) * RAW_PER_XNO + int((frac or "0").ljust(30, "0"))


class SpentStore:
    """Spent block hashes and orders in one JSON file, rewritten atomically. Survives a restart."""

    def __init__(self, path):
        self.path = path
        self.data = {"orders": {}, "spent_blocks": [], "spent_orders": []}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.data.update(json.load(f))

    def save(self):
        d = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".spent-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)


class Seller:
    """MCP tools/call handler. `tools` maps a tool name to (price_xno, fn(arguments) -> text)."""

    def __init__(self, pay_to, node_url, store_path, tools):
        if not nano_checksum_ok(pay_to):
            raise ValueError("payTo fails its checksum")
        if not node_url:
            raise ValueError("a node URL must be configured")
        self.pay_to = pay_to
        self.node_url = node_url
        self.store = SpentStore(store_path)
        self.tools = {name: (raw_of_xno(price), fn) for name, (price, fn) in tools.items()}

    # --- the node read -------------------------------------------------------------------------
    def block_info(self, block_hash):
        body = json.dumps({"action": "block_info", "json_block": "true", "hash": block_hash}).encode()
        req = urllib.request.Request(self.node_url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())

    # --- offers ---------------------------------------------------------------------------------
    def offer(self, tool):
        price, _fn = self.tools[tool]
        order_id = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode().rstrip("=")  # 32 chars
        self.store.data["orders"][order_id] = {"tool": tool, "amount": str(price), "payTo": self.pay_to}
        self.store.save()
        accept = {"scheme": "exact", "network": NETWORK, "payTo": self.pay_to, "amount": str(price),
                  "asset": "XNO", "extra": {"binding": BINDING, "orderId": order_id}}
        return {"x402Version": 2, "resource": "mcp://tools/" + tool, "accepts": [accept]}

    # --- settlement -----------------------------------------------------------------------------
    def settle(self, tool, payment):
        if not isinstance(payment, dict) or payment.get("x402Version") != 2:
            raise Refused("bad-version")
        accepted = payment.get("accepted") if isinstance(payment.get("accepted"), dict) else {}
        payload = payment.get("payload") if isinstance(payment.get("payload"), dict) else {}
        block_hash = payload.get("blockHash")
        if not isinstance(block_hash, str) or not HASH.match(block_hash):
            raise Refused("no-blockhash")
        block_hash = block_hash.upper()
        order_id = payload.get("orderId") or (accepted.get("extra") or {}).get("orderId")
        order = self.store.data["orders"].get(order_id) if isinstance(order_id, str) else None
        if order is None:
            raise Refused("unknown-order")
        if order["tool"] != tool:
            raise Refused("order-for-another-tool")
        if accepted.get("scheme") != "exact" or accepted.get("network") != NETWORK:
            raise Refused("not-exact-nano")
        if accepted.get("payTo") != order["payTo"] or accepted.get("amount") != order["amount"]:
            raise Refused("accepted-differs-from-order")
        if block_hash in self.store.data["spent_blocks"]:
            raise Refused("replay-block")
        if order_id in self.store.data["spent_orders"]:
            raise Refused("replay-order")
        info = self.block_info(block_hash)
        if not isinstance(info, dict) or "error" in info or not isinstance(info.get("contents"), dict):
            raise Refused("block-not-found")
        c = info["contents"]
        if c.get("type") != "state" or info.get("subtype") != "send":
            raise Refused("not-a-send")
        if str(info.get("confirmed")) != "true":
            raise Refused("not-confirmed")
        if c.get("link_as_account") != order["payTo"]:
            raise Refused("wrong-destination")
        amount = info.get("amount")
        if not isinstance(amount, str) or not RAW.match(amount) or amount != order["amount"]:
            raise Refused("wrong-amount")
        if c.get("representative") != bound_rep(order_id, order["payTo"], order["amount"]):
            raise Refused("not-bound-to-order")
        self.store.data["spent_blocks"].append(block_hash)
        self.store.data["spent_orders"].append(order_id)
        self.store.save()
        return {"success": True, "network": NETWORK, "transaction": block_hash, "orderId": order_id,
                "payer": info.get("block_account")}

    # --- MCP JSON-RPC ---------------------------------------------------------------------------
    def handle(self, request):
        rid = request.get("id")
        if request.get("method") != "tools/call":
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}
        params = request.get("params") or {}
        tool = params.get("name")
        if tool not in self.tools:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": "unknown tool"}}
        payment = (params.get("_meta") or {}).get(META_KEY)
        if payment is None:
            offer = self.offer(tool)
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "isError": True, "structuredContent": offer,
                "content": [{"type": "text", "text": json.dumps(offer)}]}}
        try:
            receipt = self.settle(tool, payment)
        except Refused as e:
            offer = self.offer(tool)
            offer["error"] = e.code
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "isError": True, "structuredContent": offer,
                "content": [{"type": "text", "text": json.dumps(offer)}]}}
        text = self.tools[tool][1](params.get("arguments") or {})
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": text}], "_meta": {"x402/payment-response": receipt}}}
