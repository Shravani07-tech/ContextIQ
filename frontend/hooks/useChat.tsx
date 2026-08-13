"use client";

// Conversation state + streaming chat + session management.
// All chat state is shared through context so the chat area,
// sidebar (session list), and right panel (recent sources) read
// the same state without prop drilling.
//
// Sessions: each "chat" is a named conversation with its own message
// history, stored in localStorage via useSessions. Sessions survive
// page refreshes. Data isolation: deleting a session never affects
// indexed documents; indexing/deleting documents never affects sessions.
//
// Streaming model: unchanged from v1.0. isThinking = waiting for first
// token; isStreaming = tokens arriving. Only one is ever true at once.
//
// Disambiguation: when a question seems to reference "the document"
// generically AND 2+ documents are indexed, a picker appears before
// the question is sent. The existing aggregate-score retrieval in
// rag.py is the authoritative isolation mechanism; this is a UX assist.

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
import type {
  ChatMessage,
  ChatSession,
  DocumentsResponse,
  HistoryMessage,
  Source,
} from "@/lib/types";
import { useSessions } from "./useSessions";

// ---------------------------------------------------------------------------
// Disambiguation detection
// ---------------------------------------------------------------------------

const AMBIGUOUS_PATTERNS = [
  /\bsummar(?:ize|ise|y)\b/i,
  /\b(?:the\s+)?(?:document|paper|file|report|article|study|thesis|text|publication)\b/i,
  /\bthis\s+(?:paper|doc(?:ument)?|article|file|report)\b/i,
  /\bwhat\s+(?:is|are|does)\s+(?:this|the)\s+(?:paper|doc(?:ument)?|article|study)\b/i,
  /\bauthor(?:s)?\s+of\s+(?:the|this)\b/i,
  /\btitle\s+of\s+(?:the|this)\b/i,
  /\blimitation(?:s)?\s+of\s+(?:the|this)\b/i,
];

function isAmbiguousQuery(question: string): boolean {
  return AMBIGUOUS_PATTERNS.some((p) => p.test(question));
}

function now(): string {
  return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export interface DisambiguationPending {
  question: string;
}

export interface ChatContextValue {
  messages: ChatMessage[];
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
  // sessions
  sessions: ChatSession[];
  activeSessionId: string | null;
  createNewChat: () => void;
  switchSession: (id: string) => void;
  renameSession: (id: string, title: string) => void;
  deleteSession: (id: string) => void;
  // disambiguation
  disambiguationPending: DisambiguationPending | null;
  resolveDisambiguation: (documentFilter: string | null) => void;
  cancelDisambiguation: () => void;
  // document filter / multi-doc selector
  documentFilter: string | null;
  setDocumentFilter: (filter: string | null) => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();

  const {
    sessions,
    activeSession,
    activeSessionId,
    createSession,
    switchSession: rawSwitch,
    renameSession,
    deleteSession: rawDelete,
    saveMessages,
  } = useSessions();

  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingSources, setStreamingSources] = useState<Source[]>([]);
  const [disambiguationPending, setDisambiguationPending] =
    useState<DisambiguationPending | null>(null);
  // Document selector state: null = All Documents, string = specific filename
  const [documentFilter, setDocumentFilter] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  // Clean up any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), []);

  const messages: ChatMessage[] = activeSession?.messages ?? [];

  // Stable proxy to the session store — accepts functional updaters
  // for React 18 batching safety from async stream callbacks.
  const setMessages = useCallback(
    (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
      saveMessages(updater);
    },
    [saveMessages],
  );

  // -------------------------------------------------------------------------
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
    [queryClient, setMessages],
  );

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

      // Build bounded history from the current session's messages.
      // Only user and assistant roles are sent; system messages are UI-only.
      // Cap at 6 messages (enforced by the backend schema too).
      const sessionMessages = activeSession?.messages ?? [];
      const history: HistoryMessage[] = sessionMessages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .slice(-6)
        .map((m) => ({ role: m.role as "user" | "assistant", content: m.content }));

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
        { history, documentFilter },
      );
    },
    [finalizeAnswer, setMessages, activeSession, documentFilter],
  );

  // -------------------------------------------------------------------------
  const sendMessage = useCallback(
    (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || isThinking || isStreaming) return;

      // Only show disambiguation when no specific document is already selected
      const docs = queryClient.getQueryData<DocumentsResponse>(["documents"]);
      const docCount = docs?.documents.length ?? 0;
      if (!documentFilter && docCount >= 2 && isAmbiguousQuery(trimmed)) {
        setDisambiguationPending({ question: trimmed });
        return;
      }

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
    [isThinking, isStreaming, queryClient, setMessages, runQuery, documentFilter],
  );

  const resolveDisambiguation = useCallback(
    (documentFilter: string | null) => {
      const pending = disambiguationPending;
      setDisambiguationPending(null);
      if (!pending) return;
      const finalQuestion = documentFilter
        ? `${pending.question} (focusing on the document: "${documentFilter}")`
        : pending.question;
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "user",
          content: pending.question,
          timestamp: now(),
        },
      ]);
      runQuery(finalQuestion);
    },
    [disambiguationPending, setMessages, runQuery],
  );

  const cancelDisambiguation = useCallback(() => {
    setDisambiguationPending(null);
  }, []);

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
  }, [streamingContent, streamingSources, finalizeAnswer, setMessages]);

  const regenerate = useCallback(() => {
    if (isThinking || isStreaming) return;
    let lastUserIdx = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") { lastUserIdx = i; break; }
    }
    if (lastUserIdx === -1) return;
    const question = messages[lastUserIdx].content;
    setMessages(messages.slice(0, lastUserIdx + 1));
    runQuery(question);
  }, [messages, isThinking, isStreaming, runQuery, setMessages]);

  const addSystemMessage = useCallback(
    (content: string) => {
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "system", content },
      ]);
    },
    [setMessages],
  );

  const clearConversation = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsThinking(false);
    setIsStreaming(false);
    setStreamingContent("");
    setStreamingSources([]);
    setMessages([]);
  }, [setMessages]);

  // --- Session management wrappers (abort stream before context switch) ---
  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsThinking(false);
    setIsStreaming(false);
    setStreamingContent("");
    setStreamingSources([]);
  }, []);

  const createNewChat = useCallback(() => {
    stopStream();
    createSession();
  }, [stopStream, createSession]);

  const switchSession = useCallback(
    (id: string) => { stopStream(); rawSwitch(id); },
    [stopStream, rawSwitch],
  );

  const deleteSession = useCallback(
    (id: string) => { if (id === activeSessionId) stopStream(); rawDelete(id); },
    [activeSessionId, stopStream, rawDelete],
  );

  // -------------------------------------------------------------------------
  const lastSources = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const s = messages[i].sources;
      if (s && s.length > 0) return s;
    }
    return [];
  }, [messages]);

  const value = useMemo<ChatContextValue>(
    () => ({
      messages, lastSources, isThinking, isStreaming, streamingContent,
      streamingSources, sendMessage, addSystemMessage, stopGeneration,
      regenerate, clearConversation, sessions, activeSessionId,
      createNewChat, switchSession, renameSession, deleteSession,
      disambiguationPending, resolveDisambiguation, cancelDisambiguation,
      documentFilter, setDocumentFilter,
    }),
    [
      messages, lastSources, isThinking, isStreaming, streamingContent,
      streamingSources, sendMessage, addSystemMessage, stopGeneration,
      regenerate, clearConversation, sessions, activeSessionId,
      createNewChat, switchSession, renameSession, deleteSession,
      disambiguationPending, resolveDisambiguation, cancelDisambiguation,
      documentFilter, setDocumentFilter,
    ],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used inside <ChatProvider>");
  return ctx;
}
