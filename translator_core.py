"""
translator_core.py
==================
Translation engine: Google Translate (free, no key) + MyMemory fallback.
All results are cached in ~/.pdf_translator_cache.json so re-running
the same document is instant and never hits the API again.
"""

import json
import hashlib
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

CACHE_FILE  = Path.home() / ".pdf_translator_cache.json"
BATCH_DELAY = 0.35   # seconds between API calls — stays well under rate limits


# ── Cache helpers ─────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _cache_key(text: str, src: str, tgt: str) -> str:
    return hashlib.md5(f"{src}:{tgt}:{text}".encode()).hexdigest()


# ── Translation backends ──────────────────────────────────────────────────────

def _google_free(text: str, src: str, tgt: str) -> str:
    """
    Google Translate via the unofficial gtx endpoint.
    No API key required. Free for personal use.
    """
    url = (
        "https://translate.googleapis.com/translate_a/single"
        f"?client=gtx&sl={src}&tl={tgt}&dt=t&q={urllib.parse.quote(text)}"
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return "".join(item[0] for item in data[0] if item[0])


def _mymemory(text: str, src: str, tgt: str) -> str:
    """MyMemory free translation API — 1 000 requests/day anonymous."""
    params = urllib.parse.urlencode({"q": text, "langpair": f"{src}|{tgt}"})
    url    = f"https://api.mymemory.translated.net/get?{params}"
    req    = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("responseStatus") == 200:
        return data["responseData"]["translatedText"]
    raise ValueError(f"MyMemory error: {data.get('responseDetails')}")


def _libretranslate(text: str, src: str, tgt: str,
                    host: str = "https://libretranslate.com") -> str:
    """LibreTranslate — self-hosted or public instance."""
    payload = json.dumps({"q": text, "source": src, "target": tgt,
                          "format": "text"}).encode()
    req = urllib.request.Request(
        f"{host}/translate", data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))["translatedText"]


# ── Main translate function ───────────────────────────────────────────────────

def translate_text(
    text:   str,
    src:    str  = "en",
    tgt:    str  = "ml",
    method: str  = "google",
    cache:  dict = None,
) -> str:
    """
    Translate *text* from *src* language to *tgt* language.

    method  : "google" | "mymemory" | "libretranslate" | "auto"
    cache   : pass a dict to share cache across calls; None loads from disk.
    Returns the translated string (original on failure).
    """
    if cache is None:
        cache = load_cache()

    text = text.strip()
    if not text:
        return text

    # Skip if already mostly Malayalam (U+0D00–U+0D7F)
    mal_ratio = sum(1 for c in text if "\u0D00" <= c <= "\u0D7F") / max(len(text), 1)
    if mal_ratio > 0.5:
        return text

    key = _cache_key(text, src, tgt)
    if key in cache:
        return cache[key]

    # Long text: chunk at sentence boundaries
    if len(text) > 4500:
        return _translate_long(text, src, tgt, method, cache)

    order = [method] if method != "auto" else ["google", "mymemory"]
    errors = []
    result = None

    for m in order:
        try:
            if m == "google":
                result = _google_free(text, src, tgt)
            elif m == "mymemory":
                result = _mymemory(text, src, tgt)
            elif m == "libretranslate":
                result = _libretranslate(text, src, tgt)
            if result:
                break
        except Exception as e:
            errors.append(f"{m}: {e}")
            time.sleep(0.5)

    if not result:
        print(f"  [WARN] Translation failed ({'; '.join(errors)})")
        return text   # return original — never lose content

    cache[key] = result
    return result


def _translate_long(text: str, src: str, tgt: str, method: str, cache: dict) -> str:
    """Split long text at sentence boundaries and join translated chunks."""
    import re
    sentences = re.split(r"(?<=[.!?।])\s+", text)
    parts, chunk = [], ""
    for sent in sentences:
        if len(chunk) + len(sent) < 4000:
            chunk += sent + " "
        else:
            if chunk:
                parts.append(translate_text(chunk.strip(), src, tgt, method, cache))
                time.sleep(BATCH_DELAY)
            chunk = sent + " "
    if chunk:
        parts.append(translate_text(chunk.strip(), src, tgt, method, cache))
    return " ".join(parts)
