# Evaluation report

Generated from the saved stage artifacts. Do not edit by hand; rerun the evaluate stage.

## Provenance

- Code revision: 0289a6da64fcd0810c56eb392fa1fb22a5dbf53b.
- Dirty worktree flag: yes.
- Segmentation (Parse 3.5): nvidia/nemotron-3.5-parse (revision not recorded in config).
- Embedding: nvidia/llama-nemotron-embed-vl-1b-v2 (revision 582e3bf72aee355e3c59ed89de53543c5b0657ee).
- Reranking: nvidia/llama-nemotron-rerank-vl-1b-v2 (revision b8a9987b05b75db5ad949c825cbcbf6eb7c48b5a).
- Claims and agent answers (Super VL): nvidia/Nemotron-3.5-Super-VL (revision not recorded in config).
- Britannica dataset: NationalLibraryOfScotland/encyclopaedia_britannica_illustrated (revision 309f765b1ecc83e0a7f7762e44b4a927a7555443).
- Britannica manifest checksum: 779542e078756874f23fa6971d7d8a2d8635ad6d9d9484e1deb607d94a28e396.
- Wikipedia revision: 417c267bb457fa645c22eb3b5c77764963194c70.

## Coverage

- Pages processed: 98 of 100 (failed: 2).
- Entries: 232. Continuation joins: 0.
- Pages with entries: 98.
- Pages without entries: none.

## Matching

- Entries processed: 232. Matched: 76. Unmatched: 156.
- Unique articles: 76. Repeated selections: 0.

## Claims

- Match coverage: claims for 76 of 76 matches.
- Claims total: 421. Downgraded: 129.
- Verdicts: agrees 27, differs 14, contradicts 0, not_in_wikipedia 380.

## Comparison

- Compared pairs: 76.

## Agent cases

- success-1: expected citation, passed=False (citation=False, admits_missing=True).
- success-2: expected citation, passed=False (citation=False, admits_missing=True).
- success-3: expected citation, passed=True (citation=True, admits_missing=True).
- success-4: expected citation, passed=True (citation=True, admits_missing=False).
- failure-1: expected insufficient_evidence, passed=True (citation=True, admits_missing=True).
- failure-2: expected insufficient_evidence, passed=True (citation=False, admits_missing=True).
- failure-3: expected insufficient_evidence, passed=True (citation=False, admits_missing=True).
- scan-check-1: expected scan_check, passed=True (citation=False, admits_missing=False).
- scan-check-2: expected citation, passed=False (citation=False, admits_missing=True).
- probe-1: expected citation, passed=False (citation=False, admits_missing=False).
- probe-2: expected citation, passed=False (citation=False, admits_missing=False).
- probe-3: expected citation, passed=False (citation=False, admits_missing=False).

## Failed model calls

- Extract: 2 failed pages. Source: artifacts/extract/coverage.json. Raw failure details: artifacts/extract/failures.
- Match: 0 failed entries. Source: artifacts/match/summary.json.
- Claims: 18 failed model calls. Source: artifacts/claims/failures.jsonl (line count).

## LanceDB rows

- Rows: artifact_provenance 250, match_evidence 6796, britannica_entries 232, wiki_articles 76, wiki_paragraphs 2674.

## Checks

- Pytest: 184 passed, 12 warnings in 13.33s on 2026-10-18 (command: uv run pytest -q).
- Frontend build (npm run build): not run: frontend build out of scope for this session.

## Limits

- The fixed 100-scan manifest defines the source sample; extraction failures stay listed.
- Match thresholds are calibrated on samples; unmatched entries are reported, not forced.
- OCR errors in the scans and historical spelling are documented, not corrected in place.
- Wikipedia text is quoted under CC BY-SA 4.0 with article revisions recorded.
