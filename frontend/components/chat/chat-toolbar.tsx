"use client";

// Chat-level actions bar — shown once a conversation exists. Only
// one action today (clear), but scoped as its own component since
// it's conceptually separate from the message transcript itself.

import { Eraser } from "lucide-react";

import { useChat } from "@/hooks/useChat";
import { confirmToast } from "@/lib/confirm-toast";

export function ChatToolbar() {
  const { clearConversation } = useChat();

  function confirmClear() {
    confirmToast({
      title: "Clear this conversation?",
      description: "Only the chat is cleared — your documents are untouched.",
      actionLabel: "Clear",
      onConfirm: clearConversation,
    });
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl justify-end px-1 pb-2">
      <button
        type="button"
        onClick={confirmClear}
        className="flex items-center gap-1.5 rounded-sm border border-border bg-secondary px-2 py-1 text-xs text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground"
      >
        <Eraser className="size-3.5" aria-hidden />
        Clear conversation
      </button>
    </div>
  );
}
