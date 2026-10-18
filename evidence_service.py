# evidence_service.py
#
# Transparent evidence assessment (C8).
#
# Combines signals that already exist -- the model-assisted citation
# check (C4), detected contradictions (C5), and the retrieved passages
# themselves -- into a categorical rating per claim, with the reasons
# spelled out. It is deliberately rule-based and deterministic: no extra
# LLM call, identical inputs give identical ratings, and every rule is
# listed below so a user can see why a rating was assigned.
#
# RATINGS (best to worst support):
#   STRONG        Model check says SUPPORTED, at least two INDEPENDENT
#                 sources contain relevant passages, no related conflict.
#   MODERATE      Model check says SUPPORTED with one independent source,
#                 or STRONG downgraded by a low-severity potential conflict.
#   LIMITED       Partially supported; or only keyword overlap was found
#                 (model check unavailable); or the model said SUPPORTED
#                 but no matching passage could be located.
#   CONTESTED     A detected contradiction concerns this claim. Overrides
#                 any support rating -- conflicting evidence is surfaced,
#                 never averaged away.
#   UNSUPPORTED   The model check found the evidence does not support it.
#   INSUFFICIENT  The model check could not decide, or no relevant
#                 passage was retrieved at all.
#
# A rating can only be *lowered* by missing or conflicting evidence;
# nothing here can upgrade a claim beyond what the citation check found.
#
# INDEPENDENCE: passages from the same document count once. Passages from
# different documents whose text is a near-duplicate (5-word shingle
# Jaccard >= 0.6) are treated as copies of one underlying source, so a
# report pasted into three files is not three corroborations.
#
# These are heuristic assessments of the retrieved evidence, not
# calibrated probabilities and not proof. The API returns that
# disclaimer with every assessment.

from __future__ import annotations

import re
from typing import Any

from source_refs import make_source_ref

DISCLAIMER = (
    "Evidence ratings are rule-based assessments of the retrieved passages, "
    "combining a model-assisted citation check with keyword overlap and "
    "detected contradictions. They are not calibrated probabilities and do "
    "not prove a claim true or false."
)

RATINGS = ["STRONG", "MODERATE", "LIMITED", "CONTESTED", "UNSUPPORTED", "INSUFFICIENT"]

_STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "that", "this", "with", "from",
    "has", "have", "had", "its", "their", "which", "into", "than", "then",
    "also", "been", "being", "but", "not", "all", "any", "can", "will", "would",
    "should", "could", "may", "might", "our", "his", "her", "they", "them",
    "there", "these", "those", "such", "per", "via", "about", "over", "under",
    "more", "most", "less", "between", "after", "before", "during", "each",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_MAX_PASSAGES_PER_CLAIM = 4
_DUPLICATE_JACCARD = 0.6


def content_tokens(text: str) -> set[str]:
    """Meaningful lowercase tokens: words of 3+ letters minus stopwords,
    plus every number (figures matter most for factual claims)."""
    tokens = set()
    for tok in _TOKEN_RE.findall((text or "").lower()):
        if tok[0].isdigit() or (len(tok) >= 3 and tok not in _STOPWORDS):
            tokens.add(tok)
    return tokens


def _shingles(text: str, n: int = 5) -> set[str]:
    words = _TOKEN_RE.findall((text or "").lower())
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def relevance_level(overlap: float) -> str:
    if overlap >= 0.6:
        return "HIGH"
    if overlap >= 0.35:
        return "MEDIUM"
    if overlap > 0:
        return "LOW"
    return "NONE"


def source_groups(chunks: list[dict]) -> dict[str, str]:
    """
    Map chunk_id -> independent-source group id.

    Same document => same group. Different documents with near-duplicate
    passage text are merged (union-find), so copies of one underlying
    source are never counted as independent corroboration.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    docs = sorted({c.get("filename") or "" for c in chunks})
    for d in docs:
        parent[d] = d

    shingles = [(c.get("filename") or "", _shingles(c.get("chunk_text", ""))) for c in chunks]
    for i in range(len(shingles)):
        for j in range(i + 1, len(shingles)):
            (da, sa), (db, sb) = shingles[i], shingles[j]
            if da != db and _jaccard(sa, sb) >= _DUPLICATE_JACCARD:
                union(da, db)

    return {c["chunk_id"]: find(c.get("filename") or "") for c in chunks if c.get("chunk_id")}


def _related_contradictions(claim: str, contradictions: list[dict]) -> list[dict]:
    claim_tokens = content_tokens(claim)
    if not claim_tokens:
        return []
    related = []
    for c in contradictions or []:
        best = 0.0
        for side in (c.get("claim_a", ""), c.get("claim_b", ""), c.get("topic", "")):
            side_tokens = content_tokens(side)
            if side_tokens:
                best = max(best, len(claim_tokens & side_tokens) / len(claim_tokens))
        if best >= 0.5:
            related.append(c)
    return related


class EvidenceService:
    """Deterministic evidence assessment over already-retrieved evidence."""

    def assess_claim(
        self,
        claim: str,
        chunks: list[dict],
        verification: dict | None = None,
        contradictions: list[dict] | None = None,
        groups: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        groups = groups if groups is not None else source_groups(chunks)
        claim_tokens = content_tokens(claim)
        cited = set((verification or {}).get("citation_ids") or [])

        # 1. Locate relevant passages (cited by the check, or overlapping).
        scored: list[tuple[float, bool, dict]] = []
        for c in chunks:
            passage_tokens = content_tokens(c.get("chunk_text", ""))
            overlap = (
                len(claim_tokens & passage_tokens) / len(claim_tokens) if claim_tokens else 0.0
            )
            is_cited = c.get("chunk_id") in cited
            if is_cited or overlap >= 0.35:
                scored.append((overlap, is_cited, c))
        scored.sort(key=lambda s: (-int(s[1]), -s[0]))

        best_overlap = max((s[0] for s in scored), default=0.0)
        relevant_groups = {groups.get(c["chunk_id"], c.get("filename")) for _, _, c in scored}
        relevant_docs = {c.get("filename") for _, _, c in scored}
        independent = len(relevant_groups)
        duplicates_collapsed = max(0, len(relevant_docs) - independent)

        status = (verification or {}).get("status")
        related = _related_contradictions(claim, contradictions or [])
        serious = [
            c for c in related
            if c.get("status") == "CONTRADICTION" or c.get("severity") in ("HIGH", "MEDIUM")
        ]

        reasons: list[str] = []

        # 2. Directness, from the model-assisted citation check.
        if status == "SUPPORTED":
            directness = "DIRECT"
            reasons.append("The citation check found the passages directly support the claim.")
        elif status == "PARTIALLY_SUPPORTED":
            directness = "PARTIAL"
            reasons.append("The citation check found only part of the claim supported.")
        elif status == "UNSUPPORTED":
            directness = "NONE"
            reasons.append("The citation check found the passages do not support the claim.")
        elif status == "UNVERIFIABLE":
            directness = "UNKNOWN"
            reasons.append("The citation check could not decide from the retrieved passages.")
        else:
            directness = "NOT_ASSESSED"
            reasons.append(
                "No model-assisted citation check was available; only keyword overlap "
                "with the passages was measured."
            )

        # 3. Corroboration.
        if independent == 0:
            reasons.append("No retrieved passage contains the claim's key terms.")
        else:
            reasons.append(
                f"Relevant passages come from {independent} independent source"
                f"{'' if independent == 1 else 's'}."
            )
        if duplicates_collapsed:
            reasons.append(
                f"{duplicates_collapsed} document(s) contain near-identical text and were "
                "counted as one source, not as separate corroboration."
            )

        # 4. Rating rules (see module header). Order matters: conflict and
        # missing evidence take precedence over support.
        if serious:
            rating = "CONTESTED"
            reasons.append(
                f"{len(serious)} detected contradiction(s) concern this claim; "
                "review the conflicting sources before relying on it."
            )
        elif status == "UNSUPPORTED":
            rating = "UNSUPPORTED"
        elif status == "SUPPORTED" and independent == 0:
            rating = "LIMITED"
            reasons.append(
                "The citation check said supported, but no matching passage could be "
                "located, so the verdict is not confirmed."
            )
        elif status == "UNVERIFIABLE" or independent == 0:
            rating = "INSUFFICIENT"
        elif status == "SUPPORTED":
            rating = "STRONG" if independent >= 2 else "MODERATE"
            if related and rating == "STRONG":
                rating = "MODERATE"
                reasons.append("A low-severity potential conflict was noted, so the rating was lowered.")
        else:
            # PARTIALLY_SUPPORTED, or keyword overlap only (no model check).
            rating = "LIMITED"

        if related and not serious and rating not in ("STRONG", "MODERATE"):
            reasons.append("A low-severity potential conflict was also noted.")

        passages = []
        for overlap, is_cited, c in scored[:_MAX_PASSAGES_PER_CLAIM]:
            ref = make_source_ref(c)
            ref.update(
                {
                    "relevance": relevance_level(overlap),
                    "cited_by_check": is_cited,
                    "source_group": groups.get(c["chunk_id"], c.get("filename")),
                }
            )
            passages.append(ref)

        return {
            "claim": claim,
            "rating": rating,
            "basis": "model-assisted" if status else "heuristic",
            "factors": {
                "relevance": relevance_level(best_overlap),
                "directness": directness,
                "independent_sources": independent,
                "duplicates_collapsed": duplicates_collapsed,
                "contradiction": "CONFLICT" if serious else ("POTENTIAL" if related else "NONE"),
            },
            "explanation": reasons,
            "passages": passages,
            "contradictions": [
                {k: c.get(k) for k in ("topic", "status", "severity", "source_a", "source_b")}
                for c in related
            ],
        }

    def assess_answer(
        self,
        verifications: list[dict] | None,
        chunks: list[dict],
        contradictions: list[dict] | None = None,
    ) -> dict[str, Any] | None:
        """Assess every verified claim of an answer. None when there are no
        claims to assess (e.g. the citation check was unavailable)."""
        if not verifications or not chunks:
            return None
        groups = source_groups(chunks)
        claims = [
            self.assess_claim(v.get("claim", ""), chunks, v, contradictions, groups)
            for v in verifications
            if v.get("claim")
        ]
        if not claims:
            return None
        return self._summary(claims, chunks, groups)

    def _summary(self, claims: list[dict], chunks: list[dict], groups: dict[str, str]) -> dict:
        counts = {r: 0 for r in RATINGS}
        for c in claims:
            counts[c["rating"]] += 1
        well = counts["STRONG"] + counts["MODERATE"]
        weak = counts["UNSUPPORTED"] + counts["INSUFFICIENT"] + counts["CONTESTED"]
        if counts["CONTESTED"]:
            overall = "Some claims are contested by conflicting sources."
        elif weak == 0 and well == len(claims):
            overall = "All assessed claims are supported by the retrieved passages."
        elif well >= len(claims) / 2:
            overall = "Most assessed claims are supported; some have limited or missing evidence."
        else:
            overall = "Many claims have limited, missing, or unsupported evidence."
        return {
            "claims": claims,
            "counts": counts,
            "overall": overall,
            "documents_considered": len({c.get("filename") for c in chunks}),
            "independent_sources": len(set(groups.values())),
            "disclaimer": DISCLAIMER,
        }

    def coverage_by_document(self, filenames: list[str], chunks: list[dict]) -> list[dict]:
        """Per-document evidence coverage for comparisons: how many passages
        were retrieved for each document, so a thin side is visible."""
        out = []
        for name in filenames:
            doc_chunks = [c for c in chunks if c.get("filename") == name]
            sims = [c.get("similarity") for c in doc_chunks if isinstance(c.get("similarity"), (int, float))]
            best = max(sims) if sims else None
            if not doc_chunks:
                note = "No passages were retrieved; findings for this document are unsupported."
            elif best is not None and best < 0.45:
                note = "Only weakly related passages were retrieved."
            else:
                note = None
            out.append(
                {
                    "filename": name,
                    "passages": len(doc_chunks),
                    "best_similarity": round(best, 2) if best is not None else None,
                    "note": note,
                }
            )
        return out


def check_claim(
    claim: str,
    retriever,
    collection_id: str | None = None,
    filenames: list[str] | None = None,
    check_contradictions: bool = True,
    verifier=None,
    detector=None,
    top_k: int = 6,
) -> dict[str, Any]:
    """
    Check one user-supplied statement against the documents in scope:
    scoped retrieval -> model-assisted citation check -> contradiction
    scan -> deterministic rating. Model failures degrade to a heuristic
    rating with a warning instead of an error.
    """
    from scope import resolve_scope

    scope = resolve_scope(collection_id=collection_id, filenames=filenames)
    hits = retriever.retrieve(claim, top_k=top_k, filenames=scope.retrieval_filenames)
    chunks = scope.filter_chunks(hits)
    warnings: list[str] = []
    verification = None
    contradictions: list[dict] = []

    if not chunks:
        warnings.append("No passages in the selected scope relate to this statement.")
    else:
        if verifier is None:
            from citation_verification_service import CitationVerificationService

            verifier = CitationVerificationService()
        results = verifier.verify_citations(claim, chunks)
        if results:
            # The check may split the statement into sub-claims; the weakest
            # verdict governs, so a partly false statement is never rated
            # as fully supported.
            order = ["UNSUPPORTED", "UNVERIFIABLE", "PARTIALLY_SUPPORTED", "SUPPORTED"]
            results.sort(key=lambda r: order.index(r["status"]) if r.get("status") in order else 1)
            weakest = results[0]
            cited = sorted({cid for r in results for cid in r.get("citation_ids", [])})
            verification = {"status": weakest["status"], "citation_ids": cited}
            if len(results) > 1:
                warnings.append(
                    f"The statement was checked as {len(results)} separate claims; "
                    "the weakest verdict is shown."
                )
        else:
            warnings.append(
                "The local model did not return a citation check (it may be unavailable), "
                "so this rating uses keyword overlap only."
            )
        if check_contradictions:
            if detector is None:
                from contradiction_detection_service import ContradictionDetectionService

                detector = ContradictionDetectionService()
            contradictions = detector.detect_contradictions(claim, chunks) or []

    assessment = EvidenceService().assess_claim(claim, chunks, verification, contradictions)
    return {
        "claim": claim,
        "scope": scope.describe(),
        "assessment": assessment,
        "disclaimer": DISCLAIMER,
        "model_checked": verification is not None,
        "warnings": warnings,
    }
