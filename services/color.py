"""Color identification for blind users.

Works entirely on pixel data (no camera/model needed), so it is pure and
unit-testable on synthetic images.
"""
from __future__ import annotations

import cv2
import numpy as np

# Hue boundaries (OpenCV Hue is 0..179).  OpenCV integer H keeps 2deg per unit
# for H in 0..179; we map using these edges in 0..179 space.
_HUE_BINS = [
    # (low, high, name)
    (0, 10, "red"),
    (156, 179, "red"),
    (11, 25, "orange"),
    (26, 34, "yellow"),
    (35, 85, "green"),
    (86, 130, "blue"),
    (131, 155, "purple"),
]

_BRIGHTNESS_CUT = 30  # v below this -> black
_SAT_CUT = 20         # s below this -> gray/white


def classify_hsv(h, s, v) -> str:
    """Return a human-readable color name for a single HSV pixel.

    h,s are in opencv native ranges (h 0..179, s 0..255), v 0..255.
    """
    if v < _BRIGHTNESS_CUT:
        return "black"
    if s < _SAT_CUT:
        if v > 200:
            return "white"
        if v > 60:
            return "gray"
        return "dark gray"
    for low, high, name in _HUE_BINS:
        if low <= h <= high:
            return name
    return "colored"


def dominant_color(bgr: np.ndarray) -> dict:
    """Return {'name': ..., 'hue': int, 'sat': int, 'val': int} for a BGR image.

    Sampling focuses on the center of the frame (the cross-hair region the user
    is pointing at).
    """
    frame = np.asarray(bgr)
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("expected a BGR image (H x W x 3)")

    h, w = frame.shape[:2]
    ch0 = int(h * 0.2)
    ch1 = int(h * 0.8)
    cw0 = int(w * 0.2)
    cw1 = int(w * 0.8)
    region = frame[ch0:ch1, cw0:cw1]

    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    h_flat = hsv[:, :, 0].astype(int)
    s_flat = hsv[:, :, 1].astype(int)
    v_flat = hsv[:, :, 2].astype(int)

    pixels = h_flat.shape[0] * h_flat.shape[1]
    if pixels == 0:
        return {"name": "unknown", "hue": 0, "sat": 0, "val": 0}

    dim_mask = (v_flat < _BRIGHTNESS_CUT) | (s_flat < _SAT_CUT)
    n_dim = int(np.count_nonzero(dim_mask))

    if n_dim / pixels > 0.6:
        v_mean = int(v_flat[dim_mask].mean()) if n_dim else 0
        s_mean = int(s_flat[dim_mask].mean()) if n_dim else 0
        if v_mean > 200:
            name = "white"
        elif v_mean < _BRIGHTNESS_CUT:
            name = "black"
        elif v_mean > 60:
            name = "gray"
        else:
            name = "dark gray"
        return {"name": name, "hue": 0, "sat": s_mean, "val": v_mean}

    chroma = h_flat[~dim_mask]
    sat = s_flat[~dim_mask]
    val = v_flat[~dim_mask]

    hue_mean = int(np.mean(chroma))
    sat_mean = int(np.mean(sat))
    val_mean = int(np.mean(val))
    name = classify_hsv(hue_mean, sat_mean, val_mean)
    return {"name": name, "hue": hue_mean, "sat": sat_mean, "val": val_mean}


def hsv_frame(h, s, v, size=20, separate_chroma=0):
    """Build a BGR numpy array of uniform HSV color (for tests).

    With separate_chroma truthy, the outer border stays gray while the center
    uses the requested hue, to test center-region focus.
    """
    hsv = np.zeros((size, size, 3), dtype=np.uint8)
    hsv[:, :, 0] = h
    hsv[:, :, 1] = s
    hsv[:, :, 2] = v
    if separate_chroma:
        border = size // 4
        hsv[:border] = (0, 0, 100)
        hsv[-border:] = (0, 0, 100)
        hsv[:, :border] = (0, 0, 100)
        hsv[:, -border:] = (0, 0, 100)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)