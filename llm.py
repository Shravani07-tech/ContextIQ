# llm.py
#
# Thin, reusable client for a locally running Ollama server. All
# LLM-communication code lives in this one module (mirroring how
# vector_store.py isolates database code): rag.py asks this class
# for text and never deals with HTTP details. Swapping Ollama for a
# different LLM backend would only change this file.

import json
from collections.abc import Iterator

import requests

from config import LLM_MODEL_NAME, OLLAMA_BASE_URL


class LLM:
    """
    Reusable client for chatting with a local Ollama model.

    Construction is cheap (no network call happens until generate()),
    and one instance can serve many requests -- the Streamlit app will
    later keep a single LLM alive across user questions.
    """

    def __init__(
        self,
        model: str = LLM_MODEL_NAME,
        base_url: str = OLLAMA_BASE_URL,
    ) -> None:
        """
        Store the model name and server address for later requests.

        Defaults come from config.py so every part of the app talks
        to the same model unless explicitly overridden.
        """
        self.model = model
        self.base_url = base_url

    # Generation options sent with every request:
    #   temperature  low -> factual, repeatable grounded answers.
    #   num_ctx      context window big enough for the retrieved context
    #                (~2.5k tokens) PLUS conversation history PLUS the answer,
    #                so Ollama never silently drops the FRONT of the prompt.
    #   num_predict  hard cap on answer length -> bounds worst-case CPU
    #                latency. On CPU, generation (~a few tokens/sec) is
    #                the dominant cost, so a tighter cap plus the "be
    #                concise" system prompt keeps typical answers well
    #                under it and roughly halves response time. 512 still
    #                leaves room for a short list without truncation.
    _OPTIONS = {"temperature": 0.1, "num_ctx": 4096, "num_predict": 512}

    # Keep the model resident between requests so no call pays a cold
    # reload -- those reloads were the cause of multi-minute stalls and
    # the occasional read timeout.
    _KEEP_ALIVE = "30m"

    def _payload(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        stream: bool,
        history: list[dict] | None = None,
    ) -> dict:
        """
        Build the /api/chat request body.

        Message order:
          1. system  -- grounding instructions (always first)
          2. history -- bounded prior turns in chronological order
             [{role: "user"|"assistant", content: "..."}]
             Memory does NOT affect document retrieval; it only gives the
             LLM awareness of the conversation so it can resolve references
             like "What are its weaknesses?" after "Summarize the methodology."
          3. user    -- the current question with retrieved context
        """
        messages: list[dict] = [{"role": "system", "content": system_prompt}]

        # Inject bounded history between system instructions and the current
        # question. Cap defensively here (schema already capped upstream).
        for turn in (history or [])[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_prompt})

        return {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": self._OPTIONS,
            "keep_alive": self._KEEP_ALIVE,
        }

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[dict] | None = None,
    ) -> str:
        """
        Send one chat request to Ollama and return the reply text.

        Uses Ollama's /api/chat endpoint with:
          - a "system" message carrying the grounding instructions,
          - optional prior conversation history for context continuity,
          - a "user" message carrying the retrieved context + question.
        Keeping instructions in the system role makes the model treat
        them as rules rather than as part of the question.

        stream=False returns the complete answer in one JSON response.
        temperature is set low because grounded question-answering
        should be factual and repeatable, not creative.
        raise_for_status() turns HTTP errors (e.g. Ollama not running,
        model not installed) into clear Python exceptions.
        """
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=self._payload(system_prompt, user_prompt, stream=False, history=history),
            # Local generation on CPU can be slow for long contexts,
            # so allow generous time before giving up.
            timeout=300,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[dict] | None = None,
    ) -> Iterator[str]:
        """
        Same request as generate(), but stream=True: Ollama responds
        with one newline-delimited JSON object per token (or small
        batch of tokens) instead of one big JSON blob at the end.
        Yields each text delta as it arrives.

        The connection is closed in `finally` regardless of how this
        generator's iteration ends -- including a caller abandoning it
        partway through (e.g. the client disconnected and the SSE
        route generator got torn down). Closing the underlying
        response tells Ollama the request is no longer wanted, so it
        stops spending CPU generating tokens nobody will see, instead
        of running to completion in the background regardless.
        """
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=self._payload(system_prompt, user_prompt, stream=True, history=history),
            stream=True,
            timeout=300,
        )
        response.raise_for_status()
        try:
            for line in response.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                text = chunk.get("message", {}).get("content", "")
                if text:
                    yield text
                if chunk.get("done"):
                    break
        finally:
            response.close()
