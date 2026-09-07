"""On-device object / scene recognition.

Uses a TFLite (LiteRT) model at runtime.  The model file is loaded lazily so
the module imports cleanly without the model present (matters in unit tests and
on desktop development).

The heavy math is isolated in pure functions (NMS, detection filter) so they
are unit-testable.
"""
from __future__ import annotations

import os
import time

import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
DEFAULT_MODEL = os.path.join(MODEL_DIR, "ssd_mobilenet_v2.tflite")
DEFAULT_LABELS = os.path.join(MODEL_DIR, "coco_labels.txt")
DEFAULT_YOLO_ONNX = os.path.join(MODEL_DIR, "yolo11n.onnx")
_YOLO_INPUT_SIZE = 640

# COCO detector output names used by common SSD_MobileNet conversion.
_DETECTION_BOXES = "output_boxes"
_DETECTION_CLASSES = "output_classes"
_DETECTION_SCORES = "output_scores"
_NUM_DETECTIONS = "num_detections"


def load_labels(path: str) -> list[str]:
    """Load a one-per-line label file, lowercased, whitespace stripped.

    Handles common formats:
        "person"
        "1: person"          -> "person"
        "bicycle: foo"       -> "bicycle"  (non-numeric prefix wins)
    """
    labels = []
    if not os.path.exists(path):
        return labels
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                left, _, right = line.partition(":")
                left, right = left.strip(), right.strip()
                if left.isdigit():
                    line = right or left
                else:
                    line = left or right
            labels.append(line.lower())
    return labels


def filter_detections(boxes, scores, classes, score_threshold: float) -> list[dict]:
    """Numpy-safe conversion of raw model outputs into a clean list."""
    out = []
    for box, score, cls in zip(boxes, scores, classes):
        if score < score_threshold:
            continue
        ymin, xmin, ymax, xmax = [float(v) for v in box]
        out.append(
            {
                "label_index": int(cls),
                "score": float(score),
                "box": [xmin, ymin, xmax, ymax],
            }
        )
    return out


def iou(a: list, b: list) -> float:
    """Intersection-over-union of two [xmin, ymin, xmax, ymax] boxes (0..1)."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    a_area = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    b_area = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    union = a_area + b_area - inter
    if union <= 0:
        return 0.0
    return inter / union


def nms(detections: list[dict], iou_threshold: float = 0.45) -> list[dict]:
    """Non-max suppression over [xmin, ymin, xmax, ymax] boxes.

    Keeps highest score, drops overlapping boxes within the same label class.
    """
    kept = []
    remaining = sorted(detections, key=lambda d: d["score"], reverse=True)
    while remaining:
        best = remaining.pop(0)
        kept.append(best)
        remaining = [
            d
            for d in remaining
            if not (d["label_index"] == best["label_index"] and iou(best["box"], d["box"]) > iou_threshold)
        ]
    return kept


def letterbox(img, size: int = _YOLO_INPUT_SIZE, fill: int = 114):
    """Resize an image into a square canvas keeping the aspect ratio.

    Returns (padded, scale, offset) where:
      scale = downscale factor applied to the original image
      offset = (pad_left, pad_top) in padded-canvas pixels.
    """
    if img is None:
        raise ValueError("letterbox requires an image")
    h, w = img.shape[:2]
    r = min(size / h, size / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    resized = cv2.resize(img, (nw, nh))
    dh, dw = size - nh, size - nw
    top, bottom = dh // 2, dh - dh // 2
    left, right = dw // 2, dw - dw // 2
    padded = cv2.copyMakeBorder(resized, top, bottom, left, right,
                                cv2.BORDER_CONSTANT, value=(fill, fill, fill))
    return padded, r, (left, top)


def parse_yolo_output(raw, n_classes: int = 80,
                      score_threshold: float = 0.25) -> list[dict]:
    """Decode a YOLOv8/11 raw ONNX output into pixel-space detections.

    Ultralytics-exported models already predict box centres and extents in the
    model input's pixel space (e.g. 640x640), so values are used directly.
    Handles both (1, 4+nC, anchors) and transposed (anchors, 4+nC) layouts.
    """
    preds = np.squeeze(np.asarray(raw, dtype="float32"))
    if preds.ndim != 2:
        return []
    if preds.shape[0] == 4 + n_classes and preds.shape[1] > 4 + n_classes:
        preds = preds.T
    boxes, scores, classes = [], [], []
    for row in preds:
        cx, cy, w, h = row[0:4]
        class_scores = row[4:]
        cls = int(np.argmax(class_scores))
        sc = float(class_scores[cls])
        if sc < score_threshold:
            continue
        boxes.append([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])
        scores.append(sc)
        classes.append(cls)
    detections = [
        {"label_index": cls, "score": sc, "box": [x0, y0, x1, y1]}
        for (x0, y0, x1, y1), sc, cls in zip(boxes, scores, classes)
    ]
    return nms(detections)


def _unletterbox(box, scale: float, offset) -> list[float]:
    pad_left, pad_top = offset
    x0, y0, x1, y1 = box
    return [(x0 - pad_left) / scale, (y0 - pad_top) / scale,
            (x1 - pad_left) / scale, (y1 - pad_top) / scale]


def resolve_label(index: int, labels: list[str]) -> str:
    """Map a class index to a label, tolerating 1-based SSD placeholder files."""
    if 0 <= index < len(labels) and labels[index] not in ("", "???", "?", "unknown"):
        return labels[index]
    if index + 1 < len(labels) and labels[index + 1] not in ("", "???", "?", "unknown"):
        return labels[index + 1]
    return f"object {index}"


class YoloDetector:
    """OpenCV-DNN YOLOv8/11 (ONNX) detector.

    Preferable on Android, where the TFLite runtime has no pip wheel: the
    `opencv` python-for-android recipe includes the DNN module, so scene and
    navigation detection work fully on-device without any ML runtime.
    """

    def __init__(self, model_path: str | None = None, labels_path: str | None = None,
                 score_threshold: float = 0.30):
        self.model_path = model_path or DEFAULT_YOLO_ONNX
        self.labels_path = labels_path or DEFAULT_LABELS
        self.score_threshold = score_threshold
        self._labels = load_labels(self.labels_path)
        self._net = None
        self._last_error = None

    @property
    def available(self) -> bool:
        return os.path.exists(self.model_path) and cv2 is not None

    def _load(self):
        if self._net is not None:
            return
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        if cv2 is None:
            raise RuntimeError("OpenCV is not available.")
        try:
            self._net = cv2.dnn.readNetFromONNX(self.model_path)
        except Exception as exc:
            self._last_error = str(exc)
            raise RuntimeError(f"Could not load ONNX model: {exc}") from exc

    def run(self, frame_bgr: np.ndarray, score_threshold: float = 0.30) -> list[dict]:
        if frame_bgr is None or frame_bgr.size == 0:
            return []
        if not self.available:
            return []
        try:
            self._load()
        except Exception:
            return []
        ih, iw = frame_bgr.shape[:2]
        try:
            padded, scale, offset = letterbox(frame_bgr, _YOLO_INPUT_SIZE)
            blob = cv2.dnn.blobFromImage(padded, 1 / 255.0,
                                         (_YOLO_INPUT_SIZE, _YOLO_INPUT_SIZE),
                                         swapRB=True, crop=False)
            self._net.setInput(blob)
            outs = self._net.forward()
            raw = outs if isinstance(outs, np.ndarray) else outs[0]
            parsed = parse_yolo_output(raw, n_classes=80, score_threshold=score_threshold)
            result = []
            for d in parsed[:5]:
                d["box"] = _unletterbox(d["box"], scale, offset)
                d["label"] = resolve_label(d["label_index"], self._labels)
                d["spoken"] = f"{d['label']} with {int(d['score'] * 100)} percent confidence"
                result.append(d)
            return result
        except Exception as exc:  # pragma: no cover - depends on model
            self._last_error = str(exc)
            return []

    @property
    def last_error(self) -> str | None:
        return self._last_error


class Detector:
    """TFLite object detector with graceful degradation."""

    def __init__(self, model_path: str | None = None, labels_path: str | None = None):
        self.model_path = model_path or DEFAULT_MODEL
        self.labels_path = labels_path or DEFAULT_LABELS
        self._interpreter = None
        self._input_details = None
        self._output_details = None
        self._labels = load_labels(self.labels_path)
        self._last_error = None

    @property
    def available(self) -> bool:
        if not os.path.exists(self.model_path):
            return False
        try:
            get_interpreter_cls()
            return True
        except ImportError:
            return False

    def _load(self):
        if self._interpreter is not None:
            return
        try:
            Interpreter = get_interpreter_cls()
        except ImportError as exc:
            self._last_error = "LiteRT/TFLite runtime not installed. Install ai-edge-litert or tensorflow."
            raise RuntimeError(self._last_error) from exc
        if not os.path.exists(self.model_path):
            self._last_error = f"Model not found: {self.model_path}"
            raise FileNotFoundError(self._last_error)
        self._interpreter = Interpreter(model_path=self.model_path)
        self._interpreter.allocate_tensors()
        self._input_details = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()

    def run(self, frame_bgr: np.ndarray, score_threshold: float = 0.5) -> list[dict]:
        """Detect objects; returns list of {'label','bbox_label','score','box',...}.

        Returns [] silently if the model or runtime is unavailable, so callers
        can degrade gracefully to 'I could not detect anything.'
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return []
        try:
            self._load()
        except Exception:
            return []
        try:
            inp = self._interpreter.get_input_details()[0]
            dtype = inp["dtype"]
            shape = inp["shape"]
            ih, iw = shape[1], shape[2]
            resized = cv2.resize(frame_bgr, (iw, ih))
            if dtype == np.float32:
                resized = (resized.astype(np.float32) / 255.0)
            resized = np.expand_dims(resized, axis=0)
            self._interpreter.set_tensor(inp["index"], resized)
            self._interpreter.invoke()

            order = {}
            for det in self._output_details:
                name = det["name"]
                if "box" in name or "Box" in name:
                    order["boxes"] = det
                elif "class" in name or "Class" in name:
                    order["classes"] = det
                elif "score" in name or "Score" in name:
                    order["scores"] = det
                elif "num" in name or "Num" in name:
                    order["num"] = det

            if len(order) < 3:
                # Fall back to the conventional SSD-MobileNet output order:
                # [boxes(N x 4), classes(N), scores(N), num_detections(1)]
                outs = self._output_details
                order = {
                    "boxes": outs[0],
                    "classes": outs[1],
                    "scores": outs[2],
                    "num": outs[3] if len(outs) > 3 else None,
                }

            boxes = self._interpreter.get_tensor(order["boxes"]["index"])[0]
            classes = self._interpreter.get_tensor(order["classes"]["index"])[0]
            scores = self._interpreter.get_tensor(order["scores"]["index"])[0]
            num_det = order.get("num")
            num = int(self._interpreter.get_tensor(num_det["index"])[0]) if num_det is not None else int(len(scores))

            raw = filter_detections(boxes[:num], scores[:num], classes[:num], score_threshold)
            kept = nms(raw, iou_threshold=0.45)
            result = []
            for d in kept[:5]:
                d["label"] = resolve_label(d["label_index"], self._labels)
                d["spoken"] = f"{d['label']} with {int(d['score'] * 100)} percent confidence"
                result.append(d)
            return result
        except Exception as exc:  # pragma: no cover - depends on model
            self._last_error = str(exc)
            return []

    @property
    def last_error(self) -> str | None:
        return self._last_error


try:  # pragma: no cover
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

# Re-export time for callers
_time = time

# Lazy, overridable interpreter factory (tests stub this).
_INTERPRETER_CLS = None


def get_interpreter_cls():
    global _INTERPRETER_CLS
    if _INTERPRETER_CLS is not None:
        return _INTERPRETER_CLS
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        try:
            from tflite_runtime.interpreter import Interpreter
        except ImportError:
            from tensorflow.lite.python.interpreter import Interpreter  # type: ignore
    _INTERPRETER_CLS = Interpreter
    return _INTERPRETER_CLS


def create_detector():
    """Pick the best available detector for the current device.

    Desktop uses the TFLite (LiteRT) SSD model first, then falls back to the
    OpenCV-DNN YOLO model.  Android (no pip-installable TFLite wheel) uses the
    YOLO model through the OpenCV recipe — no extra ML runtime required.
    """
    try:
        get_interpreter_cls()
        tflite_detector = Detector()
        if tflite_detector.available:
            return tflite_detector
    except Exception:
        pass
    yolo = YoloDetector()
    if yolo.available:
        return yolo
    return Detector()