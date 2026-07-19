"use client";

// Conversation state + the POST /chat mutation, shared through
// context so the chat area (messages, typing) and the right panel
// (recent sources) read the same conversation without prop drilling.
//
// Persistence: the conversation is mirrored into sessionStorage, so
// a page REFRESH restores it but closing the tab clears it — the
// right privacy posture for a private-documents tool. (The knowledge
// base itself always persists server-side.)

import { useMutation, useQueryClient } from "@tanstack/react-query";
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

import type { ChatMessage } from "@/components/chat/message-bubble";
import { api } from "@/lib/api";
import type { DocumentsResponse, Source } from "@/lib/types";

const STORAGE_KEY = "contextiq.chat.v1";

interface ChatContextValue {
  messages: ChatMessage[];
  /** Sources of the most recent assistant answer (right panel). */
  lastSources: Source[];
  isThinking: boolean;
  sendMessage: (question: string) => void;
  addSystemMessage: (content: string) => void;
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

  const mutation = useMutation({
    mutationFn: api.chat,
    onSuccess: (result) => {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: result.answer,
          timestamp: now(),
          sources: result.sources,
        },
      ]);
      // Empty-knowledge-base guidance: the backend answers honestly
      // ("I don't know...") without calling the LLM, but a new user
      // deserves to be told WHY and what to do next.
      if (result.sources.length === 0) {
        const docs =
          queryClient.getQueryData<DocumentsResponse>(["documents"]);
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
    onError: (error) => {
      // Record the failure in the transcript AND toast it — a chat
      // where questions silently vanish feels broken.
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "system",
          content: `Answer failed: ${error.message}`,
        },
      ]);
      toast.error("Could not generate an answer", {
        description: error.message,
      });
    },
  });

  // useCallback: quick-action cards and the input share this without
  // re-rendering the whole tree on each keystroke elsewhere.
  const { mutate } = mutation;
  const sendMessage = useCallback(
    (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || mutation.isPending) return;
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "user",
          content: trimmed,
          timestamp: now(),
        },
      ]);
      mutate(trimmed);
    },
    [mutate, mutation.isPending],
  );

  const addSystemMessage = useCallback((content: string) => {
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "system", content },
    ]);
  }, []);

  const lastSources = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const sources = messages[i].sources;
      if (sources && sources.length > 0) return sources;
    }
    return [];
  }, [messages]);

  const value: ChatContextValue = {
    messages,
    lastSources,
    isThinking: mutation.isPending,
    sendMessage,
    addSystemMessage,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used inside <ChatProvider>");
  return ctx;
}
