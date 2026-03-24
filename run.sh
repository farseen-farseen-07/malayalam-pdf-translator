#!/bin/bash
# Launcher for PDF Malayalam Translator
cd "$(dirname "$0")"
source venv/bin/activate

if [ "$1" = "ui" ] || [ -z "$1" ]; then
    echo "Opening web UI at http://localhost:8501"
    streamlit run app.py
else
    python3 translate_pdf.py "$@"
fi
