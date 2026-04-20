"""Main application window."""
import logging
from pathlib import Path
from PyQt6 import uic
from PyQt6.QtWidgets import (
    QMainWindow, QLabel, QApplication,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSystemTrayIcon, QMenu,
    QHBoxLayout, QComboBox, QPushButton,
    QInputDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter

from ..config import ConfigManager
from ..actions.base import build_action
from .action_widget import ActionWidget
from .serial_worker import SerialWorker, list_ports, auto_detect_port

log = logging.getLogger(__name__)

BUTTON_IDS = list(range(1, 7))

_IDLE   = "background:#3c3f41;color:#aaa;border-radius:8px;padding:4px;"
_PRESS  = "background:#4caf50;color:#fff;border-radius:8px;padding:4px;font-weight:bold;"
_HOLD   = "background:#ff9800;color:#fff;border-radius:8px;padding:4px;font-weight:bold;"


class ButtonIndicator(QLabel):
    def __init__(self, bid: int, name: str, parent=None):
        super().__init__(f"[{bid}]\n{name}", parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(56)
        self.setStyleSheet(_IDLE)

    def set_state(self, state: str):
        if state == "PRESS":
            self.setStyleSheet(_PRESS)
        elif state == "HOLD":
            self.setStyleSheet(_HOLD)
        else:
            self.setStyleSheet(_IDLE)

    def update_name(self, name: str):
        bid = self.text().split("\n")[0]
        self.setText(f"{bid}\n{name}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._worker: SerialWorker | None = None
        self._cfg = ConfigManager()
        self._indicators: dict[int, ButtonIndicator] = {}
        self._action_widgets: dict[int, tuple[ActionWidget, ActionWidget]] = {}

        uic.loadUi(Path(__file__).parent / 'ui' / 'main_window.ui', self)
        self.btn_refresh.clicked.connect(self._refresh_ports)
        self.btn_connect.clicked.connect(self._toggle_connection)
        self.btn_save.clicked.connect(self._save_config)
        self.nav_list.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)
        self.nav_list.setCurrentRow(0)
        self._populate_indicators()
        self._setup_profiles()
        self._setup_table()
        self._refresh_ports()
        self._setup_tray()
        self._set_status("Desconectado")
        QTimer.singleShot(200, self._auto_connect)

    # ── Build UI ─────────────────────────────────────────────────────────────

    def _populate_indicators(self):
        layout = self.indicator_frame.layout()
        for bid in BUTTON_IDS:
            name = self._cfg.get_button(bid).get("name", f"Button {bid}")
            ind = ButtonIndicator(bid, name)
            self._indicators[bid] = ind
            layout.addWidget(ind)

    def _setup_table(self):
        self.table.setRowCount(len(BUTTON_IDS))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked |
                                   QAbstractItemView.EditTrigger.SelectedClicked)

        for row, bid in enumerate(BUTTON_IDS):
            btn_cfg = self._cfg.get_button(bid)

            name_item = QTableWidgetItem(btn_cfg.get("name", f"Button {bid}"))
            self.table.setItem(row, 0, name_item)

            press_w = ActionWidget()
            press_w.set_config(btn_cfg.get("press"))
            self.table.setCellWidget(row, 1, press_w)

            hold_w = ActionWidget()
            hold_w.set_config(btn_cfg.get("hold"))
            self.table.setCellWidget(row, 2, hold_w)

            self._action_widgets[bid] = (press_w, hold_w)

        self.table.resizeRowsToContents()

    # ── Profiles ──────────────────────────────────────────────────────────────

    def _setup_profiles(self):
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Perfil:"))

        self.profile_combo = QComboBox()
        self.profile_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        bar.addWidget(self.profile_combo)

        btn_new    = QPushButton("+")
        btn_rename = QPushButton("✎")
        btn_delete = QPushButton("✕")
        for btn in (btn_new, btn_rename, btn_delete):
            btn.setFixedWidth(28)
            bar.addWidget(btn)
        bar.addStretch()

        btn_new.clicked.connect(self._new_profile)
        btn_rename.clicked.connect(self._rename_profile)
        btn_delete.clicked.connect(self._delete_profile)

        self.page_macros.layout().insertLayout(0, bar)

        self._refresh_profile_combo()
        self.profile_combo.currentTextChanged.connect(self._on_profile_changed)

    def _refresh_profile_combo(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for name in self._cfg.list_profiles():
            self.profile_combo.addItem(name)
        current = self._cfg.get_current_profile()
        idx = self.profile_combo.findText(current)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)
        self.profile_combo.blockSignals(False)

    def _on_profile_changed(self, name: str):
        if not name:
            return
        self._cfg.set_current_profile(name)
        self._reload_table()

    def _reload_table(self):
        for row, bid in enumerate(BUTTON_IDS):
            btn_cfg = self._cfg.get_button(bid)
            name_item = self.table.item(row, 0)
            if name_item:
                name_item.setText(btn_cfg.get("name", f"Button {bid}"))
            else:
                self.table.setItem(row, 0, QTableWidgetItem(btn_cfg.get("name", f"Button {bid}")))
            press_w, hold_w = self._action_widgets[bid]
            press_w.set_config(btn_cfg.get("press"))
            hold_w.set_config(btn_cfg.get("hold"))
        self.table.resizeRowsToContents()

    def _new_profile(self):
        name, ok = QInputDialog.getText(self, "Nuevo perfil", "Nombre del perfil:")
        if not ok or not name.strip():
            return
        name = name.strip()
        try:
            self._cfg.create_profile(name)
        except ValueError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._refresh_profile_combo()
        self.profile_combo.setCurrentText(name)

    def _rename_profile(self):
        old = self._cfg.get_current_profile()
        name, ok = QInputDialog.getText(self, "Renombrar perfil", "Nuevo nombre:", text=old)
        if not ok or not name.strip() or name.strip() == old:
            return
        name = name.strip()
        try:
            self._cfg.rename_profile(old, name)
        except ValueError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._refresh_profile_combo()

    def _delete_profile(self):
        name = self._cfg.get_current_profile()
        reply = QMessageBox.question(
            self, "Eliminar perfil",
            f"¿Eliminar el perfil «{name}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._cfg.delete_profile(name)
        except ValueError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._refresh_profile_combo()
        self._reload_table()

    # ── Tray ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _make_tray_icon(color: str) -> QIcon:
        px = QPixmap(22, 22)
        px.fill(QColor(0, 0, 0, 0))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(2, 2, 18, 18, 4, 4)
        p.end()
        return QIcon(px)

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._icon_connected    = self._make_tray_icon("#4caf50")
        self._icon_disconnected = self._make_tray_icon("#9e9e9e")

        self._tray = QSystemTrayIcon(self._icon_disconnected, self)
        self._tray.setToolTip("ButtonBox — Desconectado")

        menu = QMenu()
        menu.addAction("Mostrar / Ocultar").triggered.connect(self._toggle_visibility)
        menu.addSeparator()
        menu.addAction("Salir").triggered.connect(self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _update_tray_icon(self, connected: bool) -> None:
        if not hasattr(self, '_tray'):
            return
        if connected:
            self._tray.setIcon(self._icon_connected)
            self._tray.setToolTip("ButtonBox — Conectado")
        else:
            self._tray.setIcon(self._icon_disconnected)
            self._tray.setToolTip("ButtonBox — Desconectado")

    def _toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self._toggle_visibility()

    def _quit(self):
        self._disconnect(silent=True)
        QApplication.quit()

    # ── Serial ───────────────────────────────────────────────────────────────

    def _refresh_ports(self):
        prev_device = self.port_combo.currentData()
        self.port_combo.clear()
        ports = list_ports()
        if ports:
            for device, label in ports:
                self.port_combo.addItem(label, userData=device)
            if prev_device:
                idx = next((i for i in range(self.port_combo.count())
                            if self.port_combo.itemData(i) == prev_device), 0)
                self.port_combo.setCurrentIndex(idx)
        else:
            self.port_combo.addItem("(sin puertos)", userData=None)

    def _toggle_connection(self):
        if self._worker and self._worker.isRunning():
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.port_combo.currentData()
        if not port:
            self._set_status("Seleccioná un puerto válido")
            return
        self._worker = SerialWorker(port)
        self._worker.button_event.connect(self._on_button_event)
        self._worker.connected.connect(self._on_connected)
        self._worker.disconnected.connect(self._on_disconnected)
        self._worker.start()

    def _disconnect(self, silent: bool = False):
        if self._worker:
            self._worker.stop()
            self._worker = None
        self.btn_connect.setText("Conectar")
        self._update_tray_icon(False)
        if not silent:
            self._set_status("Desconectado")
        for ind in self._indicators.values():
            ind.set_state("IDLE")

    def _auto_connect(self):
        port = auto_detect_port()
        if not port:
            return
        for i in range(self.port_combo.count()):
            if self.port_combo.itemData(i) == port:
                self.port_combo.setCurrentIndex(i)
                break
        self._connect()

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_connected(self, port: str):
        import shutil
        from ..actions.keyboard_action import _on_wayland
        self.btn_connect.setText("Desconectar")
        self._update_tray_icon(True)
        if _on_wayland() and not shutil.which("ydotool") and not shutil.which("xdotool"):
            self._set_status(
                "Conectado — AVISO: Wayland detectado sin ydotool/xdotool; los atajos de teclado no funcionarán. "
                "Instalar: sudo dnf install ydotool && systemctl --user enable --now ydotool",
                timeout=15000,
            )
        else:
            self._set_status(f"Conectado a {port}")

    def _on_disconnected(self, error: str):
        self.btn_connect.setText("Conectar")
        self._update_tray_icon(False)
        msg = f"Desconectado: {error}" if error else "Desconectado"
        self._set_status(msg)
        self._worker = None
        for ind in self._indicators.values():
            ind.set_state("IDLE")

    def _on_button_event(self, bid: int, event_type: str):
        if bid in self._indicators:
            self._indicators[bid].set_state(event_type)
            if event_type in ("RELEASE", "RELEASE_AFTER_HOLD"):
                QTimer.singleShot(120, lambda: self._indicators[bid].set_state("IDLE"))

        if event_type in ("PRESS", "HOLD"):
            event_key = "press" if event_type == "PRESS" else "hold"
            action_cfg = self._cfg.get_button(bid).get(event_key)
            if action_cfg:
                try:
                    action = build_action(action_cfg)
                    if action:
                        import threading
                        threading.Thread(target=action.execute, daemon=True).start()
                except Exception as exc:
                    log.error("Action error [BTN%s %s]: %s", bid, event_key, exc)
                    self._set_status(f"Error BTN{bid}: {exc}", timeout=5000)

    # ── Config ───────────────────────────────────────────────────────────────

    def _save_config(self):
        for row, bid in enumerate(BUTTON_IDS):
            name_item = self.table.item(row, 0)
            name = name_item.text() if name_item else f"Button {bid}"
            press_w, hold_w = self._action_widgets[bid]

            self._cfg.set_button_name(bid, name)
            self._cfg.set_button_action(bid, "press",   press_w.get_config())
            self._cfg.set_button_action(bid, "hold",    hold_w.get_config())

            if bid in self._indicators:
                self._indicators[bid].update_name(name)

        self._set_status("Configuración guardada", timeout=3000)

    def _set_status(self, msg: str, timeout: int = 0):
        self.status_bar.showMessage(msg, timeout)

    def closeEvent(self, event):
        if hasattr(self, '_tray') and self._tray.isVisible():
            self.hide()
            event.ignore()
        else:
            self._disconnect(silent=True)
            event.accept()
