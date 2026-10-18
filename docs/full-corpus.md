# Full-corpus mode

The challenge sample is the fixed 100-scan manifest. The pinned Parquet source
holds 2,573 scans from 195 volumes. Full-corpus mode runs the same stages over
every source row without touching the 100-scan artifacts.

## What the mode changes

- `--all` sets `CORPUS_SCOPE=full`. The pipeline reads `data/full-manifest.json`,
  built from the pinned Parquet file, and validates every image checksum.
- The default work directory is `artifacts-full/`. The default evidence store
  is `data/team-full.lancedb`. The event run keeps `artifacts/` and
  `data/team.lancedb`.
- `data/full-manifest.json` is generated, not committed. It records every row,
  the image hash, and the manifest digest.
- A continuation join never crosses a volume boundary. Without this guard, a
  repeated headword at the start of a new volume would merge two unrelated
  entries.
- The embedding query is capped at 1,000 characters. The service allows 2,000
  characters but only 512 query tokens, and old encyclopaedia prose tokenizes
  worse than modern English. The reranker keeps the event-run limit of 2,000
  characters because the shortlist vector does not decide the match.

## Prepare the scans

```sh
uv run nemotron-challenge data fetch --all
uv run nemotron-challenge data show --all > /tmp/full-manifest.json
```

The fetch verifies the Parquet checksum, builds the full manifest, and writes
all scans to `data/raw/britannica`. The source is 373,874,192 bytes of encoded
images. A second fetch rewrites only damaged or missing files.

## Calibrate the match threshold first

Match confidence is a raw reranker logit, and the scale depends on the backend.
The packaged `-5.5` constant came from the hosted NIM relay. A pinned GPU
container can need another value. Calibrate on the event sample in a scratch
directory before a full match run:

```sh
mkdir -p artifacts-calib
ln -sfn ../artifacts/extract artifacts-calib/extract
CHALLENGE_DB_PATH=data/team-calib.lancedb MATCH_THRESHOLD=-999 \
  uv run nemotron-challenge run match --work-dir artifacts-calib
```

Inspect `artifacts-calib/match/matches.jsonl`, compare the confidences with the
labels in `artifacts/match/calibration.json`, then delete the scratch files.
Set the chosen value with `MATCH_THRESHOLD` for the real run. `MATCH_LIMIT`
caps one pass for a quick check.

## Run the stages

```sh
uv run nemotron-challenge run extract --all
MATCH_THRESHOLD=<calibrated> uv run nemotron-challenge run match --all
uv run nemotron-challenge run compare --all
CLAIMS_WORKERS=16 CLAIMS_DEADLINE_SECONDS=14400 \
  uv run nemotron-challenge run claims --all
SITE_OUT=deliverables/website-full \
  uv run nemotron-challenge run site --all
EXPORT_OUT=deliverables/website-full/app/data \
  uv run nemotron-challenge run export --all
EVALUATE_WRITE_DOCS=0 uv run nemotron-challenge run evaluate --all
```

Every stage resumes from its saved artifacts. Extract skips pages with a saved
raw Parse reply. Match skips entries already in `match/evidence.jsonl`. Claims
skips records whose entry and revision are in `claims/claims.jsonl` and reuses
cached model replies.

Claims has a default time cap of 4.5 hours per pass and skips work at the cap.
Repeat the claims command until `entries_skipped_by_time_cap` is zero. The
stage is the expensive one: each matched entry makes one extraction call and
one judge call per claim, with up to eight claims.

The `agent` stage runs the fixed case studies in `docs/cases`. It is not a
per-scan stage, so it does not change with the corpus size.

## Runtime and disk

- Extract: about 2 to 7 seconds per scan on the shared Parse endpoint. It is
  serial and polite to the shared service. Expect a few hours for 2,573 scans.
- Match: about 1 to 2 seconds per entry, plus one article read per match.
- Claims: several hours with 16 workers, depending on the model queue and the
  number of claims. Token use is high; check the Token Factory quota first.
- Site: about 1.8 seconds per compiled PDF.
- Disk: 374 MB of scans, article JSON under `artifacts-full/match/articles/`,
  and a claim cache with several files per entry.

## Honest limits

- Extraction failures stay in `extract/coverage.json`. They are not replaced
  with guessed text.
- Match precision on the event sample was 0.35 overall and 0.667 for headword
  entries. A full run will carry the same precision unless the threshold and
  query method change.
- The full run does not change the challenge deliverable in `artifacts/` or
  `deliverables/website/`.
