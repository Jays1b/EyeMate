"""OCR text reader for documents, signs, and labels.

Detection delegates to the platform provider (Android ML Kit text-recognition
or Tesseract on desktop), but text cleaning/summarization is pure and tested.
"""
from __future__ import annotations

import re
import unicodedata

STOP_BEGINNINGS = (
    "the ", "a ", "an ",
)


def clean_text(raw: str) -> str:
    """Normalize raw OCR blocks to a spoken-friendly single line.

    - Collapses whitespace/newlines
    - Fixes stray character-spacing like "D O C T O R"
    - Removes common junk (lonely punctuation, barcode digits)
    """
    if not raw:
        return ""
    text = unicodedata.normalize("NFKD", raw)
    # "A B C" -> "ABC"; join only for 1-char words (spaced-out text)
    spaced = re.findall(r"\b(?:[A-Za-z0-9] ){2,}[A-Za-z0-9]\b", text)
    for token in spaced:
        text = text.replace(token, token.replace(" ", ""))
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[^\w\s.,!?;:'()/-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Barcode-like digits of length 8-13
    text = re.sub(r"\b\d{8,13}\b", "", text)
    text = re.sub(r"\s+", " ", text).strip(" .,!?;:")
    return text.strip()


def read_text_from_frame(frame, lang: str = "eng") -> dict:
    """Read text from a camera frame.

    Uses pytesseract (with a system Tesseract binary) when available,
    otherwise returns a graceful guidance message.
    Returns {'ok': bool, 'text': str}.
    """
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        return {"ok": False, "text": "I could not read text on this device. "
                                     "Install the text reader, or try the scene detection."}
    try:
        text = pytesseract.image_to_string(Image.fromarray(frame), lang=lang)
    except Exception:
        return {"ok": False, "text": "The text reader is not ready. "
                                     "Make sure Tesseract is installed, then try again."}
    cleaned = clean_text(text)
    if not cleaned:
        return {"ok": False, "text": "I could not read any letters there."}
    return {"ok": True, "text": cleaned}


def summarize_medication(clean_lines: list[str], max_chars: int = 140) -> str:
    """Build a short 'label summary' suitable for speech.

    Prefers lines that look like medication info: contains digits/dose
    (mg, mg/ml, tab, tablet, take), names, warnings.
    """
    if not clean_lines:
        return ""
    preferred = []
    for line in clean_lines:
        low = line.lower()
        if any(k in low for k in ("mg", "tab", "tablet", "take", "eat", "before", "after", "daily", "warning", "do not")):
            preferred.append(line)
    candidates = preferred or [l for l in clean_lines if l]
    result = " ".join(candidates)
    if len(result) > max_chars:
        result = result[:max_chars].rsplit(" ", 1)[0] + "..."
    return clean_text(result)