"""QThread que lee eventos BTN del Pico por USB serial (puerto consola)."""
import serial
import serial.tools.list_ports
from PyQt6.QtCore import QThread, pyqtSignal

from ..events import ButtonEvent

BAUD_RATE = 115200

# VIDs reconocidos: Raspberry Pi Foundation y Adafruit (CircuitPython)
_PICO_VIDS = {0x2E8A, 0x239A}


def _is_pico(port_info) -> bool:
    return port_info.vid in _PICO_VIDS


def list_ports() -> list[tuple[str, str]]:
    """Devuelve lista de (device, label) con puertos Pico primero."""
    all_ports = serial.tools.list_ports.comports()
    result = []
    for p in sorted(all_ports, key=lambda x: x.device):
        label = p.device
        if p.description and p.description != "n/a":
            label = f"{p.device} — {p.description}"
        result.append((p.device, label, _is_pico(p)))
    # Pico primero
    result.sort(key=lambda x: (not x[2], x[0]))
    return [(dev, label) for dev, label, _ in result]


def auto_detect_port() -> str | None:
    for p in sorted(serial.tools.list_ports.comports(), key=lambda x: x.device):
        if _is_pico(p):
            return p.device
    return None


class SerialWorker(QThread):
    button_event = pyqtSignal(int, str)  # (button_id 1-6, event_type str)
    connected    = pyqtSignal(str)       # port name
    disconnected = pyqtSignal(str)       # mensaje de error (vacío = parada limpia)

    def __init__(self, port: str, parent=None):
        super().__init__(parent)
        self.port     = port
        self._running = True

    def run(self):
        try:
            with serial.Serial(self.port, BAUD_RATE, timeout=1) as ser:
                self.connected.emit(self.port)
                while self._running:
                    try:
                        raw = ser.readline()
                    except serial.SerialException as exc:
                        self.disconnected.emit(str(exc))
                        return
                    if not raw:
                        continue
                    line  = raw.decode("utf-8", errors="ignore").strip()
                    event = ButtonEvent.parse(line)
                    if event:
                        self.button_event.emit(event.button_id, event.event_type.value)
        except serial.SerialException as exc:
            self.disconnected.emit(str(exc))

    def stop(self):
        self._running = False
        self.wait()
