"use client";

// Workspace tools — the analysis features that work across documents
// rather than inside one conversation. Every tool reads the active
// collection from the sidebar, so the scope a user picked once applies
// everywhere. Labels collapse to icons on narrow screens but keep their
// accessible names.

import { CalendarClock, Network, Scale, ShieldCheck } from "lucide-react";

import { EvidenceDialog } from "@/components/insights/evidence-dialog";
import { GraphDialog } from "@/components/insights/graph-dialog";
import { TimelineDialog } from "@/components/insights/timeline-dialog";
import { CompareDialog } from "@/components/sidebar/compare-dialog";

export function WorkspaceTools() {
  return (
    <nav aria-label="Workspace tools" className="flex items-center gap-1.5">
      <CompareDialog
        trigger={
          <button type="button" className="tool-button" aria-label="Compare documents">
            <Scale className="size-3.5" aria-hidden />
            <span className="hidden lg:inline">Compare</span>
          </button>
        }
      />
      <TimelineDialog
        trigger={
          <button type="button" className="tool-button" aria-label="Timeline">
            <CalendarClock className="size-3.5" aria-hidden />
            <span className="hidden lg:inline">Timeline</span>
          </button>
        }
      />
      <EvidenceDialog
        trigger={
          <button type="button" className="tool-button" aria-label="Check a claim">
            <ShieldCheck className="size-3.5" aria-hidden />
            <span className="hidden lg:inline">Check claim</span>
          </button>
        }
      />
      <GraphDialog
        trigger={
          <button type="button" className="tool-button" aria-label="Knowledge graph">
            <Network className="size-3.5" aria-hidden />
            <span className="hidden lg:inline">Graph</span>
          </button>
        }
      />
    </nav>
  );
}
