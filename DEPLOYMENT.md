# ContextIQ — Deployment Guide (v1.0)

Production-quality **local** deployment with Docker Compose.

---

## 1. Why local, not public

ContextIQ depends on **Ollama**, which runs a multi-gigabyte LLM in
process. That has two consequences that make a public/cloud deployment
the wrong choice:

1. **Infrastructure.** Ollama needs significant RAM (and ideally a GPU).
   It does not fit serverless or small PaaS tiers; a public deployment
   means a dedicated (GPU) VM that is costly to keep running.
2. **Product intent.** ContextIQ's premise is *"private — nothing leaves
   your machine."* Hosting the model remotely would send your documents
   to a server, defeating the point.

So ContextIQ ships as a **self-contained local stack** you run with one
command. The application architecture is unchanged.

## 2. Architecture

```
        ┌─────────────────────── your machine ───────────────────────┐
        │                                                             │
browser │   http://localhost:3000        http://localhost:8000       │
  ──────┼──────────────► frontend ······► backend (FastAPI)          │
        │                (Next.js)         │   └─ ChromaDB (EMBEDDED)  │
        │                                  │      → chroma-data volume │
        │                                  ▼                          │
        │                          ollama  (llama3.2)                 │
        │                          → ollama-models volume             │
        └─────────────────────────────────────────────────────────────┘
```

- **ChromaDB is embedded in the backend** (a library, not a server). It
  persists to the `chroma-data` volume — there is no Chroma container.
- The **browser talks to the backend directly** (client-side `fetch`),
  so the backend is published on the host and CORS allows the frontend
  origin.

**Containers:** `frontend`, `backend`, `ollama`, plus a one-shot
`ollama-pull` that downloads the model then exits.
**Volumes:** `ollama-models`, `chroma-data`, `documents`, `hf-cache`.

## 3. Prerequisites

- **Docker Engine 24+** and **Docker Compose v2** (Docker Desktop on
  Windows/macOS includes both).
- **~8 GB free RAM** recommended (Ollama + `llama3.2`), **~10 GB disk**
  (model + images + embedding cache).
- **Internet on first run** — to pull base images, the LLM (~2 GB), and
  the embedding model (~130 MB). Everything runs offline afterward.
- **Optional NVIDIA GPU** — big speedup; see the commented `deploy`
  block in `docker-compose.yml` (needs the NVIDIA Container Toolkit).

## 4. Configuration

All settings are optional and default sensibly. To override, copy the
template and edit it:

```bash
cp .env.docker.example .env
```

| Variable | Default | Purpose |
|---|---|---|
| `FRONTEND_PORT` | `3000` | Host port for the UI |
| `BACKEND_PORT` | `8000` | Host port for the API |
| `OLLAMA_PORT` | `11434` | Host port for Ollama (debug/CLI) |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | **Build-time** API URL baked into the UI; must be browser-reachable |
| `LLM_MODEL` | `llama3.2` | Ollama model for answers |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model (changing it requires re-indexing) |
| `CONTEXTIQ_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Browser origins allowed by the API |
| `CONTEXTIQ_MAX_UPLOAD_MB` | `25` | Per-file upload cap |
| `CONTEXTIQ_TOP_K` | `5` | Chunks retrieved per query |
| `CONTEXTIQ_CHUNK_SIZE` / `_OVERLAP` | `1000` / `200` | Chunking |

> If you change `BACKEND_PORT`, update `NEXT_PUBLIC_API_URL` to match and
> rebuild the frontend (`NEXT_PUBLIC_*` is fixed at build time).

## 5. Startup

```bash
# Build images and start the whole stack (add -d to detach).
docker compose up --build
```

**First run takes several minutes** — it pulls base images, downloads
the LLM (~2 GB) and the embedding model (~130 MB). The startup order is
gated so "up" means "ready":

```
ollama (healthy) → ollama-pull (model downloaded, exits)
                 → backend (healthy)  → frontend (healthy)
```

When it settles, open **http://localhost:3000**.

Subsequent starts are fast (models are cached in volumes):

```bash
docker compose up -d          # start
docker compose down           # stop (volumes/data preserved)
docker compose logs -f backend
```

## 6. Health checks

Every service has a built-in Compose healthcheck:

| Service | Check |
|---|---|
| `ollama` | `ollama list` succeeds |
| `backend` | `GET /health` returns HTTP 200 |
| `frontend` | `GET /` returns HTTP 200 |

Inspect and verify manually:

```bash
docker compose ps                        # STATUS column shows (healthy)

# Backend liveness + dependency reachability (chroma/ollama true/false):
curl -s http://localhost:8000/health
# {"status":"ok","chroma":true,"ollama":true}

# Knowledge-base status + pipeline settings:
curl -s http://localhost:8000/status

# Frontend:
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000
```

`/health` returns HTTP 200 even when a dependency is down; the JSON
`status` field reports `"degraded"` and flags which of `chroma` /
`ollama` is unreachable.

## 7. Verify the deployment

1. Open http://localhost:3000 and upload a PDF/TXT in the sidebar — it
   indexes automatically.
2. Ask a question; the answer should stream in with source citations.
3. Confirm persistence: `docker compose restart backend`, then reload —
   your documents and answers-corpus are still there (volumes).

## 8. Common operations

```bash
# Change the LLM model
echo "LLM_MODEL=mistral" >> .env
docker compose up -d ollama-pull        # pull the new model
docker compose up -d backend            # picks up CONTEXTIQ_LLM_MODEL

# Rebuild after code changes
docker compose up --build -d

# Back up the knowledge base (documents + vectors)
docker run --rm -v contextiq_chroma-data:/c -v contextiq_documents:/d \
  -v "$PWD":/out alpine \
  tar czf /out/contextiq-backup.tgz -C / c d

# Full reset (DELETES all data/models)
docker compose down -v
```

## 9. Troubleshooting

**Chat returns 503 / "The language model is unreachable."**
The model isn't ready. On first run wait for `ollama-pull` to finish
(`docker compose logs -f ollama-pull`). Confirm the model exists:
`docker compose exec ollama ollama list`. Re-pull if needed:
`docker compose up ollama-pull`.

**First answer is very slow.**
Normal on CPU — the model loads on first use. Enable the GPU block in
`docker-compose.yml`, or pick a smaller `LLM_MODEL`.

**UI loads but every request fails / CORS errors in the console.**
The UI is calling the wrong API URL, or the origin isn't allowed. Ensure
`NEXT_PUBLIC_API_URL` points at the host-reachable backend
(`http://localhost:8000`, **not** `http://backend:8000`) and rebuild the
frontend; ensure your frontend origin is in `CONTEXTIQ_CORS_ORIGINS`.

**`backend` stuck "starting" / unhealthy on first boot.**
It's downloading the embedding model (~130 MB); the healthcheck has a
90s grace period. Watch `docker compose logs -f backend`. If it never
finishes, the container likely has no internet for the HuggingFace
download — check connectivity/proxy.

**`ollama-pull` fails.**
No internet to download the model, or the model name is wrong. Fix
connectivity or `LLM_MODEL`, then `docker compose up ollama-pull`.

**Port already in use (`bind: address already in use`).**
Something else holds 3000/8000/11434. Change `FRONTEND_PORT` /
`BACKEND_PORT` / `OLLAMA_PORT` in `.env` (and `NEXT_PUBLIC_API_URL` if
you moved the backend), then `docker compose up --build -d`.

**Frontend image build fails on the standalone copy.**
Ensure `output: "standalone"` is set in `frontend/next.config.ts` (it
is by default) so `.next/standalone` is produced.

**Changed the embedding model and retrieval got worse.**
Vectors from different embedding models aren't comparable. After
changing `EMBEDDING_MODEL`, clear and re-index: delete the database from
the UI (or `curl -X DELETE http://localhost:8000/database`) and re-upload
/ re-index your documents.
