import argparse
import ctypes
import json
import math
import random
import sys
import threading
import time
import traceback
from pathlib import Path

from PyQt5.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QProcess,
    QRect,
    QLockFile,
    QThread,
    QTimer,
    QUrl,
    Qt,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygon,
    QPixmap,
    QRadialGradient,
    QRegion,
)
from PyQt5.QtMultimedia import QAudioEncoderSettings, QAudioRecorder, QMultimedia, QSound
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from chat_stream import ChatCancelled, select_recent_messages
from focus_session import FocusSession
from llm_client import ModelUnavailable, YayanLLM


PROJECT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = PROJECT_DIR / "output" / "runtime"
DESKTOP_STATE_PATH = RUNTIME_DIR / "desktop-state.json"
FOCUS_STATE_PATH = RUNTIME_DIR / "focus-session.json"
AUDIO_INPUT_PATH = RUNTIME_DIR / "voice-input.wav"
AUDIO_REPLY_PATH = RUNTIME_DIR / "voice-reply.wav"
PET_ASSET_PATH = PROJECT_DIR / "assets" / "yayan-watercolor-base.png"
STARTUP_LOG_PATH = RUNTIME_DIR / "desktop-startup.log"
INSTANCE_NAME = "YayanDesktopPet-v2"
INSTANCE_LOCK_PATH = RUNTIME_DIR / "yayan-single-instance.lock"


PANEL_STYLE = """
QDialog, QFrame#actionPanel {
    background: #f4f7f6;
    color: #263a36;
    border: 1px solid #cbd8d4;
    border-radius: 12px;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 13px;
}
QFrame#actionPanel QLabel {
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 14px;
}
QFrame#actionPanel QLabel#title {
    color: #1f4039;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 18px;
    font-weight: 700;
}
QLabel#eyebrow { color: #6b837d; font-size: 11px; }
QPushButton {
    min-height: 38px;
    padding: 0 13px;
    color: #294b43;
    background: #e8efed;
    border: 1px solid #cbdad5;
    border-radius: 8px;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 14px;
}
QPushButton[role="settingsAction"] {
    min-height: 42px;
    max-height: 42px;
}
QPushButton:hover { background: #dce9e5; border-color: #a9c2ba; }
QPushButton#primary { color: white; background: #285b50; border: 1px solid #285b50; }
QPushButton#primary:hover { background: #1f4d43; }
QPushButton#quiet { background: #eef3f2; color: #4d6861; }
QLineEdit, QTextBrowser {
    min-height: 38px;
    padding: 0 12px;
    color: #263a36;
    background: #ffffff;
    border: 1px solid #c7d5d1;
    border-radius: 7px;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 14px;
    selection-background-color: #bcd9d1;
}
QComboBox, QSpinBox {
    min-height: 38px;
    padding: 0 12px;
    color: #263a36;
    background: #ffffff;
    border: 1px solid #c7d5d1;
    border-radius: 7px;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 14px;
}
QComboBox::drop-down {
    width: 28px;
    border: none;
    border-left: 1px solid #d9e3e0;
    background: #f7faf9;
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
}
QComboBox::down-arrow {
    image: none;
}
QComboBox QAbstractItemView {
    color: #263a36;
    background: #ffffff;
    border: 1px solid #c7d5d1;
    selection-background-color: #dcebe7;
    selection-color: #1f4039;
    padding: 4px;
}
QCheckBox {
    min-height: 30px;
    color: #46635b;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 13px;
}
QLabel#fieldLabel {
    color: #45645c;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 14px;
    font-weight: 600;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #d6e2df;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #5b8d80;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background: #f4f7f6;
    border: 2px solid #5b8d80;
    border-radius: 7px;
}
"""


CHAT_PANEL_STYLE = """
QDialog#chatPanel {
    background: transparent;
    border: none;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
}
QFrame#chatShell {
    color: #263a36;
    background: #f1f5f4;
    border: 1px solid #bfcec9;
    border-radius: 16px;
}
QLabel#chatTitle {
    color: #1f4039;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-weight: 700;
    letter-spacing: 0px;
}
QLabel#chatPresence {
    color: #6d7e79;
}
QLabel#presenceDot {
    color: #4f9d88;
}
QPushButton#chatHeaderButton {
    padding: 0 8px;
    color: #58706a;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
}
QPushButton#chatHeaderButton:hover {
    color: #244f45;
    background: #e1ebe8;
    border-color: #c0d3cd;
}
QScrollArea#chatLog {
    color: #263a36;
    background: #f7faf9;
    border: 1px solid #d1ddda;
    border-radius: 12px;
}
QWidget#chatMessageView { background: transparent; }
QFrame#chatWelcome {
    background: #e8f0ed;
    border: 1px solid #d0dfda;
    border-radius: 14px;
}
QLabel#chatWelcomeStatus {
    color: #4f8c7d;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 12px;
    font-weight: 600;
}
QLabel#chatWelcomeTitle {
    color: #285b50;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 17px;
    font-weight: 700;
}
QLabel#chatWelcomeCopy {
    color: #6d7e79;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 13px;
}
QFrame#petBubble, QFrame#userBubble {
    border-radius: 8px;
}
QFrame#petBubble {
    background: #e8efed;
    border: 1px solid #d2dfdb;
    border-left: 3px solid #6d9b8f;
}
QFrame#userBubble {
    background: #dce8e5;
    border: 1px solid #c8dad5;
    border-right: 3px solid #3f7568;
}
QLabel#messageSpeakerPet, QLabel#messageSpeakerUser {
    background: transparent;
    border: none;
    font-weight: 600;
}
QLabel#messageSpeakerPet { color: #4f756b; }
QLabel#messageSpeakerUser { color: #4b7168; }
QLabel#messageStage {
    color: #6a817b;
    background: transparent;
    border: none;
}
QLabel#messageBody {
    color: #263a36;
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    width: 7px;
    margin: 10px 3px 10px 0;
    background: transparent;
}
QScrollBar::handle:vertical {
    min-height: 30px;
    background: #a9c2ba;
    border-radius: 2px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QFrame#chatComposer {
    background: #ffffff;
    border: 1px solid #c5d4d0;
    border-radius: 13px;
}
QLineEdit#chatInput {
    padding: 0 7px;
    color: #263a36;
    background: transparent;
    border: none;
    font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    selection-color: #1f4039;
    selection-background-color: #cfe3de;
}
QLineEdit#chatInput:disabled {
    color: #91a099;
}
QPushButton#chatSend {
    padding: 0 13px;
    color: white;
    background: #285b50;
    border: none;
    border-radius: 10px;
    font-weight: 600;
}
QPushButton#chatSend:hover { background: #1f4d43; }
QPushButton#chatSend:pressed { background: #183f37; }
QPushButton#chatSend:disabled { color: #e8eeea; background: #90a8a1; }
QPushButton#chatStop {
    padding: 0 12px;
    color: #7b5048;
    background: #f2e7e4;
    border: 1px solid #dfc9c3;
    border-radius: 10px;
    font-weight: 600;
}
QPushButton#chatStop:hover { background: #ead6d0; }
QPushButton#chatStop:pressed { background: #e1c5bd; }
QPushButton#chatMic {
    padding: 0 12px;
    color: #466b62;
    background: #e7efed;
    border: 1px solid #c8dad5;
    border-radius: 9px;
}
QPushButton#chatMic:hover { background: #d9e9e4; }
"""


def load_json(path, fallback):
    try:
        return {**fallback, **json.loads(Path(path).read_text(encoding="utf-8-sig"))}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(fallback)


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    pending.replace(path)


class CleanComboBox(QComboBox):
    """A compact combo box with a deliberately drawn, minimal chevron."""

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.subControls &= ~QStyle.SC_ComboBoxArrow
        painter.drawComplexControl(QStyle.CC_ComboBox, option)
        arrow_rect = self.style().subControlRect(
            QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxArrow, self
        )
        center = arrow_rect.center()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#628079"))
        painter.drawPolygon(
            QPolygon(
                [
                    QPoint(center.x() - 4, center.y() - 2),
                    QPoint(center.x() + 4, center.y() - 2),
                    QPoint(center.x(), center.y() + 3),
                ]
            )
        )


def log_startup(event, **details):
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event": event,
        **details,
    }
    with STARTUP_LOG_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


class WorkThread(QThread):
    completed = pyqtSignal(str, str)
    failed = pyqtSignal(str, str)
    chunk = pyqtSignal(str, str)
    cancelled = pyqtSignal(str, str)

    def __init__(self, client, mode, payload, context=None):
        super().__init__()
        self.client = client
        self.mode = mode
        self.payload = payload
        self.context = context
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            if self.mode == "chat":
                result = self.client.stream_chat(
                    self.payload,
                    self.context,
                    on_delta=lambda text: self.chunk.emit(self.mode, text),
                    should_cancel=self.cancel_event.is_set,
                )
            elif self.mode == "tts":
                result = self.client.synthesize(self.payload, AUDIO_REPLY_PATH)
            else:
                result = self.client.transcribe(self.payload)
            self.completed.emit(self.mode, result)
        except ChatCancelled as error:
            self.cancelled.emit(self.mode, error.partial_text)
        except ModelUnavailable as error:
            self.failed.emit(self.mode, str(error))
        except Exception as error:
            self.failed.emit(self.mode, f"发生未预期错误：{type(error).__name__}")


class ChatPanel(QDialog):
    send_requested = pyqtSignal(str)
    cancel_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    voice_requested = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatPanel")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(360, 520)
        self.setMaximumSize(450, 660)
        self.resize(390, 570)
        self.setStyleSheet(CHAT_PANEL_STYLE)
        self.interface_font = self.make_font(15)
        self.setFont(self.interface_font)
        self.recording = False
        self.busy = False
        self.messages = []
        self.streaming_message = None
        self.streaming_bubble = None
        self.streaming_body = None
        self.rendered_bubbles = []
        self.rendered_speakers = []
        self.rendered_stages = []
        self.rendered_bodies = []

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(0)
        self.shell = QFrame()
        self.shell.setObjectName("chatShell")
        outer_layout.addWidget(self.shell)
        layout = QVBoxLayout(self.shell)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.title = QLabel("芽砚")
        self.title.setObjectName("chatTitle")
        presence_row = QHBoxLayout()
        presence_row.setSpacing(4)
        self.presence_dot = QLabel("●")
        self.presence_dot.setObjectName("presenceDot")
        self.presence = QLabel("在这里，慢慢说")
        self.presence.setObjectName("chatPresence")
        presence_row.addWidget(self.presence_dot)
        presence_row.addWidget(self.presence)
        presence_row.addStretch()
        title_box.addWidget(self.title)
        title_box.addLayout(presence_row)
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("chatHeaderButton")
        self.close_button.clicked.connect(self.hide)
        self.settings_button = QPushButton("设置")
        self.settings_button.setObjectName("chatHeaderButton")
        self.settings_button.clicked.connect(self.settings_requested.emit)
        header.addLayout(title_box)
        header.addStretch()
        header.addWidget(self.settings_button)
        header.addWidget(self.close_button)

        self.log = QScrollArea()
        self.log.setObjectName("chatLog")
        self.log.setWidgetResizable(True)
        self.log.setFrameShape(QFrame.NoFrame)
        self.log.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.log.viewport().setStyleSheet("background: transparent;")
        self.message_view = QWidget()
        self.message_view.setObjectName("chatMessageView")
        self.message_layout = QVBoxLayout(self.message_view)
        self.message_layout.setContentsMargins(14, 14, 14, 14)
        self.message_layout.setSpacing(10)
        self.message_layout.setSizeConstraint(self.message_layout.SetMinAndMaxSize)
        self.log.setWidget(self.message_view)
        self.render_messages()

        self.input = QLineEdit()
        self.input.setObjectName("chatInput")
        self.input.setPlaceholderText("和芽砚说点什么……")
        self.input.returnPressed.connect(self.send)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)
        self.mic = QPushButton("按住说话")
        self.mic.setObjectName("chatMic")
        self.mic.pressed.connect(lambda: self.set_recording(True))
        self.mic.released.connect(lambda: self.set_recording(False))
        self.mic.hide()

        composer = QFrame()
        composer.setObjectName("chatComposer")
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(10, 6, 6, 6)
        composer_layout.setSpacing(8)
        self.send_button = QPushButton("发送")
        self.send_button.setObjectName("chatSend")
        self.send_button.clicked.connect(self.send)
        self.stop_button = QPushButton("停止生成")
        self.stop_button.setObjectName("chatStop")
        self.stop_button.clicked.connect(self.cancel_requested.emit)
        self.stop_button.hide()
        composer_layout.addWidget(self.input, 1)
        composer_layout.addWidget(self.send_button)
        composer_layout.addWidget(self.stop_button)

        controls.addWidget(self.mic)
        controls.addWidget(composer, 1)

        layout.addLayout(header)
        layout.addWidget(self.log, 1)
        layout.addLayout(controls)
        self.apply_adaptive_layout()

    def make_font(self, pixel_size, weight=QFont.Normal, family="Noto Sans SC"):
        font = QFont(family)
        font.setPixelSize(max(9, int(pixel_size)))
        font.setWeight(weight)
        return font

    def make_display_font(self, pixel_size):
        return self.make_font(pixel_size, QFont.Bold, "Noto Sans SC")

    def adaptive_scale(self):
        width_scale = self.width() / 390
        height_scale = self.height() / 570
        return max(0.92, min(1.10, width_scale, height_scale))

    def scaled_pixels(self, base_size):
        return max(9, round(base_size * self.adaptive_scale()))

    def apply_adaptive_layout(self):
        if not hasattr(self, "send_button"):
            return

        scale = self.adaptive_scale()
        self.interface_font = self.make_font(self.scaled_pixels(15))
        self.setFont(self.interface_font)
        self.title.setFont(self.make_display_font(self.scaled_pixels(20)))
        self.presence.setFont(self.make_font(self.scaled_pixels(11)))
        self.presence_dot.setFont(self.make_font(self.scaled_pixels(11)))
        self.settings_button.setFont(self.make_font(self.scaled_pixels(12), QFont.DemiBold))
        self.close_button.setFont(self.make_font(self.scaled_pixels(12)))
        self.input.setFont(self.make_font(self.scaled_pixels(15)))
        self.send_button.setFont(self.make_font(self.scaled_pixels(13), QFont.DemiBold))
        self.stop_button.setFont(self.make_font(self.scaled_pixels(13), QFont.DemiBold))
        self.mic.setFont(self.make_font(self.scaled_pixels(12), QFont.DemiBold))

        header_height = round(30 * scale)
        self.close_button.setFixedSize(header_height, header_height)
        self.settings_button.setFixedSize(round(46 * scale), header_height)
        self.send_button.setFixedSize(round(58 * scale), round(40 * scale))
        self.stop_button.setFixedSize(round(84 * scale), round(40 * scale))
        self.input.setMinimumHeight(round(40 * scale))
        self.mic.setFixedHeight(round(40 * scale))

        for speaker in self.rendered_speakers:
            speaker.setFont(self.make_font(self.scaled_pixels(11), QFont.DemiBold))
        for stage in self.rendered_stages:
            stage.setFont(self.make_font(self.scaled_pixels(11)))
        for body in self.rendered_bodies:
            body.setFont(self.make_font(self.scaled_pixels(15)))
        for bubble in self.rendered_bubbles:
            self.update_bubble_width(bubble, bubble.property("messageText") or "")
        self.message_view.adjustSize()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.apply_adaptive_layout()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.scroll_to_bottom)

    def add_message(self, speaker, text, is_pet=False):
        message = {"speaker": str(speaker), "text": str(text), "is_pet": bool(is_pet)}
        self.messages.append(message)
        if self.empty_message is not None:
            self.message_layout.removeWidget(self.empty_message)
            self.empty_message.hide()
            self.empty_message.setParent(None)
            self.empty_message.deleteLater()
            self.empty_message = None
        self.add_message_widget(message)
        QTimer.singleShot(0, self.scroll_to_bottom)

    def start_streaming_message(self):
        message = {
            "speaker": "芽砚",
            "text": "",
            "is_pet": True,
            "streaming": True,
            "context_eligible": True,
        }
        if self.empty_message is not None:
            self.message_layout.removeWidget(self.empty_message)
            self.empty_message.hide()
            self.empty_message.setParent(None)
            self.empty_message.deleteLater()
            self.empty_message = None
        self.messages.append(message)
        self.streaming_message = message
        self.streaming_bubble, self.streaming_body = self.add_message_widget(message)
        QTimer.singleShot(0, self.scroll_to_bottom)

    def append_streaming_text(self, text):
        if self.streaming_message is None:
            return
        self.streaming_message["text"] += str(text)
        if self.streaming_bubble is not None:
            self.streaming_bubble.setProperty("messageText", self.streaming_message["text"])
            self.update_bubble_width(self.streaming_bubble, self.streaming_message["text"])
        if self.streaming_body is not None:
            self.streaming_body.setText(self.streaming_message["text"])
        self.streaming_body and self.streaming_body.adjustSize()
        QTimer.singleShot(0, self.scroll_to_bottom)

    def finish_streaming_message(self, text=None, stopped=False, eligible=True):
        if self.streaming_message is None:
            return
        if text is not None and text != self.streaming_message["text"]:
            self.streaming_message["text"] = str(text)
            if self.streaming_bubble is not None:
                self.streaming_bubble.setProperty("messageText", self.streaming_message["text"])
                self.update_bubble_width(self.streaming_bubble, self.streaming_message["text"])
            if self.streaming_body is not None:
                self.streaming_body.setText(self.streaming_message["text"])
        self.streaming_message["streaming"] = False
        self.streaming_message["context_eligible"] = bool(eligible)
        if stopped and self.streaming_body is not None:
            suffix = "\n\n（已停止）"
            if not self.streaming_message["text"].endswith(suffix):
                self.streaming_message["text"] += suffix
                if self.streaming_bubble is not None:
                    self.streaming_bubble.setProperty("messageText", self.streaming_message["text"])
                    self.update_bubble_width(self.streaming_bubble, self.streaming_message["text"])
                self.streaming_body.setText(self.streaming_message["text"])
        self.streaming_message = None
        self.streaming_bubble = None
        self.streaming_body = None
        self.message_view.adjustSize()
        QTimer.singleShot(0, self.scroll_to_bottom)

    def render_messages(self):
        self.empty_message = QFrame()
        self.empty_message.setObjectName("chatWelcome")
        self.empty_message.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        welcome_layout = QVBoxLayout(self.empty_message)
        welcome_layout.setContentsMargins(18, 16, 18, 16)
        welcome_layout.setSpacing(5)
        status = QLabel("●  准备好了")
        status.setObjectName("chatWelcomeStatus")
        title = QLabel("和芽砚慢慢聊")
        title.setObjectName("chatWelcomeTitle")
        copy = QLabel("输入一句话，想到哪里，就说到哪里。")
        copy.setObjectName("chatWelcomeCopy")
        welcome_layout.addWidget(status)
        welcome_layout.addWidget(title)
        welcome_layout.addWidget(copy)
        self.message_layout.addStretch(1)
        self.message_layout.addWidget(self.empty_message)
        self.message_layout.addStretch(1)

    def add_message_widget(self, message):
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        bubble = QFrame()
        bubble.setObjectName("petBubble" if message["is_pet"] else "userBubble")
        bubble.setProperty("messageText", message["text"])
        self.update_bubble_width(bubble, message["text"])
        bubble.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.rendered_bubbles.append(bubble)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(13, 9, 13, 10)
        bubble_layout.setSpacing(4)

        speaker = QLabel(message["speaker"])
        speaker.setObjectName("messageSpeakerPet" if message["is_pet"] else "messageSpeakerUser")
        speaker.setFont(self.make_font(self.scaled_pixels(11), QFont.DemiBold))
        speaker.setTextFormat(Qt.PlainText)
        bubble_layout.addWidget(speaker)
        self.rendered_speakers.append(speaker)

        body_text = message["text"]
        if message["is_pet"] and body_text.startswith("（") and "）" in body_text:
            stage_end = body_text.find("）") + 1
            stage = QLabel(body_text[:stage_end])
            stage.setObjectName("messageStage")
            stage.setFont(self.make_font(self.scaled_pixels(11)))
            stage.setTextFormat(Qt.PlainText)
            stage.setWordWrap(True)
            bubble_layout.addWidget(stage)
            self.rendered_stages.append(stage)
            body_text = body_text[stage_end:].lstrip()

        if body_text or message.get("streaming"):
            body = QLabel(body_text)
            body.setObjectName("messageBody")
            body.setFont(self.make_font(self.scaled_pixels(15)))
            body.setTextFormat(Qt.PlainText)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            body.setWordWrap(True)
            bubble_layout.addWidget(body)
            self.rendered_bodies.append(body)
        else:
            body = None

        if message["is_pet"]:
            row_layout.addWidget(bubble)
            row_layout.addStretch(1)
        else:
            row_layout.addStretch(1)
            row_layout.addWidget(bubble)
        self.message_layout.insertWidget(self.message_layout.count() - 1, row)
        self.message_view.adjustSize()
        return bubble, body

    def update_bubble_width(self, bubble, text):
        scale = self.adaptive_scale()
        max_line_length = max((len(line) for line in str(text).splitlines()), default=8)
        available_width = max(220, self.width() - round(62 * scale))
        maximum_width = min(round(304 * scale), round(available_width * 0.90))
        preferred_width = round(30 * scale) + min(max_line_length, 20) * self.scaled_pixels(13)
        bubble_width = min(maximum_width, max(round(148 * scale), preferred_width))
        bubble.setFixedWidth(max(144, bubble_width))

    def scroll_to_bottom(self):
        scroll_bar = self.log.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.send_requested.emit(text)

    def set_recording(self, active):
        self.recording = active
        self.mic.setText("松开就好" if active else "按住说话")
        self.voice_requested.emit(active)

    def set_voice_input_enabled(self, enabled):
        enabled = bool(enabled)
        self.mic.setEnabled(enabled)
        self.mic.setVisible(enabled)
        if enabled:
            self.mic.setText("按住说话")

    def set_busy(self, busy):
        self.busy = bool(busy)
        self.input.setEnabled(not self.busy)
        self.send_button.setEnabled(not self.busy)
        self.send_button.setText("发送")
        self.stop_button.setEnabled(self.busy)
        self.stop_button.setVisible(self.busy)
        self.input.setPlaceholderText("芽砚正在想……" if self.busy else "和芽砚说点什么……")
        if not self.busy:
            self.input.setFocus()


class SettingsPanel(QDialog):
    save_requested = pyqtSignal(dict, str)
    clear_key_requested = pyqtSignal()
    restart_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(460, 620)
        self.setStyleSheet(PANEL_STYLE)

        shell = QFrame(self)
        shell.setObjectName("actionPanel")
        shell.setGeometry(8, 8, 444, 604)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        eyebrow = QLabel("只在这台电脑上生效")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("芽砚的后台设置")
        title.setObjectName("title")
        title_box.addWidget(eyebrow)
        title_box.addWidget(title)
        close_button = QPushButton("×")
        close_button.setFixedSize(34, 34)
        close_button.clicked.connect(self.hide)
        header.addLayout(title_box)
        header.addStretch()
        header.addWidget(close_button)

        form = QGridLayout()
        form.setVerticalSpacing(9)
        form.setHorizontalSpacing(14)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        self.base_url = QLineEdit()
        self.base_url.setPlaceholderText("留空使用服务默认地址")
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("留空则保留已保存密钥")
        self.model = QLineEdit()
        self.model.setPlaceholderText("模型名称")
        self.api_mode = CleanComboBox()
        self.api_mode.addItem("Responses API", "responses")
        self.api_mode.addItem("Chat Completions 兼容", "chat")
        self.voice = CleanComboBox()
        for name in ("shimmer", "coral", "nova", "alloy"):
            self.voice.addItem(name, name)
        self.interaction_style = CleanComboBox()
        self.interaction_style.addItem("温柔灵动", "gentle")
        self.interaction_style.addItem("更活泼一点", "lively")
        self.interaction_style.addItem("更安静一点", "quiet")
        self.memory_mode = CleanComboBox()
        self.memory_mode.addItem("分级记忆", "graded")
        self.memory_mode.addItem("仅当前对话", "session")
        self.reminder_strength = QSlider(Qt.Horizontal)
        self.reminder_strength.setRange(1, 5)
        self.reminder_strength.setValue(2)
        self.voice_input_enabled = QCheckBox("在聊天窗显示“按住说话”按钮")
        self.speak_replies = QCheckBox("回复时播放语音")
        def add_field(label_text, widget, row, column=0, span=1):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            label.setFixedHeight(18)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            form.addWidget(label, row, column, 1, span)
            widget.setFixedHeight(40)
            form.addWidget(widget, row + 1, column, 1, span)

        add_field("API 地址", self.base_url, 0, span=2)
        add_field("API 密钥", self.api_key, 2, span=2)
        add_field("模型", self.model, 4)
        add_field("接口", self.api_mode, 4, 1)
        add_field("声音", self.voice, 6)
        add_field("相处语气", self.interaction_style, 6, 1)
        add_field("记忆方式", self.memory_mode, 8)
        self.reminder_strength.setMinimumHeight(40)
        add_field("提醒力度", self.reminder_strength, 8, 1)

        key_note = QLabel("密钥保存到 Windows 凭据管理器，不写入项目文件。")
        key_note.setWordWrap(True)
        key_note.setObjectName("eyebrow")
        clear_key = QPushButton("清除密钥")
        clear_key.setObjectName("settingsAction")
        clear_key.setProperty("role", "settingsAction")
        clear_key.setFixedSize(92, 40)
        clear_key.clicked.connect(self.clear_key_requested.emit)
        restart = QPushButton("重启芽砚")
        restart.setObjectName("quiet")
        restart.setProperty("role", "settingsAction")
        restart.setFixedSize(92, 40)
        restart.clicked.connect(self.restart_requested.emit)
        save = QPushButton("保存设置")
        save.setObjectName("primary")
        save.setProperty("role", "settingsAction")
        save.setFixedSize(92, 40)
        save.clicked.connect(self.save)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch()
        actions.addWidget(clear_key)
        actions.addWidget(restart)
        actions.addWidget(save)
        actions.addStretch()
        quit_button = QPushButton("退出芽砚")
        quit_button.setObjectName("quiet")
        quit_button.setProperty("role", "settingsAction")
        quit_button.setFixedSize(92, 40)
        quit_button.clicked.connect(self.quit_requested.emit)
        actions.addWidget(quit_button)

        layout.addLayout(header)
        layout.addLayout(form)
        layout.addWidget(self.voice_input_enabled)
        layout.addWidget(self.speak_replies)
        layout.addWidget(key_note)
        layout.addSpacing(4)
        layout.addLayout(actions)

    def load_values(self, settings):
        self.base_url.setText(settings.get("llm_base_url", ""))
        self.model.setText(settings.get("llm_model", ""))
        self._select(self.api_mode, settings.get("api_mode", "responses"))
        self._select(self.voice, settings.get("tts_voice", "shimmer"))
        self._select(self.interaction_style, settings.get("interaction_style", "gentle"))
        self._select(self.memory_mode, settings.get("memory_mode", "graded"))
        self.reminder_strength.setValue(int(settings.get("reminder_strength", 2)))
        self.voice_input_enabled.setChecked(bool(settings.get("voice_input_enabled", False)))
        self.speak_replies.setChecked(bool(settings.get("speak_replies", True)))
        self.api_key.clear()

    @staticmethod
    def _select(combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(max(0, index))

    def save(self):
        values = {
            "llm_base_url": self.base_url.text().strip(),
            "llm_model": self.model.text().strip(),
            "api_mode": self.api_mode.currentData(),
            "tts_voice": self.voice.currentData(),
            "interaction_style": self.interaction_style.currentData(),
            "memory_mode": self.memory_mode.currentData(),
            "reminder_strength": self.reminder_strength.value(),
            "voice_input_enabled": self.voice_input_enabled.isChecked(),
            "speak_replies": self.speak_replies.isChecked(),
        }
        self.save_requested.emit(values, self.api_key.text())
        self.api_key.clear()
        self.hide()


class TaskPanel(QDialog):
    changed = pyqtSignal(dict)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 286)
        self.setStyleSheet(PANEL_STYLE)

        shell = QFrame(self)
        shell.setObjectName("actionPanel")
        shell.setGeometry(8, 8, 344, 270)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        eyebrow = QLabel("只看眼前这一小块")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("现在主要在做什么？")
        title.setObjectName("title")
        self.task = QLineEdit(state.get("task", ""))
        self.task.setPlaceholderText("当前主任务")
        self.step = QLineEdit(state.get("next_step", ""))
        self.step.setPlaceholderText("下一步，小到可以立刻开始")
        progress_label = QLabel("大概做到哪里了")
        progress_label.setObjectName("eyebrow")
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 100)
        self.progress.setValue(int(state.get("progress", 0)))
        save = QPushButton("记住现在的位置")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        close = QPushButton("先这样")
        close.clicked.connect(self.hide)
        actions = QHBoxLayout()
        actions.addWidget(close)
        actions.addWidget(save)
        for item in (eyebrow, title, self.task, self.step, progress_label, self.progress):
            layout.addWidget(item)
        layout.addSpacing(4)
        layout.addLayout(actions)

    def save(self):
        self.state.update({
            "task": self.task.text().strip(),
            "next_step": self.step.text().strip(),
            "progress": self.progress.value(),
        })
        self.changed.emit(dict(self.state))
        self.hide()


class FocusPanel(QDialog):
    start_requested = pyqtSignal(int)
    pause_requested = pyqtSignal()
    resume_requested = pyqtSignal()
    finish_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session_status = None
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(380, 350)
        self.setStyleSheet(PANEL_STYLE)

        shell = QFrame(self)
        shell.setObjectName("actionPanel")
        shell.setGeometry(8, 8, 364, 334)
        self.shell = shell
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        eyebrow = QLabel("由你开始，也随时可以停下")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("陪你专注一小段")
        title.setObjectName("title")
        self.task_label = QLabel("先选一个舒服的时长。")
        self.task_label.setWordWrap(True)
        self.status_label = QLabel("还没有开始")
        self.status_label.setObjectName("eyebrow")

        self.duration = CleanComboBox()
        for minutes in (5, 12, 25, 45):
            self.duration.addItem(f"{minutes} 分钟", minutes)
        self.duration.addItem("自定义", None)
        self.duration.setCurrentIndex(1)
        self.custom_duration = QSpinBox()
        self.custom_duration.setRange(1, 120)
        self.custom_duration.setValue(12)
        self.custom_duration.setSuffix(" 分钟")
        self.custom_duration.setEnabled(False)
        self.custom_duration.hide()
        self.duration.currentIndexChanged.connect(
            self.update_duration_mode
        )

        self.start_button = QPushButton("开始 12 分钟")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.request_start)
        self.custom_duration.valueChanged.connect(self.update_start_text)
        self.pause_button = QPushButton("暂停")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.hide()
        self.finish_button = QPushButton("提前结束")
        self.finish_button.clicked.connect(self.finish_requested.emit)
        self.finish_button.hide()
        close_button = QPushButton("先收起面板")
        close_button.setObjectName("quiet")
        close_button.clicked.connect(self.hide)

        controls = QHBoxLayout()
        controls.addWidget(self.pause_button)
        controls.addWidget(self.finish_button)

        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(self.task_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.duration)
        layout.addWidget(self.custom_duration)
        layout.addWidget(self.start_button)
        layout.addLayout(controls)
        layout.addSpacing(4)
        layout.addWidget(close_button)

    def update_duration_mode(self):
        custom = self.duration.currentData() is None
        self.custom_duration.setEnabled(custom)
        self.custom_duration.setVisible(custom)
        panel_height = 384 if custom else 350
        self.setFixedSize(380, panel_height)
        self.shell.setGeometry(8, 8, 364, panel_height - 16)
        self.update_start_text()

    def selected_minutes(self):
        return self.custom_duration.value() if self.duration.currentData() is None else int(self.duration.currentData())

    def update_start_text(self):
        prefix = "重新开始" if self.session_status in {FocusSession.RUNNING, FocusSession.PAUSED} else "开始"
        self.start_button.setText(f"{prefix} {self.selected_minutes()} 分钟")

    def request_start(self):
        self.start_requested.emit(self.selected_minutes())

    def toggle_pause(self):
        if self.session_status == FocusSession.PAUSED:
            self.resume_requested.emit()
        else:
            self.pause_requested.emit()

    def set_session(self, session):
        if session is None or not session.is_active:
            self.session_status = None
            self.status_label.setText("还没有开始")
            self.task_label.setText("先选一个舒服的时长。")
            self.pause_button.hide()
            self.finish_button.hide()
        else:
            self.session_status = session.status
            minutes, seconds = divmod(max(0, session.remaining_seconds), 60)
            state_text = "暂停中" if session.status == FocusSession.PAUSED else "专注中"
            self.status_label.setText(f"{state_text} · {minutes:02d}:{seconds:02d}")
            step = session.next_step or session.task or "眼前最小的那一步"
            self.task_label.setText(f"现在只碰：{step}")
            self.pause_button.setText("继续" if session.status == FocusSession.PAUSED else "暂停")
            self.pause_button.show()
            self.finish_button.show()
        self.update_start_text()


class FocusReviewPanel(QDialog):
    save_requested = pyqtSignal(dict)
    dismiss_requested = pyqtSignal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(380, 344)
        self.setStyleSheet(PANEL_STYLE)

        shell = QFrame(self)
        shell.setObjectName("actionPanel")
        shell.setGeometry(8, 8, 364, 328)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        eyebrow = QLabel("不评判完成度，只记下真实留下的东西")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("刚才留下了什么？")
        title.setObjectName("title")
        self.note = QLineEdit()
        self.note.setPlaceholderText("哪怕只写了一行，也可以记下来")
        self.next_step = QLineEdit()
        self.next_step.setPlaceholderText("接下来最小的一步")
        progress_label = QLabel("现在大概做到哪里了")
        progress_label.setObjectName("eyebrow")
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 100)

        save_button = QPushButton("记下这次进展")
        save_button.setObjectName("primary")
        save_button.clicked.connect(self.save)
        dismiss_button = QPushButton("这次先不记录")
        dismiss_button.clicked.connect(self.dismiss)

        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(self.note)
        layout.addWidget(self.next_step)
        layout.addWidget(progress_label)
        layout.addWidget(self.progress)
        layout.addSpacing(4)
        layout.addWidget(save_button)
        layout.addWidget(dismiss_button)

    def load_state(self, state):
        self.state = state
        self.note.clear()
        self.next_step.setText(state.get("next_step", ""))
        self.progress.setValue(int(state.get("progress", 0)))

    def save(self):
        self.save_requested.emit(
            {
                "last_focus_note": self.note.text().strip(),
                "next_step": self.next_step.text().strip(),
                "progress": self.progress.value(),
            }
        )
        self.hide()

    def dismiss(self):
        self.dismiss_requested.emit()
        self.hide()


class PetWindow(QWidget):
    action_requested = pyqtSignal(str)
    animal_changed = pyqtSignal(str)

    COLORS = {
        "watercolor": {"name": "水彩狐猫"},
    }

    def __init__(self, animal="watercolor"):
        super().__init__()
        self.animal = "watercolor"
        self.mood = "idle"
        self.phase = 0.0
        self.drag_origin = None
        self.window_origin = None
        self.home_position = None
        self.touch_times = []
        self.blink_until = 0.0
        self.quiet = False
        self.menu_visible = False
        self.bubble_text = ""
        self.bubble_visible = False
        self.bubble_generation = 0

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFixedSize(330, 390)
        self.pet_rect = QRect(17, 43, 296, 340)
        self.pet_pixmap = QPixmap(str(PET_ASSET_PATH))
        if self.pet_pixmap.isNull():
            raise RuntimeError(f"没有找到水彩宠物素材：{PET_ASSET_PATH}")

        self.bubble = QLabel(self)
        self.bubble.setWordWrap(True)
        self.bubble.setAlignment(Qt.AlignCenter)
        self.bubble.setGeometry(25, 14, 280, 72)
        self.bubble.setStyleSheet(
            "QLabel { color:transparent; background:transparent; border:none; }"
        )
        self.bubble.hide()

        self.menu = QFrame(self)
        self.menu.setObjectName("actionPanel")
        self.menu.setGeometry(15, 15, 300, 210)
        self.menu.setStyleSheet(PANEL_STYLE)
        menu_layout = QGridLayout(self.menu)
        menu_layout.setContentsMargins(13, 13, 13, 13)
        menu_layout.setSpacing(8)
        actions = [
            ("聊聊", "chat"),
            ("当前任务", "task"),
            ("陪我开始", "focus"),
            ("安静一会", "quiet"),
            ("设置", "settings"),
            ("退出芽砚", "quit"),
        ]
        for index, (label, action) in enumerate(actions):
            button = QPushButton(label)
            if action == "chat":
                button.setObjectName("primary")
            button.clicked.connect(lambda checked=False, value=action: self.select_action(value))
            row, column = divmod(index, 2)
            if action == "quit":
                menu_layout.addWidget(button, row, 0, 1, 2)
            else:
                menu_layout.addWidget(button, row, column)
        self.menu.hide()

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.tick)
        self.animation_timer.start(33)
        self.idle_move_timer = QTimer(self)
        self.idle_move_timer.timeout.connect(self.take_tiny_walk)
        self.idle_move_timer.start(7600)
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.hover_pause)

        QTimer.singleShot(0, self.move_to_corner)
        QTimer.singleShot(400, lambda: self.set_mood("curious"))
        QTimer.singleShot(2200, lambda: self.set_mood("idle"))

    def move_to_corner(self):
        screen = QApplication.primaryScreen().availableGeometry()
        point = QPoint(screen.right() - self.width() - 20, screen.bottom() - self.height() - 14)
        self.move(point)
        self.home_position = QPoint(point)

    def tick(self):
        self.phase += 0.07
        if random.random() < 0.003 and not self.quiet:
            self.blink_until = time.time() + 0.16
        self.update()

    def take_tiny_walk(self):
        if self.quiet or self.menu_visible or self.drag_origin or not self.isVisible():
            return
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        bounds = screen.availableGeometry()
        direction = random.choice([-1, 1])
        target_x = max(bounds.left(), min(bounds.right() - self.width(), self.x() + direction * random.randint(24, 58)))
        target = QPoint(target_x, self.y())
        self.walk_animation = QPropertyAnimation(self, b"pos", self)
        self.walk_animation.setDuration(850)
        self.walk_animation.setStartValue(self.pos())
        self.walk_animation.setEndValue(target)
        self.walk_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.walk_animation.start()
        self.home_position = QPoint(target)

    def say(self, text, duration=2500):
        self.bubble_generation += 1
        generation = self.bubble_generation
        self.bubble_text = text
        self.bubble_visible = True
        self.update_mask()
        self.update()
        QTimer.singleShot(
            max(0, int(duration)), lambda: self.hide_bubble(generation)
        )

    def hide_bubble(self, generation=None):
        if generation is not None and generation != self.bubble_generation:
            return
        if not self.menu_visible and self.bubble_visible:
            self.bubble_visible = False
            self.update_mask()
            self.update()

    def set_mood(self, mood):
        self.mood = mood
        self.update()

    def select_action(self, action):
        self.menu.hide()
        self.menu_visible = False
        self.update_mask()
        self.action_requested.emit(action)

    def toggle_menu(self):
        self.menu_visible = not self.menu_visible
        self.menu.setVisible(self.menu_visible)
        if self.menu_visible:
            self.bubble_visible = False
            self.set_mood("happy")
        else:
            QTimer.singleShot(900, lambda: self.set_mood("idle"))
        self.update_mask()
        self.update()

    def cycle_animal(self):
        self.animal = "watercolor"

    def hover_pause(self):
        if not self.menu_visible:
            self.set_mood("concerned")
            QTimer.singleShot(1500, lambda: self.set_mood("curious"))

    def enterEvent(self, event):
        if not self.menu_visible and not self.quiet:
            self.set_mood("curious")
            self.hover_timer.start(1900)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_timer.stop()
        if not self.menu_visible:
            self.set_mood("sleepy" if self.quiet else "idle")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.menu_visible:
                self.toggle_menu()
                event.accept()
                return
            self.drag_origin = event.globalPos()
            self.window_origin = self.pos()
            event.accept()
        elif event.button() == Qt.RightButton:
            self.toggle_menu()

    def mouseMoveEvent(self, event):
        if self.drag_origin and event.buttons() & Qt.LeftButton:
            self.move(self.window_origin + event.globalPos() - self.drag_origin)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self.drag_origin:
            return
        distance = (event.globalPos() - self.drag_origin).manhattanLength()
        self.drag_origin = None
        if distance < 8:
            now = time.time()
            self.touch_times = [stamp for stamp in self.touch_times if now - stamp < 9]
            self.touch_times.append(now)
            if len(self.touch_times) >= 3:
                self.touch_times.clear()
                self.set_mood("shy")
            else:
                self.set_mood("happy")
            self.action_requested.emit("chat")
            QTimer.singleShot(1200, lambda: self.set_mood("idle"))
        else:
            self.home_position = QPoint(self.pos())

    def update_mask(self):
        scaled = self.pet_pixmap.scaled(
            self.pet_rect.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
        )
        region = QRegion(scaled.mask()).translated(self.pet_rect.topLeft())
        region += region.translated(0, -3)
        region += region.translated(0, 6)
        if self.bubble_visible and not self.menu_visible:
            region += QRegion(self.bubble.geometry())
        if self.menu_visible:
            region += QRegion(self.menu.geometry())
        self.setMask(region)

    def showEvent(self, event):
        self.update_mask()
        super().showEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bob = math.sin(self.phase) * (1.5 if not self.quiet else 0.6)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(54, 72, 64, 28))
        painter.drawEllipse(61, 359, 228, 19)

        breath = 1.0 + math.sin(self.phase * 0.72) * (0.006 if not self.quiet else 0.003)
        tilt = 0.0
        if self.mood == "curious":
            tilt = math.sin(self.phase * 0.8) * 1.4
        elif self.mood == "shy":
            tilt = -2.2
        elif self.mood == "concerned":
            tilt = 1.1
        elif self.mood == "sleepy":
            tilt = -1.4
        elif self.mood == "happy":
            bob += abs(math.sin(self.phase * 1.8)) * -2.4

        center = self.pet_rect.center()
        painter.save()
        painter.translate(center.x(), center.y() + bob)
        painter.rotate(tilt)
        painter.scale(breath, breath)
        painter.translate(-center.x(), -center.y())
        painter.setOpacity(0.93 if self.mood == "sleepy" else 1.0)
        painter.drawPixmap(self.pet_rect, self.pet_pixmap)
        painter.restore()

        if self.mood == "shy":
            painter.setBrush(QColor(214, 126, 129, 72))
            painter.drawEllipse(76, 171, 34, 13)
            painter.drawEllipse(220, 171, 34, 13)
        elif self.mood == "happy":
            painter.setBrush(QColor(111, 158, 123, 185))
            for x, y, size in ((48, 113, 5), (284, 132, 4), (53, 205, 3)):
                painter.drawEllipse(x, y, size, size)
        elif self.mood == "thinking":
            painter.setBrush(QColor(102, 139, 117, 145))
            for index, size in enumerate((4, 6, 8)):
                painter.drawEllipse(277 + index * 8, 91 - index * 10, size, size)
        self.draw_bubble(painter)

    def draw_fox(self, painter, body, dark, cream, tail_wave):
        tail = QPainterPath()
        tail.moveTo(207, 287)
        tail.cubicTo(284 + tail_wave * 8, 286, 304 + tail_wave * 8, 208, 264, 187)
        tail.cubicTo(286, 242, 250, 312, 207, 317)
        painter.setBrush(body)
        painter.drawPath(tail)
        painter.setBrush(cream)
        painter.drawEllipse(int(260 + tail_wave * 5), 190, 31, 50)
        self.draw_torso(painter, body, cream, dark)
        painter.setBrush(dark)
        painter.drawPolygon(QPolygon([QPoint(101, 169), QPoint(113, 90), QPoint(151, 140)]))
        painter.drawPolygon(QPolygon([QPoint(223, 169), QPoint(211, 90), QPoint(173, 140)]))
        painter.setBrush(QColor("#f5b199"))
        painter.drawPolygon(QPolygon([QPoint(114, 149), QPoint(118, 108), QPoint(139, 141)]))
        painter.drawPolygon(QPolygon([QPoint(210, 149), QPoint(206, 108), QPoint(185, 141)]))
        painter.setBrush(body)
        head = QPainterPath()
        head.moveTo(104, 153)
        head.cubicTo(112, 123, 137, 111, 162, 112)
        head.cubicTo(187, 111, 212, 123, 220, 153)
        head.cubicTo(236, 185, 216, 218, 196, 228)
        head.lineTo(182, 242)
        head.lineTo(162, 232)
        head.lineTo(142, 242)
        head.lineTo(128, 228)
        head.cubicTo(108, 218, 88, 185, 104, 153)
        painter.drawPath(head)
        painter.setBrush(cream)
        muzzle = QPainterPath()
        muzzle.moveTo(112, 186)
        muzzle.cubicTo(122, 223, 151, 236, 162, 226)
        muzzle.cubicTo(173, 236, 202, 223, 212, 186)
        muzzle.cubicTo(189, 205, 181, 176, 162, 187)
        muzzle.cubicTo(143, 176, 135, 205, 112, 186)
        painter.drawPath(muzzle)

    def draw_cat(self, painter, body, dark, cream, tail_wave):
        painter.setPen(QPen(dark, 18, Qt.SolidLine, Qt.RoundCap))
        tail = QPainterPath()
        tail.moveTo(207, 304)
        tail.cubicTo(276, 310, 291 + tail_wave * 5, 229, 248, 210)
        painter.drawPath(tail)
        painter.setPen(Qt.NoPen)
        self.draw_torso(painter, body, cream, dark)
        painter.setBrush(body)
        painter.drawPolygon(QPolygon([QPoint(98, 170), QPoint(112, 101), QPoint(151, 142)]))
        painter.drawPolygon(QPolygon([QPoint(226, 170), QPoint(212, 101), QPoint(173, 142)]))
        painter.setBrush(QColor("#f0b29c"))
        painter.drawPolygon(QPolygon([QPoint(111, 151), QPoint(117, 118), QPoint(138, 143)]))
        painter.drawPolygon(QPolygon([QPoint(213, 151), QPoint(207, 118), QPoint(186, 143)]))
        painter.setBrush(body)
        head = QPainterPath()
        head.moveTo(100, 151)
        head.cubicTo(111, 122, 137, 112, 162, 112)
        head.cubicTo(187, 112, 213, 122, 224, 151)
        head.cubicTo(236, 184, 218, 220, 192, 232)
        head.cubicTo(177, 240, 147, 240, 132, 232)
        head.cubicTo(106, 220, 88, 184, 100, 151)
        painter.drawPath(head)
        painter.setBrush(dark)
        painter.drawEllipse(95, 137, 55, 45)
        painter.setBrush(cream)
        painter.drawEllipse(116, 182, 92, 57)

    def draw_dog(self, painter, body, dark, cream, tail_wave):
        painter.setPen(QPen(QColor("#ebb26b"), 17, Qt.SolidLine, Qt.RoundCap))
        tail = QPainterPath()
        tail.moveTo(207, 292)
        tail.cubicTo(268, 273, 276 + tail_wave * 7, 230, 248, 215)
        painter.drawPath(tail)
        painter.setPen(Qt.NoPen)
        self.draw_torso(painter, body, cream, dark)
        painter.setBrush(dark)
        left_ear = QPainterPath()
        left_ear.moveTo(116, 142)
        left_ear.cubicTo(84, 116, 71, 145, 80, 193)
        left_ear.cubicTo(84, 219, 109, 221, 123, 193)
        painter.drawPath(left_ear)
        right_ear = QPainterPath()
        right_ear.moveTo(208, 142)
        right_ear.cubicTo(240, 116, 253, 145, 244, 193)
        right_ear.cubicTo(240, 219, 215, 221, 201, 193)
        painter.drawPath(right_ear)
        painter.setBrush(body)
        painter.drawEllipse(94, 122, 136, 137)
        painter.setBrush(cream)
        painter.drawEllipse(111, 180, 102, 66)
        painter.setBrush(QColor("#f4d28f"))
        painter.drawEllipse(118, 135, 88, 44)

    def draw_torso(self, painter, body, cream, dark):
        painter.setPen(Qt.NoPen)
        painter.setBrush(body)
        torso = QPainterPath()
        torso.moveTo(128, 226)
        torso.cubicTo(108, 240, 105, 279, 111, 311)
        torso.cubicTo(116, 338, 133, 350, 162, 350)
        torso.cubicTo(191, 350, 208, 338, 213, 311)
        torso.cubicTo(219, 279, 216, 240, 196, 226)
        torso.cubicTo(179, 216, 145, 216, 128, 226)
        painter.drawPath(torso)
        painter.setBrush(QColor(cream.red(), cream.green(), cream.blue(), 172))
        painter.drawEllipse(132, 250, 60, 77)
        painter.setPen(QPen(dark, 8, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(136, 269, 133, 327)
        painter.drawLine(188, 269, 191, 327)
        painter.setPen(Qt.NoPen)
        painter.setBrush(cream)
        painter.drawEllipse(116, 321, 39, 25)
        painter.drawEllipse(169, 321, 39, 25)

    def draw_face(self, painter, dark, cream):
        eyes_y = 177
        closed = time.time() < self.blink_until or self.mood == "sleepy"
        painter.setPen(QPen(QColor("#443e38"), 4, Qt.SolidLine, Qt.RoundCap))
        if closed:
            painter.drawLine(133, eyes_y + 7, 145, eyes_y + 7)
            painter.drawLine(179, eyes_y + 7, 191, eyes_y + 7)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#453f39"))
            painter.drawEllipse(132, eyes_y, 15, 21)
            painter.drawEllipse(178, eyes_y, 15, 21)
            painter.setBrush(QColor("#fffdf3"))
            painter.drawEllipse(136, eyes_y + 3, 5, 6)
            painter.drawEllipse(182, eyes_y + 3, 5, 6)

        if self.mood in ("happy", "curious"):
            painter.setBrush(QColor(235, 119, 100, 105))
            painter.drawEllipse(113, 202, 20, 9)
            painter.drawEllipse(193, 202, 20, 9)
        painter.setBrush(QColor("#59463d"))
        painter.drawEllipse(157, 202, 11, 8)
        painter.setPen(QPen(QColor("#59463d"), 2, Qt.SolidLine, Qt.RoundCap))
        if self.mood == "concerned":
            painter.drawArc(153, 214, 20, 12, 10 * 16, 160 * 16)
        else:
            painter.drawArc(151, 208, 24, 18, 200 * 16, 140 * 16)

        if self.mood == "happy":
            painter.setPen(QPen(dark, 5, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(133, 269, 119, 281)
            painter.drawLine(191, 269, 205, 281)

    def draw_charm(self, painter):
        painter.setPen(QPen(QColor("#4f8666"), 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(162, 263, 162, 279)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#79a96a"))
        painter.drawEllipse(149, 265, 16, 10)
        painter.drawEllipse(162, 260, 17, 11)
        painter.setBrush(QColor("#e9bb58"))
        painter.drawEllipse(157, 276, 11, 11)

    def draw_glow(self, painter):
        sheen = QRadialGradient(126, 154, 64)
        sheen.setColorAt(0.0, QColor(255, 255, 255, 92))
        sheen.setColorAt(0.55, QColor(255, 255, 255, 18))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(sheen))
        painter.drawEllipse(96, 126, 125, 116)
        if self.mood in ("happy", "curious"):
            sparkle = 2 + int((math.sin(self.phase * 2) + 1) * 1.5)
            painter.setBrush(QColor(255, 239, 166, 190))
            for index in range(sparkle):
                x = 79 + index * 54
                y = 118 + (index % 2) * 26
                painter.drawEllipse(x, y, 5, 5)

    def draw_bubble(self, painter):
        if not self.bubble_visible or self.menu_visible:
            return
        rect = QRect(25, 14, 280, 72)
        painter.setPen(QPen(QColor(67, 92, 78, 45), 1))
        painter.setBrush(QColor(255, 253, 245, 244))
        painter.drawRoundedRect(rect, 8, 8)
        pointer = QPolygon([QPoint(146, 85), QPoint(160, 96), QPoint(174, 85)])
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(pointer)
        painter.setPen(QColor("#3d5048"))
        painter.setFont(QFont("Microsoft YaHei UI", 9))
        painter.drawText(rect.adjusted(13, 8, -13, -8), Qt.AlignCenter | Qt.TextWordWrap, self.bubble_text)


class YayanController:
    def __init__(self, app, settings):
        self.app = app
        self.settings = settings
        self.state = load_json(
            DESKTOP_STATE_PATH,
            {"animal": settings.get("default_animal", "watercolor"), "task": "", "next_step": "", "progress": 0},
        )
        self.client = YayanLLM(PROJECT_DIR)
        self.settings = self.client.settings
        self.messages = []
        self.workers = []
        self.chat_worker = None
        self.pet = PetWindow("watercolor")
        self.pet.action_requested.connect(self.handle_action)
        self.pet.animal_changed.connect(self.save_animal)
        self.chat_panel = ChatPanel()
        self.chat_panel.send_requested.connect(self.send_chat)
        self.chat_panel.cancel_requested.connect(self.cancel_chat)
        self.chat_panel.settings_requested.connect(lambda: self.handle_action("settings"))
        self.chat_panel.voice_requested.connect(self.toggle_recording)
        self.chat_panel.set_voice_input_enabled(self.settings.get("voice_input_enabled", False))
        self.settings_panel = SettingsPanel()
        self.settings_panel.save_requested.connect(self.save_settings)
        self.settings_panel.clear_key_requested.connect(self.clear_api_key)
        self.settings_panel.restart_requested.connect(self.restart_application)
        self.settings_panel.quit_requested.connect(self.app.quit)
        self.task_panel = TaskPanel(self.state)
        self.task_panel.changed.connect(self.save_task)
        self.focus_panel = FocusPanel()
        self.focus_panel.start_requested.connect(self.start_focus_session)
        self.focus_panel.pause_requested.connect(self.pause_focus_session)
        self.focus_panel.resume_requested.connect(self.resume_focus_session)
        self.focus_panel.finish_requested.connect(self.finish_focus_session)
        self.focus_review_panel = FocusReviewPanel(self.state)
        self.focus_review_panel.save_requested.connect(self.save_focus_review)
        self.focus_review_panel.dismiss_requested.connect(self.clear_focus_session)
        self._panels = (
            self.chat_panel,
            self.settings_panel,
            self.task_panel,
            self.focus_panel,
            self.focus_review_panel,
        )
        self.focus_recovery_error = False
        self.focus_session = self.load_focus_session()
        self.focus_timer = QTimer(self.pet)
        self.focus_timer.setInterval(1000)
        self.focus_timer.timeout.connect(self.update_focus_session)
        self.recorder = None
        self.pet.show()
        QTimer.singleShot(0, self.recover_focus_session)

    def place_panel(self, panel):
        for other in self._panels:
            if other is not panel:
                other.hide()
        screen = QApplication.screenAt(self.pet.geometry().center()) or QApplication.primaryScreen()
        bounds = screen.availableGeometry()
        x = self.pet.x() - panel.width() - 12
        if x < bounds.left():
            x = self.pet.x() + self.pet.width() + 12
        y = max(bounds.top() + 10, min(self.pet.y() - 30, bounds.bottom() - panel.height() - 10))
        panel.move(x, y)
        panel.show()
        panel.raise_()
        panel.activateWindow()

    def load_focus_session(self):
        if not FOCUS_STATE_PATH.exists():
            return None
        try:
            data = json.loads(FOCUS_STATE_PATH.read_text(encoding="utf-8-sig"))
            return FocusSession.from_dict(data)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.focus_recovery_error = True
            return None

    def save_focus_session(self):
        if self.focus_session is not None:
            save_json(FOCUS_STATE_PATH, self.focus_session.to_dict())

    def clear_focus_session(self):
        self.focus_timer.stop()
        self.focus_session = None
        self.focus_panel.set_session(None)
        try:
            FOCUS_STATE_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    def recover_focus_session(self):
        if self.focus_recovery_error:
            self.pet.say("上次的专注记录没有保存完整，我没有擅自恢复。", 4200)
            return
        if self.focus_session is None:
            return
        if self.focus_session.status == FocusSession.RUNNING:
            if self.focus_session.refresh():
                self.pet.say("上次的专注已经结束啦。要不要记录进展，由你决定。", 4200)
                self.clear_focus_session()
                return
            answer = QMessageBox.question(
                self.focus_panel,
                "继续上次的专注？",
                f"上次还有 {max(1, math.ceil(self.focus_session.remaining_seconds / 60))} 分钟。要继续吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                self.clear_focus_session()
                return
            self.focus_timer.start()
            self.focus_panel.set_session(self.focus_session)
            self.place_panel(self.focus_panel)
        elif self.focus_session.status == FocusSession.PAUSED:
            answer = QMessageBox.question(
                self.focus_panel,
                "保留上次暂停的专注？",
                "上次的专注停在暂停状态。要保留并由你稍后继续吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self.focus_panel.set_session(self.focus_session)
                self.place_panel(self.focus_panel)
            else:
                self.clear_focus_session()
        else:
            self.clear_focus_session()

    def show_focus_panel(self):
        self.focus_panel.set_session(self.focus_session)
        self.place_panel(self.focus_panel)

    def start_focus_session(self, duration_minutes):
        if self.focus_session is not None and self.focus_session.is_active:
            answer = QMessageBox.question(
                self.focus_panel,
                "重新开始专注？",
                "现在已有一段专注。要结束它，并按新时长重新开始吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self.focus_session = FocusSession.start(
            duration_minutes=duration_minutes,
            task=self.state.get("task", ""),
            next_step=self.state.get("next_step", ""),
            reminder_level=self.settings.get("reminder_strength", 2),
        )
        self.save_focus_session()
        self.focus_timer.start()
        self.focus_panel.set_session(self.focus_session)
        step = self.focus_session.next_step or self.focus_session.task or "眼前最小的那一步"
        self.pet.set_mood("happy")
        self.pet.say(
            f"好，我陪你守 {duration_minutes} 分钟。只碰“{step}”，不用一下做完。",
            4200,
        )

    def pause_focus_session(self):
        if self.focus_session is not None and self.focus_session.pause():
            self.save_focus_session()
            self.focus_panel.set_session(self.focus_session)
            self.pet.say("先停在这里。剩下的时间，我替你好好放着。", 3200)

    def resume_focus_session(self):
        if self.focus_session is not None and self.focus_session.resume():
            self.save_focus_session()
            self.focus_timer.start()
            self.focus_panel.set_session(self.focus_session)
            self.pet.say("好，我们从刚才停下的地方继续。", 2800)

    def finish_focus_session(self):
        if self.focus_session is None or not self.focus_session.finish(reason="manual"):
            return
        self.complete_focus_session()

    def update_focus_session(self):
        if self.focus_session is None or not self.focus_session.is_active:
            self.focus_timer.stop()
            return
        now = time.time()
        if self.focus_session.refresh(now):
            self.complete_focus_session()
            return
        due = self.focus_session.due_reminders(now)
        if due:
            self.save_focus_session()
            if FocusSession.should_present_reminder(self.pet.quiet):
                remaining = max(1, math.ceil(self.focus_session.remaining_seconds / 60))
                self.pet.say(f"轻轻看一眼就好，还剩大约 {remaining} 分钟。", 3000)
        self.focus_panel.set_session(self.focus_session)

    def complete_focus_session(self):
        self.focus_timer.stop()
        self.save_focus_session()
        self.focus_panel.set_session(self.focus_session)
        message = "这一小段到啦。先看看刚才留下了什么，再决定要不要继续。"
        self.pet.set_mood("happy")
        if FocusSession.should_present_reminder(self.pet.quiet, final=True):
            self.pet.say(message, 4500)
        if self.settings.get("speak_replies", True) and self.client.configured:
            self.start_worker("tts", message)
        self.focus_review_panel.load_state(self.state)
        self.place_panel(self.focus_review_panel)

    def save_focus_review(self, values):
        self.state.update(values)
        save_json(DESKTOP_STATE_PATH, self.state)
        self.task_panel.step.setText(self.state.get("next_step", ""))
        self.task_panel.progress.setValue(int(self.state.get("progress", 0)))
        self.clear_focus_session()
        self.pet.say("记下啦。留下多少都算你真实走过的路。", 3400)

    def handle_action(self, action):
        if action == "chat":
            self.place_panel(self.chat_panel)
            self.chat_panel.input.setFocus()
        elif action == "task":
            self.place_panel(self.task_panel)
        elif action == "focus":
            self.show_focus_panel()
        elif action == "quiet":
            self.pet.quiet = not self.pet.quiet
            self.pet.set_mood("sleepy" if self.pet.quiet else "idle")
            self.pet.say("好，我先蜷在这里，不探头。" if self.pet.quiet else "我醒着啦，还是轻轻的。", 2500)
        elif action == "settings":
            self.show_settings()
        elif action == "quit":
            self.app.quit()

    def save_animal(self, animal):
        self.state["animal"] = animal
        save_json(DESKTOP_STATE_PATH, self.state)

    def save_task(self, task_state):
        self.state.update(task_state)
        save_json(DESKTOP_STATE_PATH, self.state)
        self.pet.say("记住啦。不是催你，是替你把线头放在看得见的地方。", 3300)

    def context(self):
        return {
            "current_task": self.state.get("task", ""),
            "next_step": self.state.get("next_step", ""),
            "progress_percent": self.state.get("progress", 0),
            "animal_form": self.pet.COLORS[self.pet.animal]["name"],
            "permission_boundary": "工作文件只读；建议不能替代用户决定",
            "interaction_style": self.settings.get("interaction_style", "gentle"),
            "reminder_strength": self.settings.get("reminder_strength", 2),
            "memory_mode": self.settings.get("memory_mode", "graded"),
        }

    def send_chat(self, text):
        self.chat_panel.add_message("你", text)
        self.messages.append({"role": "user", "content": text})
        self.chat_panel.start_streaming_message()
        self.chat_panel.set_busy(True)
        self.pet.set_mood("thinking")
        self.pet.say("嗯……让我认真听一下。", 1800)
        self.start_worker(
            "chat",
            select_recent_messages(self.messages),
            self.context(),
        )

    def start_worker(self, mode, payload, context=None):
        worker = WorkThread(self.client, mode, payload, context)
        worker.completed.connect(
            lambda worker_mode, result, ref=worker: self.worker_completed(ref, worker_mode, result)
        )
        worker.failed.connect(
            lambda worker_mode, error, ref=worker: self.worker_failed(ref, worker_mode, error)
        )
        worker.chunk.connect(
            lambda worker_mode, text, ref=worker: self.worker_chunk(ref, worker_mode, text)
        )
        worker.cancelled.connect(
            lambda worker_mode, text, ref=worker: self.worker_cancelled(ref, worker_mode, text)
        )
        worker.finished.connect(lambda: self.release_worker(worker))
        self.workers.append(worker)
        if mode == "chat":
            self.chat_worker = worker
        worker.start()

    def release_worker(self, worker):
        if worker in self.workers:
            self.workers.remove(worker)
        worker.deleteLater()

    def cancel_chat(self):
        if self.chat_worker is None:
            return
        worker = self.chat_worker
        worker.cancel()
        self.chat_worker = None
        self.chat_panel.finish_streaming_message(stopped=True, eligible=False)
        self.chat_panel.set_busy(False)
        self.pet.set_mood("idle")

    def worker_chunk(self, worker, mode, text):
        if mode == "chat" and worker is self.chat_worker:
            self.chat_panel.append_streaming_text(text)

    def worker_completed(self, worker, mode, result):
        if mode == "chat":
            if worker is not self.chat_worker:
                return
            self.chat_worker = None
            self.messages.append({"role": "assistant", "content": result})
            self.chat_panel.finish_streaming_message(result, eligible=True)
            self.chat_panel.set_busy(False)
            self.pet.set_mood("happy")
            QTimer.singleShot(1200, lambda: self.pet.set_mood("idle"))
            if self.settings.get("speak_replies", True):
                self.start_worker("tts", result)
        elif mode == "tts":
            QSound.play(result)
        elif mode == "stt":
            self.chat_panel.input.setText(result)
            self.chat_panel.input.setFocus()

    def worker_cancelled(self, worker, mode, partial_text):
        if mode == "chat" and worker is self.chat_worker:
            self.chat_worker = None
            self.chat_panel.finish_streaming_message(stopped=True, eligible=False)
            self.chat_panel.set_busy(False)
            self.pet.set_mood("idle")

    def worker_failed(self, worker, mode, error):
        if mode == "chat":
            if worker is not self.chat_worker:
                return
            self.chat_worker = None
            self.chat_panel.finish_streaming_message(error, eligible=False)
            self.chat_panel.set_busy(False)
            self.pet.set_mood("concerned")
            self.pet.say("我还没接上真正的大脑。设置好本机模型后，我再认真回答你。", 4200)
        elif mode == "tts":
            # Chat succeeded; a chat-only provider must not turn that into a false failure.
            self.client.save_user_settings({"speak_replies": False})
            self.settings = self.client.settings
            self.settings_panel.speak_replies.setChecked(False)
            self.pet.set_mood("concerned")
            self.pet.say("文字聊天没问题。语音服务没有接上，我先不自动朗读。", 4200)
            QTimer.singleShot(1200, lambda: self.pet.set_mood("idle"))
        elif mode == "stt":
            self.chat_panel.add_message("芽砚", error, True)
            self.chat_panel.mic.setEnabled(False)
            self.chat_panel.mic.setText("语音暂不可用")
            self.pet.set_mood("concerned")

    def toggle_recording(self, active):
        if active:
            try:
                RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
                self.recorder = QAudioRecorder(self.chat_panel)
                settings = QAudioEncoderSettings()
                settings.setCodec("audio/pcm")
                settings.setSampleRate(16000)
                settings.setChannelCount(1)
                settings.setQuality(QMultimedia.NormalQuality)
                self.recorder.setEncodingSettings(settings)
                self.recorder.setContainerFormat("audio/x-wav")
                self.recorder.setOutputLocation(QUrl.fromLocalFile(str(AUDIO_INPUT_PATH)))
                self.recorder.record()
                self.pet.set_mood("curious")
                self.pet.say("嗯，我听着。", 1800)
            except Exception as error:
                self.chat_panel.add_message("芽砚", f"麦克风没有准备好：{error}", True)
        elif self.recorder:
            self.recorder.stop()
            self.pet.set_mood("thinking")
            QTimer.singleShot(450, lambda: self.start_worker("stt", str(AUDIO_INPUT_PATH)))

    def show_settings(self):
        self.settings_panel.load_values(self.settings)
        self.place_panel(self.settings_panel)

    def save_settings(self, values, api_key):
        try:
            self.client.save_user_settings(values)
            if api_key.strip():
                self.client.save_api_key(api_key)
            self.client.reload_settings()
            self.settings = self.client.settings
            self.chat_panel.set_voice_input_enabled(
                self.settings.get("voice_input_enabled", False)
            )
            self.pet.set_mood("happy")
            QTimer.singleShot(1100, lambda: self.pet.set_mood("idle"))
        except Exception as error:
            QMessageBox.warning(self.settings_panel, "设置没有保存", str(error))

    def clear_api_key(self):
        try:
            self.client.clear_api_key()
            self.client.reload_settings()
            self.settings = self.client.settings
            self.settings_panel.api_key.clear()
            self.settings_panel.api_key.setPlaceholderText("没有已保存的密钥")
        except Exception as error:
            QMessageBox.warning(self.settings_panel, "密钥没有移除", str(error))

    def restart_application(self):
        result = QProcess.startDetached(
            sys.executable,
            [str(Path(__file__).resolve()), "--restart-delay"],
            str(PROJECT_DIR),
        )
        started = result[0] if isinstance(result, tuple) else bool(result)
        if not started:
            QMessageBox.warning(self.settings_panel, "芽砚没有重启", "无法启动新的芽砚进程。")
            return
        self.app.quit()


def send_instance_command(command):
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE_NAME)
    if not socket.waitForConnected(350):
        return False
    socket.write(command.encode("utf-8"))
    socket.flush()
    if not socket.waitForBytesWritten(350):
        socket.disconnectFromServer()
        return False
    if not socket.waitForReadyRead(500):
        socket.disconnectFromServer()
        return False
    acknowledged = bytes(socket.readAll()).decode("utf-8", errors="ignore") == "ok"
    socket.disconnectFromServer()
    return acknowledged


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quit", action="store_true")
    parser.add_argument("--render-preview")
    parser.add_argument("--animal", choices=["watercolor"])
    parser.add_argument("--restart-delay", action="store_true")
    args = parser.parse_args()

    if args.restart_delay:
        time.sleep(0.8)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("芽砚")
    # Every visible surface is a Qt.Tool window, so explicit IPC owns shutdown.
    app.setQuitOnLastWindowClosed(False)
    log_startup("application-created", render_preview=bool(args.render_preview), quit=args.quit)

    if args.quit:
        log_startup("quit-request", delivered=send_instance_command("quit"))
        return 0

    instance_lock = None
    if not args.render_preview:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        instance_lock = QLockFile(str(INSTANCE_LOCK_PATH))
        if not instance_lock.tryLock(0):
            existing_instance = send_instance_command("raise")
            log_startup("existing-instance-check", reachable=existing_instance)
            if existing_instance:
                return 0
            # A previous process can exit between creating the lock and
            # registering the IPC server. Let Qt remove the lock only when it
            # can verify that the recorded owner is no longer running, then
            # retry once so a stale lock cannot permanently block startup.
            stale_removed = instance_lock.removeStaleLockFile()
            log_startup("stale-lock-check", removed=stale_removed)
            if not stale_removed or not instance_lock.tryLock(0):
                return 1

    server = QLocalServer()
    if not args.render_preview:
        # Only the process holding the lock may clean up a stale socket name.
        QLocalServer.removeServer(INSTANCE_NAME)
        # Claim the single-instance channel atomically. Never remove an
        # active server: doing so creates a race where two launchers both
        # believe they are the primary instance.
        listening = server.listen(INSTANCE_NAME)
        log_startup("ipc-listen", listening=listening)
        if not listening:
            raised = send_instance_command("raise")
            log_startup("duplicate-instance", raised=raised)
            return 0

    settings = load_json(PROJECT_DIR / "desktop" / "settings.json", {})
    if args.animal:
        settings["default_animal"] = args.animal
    controller = YayanController(app, settings)
    log_startup("controller-visible", visible=controller.pet.isVisible())

    def handle_connection():
        socket = server.nextPendingConnection()
        if not socket.waitForReadyRead(300):
            return
        command = bytes(socket.readAll()).decode("utf-8", errors="ignore")
        socket.write(b"ok")
        socket.flush()
        socket.waitForBytesWritten(300)
        if command == "quit":
            app.quit()
        else:
            controller.pet.show()
            controller.pet.raise_()

    server.newConnection.connect(handle_connection)

    if args.render_preview:
        controller.pet.move(0, 0)
        controller.pet.say(f"你好呀，我是{controller.pet.COLORS[controller.pet.animal]['name']}芽砚。", 8000)
        def capture_preview():
            controller.pet.grab().save(args.render_preview)
            app.quit()

        QTimer.singleShot(240, capture_preview)
        app.exec_()
        return 0

    exit_code = app.exec_()
    log_startup("event-loop-exit", exit_code=exit_code)
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        (RUNTIME_DIR / "desktop-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        ctypes.windll.user32.MessageBoxW(None, str(error), "芽砚没有启动", 0x10)
        raise
