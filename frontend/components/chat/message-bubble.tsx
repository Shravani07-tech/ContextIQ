// Chat message bubbles — DESIGN.md §11.
// Three roles: user (right-aligned, blue tint, 82% max width),
// assistant (left, card surface, full column width), and system
// (centered pill for events like "database cleared"). Timestamps
// fade in on hover — present when wanted, silent otherwise.

import { SourceCards } from "@/components/chat/source-cards";
import type { Source } from "@/lib/types";

export type ChatRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  /** Pre-formatted display time, e.g. "2:41 PM". */
  timestamp?: string;
  /** Chunks the answer was grounded on (assistant messages only);
      shown in the right panel — per-bubble display is Phase 3B. */
  sources?: Source[];
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "system") {
    // System events: a quiet centered pill, no timestamp.
    return (
      <div className="flex justify-center">
        <span className="rounded-full border border-border bg-secondary px-3 py-1 text-xs text-muted-foreground">
          {message.content}
        </span>
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
        {/* whitespace-pre-line keeps the model's paragraph breaks
            without needing a markdown renderer. */}
        <p className="whitespace-pre-line text-[15px] leading-relaxed">
          {message.content}
        </p>
        {/* Citations under the answer (assistant messages only). */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceCards sources={message.sources} />
        )}
      </div>

      {message.timestamp && (
        <span
          className={`px-1 text-xs tabular-nums text-muted-foreground opacity-0 transition-opacity duration-150 group-hover:opacity-100 ${
            isUser ? "text-right" : "text-left"
          }`}
        >
          {message.timestamp}
        </span>
      )}
    </div>
  );
}
