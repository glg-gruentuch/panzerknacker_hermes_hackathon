# Case study

Case ID: scan-check-1
Classification: success
Run record: artifacts/agent/runs/scan-check-1/
Code revision: 91bc3dc

## Question

The stored text for page britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:257 (filename page-0257-012cf5a82a33.jpg, the Swift entry) contains the word 'grocery', which looks like a modern insertion by the text extraction. Call challenge_scan_check with this page ID and the quote 'grocery' to verify whether the word appears in the scan image. Report the returned result and reason, and quote the block text.

## Evidence

- Britannica page: britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:257. Entry: britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:257#0000, listed with scan file page-0257-012cf5a82a33.jpg in artifacts/extract/derived/entries.json.
- Tool call in trace.json: challenge_scan_check with {"page_id": "britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:257", "quote": "grocery"}.
- Tool result in the run session (session 20261018_150417_d9aabf): status "ok", result "mismatch", reason "The word 'grocery' does not appear in the visible text.", bbox [[0.0986, 0.1992], [0.5244, 0.4125]].
- Block text quoted in the answer: "I love Swiffly in his parents Sir William Temple, who left him a legacy in many, with the grocery of his manuscript; and, on his death-bed, obtained for him a proform for the long or for first petrol that should houses one can at Wittenurle or Overburnt. That this provides might not be forgotten, Swift dedicated to the king the author among people with which he we weretrafed, and for a while atten".
- Context: the derived extraction for this page (artifacts/extract/derived/page-0257-012cf5a82a33.jpg.json) contains the words 'grocery' and 'petrol' in this block, so the mismatch shows the extraction inserted them. The extraction QA notes (artifacts/extract/qa/notes.json) cite this run and scan-check-2 as the model-backed vision checks.
- Raw records: [command.json](../../artifacts/agent/runs/scan-check-1/command.json), [trace.json](../../artifacts/agent/runs/scan-check-1/trace.json), [answer.txt](../../artifacts/agent/runs/scan-check-1/answer.txt), [stdout.txt](../../artifacts/agent/runs/scan-check-1/stdout.txt). Labels in [classification.json](../../artifacts/agent/classification.json).

## Result

The agent described the tool, called challenge_scan_check once with the requested page ID and quote, and reported the returned result, reason, and block text. The answer matches the tool result word for word.

The evidence supports the finding. The word 'grocery' does not appear in the visible text of the scan of page-0257. The tool ran end to end: it located the text block with bounding box [[0.0986, 0.1992], [0.5244, 0.4125]], cropped that region, and the vision model returned mismatch.

The case is a success because the check completed with a definitive verdict and the answer carried it faithfully. classification.json records: "The vision check ran end to end and returned mismatch on the word the extraction inserted." The run used 2 tool messages, with no errors and no not_found results.

Limits: the finding covers one word in one block. The verdict is the vision model's reading of the cropped region, and the surrounding block text is itself noisy ("Swiffly", "proform"), so the check confirms the absence of 'grocery' there. It does not measure how many other words the extraction inserted or dropped on this page.
