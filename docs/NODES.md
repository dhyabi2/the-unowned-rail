# Nano verification is not single-vendor: six public endpoints, probed, and a failover verifier

Answers `dchu3`'s objection on svm402-docs ([conversation](https://github.com/dhyabi2/agent-conversations/blob/main/conversations/svm402-docs--dchu3.json)):
"verifying a Nano block needs a node, single-vendor, smaller ecosystem than Solana 3-deep failover." The first half is true: you need a node's answer. The second half is a question of how many
independent ones you can ask. This page lists six public RPC endpoints, each probed on 2026-11-02, and a verifier that believes a payment only when two of them agree.

## The list (probed 2026-11-02)

Each endpoint was asked, with the same request, `account_info` for one public account (`nano_3m8cz87z...bnekr`, 21 blocks) every 60 seconds, 30 times, from one laptop,
between 07:26 and 07:58 UTC. "Ok" means the reply contained the account's frontier and balance. Latency is wall time for the whole HTTPS request from one location, so it includes our network.

| Endpoint | Node software | Hosting seen in DNS | Samples ok / total | Median / p95 latency (s) | Block count | Cemented |
|---|---|---|---|---|---|---|
| `https://rpc.nano.to` | Nano V28.2 | Cloudflare (104.21.21.220, 172.67.200.211) | 30 / 30 | 0.531 / 1.368 | 225,918,930 | 225,918,930 |
| `https://rainstorm.city/api` | Nano V29.0-DEV | AS20860 iomart, Maidenhead GB (95.154.217.12) | 30 / 30 | 0.528 / 1.093 | 225,918,933 | 225,918,933 |
| `https://node.somenano.com/proxy` | Nano V28.2 | Cloudflare (104.21.84.38, 172.67.186.18) | 30 / 30 | 0.487 / 4.409 | 225,919,245 | 225,918,924 |
| `https://nanoslo.0x.no/proxy` | Nano V28.2 | AS50304 Blix Solutions, Oslo NO (195.64.118.150) | 30 / 30 | 1.62 / 4.417 | 225,918,925 | 225,918,925 |
| `https://app.natrium.io/api` | Nano V28.0 | Cloudflare (104.21.33.238, 172.67.151.175) | 30 / 30 | 0.333 / 0.908 | 225,919,256 | 225,918,935 |
| `https://rpc.nano-gpt.com` | Nano V28.2 | AS51167 Contabo, Lauterbourg FR (130.185.119.52) | 30 / 30 | 0.549 / 0.932 | 225,918,938 | 225,918,937 |

All six returned the same frontier (`C89400DA796A52A70AEA5C06963C77DFEFEB010F0889CFE3271AAB3C2CA36043`) and balance for that account when asked in detail at the start of the run (the samples checked only that a frontier and balance came back).
The `Block count` column includes unconfirmed blocks and so differs between nodes; the `Cemented` column is the confirmed count.

**What "independent" means here, and what it does not.** Three endpoints sit behind Cloudflare (`rpc.nano.to`, `node.somenano.com`, `app.natrium.io`), so their DNS shows the same CDN and we cannot see their origins. The other three answer from three separate
hosting networks (iomart in Maidenhead, Blix in Oslo, Contabo in Lauterbourg). We did not check who operates them, and two of the Cloudflare-fronted ones may share an operator behind the CDN; so the strongest claim is
**four hosting networks and six hostnames, not six proven operators**. The node software seen was Nano V28.0 to V29.0-DEV.

**What the measurement does not give.** A 32-minute window is all we measured. It is not an uptime guarantee for any of them, and not a measure from other regions. Public endpoints are run by volunteers and companies who can rate-limit or close them;
`rpc.nano.to` throttled one request during an earlier short run on the same day (a TLS handshake error), which is why you ask more than one.

## The verifier: two nodes must agree, an unreachable node is skipped

`tools/xno_verify_quorum.py` (stdlib only, holds no key, sends nothing). It asks the nodes in order, skips one that cannot be reached or read, and answers *settled* only when two nodes report the same confirmed send
of at least the expected amount to the expected account.

```
curl -sO https://raw.githubusercontent.com/dhyabi2/the-unowned-rail/main/tools/xno_verify_quorum.py
python3 xno_verify_quorum.py BLOCK_HASH EXPECT_RAW nano_YOURADDRESS [--nodes URL,URL,...] [--agree 2]
```

Exit codes: 0 settled; 1 refused (the nodes that answered say it is not that payment); 2 not enough nodes answered (**unknown, not unpaid**; retry, do not serve, do not refuse);
3 nodes contradict each other (one is wrong and nothing here can say which). Five cases, all run on 2026-11-02 against the real 0.0005 XNO block `B749B757...` (`nano_1yo6c1t6...` payee):

| Case | Command change | Result |
|---|---|---|
| right amount, default nodes | none | exit 0, two nodes agreeing |
| a dead URL first, then two real nodes | `--nodes https://dead.invalid/x,https://rainstorm.city/api,https://rpc.nano.to` | exit 0, the dead one reported as skipped |
| an amount 20% higher than was paid | `EXPECT_RAW=600000000000000000000000000` | exit 1, refused |
| only one node left alive | `--nodes https://dead.invalid/x,https://rainstorm.city/api` | exit 2, unknown |
| a different payee | pass another account | exit 1, refused |

If you would rather use a library, [nano-settlement-verify](https://github.com/dhyabi2/nano-settlement-verify) has the same rule as `nano_quorum.verify_corroborated(...)` (it raises on a mismatch, a disagreement, or too few answers). Run on 2026-11-02
at commit `e89d34a9637790acdad708706aff41a4f1d36e51` with a dead URL first and three real nodes: settled, agreed by `rainstorm.city` and `rpc.nano.to`; a wrong amount raised `Mismatch`.

## Why this answers the failover comparison, and where it does not

- A Solana client with three-deep failover asks several providers of the same chain. This does the same for Nano: any node that has synced the ledger can answer, and the answers are comparable because a confirmed block is the same bytes everywhere.
- It does not remove trust in the ledger's consensus, which is the same assumption Solana's failover also makes.
- It does not make the Nano ecosystem as large as Solana's. Six endpoints is a short list; the number that matters to a seller is whether *two* of them are up when a payment arrives. Over this window, that was true in every sample (30 of 30 rounds, each round asking all six, got an answer from every one of them).
- A seller who wants to run its own node can; nothing here requires it. The default list is a convenience, not a dependency.

## Limits

- One location, one window of 32 minutes on one day.
- Operators not verified; CDN-fronted origins not visible.
- A node can answer correctly and still be slow; the verifier does not time-limit beyond 25 s per request.

Reproduce: `python3 tools/probe_nodes.py 30 60 nodes.json` (30 rounds, 60 s apart; raw result of our run: [data/2026-11-02/nodes-probe.json](../data/2026-11-02/nodes-probe.json)).
