#!/usr/bin/env python3
"""quote_unit.py - for a paid URL, read its unpaid 402 and say what unit the XNO price is quoted in (read-only, pays nothing).

  python3 tools/quote_unit.py URL [URL ...]

Prints one JSON line per URL: {url, http, xno_price (decimal string), quote_unit: "xno-fixed" | "usd-pegged" | "unknown", usd_price?}
  xno-fixed   the 402 names only an XNO amount (the seller keeps price-in-dollars risk between repricings)
  usd-pegged  the same 402 also carries a USD/USDC price for the same call, so the XNO figure is a conversion of it
Reads these 402 shapes seen on 2026-11-02: x402 v2 `accepts[]` (body or `payment-required` header, base64 JSON), the flat
`payment{amount_xno,amount_raw}` shape, and `price_raw` / `x-payment-amount-raw`. Raw is integer, 1 XNO = 10^30 raw. Sends one GET.
"""
import base64
import json
import sys
import urllib.error
import urllib.request

XNO = 10 ** 30


def raw_to_xno(raw):
    raw = int(raw)
    s = f"{raw // XNO}.{raw % XNO:030d}".rstrip("0")
    return s[:-1] if s.endswith(".") else s


def parse(status, headers, body):
    """-> dict(xno_price, quote_unit, usd_price) from one 402 response; pure, no network."""
    h = {k.lower(): v for k, v in headers.items()}
    doc = None
    try:
        doc = json.loads(body)
    except Exception:
        pass
    if not isinstance(doc, dict) or "accepts" not in doc:
        for k in ("payment-required", "x-payment-required"):
            if k in h:
                try:
                    doc = json.loads(base64.b64decode(h[k] + "=" * (-len(h[k]) % 4)))
                except Exception:
                    pass
    out = {"xno_price": None, "quote_unit": "unknown", "usd_price": None}
    accepts = (doc or {}).get("accepts") if isinstance(doc, dict) else None
    raw = None
    for a in accepts or []:
        if str(a.get("network", "")).startswith("nano:") and str(a.get("amount") or a.get("maxAmountRequired") or "").isdigit():
            raw = int(a.get("amount") or a.get("maxAmountRequired"))
    if raw is None and isinstance(doc, dict):
        p = doc.get("payment") if isinstance(doc.get("payment"), dict) else doc
        for k in ("amount_raw", "price_raw"):
            if str(p.get(k, "")).isdigit():
                raw = int(p[k])
    if raw is None and str(h.get("x-payment-amount-raw", "")).isdigit():
        raw = int(h["x-payment-amount-raw"])
    if raw is None:
        return out
    out["xno_price"] = raw_to_xno(raw)
    out["quote_unit"] = "xno-fixed"
    for a in accepts or []:
        # a USDC leg on an EVM chain (6 decimals) beside the Nano leg means the XNO amount is derived from a dollar price
        if str(a.get("network", "")).startswith("eip155:") and str(a.get("amount", "")).isdigit():
            out["usd_price"] = int(a["amount"]) / 1e6
            out["quote_unit"] = "usd-pegged"
    info = (doc or {}).get("x-payment-info") if isinstance(doc, dict) else None
    if isinstance(info, dict) and (info.get("price") or {}).get("currency") in ("USDC", "USD"):
        out["usd_price"] = float(info["price"]["amount"])
        out["quote_unit"] = "usd-pegged"
    return out


def main(urls):
    for u in urls:
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"user-agent": "Mozilla/5.0"}), timeout=20)
            st, hd, body = r.status, dict(r.headers), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            st, hd, body = e.code, dict(e.headers), e.read().decode("utf-8", "replace")
        except Exception as e:
            print(json.dumps({"url": u, "error": str(e)}))
            continue
        print(json.dumps({"url": u, "http": st, **parse(st, hd, body)}))


if __name__ == "__main__":
    main(sys.argv[1:])
