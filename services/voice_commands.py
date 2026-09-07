"""Voice-command parsing.

Pure string logic so it can be unit-tested without audio hardware or a device.
"""
from __future__ import annotations

import re

INTENT_SCENE = "SCENE"
INTENT_OCR = "OCR"
INTENT_SCREEN = "SCREEN"
INTENT_CLIPBOARD = "CLIPBOARD"
INTENT_PASTE = "PASTE"
INTENT_COLOR = "COLOR"
INTENT_PRODUCT = "PRODUCT"
INTENT_NAVIGATE = "NAVIGATE"
INTENT_HELP = "HELP"
INTENT_STOP = "STOP"
INTENT_IDENTIFY = "IDENTIFY"
INTENT_REPEAT = "REPEAT"
INTENT_UNKNOWN = "UNKNOWN"

# Order matters: more specific phrases first.
_RULES = [
    (INTENT_PRODUCT, re.compile(r"\b(product|barcode|bar code|medication|medicine bottle)\b")),
    (INTENT_SCREEN, re.compile(r"\b(read\s+(the\s+)?(whole\s+)?screen|what does (the )?(whole )?screen say|screen\s+text|read\s+everything)\b")),
    (INTENT_CLIPBOARD, re.compile(r"\b(clipboard|read my (last )?copy|copy buffer|from clipboard)\b")),
    (INTENT_PASTE, re.compile(r"\b(paste text|enter text|type text|read my text|my own text|speak text)\b")),
    (INTENT_NAVIGATE, re.compile(r"\b(navigate|obstacle|walk |walking|guide me|cross the street|is there anything)\b")),
    (INTENT_OCR, re.compile(r"\b(read|ocr|text|label|bottle label|what does it say|sign|document)\b")),
    (INTENT_COLOR, re.compile(r"\b(color|colour|what.*shade|shade)\b")),
    (INTENT_SCENE, re.compile(r"\b(scene|what.*in front|what do you see|describe|what is around|surroundings)\b")),
    (INTENT_IDENTIFY, re.compile(r"\b(identify|what is this|what's this|name|object|thing)\b")),
    (INTENT_REPEAT, re.compile(r"\b(repeat|say again|again)\b")),
    (INTENT_HELP, re.compile(r"\b(help|assist|what can you do|options|menu)\b")),
    (INTENT_STOP, re.compile(r"\b(stop|pause|quit|exit|be quiet)\b")),
]


def parse_command(transcript: str) -> str:
    """Return the intent constant that best matches a transcript.

    Unknown/gibberish returns INTENT_UNKNOWN.  Matches are case-insensitive and
    whitespace-normalized.
    """
    if not transcript or not transcript.strip():
        return INTENT_UNKNOWN
    text = re.sub(r"\s+", " ", transcript).strip().lower()
    for intent, pattern in _RULES:
        if pattern.search(text):
            return intent
    return INTENT_UNKNOWN


def clean_spoken(text: str) -> str:
    """Normalize OCR / detection output into a pleasant spoken sentence."""
    if not text:
        return ""
    # ASCII-fold common punctuation to word spacing.
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*([,.!?;:])\s*", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip()