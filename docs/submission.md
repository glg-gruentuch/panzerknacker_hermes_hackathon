# Submission

Team: Panzerknacker
Repository URL and commit: https://github.com/glg-gruentuch/panzerknacker_hermes_hackathon (commit `0289a6d` at the time of writing; run `git rev-parse HEAD` and record the final commit before submitting)
Video URL, 3 minutes: TODO (human)
Static website URL: TODO (human)
Compiled LaTeX documents: deliverables/website/files/ holds 98 compiled PDFs. LaTeX sources are in artifacts/site/tex/, and the build record is in artifacts/site/build.json.

## Reproduce the run

Work from the repository root on Linux with uv and Python 3.12.

```sh
uv sync --locked
cp .env.example .env
uv run nemotron-challenge doctor --live
uv run nemotron-challenge data fetch
uv run nemotron-challenge run extract
uv run nemotron-challenge run match
uv run nemotron-challenge run compare
uv run nemotron-challenge run claims
uv run nemotron-challenge run agent
uv run nemotron-challenge run site
uv run nemotron-challenge run evaluate
uv run nemotron-challenge run export
```

Fill `.env` with the team endpoints and keys. Keep that file out of Git.
Re-derive the segmentation from the saved Parse replies without model calls: `uv run nemotron-challenge run extract --derive-only`.
Run the retrieval service on the team GPU from `docs/model-service.md`. Without a GPU, `uv run nemotron-challenge gateway --port 8001` serves the hosted NVIDIA NIM models on the same contract (`docs/nim-gateway.md`).

Tested versions. Python 3.12.13. Packages: httpx 0.28.1, pydantic 2.14.1, python-dotenv 1.2.4, lancedb 0.40.0, pyarrow 21.0.0, huggingface-hub 2.2.0, fastapi 0.144.0, uvicorn 0.54.0, tantivy 0.26.2, matplotlib 3.11.2, pytest 9.1.1. The package check output is in `artifacts/doctor-live.txt`.

Model IDs, revisions, and serving settings.

- Parse: `nvidia/nemotron-3.5-parse` on the shared organizer endpoint. Default starter prompt, temperature 0, one reply per scan.
- Embedder: `nvidia/llama-nemotron-embed-vl-1b-v2`, revision `582e3bf72aee355e3c59ed89de53543c5b0657ee`. Text inputs, `input_type` query or document, 2,048-dimension unit vectors, batches of at most 16 items.
- Reranker: `nvidia/llama-nemotron-rerank-vl-1b-v2`, revision `b8a9987b05b75db5ad949c825cbcbf6eb7c48b5a`. Raw logits, at most 32 documents. The serving contract is in `docs/model-service.md`. The GPU receipt is in `artifacts/retrieval-gpu-smoke.json`.
- Super VL: `nvidia/Nemotron-3.5-Super-VL` through Nebius Token Factory, temperature 0. Used by the Hermes agent, the claims stage, the scan check tool, and the descriptions of the two failed scans.
- Retrieval endpoint history: early matching used the hosted NVIDIA NIM gateway (`docs/nim-gateway.md`). The final runs use the team's Nebius deployment of the pinned models. The accept threshold (-5.5) was calibrated on the hosted relay; the sample and its precision are in `artifacts/match/calibration.json`. Re-check the value if the backend changes.

Sources. Britannica dataset revision `309f765b1ecc83e0a7f7762e44b4a927a7555443`, fixed sample of 100 pages, seed `20261016`, manifest SHA-256 `779542e078756874f23fa6971d7d8a2d8635ad6d9d9484e1deb607d94a28e396`, source parquet SHA-256 `08f167015db23cb027995b2b6a6bc953b01d7c1ddf667de950465cc2b601af5c`. Wikipedia snapshot revision `417c267bb457fa645c22eb3b5c77764963194c70`, searched through the shared BM25 API. Article revisions and checksums are stored with each match.

## Results

Scan coverage. 98 of 100 pages produced text. Two scans failed: page-0452 (blank binding) and page-2243 (engraved plate). Their Parse replies degenerated into repetition and stopped at the token limit. The failures stay reported in `artifacts/extract/coverage.json`, and the degenerate replies are kept in `artifacts/extract/failures/`.

Extraction. 232 entries in total: 135 headword entries and 97 fragments. No parsed page lacks an entry. The v2 segmentation rules are in `docs/parse-notes.md`.

Article associations. 232 entries processed, 76 matched to 76 unique Wikipedia articles, 156 left unmatched, accept threshold -5.5. Every candidate row keeps the BM25 score, the embedding similarity, the reranker logit, and the decision (`artifacts/match/evidence.jsonl`). Accepted pairs carry article revision IDs and checksums (`artifacts/match/matches.jsonl`). The 20-pair calibration sample (`artifacts/match/calibration.json`) reports precision 0.35 overall: 0.67 on headword entries and 0.09 on fragments. Unmatched entries are reported, never forced.

Comparison method. One record per matched pair: the Britannica entry text against the Wikipedia article text. Normalization folds long s and ligatures, keeps lowercase letter runs of two or more characters, logs every change, and removes stopwords for token counts. Measures: token counts, type/token ratio, top terms, distinctive terms (Laplace-smoothed log odds), and obsolete Britannica terms with no Wikipedia occurrence. OCR errors and historical spelling are reported, not corrected. Text exclusions: running heads, headers, footers, and page numbers stay out of the entry text; stopwords are removed for counts only.

Claims. Super VL extracted 421 atomic claims for 76 of 76 matches and judged each claim against the Wikipedia paragraphs with exact quotes. Verdicts: 27 agree, 14 differ, 0 contradict, 380 not covered in Wikipedia. Claims whose quotes failed the substring check were downgraded (129). The stage recorded 18 failed model calls (service timeouts: 4 claim-extraction calls and 14 judge calls) in `artifacts/claims/failures.jsonl`; every affected entry still carries claims. Records: `artifacts/claims/claims.jsonl`; summary in `artifacts/claims/summary.json`.

Analysis and records. Comparisons: `artifacts/compare/comparisons.jsonl` (76 rows). Plots: `artifacts/compare/plots/` (13 charts). Corpus terms: `artifacts/compare/summary.json`. Table counts: `artifacts/lancedb-summary.json` (britannica_entries 232, wiki_articles 76, wiki_paragraphs 2,674, match_evidence 6,796, full-text indexes on).

## Case studies

Six cases, each with its saved run under `artifacts/agent/runs/`:

- [docs/cases/scan-check-1.md](cases/scan-check-1.md): the scan check flags a stored word that the page image does not support.
- [docs/cases/success-4.md](cases/success-4.md): the agent reports both token counts with a Britannica and a Wikipedia citation.
- [docs/cases/success-3.md](cases/success-3.md): the agent lists the distinctive terms for the Hymenoptera pair with both source citations.
- [docs/cases/scan-check-2.md](cases/scan-check-2.md): the stored text of an unmatched entry is not reachable through the tools; the agent names the gap instead of inventing text.
- [docs/cases/failure-3.md](cases/failure-3.md): a blank scan; the agent reports not_found for page-0452 and its ID variants.
- [docs/cases/success-1.md](cases/success-1.md): the agent finds the SHIP-BUILDING entry and reports that no stored comparison exists for it.

Use `case-study.md` for each case. Failed attempts are retained: `artifacts/agent/runs-fallback-first/`, `artifacts/claims/failures-attempt1.jsonl`, and `artifacts/extract/failures/`.

## Limits

- Tested on the fixed 100-scan manifest only. Other volumes, editions, and languages are untested.
- Two scans failed and produce no entries. This is reported, not repaired.
- OCR noise stays in the text (for example 'Fractical Building' for 'Practical Building' on page-0013, listed in `artifacts/extract/qa/notes.json`). The scan check flags suspect quotes; it does not fix them.
- Matching precision is low on fragments (0.09 on the 20-pair sample against 0.67 on headwords). The calibration labels are agent labels; `artifacts/match/calibration.csv` keeps the `human_label` column open for a human override.
- The accept threshold was calibrated on the hosted relay, and the final runs use the pinned deployment with the same value. Re-verify it when the backend or the model revision changes.
- The strict citation checker passes 4 of the 9 recorded agent runs. Every run stays in the record, and `docs/evaluation.md` lists each outcome.
- The video URL and the website URL wait on the human team (TODO (human) above).
- Next steps: human labels in the calibration file, a second pass over fragments with parent-entry context, and a wider OCR error sample.
