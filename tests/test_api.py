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

    # --- GET /documents ----------------------------------------------------------------
    r = client.get("/documents")
    check("GET /documents returns 200", r.status_code == 200)
    docs = r.json()["documents"]
    check("documents include demo corpus and new upload",
          "zephyra.txt" in docs and "api_test_notes.txt" in docs, str(docs))

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

    # --- Cleanup: remove the test upload, rebuild the index from data/ -------------------------
    os.remove(os.path.join(PROJECT_ROOT, "data", "api_test_notes.txt"))
    traversal_file = os.path.join(PROJECT_ROOT, "data", "evil.txt")
    if os.path.isfile(traversal_file):
        os.remove(traversal_file)

    r = client.post("/index")  # no body -> reindex everything in data/
    check("full reindex restores the database",
          r.status_code == 200 and r.json()["vector_count"] == initial_vectors,
          f"count={r.json()['vector_count']}, expected={initial_vectors}")

print()
print("ALL PASSED" if not failures else f"FAILED: {failures}")
sys.exit(1 if failures else 0)
