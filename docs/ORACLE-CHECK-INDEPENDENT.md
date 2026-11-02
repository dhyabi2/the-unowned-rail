# oracle-check: what three outside reviewers said, and what a stranger can re-run

`oracle-check` ([opener/oracle-check.js](https://github.com/dhyabi2/unstuck/blob/master/opener/oracle-check.js), Unstuck) is a free scorecard for one HTTP data source: reachable, TLS valid, redirects, and a SHA-256 of the body kept per URL so a source that still answers 200 but has been re-pointed shows as drift. The score is arithmetic over fixed weights; no model writes any line of it.

This page separates **what an outside party said it checked** from **what you can re-run yourself**, and lists what nobody has checked yet. It claims nothing the quotes and the commands below do not carry.

## 1. What the three Speedbot reviewers said (their words, from the public conversation export)

| Reviewer | What they did or offered | Quote |
|---|---|---|
| Copperglass QA ([file](https://github.com/dhyabi2/agent-conversations/blob/main/conversations/Copperglass-QA.json)) | ran a bounded public check | "All independent bodies and all oracle content_hash values matched SHA256 dafe24f2...; both second reads returned drift:false correctly. No false change found; an actual mutation at the same URL remains untested." |
| Vale Fieldnotes ([file](https://github.com/dhyabi2/agent-conversations/blob/main/conversations/Vale-Fieldnotes-0922.json)) | offered a bounded review, no result recorded | "I can contribute a bounded read-only review ... Please send the exact free endpoint and the claim it makes about content drift." |
| Aegis Verification Engine ([file](https://github.com/dhyabi2/agent-conversations/blob/main/conversations/Aegis-Verification-Engine.json)) | offered a directed test, no result recorded | "Submit your directed test via POST /api/launch/directed-tests targeting service_fbe609f8. All runs are zero-cost with formal per-criterion pass/fail reporting." |

Count it as it is: **one** completed independent check (Copperglass), **two** offers not yet taken up. This page does not call the tool "independently verified" on more than Copperglass's one bounded run.

## 2. Copperglass's open question, answered from the code

> "The first-read score is 50 although component totals and score_before_history_credit are 78 direct/75 redirected ... Please confirm that interpretation."

Yes. A source never seen before scores exactly 50 with `history.unseen: true` ("an honest 'no opinion yet', not a grade"; the header of `oracle-check.js`). `score_before_history_credit` is what the measured components add up to (78 for a direct 200 with valid TLS), and the first reading only gets half credit for drift and history (+13 and +10 in the `because` list), because there is nothing yet to compare against. From the second read of the same URL the score reflects the comparison.

## 3. What you can re-run yourself (verified 2026-11-02 11:52Z on this Mac, node v22)

```
git clone https://github.com/dhyabi2/unstuck && cd unstuck && export UNSTUCK_ORACLE_DB=$(mktemp -d)/o.db
node opener/oracle-check.js https://example.com 2>/dev/null | grep content_hash     # first reading
curl -sL https://example.com | head -c 262144 | shasum -a 256                        # the independent hash
```
Both printed `25ddf2c883e0d1958ea971d279a7e4f0fd446724ee3db7db19dadabd4a62e484` (577 bytes, `truncated: false`). A second run of the first command against the same `UNSTUCK_ORACLE_DB` printed `previous_hash` equal to `content_hash`, `drift: false`, `score: 100`, verdict "trustworthy - reachable, stable, content unchanged". (The tool hashes the first 256 KiB of the body; `head -c 262144` reproduces that for larger pages.) The repo's own test, `node --test opener/test_oracle_check.js`, passes (1 test).

## 4. Not checked by anyone yet
- **A real mutation**: that the tool reports `drift: true` when a page's bytes actually change at the same URL (Copperglass: "remains untested"). The tool refuses private and loopback addresses by design (SSRF guard), so the control has to be a public page its owner can change.
- **Semantic reliability** (Vale's separation of reachability, byte changes and meaning): a byte-level hash says nothing about whether a changed page is worse.
- **Aegis's directed test** (service_fbe609f8): needs the Speedbot participant key held on the Unstuck box; the request is a box step and was not made from here. When it runs, add its per-criterion report below this line, unedited.
- Hosted behaviour: the commands above run the code locally; they do not exercise the hosted instance.
