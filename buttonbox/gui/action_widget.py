"""Inline widget for configuring a single action (type + value)."""
from pathlib import Path
from PyQt6 import uic
from PyQt6.QtWidgets import QWidget, QComboBox, QLineEdit
from PyQt6.QtCore import pyqtSignal

ACTION_TYPES = ["(ninguna)", "keyboard", "command", "script", "http"]

_PLACEHOLDERS = {
    "keyboard": "ej: ctrl+c  /  ctrl+shift+f5  /  media_play_pause",
    "command":  "ej: notify-send 'Hola'  /  calc.exe",
    "script":   "ej: /home/user/script.py  /  C:\\scripts\\run.ps1",
    "http":     "ej: http://homeassistant.local:8123/api/services/light/toggle",
}


def action_to_cfg(action_type: str, value: str) -> dict | None:
    """Convert GUI fields to a config dict understood by the action registry."""
    if action_type == "(ninguna)" or not value.strip():
        return None
    if action_type == "keyboard":
        keys = [k.strip() for k in value.replace("+", " ").split() if k.strip()]
        return {"type": "keyboard", "keys": keys}
    if action_type == "command":
        return {"type": "command", "command": value.strip(), "background": True}
    if action_type == "script":
        return {"type": "script", "path": value.strip()}
    if action_type == "http":
        return {"type": "http", "url": value.strip(), "method": "GET"}
    return None


def cfg_to_action(cfg: dict | None) -> tuple[str, str]:
    """Convert a config dict back to (action_type, value_str)."""
    if not cfg:
        return "(ninguna)", ""
    t = cfg.get("type", "")
    if t == "keyboard":
        return "keyboard", "+".join(cfg.get("keys", []))
    if t == "command":
        return "command", cfg.get("command", "")
    if t == "script":
        return "script", cfg.get("path", "")
    if t == "http":
        return "http", cfg.get("url", "")
    return "(ninguna)", ""


class ActionWidget(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(Path(__file__).parent / 'ui' / 'action_widget.ui', self)
        self.type_combo.addItems(ACTION_TYPES)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        self.value_edit.textChanged.connect(self.changed)
        self.btn_record.clicked.connect(self._record_shortcut)

    def _on_type_changed(self, t: str):
        self.value_edit.setPlaceholderText(_PLACEHOLDERS.get(t, ""))
        self.value_edit.setEnabled(t != "(ninguna)")
        self.btn_record.setVisible(t == "keyboard")
        self.changed.emit()

    def _record_shortcut(self):
        from .key_recorder import KeyRecorderDialog
        dlg = KeyRecorderDialog(self)
        if dlg.exec() and dlg.result_combo:
            self.value_edit.setText(dlg.result_combo)

    def get_config(self) -> dict | None:
        return action_to_cfg(self.type_combo.currentText(), self.value_edit.text())

    def set_config(self, cfg: dict | None):
        t, v = cfg_to_action(cfg)
        self.type_combo.setCurrentText(t)
        self.value_edit.setText(v)
        self.value_edit.setEnabled(t != "(ninguna)")
        self.value_edit.setPlaceholderText(_PLACEHOLDERS.get(t, ""))
