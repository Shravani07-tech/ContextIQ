"use client";

// Sticky chat input — submits the question through the shared chat
// context (POST /chat/stream). Auto-growing textarea: Enter sends,
// Shift+Enter inserts a newline (Shift+Enter only makes sense once
// the field can grow past one line, which is why it arrives together
// here). While an answer is thinking/streaming, the send button
// becomes a Stop button instead of just disabling — matching the
// ChatGPT/Claude convention of always having something to press.

import { Loader2, Send, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useChat } from "@/hooks/useChat";

// ~6 lines before the field scrolls internally instead of pushing
// the rest of the layout around indefinitely.
const MAX_TEXTAREA_HEIGHT = 160;

export function ChatInput() {
  const { sendMessage, isThinking, isStreaming, stopGeneration } = useChat();
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isGenerating = isThinking || isStreaming;

  // Auto-grow: collapse to the browser's natural height, then measure
  // content and grow up to the cap. Resetting to "auto" first is what
  // lets it SHRINK back down after deleting text, not just grow.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
  }, [value]);

  function submit() {
    const question = value.trim();
    if (!question || isGenerating) return;
    sendMessage(question);
    setValue("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="sticky bottom-0 border-t border-border bg-background px-4 pb-3 pt-4">
      <div className="mx-auto w-full max-w-3xl">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (isGenerating) stopGeneration();
            else submit();
          }}
          className="flex items-end gap-2 rounded-lg border border-input bg-card px-4 py-3 transition-colors duration-150 focus-within:border-ring"
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your knowledge..."
            aria-label="Chat input"
            className="max-h-40 flex-1 resize-none bg-transparent text-[15px] leading-relaxed outline-none placeholder:text-muted-foreground"
          />
          {isGenerating ? (
            <button
              type="submit"
              aria-label="Stop generating"
              title="Stop generating"
              className="flex size-8 shrink-0 items-center justify-center rounded-sm bg-secondary text-foreground transition-colors duration-150 hover:bg-error-soft hover:text-error"
            >
              {isThinking ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Square className="size-3.5 fill-current" aria-hidden />
              )}
            </button>
          ) : (
            <button
              type="submit"
              disabled={value.trim().length === 0}
              aria-label="Send"
              className="flex size-8 shrink-0 items-center justify-center rounded-sm bg-primary text-primary-foreground transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send className="size-4" aria-hidden />
            </button>
          )}
        </form>

        {/* Keyboard hint — quiet, right-aligned under the field. */}
        <p className="mt-1.5 text-right text-xs text-muted-foreground/70">
          <kbd className="rounded-sm border border-border bg-secondary px-1 py-0.5 font-mono text-[10px]">
            Enter
          </kbd>{" "}
          to send ·{" "}
          <kbd className="rounded-sm border border-border bg-secondary px-1 py-0.5 font-mono text-[10px]">
            Shift + Enter
          </kbd>{" "}
          for a new line
        </p>
      </div>
    </div>
  );
}
