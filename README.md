# ContextIQ

**Private AI-Powered Document Intelligence**

ContextIQ is a privacy-first knowledge workspace for your own documents.
Import PDFs, Office files, spreadsheets, Markdown and HTML; ask grounded
questions; inspect the evidence behind every answer; compare documents;
find contradictions; build timelines and an evidence-linked knowledge
graph; run bounded multi-step research; and export reports. Answers and
analysis are produced by a **local** Ollama model — your documents are
never sent to a hosted AI service.

![Stack](https://img.shields.io/badge/stack-FastAPI%20·%20Next.js%20·%20Chroma%20·%20SQLite%20·%20Ollama-blue)

> Branch status: `feature/contextiq-2.0` (unreleased). `main` holds the v1.0.0 release.

## Features

### Documents and collections
- **Multi-format ingestion** — `.pdf`, `.txt`, `.docx`, `.pptx`, `.xlsx`, `.csv`, `.md`/`.markdown`, `.html`/`.htm`.
- **Local OCR fallback** for scanned PDFs (Tesseract + Poppler, optional).
- **Source locators** — page (PDF), slide (PPTX), sheet (XLSX) and section heading (DOCX/Markdown/HTML) are kept with every chunk and shown wherever a passage is cited.
- **Collections and tags** in SQLite; moving or deleting a collection never deletes documents.
- **Automatic summaries** with key points, generated after indexing and stored locally.

### Grounded chat and research
- **Hybrid retrieval** — vector search (Chroma, `BAAI/bge-small-en-v1.5`, 384-dim) + BM25, fused with Reciprocal Rank Fusion and reranked by a local cross-encoder (with fallback).
- **Streaming answers** over Server-Sent Events, grounded only in the retrieved passages, with suggested follow-up questions.
- **Citation verification** — each claim is checked as `SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNSUPPORTED` or `UNVERIFIABLE` (model-assisted, not proof).
- **Contradiction detection** — `CONTRADICTION` / `POTENTIAL_CONTRADICTION` with severity, guarding against false positives from differing dates, units, regions, or forecasts vs. actuals.
- **Evidence assessment** (rule-based, see below) attached to every verified answer.
- **Research mode** — *Quick* one-pass synthesis, or *Deep* bounded multi-step research (see below).
- **Document comparison** of 2–5 documents with per-document evidence coverage.
- **Report export** — Markdown, PDF (ReportLab) or plain text, including sources, citation checks, contradictions, evidence ratings, research process, unresolved questions and timelines.

### Analysis tools (top bar)
- **Timeline** — events with original date wording, normalized dates, explicit certainty, actors and source locators.
- **Check claim** — rate how well the documents in scope support any statement.
- **Knowledge graph** — entities and relationships, each linked to the passage that states it.
- **Compare** — side-by-side comparison of selected documents.

Every tool respects the active collection (sidebar) and, optionally, a narrower selection of documents inside it.

### Voice
- **Voice input** via the browser's Web Speech API. The transcript is placed in the message box for review — never auto-sent.
- **Read aloud** for answers via the browser's speech synthesis.

## How the 2.0 features work — and their limits

### Timeline extraction
Passages are selected by date density (or by a focus query), then one bounded LLM call labels events against evidence ids. Every event is validated: the cited passage must exist, the quoted date wording must occur in it, and actors must appear in it. Dates are normalized **in code** (`date_normalizer.py`), never taken from the model:

| Certainty | Meaning |
|---|---|
| `EXACT` | The wording pins the date at its precision (day, month, quarter, year, range) |
| `APPROXIMATE` | "circa 1850", "mid-2019", "the 1990s", "by 2025" |
| `AMBIGUOUS` | "03/04/2024" — day/month order unknown, only the year is used |
| `RELATIVE` | "last year" — not placed on the timeline |
| `UNKNOWN` | no usable date — listed separately, never guessed |

Publication/revision dates are tagged separately from event dates, and the date a file was indexed is reported as ingestion metadata, not as an event. Without Ollama, a pattern-based extractor runs and the response says so.
*Limit:* validation is per passage, so a date that occurs elsewhere in the same passage can be attached to the wrong event; check the linked passage.

### Evidence assessment
A deterministic, documented rule set (`evidence_service.py`) — no extra LLM call. Ratings are categorical on purpose; there are **no percentages**, because these are **not calibrated probabilities**:

| Rating | Rule |
|---|---|
| `STRONG` | Citation check SUPPORTED, ≥ 2 independent sources, no related conflict |
| `MODERATE` | Citation check SUPPORTED with 1 independent source |
| `LIMITED` | Partially supported; keyword overlap only (model unavailable); or a SUPPORTED verdict whose passage can't be located |
| `CONTESTED` | A detected contradiction concerns the claim — overrides support |
| `UNSUPPORTED` | The citation check found no support — never upgraded |
| `INSUFFICIENT` | Undecidable, or no relevant passage retrieved |

Only passages cited by the check or containing most (≥ 60%) of the claim's key terms count as corroboration. Passages from the same document count once, and near-duplicate text across documents (5-word shingle Jaccard ≥ 0.6) is collapsed into one source.

### Knowledge graph
Stored in the existing SQLite database (no graph database). Entities merge only on an exact match of type and conservatively normalized name; near matches ("Acme" / "Acme Corp", acronyms) are reported as *possible duplicates* and never merged. A relationship is stored only if both entities occur in the cited passage; it is `SUPPORTED` only when the model's quote is found verbatim, otherwise `UNCERTAIN` (dashed in the UI). Without Ollama, entities are capitalized names and links are `UNCERTAIN` "mentioned with" co-mentions. Graph facts are removed when a document is deleted, re-indexed, or the database is cleared. Queries only return facts from documents in scope; an entity that exists only elsewhere is a 404.

### Bounded deep research
A deterministic orchestrator (`agentic_research.py`), not an open-ended agent: plan (≤ 4 sub-questions; simple questions are not split) → one scoped search per sub-question → follow-up searches for gaps (≤ 2, never repeating a search) → one cited synthesis over numbered passages (citations to non-existent passages are removed) → citation check, contradiction scan, evidence assessment. Hard limits: 8 searches, 9,000 context characters, 900 answer tokens, 600 s wall clock (all configurable). Scope is re-checked on every search. After the first model failure no further model calls are made and the run ends `PARTIAL` with the evidence found. The Stop button cancels the run server-side. Sub-question statuses describe *evidence* ("Evidence found" / "Weak evidence" / "No evidence"), not whether the answer resolved them.

### Voice and privacy
Voice input uses the browser's speech recognition. **Some browsers (e.g. Chrome, Edge) send audio to the browser vendor's speech service** — outside ContextIQ's local processing — so first use shows this disclosure and requires opt-in, and the microphone is only requested when you press the mic button. ContextIQ never records or stores audio and never sends documents anywhere. Where speech recognition is unsupported (e.g. Firefox), the control is hidden and typing is the fallback.

## Architecture

```
├── api/
│   ├── main.py            app assembly: CORS, logging, size limit, exception handlers
│   ├── routers/           chat · research · agent_research · compare · timeline · evidence ·
│   │                      graph · documents · collections · system
│   ├── services/          rag_service (shared retriever + LLM) · document_service
│   └── schemas/           models.py (core contract) · insights.py (2.0 analysis features)
├── rag.py                 grounded answers (sync + streaming) + verification pipeline
├── retrieval.py           hybrid retriever (vector + BM25 → RRF → rerank), scope filters
├── scope.py               single validated rule for collection / document scope
├── timeline_service.py    C7 timeline · date_normalizer.py
├── evidence_service.py    C8 evidence assessment + claim check
├── graph_service.py       C10 knowledge graph (SQLite)
├── agentic_research.py    C11 bounded research orchestrator
├── citation_verification_service.py · contradiction_detection_service.py ·
│   comparison_service.py · summary_service.py · suggested_question_service.py ·
│   report_service.py
├── llm.py                 Ollama client (per-call timeout and output cap)
├── metadata_store.py      SQLite (WAL, foreign keys): collections, tags, summaries, graph
├── ingest.py · parsers.py · ocr_service.py · vector_store.py · embedding_model.py
└── frontend/              Next.js 15 · React 19 · Tailwind · TanStack Query
    ├── components/        chat/ · insights/ (analysis dialogs) · sidebar/ · layout/ · ui/
    ├── hooks/             useChat (chat, quick + deep research) · useSpeechRecognition · …
    └── lib/               api.ts (typed client, shared SSE reader) · types.ts · graph-layout.ts
```

## API overview

Interactive docs at `http://localhost:8000/docs` once the backend runs.

| Endpoint | Purpose |
|---|---|
| `POST /upload`, `POST /index`, `GET/DELETE /documents…` | ingestion and document management |
| `GET/POST/PATCH/DELETE /collections…`, `/documents/{f}/tags` | collections and tags |
| `POST /chat`, `POST /chat/stream` | grounded Q&A (+ verification, contradictions, evidence) |
| `POST /research`, `POST /research/stream` | quick one-pass research synthesis |
| `POST /research/agent`, `POST /research/agent/stream` | bounded deep research (SSE: progress, plan, sources, token, result) |
| `POST /research/export` | Markdown / PDF / TXT report |
| `POST /compare` | 2–5 document comparison with coverage |
| `POST /timeline` | timeline extraction |
| `POST /evidence/assess` | claim check |
| `POST /graph/build`, `GET /graph`, `GET /graph/entities/{id}` | knowledge graph |
| `GET /health`, `GET /status`, `DELETE /database` | system |

Scoped endpoints accept `collection_id` and/or `filenames` (≤ 25). Unknown collections or documents return `400`; documents outside the collection return `403`.

## Prerequisites

- **Python 3.11+**, **Node.js 20+**
- **[Ollama](https://ollama.com)** running locally with `llama3.2` (`ollama pull llama3.2`)
- Optional OCR: Tesseract and Poppler on `PATH`

## Setup

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
ollama pull llama3.2
./run-dev.sh            # or .\run-dev.ps1 on Windows — backend :8000, frontend :3000
```

The first run downloads the embedding and reranker models from Hugging Face; afterwards everything runs offline. Docker: see [DEPLOYMENT.md](DEPLOYMENT.md).

## Configuration

All settings are environment variables read by [config.py](config.py) (see [.env.example](.env.example)): data and Chroma directories, chunking, embedding model, `TOP_K`, Ollama model/URL, upload limit, CORS origins, and per-feature limits and timeouts (`CONTEXTIQ_TIMELINE_*`, `CONTEXTIQ_GRAPH_*`, `CONTEXTIQ_AGENT_*`, `CONTEXTIQ_*_TIMEOUT`). The frontend reads `NEXT_PUBLIC_API_URL`.

**Performance is hardware-dependent.** Defaults are sized for CPU-only inference: on the development machine (CPU, `llama3.2`) a chat answer with all checks took about 4 minutes, a timeline about 1.5 minutes, a claim check about 3.5 minutes, and a deep-research run about 4.5 minutes for a two-document collection. A GPU is much faster; lower the timeouts there. When a model call times out, features degrade (pattern fallbacks, heuristic ratings, partial research) and say so.

## Testing

```bash
# Backend — mocked, no Ollama needed; runs against a throwaway data dir
pip install pytest   # test runner (not a runtime dependency)
python -m pytest tests --ignore=tests/test_api.py
python -m unittest tests.test_unit tests.test_timeline tests.test_evidence tests.test_graph tests.test_agentic_research

# Frontend
cd frontend && npm run lint && npx tsc --noEmit && npm test && npm run build

# Live end-to-end (real Ollama + your real indexed data)
python tests/test_api.py
```

`tests/__init__.py` redirects `CONTEXTIQ_DATA_DIR` / `CONTEXTIQ_CHROMA_DIR` to a temporary directory so test runs never touch your knowledge base (set `CONTEXTIQ_TEST_USE_REAL_DATA=1` to opt out). Some older suites load the embedding model and are slow on first run.

## Security and privacy

- Local, single-user application; the API is unauthenticated by design — keep it on `localhost` or a trusted network.
- Uploads are validated by extension and size; filenames are reduced to their base name; uploaded content is never executed.
- Document text is treated as untrusted in every prompt; model output is parsed defensively and validated (evidence ids, quotes, citations) before use.
- Client-supplied scopes are validated server-side and re-applied to every retrieval result.
- Error responses never include stack traces, paths, or exception text.
- No telemetry and no hosted AI APIs. The only optional network-dependent feature is browser speech recognition, which is disclosed and opt-in.

## Known limitations

- Citation checks, contradictions, timelines and graph relations are model-assisted interpretations by a small local model — useful signals, not proof.
- Timeline date validation is per passage (see above); graph extraction reads at most 8 date/name-dense passages per document.
- Deep research sub-question status reflects evidence retrieval, not answer completeness.
- Voice input availability and privacy depend on the browser.

## License

[MIT](LICENSE)
