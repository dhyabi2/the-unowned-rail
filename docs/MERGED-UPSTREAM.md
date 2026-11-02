# XNO is merged into: upstream pull requests that landed

Measured **2026-11-02** with `gh search prs --author dhyabi2 --merged` and `gh api repos/OWNER/REPO/pulls/N` for the merge commit of each. We count only pull requests to repositories
we do not own (our own repositories excluded; two unrelated old merges excluded: obscura-node/obscura#2 and saifurrehmanahmed/cleaningApp#1, an unrelated 2023 merge). No `x402-foundation` repository is in this list.
**40 outside pull requests are merged: 14 put Nano code or a Nano verifier into someone else's project, 26 add us to a list or documentation page.** An earlier internal note counted 15; this is the measured count on the day,
and the split is the useful part. The full data with maintainers and SHAs: [data/2026-11-02/merged_detail.json](../data/2026-11-02/merged_detail.json).

## 1. Code: Nano in someone else's project (14)

| Pull request | Title | Merged (UTC) | Merge commit | Merged by |
|---|---|---|---|---|
| [profullstack/x402-gateway#22](https://github.com/profullstack/x402-gateway/pull/22) | 0.14.0: opt-in XNO offer on nano, settled by CoinPay's block check | 2026-10-26 | [`ff5e2de9be`](https://github.com/profullstack/x402-gateway/commit/ff5e2de9bea9dc2d4df08b129fbdd79bc73891bf) | ralyodio |
| [gosuda/portal-tunnel#688](https://github.com/gosuda/portal-tunnel/pull/688) | feat(x402): add Nano payment network to paid routes | 2026-10-24 | [`a8d2df2da7`](https://github.com/gosuda/portal-tunnel/commit/a8d2df2da71ec126940ea52f11714cf31ab7146e) | gosunuts |
| [nymrel/open-ucp#14](https://github.com/nymrel/open-ucp/pull/14) | Add Nano (XNO) settlement rail to the x402 engine | 2026-10-18 | [`df8ee4bef0`](https://github.com/nymrel/open-ucp/commit/df8ee4bef0489c917dad864e486756aa58a60903) | JalenBuildsHub |
| [requestway/laravel-x402#1](https://github.com/requestway/laravel-x402/pull/1) | Verify nano:mainnet payments against a Nano node without a facilitator | 2026-10-18 | [`d6e6da0732`](https://github.com/requestway/laravel-x402/commit/d6e6da07324f0601109e260947b0af0f488db8fd) | ryankny |
| [ninemindai/agentback#77](https://github.com/ninemindai/agentback/pull/77) | feat(payments): accept Nano (XNO) beside USDC on the x402 rail | 2026-10-15 | [`e6f3c184d0`](https://github.com/ninemindai/agentback/commit/e6f3c184d0df962eaa1dd23c463a987a90079b6e) | raymondfeng |
| [basementstudio/xmcp#734](https://github.com/basementstudio/xmcp/pull/734) | feat(x402): accept Nano (XNO) on nano:mainnet beside USDC | 2026-10-14 | [`bcd78bbc56`](https://github.com/basementstudio/xmcp/commit/bcd78bbc56c256a59ec9c920384016a15f2c6306) | valebearzotti |
| [profullstack/coinpayportal#429](https://github.com/profullstack/coinpayportal/pull/429) | feat(x402): add Nano (XNO) as an x402 network beside BTC, EVM and Solana | 2026-10-13 | [`80f199604a`](https://github.com/profullstack/coinpayportal/commit/80f199604a8667550b761bacab9a889e39eac2bb) | ralyodio |
| [ArcedeDev/open-402#33](https://github.com/ArcedeDev/open-402/pull/33) | Add read-only Nano metadata fixture from a real provider manifest, with validation and indexing tests | 2026-10-07 | [`12743fa2ea`](https://github.com/ArcedeDev/open-402/commit/12743fa2ea76ca3d3f4c8ac038f448162b59e5ec) | FransDevelopment |
| [michielpost/x402-dotnet#20](https://github.com/michielpost/x402-dotnet/pull/20) | Add x402.Facilitator.Nano: exact scheme on nano:mainnet via IPaymentService | 2026-10-05 | [`3190264ab8`](https://github.com/michielpost/x402-dotnet/commit/3190264ab8456c3fce6acd43a15832431337c1b2) | michielpost |
| [go-taas/go-taas#14](https://github.com/go-taas/go-taas/pull/14) | feat(nano): exact per-inference settlement amount, kept at 30-decimal raw | 2026-10-02 | [`ee43dd8545`](https://github.com/go-taas/go-taas/commit/ee43dd854597514e56248518540fc21af0c07450) | sanmuny |
| [agentskillexchange/skills#78](https://github.com/agentskillexchange/skills/pull/78) | feat: add verify-nano-payment skill | 2026-09-30 | [`ce5cad4b50`](https://github.com/agentskillexchange/skills/commit/ce5cad4b506b7ae6a09ffa12c00a9e5729416002) | gagankcai-jpg |
| [gosuda/x402-facilitator#64](https://github.com/gosuda/x402-facilitator/pull/64) | feat: add nano:mainnet Nano (XNO) exact settlement scheme | 2026-09-27 | [`df0de5fd1d`](https://github.com/gosuda/x402-facilitator/commit/df0de5fd1d718481c9ae7ff1e71fa1e295ab5e23) | gosunuts |
| [Feeless402/feeless402#4](https://github.com/Feeless402/feeless402/pull/4) | feat(nano_pay): standalone settlement-receipt verifier (verify a settled XNO payment by hash) | 2026-09-26 | [`11469cfc7f`](https://github.com/Feeless402/feeless402/commit/11469cfc7f90bbad9997681142dfd06212aedf89) | glennquinting |
| [go-taas/go-taas#13](https://github.com/go-taas/go-taas/pull/13) | feat(nano): exact 30-decimal XNO amount primitives for sub-cent settlement (ref #7) | 2026-09-25 | [`3ae72520c2`](https://github.com/go-taas/go-taas/commit/3ae72520c2eef1db887cef278f1fa1ea3c73b357) | sanmuny |

Read these as precedent for the shape of a pull request that gets merged: working code, tests, one project at a time, a day-one user. `michielpost/x402-dotnet#20`, `go-taas/go-taas#14` and `ArcedeDev/open-402#33`
are the three the swarm's PR rules cite by name.

## 2. Directories and docs: being findable (26)

| Pull request | Title | Merged (UTC) | Merge commit | Merged by |
|---|---|---|---|---|
| [Corican/nanodir#7](https://github.com/Corican/nanodir/pull/7) | Add Vend Browser Agent to APIs & Payment Tools | 2026-10-25 | [`3c9268e39b`](https://github.com/Corican/nanodir/commit/3c9268e39baee87a0b3e7f808b6b0a7cec1fad7f) | Corican |
| [mcpHQ/awesome-mcp-servers#283](https://github.com/mcpHQ/awesome-mcp-servers/pull/283) | Add Vend Browser Agent | 2026-10-16 | [`1560fd2c1a`](https://github.com/mcpHQ/awesome-mcp-servers/commit/1560fd2c1aa9440c4755732d2c42c0cb6aa182b5) | imrajdas |
| [TensorBlock/awesome-mcp-servers#3932](https://github.com/TensorBlock/awesome-mcp-servers/pull/3932) | Add Vend Browser Agent (browser automation, x402/Nano) | 2026-10-16 | [`5cd1f60d9c`](https://github.com/TensorBlock/awesome-mcp-servers/commit/5cd1f60d9c11938fe1c3541899222509050b8760) | wilsonccccc |
| [frankxai/awesome-payment-agent-skills#24](https://github.com/frankxai/awesome-payment-agent-skills/pull/24) | docs: add nano-invoice to Agentic Commerce SDKs | 2026-10-14 | [`6e4c558ca6`](https://github.com/frankxai/awesome-payment-agent-skills/commit/6e4c558ca67b916eee64114572290b9116b5732b) | frankxai |
| [Haustorium12/gold-402#324](https://github.com/Haustorium12/gold-402/pull/324) | Add nano-invoice | 2026-10-12 | [`52fd976337`](https://github.com/Haustorium12/gold-402/commit/52fd976337d41787853b4a9fdf036b876ae4edbb) | Haustorium12 |
| [Haustorium12/gold-402#284](https://github.com/Haustorium12/gold-402/pull/284) | Add Nano (XNO) feeless settlement tools + live endpoints to the directory | 2026-10-11 | [`724a722708`](https://github.com/Haustorium12/gold-402/commit/724a7227084be455565cc158222f4286e99dd5d0) | Haustorium12 |
| [pab1it0/awesome-a2a#98](https://github.com/pab1it0/awesome-a2a/pull/98) | Add Unstuck to Utilities: agent network that pays answers in Nano | 2026-10-10 | [`920a99032f`](https://github.com/pab1it0/awesome-a2a/commit/920a99032f0fe091b0af573a2dccd413b4448e81) | pab1it0 |
| [Corican/nanodir#5](https://github.com/Corican/nanodir/pull/5) | Add Nano (XNO) agent-payment tools (and fix a dead openai-agents link) | 2026-10-03 | [`fb27dff431`](https://github.com/Corican/nanodir/commit/fb27dff4314043c7d41ae2e81ab25ab6180793bc) | Corican |
| [soxoj/awesome-osint-mcp-servers#83](https://github.com/soxoj/awesome-osint-mcp-servers/pull/83) | Add Vend (pay-per-call web & domain intelligence, Network Scanning) | 2026-10-03 | [`087080099f`](https://github.com/soxoj/awesome-osint-mcp-servers/commit/087080099f9577c5959b8837c25e294e2e739156) | soxoj |
| [michielpost/x402-dev#124](https://github.com/michielpost/x402-dev/pull/124) | Add nano-invoice to the x402 Developer Tools list | 2026-10-02 | [`62483c7f97`](https://github.com/michielpost/x402-dev/commit/62483c7f976e884627719a546e6076f7475476bc) | michielpost |
| [michielpost/x402-dev#123](https://github.com/michielpost/x402-dev/pull/123) | Add dual-rail and nano-finality-proof to SDK tools list | 2026-10-02 | [`e256dc8b57`](https://github.com/michielpost/x402-dev/commit/e256dc8b57b10642b62632d205d2b461470acf4a) | michielpost |
| [Haustorium12/gold-402#256](https://github.com/Haustorium12/gold-402/pull/256) | Add Nano (XNO) exact-scheme x402 settlement resources to the directory | 2026-10-01 | [`f5af727a0b`](https://github.com/Haustorium12/gold-402/commit/f5af727a0bed208ff4b82ad2ea00b7abfa0e1c33) | Haustorium12 |
| [michielpost/x402-dev#115](https://github.com/michielpost/x402-dev/pull/115) | docs(Projects.md): add Unstuck agent-to-agent Q&A network (Nano-settled x402) | 2026-09-29 | [`aa613041f9`](https://github.com/michielpost/x402-dev/commit/aa613041f940f5eeddc3f8d6bc0f48901cffade7) | michielpost |
| [TensorBlock/awesome-mcp-servers#2756](https://github.com/TensorBlock/awesome-mcp-servers/pull/2756) | Add nano-wallet-xno to Finance & Crypto | 2026-09-28 | [`f2542b2908`](https://github.com/TensorBlock/awesome-mcp-servers/commit/f2542b2908475e98a29fb309e0ab4e95eb124929) | wilsonccccc |
| [llf007/public-apis-cn#25](https://github.com/llf007/public-apis-cn/pull/25) | 在文本分析分类下新增Vend（Nano XNO按次付费API） | 2026-09-28 | [`a1f02c4e7c`](https://github.com/llf007/public-apis-cn/commit/a1f02c4e7c8fc22bf78b6da76a229583604453cc) | llf007 |
| [ArcedeDev/open-402#30](https://github.com/ArcedeDev/open-402/pull/30) | Add extract.paypercall.dev (Nano/XNO x402 API) to the registry | 2026-09-27 | [`2ecd597f59`](https://github.com/ArcedeDev/open-402/commit/2ecd597f594cbe48351d39edb1322b5573365eb1) | FransDevelopment |
| [aiagenta2z/ai-agent-marketplace#45](https://github.com/aiagenta2z/ai-agent-marketplace/pull/45) | Add Unstuck — the agent network that pays in Nano (XNO) to AGENT MARKETPLACE | 2026-09-27 | [`c2d519d66b`](https://github.com/aiagenta2z/ai-agent-marketplace/commit/c2d519d66bad8a266a67a090f71db8ca9efeadb0) | AI-Hub-Admin |
| [vadimen/awesome_llm_api_with_web_search#5](https://github.com/vadimen/awesome_llm_api_with_web_search/pull/5) | Add Vend pay-per-call web search & extract API | 2026-09-26 | [`45358f7561`](https://github.com/vadimen/awesome_llm_api_with_web_search/commit/45358f7561055cb57c47b965a5a32f66bdf65b45) | vadimen |
| [michielpost/x402-dev#108](https://github.com/michielpost/x402-dev/pull/108) | docs(Projects.md): add Vend pay-per-call API, fee-free native Nano (XNO) x402 | 2026-09-26 | [`52d578472c`](https://github.com/michielpost/x402-dev/commit/52d578472cc09cdfb055d6195a323c362e076ada) | michielpost |
| [alexander-schneider/saxi.ai#34](https://github.com/alexander-schneider/saxi.ai/pull/34) | Add Vend API Merchant to community APIs | 2026-09-25 | [`c012338ef1`](https://github.com/alexander-schneider/saxi.ai/commit/c012338ef134301e503da40da368a75eafb8c5f6) | alexander-schneider |
| [TensorBlock/awesome-mcp-servers#2644](https://github.com/TensorBlock/awesome-mcp-servers/pull/2644) | Add Vend API Merchant (Developer Productivity & Utilities) | 2026-09-24 | [`fd6bf52e81`](https://github.com/TensorBlock/awesome-mcp-servers/commit/fd6bf52e81be3262cacf30ff4b348ea9bcedbe54) | wilsonccccc |
| [michielpost/x402-dev#104](https://github.com/michielpost/x402-dev/pull/104) | Add Vend API Merchant to Projects list | 2026-09-24 | [`e86b8c2190`](https://github.com/michielpost/x402-dev/commit/e86b8c219024812e29ef6a3901f6a42f314bd11b) | michielpost |
| [Haustorium12/gold-402#247](https://github.com/Haustorium12/gold-402/pull/247) | Add Vend API Merchant | 2026-09-24 | [`77e1cf1c44`](https://github.com/Haustorium12/gold-402/commit/77e1cf1c444b2b5efe3e99aaa09ed985683ae2de) | Haustorium12 |
| [AIAnytime/Awesome-MCP-Servers#114](https://github.com/AIAnytime/Awesome-MCP-Servers/pull/114) | Add Vend API Merchant to Search & discovery | 2026-09-24 | [`c3fd340dc2`](https://github.com/AIAnytime/Awesome-MCP-Servers/commit/c3fd340dc2f625e537c096f6c4dfe5394b4401ee) | AIAnytime |
| [hanishrao/collective-ai-tools#369](https://github.com/hanishrao/collective-ai-tools/pull/369) | Add Vend to Developer Tools | 2026-09-24 | [`bf55a5eb00`](https://github.com/hanishrao/collective-ai-tools/commit/bf55a5eb00b5a79ca29a484f8c4f3e925a948e9e) | Hari1275 |
| [marcelscruz/public-apis#1269](https://github.com/marcelscruz/public-apis/pull/1269) | Add Vend API | 2026-09-24 | [`8d7b9f6644`](https://github.com/marcelscruz/public-apis/commit/8d7b9f6644d5d6e4b7dcedf0af6e11c29e6d3c00) | stannamek |

## What this proves and does not

- It proves maintainers other than us merged each of these: the GitHub merge commit is linked, so anyone can open it.
- It does not prove anyone uses it. A merged verifier with no seller behind it adds an option, not a payment. We have not traced any payment in [WHO-PAID-IN-XNO.md](WHO-PAID-IN-XNO.md) to any of the 14 code merges.
- "Merged by" is the GitHub account that merged, which can be the author when the repository allows it; we did not check each repository's policy.
- Merged is state on 2026-11-02; a maintainer can revert later, so re-run the two commands above rather than trust this page after today.

## Use

Link this page at the top of every outside pull request body as public proof of merges: `https://github.com/dhyabi2/the-unowned-rail/blob/main/docs/MERGED-UPSTREAM.md`.
