"use client";

// Sticky chat input — now functional: submitting sends the question
// through the shared chat context (POST /chat). Enter submits (the
// form's native behavior, matching the keyboard hint); the send
// button disables while an answer is generating. Styling unchanged.

import { Loader2, Send } from "lucide-react";
import { useState } from "react";

import { useChat } from "@/hooks/useChat";

export function ChatInput() {
  const { sendMessage, isThinking } = useChat();
  const [value, setValue] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const question = value.trim();
    if (!question || isThinking) return;
    sendMessage(question);
    setValue("");
  }

  return (
    <div className="sticky bottom-0 border-t border-border bg-background px-4 pb-3 pt-4">
      <div className="mx-auto w-full max-w-3xl">
        <form
          onSubmit={submit}
          className="flex items-center gap-2 rounded-lg border border-input bg-card px-4 py-3 transition-colors duration-150 focus-within:border-ring"
        >
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Ask anything about your knowledge..."
            aria-label="Chat input"
            className="flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted-foreground"
          />
          <button
            type="submit"
            disabled={isThinking || value.trim().length === 0}
            aria-label={isThinking ? "Generating answer…" : "Send"}
            className="flex size-8 shrink-0 items-center justify-center rounded-sm bg-primary text-primary-foreground transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isThinking ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Send className="size-4" aria-hidden />
            )}
          </button>
        </form>

        {/* Keyboard hint — quiet, right-aligned under the field. */}
        <p className="mt-1.5 text-right text-xs text-muted-foreground/70">
          Press{" "}
          <kbd className="rounded-sm border border-border bg-secondary px-1 py-0.5 font-mono text-[10px]">
            Enter
          </kbd>{" "}
          to send
        </p>
      </div>
    </div>
  );
}
