"""Main application controller with state machine."""

import gc
import logging
import sys
import threading
from enum import Enum, auto
from typing import Optional

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QEvent, QCoreApplication

from .config import config
from .audio.capture import AudioCapture
# Import transcription model
from .transcription.parakeet_model import transcriber as parakeet_transcriber
from .input.hotkeys import HotkeyListener
from .input.typer import type_text
from .ui.bubble import FloatingBubble
from .ui.tray import SystemTray
from .history.storage import HistoryStorage
from .vocabulary.manager import VocabularyManager
from .postprocessing.formatter import formatter as text_formatter

logger = logging.getLogger(__name__)


class AppState(Enum):
    """Application states."""
    IDLE = auto()
    RECORDING = auto()
    PROCESSING = auto()


class OpenSettingsEvent(QEvent):
    """Custom event for opening settings window."""
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self):
        super().__init__(OpenSettingsEvent.EVENT_TYPE)


class MedASRAppEventHandler(QObject):
    """Event handler for the main app to receive custom events."""

    def __init__(self, app):
        super().__init__()
        self.app = app

    def event(self, event):
        if event.type() == OpenSettingsEvent.EVENT_TYPE:
            logger.info("Received OpenSettingsEvent, calling _do_open_settings...")
            self.app._do_open_settings()
            return True
        return super().event(event)


class MedASRApp:
    """Main application controller."""

    def __init__(self):
        self.state = AppState.IDLE
        self._lock = threading.Lock()

        # Enable OpenGL context sharing for QtWebEngine (must precede QApplication)
        from PyQt6.QtCore import Qt
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

        # Initialize Qt application
        self.qt_app = QApplication(sys.argv)

        # Event handler for custom events
        self.event_handler = MedASRAppEventHandler(self)

        # Model management
        self.models = {
            'parakeet_tdt': parakeet_transcriber,
        }
        # Prefer config selection; fall back to Parakeet.
        configured_model = config.get('transcription.model', 'parakeet_tdt')
        if configured_model not in self.models:
            logger.warning(f"Unknown configured model '{configured_model}', defaulting to Parakeet")
            configured_model = 'parakeet_tdt'
            config.set('transcription.model', configured_model)
            config.save()

        self.current_model = configured_model
        self.transcriber = self.models[self.current_model]

        # Components
        self.audio = AudioCapture(
            sample_rate=config.get('audio.sample_rate', 16000),
            channels=config.get('audio.channels', 1),
            chunk_size=config.get('audio.chunk_size', 1024),
            on_audio=self._on_audio_chunk
        )

        self.hotkeys = HotkeyListener(
            on_activate=self._on_hotkey_activate,
            on_deactivate=self._on_hotkey_deactivate,
            on_cancel=self._on_hotkey_cancel
        )

        self.bubble: Optional[FloatingBubble] = None
        self.tray: Optional[SystemTray] = None

        # Initialize vocabulary manager
        self.vocabulary_manager = VocabularyManager()

        # Initialize history storage
        self.history_storage = HistoryStorage()

        # Initialize text formatter (lazy loaded when enabled)
        self.formatter = text_formatter

        # Settings window (created lazily on first open)
        self.settings_window = None

        # Initialize transcriber in background
        self._init_transcriber_async()

        # Initialize formatter if enabled in config
        if config.get('formatting.enabled', False):
            self._init_formatter_async()

    def _init_transcriber_async(self):
        """Initialize current transcriber in background thread."""
        def init():
            try:
                logger.info("Loading Parakeet-TDT model...")
                model_name = config.get('transcription.parakeet_model', 'nemo-parakeet-tdt-0.6b-v2')
                device = config.get('transcription.device', 'cpu')
                self.transcriber.model_name = model_name
                self.transcriber.device = device
                self.transcriber.initialize()
                logger.info("Parakeet-TDT ready! You can now use Ctrl+Win to dictate.")
            except Exception as e:
                logger.error(f"Failed to initialize transcriber: {e}")
                logger.error("If using GPU, ensure onnxruntime-gpu is installed and CUDA is available.")

        thread = threading.Thread(target=init, daemon=True)
        thread.start()

    def _init_formatter_async(self):
        """Initialize text formatter in background thread."""
        def init():
            try:
                logger.info("Loading text formatter model...")
                self.formatter.initialize()
                logger.info("Text formatter ready!")
            except Exception as e:
                logger.error(f"Failed to initialize formatter: {e}")

        thread = threading.Thread(target=init, daemon=True)
        thread.start()

    def switch_model(self, model_name: str):
        """
        Switch between transcription models.

        Args:
            model_name: Model key (e.g., 'parakeet_tdt')
        """
        with self._lock:
            if self.state != AppState.IDLE:
                logger.warning("Cannot switch models while recording/processing")
                return

            if model_name == self.current_model:
                logger.info(f"Already using {model_name} model")
                return

            if model_name not in self.models:
                logger.error(f"Unknown model: {model_name}")
                return

            # Unload the previous model to free memory
            old_model = self.transcriber
            old_model_name = self.current_model

            logger.info(f"Switching from {old_model_name} to {model_name}...")

            # Persist choice
            config.set('transcription.model', model_name)
            config.save()

            # Unload old model if it was initialized
            if old_model.is_initialized():
                logger.info(f"Unloading {old_model_name} model to free memory...")
                old_model.unload()

                # Force garbage collection and clear GPU memory
                gc.collect()

            self.current_model = model_name
            self.transcriber = self.models[model_name]

            # Initialize new model if not already initialized
            if not self.transcriber.is_initialized():
                self._init_transcriber_async()
            else:
                logger.info(f"{model_name} model ready!")

    def switch_device(self, device: str):
        """Switch between CPU and CUDA for transcription."""
        with self._lock:
            if self.state != AppState.IDLE:
                logger.warning("Cannot switch device while recording/processing")
                return

            current_device = config.get('transcription.device', 'cpu')
            if device == current_device:
                logger.info(f"Already using {device}")
                return

            logger.info(f"Switching transcription device from {current_device} to {device}...")

            # Save to config
            config.set('transcription.device', device)
            config.save()

            # Unload current model and reinitialize with new device
            if self.transcriber.is_initialized():
                self.transcriber.unload()

                gc.collect()

            self._init_transcriber_async()

    def _on_audio_chunk(self, chunk):
        """Handle audio chunk from capture."""
        if self.state == AppState.RECORDING and self.bubble:
            self.bubble.update_audio(chunk)

    def _on_hotkey_activate(self):
        """Handle Ctrl+Win press."""
        with self._lock:
            if self.state != AppState.IDLE:
                return

            # Check if model is ready
            if not self.transcriber.is_initialized():
                logger.warning("Model still loading, please wait...")
                return

            logger.info("Starting recording...")
            self.state = AppState.RECORDING

            # Start recording
            self.audio.start_recording()

            # Show bubble
            if self.bubble:
                self.bubble.set_state("recording")

    def _on_hotkey_deactivate(self):
        """Handle Ctrl+Win release."""
        with self._lock:
            if self.state != AppState.RECORDING:
                return

            logger.info("Stopping recording...")
            self.state = AppState.PROCESSING

            # Show processing state
            if self.bubble:
                self.bubble.set_state("processing")

            # Stop recording and transcribe in background
            audio_data = self.audio.stop_recording()
            threading.Thread(
                target=self._transcribe_and_type,
                args=(audio_data,),
                daemon=True
            ).start()

    def _on_hotkey_cancel(self):
        """Handle Escape press."""
        with self._lock:
            if self.state != AppState.RECORDING:
                return

            logger.info("Cancelling recording...")

            # Stop recording
            self.audio.stop_recording()

            # Hide bubble
            if self.bubble:
                self.bubble.set_state("idle")

            self.state = AppState.IDLE

    def _transcribe_and_type(self, audio_data):
        """Transcribe audio and type result."""
        try:
            duration = len(audio_data) / config.get('audio.sample_rate', 16000)
            logger.info(f"Transcribing {duration:.1f}s of audio...")

            if duration < 0.3:
                logger.info("Audio too short, skipping")
                return

            # Check if transcriber is initialized
            if not self.transcriber.is_initialized():
                logger.error("Model not ready yet - please wait for initialization to complete")
                return

            # Get hotwords from vocabulary
            hotwords = self.vocabulary_manager.get_hotwords_string()

            # Transcribe
            text = self.transcriber.transcribe(
                audio_data,
                sample_rate=config.get('audio.sample_rate', 16000),
                hotwords=hotwords,
            )

            if text:
                # Format text if enabled
                if config.get('formatting.enabled', False) and self.formatter.is_initialized():
                    fix_typos = config.get('formatting.fix_typos', False)
                    logger.info(f"Formatting text (fix_typos={fix_typos})...")
                    formatted_text = self.formatter.format_text(text, fix_typos=fix_typos)
                    if formatted_text != text:
                        logger.info(f"Formatted: '{text[:30]}...' -> '{formatted_text[:30]}...'")
                        text = formatted_text

                # Save to history (save formatted text)
                self.history_storage.add(
                    text=text,
                    model=self.current_model,
                    duration=duration
                )

                # Enter the text at cursor
                input_method = config.get('input.method', 'paste')
                logger.info(f"Entering text ({input_method}): {text}")
                type_text(text + " ", method=input_method)
            else:
                logger.warning("Empty transcription result")

        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)

        finally:
            with self._lock:
                self.state = AppState.IDLE
                if self.bubble:
                    self.bubble.set_state("idle")

    def _open_settings(self):
        """Open settings window (thread-safe via Qt event)."""
        logger.info("_open_settings called from thread, posting event...")
        event = OpenSettingsEvent()
        QCoreApplication.postEvent(self.event_handler, event)
        logger.info("Event posted successfully")

    def _do_open_settings(self):
        """Actually open the settings window (runs on Qt main thread)."""
        try:
            logger.info("_do_open_settings executing on Qt thread...")
            if self.settings_window is None:
                logger.info("Creating new settings window...")
                # Lazy import to avoid circular imports
                from .ui.settings_window import SettingsWindow
                self.settings_window = SettingsWindow(self)
                self.settings_window.model_changed.connect(self.switch_model)
                self.settings_window.device_changed.connect(self.switch_device)
                self.settings_window.vocabulary_changed.connect(self._on_vocabulary_changed)
                logger.info("Settings window created")
            else:
                logger.info("Settings window already exists")

            logger.info("Showing settings window...")
            self.settings_window.show_and_focus()
            logger.info("Settings window shown")

            # Refresh history when opening
            self.settings_window.refresh_history()
            logger.info("History refreshed")
        except Exception as e:
            logger.error(f"Error in _do_open_settings: {e}", exc_info=True)

    def _on_vocabulary_changed(self, words: list):
        """Handle vocabulary update."""
        logger.info(f"Vocabulary updated: {len(words)} words")

    def run(self):
        """Run the application."""
        logger.info("Starting MedASR...")
        logger.info("Press Ctrl+Win to start/stop dictation")
        logger.info("Press Escape while recording to cancel")
        logger.info("Right-click system tray icon to switch models")
        logger.info("Double-click system tray icon to open settings")

        # Start audio stream
        try:
            self.audio.start()
        except Exception as e:
            logger.error(f"Failed to start audio: {e}")
            return 1

        # Start hotkey listener
        self.hotkeys.start()

        # Create bubble (hidden initially)
        self.bubble = FloatingBubble()

        # Create system tray icon
        self.tray = SystemTray(self)
        self.tray.on_settings_open = self._open_settings  # Connect double-click
        self.tray.run()

        # Run Qt event loop
        return self.qt_app.exec()

    def cleanup(self):
        """Cleanup resources."""
        # Make this idempotent (can be called multiple times safely)
        if not hasattr(self, '_cleaned_up'):
            logger.info("Cleaning up...")
            self._cleaned_up = True

            self.hotkeys.stop()
            self.audio.stop()
            if self.tray:
                self.tray.stop()

            logger.info("Cleanup complete")
