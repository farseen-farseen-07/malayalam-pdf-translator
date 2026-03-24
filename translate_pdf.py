#!/usr/bin/env python3
"""
translate_pdf.py
================
Command-line tool: English PDF → Malayalam PDF

Usage examples:
    python translate_pdf.py my_document.pdf
    python translate_pdf.py my_document.pdf -o output.pdf
    python translate_pdf.py my_document.pdf --bilingual
    python translate_pdf.py my_document.pdf --ocr
    python translate_pdf.py my_document.pdf --method mymemory
    python translate_pdf.py my_document.pdf --no-cache
    python translate_pdf.py my_document.pdf --bilingual --method mymemory -o result.pdf
"""

import sys
import os
import time
import argparse
import traceback
from pathlib import Path

# Allow running from any working directory
sys.path.insert(0, str(Path(__file__).parent))

from pdf_extractor    import extract_pdf, get_translatable_blocks
from translator_core  import translate_text, load_cache, save_cache, BATCH_DELAY


# ── Renderer (auto-selects best available) ────────────────────────────────────

def _pick_renderer():
    """
    Returns (generate_pdf_fn, renderer_description).
    Tries Cairo+Pango+HarfBuzz first (best quality, works on macOS & Linux).
    Falls back to ReportLab if Cairo/Pango are not installed.
    """
    try:
        # pdf_generator_pango handles macOS (.dylib) and Linux (.so) automatically
        from pdf_generator_pango import generate_pdf, _MAL_FONT_FAMILY
        return generate_pdf, f"Cairo + Pango + HarfBuzz  [{_MAL_FONT_FAMILY}]"
    except Exception as e:
        try:
            from pdf_generator import generate_pdf
            return generate_pdf, "ReportLab + FreeSans  (fallback)"
        except Exception as e2:
            raise RuntimeError(
                f"No PDF renderer available.\n"
                f"  macOS:  brew install cairo pango && pip3 install pycairo\n"
                f"  Linux:  sudo apt-get install libcairo2 libpangocairo-1.0-0\n"
                f"  Pango error:    {e}\n"
                f"  ReportLab error: {e2}"
            )


# ── UI helpers ────────────────────────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          PDF Malayalam Translator  v3.0                      ║
║          English PDF  →  Malayalam PDF                       ║
╚══════════════════════════════════════════════════════════════╝"""


def _bar(current: int, total: int, label: str = "", width: int = 36) -> None:
    if total == 0:
        return
    pct    = current / total
    filled = int(width * pct)
    bar    = "█" * filled + "░" * (width - filled)
    short  = (label[:24] + "…") if len(label) > 25 else label.ljust(25)
    print(f"\r  [{bar}] {pct*100:5.1f}%  {short}", end="", flush=True)


# ── Pipeline ──────────────────────────────────────────────────────────────────

def translate_pdf(
    input_path,
    output_path = None,
    method      = "google",
    bilingual   = False,
    use_ocr     = False,
    use_cache   = True,
    src_lang    = "en",
    tgt_lang    = "ml",
    verbose     = False,
):
    """Full pipeline: extract → translate → generate PDF."""
    input_path  = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    if output_path is None:
        suf         = "_bilingual" if bilingual else "_malayalam"
        output_path = input_path.parent / f"{input_path.stem}{suf}.pdf"
    output_path = Path(output_path)

    generate_pdf, renderer_name = _pick_renderer()

    print(BANNER)
    print(f"\n  Input    : {input_path}")
    print(f"  Output   : {output_path}")
    print(f"  Mode     : {'Bilingual (EN + ML)' if bilingual else 'Malayalam only'}")
    print(f"  Engine   : {method}")
    print(f"  Renderer : {renderer_name}")
    print(f"  Cache    : {'enabled' if use_cache else 'disabled'}")
    print()

    # ── Step 1 : Extract ─────────────────────────────────────────────────────
    print("● Step 1/3  Extracting text from PDF …")
    t0 = time.time()

    def _ext_cb(cur, tot, lbl):
        _bar(cur, tot, lbl)

    blocks        = extract_pdf(input_path, use_ocr=use_ocr,
                                ocr_fallback=True, progress_cb=_ext_cb)
    translatable  = get_translatable_blocks(blocks)
    total_pages   = max((b.page_num for b in blocks), default=1)
    print()
    print(f"  ✓  {len(translatable)} text blocks  |  {total_pages} pages  "
          f"({time.time()-t0:.1f}s)\n")

    if not translatable:
        print("  ⚠  No text found. Try --ocr for scanned PDFs.")
        return None

    # ── Step 2 : Translate ────────────────────────────────────────────────────
    print(f"● Step 2/3  Translating {len(translatable)} blocks → Malayalam …")
    t0    = time.time()
    cache = load_cache() if use_cache else {}

    # Flatten all texts (including table cells) into one list
    all_texts:      list = []
    block_text_idx: dict = {}   # block_index → index in all_texts
    table_cell_map: dict = {}   # block_index → [(row, col, text_idx), …]

    for bi, block in enumerate(blocks):
        if block.block_type == "table" and block.table_data:
            cells = []
            for r, row in enumerate(block.table_data):
                for c, cell in enumerate(row):
                    if str(cell or "").strip():
                        cells.append((r, c, len(all_texts)))
                        all_texts.append(str(cell))
            table_cell_map[bi] = cells
        elif block.text.strip() and block.block_type != "page_break":
            block_text_idx[bi] = len(all_texts)
            all_texts.append(block.text)

    translated: list = []
    last_report = [-1]
    print()

    for i, txt in enumerate(all_texts):
        if i - last_report[0] >= 1:
            _bar(i, len(all_texts), txt[:30])
            last_report[0] = i
        translated.append(
            translate_text(txt, src_lang, tgt_lang, method, cache)
        )
        time.sleep(BATCH_DELAY)
        if (i + 1) % 50 == 0 and use_cache:
            save_cache(cache)

    if use_cache:
        save_cache(cache)
    print()
    print(f"  ✓  Translation done  ({time.time()-t0:.1f}s)\n")

    # Map translations back onto blocks
    for bi, block in enumerate(blocks):
        if block.block_type == "table" and bi in table_cell_map:
            new_rows = [row[:] for row in block.table_data]
            for r, c, ti in table_cell_map[bi]:
                new_rows[r][c] = translated[ti]
            block.table_data = new_rows
            block.translated = "[TABLE]"
        elif bi in block_text_idx:
            block.translated = translated[block_text_idx[bi]]
        else:
            block.translated = block.text

    # ── Step 3 : Generate PDF ─────────────────────────────────────────────────
    print(f"● Step 3/3  Generating {'bilingual ' if bilingual else ''}Malayalam PDF …")
    t0 = time.time()

    def _pdf_cb(cur, tot, lbl):
        _bar(cur, tot, lbl)

    doc_title = f"Malayalam Translation – {input_path.stem}"
    generate_pdf(blocks, output_path, bilingual=bilingual,
                 title=doc_title, progress_cb=_pdf_cb)
    print()

    sz = output_path.stat().st_size // 1024
    print(f"  ✓  Saved  →  {output_path}  ({sz} KB,  {time.time()-t0:.1f}s)\n")
    print("═" * 62)
    print(f"  ✅  Done!   Output: {output_path}")
    print("═" * 62)
    return output_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Translate an English PDF to Malayalam",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python translate_pdf.py report.pdf
  python translate_pdf.py report.pdf -o report_ml.pdf
  python translate_pdf.py report.pdf --bilingual
  python translate_pdf.py report.pdf --ocr
  python translate_pdf.py report.pdf --method mymemory
  python translate_pdf.py report.pdf --no-cache
        """,
    )
    ap.add_argument("input",  help="Input English PDF file")
    ap.add_argument("-o", "--output", help="Output path (default: <input>_malayalam.pdf)")
    ap.add_argument("--method",
                    choices=["google", "mymemory", "libretranslate", "auto"],
                    default="google",
                    help="Translation engine (default: google)")
    ap.add_argument("--bilingual", action="store_true",
                    help="Include original English above each Malayalam block")
    ap.add_argument("--ocr", action="store_true",
                    help="Force OCR mode (scanned / image PDFs)")
    ap.add_argument("--no-cache", action="store_true",
                    help="Disable translation cache")
    ap.add_argument("--src", default="en",
                    help="Source language code (default: en)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="Show full error tracebacks")

    args = ap.parse_args()

    try:
        result = translate_pdf(
            input_path  = args.input,
            output_path = args.output,
            method      = args.method,
            bilingual   = args.bilingual,
            use_ocr     = args.ocr,
            use_cache   = not args.no_cache,
            src_lang    = args.src,
            tgt_lang    = "ml",
            verbose     = args.verbose,
        )
        sys.exit(0 if result else 1)
    except FileNotFoundError as e:
        print(f"\n  ✗  {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n  [CANCELLED]")
        sys.exit(1)
    except Exception as e:
        print(f"\n  ✗  {e}")
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
