"use client";

// Voice input control for the chat box (C12). Hidden entirely when the
// browser has no speech recognition — typing is the always-available
// fallback, so nothing pretends to work. First use shows a disclosure
// and asks for opt-in before the microphone is ever requested.

import { Mic, MicOff, Square, X } from "lucide-react";
import { useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { readVoiceConsent, useSpeechRecognition, writeVoiceConsent } from "@/hooks/useSpeechRecognition";
import { cn } from "@/lib/utils";

export function VoiceInputButton({
  onTranscript,
  disabled = false,
}: {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}) {
  const voice = useSpeechRecognition(onTranscript);
  const [consentOpen, setConsentOpen] = useState(false);

  if (!voice.supported) return null;

  const listening = voice.status === "listening" || voice.status === "processing";

  function handleClick() {
    if (listening) {
      voice.stop();
      return;
    }
    if (!readVoiceConsent()) {
      setConsentOpen(true);
      return;
    }
    voice.start();
  }

  return (
    <>
      <div className="relative flex items-center">
        <button
          type="button"
          onClick={handleClick}
          disabled={disabled && !listening}
          aria-label={listening ? "Stop voice input" : "Start voice input"}
          aria-pressed={listening}
          title={listening ? "Stop and keep what was heard" : "Speak your question (you can edit it before sending)"}
          className={cn(
            "flex size-8 shrink-0 items-center justify-center rounded-sm transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50",
            listening
              ? "bg-error-soft text-error"
              : "text-muted-foreground hover:bg-accent hover:text-foreground",
          )}
        >
          {listening ? <Square className="size-3.5 fill-current" aria-hidden /> : <Mic className="size-4" aria-hidden />}
        </button>
        {listening && (
          <button
            type="button"
            onClick={voice.cancel}
            aria-label="Cancel voice input"
            title="Cancel and discard"
            className="ml-0.5 flex size-6 items-center justify-center rounded-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X className="size-3.5" aria-hidden />
          </button>
        )}
      </div>

      {/* Live status, announced politely; sits above the input row. */}
      {(listening || voice.error) && (
        <div
          role={voice.error ? "alert" : "status"}
          aria-live="polite"
          className={cn(
            "absolute -top-9 left-4 right-4 mx-auto flex max-w-3xl items-center gap-2 rounded-md border px-3 py-1.5 text-xs shadow-sm",
            voice.error ? "border-error/40 bg-error-soft text-error" : "border-border bg-card text-muted-foreground",
          )}
        >
          {voice.error ? (
            <>
              <MicOff className="size-3.5 shrink-0" aria-hidden />
              <span className="flex-1">{voice.error}</span>
              <button type="button" onClick={voice.dismissError} className="underline">
                Dismiss
              </button>
            </>
          ) : (
            <>
              <span className="size-2 shrink-0 animate-pulse rounded-full bg-error" aria-hidden />
              <span className="flex-1 truncate">
                {voice.status === "processing" ? "Processing…" : voice.interim || "Listening… speak now"}
              </span>
            </>
          )}
        </div>
      )}

      <Dialog open={consentOpen} onOpenChange={setConsentOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Use voice input?</DialogTitle>
            <DialogDescription className="space-y-2 text-xs leading-relaxed">
              <span className="block">
                Voice input uses your browser&apos;s built-in speech recognition. In some browsers
                (for example Chrome and Edge) your audio is sent to the browser maker&apos;s speech
                service to be transcribed — that is outside ContextIQ&apos;s local-only processing.
              </span>
              <span className="block">
                ContextIQ never records or stores audio and never sends your documents anywhere.
                The recognized text is placed in the message box so you can review or edit it
                before sending. Your browser will ask for microphone permission.
              </span>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button type="button" onClick={() => setConsentOpen(false)} className="secondary-button">
              Not now
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={() => {
                writeVoiceConsent(true);
                setConsentOpen(false);
                voice.start();
              }}
            >
              Enable voice input
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
