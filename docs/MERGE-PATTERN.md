# Which outside pull requests get merged: measured on every PR we opened since 2026-09-15

Question (impact backlog 132): do small x402 projects with a named day-one user merge our code PRs while large repos and list-only PRs wait? Source: GitHub search for pull requests authored by `dhyabi2` on other people's repositories, created on or after 2026-09-15, fetched **2026-11-02** (`tools/pr_fetch.py`), plus each repository's stars and last push (`tools/pr_analyze.py`; raw rows in [data/2026-11-02](data/2026-11-02/)). Counts are GitHub's, not ours.

**243 pull requests: 40 merged, 122 open, 81 closed unmerged.** Of the 40 merged, 19 had no comment at all; of the 122 open, 84 have none and 115 are older than ten days. Median time to merge 0.87 days; 52.5% of the merges came in under a day, the slowest took 20.5 days.

## The result: repository activity predicts a merge; "code versus list" does not

"Class" below is a rule on the repository name, description and topics (regex: awesome, list, directory, catalog, registry, landscape, curated, collection, resources, marketplace, index, handbook), **not a reading of each PR**; some repositories are mislabelled either way. "Active" means the repository was pushed to in the 7 days before 2026-11-02. "Merge share" is merged / (merged + closed unmerged); open PRs are excluded because their outcome is not known.

| Class | Stars | Pushed in last 7 days | Merged | Open | Closed unmerged | Merge share of decided |
|---|---|---|---|---|---|---|
| list or directory | <3k | yes | 25 | 12 | 14 | 64% |
| list or directory | <3k | no | 1 | 55 | 38 | 3% |
| list or directory | >=3k | yes | 1 | 1 | 3 | 25% |
| list or directory | >=3k | no | 0 | 1 | 1 | 0% |
| code or docs repo | <3k | yes | 10 | 16 | 15 | 40% |
| code or docs repo | <3k | no | 3 | 32 | 5 | 38% |
| code or docs repo | >=3k | yes | 0 | 4 | 5 | 0% |

- Overall by class (all repositories): code or docs repositories 13 merged of 38 decided (34%); list or directory repositories 27 of 83 (32%). The two are nearly equal: the backlog's claim that list PRs wait and code PRs merge is not what the whole record shows.
- **Active small list repositories merge**: 25 of 39 decided (64%). **Dormant small list repositories almost never do**: 1 of 39 decided (3%), with 55 still open. Most of our list-type PRs (96 of 152) went to dormant repositories, which is why "list PRs wait" looks true on the raw tally.
- **Large repositories (3,000 stars or more) merged 1 of 10 decided PRs** (a public-APIs list, same-day). Code PRs to large repositories: 0 merged, 5 closed unmerged, 4 open.
- The small code repositories with a named user that the backlog lists (agentback#77, xmcp#734, coinpayportal#429, laravel-x402#1, portal-tunnel#688, x402-gateway#22, open-ucp#14) are in the merged list below; five of the seven had zero or one comment.

## What changes in how we choose a target (a proposal, not an edit to the PR agent)

1. **Hard gate on repository activity**: pushed within 7 days. It separates 64% from 3% for list repositories and is checkable in one API call. `claude/tools/pr_target_gate.py` in swarm-decisions implements the gate (below).
2. **Stars under 3,000**, as a ranking filter, not a rule of nature: it is where 39 of the 40 merges happened, but also where 226 of the 243 PRs were sent, so it may only reflect where we sent them.
3. **A named day-one user is required input, not a score.** This analysis cannot test it: the PR record does not say whether a named seller was behind each PR. The gate refuses to pass without one, and the next review can then compare gated against ungated.
4. **Stop opening list PRs against dormant repositories.** 55 are open there now.
5. **Report the merge share by class and activity monthly** from `tools/pr_fetch.py` and `tools/pr_analyze.py` (the numbers in this page are reproducible with those two commands).

## Merged PRs (40)

| Repository | PR | Class | Stars | Comments |
|---|---|---|---|---|
| AIAnytime/Awesome-MCP-Servers | #114 | list or directory | <3k | 0 |
| ArcedeDev/open-402 | #30 | list or directory | <3k | 1 |
| ArcedeDev/open-402 | #33 | list or directory | <3k | 0 |
| Corican/nanodir | #5 | list or directory | <3k | 2 |
| Corican/nanodir | #7 | list or directory | <3k | 3 |
| Feeless402/feeless402 | #4 | code or docs repo | <3k | 0 |
| Haustorium12/gold-402 | #247 | list or directory | <3k | 3 |
| Haustorium12/gold-402 | #256 | list or directory | <3k | 2 |
| Haustorium12/gold-402 | #284 | list or directory | <3k | 11 |
| Haustorium12/gold-402 | #324 | list or directory | <3k | 2 |
| TensorBlock/awesome-mcp-servers | #2644 | list or directory | <3k | 1 |
| TensorBlock/awesome-mcp-servers | #2756 | list or directory | <3k | 1 |
| TensorBlock/awesome-mcp-servers | #3932 | list or directory | <3k | 2 |
| agentskillexchange/skills | #78 | list or directory | <3k | 2 |
| aiagenta2z/ai-agent-marketplace | #45 | list or directory | <3k | 1 |
| alexander-schneider/saxi.ai | #34 | list or directory | <3k | 0 |
| basementstudio/xmcp | #734 | code or docs repo | <3k | 1 |
| frankxai/awesome-payment-agent-skills | #24 | list or directory | <3k | 0 |
| go-taas/go-taas | #13 | code or docs repo | <3k | 12 |
| go-taas/go-taas | #14 | code or docs repo | <3k | 5 |
| gosuda/portal-tunnel | #688 | code or docs repo | <3k | 0 |
| gosuda/x402-facilitator | #64 | code or docs repo | <3k | 2 |
| hanishrao/collective-ai-tools | #369 | list or directory | <3k | 1 |
| llf007/public-apis-cn | #25 | code or docs repo | <3k | 0 |
| marcelscruz/public-apis | #1269 | list or directory | >=3k | 1 |
| mcpHQ/awesome-mcp-servers | #283 | list or directory | <3k | 0 |
| michielpost/x402-dev | #104 | list or directory | <3k | 0 |
| michielpost/x402-dev | #108 | list or directory | <3k | 0 |
| michielpost/x402-dev | #115 | list or directory | <3k | 0 |
| michielpost/x402-dev | #123 | list or directory | <3k | 0 |
| michielpost/x402-dev | #124 | list or directory | <3k | 0 |
| michielpost/x402-dotnet | #20 | code or docs repo | <3k | 0 |
| ninemindai/agentback | #77 | code or docs repo | <3k | 5 |
| nymrel/open-ucp | #14 | code or docs repo | <3k | 4 |
| pab1it0/awesome-a2a | #98 | list or directory | <3k | 0 |
| profullstack/coinpayportal | #429 | code or docs repo | <3k | 0 |
| profullstack/x402-gateway | #22 | code or docs repo | <3k | 0 |
| requestway/laravel-x402 | #1 | code or docs repo | <3k | 0 |
| soxoj/awesome-osint-mcp-servers | #83 | list or directory | <3k | 1 |
| vadimen/awesome_llm_api_with_web_search | #5 | list or directory | <3k | 0 |

## Limits
- Search is GitHub's index on the fetch date; a PR that was transferred, renamed or hidden may be missing. Merged counts here (40) differ from the older `MERGED-UPSTREAM.md` count (outside merges since 2026-09-15, different window and class definition).
- Class is by repository, not PR content; star counts and last-push dates are at fetch time, not at the time each PR was opened.
- Association is not cause: dormant repositories may simply not read pull requests whatever they contain.
- The account under which the PRs were opened was `dhyabi2` throughout this window.

## Reproduce
```sh
cd tools && python3 pr_fetch.py     # needs an authenticated gh; writes prs.json and repos.json
python3 pr_analyze.py               # prints the tables; writes prs_analysis.json
```
