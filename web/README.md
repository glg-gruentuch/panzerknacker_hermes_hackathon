# Knowledge Across Time: web UI

The front end for *Britannica Meets Wikipedia*, our project for the medicine
challenge. Type a medical topic and the app shows the historical Encyclopaedia
Britannica entry (1768–1860) beside its closest Wikipedia article. It marks
which claims held, which only changed their wording, and which turned out to
be wrong, and an agent answers questions about the differences with citations
into both texts.

React + TypeScript + Vite. No UI kit, no CSS framework: plain CSS modules on a
small token set.

## Run it

Run these commands in the `web/` folder.

```bash
npm install
npm run dev          # http://localhost:5173
```

By default the UI runs on **built-in sample data** (five medical topics), so it
works before the backend exists. To use the real backend:

```bash
cp .env.example .env
# set VITE_API_MODE=live and VITE_BACKEND_URL=http://localhost:8000
npm run dev
```

The dev server proxies `/api/*` to the backend. **[API.md](API.md) is the
contract for the backend team**, with example payloads in
[`api-examples/`](api-examples/).

| Script | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Typecheck, then production build into `dist/` |
| `npm run typecheck` | TypeScript only |
| `npm run examples` | Rewrite `api-examples/` from the mock data |

Link straight to a topic with `?q=`, for example `http://localhost:5173/?q=consumption`.

## What's on screen

- **Headword search.** The search field is set like an encyclopaedia headword
  ("BLOOD, *in medicine.*"). Suggestions list every indexed page and how well
  it matched.
- **Side by side.** Britannica on the left, Wikipedia on the right. The
  Britannica column switches between **Summary** (the entry, cleaned and split
  into the passages the agent cites), **Original text** (everything Nemotron
  Parse read off the page, unedited) and **Page scan**. Select an underlined
  phrase to draw a line to its modern counterpart and read what changed, or
  step through every claim in order.
- **Colour means one thing: does the old claim hold up today?**

  | Underline | Verdict | Meaning |
  |---|---|---|
  | red, wavy | Wrong | Contradicted by current knowledge |
  | yellow, dashed | Partly correct | Half right, or true then but not now |
  | green, solid | Correct | Still true |

  The agent's answers use the same scale (supported, partly supported, not
  supported), and so do the agent cases (works, fails).
- **Match.** One line above the texts says how sure the pairing is. Details
  show the embedding and rerank scores, why the pair was matched, and the
  other candidates. A doubtful match opens its reasons by default, and a page
  with no credible counterpart says so instead of forcing a comparison.
- **What changed.** How many old claims are wrong, partly correct or correct,
  then every claim grouped by verdict, each tagged as new words (a change in
  language) or new knowledge. Below: the words that mark each text, topic
  coverage and sentence statistics.
- **Ask the agent.** Docked on the right on wide screens; hide it to a thin
  rail with the button in its header (the choice is remembered). A drawer on
  tablets, a tab on phones. Citations (B = Britannica, W = Wikipedia) jump to
  the passage.
- **Agent cases** and **Data and models** are their own pages
  (`?page=cases`, `?page=sources`).

## Demo path (for the 5-minute video)

1. Landing: point at the claim key and at the index grouped by match strength.
2. Search **Blood**, select the red "The blood is made from the chyle" to
   show the line to "bone marrow", then **Step through** a few claims.
   Switch the left column to **Original text** to show the raw parse.
3. **What changed**: "4 of 10 claims from 1797 are wrong", then the
   vocabulary (vein, aliment versus cells, haemoglobin).
4. Ask "What did people in 1797 get wrong about blood?" and click a citation.
5. Search **Consumption**: the headword differs (Tuberculosis), yet it matches
   on content. Ask whether 1842 thought it was contagious.
6. Search **Animal spirits**: no clear counterpart, so the uncertainty shows.
7. **Agent cases**, then replay a failure.

## Layout

```
src/
  api/types.ts        the data contract (mirrors API.md)
  api/client.ts       fetch wrapper; mock or live by VITE_API_MODE
  api/mock/           sample topics, keyword fallback for chat, example cases
  components/         one component + one CSS module each
  lib/                change kinds, text highlighting, chat state, breakpoints
  styles/tokens.css   colours, type, spacing
```

Breakpoints: ≥ 1200px puts the agent beside the texts; 760–1199px opens it as
a drawer; below 760px the app switches to tabs (year · Today · Changes · Ask).

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

## About the sample data

The mock Britannica passages are written in period style for the demo. They are
**not** text from the dataset. The Wikipedia passages paraphrase the real
articles. The six agent cases are placeholders that show the format. All of it
is replaced once the backend runs in live mode. The "Sample data" badge in the
header shows while mock data is in use.
