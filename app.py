# app.py
#
# Streamlit UI for the RAG Knowledge Bot.
#
# This file is UI ONLY. Every real operation is delegated to the
# backend modules:
#   - ingest.py       -> processing uploaded documents
#   - rag.py          -> retrieval + answer generation
#   - vector_store.py -> database status / clearing
#   - llm.py          -> talking to Ollama
# No chunking, embedding, database, or LLM logic lives here, so the
# backend can be tested and evolved without touching the UI (and
# vice versa).

import logging
import os

import streamlit as st

logger = logging.getLogger(__name__)

from config import ASSETS_DIR, DATA_DIR
from ingest import ingest_file
from llm import LLM
from rag import Retriever, answer_question
from vector_store import clear_database, get_stored_filenames, get_vector_count


# ---------------------------------------------------------------------------
# Cached backend objects
# ---------------------------------------------------------------------------
# Streamlit reruns this whole script on every user interaction.
# @st.cache_resource makes these heavyweight objects (the embedding
# model especially) load ONCE per server process instead of on every
# rerun, keeping the chat responsive.


def load_css() -> None:
    """
    Inject the external stylesheet (assets/style.css) into the page.

    All styling lives in that CSS file — none inline here — so design
    changes never require touching Python. If the file is missing the
    app simply runs unstyled rather than crashing.
    """
    css_path = os.path.join(ASSETS_DIR, "style.css")
    try:
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


@st.cache_resource
def get_retriever() -> Retriever:
    """Build the Retriever (embedding model + DB connection) once."""
    return Retriever()


@st.cache_resource
def get_llm() -> LLM:
    """Build the Ollama client once."""
    return LLM()


# ---------------------------------------------------------------------------
# Sidebar: document upload, database status, clear button
# ---------------------------------------------------------------------------


def handle_upload(uploaded_files: list) -> None:
    """
    Save uploaded files into data/ and ingest each one.

    Each file is written to the data/ folder first (so the on-disk
    corpus stays the source of truth), then pushed through the full
    ingestion pipeline. Errors are shown per file so one bad PDF
    doesn't hide the success of the others.
    """
    for uploaded in uploaded_files:
        # basename() strips any directory components from the
        # browser-supplied filename, so a crafted name can never
        # write outside the data/ folder.
        safe_name = os.path.basename(uploaded.name)
        file_path = os.path.join(DATA_DIR, safe_name)
        try:
            with open(file_path, "wb") as f:
                f.write(uploaded.getbuffer())
            with st.spinner(f"Ingesting {safe_name}..."):
                num_chunks = ingest_file(file_path)
            st.success(f"Added '{safe_name}' ({num_chunks} chunks).")
        except Exception as e:
            logger.exception("Ingestion failed for '%s'", safe_name)
            st.error(f"Failed to ingest '{safe_name}': {e}")


def render_sidebar() -> None:
    """
    Draw the sidebar: upload control, database status, clear button.
    """
    with st.sidebar:
        # --- App identity ---------------------------------------------------
        st.title("📚 RAG Knowledge Bot")
        st.caption("Private, local document Q&A")
        st.divider()

        st.header("Knowledge Base")

        # --- Upload + indexing ----------------------------------------------
        # Uploading only stages files; nothing is processed until the
        # user explicitly clicks "Index Documents".
        uploaded_files = st.file_uploader(
            "Upload documents",
            type=["pdf", "txt"],
            accept_multiple_files=True,
            help="PDF and plain-text files are supported.",
        )
        if uploaded_files and st.button("Index Documents"):
            handle_upload(uploaded_files)

        st.divider()

        # --- Status -------------------------------------------------------
        # Reading status fresh on every rerun keeps the numbers honest
        # right after an upload or a clear.
        try:
            count = get_vector_count()
            filenames = get_stored_filenames()
        except Exception as e:
            st.error(f"Could not read database status: {e}")
            return

        st.subheader("Database status")
        st.metric("Stored vectors", count)
        if filenames:
            st.caption("Indexed documents:")
            for name in filenames:
                st.caption(f"• {name}")
        else:
            st.caption("No documents indexed yet.")

        st.divider()

        # --- Clear --------------------------------------------------------
        if st.button("Clear database"):
            try:
                clear_database()
                # The cached Retriever holds a handle to the deleted
                # collection — drop the cache so it reconnects cleanly.
                st.cache_resource.clear()
                st.success("Database cleared.")
                st.rerun()  # refresh the status panel immediately
            except Exception as e:
                st.error(f"Failed to clear database: {e}")


# ---------------------------------------------------------------------------
# Main page: title, description, chat
# ---------------------------------------------------------------------------


def render_sources(sources: list[dict]) -> None:
    """
    Show which chunks an answer was based on, inside an expander.

    Each line carries the three traceability facts: source file,
    chunk id, and similarity score.
    """
    with st.expander(f"Sources ({len(sources)})"):
        for s in sources:
            st.markdown(
                f"- **{s['filename']}** · `{s['chunk_id']}` · "
                f"similarity {s['similarity']:.4f}"
            )


def render_chat() -> None:
    """
    Draw the chat: history from session state, then handle new input.

    st.session_state survives reruns (but not browser refreshes), so
    the conversation persists while the user interacts with the app.
    Each stored message is {"role", "content", "sources"}.
    """
    # Replay existing history on every rerun.
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                render_sources(message["sources"])

    # Handle a new question, if one was submitted. st.chat_input
    # already blocks truly empty submissions in the browser; the
    # strip() check additionally rejects whitespace-only input.
    question = st.chat_input("Ask a question about your documents...")
    if not question or not question.strip():
        return
    question = question.strip()

    # Show and store the user's message.
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Generate and store the assistant's reply.
    with st.chat_message("assistant"):
        try:
            with st.spinner("Searching documents and generating answer..."):
                result = answer_question(question, get_retriever(), get_llm())
        except Exception as e:
            # Most likely cause: the Ollama server isn't running.
            logger.exception("Answer generation failed")
            st.error(
                f"Could not generate an answer: {e}\n\n"
                "Is Ollama running? Start it and try again."
            )
            return

        st.markdown(result["answer"])
        if result["sources"]:
            render_sources(result["sources"])

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["answer"],
            "sources": result["sources"],
        }
    )


def main() -> None:
    """Assemble the page: config, session state, sidebar, chat."""
    st.set_page_config(page_title="RAG Knowledge Bot", page_icon="📚")
    load_css()

    # Initialise chat history once per browser session.
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.title("📚 RAG Knowledge Bot")
    st.markdown(
        "Ask questions about your own documents. Upload PDF or text "
        "files in the sidebar; answers are generated **only** from "
        "what those documents say, with sources shown for every answer."
    )

    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
