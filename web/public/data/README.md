# Site data

The pipeline writes these files. In live mode (`VITE_API_MODE=live`) the UI
reads them directly, and Cloudflare Pages serves them as static files.

```
topics.json            { "topics": TopicSummary[] }   one entry per indexed page
compare/<slug>.json    Comparison                     one file per topic slug
cases.json             { "cases": AgentCase[] }       the 3 success and 3 failure cases
meta.json              Meta
```

The shapes are in `../../src/api/types.ts` and `../../API.md`.
Each file is the body that the matching `GET /api/...` endpoint would return.
Do not put demo data here: the UI shows these files as real results.
