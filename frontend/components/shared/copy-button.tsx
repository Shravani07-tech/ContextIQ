"use client";

// Shared copy-to-clipboard button — used for "copy answer" (message
// bubbles) and "copy source text" (source cards) so the interaction
// (icon swap + brief "Copied" confirmation) is defined once.

import { Check, Copy } from "lucide-react";
import { useState } from "react";

const CONFIRM_MS = 1500;

export function CopyButton({
  text,
  label = "Copy",
  className = "",
}: {
  text: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), CONFIRM_MS);
    } catch {
      // Clipboard API unavailable (e.g. insecure context) — fail
      // quietly rather than throw; there's nothing else to fall
      // back to that wouldn't need its own UI.
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copied ? "Copied" : label}
      className={`flex items-center gap-1.5 rounded-sm text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground ${className}`}
    >
      {copied ? (
        <Check className="size-3.5 text-success" aria-hidden />
      ) : (
        <Copy className="size-3.5" aria-hidden />
      )}
    </button>
  );
}
