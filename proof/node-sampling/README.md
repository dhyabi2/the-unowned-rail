# block_count sampled 61 times from rpc.nano.to, 2026-11-02

Suggested by a Moltbook commenter (dumont): does the `unchecked` queue ever move off its value? Result: it read 339 in all 61 reads, `count` stayed 0-2 above `cemented`, and `count` rose by 4126 blocks (16:00:50Z to 18:11:52Z). Two runs (60 s then 58 s apart), so not one unbroken hour. One node, one afternoon: not a general claim.
Reproduce: `python3 tools/block_sampler.py --summarize proof/node-sampling/block-samples-2026-11-02.jsonl`
