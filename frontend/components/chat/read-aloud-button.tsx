"use client";

// Read-aloud for assistant answers (C12) using the browser's
// speechSynthesis. Hidden when unsupported. Markdown syntax and
// citation markers are stripped so they aren't read out literally.
// Only one answer speaks at a time; pressing again stops it.

import { Volume2, VolumeX } from "lucide-react";
import { useEffect, useState } from "react";

export function speakableText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, " (code omitted) ")
    .replace(/\[S\d+\]/g, "")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[#>*_`~|]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function ReadAloudButton({ text }: { text: string }) {
  const [supported, setSupported] = useState(false);
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    setSupported(typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window);
  }, []);

  useEffect(
    () => () => {
      if (speaking) window.speechSynthesis.cancel();
    },
    [speaking],
  );

  if (!supported) return null;

  function toggle() {
    const synth = window.speechSynthesis;
    if (speaking) {
      synth.cancel();
      setSpeaking(false);
      return;
    }
    synth.cancel(); // stop any other answer that is speaking
    const utterance = new SpeechSynthesisUtterance(speakableText(text));
    utterance.lang = navigator.language || "en-US";
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    synth.speak(utterance);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={speaking ? "Stop reading aloud" : "Read answer aloud"}
      aria-pressed={speaking}
      title={speaking ? "Stop" : "Read aloud (browser speech synthesis)"}
      className="flex items-center justify-center rounded-sm p-1 text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground"
    >
      {speaking ? <VolumeX className="size-3.5" aria-hidden /> : <Volume2 className="size-3.5" aria-hidden />}
    </button>
  );
}
