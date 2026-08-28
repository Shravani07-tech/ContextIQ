"use client";

// Chat-level actions bar: document selector dropdown, clear conversation,
// memory indicator, and Research Mode toggle.
// The document selector drives the documentFilter in useChat, which is sent
// with every /chat/stream request to restrict retrieval to one document.
// Research Mode bypasses the document selector and routes to /research/stream.

import { ChevronDown, Eraser, FileText, Files, Layers, MemoryStick, MessageSquare } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { useChat } from "@/hooks/useChat";
import { useDocuments } from "@/hooks/useDocuments";
import { confirmToast } from "@/lib/confirm-toast";

export function ChatToolbar() {
  const { clearConversation, documentFilter, setDocumentFilter, messages, isResearchMode, setIsResearchMode } = useChat();
  const { data: documents } = useDocuments();
  const docList = documents ?? [];

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Count bounded memory turns for display (user + assistant only)
  const memoryTurns = Math.min(
    messages.filter((m) => m.role === "user" || m.role === "assistant").length,
    6,
  );

  const handleSelect = useCallback(
    (value: string | null) => {
      setDocumentFilter(value);
      setDropdownOpen(false);
    },
    [setDocumentFilter],
  );

  function confirmClear() {
    confirmToast({
      title: "Clear this conversation?",
      description: "Only the chat is cleared — your documents are untouched.",
      actionLabel: "Clear",
      onConfirm: clearConversation,
    });
  }

  const selectedLabel = documentFilter
    ? docList.includes(documentFilter)
      ? documentFilter.length > 28
        ? documentFilter.slice(0, 26) + "…"
        : documentFilter
      : "All Documents" // selected doc was deleted
    : "All Documents";

  return (
    <div className="mx-auto flex w-full max-w-3xl items-center justify-between px-1 pb-2">
      {/* Left side: Mode toggle + doc selector */}
      <div className="flex items-center gap-2">
        {/* Research / Chat mode toggle */}
        <div className="flex rounded-sm border border-border bg-secondary p-0.5 text-xs">
          <button
            type="button"
            id="chat-mode-btn"
            onClick={() => setIsResearchMode(false)}
            title="Chat mode: ask questions about a single document or all documents"
            className={`flex items-center gap-1 rounded-[3px] px-2 py-0.5 transition-all duration-150 ${
              !isResearchMode
                ? "bg-background text-foreground shadow-sm font-medium"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <MessageSquare className="size-3" aria-hidden />
            Chat
          </button>
          <button
            type="button"
            id="research-mode-btn"
            onClick={() => setIsResearchMode(true)}
            title="Research mode: synthesize across all documents"
            className={`flex items-center gap-1 rounded-[3px] px-2 py-0.5 transition-all duration-150 ${
              isResearchMode
                ? "bg-background text-foreground shadow-sm font-medium"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Layers className="size-3" aria-hidden />
            Research
          </button>
        </div>

        {/* Document selector — hidden in Research Mode (always all-docs) */}
        {!isResearchMode && (
          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              id="doc-selector-btn"
              aria-haspopup="listbox"
              aria-expanded={dropdownOpen}
              onClick={() => setDropdownOpen((o) => !o)}
              className="flex items-center gap-1.5 rounded-sm border border-border bg-secondary px-2 py-1 text-xs text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground"
            >
              {documentFilter ? (
                <FileText className="size-3.5" aria-hidden />
              ) : (
                <Files className="size-3.5" aria-hidden />
              )}
              <span className="max-w-[180px] truncate">{selectedLabel}</span>
              <ChevronDown
                className={`size-3 transition-transform duration-150 ${dropdownOpen ? "rotate-180" : ""}`}
                aria-hidden
              />
            </button>

            {dropdownOpen && (
              <div
                role="listbox"
                aria-label="Select document scope"
                className="absolute bottom-full mb-1 left-0 z-50 min-w-[180px] max-w-[260px] overflow-hidden rounded-md border border-border bg-background shadow-lg"
              >
                <button
                  role="option"
                  aria-selected={!documentFilter}
                  type="button"
                  onClick={() => handleSelect(null)}
                  className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors duration-100 hover:bg-accent ${
                    !documentFilter ? "bg-accent text-foreground font-medium" : "text-muted-foreground"
                  }`}
                >
                  <Files className="size-3.5 shrink-0" aria-hidden />
                  All Documents
                </button>

                {docList.length > 0 && (
                  <div className="border-t border-border" />
                )}

                {docList.map((doc) => (
                  <button
                    key={doc}
                    role="option"
                    aria-selected={documentFilter === doc}
                    type="button"
                    onClick={() => handleSelect(doc)}
                    className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors duration-100 hover:bg-accent ${
                      documentFilter === doc
                        ? "bg-accent text-foreground font-medium"
                        : "text-muted-foreground"
                    }`}
                    title={doc}
                  >
                    <FileText className="size-3.5 shrink-0" aria-hidden />
                    <span className="truncate">{doc}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Research mode badge */}
        {isResearchMode && (
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
            All Documents · Synthesis
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {/* Memory indicator — shows how many turns are in context */}
        {memoryTurns > 0 && (
          <span
            className="flex items-center gap-1 text-[10px] text-muted-foreground"
            title={`${memoryTurns} message${memoryTurns !== 1 ? "s" : ""} in context (max 6)`}
          >
            <MemoryStick className="size-3" aria-hidden />
            {memoryTurns}/6
          </span>
        )}

        <button
          type="button"
          id="clear-conversation-btn"
          onClick={confirmClear}
          className="flex items-center gap-1.5 rounded-sm border border-border bg-secondary px-2 py-1 text-xs text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground"
        >
          <Eraser className="size-3.5" aria-hidden />
          Clear
        </button>
      </div>
    </div>
  );
}
