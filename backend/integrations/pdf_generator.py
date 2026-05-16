"""
INFERA PDF export — writes report bundle to disk (verifiable side-effect).
"""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from backend.core.config import settings
from backend.models.schemas import ReportOutput
from backend.core.logger import get_logger

logger = get_logger("pdf_generator")

import markdown

def _safe_text(text: str) -> str:
    """FPDF core fonts are Latin-1 — strip unsupported characters."""
    return text.encode("latin-1", errors="replace").decode("latin-1")

def write_report_pdf(report: ReportOutput, workflow_id: str) -> str | None:
    """
    Write a combined PDF of all four briefs.

    Returns absolute path string, or None on failure.
    """
    out_dir = Path(settings.REPORTS_OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"report_{workflow_id}.pdf"

    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # Title and Confidence
        pdf.set_font("Helvetica", "B", 18)
        pdf.multi_cell(0, 8, _safe_text(report.title))
        pdf.ln(4)
        pdf.set_font("Helvetica", "I", 11)
        pdf.multi_cell(0, 5, _safe_text(f"Confidence: {report.confidence_score:.0%}"))
        pdf.ln(8)

        sections = [
            ("Executive Brief", report.exec_brief),
            ("Technical Breakdown", report.tech_brief),
            ("Sales Battle Card", report.sales_brief),
            ("Risk Register", report.risk_brief),
        ]
        for heading, body in sections:
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(0, 8, _safe_text(heading))
            pdf.ln(2)
            
            safe_body = body or "(empty)"
            safe_body = safe_body.replace(":white_check_mark:", "[+]").replace("✅", "[+]")
            safe_body = safe_body.replace(":warning:", "[!]").replace("⚠️", "[!]")
            
            # Convert markdown to HTML and write
            md_html = markdown.markdown(safe_body, extensions=["tables"])
            pdf.write_html(_safe_text(md_html))
            pdf.ln(8)

        pdf.output(str(path))
        logger.info("pdf_written", path=str(path), workflow_id=workflow_id)
        return str(path.resolve())
    except Exception as e:
        logger.error("pdf_write_failed", workflow_id=workflow_id, error=str(e))
        return None
