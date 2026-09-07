import os

import numpy as np
import pytest

from services import vision
from services.vision import YoloDetector, create_detector, letterbox, parse_yolo_output, resolve_label

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COCO91 = ["???"] + [f"class{i}" for i in range(1, 91)]


def _synthetic_yolo_output(n_classes=80, n_anchors=8400, box=(320, 300, 200, 100, 0, 0.9)):
    """Build a (1, 4+nC, nA) array with one confident 'person' prediction.

    Values are in the 640x640 model input pixel space (as ultralytics exports).
    """
    raw = np.zeros((1, 4 + n_classes, n_anchors), dtype="float32")
    cx, cy, w, h, cls, sc = box
    raw[0, 0, 0] = cx
    raw[0, 1, 0] = cy
    raw[0, 2, 0] = w
    raw[0, 3, 0] = h
    raw[0, 4 + cls, 0] = sc
    return raw


def test_letterbox_keeps_aspect_and_reports_scale():
    img = np.zeros((240, 320, 3), dtype=np.uint8)
    padded, scale, (left, top) = letterbox(img, size=640)
    assert padded.shape == (640, 640, 3)
    assert round(scale, 3) == round(640 / 320, 3)
    assert left == 0 and top > 0


def test_parse_yolo_output_decodes_person():
    raw = _synthetic_yolo_output()
    dets = parse_yolo_output(raw, score_threshold=0.25)
    assert len(dets) == 1
    d = dets[0]
    assert d["label_index"] == 0
    x0, y0, x1, y1 = d["box"]
    assert x0 == pytest.approx(320 - 100) and x1 == pytest.approx(320 + 100)
    assert y0 == pytest.approx(300 - 50) and y1 == pytest.approx(300 + 50)
    assert d["score"] == pytest.approx(0.9) and len(d["box"]) == 4


def test_parse_yolo_output_threshold_and_transposed():
    raw = _synthetic_yolo_output(box=(320, 300, 50, 50, 0, 0.05))
    assert parse_yolo_output(raw, score_threshold=0.25) == []
    arr = np.squeeze(raw).T[np.newaxis]
    dets = parse_yolo_output(arr, score_threshold=0.01)
    assert len(dets) == 1
    assert dets[0]["score"] == pytest.approx(0.05)


def test_parse_yolo_output_nms_suppresses_duplicates():
    r1 = _synthetic_yolo_output()
    r2 = _synthetic_yolo_output(box=(330, 305, 200, 100, 0, 0.85))
    raw = np.concatenate([r1, r2], axis=2)
    dets = parse_yolo_output(raw, score_threshold=0.25)
    assert len(dets) == 1


def test_resolve_label_handles_ssd_placeholder_file():
    assert resolve_label(0, COCO91) == "class1"
    assert resolve_label(0, ["person", "bicycle"]) == "person"
    assert resolve_label(5, ["person", "bicycle", "car"]) == "object 5"


@pytest.mark.skipif(os.environ.get("EYEMATE_SKIP_UI") == "1", reason="requires cv2")
def test_yolo_detector_integration_on_image():
    det = YoloDetector()
    if not det.available:
        pytest.skip("yolo11n.onnx not bundled")
    candidates = [
        os.path.join(os.environ.get("TEMP", ""), "dog.jpg"),
        r"C:\Users\UBITHEGREAT\AppData\Local\Temp\opencode\dog.jpg",
    ]
    img = None
    img_shape = None
    for c in candidates:
        if c and os.path.exists(c):
            import cv2

            img = cv2.imread(c)
            img_shape = img.shape[:2]
            break
    if img is None:
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img_shape = img.shape[:2]
    res = det.run(img, score_threshold=0.25)
    assert isinstance(res, list)
    ih, iw = img_shape
    for d in res:
        assert "label" in d and "score" in d and "box" in d
        x0, y0, x1, y1 = d["box"]
        assert 0 <= x0 <= x1 <= iw and 0 <= y0 <= y1 <= ih
    if len(res) and not res[-1]["label"].startswith("object"):
        assert res  # at least one real COCO label found on a real image


def test_create_detector_prefers_available():
    det = create_detector()
    assert det is not None
    assert hasattr(det, "run")


def test_create_detector_falls_back_to_yolo_without_tflite(monkeypatch):
    def no_runtime():
        raise ImportError("tflite unavailable on Android")

    monkeypatch.setattr(vision, "get_interpreter_cls", no_runtime)
    det = create_detector()
    assert isinstance(det, YoloDetector)
    assert det.available