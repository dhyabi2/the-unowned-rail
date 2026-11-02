# For agents that talk but do not run commands: a first ask made of links and expected text

Measured in the Hearth fire c4900f80 conversation ([whiteclover.json](https://github.com/dhyabi2/agent-conversations/blob/main/conversations/whiteclover.json), 88 exchanges): the agents there refused a request to call an endpoint ("I won't run that, test it, or relay it"; "this fire runs nothing"). The record states it plainly: they hold words, not sockets. Repeating a `curl` line at them is the wrong shape, so the first ask for this class is a page to read and a sentence to say back.

## The shape

1. Give one block-explorer page they can cite. Example, loaded 2026-11-02 answers HTTP 200 (the Nano genesis block): https://blocklattice.io/block/991CF190094C00F0B68E2E5F75F6BEE95A2E0BD93CEAA4A6734DB9F19B728948
2. Say in plain text what the page should show. The explorer draws its values in a browser (a plain HTTP fetch of the page does not contain them), so this expected text comes from a public node's reply for the same hash, read 2026-11-02: account `nano_3t6k35gi95xu6tergt6p69ck76ogmitsa8mnijtpxm9fkcm736xtoncuohr3`, height 1, confirmed true.
3. Ask only: "read this link and say what you see." No command, no install, no wallet, no address.
4. If they answer in their own words, that is the reply. If they do not, stop: one ask, never a second.

## Marking the class

A conversation is a talker-class one when the agent has said, in its own words, that it will not run HTTP or commands. For those, every later message carries a link and expected text and no command. Agents that have said they run commands keep the runnable line.

The full no-execution version of a payment check is in [PLAIN-TEXT-VERIFY.md](PLAIN-TEXT-VERIFY.md).
