# For the person who runs the agent: add an XNO address beside your checkout link

You can forward this page to your operator as it is. It is written for a person, not an agent. Nothing here asks for a key, a seed or
a payment; every command below only reads, or makes a key on your own machine.

## The decision, in one sentence

Put one extra line on your agent's payment card, `Pay in XNO to: nano_...`, **beside** the checkout link you already have. Nothing is switched off
and nothing is replaced. The address can receive and cannot spend. The key stays with you.

## What it costs

- **To receive: nothing.** A Nano transfer has no fee. Checked on 2026-11-02 on a real public account (21 confirmed blocks, 29.03 XNO received, 14 sends):
  received minus sent equals the balance to the last raw unit, so nothing was taken ([proof/ARION.md](../proof/ARION.md)).
- **To open the account: nothing you must pay.** The account exists once you first pocket a payment; a receive block needs a signature and a small proof of work and no balance
  ([FIRST-TRANSACTION-WITHOUT-A-REGISTRAR.md](FIRST-TRANSACTION-WITHOUT-A-REGISTRAR.md)).
- **To turn XNO into dollars later:** a spread, once, when you choose to. On 2026-11-02 the best public order book we measured (Binance, needs an account) was 31.5 bps wide, with 15.7 bps of slippage on a $100 order and 15.7 buying / 30.4 selling on $1,000 ([XNO-LIQUIDITY.md](XNO-LIQUIDITY.md)).
  An instant swap service that needs no account cost 4.36% to sell $100 of XNO into USDC the same morning ([xno-offramp-costs](https://github.com/dhyabi2/xno-offramp-costs)). Convert in batches, not per payment.

## What can go wrong

| Risk | How big, measured | What to do |
|---|---|---|
| Price moves while you hold XNO | last 30 days: range $0.3222 to $0.3646, daily standard deviation 2.3%, whole period -11.0% | hold only what the period needs; convert on a schedule |
| Nobody pays | a rail creates no buyers; a payer has to want it | add the line, tell buyers it exists, do not count it as revenue until a block arrives |
| A payment is final | a Nano send cannot be reversed by the payer or by us | decide your refund policy in your own terms before you publish the address |
| You lose the key | the seed is the account | keep it offline, one copy somewhere safe; never paste it into a chat, a ticket or an agent |

## What you never need to do

- Give anyone your seed or key. We never ask for one and neither should anyone who sends you this page.
- Run a node, open an inbound port, or host a public URL. You can watch for payments with outbound requests only ([SELLER-QUICKSTART.md](SELLER-QUICKSTART.md)).
- Replace your existing rail.

## The five steps (about five minutes)

1. On a machine you trust, make a key with no network call: `git clone https://github.com/dhyabi2/nano-wallet-xno && cd nano-wallet-xno && git checkout 6420e935816c && ( umask 077; python3 cli.py new > nano-key.json )`
2. Read the address only: `python3 -c "import json;print(json.load(open('nano-key.json'))['address'])"` and check it with `python3 cli.py check nano_...` (exit 0 if valid).
3. Keep `nano-key.json` offline. It is yours, not the agent's.
4. Give the agent the address and one line for its card: `Pay in XNO to: nano_...`
5. When a payment arrives, anyone can check it without trusting us: [First five minutes](https://github.com/dhyabi2/nano-wallet-xno#first-five-minutes), or
   `python3 tools/xno_poll.py nano_...` from this repository (outbound only, holds no key).

## The honest part

- In everything we have recorded, agent-to-agent is where XNO payments happen today; we have no case of a shop owner paying a small business in XNO. See [WHO-PAID-IN-XNO.md](WHO-PAID-IN-XNO.md) for the evidence, including that it is thin.
- If your agent has no buyer who wants to pay this way, the line does nothing. A rail is useful the day a payer needs it.
- The longer version for operators, including the receive-only profile that has no send function at all: [OPERATORS.md](../OPERATORS.md).
