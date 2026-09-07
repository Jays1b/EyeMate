"""EyeMate theme helpers — small pure-Python utilities for the liquid-glass UI.

Glass canvas styling lives in main.kv (where Kivy expects it).  This module
provides helpers that need runtime logic: gradient texture generation,
clipboard access, and color constants used by both Python and KV.
"""
from __future__ import annotations

from kivy.properties import ListProperty
from kivy.uix.widget import Widget

# ---------- palette (importable from .kv via #:import) ----------
BG_TOP = [0.06, 0.40, 0.78, 1.0]
BG_BOT = [0.05, 0.85, 0.70, 1.0]
GLASS = [1, 1, 1, 0.14]
GLASS_PRESSED = [1, 1, 1, 0.24]
BORDER = [1, 1, 1, 0.35]
HIGHLIGHT = [1, 1, 1, 0.42]
SHADOW = [0, 0, 0, 0.28]
ACCENT = [0.30, 0.92, 0.95, 1.0]
TEXT = [1, 1, 1, 1]
TEXT_DIM = [1, 1, 1, 0.72]
RED = [1.0, 0.30, 0.38, 1.0]
GREEN = [0.30, 0.92, 0.52, 1.0]
PILL_RADIUS = 28.0


def gradient_texture(top_color, bottom_color, height=512):
    """Return a vertical gradient Texture (uint8 RGB, fast GL upload)."""
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        return None
    top = [int(c * 255) for c in top_color[:3]]
    bot = [int(c * 255) for c in bottom_color[:3]]
    arr = np.zeros((height, 1, 3), dtype="uint8")
    for i in range(3):
        arr[:, 0, i] = np.linspace(top[i], bot[i], height).astype("uint8")
    from kivy.graphics.texture import Texture

    tex = Texture.create(size=(1, height), colorfmt="rgb", bufferfmt="ubyte")
    tex.blit_buffer(arr.tobytes(), colorfmt="rgb", bufferfmt="ubyte")
    return tex


class GradientBG(Widget):
    """Full-bleed vertical gradient background with cached texture."""

    top_color = ListProperty(BG_TOP)
    bottom_color = ListProperty(BG_BOT)
    _tex = None
    _key = None

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_a):
        key = (tuple(self.top_color), tuple(self.bottom_color), self.height)
        if key != self._key or self._tex is None:
            h = max(2, min(512, int(self.height)))
            self._tex = gradient_texture(self.top_color, self.bottom_color, h)
            self._key = key
        self.canvas.clear()
        if self._tex is not None:
            from kivy.graphics import Color, Rectangle

            with self.canvas:
                Color(1, 1, 1, 1)
                Rectangle(pos=self.pos, size=self.size, texture=self._tex)


def read_clipboard_text() -> str:
    """Best-effort clipboard text (desktop only)."""
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return text if text else ""
    except Exception:
        try:
            from kivy.core.clipboard import Clipboard

            return Clipboard.paste() or ""
        except Exception:
            return ""