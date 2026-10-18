"use client";

// Export Report Button — downloads an answer as a Markdown, PDF, or
// Plain Text report. The report carries everything attached to the
// answer: the question, sources, citation checks, contradictions, the
// evidence assessment and, for deep research, the plan and gaps.

import { Download, FileCode, FileText, FileType, Loader2 } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";

import { useDismissable } from "@/hooks/useDismissable";
import { api } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import type { ChatMessage } from "@/lib/types";

const FORMATS = [
  { id: "markdown", label: "Markdown (.md)", ext: "md", icon: FileCode },
  { id: "pdf", label: "PDF (.pdf)", ext: "pdf", icon: FileText },
  { id: "txt", label: "Plain text (.txt)", ext: "txt", icon: FileType },
] as const;

export function ExportReportButton({
  message,
  question,
}: {
  message: ChatMessage;
  question?: string;
}) {
  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismissable(containerRef, open, close, triggerRef);

  const handleExport = async (format: (typeof FORMATS)[number]) => {
    if (downloadingFormat) return;

    setDownloadingFormat(format.id);
    setOpen(false);
    try {
      const blob = await api.exportResearchReport({
        format: format.id,
        question: question || message.question || "Research Analysis",
        answer: message.content,
        sources: message.sources || [],
        citation_verification: message.citationVerification,
        contradictions: message.contradictions,
        evidence_assessment: message.evidenceAssessment,
        doc_count: new Set((message.sources ?? []).map((s) => s.filename)).size,
        subquestions: message.research?.subquestions,
        unresolved: message.research?.unresolved,
        research_status: message.research?.status ?? null,
        collection_name: message.research?.scope ?? null,
      });
      const filename = `contextiq-research-report.${format.ext}`;
      downloadBlob(blob, filename);
      toast.success(`Exported ${filename}`);
    } catch (err: unknown) {
      toast.error("Export failed", {
        description: err instanceof Error ? err.message : undefined,
      });
    } finally {
      setDownloadingFormat(null);
    }
  };

  return (
    <div ref={containerRef} className="relative inline-block text-left">
      <button
        ref={triggerRef}
        type="button"
        disabled={Boolean(downloadingFormat)}
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-sm px-1.5 py-1 text-xs font-medium text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground disabled:opacity-50"
      >
        {downloadingFormat ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
        ) : (
          <Download className="size-3.5" aria-hidden />
        )}
        {downloadingFormat ? "Exporting…" : "Export"}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Export format"
          className="absolute right-0 z-50 mt-1 w-40 rounded-md border border-border bg-popover p-1 shadow-md"
        >
          {FORMATS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="menuitem"
              onClick={() => handleExport(f)}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-popover-foreground transition-colors duration-150 hover:bg-accent focus-visible:bg-accent"
            >
              <f.icon className="size-3.5 text-muted-foreground" aria-hidden />
              {f.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
