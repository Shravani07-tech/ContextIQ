// Voice input (C12): unsupported browsers, consent before microphone
// access, transcript placed for review (not auto-sent), permission
// denied, empty transcription, cancellation, and read-aloud text.

import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { speakableText } from "@/components/chat/read-aloud-button";
import { VoiceInputButton } from "@/components/chat/voice-input";
import type { SpeechRecognitionLike } from "@/hooks/useSpeechRecognition";

let instances: FakeRecognition[] = [];

class FakeRecognition implements SpeechRecognitionLike {
  lang = "";
  continuous = true;
  interimResults = false;
  maxAlternatives = 0;
  onresult: SpeechRecognitionLike["onresult"] = null;
  onerror: SpeechRecognitionLike["onerror"] = null;
  onend: SpeechRecognitionLike["onend"] = null;
  onspeechend: SpeechRecognitionLike["onspeechend"] = null;
  start = vi.fn();
  stop = vi.fn(() => this.onend?.());
  abort = vi.fn(() => this.onend?.());
  constructor() {
    instances.push(this);
  }
  say(text: string, isFinal = true) {
    this.onresult?.({ resultIndex: 0, results: [{ isFinal, 0: { transcript: text } }] });
  }
  fail(error: string) {
    this.onerror?.({ error });
    this.onend?.();
  }
}

function install() {
  (window as unknown as { webkitSpeechRecognition: unknown }).webkitSpeechRecognition = FakeRecognition;
}

describe("VoiceInputButton", () => {
  beforeEach(() => {
    instances = [];
    localStorage.clear();
  });
  afterEach(() => {
    delete (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition;
  });

  it("renders nothing in browsers without speech recognition (typing remains)", () => {
    const { container } = render(<VoiceInputButton onTranscript={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("asks for consent before opening the microphone, then fills the box", async () => {
    install();
    const onTranscript = vi.fn();
    render(<VoiceInputButton onTranscript={onTranscript} />);

    await userEvent.click(screen.getByRole("button", { name: "Start voice input" }));
    expect(await screen.findByText(/Use voice input\?/)).toBeInTheDocument();
    expect(screen.getByText(/never records or stores audio/)).toBeInTheDocument();
    expect(instances).toHaveLength(0); // microphone not requested yet

    await userEvent.click(screen.getByRole("button", { name: "Enable voice input" }));
    expect(instances).toHaveLength(1);
    expect(instances[0].start).toHaveBeenCalled();
    expect(instances[0].interimResults).toBe(true);
    expect(screen.getByRole("status")).toHaveTextContent(/Listening/);

    act(() => instances[0].say("what was revenue", false));
    expect(screen.getByRole("status")).toHaveTextContent("what was revenue");
    act(() => instances[0].say("what was revenue in 2024"));
    await userEvent.click(screen.getByRole("button", { name: "Stop voice input" }));
    expect(onTranscript).toHaveBeenCalledWith("what was revenue in 2024");
  });

  it("skips the disclosure once consent was given", async () => {
    install();
    localStorage.setItem("contextiq.voice.consent.v1", "granted");
    render(<VoiceInputButton onTranscript={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Start voice input" }));
    expect(screen.queryByText(/Use voice input\?/)).not.toBeInTheDocument();
    expect(instances).toHaveLength(1);
  });

  it("explains a denied microphone permission", async () => {
    install();
    localStorage.setItem("contextiq.voice.consent.v1", "granted");
    const onTranscript = vi.fn();
    render(<VoiceInputButton onTranscript={onTranscript} />);
    await userEvent.click(screen.getByRole("button", { name: "Start voice input" }));
    act(() => instances[0].fail("not-allowed"));
    expect(screen.getByRole("alert")).toHaveTextContent(/Microphone access was denied/);
    expect(onTranscript).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("reports an empty transcription instead of submitting nothing", async () => {
    install();
    localStorage.setItem("contextiq.voice.consent.v1", "granted");
    const onTranscript = vi.fn();
    render(<VoiceInputButton onTranscript={onTranscript} />);
    await userEvent.click(screen.getByRole("button", { name: "Start voice input" }));
    act(() => instances[0].onend?.());
    expect(screen.getByRole("alert")).toHaveTextContent(/No speech was detected/);
    expect(onTranscript).not.toHaveBeenCalled();
  });

  it("cancel discards what was heard", async () => {
    install();
    localStorage.setItem("contextiq.voice.consent.v1", "granted");
    const onTranscript = vi.fn();
    render(<VoiceInputButton onTranscript={onTranscript} />);
    await userEvent.click(screen.getByRole("button", { name: "Start voice input" }));
    act(() => instances[0].say("never mind"));
    await userEvent.click(screen.getByRole("button", { name: "Cancel voice input" }));
    expect(instances[0].abort).toHaveBeenCalled();
    expect(onTranscript).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Start voice input" })).toBeInTheDocument();
  });

  it("start failures surface a recording error", async () => {
    install();
    localStorage.setItem("contextiq.voice.consent.v1", "granted");
    render(<VoiceInputButton onTranscript={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Start voice input" }));
    act(() => instances[0].fail("audio-capture"));
    expect(screen.getByRole("alert")).toHaveTextContent(/No microphone was found/);
  });
});

describe("ChatInput voice integration", () => {
  afterEach(() => {
    delete (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition;
  });

  it("puts the transcript in the input for review and does not auto-send", async () => {
    instances = [];
    install();
    localStorage.setItem("contextiq.voice.consent.v1", "granted");
    vi.doMock("@/lib/api", () => ({ api: { chatStream: vi.fn() } }));
    const { api } = await import("@/lib/api");
    const { ChatInput } = await import("@/components/chat/chat-input");
    const { ChatProvider } = await import("@/hooks/useChat");
    const { createTestQueryClient, withQueryClient } = await import("@/lib/test-utils");
    const Q = withQueryClient(createTestQueryClient());
    render(
      <Q>
        <ChatProvider>
          <ChatInput />
        </ChatProvider>
      </Q>,
    );

    const box = screen.getByRole("textbox", { name: "Chat input" });
    await userEvent.type(box, "Please summarise");
    await userEvent.click(screen.getByRole("button", { name: "Start voice input" }));
    act(() => instances[0].say("the 2024 report"));
    await userEvent.click(screen.getByRole("button", { name: "Stop voice input" }));

    expect(box).toHaveValue("Please summarise the 2024 report");
    expect(api.chatStream).not.toHaveBeenCalled();
    vi.doUnmock("@/lib/api");
  });
});

describe("speakableText", () => {
  it("strips markdown and citation markers before speaking", () => {
    expect(speakableText("## Summary\n**Revenue** grew [S1] per [the report](http://x).\n```js\ncode\n```"))
      .toBe("Summary Revenue grew per the report. (code omitted)");
  });
});
