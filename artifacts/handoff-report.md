# Handoff report

This report covers `docs/handoff.md` (tasks 0 to 8) and `handoff-2.md` (items B1 to B12). Branch: `feat/pipeline-completion`. The frontend task (handoff 1 task 6) was dropped on the user's instruction; frontend-owned items of handoff 2 (F1 to F4) were out of scope.

## Handoff 1, tasks 0 to 8

### Task 0. Retrieval endpoint
`uv run nemotron-challenge doctor --live` passed for Wikipedia, Parse, retrieval and Super VL. Output saved to `artifacts/doctor-live.txt`. The retrieval endpoint first served the hosted NIM relay (`docs/nim-gateway.md`), then the team's pinned Nebius deployment of embed and rerank went live (`artifacts/retrieval-gpu-smoke.json`, revision-pinned models). The claims stage ran against the pinned deployment.

### Task 1. Segmentation
`segment()` now starts entries at inline upper-case headwords, keeps `Page-header` blocks as running heads only, merges subsection headings, and records text before the first headword as a fragment. Every parsed page keeps at least one entry (B1). `entries.json` holds 232 entries (135 headwords, 97 fragments, 97 subsections) and zero headings that match the running-head pattern. The old list is kept at `entries.v1.json`.
- Evidence: `artifacts/extract/segment-summary.json` (pages_with_entries 98, pages_without_entries empty), `tests/test_extract.py` (27 tests), commits `a47fdcb` and `339bdfc`.

### Task 2. Match on all 100 pages
Queries come from the headword plus first sentence; fragments use the eight rarest content words. `artifacts/match/evidence.jsonl` stores every candidate with `bm25_rank`, `embed_similarity`, `embed_rank`, `rerank_logit` and `rerank_rank` (6,796 rows).
- `artifacts/match/summary.json`: 100 pages, 98 with text, 2 failed scans reported with errors, 232 entries processed, 76 matched, 156 unmatched, 0 failures.
- Calibration: `artifacts/match/calibration.csv` (20 rows, empty `human_label` for the team to label) and `artifacts/match/calibration.json` (agent labels: precision 0.35 overall, 0.67 headwords, 0.09 fragments, against `MATCH_LOGIT_THRESHOLD = -5.5`; the threshold trial is documented in `config.py`).
- Empty pages (B1 fragments) record a `no-candidates` row with a note instead of querying the API with an empty string.

### Task 3. Compare
76 comparison records in `artifacts/compare/comparisons.jsonl` with plots in `artifacts/compare/plots/` (13). Each record gained `obsolete_terms`: Britannica terms with zero frequency in the article after long-s normalization. The method (word frequencies and log-odds) is unchanged.

### Task 4. Claim alignment
`src/nemotron_challenge/claims.py` with the `claims` stage, 7 tests, results cached by `(entry_id, article_revision_id, prompt_hash)`.
- Coverage: **claims for 76 of 76 matches** (`artifacts/claims/summary.json`): 421 claims, verdicts agrees 27, differs 14, contradicts 0, not_in_wikipedia 380, 129 downgraded.
- Quote checks run over all 421 claims: 0 Britannica quote violations (every quote is an exact substring of the entry body), 0 Wikipedia quote violations (every stored quote is an exact substring of the article). Hand-checked 3 records (Hydrostatics agrees, Olney "nine miles" against "8 miles (13 km)" differs, CCXXXIX not_in_wikipedia).
- Failed calls: `artifacts/claims/failures.jsonl` (18 lines, service timeouts on judge calls of the largest entries; each failed claim carries a recorded fallback verdict) and `artifacts/claims/failures-attempt1.jsonl` (44 lines from the first pass, kept separate; the cause was a too-small output budget for Super VL's reasoning tokens and is fixed by dynamic budgets and a longer client timeout). All 76 entries completed.

### Task 5. Backend
`src/nemotron_challenge/api.py` (FastAPI) and `src/nemotron_challenge/web_adapter.py`, built against `web/API.md` and `web/src/api/types.ts`. Routes: `/api/topics`, `/api/compare`, `/api/cases`, `/api/meta`, `/api/scans/{name}.jpg`, `/api/scans/{name}.json` (Parse blocks with bboxes), `/api/chat` (reuses `agent_runner.ask_agent`, recorded fallback included), and `/api/search` (B3). No model call at request time. Tests: `tests/test_api.py` (12). The app served on `127.0.0.1:8020` for the live agent runs.

### Task 6. React UI
Dropped at the user's request before the frontend part of the handoff. The static export (B10) writes the data the UI needs.

### Task 7. Hermes extension and cases
Plugin `integrations/hermes/nemotron-challenge/__init__.py` now registers four tools: `challenge_search` (backend search with fallback), `challenge_compare`, `challenge_claims` (aligned claims with citations and verdicts) and `challenge_scan_check` (crops the quote's block from the scan and asks Super VL with vision input; returns match, mismatch or unreadable and a reason). `data/hermes/config.yaml` exists and loads the plugin.
- Runs: `artifacts/agent/runs/` (12 runs; the fallback-mode first attempt is kept separately in `artifacts/agent/runs-fallback-first/`). `artifacts/agent/report.json` recomputed from stored evidence with the corrected checker (12 cases, 6 passed).
- Classification: `artifacts/agent/classification.json`. Two runs contain real misconduct: `success-1` (108 tool messages chasing an unsatisfiable premise, two failed `challenge_scan_check` calls) and `failure-3` (three `challenge_scan_check` calls with malformed page ids). Twelve runs produced no fabricated citation or answer; probes on absent data end in honest refusals.
- Case studies: `docs/cases/scan-check-1.md`, `success-3.md`, `success-4.md` (successes) and `success-1.md`, `failure-3.md`, `scan-check-2.md` (failures), each with its run directory and code revision `91bc3dc`. `scan-check-2.md` documents openly that the third failure slot holds the strongest remaining failure mode (an unmet task with a missed tool path) because only two runs contain misconduct and staging a failure is not allowed.
- Tests: `tests/test_agent_plugin.py` (14) and `tests/test_agent_runner.py` (8). `artifacts/agent/search-usage.json` shows every `challenge_search` call was served by `/api/search` (zero fallbacks).

### Task 8. Static site and evaluation
- `site_build.py` finds `tectonic` through `shutil.which` (clear failure message otherwise).
- Scan pages carry a "Matched article" line and an "OCR issues" section (from `qa/notes.json` and the task 7 scan checks). The index lists the two failed scans under "Parse failed; Super VL description" (B6) and links the app data.
- LaTeX structure (B7): `\section*` for headwords, `\subsection*` for subsections, "Continued from an earlier page" for fragments, `itemize` for List items, italics for Captions. Verified inside the compiled PDFs (`page-0251` shows `\section*{SWOONING}` and a subsection; `page-0013` shows the fragment section and "Fractical Building"). Rendered first pages of the compiled PDFs: `artifacts/site/page-0013-fragment.png`, `page-0217-headword.png`, `page-0251-subkey.png`, `page-0270-headword.png`. The derived text contains no literal long-s character (0 entries), so nothing needed a font change; the long-s normalization lives in the compare stage.
- `artifacts/site/build.json`: 98 pages, 98 PDFs, **zero broken links**. `docs/evaluation.md` shows non-zero matches (76), comparisons (76) and agent cases (12).

## Handoff 2, items B1 to B12

- **B9 (first)**: `.gitignore` now hides `/runs/` and `/site/` only at the top level, ignores `.omc/`, and exposes `artifacts/agent/runs/` and `artifacts/site/tex/`. Committed run files were searched for the `.env` key values; no hit.
- **B1**: every parsed page keeps at least one entry (`pages_without_entries` empty except the two failed scans, which have no raw reply). Tested with real fixtures from `page-0257`. Evidence: `artifacts/extract/segment-summary.json`.
- **B5**: `hermes_bin()` reads `HERMES_BIN` (environment, then `.env`), falls back to `shutil.which`, and fails with one clear message. `check_answer` requires a Britannica id plus a Wikipedia revision or URL, checks every cited id against tool results, and records `cited_ids` and `unsupported_ids`. `.env.example` documents `HERMES_BIN`.
- **B2**: `src/nemotron_challenge/lancedb_sync.py` plus runtime writes in match and claims. Backfill from the saved JSONL (no model calls): `artifacts/lancedb-summary.json` shows `match_evidence` 6,796 rows, `britannica_entries` 232, `wiki_articles` 76, `wiki_paragraphs` 2,674, FTS indexes true. Claims looks paragraphs up by `(revision_id, paragraph_index, text_sha256)` and embeds only missing ones; top-10 retrieval goes through LanceDB with the in-memory path as fallback. `tantivy` added for FTS. Tests: `tests/test_lancedb_sync.py` (7: rows, scoped vector search, cache hit skips the embed call). Note: the vector columns of the disk-rebuilt rows stay empty because earlier runs discarded the vectors; the runtime code now persists them, and a backfill with fresh embeddings is one flag away if the team wants full vectors in the store.
- **B3**: `GET /api/search` serves full-text hits from both tables. The plugin's `challenge_search` calls it through `CHALLENGE_API_URL` and marks results `"search": "lance"`, falling back to the title match with `"search": "fallback"`. Tests cover both paths. Done-when evidence: `artifacts/agent/search-usage.json` (all calls served by the API) and the run traces.
- **B4**: `/api/meta` lists a model or store only when its artifact exists, names the evidence path per row, and exposes `matchLogitThreshold` (-5.5). Tested in `tests/test_api.py`.
- **B6**: `artifacts/extract/vl-fallback/page-0452-233256cb3c3c.jpg.json` (blank page, "no typeset text") and `page-2243-0bd9a3e05239.jpg.json` ("Plate XLIII", five astronomical diagrams), both with model id and `finish_reason: stop`, kind `model_description`. Regenerate with `uv run python scripts/vl_fallback.py`. Shown on the site index under "Parse failed; Super VL description".
- **B7**: see task 8 above. The `.tex` sources live in `artifacts/site/tex/` and are committed.
- **B10**: `uv run nemotron-challenge run export` writes `deliverables/website/app/data/`: `topics.json`, `meta.json`, `cases.json` (the six documented cases), `compare/index.json` plus one compare file per entry (232 of 232) using the B10 name rule, and `chat-recorded.json` (12 runs). It calls the same adapter functions as the API routes. Test: `tests/test_export.py`.
- **B11**: the evaluate stage records the code revision and dirty flag, model ids and revisions, the dataset revision, manifest checksum and `WIKIPEDIA_REVISION`, `pages_without_entries`, the claims line ("claims for 76 of 76 matches"), failed call counts with paths per stage, LanceDB row counts, and the pytest result with its date and the frontend build status. Evidence: `artifacts/evaluate/report.json` and `docs/evaluation.md`. The frontend build (npm) is recorded as not run because the frontend was dropped for this session.
- **B12**: `docs/submission.md` filled from the template with only the video and site URLs left as `TODO (human)`; README gained an "Our solution" section with the stage commands, document links and a "Runs on" note; `docs/method.md` updated to the current state; `docs/video-script.md` is a 3-minute shot list; `artifacts/extract/qa/notes.json` records `reviewer_kind: agent_review` and points to the model-backed scan checks.

## Tests

- Full suite: **184 passed** (`uv run pytest -q`, 2026-10-18). `uvx ruff check` clean on all changed files.
- Module tests added or extended: `tests/test_extract.py` (27), `tests/test_match.py` (19), `tests/test_compare.py`, `tests/test_claims.py` (7), `tests/test_api.py` (12), `tests/test_lancedb_sync.py` (7), `tests/test_export.py` (2), `tests/test_agent_plugin.py` (14), `tests/test_agent_runner.py` (8), `tests/test_site_build.py` (4).
- Known limitation: the first live agent run and the first claims pass were recorded with stricter, narrower checks. The report was recomputed from the stored evidence after the checker fix, and the corrected analysis lives in `artifacts/agent/classification.json`.

## Failed model calls

- Extract: 2 pages (0452, 2243) `finish_reason: length`; recorded in `artifacts/extract/coverage.json` and `artifacts/extract/failures/`. Described separately via B6.
- Match: 0 failed entries (`artifacts/match/summary.json`).
- Claims: 18 judge-call service timeouts (`artifacts/claims/failures.jsonl`) and 44 first-pass budget failures (`artifacts/claims/failures-attempt1.jsonl`); every failed call is recorded, and all 76 entries completed with recorded coverage.
- Agent: no failed Hermes runs after the main pass; the fallback-mode first attempt is preserved in `artifacts/agent/runs-fallback-first/`.

## Skipped or cut, and why

1. The React UI (handoff 1, task 6) and the frontend items of handoff 2 (F1 to F4), on the user's instruction. Their data side (B4, B10) is complete.
2. Pushing. The branch is ready and the team asked (B11/B12 question); the human decides when to push.
3. Vectors in the disk-rebuilt LanceDB rows (see B2). The runtime writes them; refilling the backfill would need new embed calls, which B2 forbids from the JSONL-replay path.
4. `npm run build` result in the evaluation report: recorded as not run, same reason as item 1.
