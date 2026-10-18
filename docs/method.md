# Method

Chosen methods for the pipeline. The team confirmed each choice before implementation.

## Extraction (stage: extract)

- Model: `nvidia/nemotron-3.5-parse` through the shared organizer endpoint, with the
  starter's default instruction prompt and `temperature: 0`.
- One reply per scan. Raw replies stay in `artifacts/extract/raw/`; derived
  entries in `artifacts/extract/derived/`. Details and rules: `parse-notes.md`.
- Entry segmentation uses the class labels and bounding boxes from the Parse
  reply. Headers, footers, and page numbers stay out of the entry text.
- Continuation joining stays conservative: cross-page, first-entry-of-page,
  running-head or exact repeated heading. The current sample has no such join.
- A scan that fails stays a failure in `coverage.json` with its error. Two
  scans failed (blank binding, engraved plate); their degenerate replies are
  kept as evidence.

## Matching (stage: match)

- Candidates: the shared Wikipedia BM25 API, `top_k=30`, `excerpt_chars=1200`,
  query built from the entry heading and opening text (within 512 chars and
  48 words; the service rejects a full 64-word query).
- Shortlist: Nemotron Embed VL (`input_type="query"` for the entry text,
  `input_type="document"` for candidate excerpts; batches of at most 16).
  Dot product of unit vectors keeps the best 8 candidates.
- Rerank: Nemotron Rerank VL over the shortlist excerpts. Scores are raw
  logits. The best candidate at or above the threshold becomes the match.
- Threshold: `MATCH_LOGIT_THRESHOLD` in `src/nemotron_challenge/config.py`.
  The current value is provisional until the W2.1 calibration run against the
  live retrieval service. Calibration notes will go to
  `artifacts/match/calibration.md`.
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

- extract: complete (98 of 100 scans; two failures reported).
- match and compare: implemented and tested; the live runs wait for the
  team's retrieval service deployment (W0). `doctor --live` shows retrieval
  as failed until then.
- agent: profile and plugin are ready; case runs wait for the comparison
  artifacts.
