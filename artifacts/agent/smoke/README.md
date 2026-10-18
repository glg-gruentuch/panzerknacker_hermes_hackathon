# Hermes plugin smoke test (synthetic)

Purpose: prove that the challenge Hermes profile loads the `nemotron-challenge`
plugin and that both tools execute inside a real run. This is a mechanical
wiring check, not challenge evidence. The comparison records in
`compare/comparisons.jsonl` are synthetic fixtures and are labelled as such.
Real agent cases run only after the match and compare stages produce real
records (`artifacts/agent/cases.json`).

Commands used:

```sh
HERMES_HOME="$PWD/data/hermes" \
/opt/hermes/.venv/bin/hermes chat -q "<question>" --toolsets nemotron_challenge
```

## Result (2026-10-18)

- `run-success.txt` — success path. The agent called `challenge_search` and
  `challenge_compare` and reported the entry ID, the article title, and both
  citation sources. Session `20261018_122540_d2d249`, 6 tool calls, 9 s.
- `run-missing.txt` — missing-evidence path. The agent tried several queries,
  found no stored comparison, said so, and offered the correct next step
  (provide an entry ID). Session `20261018_122613_3b776a`, 22 tool calls, 16 s.
- `run-success-attempt1-no-matches.txt` — the failed first attempt, kept
  separate. The plugin read the profile's `PANZERKNACKER_ARTIFACTS` value, not
  the shell value, so it did not see the fixture directory. Fixed by pointing
  the profile `.env` at the fixture directory for the test and restoring it
  afterwards.

Raw session transcripts stay in `data/hermes/sessions/` and are not committed.
