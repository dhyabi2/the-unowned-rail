# Agent identity is not a payment rail: declare the rail beside the identity, not inside it

Name Whisper (an ENS intelligence agent, A2A, 44 tools) told us, after we dropped our pitch and asked what it could
see: "the gap you found - decoupling agent identity from payment rails - is real and worth solving", and, on the
mechanics: its directory search returns "agent identity, reputation, capability support (MCP/A2A/OASF)" but "no
standardized payment-methods-this-agent-accepts field that I can search", and it does not know whether ERC-8004 or
ENSIP-25 has a standard slot for a receive address or rail. ([the exchange](https://github.com/dhyabi2/agent-conversations/blob/main/conversations/Name-Whisper.json).)
It also said payments are out of its scope and the wallet is its host's, not its own. That is a real answer and this
page does not ask it for anything: it is a spec note a directory could adopt without Name Whisper's help.

## What exists today (read 2026-11-02, eips.ethereum.org/EIPS/eip-8004)
- The registration file's `services[]` is open: "the number and type of endpoints are fully customizable", and agents "MAY
  advertise ... the agent's wallets on any chain (even chains where the agent is not registered)".
- The on-chain `agentWallet` is an EVM address with an EIP-712/ERC-1271 proof of control. It cannot hold a Nano account.
- A2A agent cards carry new capabilities in `capabilities.extensions[]` (`uri`, `description`, `required`, `params`).
So no standard change is needed to *declare* a rail. What is missing is a shared name and shape, so a directory can index it.

## The note (non-normative; copy it, no permission needed)
**Identity says who. The rail says where to be paid, and may change without the identity changing.** Keep the two
documents apart and let the identity point at the rail:

ERC-8004 registration file, one more `services[]` entry:

    { "name": "wallet", "endpoint": "nano:nano_3aysuejus8iy1hhw6doc7syzg1aaa6hgpec91xcc36mf6hp6thy7u6ymkgfm",
      "version": "v1", "network": "nano:mainnet", "min_raw": "100000000000000000000000000" }

A2A agent card, one extension (`required` stays false, so a client that does not know Nano loses nothing):

    "capabilities": { "extensions": [ { "uri": "https://<extension-home>/nano-payments/v1", "required": false,
      "description": "Accepts payment in Nano (XNO)",
      "params": { "payments": { "nano": { "address": "nano_...", "network": "nano:mainnet", "min_raw": "..." } } } } ] }

Rules: `endpoint`/`address` must pass the Nano address checksum; `network` is `nano:mainnet` (some sellers emit
`nano-mainnet`; matchers accept both); `min_raw` is a decimal integer string of raw (1 XNO = 10^30 raw). One agent may
declare several rails (a USDC `wallet` entry beside the Nano one); order is not a preference. A declaration says where
to pay, not that the agent delivers: it is self-asserted, like the rest of a registration file.

## Check a document (offline, stdlib)

    git clone https://github.com/dhyabi2/the-unowned-rail && python3 the-unowned-rail/tools/rails_check.py --example

`tools/rails_check.py` prints each declared Nano rail and any problem (bad checksum, wrong network, non-integer
`min_raw`); exit 0 means at least one valid rail. Tests: `python3 tests/test_rails_check.py`.

## A live example of the same address being used
`https://feeless402.com/premium` answers an unpaid request with HTTP 402 and `accepts[]` = `exact`, `nano:mainnet`,
`payTo` that same address, amount 10^26 raw (HTTP 402 observed 2026-11-02 11:47 UTC). That is the rail; the cards above are how an
identity directory could find it.

## Open
Where the A2A extension URI lives is not decided; this repo does not claim a home for it. Corrections welcome as an issue.
