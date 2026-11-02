# For the person who decides: letting your agent be paid in XNO

This page is for you, the human or team that runs an agent, not for the agent. An agent that says
"that is my operator's call" is right, and this is what the call is.

## What you are deciding

Whether to add **one receive-only address** to your agent's card, so that someone can pay it in Nano (XNO).
Nothing is switched off or replaced: whatever it takes today keeps working. A receive-only address cannot
spend. The agent never needs a key.

## The two numbers

- **Fee to move XNO: 0.** Checked live on 2026-11-02 against a real account (21 confirmed blocks, 7 receives,
  14 sends, 29.03 XNO received): received minus sent equals the balance to the last raw unit
  (209086572748719474521136187684), so no fee took anything. Re-run it yourself:
  `account_history` and `account_info` on `nano_3m8cz87zwxb1y16ob4bzp1eyek78qaig8ktohk7d45b18sh6u9exbowbnekr`
  at any public node (every block is listed in [proof/ARION.md](proof/ARION.md)).
- **Cost to get XNO in: not zero.** A third party's quote (api.nanswap.com, 2026-10-09 22:11 UTC): 1 USDC bought
  2.632 XNO, and 10 XNO sold for 3.068 USDC, so a 1 USDC round trip kept about 0.81 USDC. Quotes move; ask for
  your own before you swap. Swap once in a size that makes sense, not per payment.

## Five minutes, you do it, the agent touches no key

1. On any machine you trust, make a key with no network call:
   `git clone https://github.com/dhyabi2/nano-wallet-xno && cd nano-wallet-xno && git checkout 6420e935816c && ( umask 077; python3 cli.py new > nano-key.json )`
2. Read the address: `python3 -c "import json;print(json.load(open('nano-key.json'))['address'])"`.
   Check it: `python3 cli.py check nano_...` (exit 0 if the checksum holds). Keep `nano-key.json` (it holds the seed)
   offline. It is yours, not the agent's.
3. Give the agent only the address, and one line for its card: `Pay in XNO to: nano_...` (the operator holds the key).
4. When a payment arrives, check it without trusting anyone: [First five minutes](https://github.com/dhyabi2/nano-wallet-xno#first-five-minutes) has the one curl.

**Why a stranger cannot take the money out through your agent:** the agent only ever sees the address. The seed
is in your file. Anything sent to that address is yours to move with any Nano wallet that accepts a seed (compare the
address it shows with the one you published before you rely on it).

## If you would rather the agent make its own address

`nano-wallet-xno` has a receive-only profile in which `send` does not exist (it is absent from `tools/list`; calling
it is "method not found"), and one command lets you check that on the agent's machine before you approve anything:

```
python3 cli.py selfcheck --profile receive-only
# ... selfcheck: 7/7 pass - this install can receive XNO and cannot spend it.
```

That output is from a run on 2026-11-02. If you later want the agent to spend, the same repository has an operator
mandate (you sign once with your own key: total cap, per-payment maximum, purpose, expiry), documented in its README.
Do that as a separate decision; receiving does not require it.

## What this does not give you

- It does not make anyone pay your agent. A rail is useful the day a payer needs it.
- No escrow or conditional release: a Nano send is final. Decide your refund policy in your own terms.
- XNO changes in price against your accounting currency between receipt and conversion.
- Whether your agent should hold a presence on a paid network at all is a separate question that zero fees do not answer.
  It is yours.

The five-line Canon this comes from: [README](README.md).
