"use client";

// Main chat area — live conversation from the shared chat context:
// empty state until the first message, then the message list with
// the typing indicator while POST /chat is in flight. The demo-mode
// URL flag is gone — real data replaced it.

import { ChatInput } from "@/components/chat/chat-input";
import { EmptyState } from "@/components/chat/empty-state";
import { MessageList } from "@/components/chat/message-list";
import { useChat } from "@/hooks/useChat";

export function ChatArea() {
  const { messages, isThinking } = useChat();

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto px-4">
        {messages.length > 0 ? (
          <MessageList messages={messages} showTyping={isThinking} />
        ) : (
          <div className="flex min-h-full items-center justify-center">
            <EmptyState />
          </div>
        )}
      </div>

      <ChatInput />
    </div>
  );
}
