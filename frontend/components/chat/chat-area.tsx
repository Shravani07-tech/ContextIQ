"use client";

// Main chat area — live conversation from the shared chat context:
// empty state until the first message, then the toolbar + message
// list (with the typing indicator / live streaming bubble while an
// answer is generating) and a floating scroll-to-bottom button when
// the user has scrolled up away from the latest content.

import { ArrowDown } from "lucide-react";
import { useRef, useState } from "react";

import { ChatInput } from "@/components/chat/chat-input";
import { ChatToolbar } from "@/components/chat/chat-toolbar";
import { EmptyState } from "@/components/chat/empty-state";
import { MessageList } from "@/components/chat/message-list";
import { useChat } from "@/hooks/useChat";

// How far from the bottom (px) before the scroll-to-bottom button
// appears — small enough that it doesn't flicker in in normal use.
const SCROLL_BUTTON_THRESHOLD = 120;

export function ChatArea() {
  const { messages, isThinking, isStreaming, streamingContent, streamingSources } =
    useChat();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);

  function handleScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowScrollButton(distanceFromBottom > SCROLL_BUTTON_THRESHOLD);
  }

  function scrollToBottom() {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }

  const hasConversation = messages.length > 0;

  return (
    <div className="relative flex min-w-0 flex-1 flex-col">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4"
      >
        {hasConversation ? (
          <>
            {/* EmptyState renders its own visible <h1> for the
                welcome screen; once it's gone, the page would have
                NO heading at all for screen-reader landmark
                navigation. This keeps exactly one <h1> present at
                all times without changing anything visible. */}
            <h1 className="sr-only">ContextIQ conversation</h1>
            <ChatToolbar />
            <MessageList
              messages={messages}
              showTyping={isThinking}
              streamingContent={isStreaming ? streamingContent : ""}
              streamingSources={streamingSources}
            />
          </>
        ) : (
          <div className="flex min-h-full items-center justify-center">
            <EmptyState />
          </div>
        )}
      </div>

      {/* Positioned relative to this component's own (non-scrolling)
          wrapper, not the scrollable div above — an absolutely
          positioned child of a scrolling container would scroll away
          with the content instead of staying put. */}
      {showScrollButton && (
        <button
          type="button"
          onClick={scrollToBottom}
          aria-label="Scroll to latest message"
          className="absolute bottom-24 right-6 flex size-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-lg transition-colors duration-150 hover:bg-accent hover:text-foreground"
        >
          <ArrowDown className="size-4" aria-hidden />
        </button>
      )}

      <ChatInput />
    </div>
  );
}
