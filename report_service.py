# report_service.py
#
# Dedicated service for generating exportable Research Reports (Phase C6).
#
# Converts Research Mode & Chat outputs into professional, self-contained
# research reports in Markdown, PDF, and Plain Text formats.
#
# Preserves source attribution, citation verification states, contradiction detection
# findings, and collection/document scope metadata deterministically without
# unnecessary LLM calls or cloud dependencies.

import io
import re
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class ResearchReportService:
    """Service for compiling and formatting exportable research reports."""

    def generate_markdown(self, payload: dict[str, Any]) -> str:
        """
        Generate a professional Markdown research report from a research payload.
        """
        question = payload.get("question", "Research Query").strip()
        answer = payload.get("answer", "No answer content generated.").strip()
        sources = payload.get("sources", [])
        doc_count = payload.get("doc_count", len({s.get("filename") for s in sources if s.get("filename")}))
        verifications = payload.get("citation_verification", [])
        contradictions = payload.get("contradictions", [])
        collection_name = payload.get("collection_name") or "All Documents"
        document_filter = payload.get("document_filter")
        timestamp = payload.get("generated_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        scope_str = f"Collection: {collection_name}"
        if document_filter:
            scope_str += f" | Filter: {document_filter}"

        md_lines = []
        md_lines.append("# ContextIQ Research Report")
        md_lines.append("")
        md_lines.append(f"**Generated:** {timestamp}  ")
        md_lines.append(f"**Research Scope:** {scope_str}  ")
        md_lines.append(f"**Documents Analyzed:** {doc_count}  ")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
        md_lines.append("## Research Question")
        md_lines.append(f"> {question}")
        md_lines.append("")
        md_lines.append("## Executive Summary & Findings")
        md_lines.append(answer)
        md_lines.append("")

        # Contradictions Section if present
        if contradictions:
            md_lines.append("## ⚠️ Contradictions Detected")
            md_lines.append("The following conflicting assertions were identified across the retrieved evidence:")
            md_lines.append("")
            for idx, c in enumerate(contradictions, 1):
                status_badge = f"**[{c.get('status', 'CONTRADICTION')}]**"
                md_lines.append(f"### {idx}. {c.get('topic', 'Conflicting Claims')} {status_badge}")
                md_lines.append(f"- **{c.get('source_a', 'Source A')}**: \"{c.get('claim_a', '')}\"")
                md_lines.append(f"- **{c.get('source_b', 'Source B')}**: \"{c.get('claim_b', '')}\"")
                md_lines.append(f"- **Severity:** {c.get('severity', 'MEDIUM')}")
                md_lines.append(f"- **Analysis:** {c.get('reason', '')}")
                md_lines.append("")

        # Citation Verification Section if present
        if verifications:
            md_lines.append("## Citation Verification Analysis")
            md_lines.append("Evaluation of whether generated claims are supported by source passages:")
            md_lines.append("")
            for v in verifications:
                status_icon = "✓" if v.get("status") == "SUPPORTED" else ("⚠" if "PARTIAL" in v.get("status", "") else "✕")
                md_lines.append(f"- {status_icon} **{v.get('status')}**: \"{v.get('claim')}\"")
                if v.get("reason"):
                    md_lines.append(f"  - *Reason:* {v.get('reason')}")
                if v.get("citation_ids"):
                    md_lines.append(f"  - *Citations:* {', '.join(v.get('citation_ids'))}")
            md_lines.append("")

        # Sources & Evidence Section
        md_lines.append("## Sources & Evidence")
        if sources:
            for idx, s in enumerate(sources, 1):
                fname = s.get("filename", "Unknown Document")
                cid = s.get("chunk_id", "")
                page = f" (Page {s['page']})" if s.get("page") else ""
                section = f" [Section: {s['section']}]" if s.get("section") else ""
                sim = f" similarity={s['similarity']:.4f}" if isinstance(s.get("similarity"), (int, float)) else ""

                md_lines.append(f"### [{idx}] {fname}{page}{section}")
                md_lines.append(f"- **Chunk ID:** `{cid}`{sim}")
                if s.get("preview"):
                    md_lines.append(f"- **Excerpt:** *\"{s.get('preview').strip()}\"*")
                md_lines.append("")
        else:
            md_lines.append("No specific source chunks cited.")
            md_lines.append("")

        md_lines.append("---")
        md_lines.append("*Report generated locally by ContextIQ — Private AI-Powered Document Intelligence.*")

        return "\n".join(md_lines)

    def generate_txt(self, payload: dict[str, Any]) -> str:
        """
        Generate a clean plain text report.
        """
        md = self.generate_markdown(payload)
        # Strip markdown headers, bold/italics, and backticks for clean plain text
        txt = re.sub(r"^#+\s*", "", md, flags=re.MULTILINE)
        txt = re.sub(r"\*\*|\*|`", "", txt)
        return txt

    def generate_pdf(self, payload: dict[str, Any]) -> bytes:
        """
        Generate a professional PDF research report using ReportLab.
        Returns raw PDF bytes.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()
        normal = styles["Normal"]

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=6,
        )

        h2_style = ParagraphStyle(
            "ReportH2",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=12,
            spaceAfter=6,
        )

        meta_style = ParagraphStyle(
            "ReportMeta",
            parent=normal,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=12,
        )

        body_style = ParagraphStyle(
            "ReportBody",
            parent=normal,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#334155"),
            spaceAfter=8,
        )

        quote_style = ParagraphStyle(
            "ReportQuote",
            parent=normal,
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#0f172a"),
            backColor=colors.HexColor("#f1f5f9"),
            borderColor=colors.HexColor("#cbd5e1"),
            borderWidth=1,
            borderPadding=8,
            spaceAfter=10,
        )

        story = []

        question = payload.get("question", "Research Query").strip()
        answer = payload.get("answer", "No answer generated.").strip()
        sources = payload.get("sources", [])
        doc_count = payload.get("doc_count", len({s.get("filename") for s in sources if s.get("filename")}))
        verifications = payload.get("citation_verification", [])
        contradictions = payload.get("contradictions", [])
        collection_name = payload.get("collection_name") or "All Documents"
        document_filter = payload.get("document_filter")
        timestamp = payload.get("generated_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        scope_str = f"Collection: {collection_name}"
        if document_filter:
            scope_str += f" | Filter: {document_filter}"

        story.append(Paragraph("ContextIQ Research Report", title_style))
        story.append(
            Paragraph(
                f"<b>Generated:</b> {timestamp} &nbsp;|&nbsp; <b>Scope:</b> {scope_str} &nbsp;|&nbsp; <b>Documents:</b> {doc_count}",
                meta_style,
            )
        )
        story.append(Spacer(1, 4))

        story.append(Paragraph("Research Question", h2_style))
        story.append(Paragraph(f"<b>Q:</b> {self._escape_html(question)}", quote_style))

        story.append(Paragraph("Executive Summary & Findings", h2_style))
        # Format answer paragraphs cleanly
        answer_paragraphs = answer.split("\n\n")
        for p in answer_paragraphs:
            if p.strip():
                story.append(Paragraph(self._escape_html(p.strip()).replace("\n", "<br/>"), body_style))

        # Contradictions
        if contradictions:
            story.append(Spacer(1, 6))
            story.append(Paragraph("⚠️ Contradictions Detected", h2_style))
            for idx, c in enumerate(contradictions, 1):
                c_text = (
                    f"<b>{idx}. {self._escape_html(c.get('topic', 'Conflict'))}</b> "
                    f"<font color='#dc2626'>[{c.get('status', 'CONTRADICTION')}]</font><br/>"
                    f"• <b>{self._escape_html(c.get('source_a', 'Source A'))}:</b> \"{self._escape_html(c.get('claim_a', ''))}\"<br/>"
                    f"• <b>{self._escape_html(c.get('source_b', 'Source B'))}:</b> \"{self._escape_html(c.get('claim_b', ''))}\"<br/>"
                    f"• <b>Reason:</b> {self._escape_html(c.get('reason', ''))}"
                )
                story.append(Paragraph(c_text, body_style))

        # Citation Verifications
        if verifications:
            story.append(Spacer(1, 6))
            story.append(Paragraph("Citation Verification Analysis", h2_style))
            for v in verifications:
                status_color = "#16a34a" if v.get("status") == "SUPPORTED" else ("#d97706" if "PARTIAL" in v.get("status", "") else "#dc2626")
                v_text = (
                    f"• <font color='{status_color}'><b>[{v.get('status')}]</b></font> \"{self._escape_html(v.get('claim'))}\"<br/>"
                    f"&nbsp;&nbsp;&nbsp;<i>Reason:</i> {self._escape_html(v.get('reason', ''))}"
                )
                story.append(Paragraph(v_text, body_style))

        # Sources Table / List
        story.append(Spacer(1, 8))
        story.append(Paragraph("Sources & Evidence", h2_style))

        if sources:
            table_data = [["#", "Document / Location", "Chunk ID", "Preview Snippet"]]
            for idx, s in enumerate(sources, 1):
                fname = s.get("filename", "Document")
                page = f"p. {s['page']}" if s.get("page") else ""
                sec = f"sec. {s['section']}" if s.get("section") else ""
                loc = ", ".join(filter(None, [fname, page, sec]))
                cid = s.get("chunk_id", "")
                prev = (s.get("preview") or "")[:120].replace("\n", " ") + ("..." if len(s.get("preview") or "") > 120 else "")

                table_data.append([
                    str(idx),
                    Paragraph(self._escape_html(loc), body_style),
                    Paragraph(f"<code>{self._escape_html(cid)}</code>", body_style),
                    Paragraph(self._escape_html(prev), body_style),
                ])

            t = Table(table_data, colWidths=[20, 160, 100, 250])
            t.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])
            )
            story.append(t)
        else:
            story.append(Paragraph("No source passages cited.", body_style))

        story.append(Spacer(1, 16))
        footer_style = ParagraphStyle(
            "ReportFooter",
            parent=normal,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#94a3b8"),
            alignment=1,
        )
        story.append(Paragraph("Report generated locally by ContextIQ — Private AI-Powered Document Intelligence", footer_style))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    def _escape_html(self, text: str) -> str:
        """Escape HTML characters for safe ReportLab paragraph embedding."""
        if not text:
            return ""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
