#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh  —  PDF Malayalam Translator  (macOS + Linux)
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       PDF Malayalam Translator — Setup Script                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── Detect OS ─────────────────────────────────────────────────────────────────
OS="$(uname -s)"
echo "Detected OS: $OS"

# ── Python version check ──────────────────────────────────────────────────────
python3 -c "
import sys
if sys.version_info < (3, 8):
    print('ERROR: Python 3.8+ required. You have', sys.version)
    sys.exit(1)
print('✓  Python', sys.version.split()[0])
"

# ─────────────────────────────────────────────────────────────────────────────
# macOS
# ─────────────────────────────────────────────────────────────────────────────
if [ "$OS" = "Darwin" ]; then
    echo ""
    echo "macOS detected — using Homebrew for system libraries."
    echo ""

    # Install Homebrew if missing
    if ! command -v brew &>/dev/null; then
        echo "Homebrew not found. Installing Homebrew…"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        # Add brew to PATH for Apple Silicon
        if [ -f /opt/homebrew/bin/brew ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
    fi
    echo "✓  Homebrew $(brew --version | head -1)"

    echo ""
    echo "Installing system libraries (cairo, pango, harfbuzz, fontconfig)…"
    brew install cairo pango harfbuzz fontconfig pkg-config 2>/dev/null || \
    brew upgrade cairo pango harfbuzz fontconfig pkg-config 2>/dev/null || true
    echo "✓  System libraries installed"

    echo ""
    echo "Installing Python packages…"
    # On macOS with Python 3.12+ pip may refuse without --break-system-packages
    # Try pip3 normally first, then with the flag
    pip3 install --upgrade pip -q 2>/dev/null || true
    pip3 install pdfplumber pypdf reportlab pycairo streamlit -q \
        || pip3 install pdfplumber pypdf reportlab pycairo streamlit -q \
                --break-system-packages
    echo "✓  Python packages installed"

# ─────────────────────────────────────────────────────────────────────────────
# Linux (Debian / Ubuntu / Mint / WSL2)
# ─────────────────────────────────────────────────────────────────────────────
elif [ "$OS" = "Linux" ]; then
    echo ""
    echo "Linux detected — using apt-get."
    echo ""

    echo "Installing system libraries (requires sudo)…"
    sudo apt-get update -qq
    sudo apt-get install -y \
        libcairo2 libcairo2-dev \
        libpango-1.0-0 libpango1.0-dev \
        libpangocairo-1.0-0 \
        libgobject-2.0-0 \
        libharfbuzz0b libharfbuzz-dev \
        libfontconfig1 libfontconfig1-dev \
        python3-dev python3-pip \
        fonts-freefont-ttf \
        2>/dev/null || true
    echo "✓  System libraries installed"

    echo ""
    echo "Installing Python packages…"
    pip3 install --upgrade pip -q 2>/dev/null || true
    pip3 install pdfplumber pypdf reportlab pycairo streamlit -q \
        || pip3 install pdfplumber pypdf reportlab pycairo streamlit -q \
                --break-system-packages
    echo "✓  Python packages installed"

else
    echo ""
    echo "⚠  Unrecognised OS: $OS"
    echo "   Please install Cairo, Pango, HarfBuzz manually, then:"
    echo "   pip3 install pdfplumber pypdf reportlab pycairo streamlit"
    exit 1
fi

# ── Optional OCR ──────────────────────────────────────────────────────────────
echo ""
read -p "Install OCR support for scanned PDFs? (y/N): " ocr_choice
if [[ "$ocr_choice" =~ ^[Yy] ]]; then
    if [ "$OS" = "Darwin" ]; then
        brew install tesseract poppler 2>/dev/null || true
    else
        sudo apt-get install -y tesseract-ocr poppler-utils -q 2>/dev/null || true
    fi
    pip3 install pytesseract pdf2image -q \
        || pip3 install pytesseract pdf2image -q --break-system-packages
    echo "✓  OCR support installed"
fi

# ── Verify bundled fonts ───────────────────────────────────────────────────────
echo ""
if [ -f "fonts/FreeSans.ttf" ]; then
    echo "✓  Bundled fonts found in fonts/"
else
    echo "⚠  fonts/ directory not found next to setup.sh."
    echo "   Make sure you extracted the full zip and run setup.sh from inside it."
fi

# ── Smoke test ────────────────────────────────────────────────────────────────
echo ""
echo "Running smoke test…"
python3 - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else '.')

errors = []

# Test 1: core imports
try:
    import pdfplumber, pypdf, reportlab
    print("  ✓  Core imports OK (pdfplumber, pypdf, reportlab)")
except ImportError as e:
    errors.append(f"Core import failed: {e}")

# Test 2: Cairo + Pango
try:
    import cairo, ctypes
    ctypes.CDLL("libpangocairo-1.0.so.0" if sys.platform != "darwin" else
                next(p for p in [
                    "/opt/homebrew/lib/libpangocairo-1.0.dylib",
                    "/usr/local/lib/libpangocairo-1.0.dylib",
                ] if os.path.exists(p)))
    print("  ✓  Cairo + Pango available — high-quality renderer will be used")
except Exception as e:
    print(f"  ⚠  Cairo/Pango not available ({e})")
    print("     ReportLab fallback renderer will be used instead")

# Test 3: PDF generation
try:
    from pdf_generator_pango import generate_pdf, _MAL_FONT_FAMILY
    from pdf_extractor import TextBlock
    import tempfile
    blocks = [
        TextBlock("Test Heading", "heading1", translated="ഇന്ത്യൻ ഭരണഘടന"),
        TextBlock("Hello world.", "paragraph", translated="നമസ്കാരം ലോകം."),
    ]
    out = tempfile.mktemp(suffix=".pdf")
    generate_pdf(blocks, out, title="Smoke Test")
    sz = os.path.getsize(out) // 1024
    os.unlink(out)
    print(f"  ✓  PDF generation OK ({sz} KB, font: {_MAL_FONT_FAMILY})")
except Exception as e:
    try:
        from pdf_generator import generate_pdf
        from pdf_extractor import TextBlock
        import tempfile
        blocks = [TextBlock("Test", "heading1", translated="ഇന്ത്യൻ ഭരണഘടന")]
        out = tempfile.mktemp(suffix=".pdf")
        generate_pdf(blocks, out, title="Smoke Test")
        os.unlink(out)
        print(f"  ✓  PDF generation OK (ReportLab fallback)")
    except Exception as e2:
        errors.append(f"PDF generation failed: {e2}")

if errors:
    print("\n  ✗  Some tests failed:")
    for err in errors:
        print(f"     {err}")
    sys.exit(1)
else:
    print("\n  All smoke tests passed!")
PYEOF

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅  Setup complete!                                         ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  CLI:     python3 translate_pdf.py your_document.pdf        ║"
echo "║                                                              ║"
echo "║  Bilingual mode:                                            ║"
echo "║           python3 translate_pdf.py doc.pdf --bilingual      ║"
echo "║                                                              ║"
echo "║  Web UI:  streamlit run app.py                              ║"
echo "║           (opens at http://localhost:8501)                  ║"
echo "║                                                              ║"
echo "║  Better fonts: drop NotoSansMalayalam-Regular.ttf          ║"
echo "║  into the fonts/ folder (from fonts.google.com)            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
