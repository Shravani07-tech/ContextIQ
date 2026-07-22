"use client";

// Chat message bubbles — DESIGN.md §11.
// Three roles: user (right-aligned, blue tint, 82% max width, plain
// text — it's what the person typed, not model output), assistant
// (left, card surface, full column width, rich markdown), and system
// (centered pill for events like "database cleared"). Timestamps
// fade in on hover — present when wanted, silent otherwise.
//
// System messages that failed to answer carry a retryQuestion and
// render a Retry button that resends the exact same question,
// closing the loop without the user retyping anything.
//
// Assistant messages get Copy (always) and Regenerate (only on the
// LATEST assistant answer, via isLastAssistant — regenerating an
// older answer while newer messages exist afterward would orphan
// the conversation that followed it).

import { AlertCircle, RotateCcw } from "lucide-react";

import { MarkdownContent } from "@/components/chat/markdown-content";
import { SourceCards } from "@/components/chat/source-cards";
import { CopyButton } from "@/components/shared/copy-button";
import { useChat } from "@/hooks/useChat";
import type { ChatMessage } from "@/lib/types";

export function MessageBubble({
  message,
  isLastAssistant = false,
}: {
  message: ChatMessage;
  isLastAssistant?: boolean;
}) {
  const { sendMessage, regenerate } = useChat();

  if (message.role === "system") {
    // retryQuestion is set ONLY on failed-answer messages (useChat's
    // onError) — every other system message (cleared database,
    // empty-KB notice, "Generation stopped") never sets it, so it's
    // a reliable signal for "this pill is an error, not a routine
    // notice" without adding a new field. A real failure gets the
    // error-tinted treatment already used elsewhere (sidebar/panel
    // error cards) instead of blending into the same neutral pill as
    // benign events.
    const isError = Boolean(message.retryQuestion);
    return (
      <div className="flex flex-col items-center gap-2">
        <span
          className={
            isError
              ? "flex items-center gap-1.5 rounded-full border border-error/40 bg-error-soft px-3 py-1 text-xs text-error"
              : "rounded-full border border-border bg-secondary px-3 py-1 text-xs text-muted-foreground"
          }
        >
          {isError && <AlertCircle className="size-3" aria-hidden />}
          {message.content}
        </span>
        {message.retryQuestion && (
          <button
            type="button"
            onClick={() => sendMessage(message.retryQuestion!)}
            className="flex items-center gap-1.5 rounded-sm border border-border bg-secondary px-2 py-1 text-xs transition-colors duration-150 hover:bg-accent"
          >
            <RotateCcw className="size-3" aria-hidden />
            Retry
          </button>
        )}
      </div>
    );
  }

  const isUser = message.role === "user";

  return (
    <div
      className={`group flex flex-col gap-1 ${
        isUser ? "items-end" : "items-start"
      }`}
    >
      <div
        className={
          isUser
            ? "max-w-[92%] rounded-lg border border-chat-user-border bg-chat-user px-4 py-3 sm:max-w-[82%]"
            : "w-full rounded-lg border border-border bg-chat-assistant px-5 py-4"
        }
      >
        {isUser ? (
          // Plain text: whitespace-pre-line keeps the user's own
          // line breaks without needing a markdown renderer.
          <p className="whitespace-pre-line text-[15px] leading-relaxed">
            {message.content}
          </p>
        ) : (
          <MarkdownContent content={message.content} />
        )}
        {/* Citations under the answer (assistant messages only). */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceCards sources={message.sources} />
        )}
      </div>

      <div className="flex items-center gap-1 px-1">
        {message.timestamp && (
          <span
            className={`text-xs tabular-nums text-muted-foreground opacity-0 transition-opacity duration-150 group-hover:opacity-100 ${
              isUser ? "text-right" : "text-left"
            }`}
          >
            {message.timestamp}
          </span>
        )}
        {!isUser && (
          <div className="flex items-center gap-0.5 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
            <CopyButton
              text={message.content}
              label="Copy answer"
              className="p-1"
            />
            {isLastAssistant && (
              <button
                type="button"
                onClick={regenerate}
                aria-label="Regenerate answer"
                title="Regenerate"
                className="flex items-center justify-center rounded-sm p-1 text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground"
              >
                <RotateCcw className="size-3.5" aria-hidden />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
