import numpy as np

from services.barcode import decode_barcode


def test_qr_roundtrip():
    import cv2

    encoder = cv2.QRCodeEncoder.create()
    img = encoder.encode("Aspirin 81 mg")
    frame = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    result = decode_barcode(frame)
    assert result["ok"] is True
    assert result["data"] == "Aspirin 81 mg"


def test_qr_roundtrip_target_text():
    import cv2

    encoder = cv2.QRCodeEncoder.create()
    img = encoder.encode("IBUPROFEN 200 MG")
    frame = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    result = decode_barcode(frame)
    assert result["ok"] is True
    assert result["data"].upper() == "IBUPROFEN 200 MG"


def test_no_barcode_returns_not_ok():
    frame = np.full((200, 200, 3), 128, dtype=np.uint8)
    result = decode_barcode(frame)
    assert result["ok"] is False


def test_error_message_not_empty():
    from services.barcode import error_message
    assert error_message().strip()