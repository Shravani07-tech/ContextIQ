"use client";

// Empty chat state — the premium welcome experience (DESIGN.md §3
// display step). Shown until the first message exists. Quick-action
// cards now send a real starter question through the chat context.

import { motion, useReducedMotion } from "framer-motion";
import {
  FileSearch,
  FileText,
  GitCompareArrows,
  Lightbulb,
} from "lucide-react";

import { useChat } from "@/hooks/useChat";

const QUICK_ACTIONS = [
  {
    icon: FileText,
    title: "Summarize Documents",
    description: "Get the key points of any indexed file",
    prompt: "Summarize the key points of my documents.",
  },
  {
    icon: FileSearch,
    title: "Search Knowledge",
    description: "Find passages across your whole library",
    prompt: "What topics do my documents cover?",
  },
  {
    icon: GitCompareArrows,
    title: "Compare Documents",
    description: "Spot differences between two sources",
    prompt: "Compare the main themes across my documents.",
  },
  {
    icon: Lightbulb,
    title: "Explain a Topic",
    description: "Understand a concept from your files",
    prompt: "Explain the most important concept in my documents.",
  },
] as const;

export function EmptyState() {
  const { sendMessage } = useChat();
  const reduceMotion = useReducedMotion();

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col items-center gap-3 py-12 text-center">
      {/* Brand mark echoes the sidebar lockup at hero scale. */}
      <div className="flex size-12 items-center justify-center rounded-lg bg-primary text-xl font-extrabold text-primary-foreground">
        C
      </div>

      <h1 className="mt-2 text-4xl font-extrabold tracking-[-0.02em]">
        ContextIQ
      </h1>
      <p className="text-[15px] text-muted-foreground">
        Private AI-Powered Document Intelligence
      </p>
      <p className="max-w-md text-[13px] leading-relaxed text-muted-foreground/70">
        Ask questions about your own documents and get grounded answers
        with sources — everything stays on your machine.
      </p>

      {/* Quick actions — 2×2 on small screens and up, stacked on phones. */}
      <div className="mt-6 grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
        {QUICK_ACTIONS.map(({ icon: Icon, title, description, prompt }, index) => (
          <motion.button
            key={title}
            type="button"
            onClick={() => sendMessage(prompt)}
            initial={reduceMotion ? false : { opacity: 0, y: 4 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
            transition={{ duration: 0.18, ease: "easeOut", delay: index * 0.05 }}
            className="flex items-start gap-3 rounded-lg border border-border bg-card p-4 text-left transition-colors duration-150 hover:border-ring/50 hover:bg-accent"
          >
            <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-secondary">
              <Icon className="size-4 text-ring" aria-hidden />
            </div>
            <div className="min-w-0">
              <p className="text-[13px] font-semibold">{title}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                {description}
              </p>
            </div>
          </motion.button>
        ))}
      </div>
    </div>
  );
}
