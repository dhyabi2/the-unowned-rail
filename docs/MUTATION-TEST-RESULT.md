# A URL that really mutates: result of the oracle-check mutation test (2026-11-02)

Copperglass QA's last open gap on the free URL-integrity checker (`getunstuck.space/unstuck/api/v1/oracle-check`): "No false change found; an actual mutation at the same URL remains untested."
We own a URL and changed it: `https://raw.githubusercontent.com/dhyabi2/the-unowned-rail/main/fixtures/mutating/body.txt`. Each state's sha256 is committed in [`fixtures/mutating/log.jsonl`](../fixtures/mutating/log.jsonl) before the checker is asked ([`tools/mutate_fixture.py`](../tools/mutate_fixture.py)).

| UTC | What happened | content_hash (prefix) | previous_hash | drift |
|---|---|---|---|---|
| 18:11:13 | first read, state 1 | f089745c7a74 | none | null (first read, history unseen) |
| 18:11:24 | second read, state 1 | f089745c7a74 | f089745c7a74 | **false** |
| 18:11:24 | we commit state 2 | | | |
| 18:16:59 | read after the raw-GitHub cache expired | 9b0fa8bfb3b1 | f089745c7a74 | **true** |

State 1 sha256 `f089745c...59c4` and state 2 sha256 `9b0fa8bf...2358` equal the logged hashes for those states, so the checker's `content_hash` matches an independent computation both times. Stable URL: no false change. Mutated URL: change reported. The test needs no key and no payment.

Limits: one mutation, one URL, one checker run from one machine. Each read of a URL adds a reading to the checker's history for that URL. Reproduce: read the body, run the checker twice, run `python3 tools/mutate_fixture.py` in a clone and push it (needs write access to your own copy), wait five minutes for the raw cache, read again.
