"""EyeMate — a camera-based assistive companion for blind and low-vision users.

Fully offline.  High-contrast buttons + spoken output, with a voice loop on
Android (native SpeechRecognizer / TextToSpeech via PyJNIus).

  - Desktop: OpenCV webcam preview, SAPI voice, typed voice-command box.
  - Android: Camera4Kivy (CameraX) preview, native TTS/STT.
"""
from __future__ import annotations

import os
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.uix.widget import Widget

from services import barcode as barcode_svc
from services import ocr as ocr_svc
from services.color import dominant_color
from services.speech import STTEngine, TTSEngine, describe_color, describe_scene, help_text
from services.vision import Detector, YoloDetector, create_detector
from services.voice_commands import (
    INTENT_CLIPBOARD,
    INTENT_COLOR,
    INTENT_HELP,
    INTENT_IDENTIFY,
    INTENT_NAVIGATE,
    INTENT_OCR,
    INTENT_PASTE,
    INTENT_PRODUCT,
    INTENT_REPEAT,
    INTENT_SCENE,
    INTENT_SCREEN,
    INTENT_STOP,
    parse_command,
)
from theme import read_clipboard_text

try:  # pragma: no cover - android only
    import android  # noqa: F401

    IS_ANDROID = True
except ImportError:
    IS_ANDROID = False


def open_desktop_camera():
    """Best-effort OpenCV webcam.  Returns None when unavailable."""
    try:
        import cv2

        cap = cv2.VideoCapture(0)
        if cap is None or not cap.isOpened():
            return None
        return cap
    except Exception:
        return None


class CameraPreview(Widget):
    """Backs the camera area.

    Desktop: captures via OpenCV and draws frames to a texture.
    Android: hosts a Camera4Kivy Preview and stores analyzed frames.
    Both expose grab() for analysis actions.
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self.texture = None
        self.cap = None
        self._pv = None
        self._latest = None
        self._lock = threading.Lock()
        self._continuous = False
        self._desktop_running = False

    # ---- frame sharing (both platforms) ----
    def grab(self):
        with self._lock:
            return self._latest

    def _set_latest(self, frame):
        with self._lock:
            self._latest = frame

    # ---- lifecycle ----
    def start(self):
        if IS_ANDROID:
            self._start_android()
        else:
            self._start_desktop()

    def stop(self):
        self._desktop_running = False
        if IS_ANDROID:
            if self._pv is not None:
                try:
                    Clock.schedule_once(lambda dt: self._disconnect_android(), 0)
                except Exception:
                    pass
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    # ---- desktop ----
    def _start_desktop(self):
        self.cap = open_desktop_camera()
        if self.cap is None:
            self._announce_no_camera()
            return
        self._desktop_running = True
        threading.Thread(target=self._read_loop_desktop, daemon=True).start()
        Clock.schedule_interval(self._pump_texture, 1.0 / 20.0)
        Clock.schedule_interval(self._maybe_continuous, 4.0)

    def _announce_no_camera(self):
        app = App.get_running_app()
        if app is not None:
            Clock.schedule_once(lambda dt: app.say(
                "Camera is not available. Use the buttons to try each feature."), 1.0)

    def _read_loop_desktop(self):
        while self._desktop_running:
            ok, frame = self.cap.read()
            if not ok:
                continue
            self._set_latest(frame)

    def _pump_texture(self, dt):
        frame = self.grab()
        if frame is None:
            return
        try:
            import cv2

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            buf = rgb.tobytes()
            w, h = rgb.shape[1], rgb.shape[0]
            if self.texture is None or self.texture.size != (w, h):
                self.texture = Texture.create(size=(w, h), colorfmt="rgb", bufferfmt="ubyte")
                self.texture.flip_vertical()
            self.texture.blit_buffer(buf, colorfmt="rgb", bufferfmt="ubyte")
            self.canvas.clear()
            with self.canvas:
                from kivy.graphics import Rectangle

                Rectangle(pos=self.pos, size=self.size, texture=self.texture)
        except Exception:
            pass

    # ---- android ----
    def _start_android(self):  # pragma: no cover
        from camera4kivy import Preview

        self._pv = Preview(aspect_ratio="16:9")
        self._pv.analyze_imageproxy_callback = self._on_android_image
        self.add_widget(self._pv)
        Clock.schedule_once(lambda dt: self._connect_android(), 0.5)
        Clock.schedule_interval(self._maybe_continuous, 4.0)

    def _connect_android(self):  # pragma: no cover
        try:
            self._pv.connect_to_camera()
        except Exception as exc:
            print("[EyeMate] camera connect failed:", exc)

    def _disconnect_android(self):  # pragma: no cover
        try:
            self._pv.disconnect_camera()
        except Exception:
            pass

    def _on_android_image(self, image_proxy):  # pragma: no cover
        try:
            frame = image_proxy.to_ndarray(format="bgr")
            self._set_latest(frame)
        except Exception:
            pass

    # ---- continuous announce (both) ----
    def _maybe_continuous(self, dt):
        if not self._continuous:
            return
        app = App.get_running_app()
        if app is not None:
            try:
                app.act_scene()
            except Exception:
                pass

    def set_continuous(self, enabled):
        self._continuous = enabled


def _guarded(fn):
    """Serialize actions so inference never races with itself."""

    def wrapper(self, *a, **k):
        if self._busy.locked():
            return
        self._busy.acquire()
        try:
            fn(self, *a, **k)
        finally:
            self._busy.release()

    return wrapper


_KEYBINDINGS = {
    "1": "scene",
    "2": "read_screen",
    "3": "color",
    "4": "product",
    "5": "ocr",
    "6": "navigate",
    "7": "continuous",
    "8": "clipboard",
    "t": "paste_text",
    "h": "help",
    "?": "help",
    "s": "stop",
    "escape": "stop",
}


class EyeMateApp(App):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.title = "EyeMate"
        _icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
        if os.path.exists(_icon):
            self.icon = _icon
        self.preview = None
        self.detector = create_detector()
        self.tts = TTSEngine()
        self.stt = STTEngine()
        self._busy = threading.Lock()
        self._continuous = False
        self._listening = False
        self._last_spoken = ""

    def build(self):
        from kivy.core.window import Window
        from kivy.lang import Builder

        Window.title = "EyeMate"
        if not IS_ANDROID:
            # Phone-like window so the mobile layout renders on the desktop.
            Window.size = (420, 900)
            try:
                Window.minimum_width, Window.minimum_height = 360, 700
            except Exception:
                pass
        kv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.kv")
        root = Builder.load_file(kv_path)
        if not IS_ANDROID:
            Window.bind(on_key_down=self._on_key_down)
        return root

    def on_start(self):
        self.preview = self.root.ids.get("preview")
        if IS_ANDROID:
            # Voice-first: the typed-command row is hidden on the phone.
            row = self.root.ids.get("command_row")
            if row is not None:
                row.opacity = 0
                row.disabled = True
        Clock.schedule_once(self._welcome, 1.0)
        if self.preview is not None:
            self.preview.start()

    def _welcome(self, dt):
        self.say("Eye Mate. I keep your text readable. Say, what is in front, or use a button.")

    def on_stop(self):
        self._continuous = False
        self._listening = False
        if self.preview is not None:
            self.preview.stop()
        try:
            self.stt.stop()
        except Exception:
            pass
        self.tts.interrupt()

    # ---- speech helpers ----
    def say(self, text):
        if not text:
            return
        self._last_spoken = text
        self.tts.say(text)

    def _announce(self, text):
        self.say(text)
        self._set_status(text)

    def _set_status(self, text):
        label = self.root.ids.get("status")
        if label is not None and hasattr(label, "text"):
            label.text = text

    def grab(self):
        return self.preview.grab() if self.preview is not None else None

    # ---- actions ----
    @_guarded
    def act_scene(self):
        frame = self.grab()
        if frame is None:
            self._announce("Point the camera at something first.")
            return
        dets = self.detector.run(frame, score_threshold=0.4)
        self._announce(describe_scene(dets))

    @_guarded
    def act_color(self):
        frame = self.grab()
        if frame is None:
            self._announce("Point the camera at something first.")
            return
        props = dominant_color(frame)
        self._announce(describe_color(props))

    @_guarded
    def act_ocr(self):
        frame = self.grab()
        if frame is None:
            self._announce("Point the camera at some text first.")
            return
        result = ocr_svc.read_text_from_frame(frame)
        self._announce(result["text"])

    @_guarded
    def act_read_screen(self):
        """OCR the whole frame and open the text sheet with the result."""
        frame = self.grab()
        if frame is None:
            self._announce("Point the camera at a screen or document first.")
            return
        text = ocr_svc.read_text_from_frame(frame)["text"]
        self._open_text_sheet(text, "Screen Text")
        if not text:
            self.say("I could not read any text.")
        else:
            self.say("Here is the text I found.")

    def act_clipboard(self):
        """Read the system clipboard aloud and into the text sheet."""
        text = read_clipboard_text()
        self._open_text_sheet(text, "Clipboard")
        if not text:
            self.say("Your clipboard is empty.")
        else:
            self.say(text)

    def open_text_input_sheet(self):
        """Open an empty sheet for text the user types, pastes, or selects."""
        self._open_text_sheet("", "Your Text")

    def _open_text_sheet(self, text, title):
        from kivy.factory import Factory
        from kivy.core.clipboard import Clipboard

        popup = Factory.TextReaderPopup()
        popup.ids["text_view"].text = text
        popup.ids["sheet_title"].text = title
        self._sheet_popup = popup
        popup.open()

    def popup_speak(self, popup):
        text = popup.ids["text_view"].text or ""
        if not text.strip():
            self.say("There is no text to read.")
            return
        self.say(text)

    def popup_speak_selected(self, popup):
        text = popup.ids["text_view"].selection_text or ""
        if not text.strip():
            text = popup.ids["text_view"].text or ""
        if not text.strip():
            self.say("There is no text to read.")
            return
        self.say(text)

    def popup_copy(self, popup):
        from kivy.core.clipboard import Clipboard

        text = popup.ids["text_view"].text or ""
        if not text.strip():
            self.say("There is nothing to copy.")
            return
        Clipboard.copy(text)
        self.say("Copied to clipboard.")

    @_guarded
    def act_scanner(self):
        frame = self.grab()
        if frame is None:
            self._announce("Point the camera at a barcode or medicine label first.")
            return
        result = barcode_svc.decode_barcode(frame)
        if result["ok"]:
            self._announce(f"Found {result['type']}. {result['data'].lower()}")
        else:
            self._announce(barcode_svc.error_message())

    @_guarded
    def act_navigate(self):
        frame = self.grab()
        if frame is None:
            self._announce("Camera is not ready.")
            return
        dets = self.detector.run(frame, score_threshold=0.25)
        if not dets:
            self._announce("The path looks clear ahead.")
            return
        self._announce("Caution. " + describe_scene(dets))

    def act_help(self):
        self._announce(help_text())

    def act_repeat(self):
        if self._last_spoken:
            self.say(self._last_spoken)

    def act_stop(self):
        self._continuous = False
        self._listening = False
        if self.preview is not None:
            self.preview.set_continuous(False)
        try:
            self.stt.stop()
        except Exception:
            pass
        self.tts.interrupt()
        btn = self.root.ids.get("continuous")
        if btn is not None:
            btn.state = "normal"
        listen_btn = self.root.ids.get("listen")
        if listen_btn is not None:
            listen_btn.state = "normal"
        self._set_status("Paused.")

    # ---- toggles ----
    def toggle_continuous(self, state):
        self._continuous = state == "down"
        if self.preview is not None:
            self.preview.set_continuous(self._continuous)
        msg = "Continuous mode on. I will keep announcing." if self._continuous else "Continuous mode off."
        self.say(msg)
        self._set_status(msg)

    def toggle_listen(self, state):
        if not IS_ANDROID:
            # Desktop: submit whatever is typed in the command box.
            if state == "down":
                listen_btn = self.root.ids.get("listen")
                if listen_btn is not None:
                    listen_btn.state = "normal"
                self.submit_command_text()
            return
        if state == "down":  # pragma: no cover - android
            self._listening = True
            self.say("Listening.")
            self.stt.start(self._on_voice_result)
        else:  # pragma: no cover
            self._listening = False
            self.stt.stop()

    def submit_command_text(self):
        inp = self.root.ids.get("command_input")
        if inp is None:
            return
        text = inp.text.strip()
        inp.text = ""
        if text:
            self._handle_command(text)

    # ---- voice handling ----
    def _on_voice_result(self, transcript, error=None):
        def dispatch(dt):
            if not self._listening:
                return
            if error is not None:
                self.say("I could not hear you. Please try again.")
                self._relisten()
                return
            if transcript:
                self._handle_command(transcript)
                self._relisten()
            else:
                self.say("I did not catch that. Say help for options.")
                self._relisten()

        Clock.schedule_once(dispatch, 0)

    def _relisten(self):  # pragma: no cover - android
        if self._listening:
            try:
                self.stt.start(self._on_voice_result)
            except Exception:
                pass

    def _handle_command(self, text):
        intent = parse_command(text)
        if intent == INTENT_SCENE:
            self.act_scene()
        elif intent == INTENT_IDENTIFY:
            self.act_scene()
        elif intent == INTENT_OCR:
            self.act_ocr()
        elif intent == INTENT_SCREEN:
            self.act_read_screen()
        elif intent == INTENT_CLIPBOARD:
            self.act_clipboard()
        elif intent == INTENT_PASTE:
            self.open_text_input_sheet()
        elif intent == INTENT_COLOR:
            self.act_color()
        elif intent == INTENT_PRODUCT:
            self.act_scanner()
        elif intent == INTENT_NAVIGATE:
            self.act_navigate()
        elif intent == INTENT_HELP:
            self.act_help()
        elif intent == INTENT_REPEAT:
            self.act_repeat()
        elif intent == INTENT_STOP:
            self.act_stop()
        else:
            self.say("I did not understand. Say help, to hear what I can do.")

    # ---- keyboard (desktop) ----
    def _on_key_down(self, window, keycode, text, modifiers):
        if text and text.lower() in _KEYBINDINGS:
            self._run_command(_KEYBINDINGS[text.lower()])
            return True
        if keycode and keycode[0] == 27:  # escape
            self.act_stop()
            return True
        return False

    def _run_command(self, name):
        if name == "scene":
            self.act_scene()
        elif name == "color":
            self.act_color()
        elif name == "ocr":
            self.act_ocr()
        elif name == "product":
            self.act_scanner()
        elif name == "navigate":
            self.act_navigate()
        elif name == "read_screen":
            self.act_read_screen()
        elif name == "clipboard":
            self.act_clipboard()
        elif name == "paste_text":
            self.open_text_input_sheet()
        elif name == "help":
            self.act_help()
        elif name == "stop":
            self.act_stop()
        elif name == "continuous":
            btn = self.root.ids.get("continuous")
            if btn is not None:
                btn.state = "down" if btn.state == "normal" else "normal"


if __name__ == "__main__":
    EyeMateApp().run()