# app.py
#
# Streamlit UI for ContextIQ — Private AI-Powered Document Intelligence.
#
# This file is UI ONLY. Every real operation is delegated to the
# backend modules:
#   - ingest.py       -> processing uploaded documents
#   - rag.py          -> retrieval + answer generation
#   - vector_store.py -> database status / clearing
#   - llm.py          -> talking to Ollama
#   - config.py       -> settings this file only DISPLAYS, never sets
# No chunking, embedding, database, or LLM logic lives here, and no
# visual styling lives here either — every color, radius, and
# animation is defined once in assets/style.css and loaded via
# load_css(). That split means a design change never touches Python
# and a backend change never touches CSS.

import html
import logging
import os

import streamlit as st

from config import (
    ASSETS_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DATA_DIR,
    EMBEDDING_MODEL_NAME,
    LLM_MODEL_NAME,
    TOP_K,
)
from ingest import ingest_file
from llm import LLM
from rag import Retriever, answer_question
from vector_store import clear_database, get_stored_filenames, get_vector_count

logger = logging.getLogger(__name__)

# How many indexed filenames to list directly in the sidebar before
# collapsing the rest into a "+N more" line — keeps the sidebar tidy
# regardless of how large the corpus grows.
MAX_VISIBLE_FILES = 5

# Shown in the assistant bubble while an answer is being generated —
# a static HTML/CSS snippet with no user data, so it's safe to mark
# unsafe_allow_html. The animation itself lives in style.css.
TYPING_INDICATOR_HTML = (
    '<div class="typing-indicator"><span></span><span></span><span></span></div>'
)


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


# ---------------------------------------------------------------------------
# Cached backend objects
# ---------------------------------------------------------------------------
# Streamlit reruns this whole script on every user interaction.
# @st.cache_resource makes these heavyweight objects (the embedding
# model especially) load ONCE per server process instead of on every
# rerun, keeping the chat responsive.


@st.cache_resource
def get_retriever() -> Retriever:
    """Build the Retriever (embedding model + DB connection) once."""
    return Retriever()


@st.cache_resource
def get_llm() -> LLM:
    """Build the Ollama client once."""
    return LLM()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_brand() -> None:
    """
    Draw the product identity block at the top of the sidebar: a logo
    mark, product name, and tagline. Pure static HTML — no user data
    is interpolated, so unsafe_allow_html carries no injection risk.
    """
    st.markdown(
        '<div class="brand">'
        '<div class="brand-mark">C</div>'
        '<div>'
        '<div class="brand-name">ContextIQ</div>'
        '<div class="brand-tagline">Private AI-Powered Document Intelligence</div>'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_new_chat_button() -> None:
    """
    Draw the "New chat" action — the ChatGPT/Claude-standard way to
    reset a conversation. This clears only st.session_state (pure
    frontend state); it never touches the indexed documents or the
    database, so it's safe regardless of how large the knowledge
    base is.
    """
    if st.button("New chat", icon="➕", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


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
            with st.spinner(f"Indexing {safe_name}..."):
                num_chunks = ingest_file(file_path)
            st.success(f"Added '{safe_name}' ({num_chunks} chunks).")
        except Exception as e:
            logger.exception("Ingestion failed for '%s'", safe_name)
            st.error(f"Failed to ingest '{safe_name}': {e}")


def render_knowledge_base_section() -> None:
    """
    Draw the "Knowledge Base" card: upload, indexed files, and the
    clear-database action.

    The headline number here is DOCUMENTS, not vectors — "vectors" is
    an implementation detail a recruiter or first-time user has no
    reason to know, and leading with it reads like a debug panel
    rather than a product. The raw vector count still exists (nothing
    is hidden) but lives in the "Model details" expander below, where
    someone who wants the technical picture can find it.
    """
    st.subheader("Knowledge Base")

    with st.container(border=True):
        # --- Upload + indexing -----------------------------------------
        # Uploading only stages files; nothing is processed until the
        # user explicitly clicks "Index Documents".
        uploaded_files = st.file_uploader(
            "Upload documents",
            type=["pdf", "txt"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        if uploaded_files and st.button(
            "Index Documents", use_container_width=True, type="primary"
        ):
            handle_upload(uploaded_files)

        # --- Status ------------------------------------------------------
        # Reading status fresh on every rerun keeps the numbers honest
        # right after an upload or a clear.
        try:
            filenames = get_stored_filenames()
        except Exception as e:
            st.error(f"Could not read database status: {e}")
            return

        st.metric("Documents indexed", len(filenames))
        if filenames:
            st.caption("Files")
            for name in filenames[:MAX_VISIBLE_FILES]:
                icon = "📕" if name.lower().endswith(".pdf") else "📄"
                st.caption(f"{icon} {name}")
            remaining = len(filenames) - MAX_VISIBLE_FILES
            if remaining > 0:
                st.caption(f"+ {remaining} more")
        else:
            st.caption("No documents indexed yet.")

        # --- Clear ---------------------------------------------------------
        if st.button("Clear database", use_container_width=True):
            try:
                clear_database()
                # The cached Retriever holds a handle to the deleted
                # collection — drop the cache so it reconnects cleanly.
                st.cache_resource.clear()
                st.success("Database cleared.")
                st.rerun()  # refresh the status panel immediately
            except Exception as e:
                st.error(f"Failed to clear database: {e}")


def render_details_expander() -> None:
    """
    Draw a collapsed, read-only "Model details" expander showing the
    values already defined in config.py (embedding model, LLM model,
    chunking, retrieval depth) plus the raw vector count.

    This only DISPLAYS existing configuration — no inputs, changes
    nothing — so backend behavior stays exactly as it is. It's
    collapsed by default and visually secondary to the Knowledge Base
    card on purpose: this is diagnostic detail for someone curious
    about the internals, not information a first-time visitor needs
    in their first ten seconds.
    """
    try:
        vector_count = get_vector_count()
    except Exception:
        vector_count = "—"

    rows = [
        ("Embedding model", EMBEDDING_MODEL_NAME),
        ("LLM model", LLM_MODEL_NAME),
        ("Chunk size", f"{CHUNK_SIZE} chars"),
        ("Chunk overlap", f"{CHUNK_OVERLAP} chars"),
        ("Chunks retrieved per query", TOP_K),
        ("Vectors stored", vector_count),
    ]
    rows_html = "".join(
        f'<div class="settings-row">'
        f'<span class="label">{html.escape(str(label))}</span>'
        f'<span class="value">{html.escape(str(value))}</span>'
        f"</div>"
        for label, value in rows
    )
    with st.expander("Model details", icon="⚙️", expanded=False):
        st.markdown(rows_html, unsafe_allow_html=True)


def render_footer() -> None:
    """
    Draw the "Built with ..." credit line pinned to the sidebar's
    bottom edge (via the .st-key-sidebar-footer CSS rule, which needs
    this exact container key to target it).
    """
    with st.container(key="sidebar-footer"):
        st.markdown(
            '<div class="sidebar-footer-text">Built with<br>'
            "<b>LangChain</b> · <b>ChromaDB</b> · <b>Ollama</b> · <b>Streamlit</b>"
            "</div>",
            unsafe_allow_html=True,
        )


def render_sidebar() -> None:
    """Assemble the full sidebar: brand, new chat, knowledge base, details, footer."""
    with st.sidebar:
        render_brand()
        render_new_chat_button()
        st.divider()
        render_knowledge_base_section()
        render_details_expander()
        render_footer()


# ---------------------------------------------------------------------------
# Main page: hero, chat
# ---------------------------------------------------------------------------


def render_hero(has_messages: bool) -> None:
    """
    Draw the page's title.

    A real st.title() is used (wrapped in a keyed container) so the
    page always has exactly one semantic <h1> — screen-reader users
    navigating by heading rely on this. Only the VISUAL treatment
    changes with conversation state: full-size with a subtitle and a
    short getting-started hint before the first message (mirroring
    ChatGPT/Claude's centered empty-state greeting), collapsed to a
    small persistent label once a conversation is under way so the
    chat history doesn't have to compete with a large banner for
    space.
    """
    if has_messages:
        with st.container(key="hero-compact"):
            st.title("ContextIQ")
        return

    with st.container(key="hero-full"):
        st.title("ContextIQ")
    st.caption("Private AI-Powered Document Intelligence")

    try:
        has_documents = get_vector_count() > 0
    except Exception:
        has_documents = True  # fail silent here; sidebar surfaces DB errors

    if has_documents:
        st.caption("💬 Ask a question about your documents below.")
    else:
        st.caption("📤 Upload a PDF or TXT file in the sidebar to get started.")


def render_sources(sources: list[dict]) -> None:
    """
    Show which chunks an answer was based on, as a compact row per
    source inside a collapsible expander: filename, chunk id, and
    similarity score.

    Filenames and chunk ids ultimately trace back to user-uploaded
    file names, so they are HTML-escaped before being embedded in
    the raw HTML row — otherwise a file named e.g. "<img src=x
    onerror=...>.txt" could inject a script into the page.
    """
    with st.expander(f"Sources · {len(sources)}", icon="🔗"):
        rows_html = "".join(
            '<div class="source-row">'
            f'<span class="source-file">{html.escape(s["filename"])}</span>'
            f'<span class="source-chunk">{html.escape(s["chunk_id"])}</span>'
            f'<span class="source-score">{s["similarity"] * 100:.1f}%</span>'
            "</div>"
            for s in sources
        )
        st.markdown(f'<div class="source-list">{rows_html}</div>', unsafe_allow_html=True)


def render_answer_body(content: str, sources: list[dict] | None) -> None:
    """
    Render one assistant answer: its text, then its sources card if
    any. Shared by chat-history replay and live answer rendering
    (via a placeholder swap) so the two paths can never visually
    drift apart from each other.
    """
    st.markdown(content)
    if sources:
        render_sources(sources)


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
            if message["role"] == "assistant":
                render_answer_body(message["content"], message.get("sources"))
            else:
                st.markdown(message["content"])

    # Handle a new question, if one was submitted. st.chat_input
    # already blocks truly empty submissions in the browser; the
    # strip() check additionally rejects whitespace-only input.
    question = st.chat_input("Ask anything about your documents...")
    if not question or not question.strip():
        return
    question = question.strip()

    # Show and store the user's message.
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Generate the assistant's reply. A placeholder shows the typing
    # indicator first, then is swapped for the real answer — the one
    # animated element in the chat, matching the ChatGPT/Claude
    # convention of showing the assistant "thinking".
    with st.chat_message("assistant"):
        placeholder = st.empty()
        with placeholder.container():
            st.markdown(TYPING_INDICATOR_HTML, unsafe_allow_html=True)

        try:
            result = answer_question(question, get_retriever(), get_llm())
        except Exception:
            # Most likely cause: the Ollama server isn't running. The
            # raw exception is logged server-side for debugging, but
            # never shown to the user — a leaked stack trace/connection
            # string in the chat reads as unpolished and unprofessional.
            logger.exception("Answer generation failed")
            placeholder.empty()
            st.error(
                "Could not generate an answer. Is Ollama running? "
                "Start it and try again."
            )
            return

        with placeholder.container():
            render_answer_body(result["answer"], result["sources"])

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["answer"],
            "sources": result["sources"],
        }
    )
    # Without this, render_hero() at the top of THIS run already
    # executed with the pre-question message count, so the first-ever
    # question would show the full-size hero and the new exchange
    # stacked together — it only catches up to "compact" on the NEXT
    # rerun. Forcing one now makes the hero collapse immediately,
    # matching the ChatGPT/Claude behavior of the greeting disappearing
    # the moment a conversation starts.
    st.rerun()


def main() -> None:
    """Assemble the page: config, session state, hero, sidebar, chat."""
    st.set_page_config(page_title="ContextIQ", page_icon="🧠", layout="centered")
    load_css()

    # Initialise chat history once per browser session.
    if "messages" not in st.session_state:
        st.session_state.messages = []

    render_hero(has_messages=bool(st.session_state.messages))
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
