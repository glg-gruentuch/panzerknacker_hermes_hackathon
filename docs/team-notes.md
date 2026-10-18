# Team notes

Facts collected on 2026-10-18 from the organizer sources below.
The starter docs in this folder give the details. This file records what they leave out and where the sources disagree.

## Sources

- [Starter repository](https://github.com/october-18-hackathon/nemotron-agentic-ai-challenge), imported at commit `88abda0`.
- [Participant brief (PDF)](../Nebius%20NVIDIA%20Hackathon%20Challenge%20Participant%20Brief.pdf). It has the judging rubric.
- [Nebius participant setup guide](https://github.com/dariolaportanebius/nebius-starter-skill/blob/hackathon-participant-guide/README.md). It has accounts, team limits, and workloads.
- [NVIDIA topic modeling workflow](https://build.nvidia.com/station/topic-modeling).
- [Nemotron 3 Embed ranks #1 on RTEB](https://huggingface.co/blog/nvidia/nemotron-3-embed-wins-rteb).
- [Organizer challenge document](https://docs.google.com/document/d/132-v2EoYUcxif6GjlnfrjfD7BkmeScYstDbRwXN5F6g/edit).

## Where the sources disagree

| Topic | Starter repo | PDF brief | Follow |
| --- | --- | --- | --- |
| Video length | 3 to 5 minutes | 3 minutes | **3 minutes** (the brief says its rule overrides the starter) |
| Page selection | Fixed 100-scan manifest | 100 pages, random or by hand; the fixed sample is a starting point | Fixed manifest, unless we choose otherwise |
| Parse version | Parse 3.5 | Parse 3.5 | The first web brief said "Parse 3.0". Use **Parse 3.5** |

## Judging rubric (100 points)

| Criterion | Points | What earns them |
| --- | --- | --- |
| Completion of specs | 20 | 5 checks of 4 points: LaTeX archive site, 100-page matching coverage, comparison analysis with citations, Hermes agent + 3 success / 3 failure cases, repo + video |
| Creativity | 20 | Originality 10, value to users exploring the differences 10 |
| Nemotron 3.5 Super VL | 20 | Integration, comparison quality, grounding in both sources, failure handling (5 each) |
| Nemotron Parse 3.5 | 15 | Integration, extraction fidelity with errors identified, structure preserved into LaTeX (5 each) |
| Embedder + Reranker | 15 | Embedder 5, reranker used downstream 5, both working together in matching 5 |
| Hermes extension | 10 | Team-built tool, skill, or workflow 5; shown end to end to help 5 |

Absent or unverified work scores 0. Show execution evidence for each claim.

## Services and endpoints

| Service | Where | Key |
| --- | --- | --- |
| Parse 3.5 (`nvidia/nemotron-3.5-parse`) | Shared organizer endpoint, see `.env.example` | None |
| Wikipedia BM25 API (7,182,883 English articles) | Shared organizer endpoint, see `.env.example` | None |
| Embed VL + Rerank VL | Our Nebius AI Cloud project, one Docker image | Our endpoint token |
| Super VL (`nvidia/Nemotron-3.5-Super-VL`) | Nebius Token Factory | Our Token Factory key |

The Parse endpoint has interactive API docs at `/docs` on its host.

## Data

- **Britannica:** 2,573 page scans from 1768 to 1860. The scans have no text. The starter manifest selects 100 of them with seed `20261016`. `uv run nemotron-challenge data fetch` downloads them (about 357 MiB once).
- The source `id` is a volume ID and repeats. Identify a scan by manifest page ID, row index, and image checksum.
- **Wikipedia:** we do not download it. The shared API searches the pinned snapshot (`wikimedia/structured-wikipedia`, revision `417c267`). It returns candidates only.

## Team limits on Nebius AI Cloud

- One GPU: RTX PRO 6000 Blackwell, 96 GB. Platform `gpu-rtx6000-a`, preset `1gpu-24vcpu-218gb`.
- The embedder and reranker share one container, so one GPU endpoint serves both.
- While that endpoint runs, develop on CPU: a CPU DevLab or CPU VM, 20 vCPUs total.
- 3 VMs total, 4 disks, 500 GiB of SSD, 1 public IP, 1 registry, 1 bucket (create it at 200 GiB).
- A stopped endpoint loses its container disk. Keep outputs in the bucket.
- Region: `uk-south2`. Project names look like `groupNN-project`.

## Local setup on Intel Macs

`uv sync --locked` fails on Intel macOS: `lancedb==0.40.0` has no `macosx_x86_64` wheel. The last version with one is 0.25.3.
Apple Silicon Macs, Linux, and the Nebius CPU DevLab install the lock as it is.

**Decision (2026-10-18):** we develop and run the pipeline on a Nebius CPU DevLab. Select **Without GPUs** so the GPU stays free for the retrieval endpoint.

## Retrieval service limits

- One request at a time, queue of 4. A full queue returns `429` with `Retry-After: 1`.
- Embeddings: 1 to 16 items per request, 2,048-dimension unit vectors.
- Rerank: 1 to 32 documents. Scores are raw logits, not probabilities.
- Text documents up to 8,192 tokens. The service rejects longer input and does not cut it. Split long text ourselves.
