"use client";

// Rich markdown rendering for assistant answers: headings, lists,
// tables, links, code blocks (syntax-highlighted via rehype-highlight
// + a copy button), inline code, and blockquotes — all restyled down
// to fit inside a 15px chat bubble using only design-system tokens
// (no prose plugin, no raw hex). User messages stay plain text
// (they're what the person typed, not model output that benefits
// from formatting) — this is assistant-only.
//
// Applied to partial (still-streaming) content too: react-markdown
// tolerates an unclosed fence/list the same way ChatGPT/Claude's own
// renderers do — it just resolves cleanly once the closing token
// arrives on a later token.

import ReactMarkdown, { type Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { CopyButton } from "@/components/shared/copy-button";

/** Flatten react-markdown/rehype-highlight's nested token spans back
    into the plain source text, for the code block's copy button. */
function extractText(node: React.ReactNode): string {
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (node && typeof node === "object" && "props" in node) {
    const element = node as React.ReactElement<{ children?: React.ReactNode }>;
    return extractText(element.props.children);
  }
  return "";
}

const components: Components = {
  h1: (props) => (
    <h2 className="mt-3 mb-1 text-lg font-semibold" {...props} />
  ),
  h2: (props) => (
    <h3 className="mt-3 mb-1 text-base font-semibold" {...props} />
  ),
  h3: (props) => (
    <h4 className="mt-2 mb-1 text-sm font-semibold" {...props} />
  ),
  p: (props) => <p className="mb-2 leading-relaxed last:mb-0" {...props} />,
  ul: (props) => (
    <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0" {...props} />
  ),
  ol: (props) => (
    <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0" {...props} />
  ),
  li: (props) => <li className="leading-relaxed" {...props} />,
  blockquote: (props) => (
    <blockquote
      className="my-2 border-l-2 border-border pl-3 italic text-muted-foreground"
      {...props}
    />
  ),
  a: ({ href, ...props }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-ring underline underline-offset-2 hover:no-underline"
      {...props}
    />
  ),
  hr: (props) => <hr className="my-3 border-border" {...props} />,
  table: (props) => (
    <div className="my-2 overflow-x-auto rounded-md border border-border">
      <table className="w-full border-collapse text-[13px]" {...props} />
    </div>
  ),
  th: (props) => (
    <th
      className="border-b border-border bg-secondary px-2 py-1.5 text-left font-semibold"
      {...props}
    />
  ),
  td: (props) => (
    <td className="border-b border-border px-2 py-1.5 last:border-b-0" {...props} />
  ),
  code: ({ className, children, ...props }) => {
    // rehype-highlight only adds a `language-*` class to FENCED code
    // blocks — inline `code` spans have none, which is what
    // distinguishes the two (no `inline` prop exists in this
    // react-markdown version's API).
    const isBlock = /language-/.test(className ?? "");
    if (!isBlock) {
      return (
        <code
          className="rounded-sm bg-secondary px-1 py-0.5 font-mono text-[0.85em]"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children, ...props }) => {
    const codeElement = Array.isArray(children) ? children[0] : children;
    const codeClassName =
      (codeElement as React.ReactElement<{ className?: string }> | undefined)
        ?.props?.className ?? "";
    const language = /language-(\w+)/.exec(codeClassName)?.[1] ?? "text";
    const rawText = extractText(
      (codeElement as React.ReactElement<{ children?: React.ReactNode }> | undefined)
        ?.props?.children,
    );

    return (
      <div className="my-2 overflow-hidden rounded-lg border border-border bg-background">
        <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
          <span className="font-mono text-xs text-muted-foreground">
            {language}
          </span>
          <CopyButton text={rawText} label="Copy code" />
        </div>
        <pre className="overflow-x-auto p-3 text-[13px] leading-relaxed" {...props}>
          {children}
        </pre>
      </div>
    );
  },
};

// Common languages only — keeps rehype-highlight's bundle from
// pulling in every language lowlight ships, which this document-QA
// tool has no realistic use for.
const HIGHLIGHT_LANGUAGES = [
  "javascript",
  "typescript",
  "python",
  "json",
  "bash",
  "css",
  "xml",
  "markdown",
  "sql",
  "yaml",
];

export function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="text-[15px] [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { subset: HIGHLIGHT_LANGUAGES }]]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
