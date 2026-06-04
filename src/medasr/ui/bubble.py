"""Floating bubble UI window — web-rendered glassmorphic 'liquid glass' overlay.

The overlay is a transparent QWebEngineView rendering ``assets/overlay.html``
(a CSS glass pill + a siriwave voice waveform). Rendering in the web layer gives
true anti-aliased rounded corners and a fluid, Apple-style waveform that plain
Qt 2D painting can't match. The public API (set_state / update_audio /
position_bottom_center) is unchanged so app.py needs no changes.
"""

import os
import logging
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QApplication
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView

logger = logging.getLogger(__name__)

_OVERLAY_HTML = os.path.join(os.path.dirname(__file__), "assets", "overlay.html")


class FloatingBubble(QWidget):
    """Floating glass overlay with a web-rendered siriwave waveform."""

    # Signals for thread-safe updates (audio arrives on a background thread).
    state_changed_signal = pyqtSignal(str)
    audio_received_signal = pyqtSignal(object)

    # Recording footprint of the overlay window. Larger than the visible pill:
    # the extra ~28px on every side is transparent margin that lets the pill's
    # drop shadow fade out fully instead of being clipped into a hard rectangle.
    _REC_W, _REC_H = 376, 124

    def __init__(self):
        super().__init__()
        self._state = "idle"
        self._loaded = False
        self._setup_window()
        self._setup_ui()

        # Connect signals
        self.state_changed_signal.connect(self._on_state_changed)
        self.audio_received_signal.connect(self._on_audio_received)

    def _setup_window(self):
        """Configure window flags for floating behavior."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # Don't show in taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(self._REC_W, self._REC_H)

    def _setup_ui(self):
        """Create the transparent web view and load the overlay page."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView(self)
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.view.setStyleSheet("background: transparent;")
        self.view.page().setBackgroundColor(QColor(Qt.GlobalColor.transparent))
        self.view.loadFinished.connect(self._on_load_finished)
        # Load immediately at startup so it's ready before the first recording.
        self.view.setUrl(QUrl.fromLocalFile(_OVERLAY_HTML))
        layout.addWidget(self.view)

    # -- web bridge ---------------------------------------------------------
    def _on_load_finished(self, ok: bool):
        self._loaded = bool(ok)
        if not ok:
            logger.warning("Overlay page failed to load: %s", _OVERLAY_HTML)
            return
        # Sync the page to whatever state we're already in.
        self._set_web_state(self._state)

    def _js(self, code: str):
        if self._loaded:
            self.view.page().runJavaScript(code)

    def _set_web_state(self, state: str):
        palette = state if state in ("recording", "processing") else "recording"
        self._js(f"window.setState && window.setState('{palette}');")

    # -- slots (run on the GUI thread) -------------------------------------
    def _on_state_changed(self, state: str):
        """Handle state change (thread-safe via signal)."""
        self._state = state

        if state == "recording":
            self._set_web_state("recording")
            self.position_bottom_center()
            if not self.isVisible():
                self.show()
        elif state == "processing":
            self._set_web_state("processing")
        else:
            # Idle: hide the overlay.
            self.hide()

    def _on_audio_received(self, audio_chunk):
        """Push an audio level into the waveform (thread-safe via signal)."""
        if self._state != "recording" or audio_chunk is None or len(audio_chunk) == 0:
            return
        samples = np.asarray(audio_chunk, dtype=np.float32)
        rms = float(np.sqrt(np.mean(samples ** 2)))
        level = min(1.0, rms * 8.0)
        self._js(f"window.setLevel && window.setLevel({level:.3f});")

    # -- public API (unchanged) --------------------------------------------
    def set_state(self, state: str):
        """Change bubble state: 'idle', 'recording', or 'processing'."""
        self.state_changed_signal.emit(state)

    def update_audio(self, audio_chunk):
        """Update waveform visualization with an audio chunk."""
        self.audio_received_signal.emit(audio_chunk)

    def position_bottom_center(self):
        """Position bubble at bottom-center of screen."""
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            x = (geom.width() - self.width()) // 2
            y = geom.height() - self.height() - 60  # 60px from bottom
            self.move(x, y)
