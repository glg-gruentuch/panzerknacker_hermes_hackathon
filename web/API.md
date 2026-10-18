# Web API: what the UI reads

The React app reads data in one of three modes, set by `VITE_API_MODE`:

| Mode | Source | Use |
|---|---|---|
| `live` (default) | The FastAPI backend, `src/nemotron_challenge/api.py`, at `/api` | Development and the recorded demo |
| `static` | Exported JSON files in `app/data/` next to the built app | The deployed site, with no server |
| `mock` | Sample data in `src/api/mock/` | UI work without the backend. Other builds leave it out. |

In development, Vite sends `/api/*` to `VITE_BACKEND_URL` (default `http://localhost:8000`).

The UI's own model is `src/api/types.ts`. `src/api/normalize.ts` maps each backend reply onto it. A field the backend does not send becomes "pending" in the UI. The UI never fills it with a made-up value.

Errors: return a non-2xx status with JSON `{"detail": "..."}`. The UI shows `detail` to the user.

## Routes

Each route has one saved live reply in `artifacts/web/`, taken with `curl` from the backend at commit `df45ca8`.

| Route | Purpose | Saved reply |
|---|---|---|
| `GET /api/topics` | Every entry, for search and the landing page | `artifacts/web/live-topics.json` |
| `GET /api/compare?q=` | One entry with its match, claims and vocabulary. `q` is a slug, a headword or a label. | `artifacts/web/live-compare.json`, `live-compare-fragment.json` |
| `GET /api/scans/<page>.json` | Parse blocks with boxes for one page | `artifacts/web/live-scans-blocks.json` |
| `GET /api/scans/<page>.jpg` | The page scan | (image) |
| `POST /api/chat` | One question to Hermes | `artifacts/web/live-chat.json` |
| `GET /api/cases` | The agent cases | `artifacts/web/live-cases.json` |
| `GET /api/meta` | Datasets, models, sample | `artifacts/web/live-meta.json` |

## Where each required model shows up

Every field below appears in a saved reply in `artifacts/web/`.

| Model or store | Fields the backend fills | Where the UI shows it |
|---|---|---|
| `nvidia/nemotron-3.5-parse` | `britannica.rawText`, `britannica.passages[]` (compare); `blocks[].bbox`, `blocks[].class` (scans) | Original text and Summary views; the boxes in the Scan view |
| `nvidia/llama-nemotron-embed-vl-1b-v2` | `match.embedScore`, `candidates[].embedScore` (cosine similarity) | Similarity column in the match details |
| `nvidia/llama-nemotron-rerank-vl-1b-v2` | `match.rerankScore`, `candidates[].rerankScore` (raw logit, not 0 to 1) | Logit in the match bar and the match details |
| `nvidia/Nemotron-3.5-Super-VL` (claims stage) | `alignments[].verdict`, `alignments[].note`, `alignments[].type` | Underlines, What changed, the claim bar. Notes are labelled "Inference". |
| `nvidia/Nemotron-3.5-Super-VL` via Hermes Agent | `answer`, `grounding`, `trace[]` (chat). With `recorded: true`, `runDir` and `error` when Hermes did not run | Agent panel, "How this answer was made", the "Recorded run" tag |
| LanceDB | Listed in `models[]` (meta) only. No route reads from it. | Data and models page |

The UI lists models and the chat trace exactly as the backend returns them. It adds no rows of its own in live or static mode.

## Match strength and thresholds

`match.strength` is `strong`, `partial` or `none`. Thresholds on the raw reranker logit come from `/api/meta`. The UI reads `matchLogitThreshold` from `/api/meta` and shows the logit next to it. Until the backend sends that field, the UI shows "threshold pending".

## Claims and verdicts

Each claim in `alignments[]` compares one Britannica quote with the matched article:

| `verdict` | UI label | Underline |
|---|---|---|
| `agrees` | Agrees | Green, solid |
| `differs` | Differs | Amber, dashed |
| `contradicts` | Contradicts | Red, wavy |
| `not_in_wikipedia` | Not in Wikipedia | Grey, dotted |

Wikipedia is a comparison source, not ground truth. The labels say whether the texts agree, not which one is right.

- `britannica.quote` must be an exact substring of a `B` passage. When the backend cannot place a quote, it sends `britannica: null` and the UI lists the claim without a mark.
- `wikipedia.quote` must be an exact substring of a `W` passage, or `null` for `not_in_wikipedia`.
- `downgraded: true` shows "Lowered: the model's Wikipedia quote was not in the article".
- `value` and `unit` on a quantity claim fill the quantity drift table.

## Fields the UI already supports, requested from the backend

The UI reads these when present and shows "pending" until then.

| Route | Field | Shape |
|---|---|---|
| topics, compare | `topic.entryId` | The pipeline `entry_id`. Static mode needs it to find the comparison file. |
| topics, compare | `topic.fragment`, `britannica.fragment` | `true` for a fragment. Today the UI infers it from an empty headword. |
| topics | `area`, `teaser`, `verdicts` | Landing subjects: `infectious-disease`, `anatomy`, `geology` or `natural-sciences`; one exact quote; counts per verdict |
| topics, compare | `edition`, `year` | Today every entry says "Not recorded" with `year: null`. |
| compare | `britannica.normalized` | `{ "text": "...", "fixes": [{ "start", "end", "original" }] }` for the Normalized view |
| compare | `britannica.quality` | `{ "dictionaryShare": 0.95, "issues": ["..."], "pdfUrl": "..." }` for the quality chip |
| compare | `britannica.scanSha256`, `britannica.entryId` | Provenance under the scan |
| compare | `wikipedia.revisionId`, `wikipedia.revisionUrl`, `wikipedia.license` | The revision link. The UI assumes CC BY-SA 4.0 when `license` is missing. |
| compare | `candidates[].bm25Rank`, `embedRank`, `rerankRank` | The funnel columns. `match/evidence.jsonl` has them; the adapter drops them today. |
| compare | `obsoleteTerms` | The `obsolete_terms` list from `compare/comparisons.jsonl` |
| compare | `sectionCoverage` | `[{ "section", "covered", "claims" }]`. The older `coverage` rows still work. |
| meta | `matchLogitThreshold` | `MATCH_LOGIT_THRESHOLD` (B4) |

## Static mode

The export (B10 in `docs/handoff-2.md`) writes these files to `deliverables/website/app/data/`:

| File | Same shape as |
|---|---|
| `topics.json` | `GET /api/topics` |
| `meta.json` | `GET /api/meta` |
| `cases.json` | `GET /api/cases` |
| `compare/index.json` | A map from `entry_id` to a file name |
| `compare/<file>.json` | `GET /api/compare` for one entry |
| `chat-recorded.json` | A list of recorded runs: `question`, `topic`, `answer`, `citations`, `grounding`, `trace`, `runDir` |

File names replace every character outside `[A-Za-z0-9_-]` in `entry_id` with `_`.

In static mode the app searches `topics.json` in the browser (headword and title, case-insensitive), then loads the entry's file through `compare/index.json`. It makes no call to `/api`. The agent panel offers only the recorded questions and marks each answer "Recorded run" with its run directory.

Build it with `npm run build:static`. It writes the app to `deliverables/website/app/` with relative paths, so it works under any base path.

Until B10 lands, `web/scripts/export-static.py` writes the same files from the backend's own `WebAdapter` into `web/static-data/`, which the Cloudflare build serves. It adds three things a static host needs: `topics[].entryId`, `britannica.blocks` (the Parse boxes, because `/api/scans/<page>.json` is not available) and a relative `britannica.imageUrl` (`scans/<file>`). It also adds `meta.matchLogitThreshold` from `config.py`.

## Example payloads

`web/api-examples/` holds sample replies generated from the mock by `npm run examples`. They show the shapes; they are not evidence. The live replies above are.
