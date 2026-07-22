"use client";

// Scrollable message list with auto-scroll. Client component solely
// for the scroll behavior (a ref + effect) — rendering stays pure.
//
// Message spacing (DESIGN.md §4): 10px between consecutive messages
// from the same speaker (reads as one thread), 16px between speaker
// turns, 24px around system pills so events breathe.

import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";

import { MarkdownContent } from "@/components/chat/markdown-content";
import { MessageBubble } from "@/components/chat/message-bubble";
import { SourceCards } from "@/components/chat/source-cards";
import { TypingIndicator } from "@/components/chat/typing-indicator";
import type { ChatMessage, Source } from "@/lib/types";

function gapClass(prev: ChatMessage | undefined, current: ChatMessage): string {
  if (!prev) return "";
  if (prev.role === "system" || current.role === "system") return "mt-6";
  return prev.role === current.role ? "mt-2.5" : "mt-4";
}

export function MessageList({
  messages,
  showTyping = false,
  streamingContent = "",
  streamingSources = [],
}: {
  messages: ChatMessage[];
  showTyping?: boolean;
  /** In-flight answer text, rendered live below the transcript while
      a new answer streams in — not yet a permanent ChatMessage. */
  streamingContent?: string;
  streamingSources?: Source[];
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const didMount = useRef(false);
  const reduceMotion = useReducedMotion();

  // Auto-scroll: keep the newest content in view whenever the list
  // grows, the typing indicator appears, or streamed text grows.
  // First paint jumps instantly (no long animated scroll through an
  // existing conversation); afterwards new content glides in
  // smoothly.
  useEffect(() => {
    endRef.current?.scrollIntoView({
      behavior: didMount.current ? "smooth" : "instant",
      block: "end",
    });
    didMount.current = true;
  }, [messages.length, showTyping, streamingContent]);

  // Regenerate is only offered on the latest FINALIZED assistant
  // answer, and only when nothing new is currently being generated
  // (a stale regenerate button on the previous answer while a fresh
  // one streams in would be confusing).
  let lastAssistantIndex = -1;
  if (!showTyping && !streamingContent) {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") {
        lastAssistantIndex = i;
        break;
      }
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-1 py-8">
      {/* role="log" covers ONLY the finalized transcript. The typing
          indicator and live streaming bubble (below) are kept as
          siblings, outside this region — nesting a live region
          inside another risks some screen-reader/browser
          combinations dropping the inner announcement entirely, and
          announcing every incoming token would be noise anyway; only
          the FINISHED message gets announced, once. */}
      <div
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Conversation"
      >
        {messages.map((message, i) => (
          <motion.div
            key={message.id}
            initial={reduceMotion ? false : { opacity: 0, y: 4 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className={gapClass(messages[i - 1], message)}
          >
            <MessageBubble
              message={message}
              isLastAssistant={i === lastAssistantIndex}
            />
          </motion.div>
        ))}
      </div>

      {showTyping && (
        <div className="mt-4">
          <TypingIndicator />
        </div>
      )}

      {streamingContent && (
        <div className="mt-4 w-full rounded-lg border border-border bg-chat-assistant px-5 py-4">
          <MarkdownContent content={streamingContent} />
          <span className="streaming-cursor" aria-hidden />
          {streamingSources.length > 0 && (
            <SourceCards sources={streamingSources} />
          )}
        </div>
      )}

      <div ref={endRef} aria-hidden />
    </div>
  );
}
