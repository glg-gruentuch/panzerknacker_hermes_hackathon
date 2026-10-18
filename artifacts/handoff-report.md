# Handoff report

## Frontend handoff

Branch `ui-real-data`, based on `landing-page` with `main` merged at `df45ca8`. Covers Task 6 in `docs/handoff.md` and F1 to F4 in the frontend handoff. The backend was run locally from `main` for the live checks.

### Done

| Item | What changed | Evidence |
|---|---|---|
| Task 6: verdicts | `agrees`, `differs`, `contradicts`, `not_in_wikipedia` replace the old labels. Every explanation carries an "Inference" tag. | `artifacts/web/live-strong-match-changes.png` |
| Task 6: funnel | The match details list each candidate with BM25 rank, embed rank and similarity, rerank rank and logit, and the rank change. The Wikipedia licence and revision link show when sent. | `artifacts/web/live-strong-match-funnel.png` |
| Task 6: reading pane | Britannica views: Summary, Normalized, Original text, Scan. The scan outlines Parse blocks and boxes the selected claim's block. Source text and model text look different. | `artifacts/web/live-strong-match.png`, `live-strong-match-scan.png` |
| Task 6: changes view | In order: verdict counts, claims by verdict with both quotes, quantity drift, distinctive vocabulary, obsolete terms, section coverage. Each part shows "pending" when its stage has not run. | `artifacts/web/live-strong-match-changes.png` |
| Task 6: quality chip | Shows dictionary-word share, known OCR issues and the compiled PDF link when the backend sends `britannica.quality`. | Checked in mock mode on the real page 13 entry |
| Task 6: mock gated | Live is the default. Mock data loads only with `VITE_API_MODE=mock` and is absent from the live and static bundles (no mock strings in `dist/`). | `npm run build` output |
| Task 6: three entries | Strong match (COINAGE), fragment (page 13, SHIP-BUILDING), unmatched (WILLIN), live backend, browser screenshots. | `artifacts/web/live-strong-match.png`, `live-fragment.png`, `live-unmatched.png` |
| F1 | Model IDs from `config.py` everywhere. Scores shown as raw logits. Threshold read from `/api/meta` `matchLogitThreshold`, not hard-coded. `api-examples/` regenerated with `npm run examples`. | `grep -rF -e "3.0" -e "Nemotron-3-" -e "Nemotron 3-" -e "0.5 to be compared" web/src web/API.md web/api-examples` finds 0 lines |
| F2 | The UI shows models and the chat trace exactly as the API returns them. `web/API.md` rewritten from saved live replies; each row of its model table names a field in one of them. | `artifacts/web/live-topics.json`, `live-compare.json`, `live-compare-fragment.json`, `live-scans-blocks.json`, `live-chat.json`, `live-cases.json`, `live-meta.json` |
| F3 (code) | `VITE_API_MODE=static` reads `data/*.json` with relative URLs, searches `topics.json` in the browser, loads the entry file through `compare/index.json`, offers only recorded questions, and marks answers "Recorded run" with the run directory. Vite `base: './'`. `npm run build:static` writes to `deliverables/website/app/`. | Trial: `artifacts/web/static-trial-*.png` |
| F4 | `web` job in `.github/workflows/checks.yml`: `actions/setup-node` pinned to `949feb2` (v7.1.0), Node 22, `npm ci` and `npm run build` in `web/`. | `npm ci && npm run build` passes locally on a clean install |

### Checks

- `npm run typecheck`: pass.
- `npm run build`: pass. Live bundle 291 kB, no mock data.
- Static trial: built with `VITE_API_MODE=static` and served with `python3 -m http.server` while the backend was stopped. Strong match, fragment and unmatched entry load; recorded chat replays.
- Impeccable design detector on `/`, `/?q=coinage`, `/?q=page-0013-fragment`: no findings.
- Phone width (390 px): `artifacts/web/live-strong-match-phone.png`.

### Not done, and why

- **F3 done-check on the B10 export.** B10 has not written `deliverables/website/app/data/`. The frontend export in `web/static-data/` (commit `df45ca8`) covers the Cloudflare site in the meantime. Once B10 lands, rerun `npm run build:static`, check a strong match, a fragment and an unmatched entry, and save `artifacts/web/static-*.png`.
- **F3 hosting.** Waiting for the human: where the site is hosted, and whether the repository stays public. Nothing was published.
- **F4 green run.** Needs a push, which the human has not asked for yet.
- **`package-lock.json`.** This clone has no uncommitted lock change, so nothing to decide here. The teammate's local change still needs the human's call.

### Decisions by the human

- **Cloudflare deploy uses the real artifacts of commit `df45ca8`.** Cloudflare does not run the Python backend, so `web/scripts/export-static.py` exports the artifacts to `web/static-data/` with the backend's `WebAdapter` and `recorded_run` (no model calls), and `web/wrangler.jsonc` runs `npm run build:cloudflare` (`VITE_API_MODE=static`) before each deploy. The landing page names the commit. An earlier commit on this branch used the sample data; the human replaced that with this export.

### Requests for the backend agent

The UI reads these when present and shows "pending" until then. Details in `web/API.md`, section "Fields the UI already supports".

1. `candidates[].bm25Rank`, `embedRank`, `rerankRank` from `match/evidence.jsonl`. The funnel columns show "–" today.
2. `meta.matchLogitThreshold` (B4). The UI shows "threshold pending" today.
3. `topic.entryId` on every topic, so static mode can use `compare/index.json` keyed by `entry_id`.
4. `topic.area` for the landing subjects. All four subjects show 0 articles today.
5. `obsoleteTerms`, `wikipedia.revisionId` and `revisionUrl`, `britannica.normalized`, `britannica.quality`, `edition` and `year`.
6. In the static export, rewrite `britannica.imageUrl` to the scan in `assets/scans/` (the UI also maps `/api/scans/<name>` there) and embed `britannica.blocks`, because static mode cannot call `/api/scans/<page>.json`.

### Failed model calls

None from the frontend. `POST /api/chat` on this machine returned a recorded run with `error: "ConfigurationError: Hermes binary not found at /opt/hermes/.venv/bin/hermes"` (`artifacts/web/live-chat.json`). The UI shows that error under the answer.
