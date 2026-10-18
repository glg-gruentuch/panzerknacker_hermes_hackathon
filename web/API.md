# Backend API for the web UI

The UI calls five endpoints under `/api`. In development, Vite proxies `/api/*`
to `VITE_BACKEND_URL` (default `http://localhost:8000`), so the backend needs no
CORS setup. The TypeScript source of truth is [`src/api/types.ts`](src/api/types.ts);
real example payloads are in [`api-examples/`](api-examples/) (regenerate with
`npm run examples`).

Errors: return a non-2xx status with JSON `{"detail": "..."}` (FastAPI's default
shape). The UI shows `detail` to the user, so write it as a sentence.

| Endpoint | Purpose | Example |
|---|---|---|
| `GET /api/topics` | Every indexed Britannica page, for search suggestions and the landing index | [topics.json](api-examples/topics.json) |
| `GET /api/compare?q=blood` | The pair of texts, match scores, aligned claims, vocabulary, coverage | [compare_q-blood.json](api-examples/compare_q-blood.json) |
| `POST /api/chat` | One question to the agent, answered with citations | [chat.json](api-examples/chat.json) |
| `GET /api/cases` | The six documented agent cases (3 work, 3 fail) | [cases.json](api-examples/cases.json) |
| `GET /api/meta` | Dataset versions, models, how the 100 pages were sampled | [meta.json](api-examples/meta.json) |

## Where each required model shows up

| Model | Fills these fields | Where the user sees it |
|---|---|---|
| Nemotron Parse 3.5 | `britannica.rawText` and `britannica.passages` | Left column: Original text and Summary |
| Nemotron-3-Embed-VL | `match.embedScore`, `candidates[].embedScore` | Match card, "Other candidates" table |
| Nemotron 3-Rerank-VL | `match.rerankScore`, `candidates[].rerankScore`, `citations[].rerankScore` | Match card, uncertainty state, the evidence list under each answer |
| LanceDB | Retrieval behind `/compare` and `/chat` | The "How this answer was made" trace |
| Hermes Agent + Nemotron 3.5 Super VL | `answer`, `grounding` | Agent panel |

Put the real model names and timings in `trace` on every chat response. It is
how judges see the pipeline working.

## `GET /api/topics`

Return `{ "topics": TopicSummary[] }`, one entry per indexed Britannica page.
The landing page groups them by subject, so fill these fields:

| Field | What to send |
|---|---|
| `area` | One of `infectious-disease`, `anatomy`, `geology`, `natural-sciences`, or `null` to keep the page out of the subject lists (search still finds it). |
| `teaser` | One short sentence from the Britannica entry, quoted exactly. Featured articles show it. |
| `verdicts` | Counts of the claims in `/compare`: `{ "correct": 4, "partly": 1, "wrong": 1 }`. `null` when no claims were compared. |

The four subjects, their plates and which articles are featured live in
`src/config/areas.ts`. Change a subject's slug there and here together.

## `GET /api/compare?q=<topic>`

Return **404** when nothing in the index matches `q`; the UI then offers the
topic list. Otherwise return a `Comparison`. The rules that matter:

**Passage ids are the citation keys.** Number Britannica passages `B1, B2, …`
and Wikipedia passages `W1, W2, …`, in reading order. The agent cites these
exact ids, and the UI scrolls to and highlights `[data-pid="B3"]` when a
citation is clicked.

**Two versions of the Britannica text.** `britannica.rawText` is everything
Nemotron Parse read off the page, unedited: running heads, neighbouring
entries, long-s (ſ) and OCR errors included. The UI shows it under
"Original text". `britannica.passages` is the entry itself, cleaned and split;
the UI shows it under "Summary", and it is what the agent cites.

**`section`**: for Wikipedia, the section heading, `"Introduction"` for the lead.
Britannica: the headword, or a sub-entry name (`"TRANSFUSION"`) when the page
has one; the UI prints a heading whenever it changes.

**`wikipedia: null` means no credible counterpart.** Send `match.strength:
"none"`, keep `candidates` filled, and explain why in `match.reasons`. The UI
shows the uncertainty instead of a comparison. The demo uses rerank ≥ 0.75 for
`strong`, 0.5–0.75 for `partial`, < 0.5 for `none`; pick your own thresholds
and say so in `reasons`.

**Alignments** pair one claim across the two texts:

```json
{
  "id": "a6",
  "kind": "revised",
  "verdict": "wrong",
  "label": "Where blood is made",
  "britannica": { "passageId": "B4", "quote": "The blood is made from the chyle" },
  "wikipedia": { "passageId": "W4", "quote": "Blood cells are produced in the bone marrow" },
  "note": "In 1797, blood is made from digested food. Today, the cells come from the bone marrow."
}
```

- `quote` must be an exact substring of that passage's `text` (matched case-
  insensitively, first occurrence). A quote that is not found is silently not
  highlighted, so validate this server-side.
- `kind` is the language-versus-knowledge call the challenge asks for:

  | kind | glyph | meaning |
  |---|---|---|
  | `retained` | = | Same fact, said much the same way |
  | `reworded` | ≈ | Same fact, new words: a change in **language** |
  | `revised` | ≠ | The claim itself changed: a change in **knowledge** |
  | `dropped` | − | Only in Britannica (`wikipedia: null`) |
  | `added` | + | Only in Wikipedia (`britannica: null`) |

- `verdict` says whether the Britannica claim holds up today. It drives the
  only colour in the UI: the claim is underlined red (wavy) when `wrong`,
  yellow (dashed) when `partly` (half right, or true then but not now), and
  green (solid) when `correct`. Use `null` when there is no Britannica side
  (`kind: "added"`).
- `kind` and `verdict` are independent: a claim can be `reworded` and
  `correct` (same fact, new words) or `revised` and `partly` (an incurable
  disease that became curable).
- Keep `label` short (2–4 words) and `note` to one or two sentences.

**`vocabulary`**: up to ~10 terms per side that mark that text against the
other (`per1k` = uses per 1,000 words), plus a list of `shared` terms. Leave out
stopwords and the topic's own name.

**`coverage`**: topic rows with each text's share (0–1). A `0` is drawn as
"missing from this text", which is often the most interesting row. The
NVIDIA topic-modelling workflow is a natural source for these rows.

**`stats`**: words, sentences, average sentence length, distinct terms.
`wikipedia` is `null` when there is no counterpart.

**`suggestedQuestions`**: two or three questions the agent answers well for
this pair. They are shown as one-click prompts.

## `POST /api/chat`

Request:

```json
{ "topic": "Blood", "question": "Which facts about blood survived?", "history": [{ "role": "user", "content": "…" }, { "role": "agent", "content": "…" }] }
```

`topic` is the `topic.label` from `/compare`. Response:

```json
{
  "answer": "Harvey's account … [B5] matches the modern description [W5].\n\nThe red globules [B3] are today's red blood cells [W2].",
  "citations": [{ "id": "B5", "source": "britannica", "passageId": "B5", "rerankScore": 0.94 }],
  "grounding": "supported",
  "trace": [
    { "step": "Embed question", "model": "Nemotron-3-Embed-VL", "detail": "1 query", "ms": 38 },
    { "step": "Search both collections", "model": "LanceDB", "detail": "top 20 per side", "ms": 12 },
    { "step": "Rerank passages", "model": "Nemotron 3-Rerank-VL", "detail": "kept 6 above 0.5", "ms": 210 },
    { "step": "Write answer", "model": "Hermes Agent · Nemotron 3.5 Super VL", "detail": "2 tool calls", "ms": 3400 }
  ]
}
```

- Answer format: plain text. A blank line starts a paragraph, lines starting
  with `- ` form a list, `[B2]` / `[W5]` become clickable citation chips. No
  other markdown is rendered.
- Cite only ids that exist in the current comparison; unknown ids render as a
  dashed, unclickable chip.
- `grounding`: `supported` when every claim is cited, `partial` when some are
  not, `unsupported` when the agent could not answer from the sources. The UI
  labels these green, yellow and red, the same scale as the claims, which
  makes the failure cases easy to see in the demo video.

## `GET /api/cases`

The six cases the challenge requires: three with `outcome: "success"` and three
with `outcome: "failure"`. Each has a `question` and `topic` that the "Replay
this case" button sends through `/compare` and `/chat`. Make the replay
reproduce the documented answer.

## `GET /api/meta`

Dataset versions and download dates (required for reproducibility), the model
list, and the sample-selection method. The Britannica dataset revision in the
demo (`309f765`, last modified 2026-07-16) is the real one from Hugging Face.
Fill in the Wikipedia snapshot and download dates.

## Page scans

`britannica.imageUrl` can point at anything the browser can load: a static
file the backend serves (`/api/scans/<pageId>.jpg`), or a data URL. The
dataset stores images in parquet, so the simplest route is to export the 100
sampled pages to files during indexing.
