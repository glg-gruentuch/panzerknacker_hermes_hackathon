# Method

Chosen methods for the pipeline. The team confirmed each choice before implementation.

## Extraction (stage: extract)

- Model: `nvidia/nemotron-3.5-parse` through the shared organizer endpoint, with the
  starter's default instruction prompt and `temperature: 0`.
- One reply per scan. Raw replies stay in `artifacts/extract/raw/`; derived
  entries in `artifacts/extract/derived/`. Details and rules: `parse-notes.md`.
- Entry segmentation follows the v2 rules in `parse-notes.md`. A `Text` block
  that opens with an inline upper-case headword starts an entry. `Page-header`
  blocks are running heads only. Subsection headings merge into the parent
  entry. Text before the first headword becomes a fragment entry with no
  heading. Every parsed page keeps at least one entry. Running heads, headers,
  footers, and page numbers stay out of the entry text.
- Continuation joining stays conservative: cross-page, first-entry-of-page,
  running-head or exact repeated heading. The current sample has no such join.
- A scan that fails stays a failure in `coverage.json` with its error. Two
  scans failed (blank binding, engraved plate); their degenerate replies are
  kept as evidence. The two failed scans also carry Super VL image
  descriptions in `artifacts/extract/vl-fallback/`, and the site index shows
  them.

## Matching (stage: match)

- Candidates: the shared Wikipedia BM25 API, `top_k=30`, `excerpt_chars=1200`,
  query built from the entry heading and opening text (within 512 chars and
  48 words; the service rejects a full 64-word query).
- Shortlist: Nemotron Embed VL (`input_type="query"` for the entry text,
  `input_type="document"` for candidate excerpts; batches of at most 16).
  Dot product of unit vectors keeps the best 8 candidates.
- Rerank: Nemotron Rerank VL over the shortlist excerpts. Scores are raw
  logits. The best candidate at or above the threshold becomes the match.
- Retrieval endpoint history: early runs used the hosted NVIDIA NIM gateway
  (`docs/nim-gateway.md`). Since 2026-10-18 the stage runs against the team's
  Nebius deployment of the pinned embedder and reranker
  (`docs/model-service.md`, GPU receipt `artifacts/retrieval-gpu-smoke.json`).
  Every candidate row keeps the BM25 score, the embedding similarity, and the
  reranker logit.
- Threshold: `MATCH_LOGIT_THRESHOLD` in `src/nemotron_challenge/config.py`.
  The value is `-5.5`. It comes from a hosted-NIM trial, and
  `artifacts/match/calibration.json` reports the sample precision: 0.35
  overall, 0.67 on headword entries, 0.09 on fragments. The final runs use
  the pinned deployment with the same value; re-calibrate when the backend
  or the model revision changes.
- A weak candidate set produces an explicit `unmatched` decision. Later
  stages never force a match.
- Evidence: every candidate row, both scores, and the decision stay in
  `artifacts/match/evidence.jsonl`; accepted pairs carry article revision IDs
  and checksums in `artifacts/match/matches.jsonl`.

## Comparison (stage: compare)

- Text units: the full matched pair (entry text against article text).
- Normalization: lowercase letter runs of two or more characters; long s and
  ligatures are folded; every change is logged. OCR errors and historical
  spelling are reported, not corrected in place.
- Measures: token counts, type/token ratio, top terms per side, and
  distinctive terms by Laplace-smoothed log-odds.
- Plots: one chart per showcase pair and one corpus chart. Chart data counts
  exactly the compared pairs.

## Status of the runs

- extract: complete. 98 of 100 scans produced text. Segmentation v2 derived
  232 entries (135 headwords, 97 fragments). The two failed scans stay in
  `coverage.json` with their errors.
- match: complete. 232 entries processed, 76 matched to 76 unique articles,
  156 unmatched, threshold -5.5.
- compare: complete. 76 pairs compared, 13 plots in `artifacts/compare/plots/`.
- claims: complete. Claims exist for 76 of 76 matches: 421 claims (27 agree,
  14 differ, 380 not in Wikipedia, 0 contradict).
- agent: complete. Case runs are saved under `artifacts/agent/runs/`, and the
  classification is in `artifacts/agent/report.json`.
- site and export: complete. The build compiled 98 LaTeX pages into
  `deliverables/website/` with 76 comparison pages and no broken links; the
  export stage writes the static app data.
- evaluate: complete. `docs/evaluation.md` and `artifacts/evaluate/report.json`
  were regenerated from the current artifacts: provenance, coverage (98 of
  100 pages, 232 entries), matching (76 of 232), claims (421), the nine agent
  case runs, the failed model calls per stage, and the pytest result.
- LanceDB: backfilled from the saved JSONL artifacts (B2). Tables:
  britannica_entries 232, wiki_articles 76, wiki_paragraphs 2,674,
  match_evidence 6,796; full-text indexes on. Vector columns fill on later
  stage runs.
