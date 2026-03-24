"""
pdf_generator_pango.py
======================
High-quality Malayalam PDF generator using:
  Cairo      — vector PDF output
  Pango      — Unicode text layout + line wrapping
  HarfBuzz   — complex-script shaping (conjuncts, ligatures, correct glyph order)

Works on macOS (Homebrew) and Linux.
Fonts are loaded from the bundled  fonts/  folder — no system font install needed.

Font priority (drop files into fonts/ to upgrade automatically):
  1. NotoSansMalayalam-Regular.ttf   best quality
  2. Manjari-Regular.ttf             elegant, modern
  3. AnjaliOldLipi.ttf
  4. Meera.ttf / Rachana.ttf
  5. FreeSans.ttf                    bundled fallback (always present)
"""

import cairo
import ctypes
import struct
import sys
import os
import re
from pathlib import Path
from typing import List, Optional

# ── Locate fonts/ next to this script ────────────────────────────────────────

_HERE      = Path(__file__).parent.resolve()
_FONTS_DIR = _HERE / "fonts"


# ── Platform-aware library names ─────────────────────────────────────────────

def _lib_names(base: str):
    """Return candidate library filenames for the current platform."""
    if sys.platform == "darwin":  # macOS
        homebrew_prefixes = [
            "/opt/homebrew/lib",   # Apple Silicon
            "/usr/local/lib",      # Intel
        ]
        candidates = []
        for prefix in homebrew_prefixes:
            candidates += [
                f"{prefix}/{base}.dylib",
                f"{prefix}/{base}.0.dylib",
            ]
        return candidates
    else:                          # Linux
        so_map = {
            "libcairo":          ["libcairo.so.2"],
            "libgobject-2.0":    ["libgobject-2.0.so.0"],
            "libpango-1.0":      ["libpango-1.0.so.0"],
            "libpangocairo-1.0": ["libpangocairo-1.0.so.0"],
            "libfontconfig":     ["libfontconfig.so.1"],
        }
        return so_map.get(base, [f"{base}.so"])


def _load_lib(base: str) -> ctypes.CDLL:
    """Load a shared library by base name, trying platform-specific paths."""
    errors = []
    for name in _lib_names(base):
        try:
            return ctypes.CDLL(name)
        except OSError as e:
            errors.append(f"{name}: {e}")

    # Last resort: let the dynamic linker try (works if pkg-config paths are set)
    short = base + (".dylib" if sys.platform == "darwin" else ".so")
    try:
        return ctypes.CDLL(short)
    except OSError as e:
        errors.append(f"{short}: {e}")

    install_hint = (
        "  macOS:  brew install cairo pango harfbuzz fontconfig\n"
        "  Linux:  sudo apt-get install libcairo2 libpango-1.0-0 libpangocairo-1.0-0"
    )
    raise RuntimeError(
        f"Cannot load '{base}'.\n{install_hint}\nAttempted:\n" +
        "\n".join(f"  {e}" for e in errors)
    )


_libcairo = _load_lib("libcairo")
_libgobj  = _load_lib("libgobject-2.0")
_libpango = _load_lib("libpango-1.0")
_libpc    = _load_lib("libpangocairo-1.0")


# ── Register bundled fonts with Fontconfig ────────────────────────────────────

def _register_fonts():
    """Tell Fontconfig about fonts/ so Pango can find them by family name."""
    try:
        fc = _load_lib("libfontconfig")
        fc.FcConfigGetCurrent.restype  = ctypes.c_void_p
        fc.FcConfigAppFontAddDir.restype  = ctypes.c_int
        fc.FcConfigAppFontAddDir.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        cfg = fc.FcConfigGetCurrent()
        fc.FcConfigAppFontAddDir(cfg, str(_FONTS_DIR).encode())
    except Exception:
        pass  # non-fatal


_register_fonts()


# ── ctypes signatures ─────────────────────────────────────────────────────────

_libgobj.g_object_unref.argtypes = [ctypes.c_void_p]

_libpango.pango_font_description_from_string.restype  = ctypes.c_void_p
_libpango.pango_font_description_from_string.argtypes = [ctypes.c_char_p]
_libpango.pango_font_description_free.argtypes        = [ctypes.c_void_p]

_libpc.pango_cairo_create_layout.restype   = ctypes.c_void_p
_libpc.pango_cairo_create_layout.argtypes  = [ctypes.c_void_p]

_libpango.pango_layout_set_text.argtypes             = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
_libpango.pango_layout_set_font_description.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_libpango.pango_layout_set_width.argtypes            = [ctypes.c_void_p, ctypes.c_int]
_libpango.pango_layout_set_alignment.argtypes        = [ctypes.c_void_p, ctypes.c_int]
_libpango.pango_layout_set_wrap.argtypes             = [ctypes.c_void_p, ctypes.c_int]
_libpango.pango_layout_set_spacing.argtypes          = [ctypes.c_void_p, ctypes.c_int]

_libpc.pango_cairo_show_layout.argtypes   = [ctypes.c_void_p, ctypes.c_void_p]
_libpc.pango_cairo_update_layout.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

_libpango.pango_layout_get_pixel_size.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_int),
]

_libcairo.cairo_status.restype  = ctypes.c_int
_libcairo.cairo_status.argtypes = [ctypes.c_void_p]

PANGO_SCALE        = 1024
PANGO_ALIGN_LEFT   = 0
PANGO_ALIGN_CENTER = 1
PANGO_ALIGN_RIGHT  = 2
PANGO_WRAP_WORD    = 0


# ── Best Malayalam font detection ─────────────────────────────────────────────

def _detect_malayalam_font() -> str:
    checks = [
        ("NotoSansMalayalam-Regular.ttf", "Noto Sans Malayalam"),
        ("Manjari-Regular.ttf",           "Manjari"),
        ("AnjaliOldLipi.ttf",             "AnjaliOldLipi"),
        ("Meera.ttf",                     "Meera"),
        ("Rachana.ttf",                   "Rachana"),
        ("FreeSans.ttf",                  "FreeSans"),
    ]
    for fname, family in checks:
        if (_FONTS_DIR / fname).exists():
            return family
    return "FreeSans"


_MAL_FONT_FAMILY = _detect_malayalam_font()


# ── Page layout ───────────────────────────────────────────────────────────────

A4_W, A4_H = 595.28, 841.89
MARGIN_L    = 56
MARGIN_R    = 56
MARGIN_T    = 64
MARGIN_B    = 58
TEXT_W      = A4_W - MARGIN_L - MARGIN_R

# ── Colours ───────────────────────────────────────────────────────────────────

C_HEADING   = (0.07, 0.09, 0.25)
C_BODY      = (0.07, 0.07, 0.07)
C_GREY      = (0.50, 0.50, 0.50)
C_ACCENT    = (0.15, 0.27, 0.53)
C_TABLE_HDR = (0.15, 0.27, 0.53)
C_TABLE_ROW = (0.97, 0.97, 0.99)
C_TABLE_ALT = (1.00, 1.00, 1.00)
C_WHITE     = (1.00, 1.00, 1.00)
C_RULE      = (0.15, 0.27, 0.53)

# ── Font strings ──────────────────────────────────────────────────────────────

def _build_fonts() -> dict:
    f = _MAL_FONT_FAMILY
    return {
        "body":    f"{f} 11",
        "bold":    f"{f} Bold 11",
        "h1":      f"{f} Bold 20",
        "h2":      f"{f} Bold 15",
        "h3":      f"{f} Bold 12",
        "english": "FreeSans Italic 9",
        "table":   f"{f} 9",
        "table_h": f"{f} Bold 9",
        "page":    "FreeSans 8",
        "footer":  "FreeSans 7",
    }


_F = _build_fonts()


# ── PyCairo pointer extraction ────────────────────────────────────────────────

def _get_cairo_ptr(ctx: cairo.Context) -> int:
    """Extract raw cairo_t* from PyCairo Context (CPython ABI offset 16)."""
    return struct.unpack_from("Q", (ctypes.c_char * 8).from_address(id(ctx) + 16))[0]


# ── Renderer ──────────────────────────────────────────────────────────────────

class _PangoRenderer:
    def __init__(self, ctx: cairo.Context):
        self.ctx = ctx
        self._cr = _get_cairo_ptr(ctx)
        assert _libcairo.cairo_status(self._cr) == 0, "Invalid cairo context"

    def text(self, text: str, font_str: str, x: float, y: float,
             max_width: float = 0, color=(0, 0, 0),
             align: int = PANGO_ALIGN_LEFT, line_spacing: int = 0) -> int:
        if not text.strip():
            return 0
        layout = _libpc.pango_cairo_create_layout(self._cr)
        if not layout:
            return 0
        fd = _libpango.pango_font_description_from_string(font_str.encode())
        _libpango.pango_layout_set_font_description(layout, fd)
        _libpango.pango_layout_set_text(layout, text.encode("utf-8"), -1)
        if max_width > 0:
            _libpango.pango_layout_set_width(layout, int(max_width * PANGO_SCALE))
        _libpango.pango_layout_set_alignment(layout, align)
        _libpango.pango_layout_set_wrap(layout, PANGO_WRAP_WORD)
        if line_spacing:
            _libpango.pango_layout_set_spacing(layout, line_spacing * PANGO_SCALE)
        self.ctx.set_source_rgb(*color)
        self.ctx.move_to(x, y)
        _libpc.pango_cairo_show_layout(self._cr, layout)
        w, h = ctypes.c_int(0), ctypes.c_int(0)
        _libpango.pango_layout_get_pixel_size(layout, ctypes.byref(w), ctypes.byref(h))
        _libgobj.g_object_unref(layout)
        _libpango.pango_font_description_free(fd)
        return h.value

    def hrule(self, y: float, color=C_RULE, thickness: float = 0.8):
        self.ctx.set_source_rgb(*color)
        self.ctx.set_line_width(thickness)
        self.ctx.move_to(MARGIN_L, y)
        self.ctx.line_to(A4_W - MARGIN_R, y)
        self.ctx.stroke()

    def rect_fill(self, x, y, w, h, color):
        self.ctx.set_source_rgb(*color)
        self.ctx.rectangle(x, y, w, h)
        self.ctx.fill()

    def rect_stroke(self, x, y, w, h, color, thickness=0.5):
        self.ctx.set_source_rgb(*color)
        self.ctx.set_line_width(thickness)
        self.ctx.rectangle(x, y, w, h)
        self.ctx.stroke()


# ── Page manager ──────────────────────────────────────────────────────────────

class PageManager:
    def __init__(self, surface: cairo.PDFSurface, title: str = ""):
        self.surface  = surface
        self.title    = title
        self.page_num = 1
        self._new_page()

    def _new_page(self):
        self.ctx   = cairo.Context(self.surface)
        self.pango = _PangoRenderer(self.ctx)
        self.y     = MARGIN_T
        self.ctx.set_source_rgb(1, 1, 1)
        self.ctx.paint()
        self._chrome()

    def _chrome(self):
        r = self.pango
        r.hrule(MARGIN_T - 12, color=C_ACCENT, thickness=0.7)
        r.text(self.title, _F["page"], MARGIN_L, MARGIN_T - 22, color=C_GREY)
        r.text(f"Page {self.page_num}", _F["page"],
               A4_W - MARGIN_R - 36, MARGIN_T - 22, color=C_GREY)
        r.hrule(A4_H - MARGIN_B + 10, color=C_ACCENT, thickness=0.7)
        r.text(
            f"PDF Malayalam Translator  ·  Cairo+Pango+HarfBuzz  ·  Font: {_MAL_FONT_FAMILY}",
            _F["footer"], MARGIN_L, A4_H - MARGIN_B + 14, color=C_GREY,
        )

    def ensure_space(self, needed: int):
        if self.y + needed > A4_H - MARGIN_B - 4:
            self.surface.show_page()
            self.page_num += 1
            self._new_page()

    def advance(self, px: int):
        self.y += px


# ── Table ─────────────────────────────────────────────────────────────────────

def _render_table(pm: PageManager, table_data: List[List[str]]):
    if not table_data:
        return
    col_count = max(len(row) for row in table_data)
    if col_count == 0:
        return
    col_w      = TEXT_W / col_count
    pad_v, pad_h = 6, 7
    cell_w     = col_w - 2 * pad_h

    def _measure(text, font_str):
        cr_ = _get_cairo_ptr(pm.ctx)
        layout = _libpc.pango_cairo_create_layout(cr_)
        if not layout:
            return 16
        fd = _libpango.pango_font_description_from_string(font_str.encode())
        _libpango.pango_layout_set_font_description(layout, fd)
        _libpango.pango_layout_set_text(layout, text.encode("utf-8"), -1)
        _libpango.pango_layout_set_width(layout, int(cell_w * PANGO_SCALE))
        _libpango.pango_layout_set_wrap(layout, PANGO_WRAP_WORD)
        w, h = ctypes.c_int(0), ctypes.c_int(0)
        _libpango.pango_layout_get_pixel_size(layout, ctypes.byref(w), ctypes.byref(h))
        _libgobj.g_object_unref(layout)
        _libpango.pango_font_description_free(fd)
        return h.value

    pm.ensure_space(40)
    pm.advance(8)

    for ri, row in enumerate(table_data):
        is_hdr = ri == 0
        font   = _F["table_h"] if is_hdr else _F["table"]
        bg     = C_TABLE_HDR   if is_hdr else (C_TABLE_ROW if ri % 2 else C_TABLE_ALT)
        fg     = C_WHITE        if is_hdr else C_BODY
        row_h  = max((_measure(str(c or ""), font) for c in row), default=14) + 2 * pad_v

        pm.ensure_space(row_h + 2)
        r = pm.pango
        r.rect_fill  (MARGIN_L, pm.y, TEXT_W, row_h, bg)
        r.rect_stroke(MARGIN_L, pm.y, TEXT_W, row_h, (0.78, 0.78, 0.84))

        for ci in range(1, col_count):
            xd = MARGIN_L + ci * col_w
            pm.ctx.set_source_rgb(0.78, 0.78, 0.84)
            pm.ctx.set_line_width(0.4)
            pm.ctx.move_to(xd, pm.y); pm.ctx.line_to(xd, pm.y + row_h)
            pm.ctx.stroke()

        for ci, cell in enumerate(row[:col_count]):
            r.text(str(cell or ""), font,
                   MARGIN_L + ci * col_w + pad_h, pm.y + pad_v,
                   max_width=cell_w, color=fg)
        pm.advance(row_h)

    pm.advance(12)


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_pdf(blocks, output_path, bilingual=False,
                 title="Malayalam Translation", progress_cb=None):
    """
    Render translated TextBlocks to a Malayalam PDF.
    blocks      — list of TextBlock with .translated populated
    output_path — destination .pdf
    bilingual   — show original English in grey above each block
    """
    output_path = str(output_path)
    surface = cairo.PDFSurface(output_path, A4_W, A4_H)
    surface.set_metadata(cairo.PDF_METADATA_TITLE, title)
    surface.set_metadata(cairo.PDF_METADATA_CREATOR, "PDF Malayalam Translator")

    pm    = PageManager(surface, title=title)
    total = len(blocks)

    for idx, block in enumerate(blocks):
        if progress_cb and idx % 10 == 0:
            progress_cb(idx, total, "rendering PDF")

        btype = block.block_type
        r     = pm.pango

        if btype == "page_break":
            if pm.y > MARGIN_T + 30:
                surface.show_page()
                pm.page_num += 1
                pm._new_page()
            continue

        mal = (block.translated or block.text).strip()
        eng = block.text.strip()
        if not mal:
            continue

        if btype == "table" and block.table_data:
            _render_table(pm, block.table_data)
            continue

        if btype == "heading1":
            pm.ensure_space(60); pm.advance(14)
            if bilingual and eng:
                pm.advance(r.text(eng, _F["english"], MARGIN_L, pm.y, TEXT_W, C_GREY) + 2)
            pm.advance(r.text(mal, _F["h1"], MARGIN_L, pm.y, TEXT_W, C_HEADING) + 5)
            r.hrule(pm.y, color=C_ACCENT, thickness=0.9); pm.advance(12)
            continue

        if btype == "heading2":
            pm.ensure_space(44); pm.advance(12)
            if bilingual and eng:
                pm.advance(r.text(eng, _F["english"], MARGIN_L, pm.y, TEXT_W, C_GREY) + 2)
            pm.advance(r.text(mal, _F["h2"], MARGIN_L, pm.y, TEXT_W, C_HEADING) + 9)
            continue

        if btype == "heading3":
            pm.ensure_space(32); pm.advance(9)
            if bilingual and eng:
                pm.advance(r.text(eng, _F["english"], MARGIN_L, pm.y, TEXT_W, C_GREY) + 2)
            pm.advance(r.text(mal, _F["h3"], MARGIN_L, pm.y, TEXT_W, C_HEADING) + 7)
            continue

        if btype == "list_item":
            if not re.match(r"^[•\-\*\d]", mal):
                mal = "• " + mal
            pm.ensure_space(22)
            if bilingual and eng:
                pm.advance(r.text(eng, _F["english"], MARGIN_L + 18, pm.y,
                                  TEXT_W - 18, C_GREY) + 1)
            pm.advance(r.text(mal, _F["body"], MARGIN_L + 18, pm.y,
                              TEXT_W - 18, C_BODY, line_spacing=2) + 6)
            continue

        # paragraph
        pm.ensure_space(22)
        if bilingual and eng:
            pm.advance(r.text(eng, _F["english"], MARGIN_L, pm.y, TEXT_W, C_GREY) + 2)
        pm.advance(r.text(mal, _F["body"], MARGIN_L, pm.y, TEXT_W, C_BODY,
                          align=PANGO_ALIGN_LEFT, line_spacing=3) + 9)

    surface.finish()
    return output_path
