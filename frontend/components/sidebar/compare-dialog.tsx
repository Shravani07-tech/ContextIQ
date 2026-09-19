"use client";

// Document Comparison Dialog Component (Phase C3).
// Allows selecting two or more documents, entering a comparison query,
// and displaying grounded comparative findings with source citations.

import {
  ArrowRightLeft,
  CheckCircle2,
  FileText,
  Loader2,
  Scale,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { SourceCards } from "@/components/chat/source-cards";
import { InlineError } from "@/components/shared/inline-error";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useActiveCollection } from "@/hooks/useCollections";
import { useDetailedDocuments } from "@/hooks/useDocuments";
import { api } from "@/lib/api";
import type { CompareResponse } from "@/lib/types";

const PRESET_QUESTIONS = [
  "Compare the major risks and mitigations identified in these documents.",
  "What key metrics or financial figures changed between the documents?",
  "What recommendations or conclusions differ between these documents?",
  "What information is present in one document but missing from the other?",
];

export function CompareDialog({
  initialSelectedDocs = [],
  trigger,
}: {
  initialSelectedDocs?: string[];
  trigger?: React.ReactElement;
}) {
  const [open, setOpen] = useState(false);
  const [activeCollectionId] = useActiveCollection();
  const { data: docsData, isLoading: isDocsLoading } = useDetailedDocuments(
    activeCollectionId ? { collection_id: activeCollectionId } : undefined
  );

  const [selectedDocs, setSelectedDocs] = useState<string[]>(initialSelectedDocs);
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CompareResponse | null>(null);

  const availableDocs = docsData ?? [];

  const handleToggleDoc = (filename: string) => {
    setSelectedDocs((prev) => {
      if (prev.includes(filename)) {
        return prev.filter((f) => f !== filename);
      }
      if (prev.length >= 5) {
        toast.warning("Comparison limit reached", {
          description: "You can compare up to 5 documents at a time.",
        });
        return prev;
      }
      return [...prev, filename];
    });
  };

  const handleRunComparison = async (customQ?: string) => {
    if (selectedDocs.length < 2) {
      toast.error("Selection required", {
        description: "Please select at least 2 documents to compare.",
      });
      return;
    }

    const q = customQ ?? (question.trim() || PRESET_QUESTIONS[0]);

    setIsLoading(true);
    setError(null);
    try {
      const res = await api.compare({
        filenames: selectedDocs,
        question: q,
        collection_id: activeCollectionId,
      });
      setResult(res);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Failed to compare documents.";
      setError(errMsg);
      toast.error("Comparison failed", { description: errMsg });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          trigger ?? (
            <button
              type="button"
              className="flex items-center gap-1.5 rounded-md border border-border bg-secondary px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent"
            >
              <Scale className="size-3.5 text-primary" />
              <span>Compare Documents</span>
            </button>
          )
        }
      />

      <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col overflow-hidden p-6">
        <DialogHeader className="shrink-0">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Scale className="size-5 text-primary" />
            <span>Document Comparison</span>
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            Select 2 to 5 documents to compare their findings, changes, and evidence side-by-side.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto pr-1 space-y-5 my-2">
          {/* Document Picker Section */}
          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <div className="flex items-center justify-between text-xs font-medium">
              <span>Select Documents ({selectedDocs.length}/5)</span>
              {selectedDocs.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedDocs([])}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Clear selection
                </button>
              )}
            </div>

            {isDocsLoading ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
                <Loader2 className="size-3.5 animate-spin" />
                <span>Loading document library...</span>
              </div>
            ) : availableDocs.length === 0 ? (
              <p className="text-xs text-muted-foreground py-2">
                No indexed documents available in this scope.
              </p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-40 overflow-y-auto pr-1">
                {availableDocs.map((doc) => {
                  const isChecked = selectedDocs.includes(doc.filename);
                  return (
                    <button
                      key={doc.filename}
                      type="button"
                      onClick={() => handleToggleDoc(doc.filename)}
                      className={`flex items-center gap-2.5 rounded-md border p-2 text-left transition-all ${
                        isChecked
                          ? "border-primary bg-primary/5 text-foreground font-medium"
                          : "border-border/60 bg-muted/20 text-muted-foreground hover:border-border hover:bg-accent"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => {}} // handled by parent button click
                        className="size-3.5 rounded border-border text-primary focus:ring-0"
                      />
                      <FileText className="size-3.5 shrink-0 text-muted-foreground" />
                      <span className="truncate text-xs">{doc.filename}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Question & Presets Section */}
          <div className="space-y-3">
            <label className="text-xs font-medium text-foreground">
              Comparison Question
            </label>

            <div className="flex gap-2">
              <Input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g. Compare the major risks and financial projections..."
                className="text-xs"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleRunComparison();
                  }
                }}
              />
              <button
                type="button"
                disabled={selectedDocs.length < 2 || isLoading}
                onClick={() => handleRunComparison()}
                className="flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-xs font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 disabled:opacity-50 shrink-0"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" />
                    <span>Comparing...</span>
                  </>
                ) : (
                  <>
                    <ArrowRightLeft className="size-3.5" />
                    <span>Compare</span>
                  </>
                )}
              </button>
            </div>

            {/* Presets */}
            <div className="flex flex-wrap gap-1.5">
              {PRESET_QUESTIONS.map((pq, idx) => (
                <button
                  key={idx}
                  type="button"
                  disabled={selectedDocs.length < 2 || isLoading}
                  onClick={() => {
                    setQuestion(pq);
                    handleRunComparison(pq);
                  }}
                  className="rounded-full border border-border bg-secondary px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:bg-accent hover:text-foreground disabled:opacity-50"
                >
                  ⚡ {pq.slice(0, 45)}...
                </button>
              ))}
            </div>
          </div>

          {/* Error Notice */}
          {error && (
            <InlineError
              message={error}
              onRetry={() => handleRunComparison()}
            />
          )}

          {/* Result Section */}
          {result && (
            <div className="space-y-4 rounded-lg border border-border bg-card p-5">
              <div className="flex items-center justify-between border-b border-border/60 pb-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="size-4 text-amber-500" />
                  <span className="text-sm font-semibold text-foreground">
                    Comparison Results
                  </span>
                </div>
                <span className="text-xs text-muted-foreground">
                  Compared: {result.filenames.join(" vs ")}
                </span>
              </div>

              {/* Summary */}
              {result.summary && (
                <div className="space-y-1">
                  <h4 className="text-xs font-semibold text-foreground">Summary</h4>
                  <p className="text-xs leading-relaxed text-muted-foreground whitespace-pre-line">
                    {result.summary}
                  </p>
                </div>
              )}

              {/* Similarities */}
              {result.similarities.length > 0 && (
                <div className="space-y-1.5">
                  <h4 className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                    <CheckCircle2 className="size-3.5" />
                    <span>Key Similarities</span>
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-xs text-muted-foreground">
                    {result.similarities.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Differences */}
              {result.differences.length > 0 && (
                <div className="space-y-1.5">
                  <h4 className="flex items-center gap-1.5 text-xs font-semibold text-amber-600 dark:text-amber-400">
                    <ArrowRightLeft className="size-3.5" />
                    <span>Key Differences</span>
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-xs text-muted-foreground">
                    {result.differences.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Doc A Only */}
              {result.document_a_only.length > 0 && (
                <div className="space-y-1.5">
                  <h4 className="text-xs font-semibold text-foreground">
                    Exclusive to {result.filenames[0]}
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-xs text-muted-foreground">
                    {result.document_a_only.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Doc B Only */}
              {result.document_b_only.length > 0 && result.filenames.length > 1 && (
                <div className="space-y-1.5">
                  <h4 className="text-xs font-semibold text-foreground">
                    Exclusive to {result.filenames[1]}
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-xs text-muted-foreground">
                    {result.document_b_only.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Citations */}
              {result.sources.length > 0 && (
                <div className="pt-2">
                  <h4 className="text-xs font-semibold text-foreground mb-2">
                    Evidence Sources
                  </h4>
                  <SourceCards sources={result.sources} />
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
