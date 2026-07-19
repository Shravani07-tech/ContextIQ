"use client";

// Scrollable message list with auto-scroll. Client component solely
// for the scroll behavior (a ref + effect) — rendering stays pure.
//
// Message spacing (DESIGN.md §4): 10px between consecutive messages
// from the same speaker (reads as one thread), 16px between speaker
// turns, 24px around system pills so events breathe.

import { useEffect, useRef } from "react";

import {
  MessageBubble,
  type ChatMessage,
} from "@/components/chat/message-bubble";
import { TypingIndicator } from "@/components/chat/typing-indicator";

function gapClass(prev: ChatMessage | undefined, current: ChatMessage): string {
  if (!prev) return "";
  if (prev.role === "system" || current.role === "system") return "mt-6";
  return prev.role === current.role ? "mt-2.5" : "mt-4";
}

export function MessageList({
  messages,
  showTyping = false,
}: {
  messages: ChatMessage[];
  showTyping?: boolean;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const didMount = useRef(false);

  // Auto-scroll: keep the newest message in view whenever the list
  // grows or the typing indicator appears. First paint jumps
  // instantly (no long animated scroll through an existing
  // conversation); afterwards new messages glide in smoothly.
  useEffect(() => {
    endRef.current?.scrollIntoView({
      behavior: didMount.current ? "smooth" : "instant",
      block: "end",
    });
    didMount.current = true;
  }, [messages.length, showTyping]);

  return (
    <div className="mx-auto w-full max-w-3xl px-1 py-8">
      {messages.map((message, i) => (
        <div key={message.id} className={gapClass(messages[i - 1], message)}>
          <MessageBubble message={message} />
        </div>
      ))}

      {showTyping && (
        <div className="mt-4">
          <TypingIndicator />
        </div>
      )}

      <div ref={endRef} aria-hidden />
    </div>
  );
}
