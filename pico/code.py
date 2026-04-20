"""
ButtonBox firmware — CircuitPython
Protocolo: BTN:<id>:<EVENT>\n   (EVENT = PRESS | HOLD | RELEASE | RELEASE_AFTER_HOLD)
Los botones están en GP5-GP10 con pull-down (activo HIGH al presionar).
"""
import time
import board
import digitalio

BUTTON_PINS = [
    (board.GP5,  1),
    (board.GP6,  2),
    (board.GP7,  3),
    (board.GP8,  4),
    (board.GP9,  5),
    (board.GP10, 6),
]

DEBOUNCE_MS       = 20
HOLD_THRESHOLD_MS = 800
POLL_INTERVAL_S   = 0.005


class Button:
    def __init__(self, pin, button_id: int):
        self.id = button_id
        self.io = digitalio.DigitalInOut(pin)
        self.io.direction = digitalio.Direction.INPUT
        self.io.pull = digitalio.Pull.DOWN

        self._state       = False
        self._last_change = 0.0
        self._pressed_at  = 0.0
        self._hold_sent   = False

    def update(self, now_ms: float) -> list:
        raw    = self.io.value
        events = []

        if raw != self._state:
            if (now_ms - self._last_change) >= DEBOUNCE_MS:
                self._last_change = now_ms
                self._state = raw
                if raw:
                    self._pressed_at = now_ms
                    self._hold_sent  = False
                    events.append("PRESS")
                else:
                    events.append("RELEASE_AFTER_HOLD" if self._hold_sent else "RELEASE")

        if self._state and not self._hold_sent:
            if (now_ms - self._pressed_at) >= HOLD_THRESHOLD_MS:
                self._hold_sent = True
                events.append("HOLD")

        return events


buttons = [Button(pin, bid) for pin, bid in BUTTON_PINS]

print("READY")

while True:
    now = time.monotonic() * 1000
    for btn in buttons:
        for ev in btn.update(now):
            print(f"BTN:{btn.id}:{ev}")
    time.sleep(POLL_INTERVAL_S)
