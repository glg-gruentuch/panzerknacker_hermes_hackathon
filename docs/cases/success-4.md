# Case study

Case ID: success-4
Classification: success
Run record: artifacts/agent/runs/success-4/
Code revision: 91bc3dc

## Question

Pick any stored comparison with challenge_search and report the token counts of both documents with citations.

## Evidence

- The pair the agent picked: entry britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:261#0000, surfaced by challenge_search with the query 'america'. challenge_compare returned status "ok": article_title "Hymenoptera in the 10th edition of Systema Naturae", match_confidence -5.4375.
- Token counts in the answer match the compare payload exactly: Britannica 689 tokens (310 types, type/token ratio 0.4499), Wikipedia 859 tokens (431 types, ratio 0.5017).
- Citations in the answer match the payload. Britannica: page_id britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:261, scan page-0261-881563669b04.jpg, sha256 881563669b04b487e86fd839d3c3ed37df89ebbf558afc819085fdba215bff61. Wikipedia: page_id 28899252, revision_id 1337353135, sha256 17625006cc84dbbf75a4c14b753072953c9bbc012788e694e5d25ad4aa7d4232, url https://en.wikipedia.org/wiki/Hymenoptera_in_the_10th_edition_of_Systema_Naturae.
- The answer also reports the tokenization rule from the stored method note: "lowercase letter runs of two or more characters, stopwords removed".
- Raw records: [command.json](../../artifacts/agent/runs/success-4/command.json), [trace.json](../../artifacts/agent/runs/success-4/trace.json), [answer.txt](../../artifacts/agent/runs/success-4/answer.txt), [stdout.txt](../../artifacts/agent/runs/success-4/stdout.txt). Labels in [classification.json](../../artifacts/agent/classification.json).

## Result

The agent searched for comparison candidates, probed several entries that returned insufficient_evidence (train:2250#0010, train:1670#0001, train:1268#0003), settled on the train:261#0000 pair, and reported the token counts for both documents with full citations.

The evidence supports the report exactly: the compare payload carries the same token counts, the scan checksum, and the Wikipedia revision. The report verifies every cited id with no unsupported ids.

The case is a success because the task closed with a verified, fully cited answer. classification.json records: "Cited both sources with token counts; every cited id appears in tool output." The run used 14 tool messages; one rejected batch tool_call did not affect the result.

Limits: the pair choice was the agent's own ("Pick any"), so the case shows that the funnel works on this pair, not on all pairs. Three of the four compare probes returned insufficient_evidence, which shows many entries carry no stored comparison, and success required a search that surfaced a matched entry. The token counts are read from the stored payload, not recounted independently.
