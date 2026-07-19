// Typing indicator — shown in an assistant-styled bubble while an
// answer is being generated. The dot animation itself lives in
// globals.css (.typing-dot) since it's a design-system-sanctioned
// loop; this component only provides the bubble and a11y text.

export function TypingIndicator() {
  return (
    <div className="flex items-start">
      <div
        className="flex items-center gap-1.5 rounded-lg border border-border bg-chat-assistant px-5 py-4"
        role="status"
        aria-label="Assistant is thinking"
      >
        <span className="typing-dot" aria-hidden />
        <span className="typing-dot" aria-hidden />
        <span className="typing-dot" aria-hidden />
      </div>
    </div>
  );
}
