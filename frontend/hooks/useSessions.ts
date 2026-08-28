import { useState, useEffect, useCallback, useRef } from "react";
import type { ChatSession, ChatMessage } from "@/lib/types";

const STORAGE_KEY = "contextiq.sessions.v1";

export function useSessions() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const loadedRef = useRef(false);

  // Load from sessionStorage on mount
  useEffect(() => {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    let parsed: ChatSession[] = [];
    if (raw) {
      try {
        parsed = JSON.parse(raw) as ChatSession[];
      } catch (e) {
        console.error("Failed to parse sessions from sessionStorage", e);
      }
    }

    if (parsed.length === 0) {
      // Auto-create initial session if empty
      const initial: ChatSession = {
        id: crypto.randomUUID(),
        title: "New Chat",
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      parsed = [initial];
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(parsed));
    }

    setSessions(parsed);
    setActiveSessionId(parsed[0].id);
    loadedRef.current = true;
  }, []);

  // Sync to sessionStorage whenever sessions change
  const saveToStorage = useCallback((newSessions: ChatSession[]) => {
    if (!loadedRef.current) return;
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(newSessions));
    setSessions(newSessions);
  }, []);

  const activeSession = sessions.find((s) => s.id === activeSessionId) || null;

  const createSession = useCallback(() => {
    const newSession: ChatSession = {
      id: crypto.randomUUID(),
      title: "New Chat",
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    const updated = [newSession, ...sessions];
    saveToStorage(updated);
    setActiveSessionId(newSession.id);
  }, [sessions, saveToStorage]);

  const switchSession = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  const renameSession = useCallback((id: string, title: string) => {
    const updated = sessions.map((s) => {
      if (s.id === id) {
        return { ...s, title: title.slice(0, 45), updatedAt: Date.now() };
      }
      return s;
    });
    saveToStorage(updated);
  }, [sessions, saveToStorage]);

  const deleteSession = useCallback((id: string) => {
    let updated = sessions.filter((s) => s.id !== id);
    if (updated.length === 0) {
      // Never allow 0 sessions — create a fresh one
      const fresh: ChatSession = {
        id: crypto.randomUUID(),
        title: "New Chat",
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      updated = [fresh];
    }
    saveToStorage(updated);

    if (activeSessionId === id) {
      setActiveSessionId(updated[0].id);
    }
  }, [sessions, activeSessionId, saveToStorage]);

  const saveMessages = useCallback(
    (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
      if (!activeSessionId) return;
      setSessions((prevSessions) => {
        const updated = prevSessions.map((s) => {
          if (s.id === activeSessionId) {
            const nextMessages =
              typeof updater === "function" ? updater(s.messages) : updater;
            let title = s.title;
            // Auto-generate title from first user query if still default title
            if (title === "New Chat" && nextMessages.length > 0) {
              const firstUser = nextMessages.find((m) => m.role === "user");
              if (firstUser) {
                title = firstUser.content.slice(0, 45);
              }
            }
            return {
              ...s,
              messages: nextMessages,
              title,
              updatedAt: Date.now(),
            };
          }
          return s;
        });
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        return updated;
      });
    },
    [activeSessionId]
  );

  return {
    sessions,
    activeSession,
    activeSessionId,
    createSession,
    switchSession,
    renameSession,
    deleteSession,
    saveMessages,
  };
}
