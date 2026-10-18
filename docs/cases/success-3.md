# Case study

Case ID: success-3
Classification: success
Run record: artifacts/agent/runs/success-3/
Code revision: 91bc3dc

## Question

Find the entomology entry in the stored comparisons with challenge_search. Report which terms are most distinctive to the historical Britannica text. Cite the source records.

## Evidence

- The literal query 'entomology' returned no stored match (challenge_search, status "insufficient_evidence", "No stored entry or paragraph matches the query terms."). The query 'insect' returned the pair: entry britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:261#0000 (score 7.230716228485107), a Linnaean natural-history passage on insects, paired with the Wikipedia article "Hymenoptera in the 10th edition of Systema Naturae".
- challenge_compare on the entry returned status "ok" with match_confidence -5.4375. Britannica side: page_id britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:261, scan page-0261-881563669b04.jpg, sha256 881563669b04b487e86fd839d3c3ed37df89ebbf558afc819085fdba215bff61. Source excerpt: "Aptera a great height; to accomplish which, they climb up some eminence, and are walked about by the winds, filling the air with their threads."
- Wikipedia side: page_id 28899252, revision_id 1337353135, text_sha256 17625006cc84dbbf75a4c14b753072953c9bbc012788e694e5d25ad4aa7d4232, url https://en.wikipedia.org/wiki/Hymenoptera_in_the_10th_edition_of_Systema_Naturae.
- Distinctive terms reported, with counts (Britannica / Wikipedia) and log-odds, all matching the compare payload: native 17/0 (3.5626), marked 13/0 (3.3112), europe 12/0 (3.2371), legs 10/0 (3.0701), abdomen 10/0 (3.0701), brown 9/0 (2.9748), oval 8/0 (2.8694), white 7/0 (2.7516), colour 7/0 (2.7516), thorax 6/0 (2.6181).
- Raw records: [command.json](../../artifacts/agent/runs/success-3/command.json), [trace.json](../../artifacts/agent/runs/success-3/trace.json), [answer.txt](../../artifacts/agent/runs/success-3/answer.txt), [stdout.txt](../../artifacts/agent/runs/success-3/stdout.txt). Labels in [classification.json](../../artifacts/agent/classification.json).

## Result

The agent searched the store, substituted the query 'insect' after 'entomology' returned nothing, identified the entomology pair, and reported the distinctive terms as a table with citations to both sources.

The evidence supports every number in the answer. The compare payload carries the same counts and log-odds, the Britannica scan checksum, and the Wikipedia revision. The answer cites the entry id, the Wikipedia URL, and revision 1337353135. The report verifies every citation with no unsupported ids.

The case is a success because the full funnel ran: search, compare, and a cited answer on the stored pair. classification.json records: "Full funnel: found the right pair, reported distinctive terms, cited entry and Wikipedia revision." The run used 8 tool messages; one rejected batch tool_call did not affect the result.

Limits: the store has no literal match for 'entomology', so the pairing depends on the agent's substitution of 'insect' and its judgment that this page is the entomology entry, which the wingless-insect text supports. The reported terms are corpus statistics from the stored comparison, not a fresh analysis. The log-odds values are rounded to two decimals in the answer (3.56 for 3.5626).
