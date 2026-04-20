"""Dialog that captures a keyboard shortcut by pressing it."""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent

_MODIFIERS = {
    Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
    Qt.Key.Key_Meta, Qt.Key.Key_AltGr,
}

_KEY_NAMES = {
    Qt.Key.Key_Return:          "enter",
    Qt.Key.Key_Enter:           "enter",
    Qt.Key.Key_Space:           "space",
    Qt.Key.Key_Escape:          "esc",
    Qt.Key.Key_Tab:             "tab",
    Qt.Key.Key_Backspace:       "backspace",
    Qt.Key.Key_Delete:          "delete",
    Qt.Key.Key_Home:            "home",
    Qt.Key.Key_End:             "end",
    Qt.Key.Key_PageUp:          "page_up",
    Qt.Key.Key_PageDown:        "page_down",
    Qt.Key.Key_Up:              "up",
    Qt.Key.Key_Down:            "down",
    Qt.Key.Key_Left:            "left",
    Qt.Key.Key_Right:           "right",
    Qt.Key.Key_F1:  "f1",  Qt.Key.Key_F2:  "f2",  Qt.Key.Key_F3:  "f3",
    Qt.Key.Key_F4:  "f4",  Qt.Key.Key_F5:  "f5",  Qt.Key.Key_F6:  "f6",
    Qt.Key.Key_F7:  "f7",  Qt.Key.Key_F8:  "f8",  Qt.Key.Key_F9:  "f9",
    Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
    Qt.Key.Key_MediaPlay:       "media_play_pause",
    Qt.Key.Key_MediaNext:       "media_next",
    Qt.Key.Key_MediaPrevious:   "media_previous",
    Qt.Key.Key_VolumeUp:        "media_volume_up",
    Qt.Key.Key_VolumeDown:      "media_volume_down",
    Qt.Key.Key_VolumeMute:      "media_volume_mute",
}


def _qt_key_to_str(key: Qt.Key) -> str | None:
    if key in _KEY_NAMES:
        return _KEY_NAMES[key]
    code = int(key)
    if 0x41 <= code <= 0x5A:
        return chr(code).lower()
    if 0x30 <= code <= 0x39:
        return chr(code)
    return None


class KeyRecorderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Grabar atajo")
        self.setFixedSize(320, 140)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.result_combo: str = ""
        self._main_key: Qt.Key | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        hint = QLabel("Presioná la combinación de teclas")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self._preview = QLabel("—")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._preview.font()
        font.setPointSize(14)
        font.setBold(True)
        self._preview.setFont(font)
        layout.addWidget(self._preview)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Aceptar")
        btn_cancel = QPushButton("Cancelar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def showEvent(self, event):
        super().showEvent(event)
        self.grabKeyboard()

    def closeEvent(self, event):
        self.releaseKeyboard()
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        key = Qt.Key(event.key())
        if key in _MODIFIERS:
            return

        mods = event.modifiers()
        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("cmd")

        key_str = _qt_key_to_str(key)
        if key_str:
            parts.append(key_str)
            self._main_key = key
            self.result_combo = "+".join(parts)
            self._preview.setText(self.result_combo)

    def keyReleaseEvent(self, event: QKeyEvent):
        if Qt.Key(event.key()) == self._main_key and self.result_combo:
            self.accept()
