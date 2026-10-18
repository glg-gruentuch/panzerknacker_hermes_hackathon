# Knowledge Across Time: web UI

The front end for *Britannica Meets Wikipedia*. Type a topic and the app shows
a historical Encyclopaedia Britannica entry (1768 to 1860) beside its matched
Wikipedia article. Each Britannica claim is marked by how the article compares
with it, and an agent answers questions with citations into both texts.

React, TypeScript and Vite. No UI kit and no CSS framework: plain CSS modules
on a small token set.

## Run it

Run these commands in the `web/` folder.

```bash
npm install
npm run dev          # http://localhost:5173, reads the backend at /api
```

`npm run dev` reads the FastAPI backend. Start it from the repository root
with `uv run uvicorn nemotron_challenge.api:app --port 8000`, or point
`VITE_BACKEND_URL` at another host. Without a backend, use the sample data:

```bash
npm run dev:mock
```

| Script | What it does |
|---|---|
| `npm run dev` | Dev server on live data (`VITE_API_MODE=live`, the default) |
| `npm run dev:mock` | Dev server on built-in sample data |
| `npm run build` | Typecheck, then a live build into `dist/`. CI runs this. |
| `npm run build:static` | Static build into `../deliverables/website/app/`, read from exported JSON |
| `npm run build:cloudflare` | Static build into `dist/` with `static-data/` and the scans, for the Cloudflare deploy |
| `npm run typecheck` | TypeScript only |
| `npm run examples` | Rewrite `api-examples/` from the mock data |

[API.md](API.md) lists what the UI reads from each route, with saved live
replies in `artifacts/web/`. Only `npm run dev:mock` includes the sample data;
every other build leaves it out.

Link straight to an entry with `?q=`, for example `http://localhost:5173/?q=coinage`.

## Deploy to Cloudflare

Cloudflare Workers builds and serves the site from this repository. Each push
to `landing-page` starts a new deploy. The dashboard settings are:

| Setting | Value |
|---|---|
| Production branch | `landing-page` |
| Root directory | `/web/` |
| Build command | `npm ci && npm run build` |
| Deploy command | `npx wrangler deploy` |

Cloudflare does not run the Python backend, so the deployed site reads a
static export of the pipeline artifacts. `wrangler.jsonc` has a
`build.command`, so `npx wrangler deploy` first runs `npm run build:cloudflare`:
a static build (`VITE_API_MODE=static`), then a copy of `static-data/` to
`dist/data/` and of `deliverables/website/assets/scans/` to `dist/scans/`. The
dashboard settings above stay as they are.

`static-data/` holds the export of commit `df45ca8` (`static-data/SOURCE.json`
records the commit). To export newer artifacts, run from the repository root:

```bash
uv run python web/scripts/export-static.py --commit <commit> --out web/static-data
```

The script uses the backend's `WebAdapter` and recorded-run loader, so the files
have the same shape as the live API, and it refuses to run if `artifacts/`
differs from that commit. No model is called.

`wrangler.jsonc` names the Worker and tells it to serve the built files in
`dist/`. The name in that file must match the Worker name in Cloudflare.

## What's on screen

- **Landing page.** An engraved plate from the Britannica sits behind the
  page. The search field is set like an encyclopaedia headword. Below it, four
  subjects open into short lists of articles once the backend tags them.
- **Side by side.** Britannica on the left, Wikipedia on the right. The
  Britannica column has four views: **Summary** (the entry's passages, which
  the agent cites), **Normalized** (long-s and OCR fixes marked), **Original
  text** (everything Nemotron Parse read off the page) and **Scan** (the page,
  with Parse's blocks outlined and the selected claim's block boxed). A quality
  chip shows the share of dictionary words, known OCR issues and the compiled
  PDF when the backend sends them. Fragments, which continue an entry from a
  page outside the sample, are labelled as such.
- **Verdicts.** Colour means one thing: how the Wikipedia article compares with
  a Britannica claim. Wikipedia is a comparison source, not ground truth.

  | Underline | Verdict |
  |---|---|
  | red, wavy | Contradicts |
  | amber, dashed | Differs |
  | green, solid | Agrees |
  | grey, dotted | Not in Wikipedia |

  Every model-written explanation carries an "Inference" tag. Source quotes
  never do.
- **Match.** The bar above the texts shows the match strength and the raw
  reranker logit. Details show the funnel for every candidate: BM25 rank,
  embedder rank and similarity, reranker rank and logit, and the change in
  rank. The threshold comes from `/api/meta`.
- **What changed.** Verdict counts, the claims grouped by verdict with both
  quotes, quantity drift, distinctive vocabulary, obsolete terms and section
  coverage. A stage that has not run shows "pending".
- **Ask the agent.** Docked on the right on wide screens, or hidden to a thin
  rail. A recorded run is marked "Recorded run" with its run directory. In the
  static build the panel offers only recorded questions.
- **Agent cases** and **Data and models** are their own pages
  (`?page=cases`, `?page=sources`). They list exactly what the backend sends.

## Demo path

1. Landing: the plate, the search, the subjects.
2. Search **coinage**: a clear match. Select a claim, step through the claims,
   then open **Scan** to show the claim's block boxed on the page.
3. **What changed**: verdict counts and the claims with both quotes.
4. **Details**: the retrieval funnel and the reranker logits.
5. Search **page-0013-fragment**: a fragment with no clear match.
6. Search **willin**: an unmatched entry and its closest candidates.
7. **Agent cases**.

## Layout

```
src/
  api/types.ts        the UI's data model
  api/normalize.ts    maps backend replies onto it; missing data becomes "pending"
  api/client.ts       live, static or mock, by VITE_API_MODE
  api/mock/           sample topics and one real entry (page 13), only in dev:mock
  components/         one component + one CSS module each
  lib/                change kinds, text highlighting, chat state, breakpoints
  styles/tokens.css   colours, type, spacing
```

Breakpoints: ≥ 1200px puts the agent beside the texts; 760–1199px opens it as
a drawer; below 760px the app switches to tabs (Britannica, Today, Changes, Ask).

### Design notes

Minimal on purpose, refined with [Impeccable](https://impeccable.style)
(installed locally with `npx impeccable install`; not committed).

- **Colour** is reserved for the verdict. Everything else is ink on white with
  hairline dividers. Each verdict also has its own underline style and icon,
  so colour is never the only cue.
- **Type**: Libre Caslon for Britannica (Caslon was the British typeface of
  the 1700s); Libre Franklin, a revival of Franklin Gothic (1902), for the
  modern side and the interface.
- To check a page against Impeccable's design rules, install it, then run
  `.claude/skills/impeccable/scripts/impeccable detect http://localhost:5173/`.

## Subjects and plates

`src/config/areas.ts` lists the subjects: label, one-line description, plate,
and which articles to feature first. The backend tags each topic with a
subject slug (see API.md).

The plates come from the same Hugging Face dataset as the sample (revision
`309f765`, CC0, National Library of Scotland). `scripts/prepare-plates.py`
turns the paper white, crops the margins and writes `public/plates/` and
`src/config/plates.json`, which records each plate's page ID, row and source
checksum. To change a plate, edit the list at the top of the script and run it
from the repository root:

```bash
uv run nemotron-challenge data fetch
uv run --with pillow python web/scripts/prepare-plates.py
```

| Plate | Subject | Source row | In our 100-page sample |
|---|---|---|---|
| Anatomy (skeleton) | Anatomy and physiology, and the default | 1274 | No |
| Helminthology (parasitic worms) | Infectious disease and fevers | 651 | Yes |
| Hver, or boiling fountain (geyser) | Geology | 1369 | No |
| Electricity | Natural sciences | 1446 | No |

## About the sample data

`npm run dev:mock` serves eight sample topics and one real entry. The sample
Britannica passages are written in period style for UI work; they are **not**
text from the dataset, and the Wikipedia passages paraphrase the articles. The
real entry is page 13 (a SHIP-BUILDING fragment), built from the committed
Parse output, QA notes and scan; its match and claims are pending. The "Sample
data" badge in the header shows while mock data is in use.
