---
name: nano-fetch
description: Fetch a URL and, when it answers HTTP 402 with a Nano (XNO) price, pay it once through your own signer and retry. A per-call cap and a total budget in raw are checked before anything is signed, and a journal file refuses to pay the same order twice, also after a restart. This skill holds no key and no seed.
version: 0.1.0
metadata:
  openclaw:
    requires:
      bins:
        - python3
---

# nano-fetch

Use this when you BUY something for Nano (XNO): a page, an API answer or a tool call that costs a
fraction of a coin and answers `402 Payment Required` until it is paid. It is the buyer's side of
`nano-settlement-verify` (the seller's check).

`fetch.py` is in this folder, with the two things it imports: `middleware.py` (the settle step) and
the `xno_buyer_plan/` package (the quote reader). Standard library only; nothing to install. Copy the
whole folder and run `python3 fetch.py` from it (or give its path).

## Before the first paid call: the operator's three settings

Do not guess these. If any is missing, run without them (a 402 is then shown, never paid) and ask the
person you work for.

1. **A signer** - `--signer module.attr`: a Python function the operator wrote, which holds the key.
   It gets `{"network", "payTo", "amount_raw", "representative", "orderId"}`, publishes a send of
   `amount_raw` raw to `payTo` (with `representative` as the block's representative when it is not
   None), waits for confirmation and returns the 64-hex block hash. You never see the key, and you never
   write a key, a seed or a wallet file yourself. The signer's module is found on `PYTHONPATH`
   (for example `PYTHONPATH=~/wallet`, where the operator keeps `mywallet.py`).
2. **A journal** - `--journal FILE`: one file per agent, kept between runs. `--signer` without
   `--journal` is refused.
3. **The limits, in raw** (1 XNO = 10**30 raw): `--cap-raw N` per call, `--budget-raw N` over the whole
   journal (default 10 x the cap). A price over either is refused before the signer is called.

## Run it

Look first, pay nothing:

```sh
python3 fetch.py https://seller.example/report -o report.json
```

Pay at most one tenth of an XNO (10**29 raw) for this call, and at most 10**30 raw in all:

```sh
python3 fetch.py https://seller.example/report --signer mywallet.sign_bound_send --journal ~/.nano-pay.jsonl --cap-raw 100000000000000000000000000000 --budget-raw 1000000000000000000000000000000 -o report.json
```

A POST with a header and a body (`-X`/`--request` METHOD, `-H`/`--header 'Name: value'` as often as
needed, `-d`/`--data` BODY, `-o`/`--output` FILE; POST is used whenever `-d` is given):

```sh
python3 fetch.py https://seller.example/api -X POST -H 'Content-Type: application/json' -d '{"q": "nano"}' --signer mywallet.sign_bound_send --journal ~/.nano-pay.jsonl --timeout 60
```

`--allow-unbound` also pays a quote that only asks for a send hash, with nothing binding the send to
this one request. Leave it off unless the operator asked for it.

## Read the answer

| exit | meaning | what you do |
|------|---------|-------------|
| 0 | a 2xx or 3xx answer, paid or free | use the body (stdout or `-o FILE`) |
| 1 | another HTTP status, or no connection | report it; nothing was paid unless stderr says `paid` |
| 2 | usage: a bad flag, URL or signer | fix the command; nothing was paid |
| 3 | a 402 that was not paid; stderr names why | report the reason; do not retry with a higher cap on your own |
| 4 | paid, and the retry still met 402 | stop; the payment is in the journal; report the hash on stderr |

Reasons on stderr after `402 not paid:` include `not_configured` (no signer or journal), `over_cap`, `over_budget`,
`unbound` (a send-hash quote without `--allow-unbound`), `signer_no_hash` (the signer did not return a
hash; the intent stays in the journal and is never paid again) and `replayed` (this order is already in
the journal).

## The journal

One JSON object a line, fsynced: an `intent` line (`key`, `amount_raw`, `orderId`, `url`) before the
signer is called, and a `paid` line (`key`, `amount_raw`, `orderId`, `blockHash`) after. To know what
you spent, add `amount_raw` over the `paid` lines. Never edit or delete the file: it is what stops a
second payment for one order.

## As a WebFetch hook (installed as a plugin)

Installed as the `nano-fetch` plugin, `hooks/hooks.json` runs `hook.py` after every WebFetch call. When
WebFetch reports HTTP 402, the hook asks the same URL once more itself (WebFetch's result has no headers to
read the quote from), pays a bound order through the same settle step, journal, cap and budget as
`fetch.py`, and adds the paid answer next to WebFetch's result. A send-hash quote is never paid from the
hook. It is off until the operator sets, in the environment (for example the `env` block of settings):
`NANO_FETCH_SIGNER` (module.attr), `NANO_FETCH_JOURNAL` (file), and optionally `NANO_FETCH_CAP_RAW`,
`NANO_FETCH_BUDGET_RAW` and `NANO_FETCH_MAX_CHARS`. Unset, a 402 is reported in one line and nothing is
requested or paid. The hook always exits 0, so it never blocks a session.
