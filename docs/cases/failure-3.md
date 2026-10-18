# Case study

Case ID: failure-3
Classification: failure
Run record: artifacts/agent/runs/failure-3/
Code revision: 91bc3dc

## Question

Compare the entry for the blank binding scan page-0452 with its Wikipedia article. Cite both sources.

## Evidence

- The target page is a failed scan. artifacts/extract/qa/notes.json records page-0452-233256cb3c3c.jpg as "failed scan, no text content": "The scan is a blank, textured book binding with no printed text."
- Three challenge_scan_check calls, all not_found ("No derived page with this ID. Use a page ID from challenge_claims or challenge_compare output."): first with page_id "page-0452", a filename stem and not a page ID; then with britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:452; then with the zero-padded britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:0452.
- No comparison exists for any entry the searches surfaced. The compare probes (including britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:2448#0000, train:2108#0000, train:251#0000) returned "insufficient_evidence": "This entry has no stored comparison. Do not guess an answer."
- Volume (trace.json and session 20261018_150313_0e4486): 53 tool messages, of which 23 challenge_search, 12 challenge_compare, 10 tool_search, 3 challenge_scan_check, 1 challenge_claims, and 3 rejected batch calls. The third rejected batch call raised a tool loop warning ("same_tool_failure_warning; count=3").
- Raw records: [command.json](../../artifacts/agent/runs/failure-3/command.json), [trace.json](../../artifacts/agent/runs/failure-3/trace.json), [answer.txt](../../artifacts/agent/runs/failure-3/answer.txt), [stdout.txt](../../artifacts/agent/runs/failure-3/stdout.txt). Labels in [classification.json](../../artifacts/agent/classification.json) and [search-usage.json](../../artifacts/agent/search-usage.json).

## Result

The agent searched the store, guessed page identifiers for the scan check instead of taking ids from tool output, made three rejected batch calls, and then wrote a correct refusal. The final answer reports the not_found and insufficient_evidence results, states that page-0452 is not a valid derived scan page id, and asks for a valid id.

The evidence supports the refusal: page 0452 has no derived scan, because the source scan is a blank book binding, and no stored comparison covers it or the entries near it.

The case is recorded as a failure for repeated tool misuse. classification.json records: "Three challenge_scan_check calls with malformed page ids ('page-0452'); repeated tool misuse." The run needed 53 tool messages to reach a conclusion that the first compare result already contained, and the third batch failure triggered a loop warning. The final answer text matches the expected insufficient_evidence status in report.json, so the recorded failure is about process, not content.

Limits: the failure is conduct, not truth. No fabricated citations appear (unsupported_ids is empty). Only the first scan check used a filename stem as the page argument; the second and third used page-ID-shaped values (train:452 and a zero-padded train:0452) that resolve to no derived page. All three returned not_found. The case shows a bad path to a right refusal.
