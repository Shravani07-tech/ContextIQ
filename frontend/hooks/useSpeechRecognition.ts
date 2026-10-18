"use client";

// Voice input (C12) via the browser's built-in Web Speech API.
//
// Why browser-native: it needs no new dependency, no model download and
// no backend change, and ContextIQ never touches audio — the browser
// hands back text only, so there is nothing to record or store.
//
// Privacy caveat, surfaced to the user before first use: some browsers
// (notably Chrome and Edge) transcribe speech on the browser vendor's
// servers. So the microphone is never opened until the user has read
// that disclosure and opted in (remembered per browser), and only when
// they press the mic button. Document contents are never involved.
//
// The recognized text is returned to the caller to place in the input
// box for review — it is never auto-submitted.

import { useCallback, useEffect, useRef, useState } from "react";

export type VoiceStatus = "unsupported" | "idle" | "listening" | "processing" | "error";

const CONSENT_KEY = "contextiq.voice.consent.v1";

// Minimal structural types — the Web Speech API is not in lib.dom for
// every TypeScript target, and only these members are used.
interface RecognitionAlternative {
  transcript: string;
}
interface RecognitionResult {
  isFinal: boolean;
  0: RecognitionAlternative;
}
interface RecognitionEvent {
  resultIndex: number;
  results: ArrayLike<RecognitionResult>;
}
interface RecognitionErrorEvent {
  error: string;
}
export interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  onspeechend?: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}
type RecognitionCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function readVoiceConsent(): boolean {
  try {
    return localStorage.getItem(CONSENT_KEY) === "granted";
  } catch {
    return false;
  }
}

export function writeVoiceConsent(granted: boolean): void {
  try {
    if (granted) localStorage.setItem(CONSENT_KEY, "granted");
    else localStorage.removeItem(CONSENT_KEY);
  } catch {
    // Storage unavailable (private mode): consent is asked again next time.
  }
}

const ERROR_MESSAGES: Record<string, string> = {
  "not-allowed": "Microphone access was denied. Allow it in your browser's site settings to use voice input.",
  "service-not-allowed": "Your browser blocked its speech service for this site.",
  "audio-capture": "No microphone was found.",
  "no-speech": "No speech was detected. Try again and speak after the tone.",
  network: "The browser's speech service could not be reached. Voice input needs it; typing still works.",
  "language-not-supported": "Speech recognition isn't available for your browser language.",
};

export function useSpeechRecognition(onTranscript: (text: string) => void) {
  const [supported, setSupported] = useState(false);
  const [status, setStatus] = useState<VoiceStatus>("unsupported");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const finalRef = useRef("");
  const erroredRef = useRef(false);
  const cancelledRef = useRef(false);
  const onTranscriptRef = useRef(onTranscript);
  onTranscriptRef.current = onTranscript;

  // Detect support after mount (SSR has no window).
  useEffect(() => {
    const ok = getRecognitionCtor() !== null;
    setSupported(ok);
    setStatus(ok ? "idle" : "unsupported");
  }, []);

  // Never leave the microphone open after unmount.
  useEffect(() => () => recRef.current?.abort(), []);

  const start = useCallback(() => {
    const Ctor = getRecognitionCtor();
    if (!Ctor || recRef.current) return;
    const rec = new Ctor();
    rec.lang = (typeof navigator !== "undefined" && navigator.language) || "en-US";
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    finalRef.current = "";
    erroredRef.current = false;
    cancelledRef.current = false;
    setInterim("");
    setError(null);

    rec.onresult = (e) => {
      let interimText = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalRef.current += r[0].transcript;
        else interimText += r[0].transcript;
      }
      setInterim(interimText);
    };
    rec.onspeechend = () => setStatus("processing");
    rec.onerror = (e) => {
      if (e.error === "aborted") return; // user cancelled
      erroredRef.current = true;
      setError(ERROR_MESSAGES[e.error] ?? "Voice input failed. You can keep typing instead.");
      setStatus("error");
    };
    rec.onend = () => {
      recRef.current = null;
      setInterim("");
      if (cancelledRef.current || erroredRef.current) {
        if (cancelledRef.current) setStatus("idle");
        return;
      }
      const text = finalRef.current.trim();
      if (!text) {
        setError(ERROR_MESSAGES["no-speech"]);
        setStatus("error");
        return;
      }
      onTranscriptRef.current(text);
      setStatus("idle");
    };

    recRef.current = rec;
    try {
      rec.start(); // the browser asks for microphone permission here, not before
      setStatus("listening");
    } catch {
      recRef.current = null;
      setError("Voice input could not start. You can keep typing instead.");
      setStatus("error");
    }
  }, []);

  /** Stop listening and keep what was heard. */
  const stop = useCallback(() => {
    if (!recRef.current) return;
    setStatus("processing");
    recRef.current.stop();
  }, []);

  /** Stop listening and discard everything. */
  const cancel = useCallback(() => {
    cancelledRef.current = true;
    recRef.current?.abort();
    recRef.current = null;
    finalRef.current = "";
    setInterim("");
    setStatus(supported ? "idle" : "unsupported");
  }, [supported]);

  const dismissError = useCallback(() => {
    setError(null);
    setStatus(supported ? "idle" : "unsupported");
  }, [supported]);

  return { supported, status, interim, error, start, stop, cancel, dismissError };
}
