"""ATS-friendly resume PDF export (text-based layout, no images or tables)."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .models import Profile

_TITLE = ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=22, leading=26, alignment=TA_CENTER, spaceAfter=4)
_CONTACT = ParagraphStyle("Contact", fontName="Helvetica", fontSize=10, leading=14, alignment=TA_CENTER, spaceAfter=15)
_H1 = ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=13, leading=16, spaceBefore=12, spaceAfter=4, keepWithNext=True)
_BODY = ParagraphStyle("Body", fontName="Helvetica", fontSize=10, leading=14, alignment=TA_LEFT, spaceAfter=6)
_ITEM = ParagraphStyle("Item", fontName="Helvetica-Bold", fontSize=11, leading=14, keepWithNext=True)


def _p(text: str) -> str:
    """Escape user text so characters like & and < can't break ReportLab's markup parser."""
    return escape(text).replace("\n", "<br/>")


def generate_ats_pdf(profile: Profile) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54,
        title=f"{profile.full_name} - Resume", author=profile.full_name,
    )
    story = [Paragraph(_p(profile.full_name), _TITLE)]

    contact = "  |  ".join(x for x in (profile.phone, profile.email, profile.location) if x)
    if contact:
        story.append(Paragraph(_p(contact), _CONTACT))

    if profile.summary:
        story += [Paragraph("PROFESSIONAL SUMMARY", _H1), Paragraph(_p(profile.summary), _BODY)]

    if profile.experience:
        story.append(Paragraph("PROFESSIONAL EXPERIENCE", _H1))
        for x in profile.experience:
            dur = f" ({x.duration})" if x.duration else ""
            story.append(Paragraph(f"<b>{_p(x.role)}</b> — {_p(x.company)}{_p(dur)}", _ITEM))
            if x.description:
                story.append(Paragraph(_p(x.description), _BODY))
            story.append(Spacer(1, 4))

    if profile.education:
        story.append(Paragraph("EDUCATION", _H1))
        for e in profile.education:
            yr = f" ({e.graduation_year})" if e.graduation_year else ""
            story.append(Paragraph(f"<b>{_p(e.degree)}</b> — {_p(e.school)}{yr}", _BODY))

    if profile.certifications:
        story.append(Paragraph("CERTIFICATIONS &amp; SKILLS", _H1))
        story.append(Paragraph(" • ".join(_p(c.name) for c in profile.certifications), _BODY))

    doc.build(story)
    return buffer.getvalue()
