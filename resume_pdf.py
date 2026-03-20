"""
resume_pdf.py — Professional resume PDF generator using ReportLab.
Replaces the LaTeX/pdflatex pipeline entirely. No external tools needed.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle
)
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
import os

# --- Colour palette ---
BLACK      = HexColor("#1a1a1a")
DARK_GREY  = HexColor("#333333")
MID_GREY   = HexColor("#555555")
LIGHT_GREY = HexColor("#888888")
ACCENT     = HexColor("#2563eb")   # clean blue for name / section headers
RULE_COLOR = HexColor("#d1d5db")

# --- Typography ---
NAME_SIZE       = 22
SECTION_SIZE    = 10
BODY_SIZE       = 9
SMALL_SIZE      = 8.5
LEADING_BODY    = 13
LEADING_SMALL   = 12

FONT_REGULAR = "Helvetica"
FONT_BOLD    = "Helvetica-Bold"
FONT_ITALIC  = "Helvetica-Oblique"

MARGIN = 0.65 * inch


def _styles():
    return {
        "name": ParagraphStyle(
            "name",
            fontName=FONT_BOLD,
            fontSize=NAME_SIZE,
            leading=NAME_SIZE + 4,
            textColor=BLACK,
            alignment=TA_LEFT,
        ),
        "contact": ParagraphStyle(
            "contact",
            fontName=FONT_REGULAR,
            fontSize=SMALL_SIZE,
            leading=LEADING_SMALL,
            textColor=MID_GREY,
            alignment=TA_LEFT,
        ),
        "section_header": ParagraphStyle(
            "section_header",
            fontName=FONT_BOLD,
            fontSize=SECTION_SIZE,
            leading=SECTION_SIZE + 4,
            textColor=ACCENT,
            spaceAfter=2,
        ),
        "job_title": ParagraphStyle(
            "job_title",
            fontName=FONT_BOLD,
            fontSize=BODY_SIZE,
            leading=LEADING_BODY,
            textColor=BLACK,
        ),
        "job_meta": ParagraphStyle(
            "job_meta",
            fontName=FONT_ITALIC,
            fontSize=SMALL_SIZE,
            leading=LEADING_SMALL,
            textColor=LIGHT_GREY,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontName=FONT_REGULAR,
            fontSize=BODY_SIZE,
            leading=LEADING_BODY,
            textColor=DARK_GREY,
            leftIndent=12,
            bulletIndent=2,
            spaceBefore=1,
        ),
        "summary": ParagraphStyle(
            "summary",
            fontName=FONT_REGULAR,
            fontSize=BODY_SIZE,
            leading=LEADING_BODY,
            textColor=DARK_GREY,
        ),
        "education_title": ParagraphStyle(
            "education_title",
            fontName=FONT_BOLD,
            fontSize=BODY_SIZE,
            leading=LEADING_BODY,
            textColor=BLACK,
        ),
        "education_sub": ParagraphStyle(
            "education_sub",
            fontName=FONT_REGULAR,
            fontSize=SMALL_SIZE,
            leading=LEADING_SMALL,
            textColor=MID_GREY,
        ),
        "skills": ParagraphStyle(
            "skills",
            fontName=FONT_REGULAR,
            fontSize=BODY_SIZE,
            leading=LEADING_BODY,
            textColor=DARK_GREY,
        ),
    }


def _rule(story):
    story.append(Spacer(1, 3))
    story.append(HRFlowable(width="100%", thickness=0.5, color=RULE_COLOR))
    story.append(Spacer(1, 5))


def _section(story, title, styles):
    story.append(Paragraph(title.upper(), styles["section_header"]))
    _rule(story)


def _contact_line(data: dict) -> str:
    parts = []
    if data.get("email"):    parts.append(data["email"])
    if data.get("phone"):    parts.append(data["phone"])
    if data.get("linkedin"): parts.append(data["linkedin"])
    if data.get("github"):   parts.append(data["github"])
    return "  ·  ".join(parts)


def build_resume_pdf(data: dict, output_path: str, job_title_hint: str = None):
    """
    Build a professional single-page resume PDF from structured data dict.

    data keys:
        name, email, phone, linkedin, github, summary,
        experience: [{title, company, location, start_date, end_date, bullets}],
        education:  [{degree, institution, year}],
        skills:     [str, ...]
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )

    styles = _styles()
    story  = []

    # ── Header ────────────────────────────────────────────────────────────────
    name = data.get("name", "Your Name")
    story.append(Paragraph(name, styles["name"]))

    contact = _contact_line(data)
    if contact:
        story.append(Paragraph(contact, styles["contact"]))
    story.append(Spacer(1, 8))

    # ── Summary ───────────────────────────────────────────────────────────────
    if data.get("summary"):
        _section(story, "Summary", styles)
        story.append(Paragraph(data["summary"], styles["summary"]))
        story.append(Spacer(1, 8))

    # ── Experience ────────────────────────────────────────────────────────────
    experience = data.get("experience", [])
    if experience:
        _section(story, "Experience", styles)
        for i, job in enumerate(experience):
            title   = job.get("title", "")
            company = job.get("company", "")
            loc     = job.get("location", "")
            start   = job.get("start_date", "")
            end     = job.get("end_date", "Present")
            bullets = job.get("bullets", [])

            date_str = f"{start} – {end}" if start else end

            # Two-column row: title+company left, dates right
            left_text  = f"<b>{title}</b>"
            right_text = f"<font color='#{LIGHT_GREY.hexval()[2:]}'>{date_str}</font>"

            left_para  = Paragraph(left_text,  styles["job_title"])
            right_para = Paragraph(right_text, ParagraphStyle(
                "date_right",
                fontName=FONT_REGULAR,
                fontSize=SMALL_SIZE,
                leading=LEADING_SMALL,
                textColor=LIGHT_GREY,
                alignment=TA_RIGHT,
            ))

            usable_width = doc.width
            t = Table(
                [[left_para, right_para]],
                colWidths=[usable_width * 0.72, usable_width * 0.28],
            )
            t.setStyle(TableStyle([
                ("VALIGN",     (0, 0), (-1, -1), "BOTTOM"),
                ("LEFTPADDING",  (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING",   (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
            ]))
            story.append(t)

            meta_parts = [company]
            if loc: meta_parts.append(loc)
            story.append(Paragraph(" · ".join(meta_parts), styles["job_meta"]))
            story.append(Spacer(1, 3))

            for b in bullets:
                story.append(Paragraph(f"• {b}", styles["bullet"]))

            if i < len(experience) - 1:
                story.append(Spacer(1, 7))

        story.append(Spacer(1, 8))

    # ── Education ─────────────────────────────────────────────────────────────
    education = data.get("education", [])
    if education:
        _section(story, "Education", styles)
        for edu in education:
            degree      = edu.get("degree", "")
            institution = edu.get("institution", "")
            year        = edu.get("year", "")
            story.append(Paragraph(degree, styles["education_title"]))
            sub_parts = [institution]
            if year: sub_parts.append(year)
            story.append(Paragraph(" · ".join(sub_parts), styles["education_sub"]))
            story.append(Spacer(1, 4))

        story.append(Spacer(1, 4))

    # ── Skills ────────────────────────────────────────────────────────────────
    skills = data.get("skills", [])
    if skills:
        _section(story, "Skills", styles)
        story.append(Paragraph(", ".join(skills), styles["skills"]))

    doc.build(story)
    print(f"✅  Resume written → {output_path}")