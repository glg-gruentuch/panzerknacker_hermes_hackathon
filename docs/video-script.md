# Video script and shot list

The PDF participant brief sets the limit: "A 3-minute video showing successful and failed cases from your pipeline."
The starter README says 3 to 5 minutes, and the brief overrides it (see `docs/team-notes.md`).
This script plans about 2:21 of material, inside the hard 3-minute limit.

## Before you record

1. Check the provenance block in `docs/evaluation.md`. Rerun `uv run nemotron-challenge run evaluate` if any stage ran after the report.
2. Serve the site and open it: `uv run python -m http.server 8080 --directory deliverables/website`, then browse `http://localhost:8080/index.html`.
3. Open a terminal in the repository root.
4. Keep these ready: the site index, the site compare page, the page-0257 scan page, `artifacts/agent/runs/success-4/answer.txt`, `artifacts/agent/runs/failure-3/trace.json`, `artifacts/agent/runs/scan-check-1/answer.txt`, `artifacts/evaluate/report.json`, and `artifacts/claims/claims.jsonl`.
5. Do not show `.env`, API keys, account screens, or token values on screen.

## Shot list

Each shot covers one rubric line from the brief. Keep each shot between 15 and 20 seconds.

### Intro, 0:00 to 0:15
- Show: the site index (`deliverables/website/index.html`).
- Say: "Panzerknacker. 100 historical Britannica scans, 76 matched Wikipedia articles, 421 claims, and one Hermes agent that answers with citations."

### Shot 1, 0:15 to 0:33. Rubric line: Completion of specs (20 points)
- Show: the scan `data/raw/britannica/page-0013-50049db49e8b.jpg`, the LaTeX source `artifacts/site/tex/page-0013-50049db49e8b.jpg.tex`, the compiled PDF `deliverables/website/files/page-0013-50049db49e8b.jpg.pdf`, and the archive `deliverables/website/index.html`. `artifacts/site/build.json` lists 98 compiled pages and no broken links.
- Say: "Parse 3.5 extracted 232 entries from the sample. 98 pages compile to LaTeX PDFs on the static site. Two scans failed, and both stay reported."

### Shot 2, 0:33 to 0:52. Rubric line: Nemotron Embedder and Reranker (15 points)
- Show: `artifacts/match/summary.json` (232 processed, 76 matched, 156 unmatched, threshold -5.5), one row of `artifacts/match/evidence.jsonl` with the BM25 score, the embedding similarity, and the rerank logit, and `artifacts/lancedb-summary.json` (match_evidence 6,796 rows).
- Say: "The funnel: BM25 finds candidates, the embedder keeps the best 8, and the reranker decides. 76 of 232 entries matched. Every candidate and every score is kept."

### Shot 3, 0:52 to 1:11. Rubric line: Nemotron 3.5 Super VL (20 points)
- Show: the Olney claim in `artifacts/claims/claims.jsonl`. Entry `britannica:...:train:713#0001`, article "Olney, Buckinghamshire". Britannica quote: "nine miles". Wikipedia quote: "the Town is located around 8 miles (13 km) from Milton Keynes, and 10 miles (16 km) from Bedford, Northampton and Wellingborough." Verdict: differs. The explanation is labeled an inference.
- Say: "Super VL reads each matched pair and judges every claim against the Wikipedia paragraphs. Here the 1768 distance and the modern distance do not agree. 27 claims agree, 14 differ, and 380 are not covered in Wikipedia."

### Shot 4, 1:11 to 1:29. Rubric line: Nemotron Parse 3.5 (15 points)
- Show: the scan `data/raw/britannica/page-0257-012cf5a82a33.jpg` next to the site page `deliverables/website/page-0257-012cf5a82a33.html` with its OCR issues section. Show `artifacts/agent/runs/scan-check-1/answer.txt`: result "mismatch", reason "the word 'grocery' does not appear in the visible text". Show `artifacts/extract/qa/notes.json`: "Fractical Building" for "Practical Building" and "Eta" for "Etna".
- Say: "The scan check crops the quote's text block and asks the vision model whether the image supports it. Extraction errors are identified and reported, not corrected in place."

### Shot 5, 1:29 to 1:48. Rubric line: Extension of Hermes Agent (10 points)
- Show: `artifacts/agent/runs/success-4/answer.txt` (token counts with a Britannica citation and a Wikipedia citation) and `artifacts/agent/runs/failure-3/answer.txt` with its trace (the trace shows three challenge_scan_check calls with malformed page ids; the answer still refuses honestly). Name the tools from `integrations/hermes/nemotron-challenge/plugin.yaml`: challenge_search, challenge_compare, challenge_claims, challenge_scan_check.
- Say: "We built a Hermes plugin with four comparison tools over the saved evidence. The success case reports token counts with both citations. The failure case shows repeated malformed scan-check ids, and the answer still refuses honestly."

### Shot 6, 1:48 to 2:06. Rubric line: Creativity (20 points)
- Show: `docs/evaluation.md` (coverage: 98 of 100 pages, 232 entries, 76 matched, 76 compared), `artifacts/compare/plots/corpus.png`, and one compare page in `deliverables/website/compare.html`.
- Say: "The whole run: 98 of 100 pages, 232 entries, 76 matched articles, 76 comparisons, 421 claims. Every comparison page lets a user open both sources and see the differences."

### Close, 2:06 to 2:21
- Show: `docs/submission.md`, pointing at the two TODO (human) lines.
- Say: "The repository holds the pipeline, the site, the case studies, and the method. The site URL and the video URL go into the submission file."

## After recording

1. Upload the video (3 minutes or shorter) and put the URL in `docs/submission.md` on the "Video URL" line.
2. Put the public site URL in `docs/submission.md` on the "Static website URL" line.
3. Run `uv run nemotron-challenge run evaluate` again if any case run changes after recording, so the evaluation numbers match the video.
