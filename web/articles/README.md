# Articles

Each file in this folder is one article on the site: a Britannica entry, its
Wikipedia counterpart, and how the claims compare. The site finds every
`.json` file here by itself. No other file needs to change.

## Add an article

1. Copy an existing file, for example `blood.json`, to `<slug>.json`.
   Use lowercase letters, digits and hyphens for the slug: `yellow-fever.json`.
2. Set `summary.slug` to the same slug.
3. Replace the content. The fields are listed below.
4. Run the check in the `web/` folder:

   ```bash
   npm run check-articles
   ```

5. Open the site with `npm run dev` and search for the article.
6. Commit only the new file, then push.

The Cloudflare build runs the same check. If a file has a problem, the build
stops, names the file and the field, and the current site stays online.

Do not edit other articles to add yours. To replace an article, change only
its own file.

## Fields

The full types are `ArticleFile` in
[`src/api/demo/article.ts`](../src/api/demo/article.ts) and the shapes in
[`src/api/types.ts`](../src/api/types.ts).

| Field | What to put in it |
|---|---|
| `demo` | `true` for invented demo text. Leave it out or set `false` for real articles. The header shows "Demo data" while any article has `true`. |
| `summary` | `slug`, `label` (what a user types, "Blood"), `headword` ("BLOOD"), `edition`, `year`, `match` (`strong`, `partial` or `none`), `wikipediaTitle` (or `null`), `area` (see below), `teaser` (or `null`) |
| `aliases` | Optional. Other search words, for example `["tuberculosis", "phthisis"]`. Two articles cannot share a label or alias. |
| `britannica` | `pageId`, `headword`, `edition`, `year`, `volume`, `meta`, `imageUrl` (or `null`), `sourceUrl` (or `null`), `rawText` (everything Parse read), `passages` (`B1`, `B2`, …) |
| `wikipedia` | `identifier`, `title`, `url`, `dateModified`, `passages` (`W1`, `W2`, …). Use `null` when no article matches. |
| `match` | `strength`, `embedScore` and `rerankScore` (0 to 1), `reasons` (plain sentences) |
| `candidates` | Other Wikipedia articles that scored: `title`, `url`, `embedScore`, `rerankScore`. Can be `[]`. |
| `alignments` | One entry per claim: `id`, `kind`, `verdict`, `label`, `note`, and a `britannica` and/or `wikipedia` anchor `{ "passageId": "B2", "quote": "..." }` |
| `coverage` | Share of each text per sub-topic: `topic`, `britannica`, `wikipedia` (0 to 1) |
| `suggestedQuestions` | Questions shown under the agent panel |
| `answers` | Optional. Scripted demo-chat answers, keyed by the exact question |

`area` is one of `infectious-disease`, `anatomy`, `geology`,
`natural-sciences`, or `null` to keep the article out of the subject lists
(search still finds it). To feature an article on the landing page, add its
slug to `featured` in [`src/config/areas.ts`](../src/config/areas.ts).

The site computes verdict counts, vocabulary and text stats from the file.
Do not add them by hand.

## What the check looks for

- The file is valid JSON and the slug matches the file name.
- Every required field is present and has the right type. Unknown fields are
  refused, so a typo such as `"alignment"` is caught.
- Passage IDs are unique and follow `B1`, `B2`, … and `W1`, `W2`, ….
- Each alignment points at a passage that exists, and its `quote` is an exact
  part of that passage. The page underlines that exact text.
- The `teaser` is quoted exactly from a Britannica passage.
- Scripted answers cite passages that exist.
- No two articles share a label or alias.

## Real articles from the backend

The backend can export selected articles in this same format. Put each export
here as its own file, without `"demo": true`, and delete the demo file it
replaces.
