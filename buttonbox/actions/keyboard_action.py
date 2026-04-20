import logging
import os
import platform
import shutil
import subprocess
import threading
import time

from pynput.keyboard import Controller, Key
from .base import BaseAction, register_action

log = logging.getLogger(__name__)

_SPECIAL: dict = {
    "ctrl":        Key.ctrl,   "ctrl_l":    Key.ctrl_l,  "ctrl_r":    Key.ctrl_r,
    "alt":         Key.alt,    "alt_l":     Key.alt_l,   "alt_gr":    Key.alt_gr,
    "shift":       Key.shift,  "shift_l":   Key.shift_l, "shift_r":   Key.shift_r,
    "super":       Key.cmd,    "win":       Key.cmd,     "cmd":       Key.cmd,
    "enter":       Key.enter,  "return":    Key.enter,
    "space":       Key.space,  "tab":       Key.tab,
    "esc":         Key.esc,    "escape":    Key.esc,
    "backspace":   Key.backspace, "delete": Key.delete,  "insert":    Key.insert,
    "up":          Key.up,     "down":      Key.down,    "left":      Key.left,
    "right":       Key.right,  "home":      Key.home,    "end":       Key.end,
    "page_up":     Key.page_up, "page_down": Key.page_down,
    "caps_lock":   Key.caps_lock, "num_lock": Key.num_lock,
    "print_screen": Key.print_screen,
    "media_play_pause":  Key.media_play_pause,
    "media_next":        Key.media_next,
    "media_previous":    Key.media_previous,
    "media_volume_up":   Key.media_volume_up,
    "media_volume_down": Key.media_volume_down,
    "media_volume_mute": Key.media_volume_mute,
    **{f"f{i}": getattr(Key, f"f{i}") for i in range(1, 21)},
}


def _parse_key(key_str: str):
    lower = key_str.lower().strip()
    if lower in _SPECIAL:
        return _SPECIAL[lower]
    if len(key_str) == 1:
        return key_str
    raise ValueError(f"Unknown key: '{key_str}'")


def _on_wayland() -> bool:
    return platform.system() == "Linux" and bool(os.environ.get("WAYLAND_DISPLAY"))


# ---------------------------------------------------------------------------
# evdev / UInput approach (Linux, bypasses ydotool and wtype)
# ---------------------------------------------------------------------------

try:
    import evdev
    from evdev import UInput, ecodes
    _EVDEV_AVAILABLE = True
except ImportError:
    _EVDEV_AVAILABLE = False

_EVDEV_KEY_MAP: dict = {}

if _EVDEV_AVAILABLE:
    _EVDEV_KEY_MAP = {
        "ctrl":        ecodes.KEY_LEFTCTRL,   "ctrl_l":  ecodes.KEY_LEFTCTRL,
        "ctrl_r":      ecodes.KEY_RIGHTCTRL,
        "alt":         ecodes.KEY_LEFTALT,    "alt_l":   ecodes.KEY_LEFTALT,
        "alt_gr":      ecodes.KEY_RIGHTALT,
        "shift":       ecodes.KEY_LEFTSHIFT,  "shift_l": ecodes.KEY_LEFTSHIFT,
        "shift_r":     ecodes.KEY_RIGHTSHIFT,
        "super":       ecodes.KEY_LEFTMETA,   "win":     ecodes.KEY_LEFTMETA,
        "cmd":         ecodes.KEY_LEFTMETA,
        "enter":       ecodes.KEY_ENTER,      "return":  ecodes.KEY_ENTER,
        "space":       ecodes.KEY_SPACE,      "tab":     ecodes.KEY_TAB,
        "esc":         ecodes.KEY_ESC,        "escape":  ecodes.KEY_ESC,
        "backspace":   ecodes.KEY_BACKSPACE,  "delete":  ecodes.KEY_DELETE,
        "insert":      ecodes.KEY_INSERT,
        "up":          ecodes.KEY_UP,         "down":    ecodes.KEY_DOWN,
        "left":        ecodes.KEY_LEFT,       "right":   ecodes.KEY_RIGHT,
        "home":        ecodes.KEY_HOME,       "end":     ecodes.KEY_END,
        "page_up":     ecodes.KEY_PAGEUP,     "page_down": ecodes.KEY_PAGEDOWN,
        "caps_lock":   ecodes.KEY_CAPSLOCK,   "num_lock":  ecodes.KEY_NUMLOCK,
        "print_screen": ecodes.KEY_SYSRQ,
        "media_play_pause":  ecodes.KEY_PLAYPAUSE,
        "media_next":        ecodes.KEY_NEXTSONG,
        "media_previous":    ecodes.KEY_PREVIOUSSONG,
        "media_volume_up":   ecodes.KEY_VOLUMEUP,
        "media_volume_down": ecodes.KEY_VOLUMEDOWN,
        "media_volume_mute": ecodes.KEY_MUTE,
        **{chr(c): getattr(ecodes, f"KEY_{chr(c).upper()}") for c in range(ord("a"), ord("z") + 1)},
        **{str(i): getattr(ecodes, f"KEY_{i}") for i in range(0, 10)},
        **{f"f{i}": getattr(ecodes, f"KEY_F{i}") for i in range(1, 21)},
    }

_uinput_lock = threading.Lock()
_uinput_device = None  # type: ignore


def _get_uinput():
    global _uinput_device
    if _uinput_device is not None:
        return _uinput_device
    with _uinput_lock:
        if _uinput_device is None:
            _uinput_device = UInput(name="buttonbox-keyboard")
            # Give the compositor time to register the new device
            time.sleep(0.3)
    return _uinput_device


def _send_via_uinput(keys: list[str]) -> None:
    codes = [_EVDEV_KEY_MAP.get(k.lower()) for k in keys]
    codes = [c for c in codes if c is not None]
    if not codes:
        raise ValueError(f"No evdev keycodes found for: {keys}")

    global _uinput_device
    try:
        ui = _get_uinput()
        for c in codes:
            ui.write(ecodes.EV_KEY, c, 1)
        ui.syn()
        time.sleep(0.02)
        for c in reversed(codes):
            ui.write(ecodes.EV_KEY, c, 0)
        ui.syn()
    except Exception:
        # Reset the device on error so it's recreated next time
        with _uinput_lock:
            try:
                if _uinput_device:
                    _uinput_device.close()
            except Exception:
                pass
            _uinput_device = None
        raise


# ---------------------------------------------------------------------------
# Subprocess fallbacks (wtype / ydotool / xdotool)
# ---------------------------------------------------------------------------

_YDOTOOL_SOCKET_CANDIDATES = [
    "/tmp/.ydotool.socket",
    "/tmp/.ydotool_socket",
    "/run/ydotool.socket",
]

_WTYPE_MODIFIER_MAP = {
    "ctrl": "ctrl", "ctrl_l": "ctrl", "ctrl_r": "ctrl",
    "alt": "alt", "alt_l": "alt", "alt_gr": "alt",
    "shift": "shift", "shift_l": "shift", "shift_r": "shift",
    "super": "super", "win": "super", "cmd": "super",
}


def _find_ydotool_socket() -> str | None:
    candidates = list(_YDOTOOL_SOCKET_CANDIDATES)
    explicit = os.environ.get("YDOTOOL_SOCKET")
    if explicit:
        candidates.insert(0, explicit)
    for path in candidates:
        if os.path.exists(path) and os.access(path, os.W_OK):
            return path
    return None


def _send_via_wtype(keys: list[str]) -> None:
    modifiers = [k for k in keys[:-1] if k.lower() in _WTYPE_MODIFIER_MAP]
    main = keys[-1]
    args = ["wtype"]
    for mod in modifiers:
        args += ["-P", _WTYPE_MODIFIER_MAP[mod.lower()]]
    args += ["-k", main]
    for mod in reversed(modifiers):
        args += ["-p", _WTYPE_MODIFIER_MAP[mod.lower()]]
    subprocess.run(args, check=True)


def _send_via_subprocess(keys: list[str]) -> None:
    if _EVDEV_AVAILABLE:
        _send_via_uinput(keys)
        return

    if shutil.which("wtype"):
        _send_via_wtype(keys)
        return

    combo = "+".join(keys)
    if shutil.which("ydotool"):
        env = os.environ.copy()
        socket = _find_ydotool_socket()
        if socket:
            env["YDOTOOL_SOCKET"] = socket
        result = subprocess.run(["ydotool", "key", combo], capture_output=True, env=env)
        if result.returncode != 0:
            # ydotool writes errors to stdout, not stderr
            out = (result.stdout or result.stderr).decode(errors="replace").strip()
            raise RuntimeError(
                f"ydotool falló (socket={socket}):\n{out}\n"
                "Asegurate de que el daemon esté corriendo:\n"
                "  sudo systemctl enable --now ydotool"
            )
        return

    if shutil.which("xdotool"):
        subprocess.run(["xdotool", "key", "--clearmodifiers", combo], check=True)
        return

    raise RuntimeError(
        "Wayland detectado pero no hay herramienta disponible.\n"
        "Instalá evdev:  pip install evdev\n"
        "O wtype:        sudo dnf install wtype"
    )


@register_action("keyboard")
class KeyboardAction(BaseAction):
    def __init__(self, config: dict):
        super().__init__(config)
        self._key_strs = config.get("keys", [])
        self._pynput_keys = None
        if not _on_wayland():
            self._pynput_keys = [_parse_key(k) for k in self._key_strs]

    def execute(self) -> None:
        if not self._key_strs:
            return
        if _on_wayland():
            _send_via_subprocess(self._key_strs)
        else:
            self._execute_pynput()

    def _execute_pynput(self) -> None:
        kb = Controller()
        keys = self._pynput_keys or [_parse_key(k) for k in self._key_strs]
        modifiers, main = keys[:-1], keys[-1]
        try:
            for mod in modifiers:
                kb.press(mod)
            kb.tap(main)
        finally:
            for mod in reversed(modifiers):
                kb.release(mod)

    @classmethod
    def describe(cls) -> str:
        return "Send a keyboard shortcut or key combination"

    @classmethod
    def example(cls) -> dict:
        return {"type": "keyboard", "keys": ["ctrl", "c"]}
