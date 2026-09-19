"use client";

// Export Report Button — allows downloading research results in Markdown, PDF, or Plain Text.

import { Download, FileText, Loader2, FileCode, FileType } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

export function ExportReportButton({
  message,
  question,
}: {
  message: ChatMessage;
  question?: string;
}) {
  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const handleExport = async (format: "markdown" | "pdf" | "txt") => {
    if (downloadingFormat) return;

    setDownloadingFormat(format);
    try {
      const blob = await api.exportResearchReport({
        format,
        question: question || "Research Analysis",
        answer: message.content,
        sources: message.sources || [],
        citation_verification: message.citationVerification,
        contradictions: message.contradictions,
      });

      const ext = format === "markdown" ? "md" : format;
      const filename = `contextiq-research-report.${ext}`;

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.success(`Exported research report as ${format.toUpperCase()}`);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Failed to export report";
      toast.error(errorMsg);
    } finally {
      setDownloadingFormat(null);
      setOpen(false);
    }
  };

  return (
    <div className="relative inline-block text-left">
      <button
        type="button"
        disabled={Boolean(downloadingFormat)}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded border border-border bg-secondary px-2 py-1 text-xs font-medium text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground disabled:opacity-50"
      >
        {downloadingFormat ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
        ) : (
          <Download className="size-3.5" aria-hidden />
        )}
        Export Report
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-1 w-36 rounded-md border border-border bg-popover p-1 shadow-md">
          <button
            type="button"
            onClick={() => handleExport("markdown")}
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-popover-foreground transition-colors duration-150 hover:bg-accent"
          >
            <FileCode className="size-3.5 text-blue-500" />
            Markdown (.md)
          </button>
          <button
            type="button"
            onClick={() => handleExport("pdf")}
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-popover-foreground transition-colors duration-150 hover:bg-accent"
          >
            <FileText className="size-3.5 text-red-500" />
            PDF (.pdf)
          </button>
          <button
            type="button"
            onClick={() => handleExport("txt")}
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-popover-foreground transition-colors duration-150 hover:bg-accent"
          >
            <FileType className="size-3.5 text-slate-500" />
            Plain Text (.txt)
          </button>
        </div>
      )}
    </div>
  );
}
