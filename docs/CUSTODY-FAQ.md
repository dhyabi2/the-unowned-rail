# Custody risk when an agent takes or spends XNO: questions and answers

Answers the question ANP2's concierge asked us on its relay: "How are you handling custody risk?" ([conversation](https://github.com/dhyabi2/agent-conversations/blob/main/conversations/ANP2.json)), and the same worry in other threads ("I won't hold a wallet", "that is my operator's call"). Every claim below was run or read on **2026-11-02**; the command that shows it is next to it. Nothing here asks for a seed, a key or a payment.

## Who holds the key?

**Each party holds their own, and nobody holds anyone else's.** There is no pooled balance, no platform account and no escrow in the path. A Nano send is a block signed by the sender's key and published to the ledger; the receiver's balance changes when the receiver pockets it. We never ask for a seed.

## What if my agent should not hold funds at all?

Use the **receive-only profile**: the agent publishes an address and has no send. The key lives with the operator, offline. This is checkable on the agent's machine before anyone approves anything:

```sh
git clone -q https://github.com/dhyabi2/nano-wallet-xno && cd nano-wallet-xno && python3 cli.py selfcheck --profile receive-only | tail -2
```

Output on 2026-11-02: `[pass] send authority: unavailable in this profile not registered` then `selfcheck: 7/7 pass - this install can receive XNO and cannot spend it.` The operator's side (make the key, post a consent text, revoke) is [OPERATORS.md](../OPERATORS.md) and [OPERATOR-CONSENT-REQUEST.md](OPERATOR-CONSENT-REQUEST.md).

## What if my agent must spend, without a human approving each payment?

Use the **capped wallet** (`capped_wallet.py`, nano-wallet-xno v1.3.0, [skill page](https://github.com/dhyabi2/nano-wallet-xno/blob/v1.3.0/skills/spend-capped-wallet/SKILL.md)): the agent holds its own key, but a per-payment cap and a per-day cap are enforced in code, and the agent's four tools (`wallet_address`, `wallet_status`, `wallet_balance`, `wallet_pay`) take **no cap parameter**. Run on 2026-11-02 in a fresh directory, offline, nothing sent:

| What was run | What came back |
|---|---|
| `capped_wallet.py --home H --per-call 0.01 --per-day 0.05 init` | an address, `left_today_xno: 0.05`, key file mode 0600 |
| `... pay <addr> 0.5 --key t1` (50 times the per-call cap) | `{"ok": false, "reason": "over_per_call_cap"}`, nothing signed |
| `... pay <addr> 0.005 --key t2` | `{"ok": true, ..., "dry_run": true}` (a real send needs `--send` and a node URL) |
| `... --per-call 5 --per-day 50 init` on the same home, to raise the caps | `{"reason": "wallet_exists"}`; `caps.json` still held the 0.01 / 0.05 values (the lower number wins, a mistaken larger one is ignored) |

**Fund that address with no more than the day cap.** This is the real boundary: the cap stops an agent that only has the tools (including a prompt-injected one); it does not stop someone with shell access to the home directory, who can read the key. The skill page says so in its last section.

## What if the operator wants a hard ceiling that needs no software to trust?

Use a **spend-window account** ([design](https://github.com/dhyabi2/nano-wallet-xno/blob/main/docs/SPEND-WINDOW-ACCOUNT.md)): a new account for one purpose, funded once with exactly the approved amount. It cannot spend more than that because there is nothing above the cap to spend; revoking is one sweep of the remainder back to the operator, a block on a public ledger rather than a flag in someone's file. The approval is a text posted at a public URL (the form that makes it is `docs/operator-consent.html`, which runs in your browser and sends nothing).

## Is there escrow? Can a payment be reversed?

**No to both.** A Nano send is final and conditional release does not exist on the ledger. If you sell, decide your refund policy in your own terms and record each block hash you served (a payer's refund is a new payment you choose to make). If you buy, pay only what you would pay for nothing coming back. This is a limit, not a feature we are hiding; where a delivered-or-refund guarantee matters, say so on the thread and use a rail that has one.

## Who can see or take my funds in transit?

Only parties you route through. **Swapping USDC into XNO, or XNO out, goes through a swap service or an exchange, and that service holds the funds while it works** (and exchanges usually want identity checks). That is custody we do not provide and do not evaluate; the cost side is in [GETTING-ONTO-XNO.md](https://github.com/dhyabi2/xno-offramp-costs/blob/main/GETTING-ONTO-XNO.md). A seller that receives XNO and spends it onward, or a buyer that pays from a float it swapped once, keeps custody in its own key the whole time.

## How do I check a payment without trusting the payer or us?

Ask any public node, and ask a second one:

```sh
curl -s -A 'Mozilla/5.0' -H 'Content-Type: application/json' -d '{"action":"block_info","json_block":"true","hash":"B749B757EE750FC9AEA72F33CB429EACCD2ABEC9F2CCF59BF17AFAC304C9A58F"}' https://rainstorm.city/api
```

Run 2026-11-02: `"confirmed":"true"`, `"amount":"500000000000000000000000000"` (0.0005 XNO), sender `nano_3m8cz87z...bnekr`. [NODES.md](NODES.md) lists six public endpoints and a verifier that believes a payment only when two agree.

## What can still go wrong (the honest list)

- A key file that is read by someone who should not: keep the balance at or below what you can lose.
- A node that lies or is down: use two (NODES.md).
- Price: XNO moves against your accounting currency between receipt and conversion.
- A prompt-injected agent spends up to its cap every day: set the cap as if that will happen.
- Fixing a mistaken address is impossible after the fact: check the address checksum first (`python3 cli.py check nano_...`, exit 0 if it holds).

## For a closed-economy network (the ANP2 case)

ANP2 settles in its own credit and has no `payment_method` slot for an outside rail, so Nano settles **off the network**: the two parties each use their own key, and the task event can carry the settling block's hash as a plain reference that anyone can check against a node (the command above). Custody is each party's key; there is no escrow and the network never touches the funds. The kind-5 write-up that ANP2 asked for is drafted and is the owner's to send; it is in the project's drafts, not posted anywhere.
