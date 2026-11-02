# Seller quickstart: accept XNO with no funding, no onboarding and no inbound connection

For a seller (an agent or its operator) who wants to be paid in XNO beside whatever it takes today. You need: an address, somewhere to publish it, and
outbound HTTPS to a public Nano node. You do not need: money, a node, a public URL, an open port, a webhook, or anyone's approval.

Everything marked "ran" below was run on 2026-11-02 (Python 3.14, stdlib only).

## 1. Make the address offline (no network)

```
git clone https://github.com/dhyabi2/nano-wallet-xno && cd nano-wallet-xno && git checkout v1.2.0
python3 nano_keygen.py selftest                       # ran: "selftest: ok - matches the official vector", exit 0
python3 nano_keygen.py new --seed-file ./seed.txt     # address on stdout; seed written 0600 to seed.txt, never printed
python3 nano_keygen.py check nano_...                 # exit 0 if the checksum holds
```

The seed is the account: keep `seed.txt` offline and never paste it anywhere. The self-test is the test vector: if it prints `ok` your copy derives
keys the way the official documentation says it must. (`v1.2.0` is commit `eaf48d388c2f`.)

## 2. Publish only the address

Put `Pay in XNO to: nano_...` next to your existing payment instructions, or add an entry to `accepts[]` if you sell over x402
([seller guide](https://github.com/dhyabi2/dual-rail/blob/main/docs/x402-nano-seller-guide.md)). An address nobody has paid yet is fine: an account does not exist on the ledger until the first receive.

## 3. See payments with outbound requests only

```
curl -O https://raw.githubusercontent.com/dhyabi2/the-unowned-rail/main/tools/xno_poll.py
python3 xno_poll.py nano_YOURADDRESS --watch 30            # one JSON line per new payment; no key, nothing sent
python3 xno_poll.py nano_YOURADDRESS --expect-raw 500000000000000000000000000   # exit 0 once a confirmed payment of >= 0.0005 XNO is visible, else 1
```

What it does: asks `receivable` (confirmed incoming sends the account has not yet pocketed, with the sender) and `account_history` (what the account already received), tries the next of three public nodes only if the
previous one is unreachable, and prints each block once. It makes no inbound connection, so it runs in a sandbox whose only open door is HTTPS out.
Ran against the public account in [proof/ARION.md](../proof/ARION.md): 7 received blocks printed, `--expect-raw` exit 0 for a 6.2756 XNO threshold it has received, exit 1 for an amount it has not.
The `receivable` path ran and returned nothing for that account (nothing was waiting); we did not have a live waiting payment to show it catching one, so treat that path as run but not yet demonstrated on a real incoming send.

1 XNO = 10^30 raw. Compare raw integers, never floats.

## 4. Check one payment against what you quoted, with no code of ours

```
curl -s -H 'Content-Type: application/json' -d '{"action":"block_info","json_block":"true","hash":"B749B757EE750FC9AEA72F33CB429EACCD2ABEC9F2CCF59BF17AFAC304C9A58F"}' https://rainstorm.city/api | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['confirmed'],d['subtype'],d['amount'],d['contents']['link_as_account'])"
# ran -> true send 500000000000000000000000000 nano_1yo6c1t64ahfjdw1dxizmbbnpdmbrckwhw9phbg5pdkeubrizga4qhnjmnx7
```

That is the test vector for the check: `confirmed` true, subtype `send`, the amount you quoted in raw, and the account you expected. Four things must hold; if any does not, it is not your payment.
To make a payment answer to one request only (so one block cannot pay for two orders), see the
[binding standard](https://github.com/dhyabi2/xno-call-binding/blob/main/docs/BINDING-STANDARD.md). For two-node agreement before you hand over something you cannot take back, see [NODES.md](NODES.md).

## 5. When you want to spend it

Receiving only needs steps 1 to 4. The XNO sits as a confirmed receivable until you sign a receive block with your key (a signature and a small proof of work, no balance needed);
any Nano wallet that accepts a seed does it. Receiving cost nothing, and you decide when. Details and the work required: [FIRST-TRANSACTION-WITHOUT-A-REGISTRAR.md](FIRST-TRANSACTION-WITHOUT-A-REGISTRAR.md).

## For an egress-limited sandbox (no public URL, no inbound)

This is the shape that fits an agent that can only make outbound calls: poll, do not listen. Poll every 30 s, and treat "no node answered" (the tool exits with that message) as unknown, never as unpaid.
A hosted checkout page is not required; the address is the whole interface.

## What this does not do

It holds no key and cannot send. It does not decide a refund policy, convert to dollars, or create a buyer. A confirmed receivable is the node's word; for a large amount ask a second node first.
