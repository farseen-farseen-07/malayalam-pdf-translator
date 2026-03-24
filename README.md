---
title: PDF Malayalam Translator
emoji: 📄
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.41.0
app_file: app.py
pinned: false
license: mit
short_description: English PDF to Malayalam — free, no API key
---

# PDF Malayalam Translator

> **Live demo:** [huggingface.co/spaces/Farseen-Farseen/malayalam-pdf-translator](https://huggingface.co/spaces/Farseen-Farseen/malayalam-pdf-translator)

Translate any English PDF to Malayalam — preserving headings, paragraphs, lists,
and tables — with **correct Malayalam conjunct shaping** via Cairo + Pango + HarfBuzz.

```
English PDF  →  [Extract]  →  [Translate]  →  [Render]  →  Malayalam PDF
                pdfplumber    Google/MyMemory  Cairo+Pango+HarfBuzz
```

---

## Use Online (no install needed)

Visit the live app — drag-and-drop your PDF, click Translate, download:

**https://huggingface.co/spaces/Farseen-Farseen/malayalam-pdf-translator**

---

## Install CLI (from anywhere)

```bash
# Install directly from GitHub (Linux/macOS)
pip install git+https://github.com/farseen-farseen-07/malayalam-pdf-translator.git.git

# Then use the translate-pdf command
translate-pdf your_document.pdf
translate-pdf your_document.pdf --bilingual
translate-pdf your_document.pdf --method mymemory -o output.pdf
```

> **Note:** System libraries (Cairo, Pango) must be installed separately — see setup below.

---

## Local Development

### Quick Start (3 commands)

```bash
# 1. Clone and run setup (installs everything automatically)
git clone https://github.com/farseen-farseen-07/malayalam-pdf-translator.git.git
cd malayalam-pdf-translator
chmod +x setup.sh && ./setup.sh

# 2. Translate a PDF (CLI)
python translate_pdf.py your_document.pdf

# 3. Open the web UI
streamlit run app.py
```

### Manual Setup

#### Ubuntu / Debian / WSL2

```bash
sudo apt-get update && sudo apt-get install -y \
    libcairo2 libcairo2-dev \
    libpango-1.0-0 libpango1.0-dev \
    libpangocairo-1.0-0 \
    libgobject-2.0-0 \
    libharfbuzz0b \
    libfontconfig1 \
    fonts-freefont-ttf fonts-noto-core \
    python3-dev python3-pip

pip install pdfplumber pypdf reportlab pycairo streamlit
```

#### macOS

```bash
brew install cairo pango harfbuzz fontconfig pkg-config
pip install pdfplumber pypdf reportlab pycairo streamlit
```

#### Windows

Use **WSL2 (Ubuntu)** and follow the Ubuntu steps above.

---

## Usage

### Command line

```bash
# Basic — outputs <filename>_malayalam.pdf
python translate_pdf.py report.pdf

# Specify output path
python translate_pdf.py report.pdf -o report_ml.pdf

# Bilingual mode — English + Malayalam side by side
python translate_pdf.py report.pdf --bilingual

# Scanned PDF (image-only) — uses Tesseract OCR
python translate_pdf.py scanned.pdf --ocr

# Use MyMemory instead of Google (good fallback if rate-limited)
python translate_pdf.py report.pdf --method mymemory

# Disable cache (re-translate everything fresh)
python translate_pdf.py report.pdf --no-cache
```

### Web UI

```bash
streamlit run app.py
# Opens at http://localhost:8501
```

### All CLI Options

```
usage: translate_pdf.py [-h] [-o OUTPUT]
                        [--method {google,mymemory,libretranslate,auto}]
                        [--bilingual] [--ocr] [--no-cache] [--src LANG] [-v]
                        input

positional arguments:
  input          Input English PDF file

optional arguments:
  -o, --output   Output path  (default: <input>_malayalam.pdf)
  --method       Translation engine: google (default) | mymemory | libretranslate | auto
  --bilingual    Show original English above each Malayalam block
  --ocr          Force OCR (scanned / image-only PDFs)
  --no-cache     Disable translation cache
  --src LANG     Source language  (default: en)
  -v, --verbose  Show full error tracebacks
```

---

## Deploy Your Own Instance

### Option 1 — Hugging Face Spaces (recommended, free)

1. [Create a Hugging Face account](https://huggingface.co/join)
2. Go to **New Space** → choose **Streamlit** SDK
3. Under **Repository**, connect this GitHub repo
4. HF Spaces reads `packages.txt` and `requirements.txt` automatically
5. Your app is live at `huggingface.co/spaces/<your-username>/<space-name>`

**Auto-deploy on push** (optional): Add your HF token as a GitHub secret named `HF_TOKEN` — the included GitHub Action will push to HF Spaces on every commit to `main`.

### Option 2 — Render (free tier, Docker)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

1. Fork this repo on GitHub
2. Create a Render account → New Web Service → connect your fork
3. Set **Runtime** to Docker (uses the included `Dockerfile`)
4. Free tier sleeps after inactivity; it wakes automatically on the next request

---

## Getting Better Malayalam Fonts (free, 5 minutes)

The bundled **FreeSans** covers all Malayalam code points. For the best output:

| Priority | Font | Source |
|---|---|---|
| 1 | **Noto Sans Malayalam** | fonts.google.com → search "Noto Sans Malayalam" |
| 2 | **Manjari** | fonts.google.com → search "Manjari" |
| 3 | **Meera / Rachana** | smc.org.in/fonts |
| 4 | FreeSans *(bundled)* | — |

Copy any `.ttf` file into the `fonts/` folder — the app picks it up automatically. No config changes needed.

---

## How It Works

### 1. Extraction (`pdf_extractor.py`)
- Uses `pdfplumber` to read every word with font name, size, and position
- Groups words → lines (Y-coordinate) → paragraphs (vertical gap + style)
- Detects heading level from font-size ratio (18 pt / 10 pt base = H1)
- Extracts tables separately, cell by cell
- Falls back to Tesseract OCR for scanned PDFs

### 2. Translation (`translator_core.py`)
- Google Translate free endpoint — no API key, best quality
- MyMemory API — 1,000 req/day free fallback
- Results cached to `~/.pdf_translator_cache.json` (re-running same doc is instant)
- 350 ms delay between calls keeps you under rate limits
- Text > 4,500 chars is auto-chunked at sentence boundaries

### 3. Rendering (`pdf_generator_pango.py`)
- **Cairo** — vector PDF, crisp at any resolution
- **Pango** — Unicode layout, line wrapping, alignment
- **HarfBuzz** — OpenType shaping: conjuncts (ക്ക, ന്ത്യ), ligatures, correct glyph order
- Fontconfig registers `fonts/` so Pango finds any `.ttf`/`.otf` you add

---

## Translation Engines

| Engine | API Key | Free Limit | Notes |
|---|---|---|---|
| **Google** | None | ~5,000 req/hr per IP | Default; best accuracy |
| **MyMemory** | None | 1,000 req/day | Use `--method mymemory` |
| **LibreTranslate** | Optional | Unlimited (self-hosted) | `pip install libretranslate` |
| **Auto** | — | — | Tries Google, falls back to MyMemory |

---

## OCR for Scanned PDFs

```bash
# Install OCR dependencies
sudo apt-get install tesseract-ocr poppler-utils
pip install pytesseract pdf2image

# Translate a scanned PDF
python translate_pdf.py scanned.pdf --ocr
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `libcairo.so.2: cannot open` | `sudo apt-get install libcairo2` |
| `libpangocairo-1.0.so.0: cannot open` | `sudo apt-get install libpangocairo-1.0-0` |
| Malayalam shows as boxes | Add Noto Sans Malayalam to `fonts/` |
| `ModuleNotFoundError: pdfplumber` | `pip install pdfplumber pypdf` |
| No text extracted | Add `--ocr` — it's a scanned PDF |
| Translation fails / `[WARN]` | Rate-limited. Try `--method mymemory` |
| App won't start on Windows | Use WSL2 (Ubuntu) |

---

## Project Structure

```
├── app.py                  ← Streamlit web UI
├── translate_pdf.py        ← CLI entry point
├── pdf_extractor.py        ← PDF text + structure extraction
├── translator_core.py      ← Translation engines + cache
├── pdf_generator_pango.py  ← Cairo+Pango+HarfBuzz renderer (primary)
├── pdf_generator.py        ← ReportLab renderer (fallback)
├── fonts/                  ← Bundled fonts (drop better ones here)
├── packages.txt            ← System packages (for HF Spaces / Docker)
├── requirements.txt        ← Python dependencies
└── pyproject.toml          ← Installable package config
```

---

## License

MIT
