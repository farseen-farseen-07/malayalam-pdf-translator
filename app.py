"""
app.py  –  Streamlit Web UI for PDF Malayalam Translator
Run with:   streamlit run app.py
"""

import streamlit as st
import tempfile
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pdf_extractor   import extract_pdf, get_translatable_blocks
from translator_core import translate_text, load_cache, save_cache, BATCH_DELAY


# ── Renderer selection ────────────────────────────────────────────────────────

@st.cache_resource
def _get_renderer():
    try:
        from pdf_generator_pango import generate_pdf, _MAL_FONT_FAMILY
        return generate_pdf, f"Cairo + Pango + HarfBuzz  [{_MAL_FONT_FAMILY}]"
    except Exception:
        from pdf_generator import generate_pdf
        return generate_pdf, "ReportLab + FreeSans  (fallback)"


generate_pdf, RENDERER = _get_renderer()

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="PDF Malayalam Translator",
    page_icon="📄",
    layout="centered",
)

st.markdown("""
<style>
  .main-title   { font-size:2rem; font-weight:700; color:#1a1a2e; margin-bottom:.15rem }
  .subtitle     { color:#555; font-size:1.05rem; margin-bottom:1.6rem }
  .badge        { background:#e3f2fd; border-left:4px solid #1976d2;
                  padding:6px 14px; border-radius:4px; font-size:.88rem; margin-bottom:1rem }
  .stat-box     { background:#f4f6fa; border-radius:8px;
                  padding:9px 15px; margin:4px 0; font-size:.93rem }
  .ok-box       { background:#e8f5e9; border-left:4px solid #43a047;
                  padding:12px 16px; border-radius:4px; margin:10px 0 }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown('<div class="main-title">📄 PDF Malayalam Translator</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Upload an English PDF — get a complete, '
    'properly shaped Malayalam PDF</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="badge">🖋️ Renderer: <b>{RENDERER}</b>'
    " — Malayalam conjuncts shaped correctly via HarfBuzz</div>",
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Settings")

    method = st.selectbox(
        "Translation Engine",
        ["google", "mymemory", "auto"],
        index=0,
        help="Google: fastest, best quality. MyMemory: good free fallback (1000 req/day).",
    )
    bilingual = st.checkbox(
        "Bilingual mode (EN + ML)", value=False,
        help="Show original English in grey above each Malayalam block.",
    )
    use_ocr = st.checkbox(
        "OCR mode (scanned PDFs)", value=False,
        help="Enable for image-based PDFs. Requires tesseract-ocr to be installed.",
    )
    use_cache = st.checkbox(
        "Use translation cache", value=True,
        help="Cached results skip the API entirely on repeat runs.",
    )

    st.divider()
    st.markdown("**Better fonts (free)**")
    st.caption(
        "Drop `NotoSansMalayalam-Regular.ttf` & `-Bold.ttf` from Google Fonts "
        "into the `fonts/` folder — the tool picks them up automatically."
    )
    st.caption(
        "Or try **Manjari** (elegant serif-like) from fonts.google.com."
    )
    st.divider()
    st.markdown("**Cache**")
    if st.button("🗑 Clear translation cache"):
        cache_file = Path.home() / ".pdf_translator_cache.json"
        if cache_file.exists():
            cache_file.unlink()
            st.success("Cache cleared.")
        else:
            st.info("Cache is already empty.")

# ── Upload ────────────────────────────────────────────────────────────────────

uploaded = st.file_uploader("Upload English PDF", type=["pdf"])

if uploaded:
    kb = len(uploaded.getvalue()) // 1024
    st.markdown(
        f'<div class="stat-box">📎 <b>{uploaded.name}</b>  —  {kb:,} KB</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        go   = st.button("🔄 Translate to Malayalam", type="primary", use_container_width=True)
    with col2:
        prev = st.button("👁 Preview text", use_container_width=True)

    # ── Preview ───────────────────────────────────────────────────────────────
    if prev:
        with st.spinner("Extracting text…"):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name
            try:
                blks  = extract_pdf(tmp_path, use_ocr=use_ocr)
                trans = get_translatable_blocks(blks)
                preview = "\n\n".join(
                    f"[{b.block_type.upper()}] {b.text[:300]}"
                    for b in trans[:25]
                )
                st.text_area(
                    f"First 25 of {len(trans)} blocks extracted",
                    preview, height=320,
                )
            except Exception as e:
                st.error(f"Extraction error: {e}")
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    # ── Translate ─────────────────────────────────────────────────────────────
    if go:
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = Path(tmpdir) / uploaded.name
            with open(inp, "wb") as f:
                f.write(uploaded.getvalue())
            out = Path(tmpdir) / f"{inp.stem}_malayalam.pdf"

            status = st.empty()
            pbar   = st.progress(0)
            detail = st.empty()
            t0     = time.time()

            try:
                # Step 1 — Extract
                status.info("📖 Step 1/3 — Extracting text…")

                def _ext_cb(cur, tot, lbl):
                    pbar.progress(int(cur / max(tot, 1) * 28))
                    detail.caption(f"Page {cur+1}/{tot}")

                blocks = extract_pdf(inp, use_ocr=use_ocr, progress_cb=_ext_cb)
                trans  = get_translatable_blocks(blocks)
                pages  = max((b.page_num for b in blocks), default=1)
                pbar.progress(28)
                status.info(f"📖 Extracted {len(trans)} blocks from {pages} pages")

                if not trans:
                    st.warning("⚠️ No text found. Enable OCR for scanned PDFs.")
                    st.stop()

                # Step 2 — Translate
                status.info(f"🔤 Step 2/3 — Translating {len(trans)} blocks…")
                cache = load_cache() if use_cache else {}

                all_texts, block_text_idx, table_cell_map = [], {}, {}
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

                translated_all = []
                for i, txt in enumerate(all_texts):
                    t = translate_text(txt, "en", "ml", method, cache)
                    translated_all.append(t)
                    pbar.progress(28 + int((i + 1) / max(len(all_texts), 1) * 57))
                    detail.caption(f"Block {i+1}/{len(all_texts)}: {txt[:55]}…")
                    time.sleep(BATCH_DELAY)
                    if (i + 1) % 50 == 0 and use_cache:
                        save_cache(cache)

                if use_cache:
                    save_cache(cache)

                # Map back
                for bi, block in enumerate(blocks):
                    if block.block_type == "table" and bi in table_cell_map:
                        new_rows = [row[:] for row in block.table_data]
                        for r, c, ti in table_cell_map[bi]:
                            new_rows[r][c] = translated_all[ti]
                        block.table_data = new_rows
                        block.translated = "[TABLE]"
                    elif bi in block_text_idx:
                        block.translated = translated_all[block_text_idx[bi]]
                    else:
                        block.translated = block.text

                # Step 3 — Generate
                status.info("📝 Step 3/3 — Generating Malayalam PDF…")
                pbar.progress(88)
                generate_pdf(blocks, out, bilingual=bilingual,
                             title=f"Malayalam Translation – {inp.stem}")
                pbar.progress(100)
                detail.empty()

                elapsed = time.time() - t0
                sz      = out.stat().st_size // 1024
                status.empty()
                st.markdown(
                    f'<div class="ok-box">✅ <b>Done!</b>  '
                    f'{len(trans)} blocks · {pages} pages · '
                    f'{elapsed:.0f}s · {sz:,} KB</div>',
                    unsafe_allow_html=True,
                )
                with open(out, "rb") as f:
                    st.download_button(
                        "⬇️ Download Malayalam PDF",
                        f.read(),
                        file_name=out.name,
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True,
                    )

            except Exception as e:
                status.empty(); pbar.empty(); detail.empty()
                st.error(f"❌ {e}")
                with st.expander("Error details"):
                    import traceback
                    st.code(traceback.format_exc())

# ── Info expanders ────────────────────────────────────────────────────────────

with st.expander("ℹ️ Getting better Malayalam fonts (free, 5 minutes)"):
    st.markdown("""
**Noto Sans Malayalam** (recommended — Google's reference implementation)
1. Go to **fonts.google.com** → search `Noto Sans Malayalam`
2. Click **Download family** → unzip
3. Copy `NotoSansMalayalam-Regular.ttf` and `NotoSansMalayalam-Bold.ttf`
   into the `fonts/` folder inside this project
4. Restart the app — the new font is picked up automatically

**Manjari** (elegant, book-like style — also excellent)
- Same steps, search `Manjari` on Google Fonts

**Meera / Rachana** (traditional style — from smc.org.in)
- Download from **smc.org.in/fonts**, copy into `fonts/`

No config changes needed — the app always uses the best font it finds.
    """)

with st.expander("ℹ️ Translation engines & tips"):
    st.markdown("""
| Engine | API key | Limit | Best for |
|---|---|---|---|
| **Google** (default) | None | ~5 000 req/hr | Everyday use |
| **MyMemory** | None | 1 000 req/day | Fallback |
| **LibreTranslate** | Optional | Unlimited | Self-hosted |

**Cache** lives at `~/.pdf_translator_cache.json`.
Re-running the same document is instant — translations are never fetched twice.

**For 100+ page PDFs:** The 0.35 s delay keeps you safely under rate limits.
A 100-page document typically takes 5–10 minutes. Leave it running.

**For scanned PDFs:** Enable **OCR mode** and make sure `tesseract-ocr` is
installed:  `sudo apt-get install tesseract-ocr`
    """)
