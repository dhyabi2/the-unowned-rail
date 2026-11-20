"""Reference processor for the `io.github.dhyabi2.nano` UCP payment handler.

Python standard library only. The business verifies a buyer's Nano send block
against its own quote, with its own node, and records every credited block
hash in a durable store so a block pays for one checkout, once.

No key and no seed is used or accepted anywhere: verification only reads a
confirmed block from a node URL the operator configures.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone

HANDLER_NAME = "io.github.dhyabi2.nano"
HANDLER_VERSION = "2026-11-20"
NETWORK = "nano:mainnet"
INSTRUMENT_TYPE = "nano_block"
CREDENTIAL_TYPE = "nano_send_block"

RAW_PER_XNO = 10 ** 30
EXPIRY_GRACE_SECONDS = 60

_ALPHABET = "13456789abcdefghijkmnopqrstuwxyz"
_ADDRESS_RE = re.compile(r"^(nano|xrb)_[13][13-9a-km-uw-z]{59}$")
_HASH_RE = re.compile(r"^[0-9A-F]{64}$")
_DIGITS_RE = re.compile(r"^[0-9]+$")


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------

def _b32encode(data: bytes, bits: int) -> str:
    value = int.from_bytes(data, "big")
    chars = []
    for _ in range(bits // 5):
        chars.append(_ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def _b32decode(text: str) -> int:
    value = 0
    for ch in text:
        value = (value << 5) | _ALPHABET.index(ch)
    return value


def account_from_public_key(public_key: bytes) -> str:
    """Encode a 32-byte public key as a `nano_` account with its checksum."""
    if len(public_key) != 32:
        raise ValueError("public key must be 32 bytes")
    body = _b32encode(b"\x00" + public_key, 260)  # 4 zero bits + 256 key bits
    checksum = hashlib.blake2b(public_key, digest_size=5).digest()[::-1]
    return "nano_" + body + _b32encode(checksum, 40)


def public_key_from_account(account: str) -> bytes:
    """Decode an account and check its checksum. Raises ValueError if invalid."""
    if not isinstance(account, str) or not _ADDRESS_RE.match(account):
        raise ValueError("not a Nano account")
    text = account.split("_", 1)[1]
    key_int = _b32decode(text[:52])
    if key_int >> 256:
        raise ValueError("not a Nano account")
    public_key = key_int.to_bytes(32, "big")
    checksum = _b32decode(text[52:]).to_bytes(5, "big")
    if hashlib.blake2b(public_key, digest_size=5).digest()[::-1] != checksum:
        raise ValueError("Nano account checksum does not match")
    return public_key


def is_valid_account(account: str) -> bool:
    try:
        public_key_from_account(account)
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------------
# Amounts and quotes
# --------------------------------------------------------------------------

def raw_to_xno_display(amount_raw: str, places: int = 6) -> str:
    """Display string derived from raw. Never used for checking."""
    if not _DIGITS_RE.match(amount_raw):
        raise ValueError("amount_raw must be a string of digits")
    raw = int(amount_raw)
    whole, frac = divmod(raw, RAW_PER_XNO)
    frac_text = str(frac).rjust(30, "0")[:places].rstrip("0")
    return str(whole) + ("." + frac_text if frac_text else "")


def make_quote(checkout_id: str, amount_raw: str, expires_at: str,
               open_amounts_raw=()) -> dict:
    """Quote for one checkout. If another open quote already asks for the same
    amount, the amount is raised by 1 raw until it is unique, so a block can
    match one open quote only (Nano blocks carry no memo)."""
    if not _DIGITS_RE.match(amount_raw) or int(amount_raw) <= 0:
        raise ValueError("amount_raw must be a positive string of digits")
    taken = {int(a) for a in open_amounts_raw}
    amount = int(amount_raw)
    while amount in taken:
        amount += 1
    _parse_time(expires_at)
    return {
        "quote_id": checkout_id,
        "amount_raw": str(amount),
        "amount_xno": raw_to_xno_display(str(amount)),
        "expires_at": expires_at,
    }


def _parse_time(value: str) -> datetime:
    text = value.replace("Z", "+00:00") if value.endswith("Z") else value
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must carry a time zone")
    return parsed


# --------------------------------------------------------------------------
# UCP messages
# --------------------------------------------------------------------------

MESSAGES = {
    "bad_hash": ("recoverable", "Nano block hash is not 64 hex characters."),
    "unknown_handler": ("recoverable", "Nano instrument does not name an advertised handler."),
    "not_confirmed": ("recoverable", "Nano block is not confirmed yet; retry."),
    "wrong_destination": ("requires_buyer_input", "Nano block does not pay this business's account."),
    "wrong_amount": ("requires_buyer_input", "Nano block amount does not match the quote exactly."),
    "expired": ("requires_buyer_input", "Nano quote expired; request a new checkout total."),
    "replay": ("unrecoverable", "Nano block was already used for another checkout."),
    "node_unavailable": ("recoverable", "Payment could not be checked right now; retry."),
}


def error(case: str) -> dict:
    severity, content = MESSAGES[case]
    return {
        "status": "failed",
        "reason": case,
        "messages": [{
            "type": "error",
            "code": "payment_failed",
            "severity": severity,
            "content": content,
        }],
    }


# --------------------------------------------------------------------------
# Node access and the seen store
# --------------------------------------------------------------------------

class NodeUnavailable(Exception):
    pass


def http_rpc(node_url: str, timeout: float = 10.0):
    """RPC callable for the business's own node. The URL is configured by the
    operator; it is never taken from a platform or a buyer."""
    def call(payload: dict) -> dict:
        request = urllib.request.Request(
            node_url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise NodeUnavailable(str(exc)) from exc
    return call


class SeenStore:
    """Durable record of credited block hashes (SQLite, survives restarts).
    The primary key makes a second credit of one hash impossible, even under
    two concurrent requests."""

    def __init__(self, path: str):
        self._db = sqlite3.connect(path, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS credited ("
            " block_hash TEXT PRIMARY KEY,"
            " checkout_id TEXT NOT NULL,"
            " result TEXT NOT NULL)")

    def get(self, block_hash: str):
        row = self._db.execute(
            "SELECT checkout_id, result FROM credited WHERE block_hash = ?",
            (block_hash,)).fetchone()
        if row is None:
            return None
        return row[0], json.loads(row[1])

    def credit(self, block_hash: str, checkout_id: str, result: dict) -> bool:
        try:
            self._db.execute(
                "INSERT INTO credited (block_hash, checkout_id, result) VALUES (?, ?, ?)",
                (block_hash, checkout_id, json.dumps(result, sort_keys=True)))
            return True
        except sqlite3.IntegrityError:
            return False

    def count(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM credited").fetchone()[0]

    def close(self):
        self._db.close()


# --------------------------------------------------------------------------
# The handler
# --------------------------------------------------------------------------

class NanoHandler:
    def __init__(self, handler_id: str, config: dict, rpc, store: SeenStore):
        if config.get("network") != NETWORK:
            raise ValueError("config.network must be nano:mainnet")
        public_key_from_account(config.get("pay_to", ""))  # checksum check
        self.handler_id = handler_id
        self.config = config
        self.pay_to_key = public_key_from_account(config["pay_to"])
        self.rpc = rpc
        self.store = store

    def verify(self, checkout: dict, instrument: dict, quote: dict) -> dict:
        checkout_id = checkout["id"]
        if quote.get("quote_id") != checkout_id:
            # The business passed the quote of another checkout: a caller bug.
            raise ValueError("quote does not belong to this checkout")
        if not _DIGITS_RE.match(str(quote.get("amount_raw", ""))):
            raise ValueError("quote.amount_raw must be a string of digits")

        # 1. Handler, credential type, hash shape.
        if instrument.get("handler_id") != self.handler_id or \
                instrument.get("type") != INSTRUMENT_TYPE:
            return error("unknown_handler")
        credential = instrument.get("credential") or {}
        block_hash = credential.get("block_hash")
        if credential.get("type") != CREDENTIAL_TYPE or \
                not isinstance(block_hash, str) or not _HASH_RE.match(block_hash):
            return error("bad_hash")

        # 2. Idempotency: same block, same checkout -> the earlier result.
        earlier = self.store.get(block_hash)
        if earlier is not None and earlier[0] == checkout_id:
            return earlier[1]

        # 3. Read the block from the business's own node.
        try:
            answer = self.rpc({"action": "blocks_info", "hashes": [block_hash],
                               "json_block": "true", "source": "true"})
        except NodeUnavailable:
            return error("node_unavailable")
        if not isinstance(answer, dict):
            return error("node_unavailable")
        info = (answer.get("blocks") or {}).get(block_hash)
        if info is None:
            if "error" in answer or "blocks" in answer:
                return error("not_confirmed")  # not seen yet by our node
            return error("node_unavailable")
        if not isinstance(info, dict):
            return error("node_unavailable")
        contents = info.get("contents") or {}
        if info.get("subtype") != "send":
            return error("wrong_destination")
        if str(info.get("confirmed")) != "true":
            return error("not_confirmed")

        # 4. Destination.
        destination = contents.get("link_as_account")
        try:
            if destination:
                dest_key = public_key_from_account(destination)
            else:
                dest_key = bytes.fromhex(contents.get("link", ""))
        except ValueError:
            return error("wrong_destination")
        if dest_key != self.pay_to_key:
            return error("wrong_destination")

        # 5. Exact amount, compared as integers of arbitrary size.
        amount = info.get("amount")
        if not isinstance(amount, str) or not _DIGITS_RE.match(amount) or \
                int(amount) != int(quote["amount_raw"]):
            return error("wrong_amount")

        # 6. Not after the quote's expiry plus the grace period.
        try:
            block_time = int(info.get("local_timestamp", ""))
        except (TypeError, ValueError):
            return error("node_unavailable")
        deadline = _parse_time(quote["expires_at"]).timestamp() + EXPIRY_GRACE_SECONDS
        if block_time > deadline:
            return error("expired")

        # 7 and 8. Credit once ever, recorded before success is answered.
        if earlier is not None:
            return error("replay")
        payer = info.get("block_account") or contents.get("account")
        result = {
            "status": "succeeded",
            "network": NETWORK,
            "block_hash": block_hash,
            "amount_raw": str(int(amount)),
            "payer": payer,
        }
        if not self.store.credit(block_hash, checkout_id, result):
            again = self.store.get(block_hash)
            if again is not None and again[0] == checkout_id:
                return again[1]
            return error("replay")
        return result


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
