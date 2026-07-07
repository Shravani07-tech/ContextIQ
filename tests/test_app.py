# tests/test_app.py
#
# End-to-end regression suite. Drives the real Streamlit app with
# Streamlit's official AppTest harness against the REAL backend:
# real Chroma database, real embedding model, real Ollama server.
#
# Prerequisites:
#   - dependencies installed (pip install -r requirements.txt)
#   - Ollama running locally with the model from config.py
#   - the demo corpus indexed (python ingest.py with data/zephyra.txt)
#
# Run with:  python tests/test_app.py
# Exits 0 if every check passes, 1 otherwise.

import os
import sys

# Make the project root importable and the working directory,
# regardless of where this script is invoked from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from streamlit.testing.v1 import AppTest

APP = os.path.join(PROJECT_ROOT, "app.py")

failures: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    """Record and print one pass/fail check."""
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" - {extra}" if extra else ""))
    if not cond:
        failures.append(name)


# --- 1. Upload + indexing path ---------------------------------------------
# AppTest cannot drive the browser file-drop widget, so simulate the
# exact path the "Index Documents" button takes: file lands in data/,
# then ingest_file() is called on it.
from ingest import ingest_file

notes_path = os.path.join(PROJECT_ROOT, "data", "notes.txt")
with open(notes_path, "w", encoding="utf-8") as f:
    f.write(
        "Project Notes\n\nThe RAG Knowledge Bot ships with a fictional "
        "assistant called Zephyra as its demo corpus. These notes exist "
        "to verify that newly uploaded documents are indexed and appear "
        "in the sidebar list of indexed files."
    )
n = ingest_file(notes_path)
check("uploaded file indexed via ingest_file", n >= 1, f"{n} chunk(s)")

# --- 2. Initial render -------------------------------------------------------
at = AppTest.from_file(APP, default_timeout=120).run()
check("app runs without exception", not at.exception,
      str(at.exception[0].value) if at.exception else "")
check("sidebar app title present",
      any("RAG Knowledge Bot" in t.value for t in at.sidebar.title))
check("main title rendered", any("RAG Knowledge Bot" in t.value for t in at.title))
check("description rendered", any("Upload PDF or text" in m.value for m in at.markdown))
check("stylesheet injected",
      sum("<style>" in m.value for m in at.markdown) == 1)
check("vector count metric present",
      len(at.metric) == 1 and at.metric[0].label == "Stored vectors",
      f"value={at.metric[0].value if at.metric else 'none'}")
check("indexed files list shows zephyra.txt",
      any("zephyra.txt" in c.value for c in at.caption))
check("indexed files list shows newly uploaded notes.txt",
      any("notes.txt" in c.value for c in at.caption))
check("chat input present", len(at.chat_input) == 1)
check("chat history empty at start", len(at.chat_message) == 0)

# --- 3. Ask a question through the chat --------------------------------------
at.chat_input[0].set_value("How does Zephyra store knowledge?").run(timeout=600)
check("no exception after chat submit", not at.exception,
      str(at.exception[0].value) if at.exception else "")
check("two chat messages rendered (user + assistant)", len(at.chat_message) == 2)
if len(at.chat_message) == 2:
    user_msg, assistant_msg = at.chat_message
    check("user bubble shows the question",
          "Zephyra" in user_msg.markdown[0].value)
    answer = assistant_msg.markdown[0].value
    check("assistant answer is non-empty and on-topic",
          len(answer) > 40 and "know based on the provided documents" not in answer,
          answer[:100] + "...")
    exp = assistant_msg.expander
    check("sources expander shown", len(exp) == 1,
          exp[0].label if exp else "")
    if exp:
        src_text = " ".join(m.value for m in exp[0].markdown)
        check("sources show filename", "zephyra.txt" in src_text)
        check("sources show chunk ids", "zephyra.txt-" in src_text)
        check("sources show similarity scores", "similarity 0." in src_text)
check("history stored in session state",
      len(at.session_state["messages"]) == 2)

# --- 4. Whitespace-only query is rejected -------------------------------------
at.chat_input[0].set_value("   ").run(timeout=120)
check("whitespace-only query adds no messages",
      len(at.session_state["messages"]) == 2,
      f"history length={len(at.session_state['messages'])}")

# --- 5. Clear database button --------------------------------------------------
clear_btn = [b for b in at.button if b.label == "Clear database"]
check("clear button present", len(clear_btn) == 1)
clear_btn[0].click().run(timeout=120)
check("no exception after clear", not at.exception,
      str(at.exception[0].value) if at.exception else "")
check("vector count now 0", at.metric[0].value == "0",
      f"value={at.metric[0].value}")
check("status shows no indexed documents",
      any("No documents indexed yet" in c.value for c in at.caption))

# --- 6. Question against empty DB uses honest fallback --------------------------
at.chat_input[0].set_value("What is semantic memory?").run(timeout=120)
last = at.session_state["messages"][-1]
check("empty-DB fallback answer",
      "I don't know based on the provided documents." in last["content"],
      last["content"][:80])

# --- Cleanup: remove test upload, restore canonical DB state ---------------------
os.remove(notes_path)
ingest_file(os.path.join(PROJECT_ROOT, "data", "zephyra.txt"))
from vector_store import get_vector_count
check("database restored after test run", get_vector_count() > 0,
      f"count={get_vector_count()}")

print()
print("ALL PASSED" if not failures else f"FAILED: {failures}")
sys.exit(1 if failures else 0)
