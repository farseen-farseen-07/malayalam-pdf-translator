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
    page_title="Malayalam PDF Translator",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  /* ── Global ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
  }

  /* ── Hide default Streamlit branding ── */
  #MainMenu { visibility: hidden; }
  footer    { visibility: hidden; }
  header    { visibility: hidden; }

  /* ── Hero banner ── */
  .hero {
    background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
    border-radius: 16px;
    padding: 40px 48px 36px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
  }
  .hero::before {
    content: "മ";
    position: absolute;
    right: 40px;
    top: 10px;
    font-size: 140px;
    opacity: 0.07;
    color: #fff;
    font-weight: 900;
    line-height: 1;
  }
  .hero-title {
    font-size: 2.4rem;
    font-weight: 700;
    color: #ffffff;
    margin: 0 0 8px 0;
    letter-spacing: -0.5px;
  }
  .hero-sub {
    font-size: 1.05rem;
    color: #a8d8ea;
    margin: 0 0 20px 0;
    max-width: 560px;
    line-height: 1.55;
  }
  .hero-badge {
    display: inline-block;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 20px;
    padding: 5px 14px;
    font-size: 0.8rem;
    color: #cfe8f3;
    backdrop-filter: blur(4px);
  }

  /* ── Feature cards ── */
  .cards-row {
    display: flex;
    gap: 14px;
    margin-bottom: 28px;
    flex-wrap: wrap;
  }
  .card {
    flex: 1;
    min-width: 150px;
    background: #f8faff;
    border: 1px solid #e2e8f4;
    border-radius: 12px;
    padding: 18px 16px;
    text-align: center;
  }
  .card-icon { font-size: 1.8rem; margin-bottom: 8px; }
  .card-label { font-size: 0.82rem; font-weight: 600; color: #374151; }
  .card-desc  { font-size: 0.75rem; color: #6b7280; margin-top: 4px; }

  /* ── Upload zone ── */
  .upload-hint {
    background: #f0f7ff;
    border: 2px dashed #93c5fd;
    border-radius: 12px;
    padding: 18px 20px;
    text-align: center;
    font-size: 0.9rem;
    color: #3b82f6;
    margin-bottom: 12px;
  }

  /* ── File stat ── */
  .stat-box {
    background: #f1f5f9;
    border-left: 4px solid #3b82f6;
    border-radius: 8px;
    padding: 11px 16px;
    margin: 8px 0 16px;
    font-size: 0.92rem;
    color: #1e293b;
  }

  /* ── Step indicator ── */
  .steps {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 18px;
  }
  .step {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.82rem;
    font-weight: 500;
    color: #94a3b8;
  }
  .step.active { color: #3b82f6; }
  .step.done   { color: #22c55e; }
  .step-num {
    width: 24px; height: 24px;
    border-radius: 50%;
    border: 2px solid currentColor;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem; font-weight: 700;
  }
  .step-sep { flex: 1; height: 2px; background: #e2e8f0; border-radius: 1px; }

  /* ── Progress labels ── */
  .prog-label {
    background: #eff6ff;
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 0.85rem;
    color: #1d4ed8;
    margin-bottom: 6px;
    border-left: 3px solid #3b82f6;
  }

  /* ── Success box ── */
  .ok-box {
    background: linear-gradient(135deg, #f0fdf4, #dcfce7);
    border: 1px solid #86efac;
    border-left: 4px solid #22c55e;
    border-radius: 12px;
    padding: 18px 20px;
    margin: 14px 0;
  }
  .ok-title { font-size: 1.1rem; font-weight: 700; color: #15803d; margin-bottom: 6px; }
  .ok-stats { font-size: 0.88rem; color: #166534; }

  /* ── Sidebar ── */
  .sidebar-section {
    background: #f8faff;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 14px;
  }
  .sidebar-title {
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #64748b;
    margin-bottom: 10px;
  }

  /* ── Footer ── */
  .footer {
    text-align: center;
    margin-top: 48px;
    padding: 20px;
    border-top: 1px solid #e2e8f0;
    font-size: 0.8rem;
    color: #94a3b8;
  }
  .footer a { color: #3b82f6; text-decoration: none; }
</style>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero">
  <div class="hero-title">🌿 Malayalam PDF Translator</div>
  <div class="hero-sub">
    Upload any English PDF and receive a beautifully rendered Malayalam PDF —
    with proper conjunct shaping, tables, headings, and page layout preserved.
  </div>
  <span class="hero-badge">🖋️ """ + RENDERER + """</span>
</div>
""", unsafe_allow_html=True)

# ── Feature cards ─────────────────────────────────────────────────────────────

st.markdown("""
<div class="cards-row">
  <div class="card">
    <div class="card-icon">🔤</div>
    <div class="card-label">Smart Translation</div>
    <div class="card-desc">Google Translate + MyMemory fallback</div>
  </div>
  <div class="card">
    <div class="card-icon">📐</div>
    <div class="card-label">Layout Preserved</div>
    <div class="card-desc">Headings, tables & lists intact</div>
  </div>
  <div class="card">
    <div class="card-icon">⚡</div>
    <div class="card-label">Smart Cache</div>
    <div class="card-desc">Repeat runs are instant</div>
  </div>
  <div class="card">
    <div class="card-icon">📖</div>
    <div class="card-label">Bilingual Mode</div>
    <div class="card-desc">EN + ML side-by-side output</div>
  </div>
  <div class="card">
    <div class="card-icon">🔍</div>
    <div class="card-label">OCR Support</div>
    <div class="card-desc">Works on scanned PDFs too</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")

    st.markdown('<div class="sidebar-title">Translation</div>', unsafe_allow_html=True)
    method = st.selectbox(
        "Engine",
        ["google", "mymemory", "auto"],
        index=0,
        help="Google: fastest, best quality. MyMemory: good free fallback (1 000 req/day). Auto: tries Google, falls back to MyMemory.",
    )

    st.markdown('<div class="sidebar-title" style="margin-top:14px">Output Options</div>', unsafe_allow_html=True)
    bilingual = st.checkbox(
        "Bilingual mode (EN + ML)", value=False,
        help="Show original English in grey above each Malayalam block.",
    )
    use_ocr = st.checkbox(
        "OCR mode (scanned PDFs)", value=False,
        help="Enable for image-based or scanned PDFs. Requires tesseract-ocr to be installed.",
    )
    use_cache = st.checkbox(
        "Use translation cache", value=True,
        help="Cached results skip the API entirely on repeat runs — much faster.",
    )

    st.divider()

    with st.expander("🔤 Better Malayalam Fonts"):
        st.caption(
            "Drop `NotoSansMalayalam-Regular.ttf` & `-Bold.ttf` from Google Fonts "
            "into the `fonts/` folder — picked up automatically on restart."
        )
        st.caption("Or try **Manjari** (elegant, book-like) from fonts.google.com.")

    st.divider()

    st.markdown('<div class="sidebar-title">Cache</div>', unsafe_allow_html=True)
    if st.button("🗑️ Clear cache", use_container_width=True):
        cache_file = Path.home() / ".pdf_translator_cache.json"
        if cache_file.exists():
            cache_file.unlink()
            st.success("Cache cleared.")
        else:
            st.info("Cache is already empty.")

    st.divider()
    st.caption("Built with Streamlit · Deployed on Hugging Face Spaces")

# ── Main content ──────────────────────────────────────────────────────────────

main_col, info_col = st.columns([3, 1], gap="large")

with main_col:
    st.markdown('<div class="upload-hint">📂 Drop your English PDF here or click to browse</div>',
                unsafe_allow_html=True)
    uploaded = st.file_uploader("", type=["pdf"], label_visibility="collapsed")

    if uploaded:
        kb = len(uploaded.getvalue()) // 1024
        pages_hint = f"{kb:,} KB"
        st.markdown(
            f'<div class="stat-box">📎 <b>{uploaded.name}</b> &nbsp;·&nbsp; {pages_hint}</div>',
            unsafe_allow_html=True,
        )

        btn_col1, btn_col2 = st.columns([2, 1])
        with btn_col1:
            go = st.button("🔄 Translate to Malayalam", type="primary", use_container_width=True)
        with btn_col2:
            prev = st.button("👁 Preview text", use_container_width=True)

        # ── Preview ───────────────────────────────────────────────────────────
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

        # ── Translate ─────────────────────────────────────────────────────────
        if go:
            with tempfile.TemporaryDirectory() as tmpdir:
                inp = Path(tmpdir) / uploaded.name
                with open(inp, "wb") as f:
                    f.write(uploaded.getvalue())
                out = Path(tmpdir) / f"{inp.stem}_malayalam.pdf"

                # Step indicator
                step_ui = st.empty()
                status  = st.empty()
                pbar    = st.progress(0)
                detail  = st.empty()
                t0      = time.time()

                def _steps(active):
                    icons = ["📖 Extract", "🔤 Translate", "📝 Generate PDF"]
                    parts = []
                    for i, label in enumerate(icons):
                        n = i + 1
                        if n < active:
                            cls = "done"
                            num = "✓"
                        elif n == active:
                            cls = "active"
                            num = str(n)
                        else:
                            cls = ""
                            num = str(n)
                        parts.append(
                            f'<div class="step {cls}"><div class="step-num">{num}</div>{label}</div>'
                        )
                        if i < len(icons) - 1:
                            parts.append('<div class="step-sep"></div>')
                    step_ui.markdown(
                        '<div class="steps">' + "".join(parts) + "</div>",
                        unsafe_allow_html=True,
                    )

                try:
                    # Step 1 — Extract
                    _steps(1)
                    status.markdown('<div class="prog-label">📖 Step 1 / 3 — Extracting text…</div>',
                                    unsafe_allow_html=True)

                    def _ext_cb(cur, tot, lbl):
                        pbar.progress(int(cur / max(tot, 1) * 28))
                        detail.caption(f"Page {cur+1} / {tot}")

                    blocks = extract_pdf(inp, use_ocr=use_ocr, progress_cb=_ext_cb)
                    trans  = get_translatable_blocks(blocks)
                    pages  = max((b.page_num for b in blocks), default=1)
                    pbar.progress(28)

                    if not trans:
                        st.warning("⚠️ No text found. Enable OCR mode for scanned PDFs.")
                        st.stop()

                    # Step 2 — Translate
                    _steps(2)
                    status.markdown(
                        f'<div class="prog-label">🔤 Step 2 / 3 — Translating {len(trans)} blocks via {method}…</div>',
                        unsafe_allow_html=True,
                    )
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
                        detail.caption(f"Block {i+1} / {len(all_texts)}: {txt[:60]}…")
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
                    _steps(3)
                    status.markdown('<div class="prog-label">📝 Step 3 / 3 — Rendering Malayalam PDF…</div>',
                                    unsafe_allow_html=True)
                    pbar.progress(88)
                    generate_pdf(blocks, out, bilingual=bilingual,
                                 title=f"Malayalam Translation – {inp.stem}")
                    pbar.progress(100)
                    detail.empty()
                    _steps(4)  # all done

                    elapsed = time.time() - t0
                    sz      = out.stat().st_size // 1024
                    status.empty()
                    st.markdown(
                        f'<div class="ok-box">'
                        f'<div class="ok-title">✅ Translation Complete!</div>'
                        f'<div class="ok-stats">'
                        f'📄 {pages} pages &nbsp;·&nbsp; 🔤 {len(trans)} blocks &nbsp;·&nbsp; '
                        f'⏱ {elapsed:.0f}s &nbsp;·&nbsp; 💾 {sz:,} KB'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
                    with open(out, "rb") as f:
                        st.download_button(
                            "⬇️  Download Malayalam PDF",
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

with info_col:
    st.markdown("### How it works")
    st.markdown("""
**1. Upload** your English PDF

**2. Configure** options in the sidebar (engine, bilingual, OCR)

**3. Translate** — watch live progress

**4. Download** the Malayalam PDF
""")
    st.divider()
    st.markdown("### Tips")
    st.markdown("""
- **Large PDFs** (100+ pages) take 5–10 min due to rate limits
- **Scanned PDFs?** Enable OCR mode in settings
- **Re-running** the same PDF? Use cache — it's instant
- **Better fonts?** Drop a `.ttf` into the `fonts/` folder
""")
    st.divider()
    st.markdown("### Engines")
    st.markdown("""
| Engine | Limit |
|--------|-------|
| Google | ~5k/hr |
| MyMemory | 1k/day |
| Auto | auto-fallback |
""")

# ── Info expanders ────────────────────────────────────────────────────────────

st.divider()
exp1, exp2 = st.columns(2)

with exp1:
    with st.expander("🔤 Getting better Malayalam fonts (free, 5 min)"):
        st.markdown("""
**Noto Sans Malayalam** (recommended)
1. Go to **fonts.google.com** → search `Noto Sans Malayalam`
2. Click **Download family** → unzip
3. Copy `NotoSansMalayalam-Regular.ttf` and `-Bold.ttf` into `fonts/`
4. Restart the app — new font is auto-detected

**Manjari** (elegant, book-like)
- Same steps, search `Manjari` on Google Fonts

**Meera / Rachana** (traditional)
- Download from **smc.org.in/fonts**, copy into `fonts/`

No config changes needed.
""")

with exp2:
    with st.expander("ℹ️ Translation engines & rate limits"):
        st.markdown("""
| Engine | API key | Limit | Best for |
|--------|---------|-------|----------|
| **Google** (default) | None | ~5 000 req/hr | Everyday use |
| **MyMemory** | None | 1 000 req/day | Fallback |
| **Auto** | None | Combined | Best effort |

**Cache** lives at `~/.pdf_translator_cache.json`.
Re-running the same document is instant.

**For 100+ page PDFs:** The 0.35 s delay keeps you safely under rate limits.

**OCR install:** `sudo apt-get install tesseract-ocr`
""")

# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="footer">
  Built with ❤️ using Streamlit &nbsp;·&nbsp;
  Deployed on <a href="https://huggingface.co/spaces" target="_blank">Hugging Face Spaces</a> &nbsp;·&nbsp;
  Malayalam shaped via HarfBuzz + Pango
</div>
""", unsafe_allow_html=True)
