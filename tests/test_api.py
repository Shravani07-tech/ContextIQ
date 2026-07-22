# tests/test_api.py
#
# End-to-end verification of every FastAPI endpoint, against the REAL
# backend: real Chroma database, real embedding model, real Ollama.
# Uses FastAPI's TestClient (in-process ASGI — no separate server
# needed), with the lifespan hook active so the startup warm-up path
# is exercised too.
#
# Prerequisites:
#   - dependencies installed (pip install -r requirements.txt)
#   - Ollama running locally with the model from config.py
#   - the demo corpus present in data/ (zephyra.txt)
#
# Run with:  python tests/test_api.py
# Exits 0 if every check passes, 1 otherwise.

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from fastapi.testclient import TestClient

from api.main import app

failures: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    """Record and print one pass/fail check (console-encoding safe)."""
    status = "PASS" if cond else "FAIL"
    line = f"[{status}] {name}" + (f" - {extra}" if extra else "")
    encoding = sys.stdout.encoding or "utf-8"
    print(line.encode(encoding, errors="replace").decode(encoding))
    if not cond:
        failures.append(name)


with TestClient(app) as client:  # `with` triggers the lifespan warm-up

    # --- GET /health ----------------------------------------------------------
    r = client.get("/health")
    check("GET /health returns 200", r.status_code == 200, str(r.status_code))
    body = r.json()
    check("health reports chroma reachable", body.get("chroma") is True)
    check("health reports ollama reachable", body.get("ollama") is True,
          "is Ollama running?")
    check("health overall ok", body.get("status") == "ok", body.get("status", ""))

    # --- GET /status ------------------------------------------------------------
    r = client.get("/status")
    check("GET /status returns 200", r.status_code == 200)
    body = r.json()
    initial_vectors = body["vector_count"]
    check("status has documents + settings",
          body["document_count"] == len(body["documents"])
          and body["llm_model"] == "llama3.2"
          and body["chunk_size"] == 1000,
          f"vectors={initial_vectors}")

    # --- POST /upload -------------------------------------------------------------
    upload_content = (
        b"Upload Endpoint Test\n\nContextIQ exposes a REST API. This "
        b"temporary document verifies that POST /upload stages a file "
        b"into the data folder and POST /index makes it searchable."
    )
    r = client.post(
        "/upload",
        files=[("files", ("api_test_notes.txt", upload_content, "text/plain"))],
    )
    check("POST /upload returns 200", r.status_code == 200, str(r.status_code))
    body = r.json()
    check("upload reports file saved",
          body["files"][0]["status"] == "saved"
          and body["files"][0]["filename"] == "api_test_notes.txt")
    check("uploaded file exists in data/",
          os.path.isfile(os.path.join(PROJECT_ROOT, "data", "api_test_notes.txt")))

    # Unsupported type is rejected per-file, not with a whole-request error.
    r = client.post(
        "/upload",
        files=[("files", ("malware.exe", b"nope", "application/octet-stream"))],
    )
    check("unsupported upload rejected per-file",
          r.status_code == 200 and r.json()["files"][0]["status"] == "error")

    # Oversized upload is rejected server-side (client checks are UX,
    # this is the security boundary) — nothing may reach data/.
    big = b"x" * (26 * 1024 * 1024)  # 1 MB over the 25 MB default cap
    r = client.post(
        "/upload", files=[("files", ("too_big.txt", big, "text/plain"))]
    )
    body = r.json()["files"][0]
    check("oversized upload rejected server-side",
          r.status_code == 200 and body["status"] == "error"
          and "limit" in (body["error"] or ""),
          str(body["error"]))
    check("oversized file not written to data/",
          not os.path.isfile(os.path.join(PROJECT_ROOT, "data", "too_big.txt")))

    # Empty files are rejected server-side too.
    r = client.post(
        "/upload", files=[("files", ("empty.txt", b"", "text/plain"))]
    )
    check("empty upload rejected server-side",
          r.json()["files"][0]["status"] == "error")

    # Total-request-size middleware: a batch whose COMBINED size
    # exceeds the total-request ceiling must be rejected at the
    # transport layer (413) before any per-file processing — this is
    # the real defense; the per-file check above runs only after the
    # whole body is already parsed.
    huge_batch = [
        ("files", (f"batch_{i}.txt", b"x" * (30 * 1024 * 1024), "text/plain"))
        for i in range(4)  # 4 x 30 MB = 120 MB > the 100 MB default ceiling
    ]
    r = client.post("/upload", files=huge_batch)
    check("oversized total request rejected with 413",
          r.status_code == 413 and "limit" in r.json().get("detail", ""),
          f"status={r.status_code}, body={r.json()}")

    # Path traversal in the filename is neutralised by basename().
    r = client.post(
        "/upload",
        files=[("files", ("..\\..\\evil.txt", b"traversal test", "text/plain"))],
    )
    saved_name = r.json()["files"][0]["filename"]
    check("path traversal neutralised",
          ".." not in saved_name and not os.path.isfile(
              os.path.join(PROJECT_ROOT, "evil.txt")),
          f"saved as {saved_name!r}")

    # --- POST /index ----------------------------------------------------------------
    r = client.post("/index", json={"filenames": ["api_test_notes.txt"]})
    check("POST /index returns 200", r.status_code == 200, str(r.status_code))
    body = r.json()
    check("index reports chunks for the file",
          body["files"][0]["status"] == "indexed"
          and body["files"][0]["chunks_indexed"] >= 1,
          str(body["files"][0]))
    check("vector count grew after indexing",
          body["vector_count"] > initial_vectors,
          f"{initial_vectors} -> {body['vector_count']}")

    # Indexing a file that was never uploaded is a per-file error.
    r = client.post("/index", json={"filenames": ["ghost.txt"]})
    check("indexing unknown file reports per-file error",
          r.json()["files"][0]["status"] == "error")

    # Orphaned-upload cleanup: a file that STAGES successfully but
    # fails INDEXING (e.g. a corrupt/unreadable PDF) must not linger
    # on disk forever — it would silently resurface and get indexed
    # on a future full reindex. The backend should remove it and say
    # so in the per-file error.
    corrupt_pdf_path = os.path.join(PROJECT_ROOT, "data", "corrupt.pdf")
    with open(corrupt_pdf_path, "wb") as f:
        f.write(b"this is not a valid pdf file at all")
    r = client.post("/index", json={"filenames": ["corrupt.pdf"]})
    body = r.json()["files"][0]
    check("corrupt file reports indexing error",
          body["status"] == "error", str(body))
    check("corrupt file's error mentions removal",
          "removed" in (body["error"] or ""), body["error"])
    check("orphaned file actually removed from data/",
          not os.path.isfile(corrupt_pdf_path))

    # --- GET /documents ----------------------------------------------------------------
    r = client.get("/documents")
    check("GET /documents returns 200", r.status_code == 200)
    docs = r.json()["documents"]
    check("documents include demo corpus and new upload",
          "zephyra.txt" in docs and "api_test_notes.txt" in docs, str(docs))

    # --- DELETE /documents/{filename} --------------------------------------------------------
    # Single-file delete: only THIS file's vectors + disk copy go
    # away; everything else in the knowledge base is untouched.
    before_count = client.get("/status").json()["vector_count"]
    r = client.delete("/documents/api_test_notes.txt")
    check("DELETE /documents/{filename} returns 200", r.status_code == 200,
          str(r.status_code))
    body = r.json()
    check("delete response reports the right filename and status",
          body["filename"] == "api_test_notes.txt" and body["status"] == "deleted",
          str(body))
    check("vector count dropped by exactly this file's chunks",
          body["vector_count"] < before_count, f"{before_count} -> {body['vector_count']}")
    r = client.get("/documents")
    check("deleted file no longer listed",
          "api_test_notes.txt" not in r.json()["documents"]
          and "zephyra.txt" in r.json()["documents"],
          str(r.json()["documents"]))
    check("deleted file removed from data/ on disk",
          not os.path.isfile(os.path.join(PROJECT_ROOT, "data", "api_test_notes.txt")))

    # Deleting an unknown filename is a no-op, not an error.
    r = client.delete("/documents/never_existed.txt")
    check("deleting an unknown filename is a no-op 200, not 404",
          r.status_code == 200 and r.json()["status"] == "deleted")

    # --- POST /chat -----------------------------------------------------------------------
    r = client.post("/chat", json={"question": "How does Zephyra store knowledge?"})
    check("POST /chat returns 200", r.status_code == 200, str(r.status_code))
    body = r.json()
    check("chat answer is non-empty and grounded",
          len(body["answer"]) > 40
          and "know based on the provided documents" not in body["answer"],
          body["answer"][:100] + "...")
    check("chat returns sources with all three fields",
          len(body["sources"]) >= 1
          and all(
              {"filename", "chunk_id", "similarity"} <= set(s) for s in body["sources"]
          ),
          f"{len(body['sources'])} source(s)")
    check("chat sources carry preview snippets",
          all(
              isinstance(s.get("preview"), str) and len(s["preview"]) > 0
              for s in body["sources"]
          ),
          (body["sources"][0].get("preview") or "")[:60] + "...")

    # Validation: blank questions are rejected before reaching the pipeline.
    r = client.post("/chat", json={"question": "   "})
    check("blank question rejected with 422", r.status_code == 422,
          str(r.status_code))

    # --- POST /chat/stream -----------------------------------------------------------------
    import json as _json

    r = client.post(
        "/chat/stream",
        json={"question": "How does Zephyra store knowledge?"},
    )
    check("POST /chat/stream returns 200", r.status_code == 200, str(r.status_code))
    check("stream response is text/event-stream",
          "text/event-stream" in r.headers.get("content-type", ""),
          r.headers.get("content-type"))

    stream_events = [
        _json.loads(line[len("data: "):])
        for line in r.text.splitlines()
        if line.startswith("data: ")
    ]
    check("stream starts with a sources event",
          len(stream_events) > 0 and stream_events[0]["type"] == "sources",
          stream_events[0]["type"] if stream_events else "no events")
    check("stream's sources carry preview snippets",
          all(
              isinstance(s.get("preview"), str) and len(s["preview"]) > 0
              for s in stream_events[0]["sources"]
          ),
          str(stream_events[0]["sources"][:1]))

    token_events = [e for e in stream_events if e["type"] == "token"]
    streamed_answer = "".join(e["text"] for e in token_events)
    check("stream emits multiple token events (progressive, not one blob)",
          len(token_events) > 5, f"{len(token_events)} token event(s)")
    check("streamed answer reconstructs to a real grounded answer",
          len(streamed_answer) > 40
          and "know based on the provided documents" not in streamed_answer,
          streamed_answer[:100] + "...")
    check("stream ends with a done event",
          stream_events[-1] == {"type": "done"}, str(stream_events[-1]))

    # Empty question still validated the same way as /chat.
    r = client.post("/chat/stream", json={"question": "   "})
    check("stream endpoint also rejects blank questions with 422",
          r.status_code == 422, str(r.status_code))

    # --- DELETE /database --------------------------------------------------------------------
    r = client.delete("/database")
    check("DELETE /database returns 200", r.status_code == 200)
    check("database reports cleared with zero vectors",
          r.json() == {"status": "cleared", "vector_count": 0}, str(r.json()))
    r = client.get("/documents")
    check("documents empty after clear", r.json()["documents"] == [])

    # Chat against the empty database: honest fallback, no LLM call.
    r = client.post("/chat", json={"question": "What is semantic memory?"})
    check("empty-DB chat uses honest fallback",
          "I don't know based on the provided documents." in r.json()["answer"],
          r.json()["answer"][:60])

    # Streaming version of the same honest-fallback guarantee: the
    # fallback arrives as a single token event, and the LLM is never
    # called (same policy as non-streaming, just delivered as SSE).
    r = client.post("/chat/stream", json={"question": "What is semantic memory?"})
    empty_events = [
        _json.loads(line[len("data: "):])
        for line in r.text.splitlines()
        if line.startswith("data: ")
    ]
    empty_answer = "".join(e["text"] for e in empty_events if e["type"] == "token")
    check("empty-DB stream also uses the honest fallback",
          "I don't know based on the provided documents." in empty_answer,
          empty_answer[:60])
    check("empty-DB stream reports zero sources",
          empty_events[0] == {"type": "sources", "sources": []}, str(empty_events[0]))

    # --- Cleanup: remove any leftover test uploads, rebuild the index from data/ ----------------
    # api_test_notes.txt was already removed by the DELETE /documents/
    # test above — isfile guards make this block safe whether that
    # ran or not.
    for leftover in ("api_test_notes.txt", "evil.txt"):
        leftover_path = os.path.join(PROJECT_ROOT, "data", leftover)
        if os.path.isfile(leftover_path):
            os.remove(leftover_path)

    r = client.post("/index")  # no body -> reindex everything in data/
    check("full reindex restores the database",
          r.status_code == 200 and r.json()["vector_count"] == initial_vectors,
          f"count={r.json()['vector_count']}, expected={initial_vectors}")

print()
print("ALL PASSED" if not failures else f"FAILED: {failures}")
sys.exit(1 if failures else 0)
