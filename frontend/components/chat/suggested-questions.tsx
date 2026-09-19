"use client";

// Suggested Follow-up Questions component (Phase C2).
// Renders a list of grounded, context-aware follow-up question pills under an
// assistant message. Clicking a pill submits it as the next user query.

import { Sparkles } from "lucide-react";
import { useChat } from "@/hooks/useChat";

export function SuggestedQuestions({
  questions,
}: {
  questions: string[];
}) {
  const { sendMessage, isThinking, isStreaming } = useChat();

  if (!questions || questions.length === 0) return null;

  const isDisabled = isThinking || isStreaming;

  return (
    <div className="mt-3 flex flex-col gap-2 rounded-md border border-border/60 bg-muted/30 p-3">
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Sparkles className="size-3.5 text-primary" aria-hidden />
        <span>Suggested follow-ups</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {questions.map((question, index) => (
          <button
            key={index}
            type="button"
            disabled={isDisabled}
            onClick={() => sendMessage(question)}
            className="flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-normal text-foreground transition-all duration-150 hover:border-primary/50 hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-50 text-left"
          >
            <span>{question}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
