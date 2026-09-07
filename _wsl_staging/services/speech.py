"""Speech output (TTS) and input (STT).

Cross-platform abstraction:

- Android: uses PyJNIus wrappers around TextToSpeech / SpeechRecognizer so the
  app is fully voice-first on the phone.
- Desktop: win32com SAPI voice for speaking (offline, no audio capture needed
  for a first pass).  STT on desktop returns "" and callers fall back to the
  touch interface.
"""
from __future__ import annotations

import threading

_INTENTS_HELP = (
    "I can help you. Say: what is in front, to hear about your surroundings. "
    "Say: read screen, to read all text visible on the screen. "
    "Say: read text, to read a document or label. "
    "Say: what color, to hear the color under the arrow. "
    "Say: scan product, to read a barcode or medicine label. "
    "Say: navigate, to check for obstacles ahead. "
    "Say: clipboard, to read text from your clipboard. "
    "Say: paste text, to read text you type or paste. "
    "Say: repeat, for me to say that again. "
    "Say: stop, to make me be quiet."
)

try:  # pragma: no cover - android only
    import android  # noqa: F401  (python-for-android marker module)

    _ON_ANDROID = True
except ImportError:
    _ON_ANDROID = False


class SpeechRecognizerListener:
    """Android-native speech recognition via PyJNIus (SpeechRecognizer).

    Only construct on Android; the PyJNIus import is guarded.  All callbacks
    arrive on a Java binder thread — wrap them with Clock.schedule_once before
    touching Kivy widgets.
    """

    def __init__(self, on_result, wake=False):
        self.on_result = on_result
        self._rec = None
        self._listener = None

    def start(self):
        if not _ON_ANDROID:  # pragma: no cover
            return
        from jnius import PythonJavaClass, autoclass, java_method

        SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")
        Intent = autoclass("android.content.Intent")
        RecognizerIntent = autoclass("android.speech.RecognizerIntent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")

        class _Listener(PythonJavaClass):
            __javainterfaces__ = ["android.speech.RecognitionListener"]
            __javacontext__ = "app"

            def __init__(self, outer):
                super().__init__()
                self._outer = outer

            @java_method("(I)V")
            def onReadyForSpeech(self, params):
                pass

            @java_method("()V")
            def onBeginningOfSpeech(self):
                pass

            @java_method("()V")
            def onEndOfSpeech(self):
                pass

            @java_method("(F)V")
            def onRmsChanged(self, rms):
                pass

            @java_method("([B)V")
            def onBufferReceived(self, buffer):
                pass

            @java_method("(I)V")
            def onError(self, error):
                cb = self._outer.on_result
                if cb:
                    cb(None, error)

            @java_method("(Landroid/os/Bundle;)V")
            def onResults(self, results):
                arr = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                text = None
                if arr is not None and arr.size():
                    text = arr.get(0)
                cb = self._outer.on_result
                if cb:
                    cb(text, None)

            @java_method("(Landroid/os/Bundle;)V")
            def onPartialResults(self, results):
                pass

            @java_method("(ILandroid/os/Bundle;)V")
            def onEvent(self, event_type, params):
                pass

        self._listener = _Listener(self)
        self._rec = SpeechRecognizer.createSpeechRecognizer(PythonActivity.mActivity)
        self._rec.setRecognitionListener(self._listener)
        intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, False)
        self._rec.startListening(intent)

    def stop(self):
        if self._rec is not None:
            try:
                self._rec.stopListening()
            except Exception:
                pass
            try:
                self._rec.destroy()
            except Exception:
                pass
            self._rec = None
        self._listener = None


class STTEngine:
    """Voice input used by the app.

    Android: native SpeechRecognizer in a one-shot loop (the app restarts
    listening after each result via its callback).  Desktop: no microphone
    capture — the app falls back to the typed-command box.
    """

    def __init__(self):
        self._listener = None
        self._callback = None
        self.on_android = _ON_ANDROID

    def start(self, callback) -> None:
        self._callback = callback
        if _ON_ANDROID:  # pragma: no cover
            self._listener = SpeechRecognizerListener(callback)
            self._listener.start()
        else:
            print("[stt] desktop: type a command instead")

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def listen(self, timeout_s: float = 5.0) -> str:
        return ""


class TTSEngine:
    """Speaks text aloud.  Singleton-friendly, thread-safe providing queue."""

    def __init__(self, platform: str = "auto"):
        self._platform = platform
        self._android = None
        self._sapi = None
        self._lock = threading.Lock()
        self._last_text = ""
        self._init_backend()

    def _init_backend(self):
        if self._platform == "auto" or self._platform == "android":
            try:
                import jnius  # noqa: F401
                from jnius import autoclass  # type: ignore

                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                self._activity = PythonActivity.mActivity
                TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
                self._android = True
                self._tts = TextToSpeech(self._activity)
                return
            except Exception:
                self._android = False
        if self._platform in ("auto", "desktop", "windows"):
            try:
                import win32com.client  # type: ignore

                self._sapi = win32com.client.Dispatch("SAPI.SpVoice")
                self._platform = "desktop"
            except Exception:
                self._platform = "none"

    def say(self, text: str) -> None:
        if not text:
            return
        text = str(text).strip()
        self._last_text = text
        try:
            if self._android:
                self._tts.speak(text, 0, None)  # QUEUE_ADD=1? use 1 to avoid drop
            elif self._sapi is not None:
                self._sapi.Speak(text, 1)  # SVSFlagsAsync so we don't block UI
            else:
                print(f"[speak] {text}")
        except Exception:
            print(f"[speak-fallback] {text}")

    def interrupt(self) -> None:
        try:
            if self._android:
                self._tts.stop()
            elif self._sapi is not None:
                self._sapi.Speak("", 2)  # SVSFPurgeBeforeSpeak
        except Exception:
            pass

    @property
    def last_text(self) -> str:
        return self._last_text


def help_text() -> str:
    """The command list spoken in HELP / first-run."""
    return _INTENTS_HELP


def describe_color(props: dict) -> str:
    """Turn a color dict into an utterance like 'You are pointing at a red item.'"""
    name = props.get("name", "unknown")
    return f"You are pointing at a {name} colored item."


def describe_detections(dets: list[dict]) -> str:
    """Short spoken summary of detector output."""
    if not dets:
        return "I could not identify any objects."
    top = dets[0]
    return f"I see a {top['label']}, with {int(top['score'] * 100)} percent confidence."


def describe_scene(dets: list[dict]) -> str:
    if not dets:
        return "I cannot see anything recognizable ahead."
    labels = [d["label"] for d in dets[:3]]
    unique = []
    for l in labels:
        if l not in unique:
            unique.append(l)
    if len(unique) == 1:
        return f"Ahead, I see {unique[0]}."
    return "Ahead, I see " + ", ".join(unique)