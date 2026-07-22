// Shared similarity-score pill — was duplicated identically in
// source-cards.tsx's SourceRow and the right panel's Recent Sources
// list (same classes, same `(score * 100).toFixed(1)}%` formatting).

export function SimilarityBadge({ score }: { score: number }) {
  return (
    <span className="shrink-0 text-[13px] font-bold tabular-nums text-ring">
      {(score * 100).toFixed(1)}%
    </span>
  );
}
