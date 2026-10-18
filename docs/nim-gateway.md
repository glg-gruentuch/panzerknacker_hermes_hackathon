# Use NVIDIA hosted NIM for retrieval

The team's retrieval service in `docs/model-service.md` needs a GPU. Until the
Nebius deployment is ready, the same two models are available from NVIDIA's
hosted NIM API. The hosted routes use another request shape than the container,
so this repository adds a small loopback gateway. The gateway serves the
container contract and calls the hosted API.

The client, the stage code, and the evidence format do not change.

## Start

Put the key in `.env`. Do not commit it.

```dotenv
NVIDIA_API_KEY=<your-key>
RETRIEVAL_BASE_URL=http://127.0.0.1:8001/v1
```

Run the gateway in its own terminal:

```sh
uv run nemotron-challenge gateway --port 8001
```

Check it:

```sh
curl --fail http://127.0.0.1:8001/health
curl --fail http://127.0.0.1:8001/v1/models
uv run nemotron-challenge doctor --live
```

The gateway binds to loopback only. Set `NIM_GATEWAY_TOKEN` if another local
process must present a Bearer token. The client sends `RETRIEVAL_API_KEY`; leave
that value empty for the gateway.

## Routes

| Route | Hosted counterpart |
| --- | --- |
| `GET /v1/models` | none; the catalog is local |
| `POST /v1/embeddings` | `https://integrate.api.nvidia.com/v1/embeddings` |
| `POST /v1/rerank` | `https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-vl-1b-v2/reranking` |

The embedder maps the challenge `input_type: document` to the hosted
`input_type: passage`. The reranker maps `query` and `documents` to the hosted
`query: {text}` and `passages: [{text}]`, and maps hosted `rankings[].logit` to
`results[].relevance_score`.

Override the upstream routes with `NIM_EMBED_URL` and `NIM_RERANK_URL`.

## Limits

The gateway enforces the limits that the client and the container share: 16
embedding items, 32 reranking documents, 2,000 query characters, 32,000
document characters, and a 24 MiB body. It runs one upstream request at a time
and answers `429` with `Retry-After: 1` when the queue is full. The client
retries `429` and `503`.

The gateway has no tokenizer. It cannot check the 512-token query limit or the
8,192-token document limit before the request leaves the box. The hosted API
rejects text that is too long; the call fails and the stage records the failure.
Keep source text inside the character limits above.

## What the gateway does not do

The hosted embedder accepts text only. An image record returns `422` with a
clear message. The match stage embeds text excerpts, so this does not block it.

## Evidence rules

The hosted API does not report a model snapshot. The gateway reports the
challenge pin in `/v1/models` with `revision_verified: false`, and every reply
carries `backend: nvidia-hosted-nim`. The strict client still checks the model
IDs, the vector size, and the score type.

Do not present a hosted run as a run against the pinned snapshot. Label the
backend in notes and in the report. Re-run the stages against the team
deployment before final submission if the rubric needs the pinned revision.

## Verified on 2026-10-18

Real calls through the gateway with the team key:

- `GET /v1/models` returns both model IDs with `dimensions: 2048`.
- Embedding a query returns 2,048 finite values with unit L2 length. `doctor
  --live` reports `retrieval: ok` together with `wikipedia`, `parse`, and
  `super`.
- Reranking a question against three passages returns raw logits in
  descending order, from `2.83` for the answering sentence to `-6.95` for an
  unrelated one.

The provisional accept threshold of `0.0` in `config.py` came from the
container contract. Hosted logits sit on a different scale for long queries. A
three-entry trial run matched 0 entries with a best logit of `-4.03`. Calibrate
the threshold on the chosen backend before the match stage decides anything.

## Tests

```sh
uv run pytest tests/test_nim_gateway.py
```

The tests use a stub upstream and a real loopback server. They do not call
NVIDIA's API and they do not need a key.
