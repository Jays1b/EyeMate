"""Barcode / QR scanning for products.

Provider-agnostic: tries OpenCV QRCodeDetector first (available on desktop and
Android via opencv), and falls back to pyzbar when present.  Decoding logic is
wrapped so tests can round-trip generated QR codes.
"""
from __future__ import annotations

import numpy as np

try:  # pragma: no cover
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

PLAIN_ERROR = "Could not read a barcode. Try holding the phone still and closer to the label."
PRODUCT_SUFFIXES = ("mg", "ml", "tablet", "capsule", "drops", "ointment")


_QR_MIN_SIDE = 200
_QR_UPSCALE_SIDE = 400
_QR_QUIET_ZONE = 100


def _qrcode_decode(gray: np.ndarray) -> str | None:
    if cv2 is None:  # pragma: no cover
        return None
    h, w = gray.shape[:2]
    # Tiny generated/synthetic codes lack a quiet zone and fool the detector;
    # upscale + pad before decoding.
    if min(h, w) <= _QR_MIN_SIDE:
        scale = _QR_UPSCALE_SIDE / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        gray = cv2.copyMakeBorder(gray, _QR_QUIET_ZONE, _QR_QUIET_ZONE,
                                  _QR_QUIET_ZONE, _QR_QUIET_ZONE,
                                  cv2.BORDER_CONSTANT, value=255)
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(gray)
    if points is not None and len(points) > 3 and data:
        return data
    ok, decoded, _, _ = detector.detectAndDecodeMulti(gray)
    if ok and decoded:
        return decoded[0]
    return None


def _pyzbar_decode(gray: np.ndarray) -> str | None:
    try:  # pragma: no cover
        from pyzbar import pyzbar  # available on Android via buildozer
    except ImportError:
        return None
    results = pyzbar.decode(gray)
    if results:
        return results[0].data.decode("utf-8", errors="replace")
    return None


def decode_barcode(frame: np.ndarray) -> dict:
    """Return {'ok': bool, 'data': ...} decoding a 1D/2D barcode from a frame."""
    if cv2 is not None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        data = _qrcode_decode(gray)
        if data:
            return {"ok": True, "data": data, "type": "qrcode"}
        data = _pyzbar_decode(gray)
        if data:
            kind = "product" if any(data.lower().endswith(s) for s in PRODUCT_SUFFIXES) else "barcode"
            return {"ok": True, "data": data, "type": kind}
    return {"ok": False, "data": "", "type": "none"}


def error_message() -> str:
    return PLAIN_ERROR