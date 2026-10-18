# Case study

Case ID: success-1
Classification: failure
Run record: artifacts/agent/runs/success-1/
Code revision: 91bc3dc

## Question

Use challenge_search to find the stored comparison for the page with running head SHIP-BUILDING, then use challenge_compare. List two vocabulary differences between the 1768 Britannica text and the Wikipedia article. Cite both sources.

## Evidence

- The SHIP-BUILDING page resolves to entry britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:13#0000. challenge_compare on that entry, and on the suffixes #0001 through #0005, returned status "insufficient_evidence": "This entry has no stored comparison. Do not guess an answer." No comparison exists for this page.
- Two challenge_scan_check calls on page britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:13 with the quote "SHIP-BUILDING" both returned not_found: "The quote is not in any text block with a bounding box on this page."
- Two malformed batch attempts failed with: "Local tools require one entry per tool_call; mixed and multi-local batches are not supported."
- Volume (trace.json and session 20261018_145739_f633d5): 108 tool messages, of which 87 challenge_search calls, 13 challenge_compare, 2 challenge_scan_check, 1 challenge_claims, 2 tool_search, 1 tool_describe, and 2 rejected batch calls. search-usage.json records the 87 searches, all served by the API.
- Answer check: the final answer says it "verified with challenge_claims and multiple paragraph suffixes (#0001 through #0005)". Those calls exist. The session shows one challenge_claims call on britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:13#0000, which returned "insufficient_evidence" ("This entry has no stored claim alignment. Do not guess an answer."), and challenge_compare calls on britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:13#0001, #0002, #0003, #0004, and #0005, all returning the same insufficient_evidence result. The claim checks out; the failure here is not fabrication.
- Raw records: [command.json](../../artifacts/agent/runs/success-1/command.json), [trace.json](../../artifacts/agent/runs/success-1/trace.json), [answer.txt](../../artifacts/agent/runs/success-1/answer.txt), [stdout.txt](../../artifacts/agent/runs/success-1/stdout.txt). Labels in [classification.json](../../artifacts/agent/classification.json) and [search-usage.json](../../artifacts/agent/search-usage.json).

## Result

The agent searched the store dozens of times with reworded shipbuilding queries, probed many entry ids, ran the suffix and claims checks, made two scan-check attempts, and then refused to list vocabulary differences because the page has no stored comparison.

The evidence supports the refusal: the requested comparison does not exist, and the answer invents nothing. The claimed verification calls exist in the session and all returned the same insufficient_evidence result. An incidental probe of britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:1818#0000 returned a stored comparison (article "Oregonite"), so the store is not empty in general; it holds nothing for the SHIP-BUILDING entry.

The case is recorded as a failure for process. classification.json records: "108 tool calls chasing an unsatisfiable premise; two challenge_scan_check calls with unusable quotes." The run spent its full budget on variations of one query and reached the dead end only at the end.

Limits: the failure is conduct and efficiency, not the truth of the answer. No fabricated citations appear (unsupported_ids is empty), and the final text is a correct refusal. The two scan checks used a running head as the quote, which cannot resolve to a bboxed text block, so they add nothing. The case does not show the tools failing; it shows the run failing to stop.
