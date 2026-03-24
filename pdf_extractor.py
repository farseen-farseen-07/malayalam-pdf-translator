"""
pdf_extractor.py
================
Extract structured text blocks from PDF files.
Detects: headings, paragraphs, list items, tables, page breaks.
Falls back to OCR for scanned/image PDFs (requires tesseract).
"""

import re
import pdfplumber
from pypdf import PdfReader
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TextBlock:
    """One logical unit of content from the PDF."""
    text:       str
    block_type: str = "paragraph"
    # block_type values:
    #   paragraph | heading1 | heading2 | heading3
    #   list_item | table    | page_break
    page_num:   int   = 0
    font_size:  float = 0.0
    is_bold:    bool  = False
    table_data: Optional[List[List[str]]] = None
    translated: str   = ""

    def is_empty(self) -> bool:
        return not self.text.strip()


# ── Heuristics ────────────────────────────────────────────────────────────────

def _heading_level(text: str, size: float, avg: float, bold: bool) -> str:
    text = text.strip()
    if not text or len(text) > 250:
        return "paragraph"
    ratio = size / max(avg, 1.0)
    if ratio >= 1.5 or (ratio >= 1.3 and bold):
        return "heading1"
    if ratio >= 1.2 or (ratio >= 1.1 and bold):
        return "heading2"
    if bold and len(text) < 150:
        return "heading3"
    if re.match(r"^\d+(\.\d+)*[\s.)‐-]+[A-Z]", text) and len(text) < 120:
        return "heading2"
    return "paragraph"


def _is_list_item(text: str) -> bool:
    t = text.strip()
    return bool(
        re.match(r"^[\u2022\u2023\u25E6\u2043\u2219\u00b7\*•]\s", t) or
        re.match(r"^-\s+\S",  t) or
        re.match(r"^\d+[.)]\s", t) or
        re.match(r"^[a-zA-Z][.)]\s", t)
    )


# ── pdfplumber extractor (primary) ───────────────────────────────────────────

def _extract_pdfplumber(pdf_path: Path, progress_cb=None) -> List[TextBlock]:
    blocks: List[TextBlock] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)

        # Sample pages to get average body font size
        all_sizes = []
        for page in pdf.pages[: min(6, total)]:
            for ch in page.chars or []:
                sz = ch.get("size", 0)
                if sz and sz > 4:
                    all_sizes.append(sz)
        avg = (sum(all_sizes) / len(all_sizes)) if all_sizes else 10.0

        for pi, page in enumerate(pdf.pages):
            if progress_cb:
                progress_cb(pi, total, f"Page {pi+1}/{total}")

            page_num = pi + 1

            # ── Tables ───────────────────────────────────────────────────────
            table_bboxes: List = []
            try:
                for tbl_obj in page.find_tables() or []:
                    table_bboxes.append(tbl_obj.bbox)
                    raw = tbl_obj.extract()
                    if raw:
                        cleaned = [
                            [str(c or "").strip() for c in row] for row in raw
                        ]
                        blocks.append(TextBlock(
                            text="[TABLE]", block_type="table",
                            page_num=page_num, table_data=cleaned,
                        ))
            except Exception:
                pass

            # ── Words ─────────────────────────────────────────────────────────
            try:
                words = page.extract_words(
                    extra_attrs=["fontname", "size"],
                    keep_blank_chars=False,
                    use_text_flow=True,
                ) or []
            except Exception:
                words = []

            if not words:
                plain = page.extract_text() or ""
                for ln in plain.split("\n"):
                    ln = ln.strip()
                    if ln:
                        btype = "list_item" if _is_list_item(ln) else "paragraph"
                        blocks.append(TextBlock(text=ln, block_type=btype,
                                                page_num=page_num, font_size=avg))
                blocks.append(TextBlock(text="", block_type="page_break",
                                        page_num=page_num))
                continue

            # Filter words inside table bboxes
            def _in_table(w):
                wx = (w["x0"] + w["x1"]) / 2
                wy = (w["top"] + w["bottom"]) / 2
                return any(
                    b[0] <= wx <= b[2] and b[1] <= wy <= b[3]
                    for b in table_bboxes
                )

            words = [w for w in words if not _in_table(w)]

            # Group words → lines by rounded top-y
            line_map: dict = {}
            for w in words:
                key = round(w["top"], 1)
                line_map.setdefault(key, []).append(w)

            sorted_lines = []
            for y in sorted(line_map):
                ws = sorted(line_map[y], key=lambda w: w["x0"])
                txt  = " ".join(w["text"] for w in ws)
                szs  = [w.get("size", avg) for w in ws if w.get("size")]
                fsz  = max(szs) if szs else avg
                fns  = [w.get("fontname", "") for w in ws]
                bold = any("Bold" in f or "bold" in f for f in fns)
                sorted_lines.append({"y": y, "text": txt,
                                     "font_size": fsz, "is_bold": bold})

            # Lines → paragraphs (merge same-style consecutive lines)
            cur_lines: List[str] = []
            cur_size  = avg
            cur_bold  = False
            prev_bottom: Optional[float] = None

            def _flush():
                nonlocal cur_lines, cur_size, cur_bold, prev_bottom
                if not cur_lines:
                    return
                merged = " ".join(cur_lines).strip()
                if not merged:
                    cur_lines = []; return
                btype = _heading_level(merged, cur_size, avg, cur_bold)
                if _is_list_item(merged):
                    btype = "list_item"
                blocks.append(TextBlock(
                    text=merged, block_type=btype,
                    page_num=page_num, font_size=cur_size, is_bold=cur_bold,
                ))
                cur_lines = []
                cur_size  = avg
                cur_bold  = False

            for line in sorted_lines:
                y    = line["y"]
                size = line["font_size"]
                bold = line["is_bold"]
                txt  = line["text"].strip()
                if not txt:
                    continue

                style_changed = abs(size - cur_size) > 0.9 or bold != cur_bold
                gap_break     = prev_bottom is not None and (y - prev_bottom) > size * 1.8

                if cur_lines and (gap_break or style_changed):
                    _flush()

                if not cur_lines:
                    cur_size = size
                    cur_bold = bold

                cur_lines.append(txt)
                prev_bottom = y + size

            _flush()

            blocks.append(TextBlock(text="", block_type="page_break",
                                    page_num=page_num))

    return blocks


# ── OCR fallback ─────────────────────────────────────────────────────────────

def _extract_ocr(pdf_path: Path, progress_cb=None, lang: str = "eng") -> List[TextBlock]:
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        raise ImportError(
            "OCR requires:\n"
            "  pip install pytesseract pdf2image\n"
            "  sudo apt-get install tesseract-ocr poppler-utils"
        )

    blocks: List[TextBlock] = []
    images = convert_from_path(str(pdf_path), dpi=200)
    for i, img in enumerate(images):
        if progress_cb:
            progress_cb(i, len(images), f"OCR page {i+1}/{len(images)}")
        text = pytesseract.image_to_string(img, lang=lang)
        for ln in text.split("\n"):
            ln = ln.strip()
            if not ln:
                continue
            btype = "list_item" if _is_list_item(ln) else "paragraph"
            blocks.append(TextBlock(text=ln, block_type=btype, page_num=i + 1))
        blocks.append(TextBlock(text="", block_type="page_break", page_num=i + 1))
    return blocks


# ── Public API ────────────────────────────────────────────────────────────────

def extract_pdf(
    pdf_path,
    use_ocr:       bool = False,
    ocr_fallback:  bool = True,
    progress_cb=None,
) -> List[TextBlock]:
    """
    Extract TextBlocks from *pdf_path*.
    Automatically falls back to OCR if almost no text is found.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted:
            raise ValueError("PDF is password-protected. Please decrypt it first.")
    except Exception as e:
        if "password" in str(e).lower() or "encrypted" in str(e).lower():
            raise

    if use_ocr:
        print("  [OCR] Using Tesseract OCR…")
        return _extract_ocr(pdf_path, progress_cb)

    blocks = _extract_pdfplumber(pdf_path, progress_cb)

    body_text = " ".join(
        b.text for b in blocks
        if b.block_type not in ("page_break", "table")
    ).strip()

    if len(body_text) < 100 and ocr_fallback:
        print("  [INFO] Very little text found — trying OCR fallback…")
        try:
            return _extract_ocr(pdf_path, progress_cb)
        except ImportError:
            print(
                "  [WARN] OCR not available. "
                "Install pytesseract + pdf2image for scanned PDFs."
            )

    return blocks


def get_translatable_blocks(blocks: List[TextBlock]) -> List[TextBlock]:
    """Return only blocks that carry text worth translating."""
    return [b for b in blocks if b.text.strip() and b.block_type != "page_break"]
