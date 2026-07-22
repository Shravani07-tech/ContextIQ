"use client";

// Conversation state + streaming chat, shared through context so the
// chat area (messages, live streaming bubble) and the right panel
// (recent sources) read the same conversation without prop drilling.
//
// Persistence: the conversation is mirrored into sessionStorage, so
// a page REFRESH restores it but closing the tab clears it — the
// right privacy posture for a private-documents tool. (The knowledge
// base itself always persists server-side.)
//
// Streaming model: `isThinking` is true from send until the FIRST
// token arrives (the pre-content wait); `isStreaming` is true while
// tokens are actively arriving. Only one of the two is ever true at
// once. `streamingContent`/`streamingSources` hold the in-flight
// answer for live rendering — they're not `ChatMessage`s yet; the
// answer only becomes a permanent message once it finishes (done,
// stopped, or errored-with-partial-content).

import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { ChatMessage, DocumentsResponse, Source } from "@/lib/types";

const STORAGE_KEY = "contextiq.chat.v1";

interface ChatContextValue {
  messages: ChatMessage[];
  /** Sources of the most recent assistant answer (right panel). */
  lastSources: Source[];
  isThinking: boolean;
  isStreaming: boolean;
  streamingContent: string;
  streamingSources: Source[];
  sendMessage: (question: string) => void;
  addSystemMessage: (content: string) => void;
  stopGeneration: () => void;
  regenerate: () => void;
  clearConversation: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

function now(): string {
  return new Date().toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const queryClient = useQueryClient();

  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingSources, setStreamingSources] = useState<Source[]>([]);
  // Holds the in-flight stream's abort handle so stopGeneration()
  // (called from a button, outside runQuery's own scope) can reach
  // it — same pattern as useUpload's cancelRef.
  const abortRef = useRef<AbortController | null>(null);

  // --- sessionStorage persistence ---------------------------------------
  // Restore once after mount (not in the useState initializer: that
  // would run during SSR/hydration and mismatch the server markup).
  // The `restored` gate stops the write effect from clobbering the
  // stored conversation with the initial empty array.
  const restored = useRef(false);
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (raw) setMessages(JSON.parse(raw) as ChatMessage[]);
    } catch {
      // Corrupt/blocked storage — start fresh rather than crash.
    }
    restored.current = true;
  }, []);

  useEffect(() => {
    if (!restored.current) return;
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {
      // Storage full/blocked — the app still works, just unpersisted.
    }
  }, [messages]);

  // Abort any in-flight stream if the provider unmounts mid-answer
  // (e.g. hot reload during development).
  useEffect(() => () => abortRef.current?.abort(), []);

  /** Append the finished answer as a permanent message, plus the
      same empty-knowledge-base guidance the non-streaming version
      had: the backend answers honestly ("I don't know...") without
      calling the LLM, but a new user deserves to be told why. */
  const finalizeAnswer = useCallback(
    (content: string, sources: Source[]) => {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content,
          timestamp: now(),
          sources,
        },
      ]);
      if (sources.length === 0) {
        const docs = queryClient.getQueryData<DocumentsResponse>(["documents"]);
        if (docs && docs.documents.length === 0) {
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: "system",
              content:
                "Your knowledge base is empty — upload documents in the sidebar to get grounded answers.",
            },
          ]);
        }
      }
    },
    [queryClient],
  );

  /** The shared engine behind sendMessage/regenerate/retry: run the
      streaming pipeline for one question and manage all the
      thinking/streaming state around it. Does NOT touch the user
      bubble — callers decide whether to add one first. */
  const runQuery = useCallback(
    (question: string) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setIsThinking(true);
      setIsStreaming(false);
      setStreamingContent("");
      setStreamingSources([]);

      let accumulated = "";
      let sources: Source[] = [];

      api.chatStream(
        question,
        {
          onSources: (s) => {
            sources = s;
            setStreamingSources(s);
          },
          onToken: (text) => {
            accumulated += text;
            setIsThinking(false);
            setIsStreaming(true);
            setStreamingContent(accumulated);
          },
          onDone: () => {
            abortRef.current = null;
            setIsThinking(false);
            setIsStreaming(false);
            setStreamingContent("");
            setStreamingSources([]);
            finalizeAnswer(
              accumulated || "I don't know based on the provided documents.",
              sources,
            );
          },
          onError: (detail) => {
            abortRef.current = null;
            setIsThinking(false);
            setIsStreaming(false);
            setStreamingContent("");
            setStreamingSources([]);
            // Keep whatever tokens arrived before it broke, rather
            // than discarding a partial answer the user was already
            // reading.
            if (accumulated) finalizeAnswer(accumulated, sources);
            setMessages((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "system",
                content: `Answer failed: ${detail}`,
                retryQuestion: question,
              },
            ]);
            toast.error("Could not generate an answer", { description: detail });
          },
        },
        controller.signal,
      );
    },
    [finalizeAnswer],
  );

  const sendMessage = useCallback(
    (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || isThinking || isStreaming) return;
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "user",
          content: trimmed,
          timestamp: now(),
        },
      ]);
      runQuery(trimmed);
    },
    [isThinking, isStreaming, runQuery],
  );

  /** Stop the in-flight answer. Whatever streamed in so far becomes
      the final message (not discarded) — matching how stopping a
      ChatGPT/Claude answer keeps the partial response. */
  const stopGeneration = useCallback(() => {
    const controller = abortRef.current;
    if (!controller) return;
    controller.abort();
    abortRef.current = null;
    setIsThinking(false);
    setIsStreaming(false);
    if (streamingContent) {
      finalizeAnswer(streamingContent, streamingSources);
    } else {
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "system", content: "Generation stopped" },
      ]);
    }
    setStreamingContent("");
    setStreamingSources([]);
  }, [streamingContent, streamingSources, finalizeAnswer]);

  /** Re-run the LAST question, replacing its answer in place — the
      old assistant message (and anything after it, e.g. a stray
      system notice) is dropped rather than appended twice, matching
      the ChatGPT/Claude "regenerate replaces" convention. Only ever
      offered on the latest answer (see MessageBubble). */
  const regenerate = useCallback(() => {
    if (isThinking || isStreaming) return;
    let lastUserIdx = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        lastUserIdx = i;
        break;
      }
    }
    if (lastUserIdx === -1) return;
    const question = messages[lastUserIdx].content;
    setMessages(messages.slice(0, lastUserIdx + 1));
    runQuery(question);
  }, [messages, isThinking, isStreaming, runQuery]);

  const addSystemMessage = useCallback((content: string) => {
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "system", content },
    ]);
  }, []);

  /** Start a fresh conversation. Does not touch the knowledge base —
      only the client-side transcript. */
  const clearConversation = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsThinking(false);
    setIsStreaming(false);
    setStreamingContent("");
    setStreamingSources([]);
    setMessages([]);
  }, []);

  const lastSources = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const sources = messages[i].sources;
      if (sources && sources.length > 0) return sources;
    }
    return [];
  }, [messages]);

  const value = useMemo<ChatContextValue>(
    () => ({
      messages,
      lastSources,
      isThinking,
      isStreaming,
      streamingContent,
      streamingSources,
      sendMessage,
      addSystemMessage,
      stopGeneration,
      regenerate,
      clearConversation,
    }),
    [
      messages,
      lastSources,
      isThinking,
      isStreaming,
      streamingContent,
      streamingSources,
      sendMessage,
      addSystemMessage,
      stopGeneration,
      regenerate,
      clearConversation,
    ],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used inside <ChatProvider>");
  return ctx;
}
