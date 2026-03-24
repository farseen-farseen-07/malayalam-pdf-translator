"""
pdf_generator.py - Generate Malayalam PDF from translated text blocks
Uses ReportLab with embedded Malayalam-capable font (FreeSans/FreeSerif)
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from pathlib import Path
import os


# ── Font setup ──────────────────────────────────────────────────────────────

FONT_PATHS = {
    "regular": [
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "bold": [
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "italic": [
        "/usr/share/fonts/truetype/freefont/FreeSansOblique.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    ],
}


def find_font(font_type="regular"):
    for path in FONT_PATHS.get(font_type, []):
        if Path(path).exists():
            return path
    return None


def register_fonts():
    """Register Malayalam-capable fonts with ReportLab."""
    reg_path = find_font("regular")
    bold_path = find_font("bold")
    italic_path = find_font("italic")

    if not reg_path:
        raise RuntimeError("No suitable font found. Install fonts-freefont-ttf or fonts-dejavu")

    pdfmetrics.registerFont(TTFont("MalFont", reg_path))
    if bold_path:
        pdfmetrics.registerFont(TTFont("MalFont-Bold", bold_path))
    else:
        pdfmetrics.registerFont(TTFont("MalFont-Bold", reg_path))
    if italic_path:
        pdfmetrics.registerFont(TTFont("MalFont-Italic", italic_path))
    else:
        pdfmetrics.registerFont(TTFont("MalFont-Italic", reg_path))

    return reg_path


# ── Style definitions ────────────────────────────────────────────────────────

def build_styles(bilingual=False):
    """Return a dict of named paragraph styles."""
    base_size = 11

    styles = {
        "normal": ParagraphStyle(
            "MalNormal",
            fontName="MalFont",
            fontSize=base_size,
            leading=base_size * 1.7,
            spaceAfter=6,
            spaceBefore=2,
            alignment=TA_JUSTIFY,
            wordWrap="RTL",  # Better for complex scripts
        ),
        "heading1": ParagraphStyle(
            "MalH1",
            fontName="MalFont-Bold",
            fontSize=base_size + 6,
            leading=(base_size + 6) * 1.4,
            spaceAfter=10,
            spaceBefore=16,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#1a1a2e"),
        ),
        "heading2": ParagraphStyle(
            "MalH2",
            fontName="MalFont-Bold",
            fontSize=base_size + 3,
            leading=(base_size + 3) * 1.4,
            spaceAfter=8,
            spaceBefore=12,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#16213e"),
        ),
        "heading3": ParagraphStyle(
            "MalH3",
            fontName="MalFont-Bold",
            fontSize=base_size + 1,
            leading=(base_size + 1) * 1.4,
            spaceAfter=6,
            spaceBefore=8,
            alignment=TA_LEFT,
        ),
        "list_item": ParagraphStyle(
            "MalList",
            fontName="MalFont",
            fontSize=base_size,
            leading=base_size * 1.6,
            spaceAfter=4,
            leftIndent=20,
            bulletIndent=10,
        ),
        "table_cell": ParagraphStyle(
            "MalTableCell",
            fontName="MalFont",
            fontSize=base_size - 1,
            leading=(base_size - 1) * 1.5,
        ),
        # English companion (bilingual mode)
        "english": ParagraphStyle(
            "English",
            fontName="Helvetica",
            fontSize=base_size - 1,
            leading=(base_size - 1) * 1.5,
            textColor=colors.HexColor("#555555"),
            spaceAfter=2,
            italic=True,
        ),
        "english_heading": ParagraphStyle(
            "EnglishH",
            fontName="Helvetica-Bold",
            fontSize=base_size,
            leading=base_size * 1.4,
            textColor=colors.HexColor("#555555"),
            spaceAfter=2,
        ),
        "page_header": ParagraphStyle(
            "PageHeader",
            fontName="MalFont",
            fontSize=8,
            textColor=colors.HexColor("#888888"),
            alignment=TA_CENTER,
        ),
    }
    return styles


# ── Table rendering ──────────────────────────────────────────────────────────

def make_table_flowable(table_data, translated_rows, styles):
    """Build a ReportLab Table from original + translated cell data."""
    if not table_data:
        return None

    table_style_def = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "MalFont-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTNAME", (0, 1), (-1, -1), "MalFont"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8f9fa")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ])

    cell_style = styles["table_cell"]
    rows_flowable = []

    for row_i, row in enumerate(translated_rows):
        flow_row = []
        for cell_text in row:
            text = str(cell_text or "").strip()
            if text:
                try:
                    flow_row.append(Paragraph(text, cell_style))
                except Exception:
                    flow_row.append(text)
            else:
                flow_row.append("")
        if flow_row:
            rows_flowable.append(flow_row)

    if not rows_flowable:
        return None

    # Auto-size columns
    col_count = max(len(r) for r in rows_flowable)
    page_width = A4[0] - 40 * mm
    col_width = page_width / max(col_count, 1)

    tbl = Table(rows_flowable, colWidths=[col_width] * col_count, repeatRows=1)
    tbl.setStyle(table_style_def)
    return tbl


# ── Header/Footer ────────────────────────────────────────────────────────────

def make_header_footer(title="Malayalam Translation"):
    def on_page(canvas, doc):
        canvas.saveState()
        w, h = A4
        # Header line
        canvas.setStrokeColor(colors.HexColor("#2c3e50"))
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, h - 15 * mm, w - 20 * mm, h - 15 * mm)
        canvas.setFont("MalFont", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(20 * mm, h - 12 * mm, title)
        canvas.drawRightString(w - 20 * mm, h - 12 * mm, f"Page {doc.page}")
        # Footer line
        canvas.line(20 * mm, 12 * mm, w - 20 * mm, 12 * mm)
        canvas.setFont("MalFont", 7)
        canvas.drawCentredString(w / 2, 8 * mm, "Generated by PDF Malayalam Translator")
        canvas.restoreState()

    return on_page


# ── Main PDF builder ─────────────────────────────────────────────────────────

def generate_pdf(blocks, output_path, bilingual=False,
                 title="Malayalam Translation", progress_cb=None):
    """
    Build output PDF from translated TextBlock list.
    blocks: list of TextBlock (with .text = Malayalam and .translated = Malayalam)
    bilingual: if True, include original English alongside Malayalam
    """
    register_fonts()
    styles = build_styles(bilingual)

    story = []
    total = len(blocks)

    # Cover-style title spacer
    story.append(Spacer(1, 8 * mm))

    page_num = 1

    for idx, block in enumerate(blocks):
        if progress_cb and idx % 20 == 0:
            progress_cb(idx, total, "generating PDF")

        btype = block.block_type

        # Page break
        if btype == "page_break":
            story.append(PageBreak())
            page_num += 1
            continue

        # Use translated text if available, else original
        mal_text = block.translated if block.translated else block.text
        eng_text = block.text  # original English

        if not mal_text.strip():
            continue

        # Escape XML special chars for ReportLab
        def rl_escape(t):
            return (t.replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;"))

        mal_safe = rl_escape(mal_text)
        eng_safe = rl_escape(eng_text)

        # Table block
        if btype == "table" and block.table_data:
            # Translate each cell
            translated_rows = []
            for row in block.table_data:
                t_row = []
                for cell in row:
                    t_cell = cell  # cells are already translated in main flow
                    t_row.append(t_cell)
            translated_rows = block.table_data  # Use whatever is in table_data

            tbl = make_table_flowable(block.table_data, translated_rows, styles)
            if tbl:
                story.append(Spacer(1, 4))
                story.append(tbl)
                story.append(Spacer(1, 8))
            continue

        # Heading blocks
        if btype in ("heading1", "heading2", "heading3"):
            style_key = btype
            style = styles[style_key]

            group = []
            if bilingual and eng_text.strip():
                eng_style = styles["english_heading"]
                try:
                    group.append(Paragraph(eng_safe, eng_style))
                except Exception:
                    pass

            try:
                group.append(Paragraph(mal_safe, style))
            except Exception as e:
                group.append(Paragraph(f"[Render error: {e}]", styles["normal"]))

            if btype == "heading1":
                group.append(HRFlowable(width="100%", thickness=0.5,
                                        color=colors.HexColor("#2c3e50"), spaceAfter=4))

            story.append(KeepTogether(group))
            continue

        # List item
        if btype == "list_item":
            style = styles["list_item"]
            # Add bullet if not present
            if not re.match(r'^[•\-\*\d]', mal_text):
                mal_safe = "• " + mal_safe

            if bilingual and eng_text.strip():
                try:
                    story.append(Paragraph(eng_safe, styles["english"]))
                except Exception:
                    pass

            try:
                story.append(Paragraph(mal_safe, style))
            except Exception as e:
                story.append(Paragraph(f"[Error: {e}]", styles["normal"]))
            continue

        # Normal paragraph
        style = styles["normal"]
        if bilingual and eng_text.strip():
            try:
                story.append(Paragraph(eng_safe, styles["english"]))
            except Exception:
                pass

        try:
            story.append(Paragraph(mal_safe, style))
        except Exception as e:
            story.append(Paragraph(f"[Render error: {e}]", styles["normal"]))

    # Build
    on_page = make_header_footer(title)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title=title,
        author="PDF Malayalam Translator",
    )

    try:
        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    except Exception as e:
        # Try building without header/footer if font issue
        print(f"  [WARN] Header/footer error ({e}), rebuilding without...")
        doc.build(story)

    return output_path


import re
