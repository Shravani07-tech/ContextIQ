"use client";

// Chat-level actions bar: document selector dropdown, clear conversation,
// and memory indicator. Shown once a conversation exists.
// The document selector drives the documentFilter in useChat, which is sent
// with every /chat/stream request to restrict retrieval to one document.

import { ChevronDown, Eraser, FileText, Files, MemoryStick } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { useChat } from "@/hooks/useChat";
import { useDocuments } from "@/hooks/useDocuments";
import { confirmToast } from "@/lib/confirm-toast";

export function ChatToolbar() {
  const { clearConversation, documentFilter, setDocumentFilter, messages } = useChat();
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
      {/* Document selector */}
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
