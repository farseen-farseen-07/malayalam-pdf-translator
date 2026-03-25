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

# ── Page config — MUST be first Streamlit call ────────────────────────────────

st.set_page_config(
    page_title="Malayalam PDF Translator",
    page_icon="🌿",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── Renderer selection (after set_page_config) ───────────────────────────────

@st.cache_resource
def _get_renderer():
    try:
        from pdf_generator_pango import generate_pdf, _MAL_FONT_FAMILY
        return generate_pdf, f"Cairo · Pango · HarfBuzz  [{_MAL_FONT_FAMILY}]"
    except Exception:
        from pdf_generator import generate_pdf
        return generate_pdf, "ReportLab · FreeSans  (fallback)"


generate_pdf, RENDERER = _get_renderer()

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  /* ── Force light theme globally ── */
  html, body,
  [class*="css"],
  [data-testid="stAppViewContainer"],
  [data-testid="stAppViewBlockContainer"],
  [data-testid="block-container"],
  .main, .block-container {
    font-family: 'Inter', sans-serif !important;
    background-color: #ffffff !important;
    color: #1e293b !important;
  }

  /* ── Force all native Streamlit text to dark ── */
  p, span, div, label, li, td, th, h1, h2, h3, h4, h5, h6,
  .stMarkdown, .stMarkdown p, .stMarkdown span,
  .stSelectbox label, .stCheckbox label, .stCheckbox span,
  .stButton label, .stFileUploader label,
  [data-testid="stWidgetLabel"],
  [data-testid="stCaptionContainer"],
  [data-testid="stExpander"] summary,
  [data-testid="stExpander"] p {
    color: #1e293b !important;
  }

  /* caption / small text */
  .stCaption, [data-testid="stCaptionContainer"] p {
    color: #64748b !important;
  }

  /* ── Sidebar: force white background + dark text ── */
  [data-testid="stSidebar"],
  [data-testid="stSidebar"] > div {
    background-color: #f8fafc !important;
  }
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] span,
  [data-testid="stSidebar"] div,
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] h1,
  [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] h3,
  [data-testid="stSidebar"] .stMarkdown,
  [data-testid="stSidebar"] .stMarkdown p,
  [data-testid="stSidebar"] [data-testid="stWidgetLabel"],
  [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,
  [data-testid="stSidebar"] .stSelectbox label,
  [data-testid="stSidebar"] .stCheckbox label,
  [data-testid="stSidebar"] .stCheckbox span,
  [data-testid="stSidebar"] [data-testid="stExpander"] summary,
  [data-testid="stSidebar"] [data-testid="stExpander"] p {
    color: #1e293b !important;
  }
  [data-testid="stSidebar"] .stCaption,
  [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: #64748b !important;
  }

  /* selectbox dropdown text */
  [data-testid="stSelectbox"] div[data-baseweb="select"] span,
  [data-testid="stSelectbox"] div[data-baseweb="select"] div {
    color: #1e293b !important;
  }

  /* divider */
  [data-testid="stSidebar"] hr { border-color: #e2e8f0 !important; }

  /* ── Hide default Streamlit chrome ── */
  #MainMenu, footer, header { visibility: hidden; }

  /* scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: #f1f5f9; }
  ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }

  /* ── Hero ── */
  .hero {
    background: linear-gradient(135deg, #0f2027 0%, #1a3a4a 55%, #2c5364 100%);
    border-radius: 20px;
    padding: 44px 52px 40px;
    margin-bottom: 32px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(15,32,39,0.18);
  }
  .hero::after {
    content: "മ";
    position: absolute;
    right: 36px; bottom: -10px;
    font-size: 160px;
    opacity: 0.06;
    color: #fff;
    font-weight: 900;
    line-height: 1;
    pointer-events: none;
  }
  .hero-eyebrow {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #7dd3fc;
    margin-bottom: 10px;
  }
  .hero-title {
    font-size: 2.6rem;
    font-weight: 800;
    color: #fff;
    margin: 0 0 12px;
    letter-spacing: -0.5px;
    line-height: 1.15;
  }
  .hero-sub {
    font-size: 1rem;
    color: #bae6fd;
    margin: 0 0 24px;
    max-width: 520px;
    line-height: 1.65;
  }
  .hero-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 100px;
    padding: 6px 16px;
    font-size: 0.78rem;
    color: #e0f2fe;
  }

  /* ── Feature strip ── */
  .features {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-bottom: 32px;
  }
  .feat {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 16px 12px;
    text-align: center;
    transition: box-shadow .15s, transform .15s;
  }
  .feat:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.07); transform: translateY(-2px); }
  .feat-icon  { font-size: 1.6rem; margin-bottom: 8px; }
  .feat-name  { font-size: 0.78rem; font-weight: 700; color: #1e293b; }
  .feat-desc  { font-size: 0.7rem;  color: #64748b; margin-top: 3px; line-height: 1.4; }

  /* ── Section label ── */
  .section-label {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #94a3b8;
    margin-bottom: 8px;
  }

  /* ── Upload zone ── */
  .upload-zone {
    background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
    border: 2px dashed #7dd3fc;
    border-radius: 16px;
    padding: 24px 20px 20px;
    text-align: center;
    margin-bottom: 4px;
  }
  .upload-zone-icon { font-size: 2rem; margin-bottom: 6px; }
  .upload-zone-text { font-size: 0.92rem; color: #0369a1; font-weight: 500; }
  .upload-zone-sub  { font-size: 0.78rem; color: #7dd3fc; margin-top: 2px; }

  /* ── File pill ── */
  .file-pill {
    display: flex;
    align-items: center;
    gap: 10px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #3b82f6;
    border-radius: 10px;
    padding: 12px 16px;
    margin: 12px 0 18px;
    font-size: 0.9rem;
    color: #1e293b;
  }
  .file-pill-icon { font-size: 1.3rem; }
  .file-pill-name { font-weight: 600; flex: 1; }
  .file-pill-size { font-size: 0.8rem; color: #64748b; }

  /* ── Step tracker ── */
  .steps {
    display: flex;
    align-items: center;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 12px 20px;
    margin-bottom: 16px;
    gap: 8px;
  }
  .step-item {
    display: flex; align-items: center; gap: 7px;
    font-size: 0.82rem; font-weight: 500; color: #94a3b8;
  }
  .step-item.active { color: #2563eb; }
  .step-item.done   { color: #16a34a; }
  .step-dot {
    width: 22px; height: 22px; border-radius: 50%;
    border: 2px solid currentColor;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.7rem; font-weight: 800; flex-shrink: 0;
  }
  .step-dot.done-dot { background: #16a34a; border-color: #16a34a; color: #fff; }
  .step-line { flex: 1; height: 2px; background: #e2e8f0; border-radius: 2px; }
  .step-line.done-line { background: #86efac; }

  /* ── Progress label ── */
  .prog-label {
    background: #eff6ff;
    border-left: 3px solid #3b82f6;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 0.86rem;
    color: #1d4ed8;
    font-weight: 500;
    margin-bottom: 8px;
  }

  /* ── Success card ── */
  .success-card {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border: 1px solid #86efac;
    border-left: 5px solid #22c55e;
    border-radius: 16px;
    padding: 22px 24px;
    margin: 16px 0;
  }
  .success-title { font-size: 1.15rem; font-weight: 800; color: #14532d; margin-bottom: 10px; }
  .success-stats {
    display: flex; gap: 20px; flex-wrap: wrap;
  }
  .success-stat {
    display: flex; align-items: center; gap: 5px;
    font-size: 0.85rem; color: #166534; font-weight: 500;
  }

  /* ── Sidebar labels ── */
  .sb-title {
    font-size: 0.7rem; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: #94a3b8 !important; margin-bottom: 10px;
  }

  /* ── Info section ── */
  .info-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
    margin-top: 8px;
  }
  .info-card {
    background: #fff; border: 1px solid #e2e8f0;
    border-radius: 12px; padding: 16px;
  }
  .info-card h4 { font-size: 0.85rem; font-weight: 700; color: #1e293b; margin: 0 0 8px; }
  .info-card p, .info-card li {
    font-size: 0.8rem; color: #475569; line-height: 1.6; margin: 0;
  }
  .info-card ul { padding-left: 16px; margin: 0; }

  /* ── Footer ── */
  .footer {
    text-align: center;
    margin-top: 48px;
    padding: 18px 0 8px;
    border-top: 1px solid #e2e8f0;
    font-size: 0.78rem;
    color: #94a3b8;
  }
  .footer a { color: #60a5fa; text-decoration: none; }

  /* ── Responsive ── */
  @media (max-width: 640px) {
    .hero { padding: 28px 24px 24px; }
    .hero-title { font-size: 1.8rem; }
    .features { grid-template-columns: repeat(2, 1fr); }
    .info-grid { grid-template-columns: 1fr; }
  }
</style>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────

st.markdown(f"""
<div class="hero">
  <div class="hero-eyebrow">AI-Powered · Free · No Login Required</div>
  <div class="hero-title">🌿 Malayalam PDF<br>Translator</div>
  <div class="hero-sub">
    Upload any English PDF and get a complete, properly shaped Malayalam PDF —
    headings, tables, and layout preserved.
  </div>
  <div class="hero-pill">🖋️ {RENDERER}</div>
</div>
""", unsafe_allow_html=True)

# ── Feature strip ─────────────────────────────────────────────────────────────

st.markdown("""
<div class="features">
  <div class="feat">
    <div class="feat-icon">🔤</div>
    <div class="feat-name">Smart Translation</div>
    <div class="feat-desc">Google + MyMemory fallback</div>
  </div>
  <div class="feat">
    <div class="feat-icon">📐</div>
    <div class="feat-name">Layout Kept</div>
    <div class="feat-desc">Headings, tables & lists</div>
  </div>
  <div class="feat">
    <div class="feat-icon">⚡</div>
    <div class="feat-name">Cached</div>
    <div class="feat-desc">Re-runs are instant</div>
  </div>
  <div class="feat">
    <div class="feat-icon">📖</div>
    <div class="feat-name">Bilingual</div>
    <div class="feat-desc">EN + ML output</div>
  </div>
  <div class="feat">
    <div class="feat-icon">🔍</div>
    <div class="feat-name">OCR</div>
    <div class="feat-desc">Scanned PDFs too</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")

    st.markdown('<div class="sb-title">Translation Engine</div>', unsafe_allow_html=True)
    method = st.selectbox(
        "Engine",
        ["google", "mymemory", "auto"],
        index=0,
        label_visibility="collapsed",
        help="Google: fastest, best quality. MyMemory: good fallback (1 000 req/day). Auto: tries Google, falls back.",
    )

    st.markdown("---")
    st.markdown('<div class="sb-title">Output Options</div>', unsafe_allow_html=True)
    bilingual = st.checkbox(
        "Bilingual (EN + ML)",
        help="Show original English in grey above each Malayalam paragraph.",
    )
    use_ocr = st.checkbox(
        "OCR mode",
        help="For scanned or image-based PDFs. Requires tesseract-ocr on the system.",
    )
    use_cache = st.checkbox(
        "Use translation cache", value=True,
        help="Skip API calls for already-translated text. Instant on re-runs.",
    )

    st.markdown("---")
    st.markdown('<div class="sb-title">Maintenance</div>', unsafe_allow_html=True)
    if st.button("🗑️ Clear cache", use_container_width=True):
        cache_file = Path.home() / ".pdf_translator_cache.json"
        if cache_file.exists():
            cache_file.unlink()
            st.success("Cache cleared.")
        else:
            st.info("Cache is already empty.")

    st.markdown("---")
    with st.expander("🔤 Better fonts (free)"):
        st.caption(
            "Add **NotoSansMalayalam-Regular.ttf** or **Manjari-Regular.ttf** "
            "to the `fonts/` folder — picked up automatically on restart."
        )
        st.caption("Get them from **fonts.google.com** → search the name → Download family.")

    st.markdown(
        '<div style="margin-top:16px; font-size:0.72rem; color:#94a3b8; text-align:center;">'
        'Streamlit · Hugging Face Spaces</div>',
        unsafe_allow_html=True,
    )

# ── Upload ────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-label">Step 1 — Upload your PDF</div>', unsafe_allow_html=True)

st.markdown("""
<div class="upload-zone">
  <div class="upload-zone-icon">📂</div>
  <div class="upload-zone-text">Drop your English PDF here</div>
  <div class="upload-zone-sub">or click Browse below · PDF files only</div>
</div>
""", unsafe_allow_html=True)

uploaded = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")

if uploaded:
    kb = len(uploaded.getvalue()) // 1024
    st.markdown(
        f'<div class="file-pill">'
        f'<span class="file-pill-icon">📄</span>'
        f'<span class="file-pill-name">{uploaded.name}</span>'
        f'<span class="file-pill-size">{kb:,} KB</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-label">Step 2 — Choose action</div>', unsafe_allow_html=True)
    btn_col1, btn_col2 = st.columns([3, 1])
    with btn_col1:
        go = st.button("🔄 Translate to Malayalam", type="primary", use_container_width=True)
    with btn_col2:
        prev = st.button("👁 Preview", use_container_width=True)

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
                    f"[{b.block_type.upper()}]  {b.text[:300]}"
                    for b in trans[:25]
                )
                st.text_area(
                    f"First 25 of {len(trans)} text blocks",
                    preview, height=340,
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

            step_ui = st.empty()
            status  = st.empty()
            pbar    = st.progress(0)
            detail  = st.empty()
            t0      = time.time()

            def _steps(active):
                labels = ["Extract", "Translate", "Build PDF"]
                parts  = []
                for i, lbl in enumerate(labels):
                    n   = i + 1
                    done = n < active
                    act  = n == active
                    s_cls  = "done" if done else ("active" if act else "")
                    d_cls  = "done-dot" if done else ""
                    num    = "✓" if done else str(n)
                    parts.append(
                        f'<div class="step-item {s_cls}">'
                        f'  <div class="step-dot {d_cls}">{num}</div>'
                        f'  {lbl}'
                        f'</div>'
                    )
                    if i < len(labels) - 1:
                        line_cls = "done-line" if done else ""
                        parts.append(f'<div class="step-line {line_cls}"></div>')
                step_ui.markdown(
                    '<div class="steps">' + "".join(parts) + "</div>",
                    unsafe_allow_html=True,
                )

            try:
                # ── Step 1: Extract ──────────────────────────────────────────
                _steps(1)
                status.markdown(
                    '<div class="prog-label">📖 Extracting text from PDF…</div>',
                    unsafe_allow_html=True,
                )

                def _ext_cb(cur, tot, _lbl):
                    pbar.progress(int(cur / max(tot, 1) * 28))
                    detail.caption(f"Page {cur + 1} / {tot}")

                blocks = extract_pdf(inp, use_ocr=use_ocr, progress_cb=_ext_cb)
                trans  = get_translatable_blocks(blocks)
                pages  = max((b.page_num for b in blocks), default=1)
                pbar.progress(28)

                if not trans:
                    st.warning("⚠️ No text found. Try enabling OCR mode in the sidebar.")
                    st.stop()

                # ── Step 2: Translate ────────────────────────────────────────
                _steps(2)
                status.markdown(
                    f'<div class="prog-label">🔤 Translating {len(trans)} blocks via {method}…</div>',
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
                    detail.caption(f"Block {i + 1} / {len(all_texts)}  ·  {txt[:55]}…")
                    time.sleep(BATCH_DELAY)
                    if (i + 1) % 50 == 0 and use_cache:
                        save_cache(cache)

                if use_cache:
                    save_cache(cache)

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

                # ── Step 3: Generate ─────────────────────────────────────────
                _steps(3)
                status.markdown(
                    '<div class="prog-label">📝 Rendering Malayalam PDF…</div>',
                    unsafe_allow_html=True,
                )
                pbar.progress(88)
                generate_pdf(blocks, out, bilingual=bilingual,
                             title=f"Malayalam Translation – {inp.stem}")
                pbar.progress(100)
                detail.empty()
                _steps(4)

                elapsed = time.time() - t0
                sz      = out.stat().st_size // 1024
                status.empty()

                st.markdown(
                    f'<div class="success-card">'
                    f'  <div class="success-title">✅ Translation complete!</div>'
                    f'  <div class="success-stats">'
                    f'    <div class="success-stat">📄 {pages} pages</div>'
                    f'    <div class="success-stat">🔤 {len(trans)} blocks</div>'
                    f'    <div class="success-stat">⏱ {elapsed:.0f}s</div>'
                    f'    <div class="success-stat">💾 {sz:,} KB</div>'
                    f'  </div>'
                    f'</div>',
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

# ── Info cards ────────────────────────────────────────────────────────────────

st.markdown("---")

with st.expander("ℹ️ How to use  ·  Tips  ·  Engines"):
    st.markdown("""
**How to use**
1. Upload your English PDF above
2. Configure options in the sidebar (engine, bilingual, OCR)
3. Click **Translate to Malayalam**
4. Download when done

**Tips**
- Large PDFs (100+ pages) take 5–10 min — the 0.35s delay avoids rate limits
- Scanned PDF? Enable **OCR mode** in the sidebar
- Repeat run? Enable **cache** for instant results
- Better output? Add `NotoSansMalayalam-Regular.ttf` to the `fonts/` folder

**Translation engines**

| Engine | Key needed | Limit | Best for |
|--------|-----------|-------|----------|
| **Google** | None | ~5 000 req/hr | Default |
| **MyMemory** | None | 1 000 req/day | Fallback |
| **Auto** | None | combined | Best effort |

**OCR install (self-hosted):** `sudo apt-get install tesseract-ocr`
""")

# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="footer">
  Built with Streamlit &nbsp;·&nbsp;
  Hosted on <a href="https://huggingface.co/spaces" target="_blank">Hugging Face Spaces</a>
  &nbsp;·&nbsp; Malayalam shaped with HarfBuzz + Pango
</div>
""", unsafe_allow_html=True)
