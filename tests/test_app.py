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
    """
    Record and print one pass/fail check.

    Widget labels in this app include emoji (part of the UI design),
    and this Windows console's codepage can't encode all of them —
    printing one raw would crash the whole test run. Re-encoding
    through the console's own encoding with errors="replace" avoids
    that without needing to touch the app's actual labels.
    """
    status = "PASS" if cond else "FAIL"
    line = f"[{status}] {name}" + (f" - {extra}" if extra else "")
    encoding = sys.stdout.encoding or "utf-8"
    print(line.encode(encoding, errors="replace").decode(encoding))
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
        "Project Notes\n\nContextIQ ships with a fictional "
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
# The hero is a real st.title() (a semantic <h1>, for screen-reader
# heading navigation), checked via the .title accessor rather than
# .markdown now that it's no longer hand-rolled HTML.
check("hero heading rendered (real <h1> via st.title)",
      any("ContextIQ" in t.value for t in at.title))
check("empty-state getting-started hint shown",
      any("Upload a PDF or TXT file" in c.value for c in at.caption)
      or any("Ask a question about your documents" in c.value for c in at.caption))
check("sidebar brand name rendered",
      any("ContextIQ" in m.value for m in at.sidebar.markdown))
check("new chat button present",
      any(b.label == "New chat" for b in at.sidebar.button))
check("stylesheet injected",
      sum("<style>" in m.value for m in at.markdown) == 1)
# "Documents indexed" (not "vectors") is the headline sidebar metric —
# vector count is technical detail, demoted into the details expander.
check("documents-indexed metric present",
      len(at.metric) == 1 and at.metric[0].label == "Documents indexed",
      f"value={at.metric[0].value if at.metric else 'none'}")
# st.expander(..., icon=...) is classified internally by AppTest as
# a "Status" element rather than "Expander" (an AppTest quirk tied to
# the icon parameter — the real browser UI renders a normal expander
# either way), so it's found via .status, not .expander.
details_expanders = [e for e in at.sidebar.status if "Model details" in e.label]
check("model details expander present", len(details_expanders) == 1)
if details_expanders:
    details_text = " ".join(m.value for m in details_expanders[0].markdown)
    check("model details show configured LLM model", "llama3.2" in details_text)
    check("model details show raw vector count", "Vectors stored" in details_text)
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
# render_chat() calls st.rerun() itself once the answer is ready (so
# the hero can collapse to compact immediately — see app.py). AppTest
# accumulates elements from BOTH the pre-rerun and post-rerun passes
# for a script-triggered rerun like this (unlike a normal external
# widget interaction, which yields a single clean pass), so the tree
# ends up with 4 chat_message blocks even though session_state and a
# real browser only ever show 2. The last two are the settled,
# post-rerun pair a user would actually see.
check("at least two chat messages rendered (user + assistant)",
      len(at.chat_message) >= 2, f"count={len(at.chat_message)}")
if len(at.chat_message) >= 2:
    user_msg, assistant_msg = at.chat_message[-2], at.chat_message[-1]
    check("user bubble shows the question",
          "Zephyra" in user_msg.markdown[0].value)
    answer = assistant_msg.markdown[0].value
    check("assistant answer is non-empty and on-topic",
          len(answer) > 40 and "know based on the provided documents" not in answer,
          answer[:100] + "...")
    # Same AppTest quirk as the sidebar's "Model details": an
    # icon-bearing expander shows up under .status, not .expander.
    exp = assistant_msg.status
    check("sources expander shown", len(exp) == 1,
          exp[0].label if exp else "")
    if exp:
        src_text = " ".join(m.value for m in exp[0].markdown)
        check("sources show filename", "zephyra.txt" in src_text)
        check("sources show chunk ids", "zephyra.txt-" in src_text)
        # Similarity is now shown as a "NN.N%" badge rather than a raw
        # "similarity 0.xxxx" string — check for the percent sign and
        # the CSS class the badge is rendered with.
        check("sources show similarity scores",
              "source-score" in src_text and "%" in src_text)
check("history stored in session state",
      len(at.session_state["messages"]) == 2)
check("hero collapses to compact once a conversation exists",
      not any("Upload a PDF or TXT file" in c.value or
              "Ask a question about your documents" in c.value
              for c in at.caption))

# --- 4. Whitespace-only query is rejected -------------------------------------
at.chat_input[0].set_value("   ").run(timeout=120)
check("whitespace-only query adds no messages",
      len(at.session_state["messages"]) == 2,
      f"history length={len(at.session_state['messages'])}")

# --- 5. "New chat" resets the conversation but leaves the database alone ------
new_chat_btn = [b for b in at.sidebar.button if b.label == "New chat"]
check("new chat button clickable", len(new_chat_btn) == 1)
new_chat_btn[0].click().run(timeout=60)
check("no exception after new chat", not at.exception,
      str(at.exception[0].value) if at.exception else "")
check("new chat clears history", len(at.session_state["messages"]) == 0)
check("hero returns to full/getting-started state after new chat",
      any("Ask a question about your documents" in c.value for c in at.caption))
check("new chat does not touch the database",
      at.metric[0].value != "0", f"value={at.metric[0].value}")

# --- 6. Clear database button --------------------------------------------------
clear_btn = [b for b in at.button if b.label == "Clear database"]
check("clear button present", len(clear_btn) == 1)
clear_btn[0].click().run(timeout=120)
check("no exception after clear", not at.exception,
      str(at.exception[0].value) if at.exception else "")
check("documents-indexed count now 0", at.metric[0].value == "0",
      f"value={at.metric[0].value}")
check("status shows no indexed documents",
      any("No documents indexed yet" in c.value for c in at.caption))

# --- 7. Question against empty DB uses honest fallback --------------------------
at.chat_input[0].set_value("What is semantic memory?").run(timeout=120)
last = at.session_state["messages"][-1]
check("empty-DB fallback answer",
      "I don't know based on the provided documents." in last["content"],
      last["content"][:80])

# --- Cleanup: remove test upload, rebuild the index from data/ -------------------
# Step 5 clicked "Clear database", wiping EVERYTHING — not just the
# temporary notes.txt this test added. data/ may hold real documents
# a user indexed through the live app, so cleanup must reindex the
# whole folder (what `python ingest.py` does), not just one file, or
# running this test would silently destroy real indexed content.
os.remove(notes_path)
from ingest import chunk_documents, embed_chunks, load_documents
from vector_store import get_vector_count, save_chunks

remaining_docs = load_documents()
remaining_chunks = embed_chunks(chunk_documents(remaining_docs))
if remaining_chunks:
    save_chunks(remaining_chunks)
check("database restored after test run",
      get_vector_count() == len(remaining_chunks),
      f"count={get_vector_count()}, expected={len(remaining_chunks)}")

print()
print("ALL PASSED" if not failures else f"FAILED: {failures}")
sys.exit(1 if failures else 0)
