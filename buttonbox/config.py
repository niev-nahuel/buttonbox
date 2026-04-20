import copy
import json
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".buttonbox"

_DEFAULT: dict = {
    "device": {
        "auto_detect": True,
        "port": None,
        "baud_rate": 115200,
    },
    "current_profile": "Default",
    "profiles": {
        "Default": {
            "buttons": {
                str(i): {"name": f"Button {i}", "press": None, "hold": None, "release": None}
                for i in range(1, 7)
            }
        }
    },
}


class ConfigManager:
    def __init__(self, config_path: Optional[Path] = None):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.path = config_path or CONFIG_DIR / "config.json"
        self.config = self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self.path.exists():
            with open(self.path) as f:
                data = json.load(f)
            # Migration: flat "buttons" key → profiles structure
            if "buttons" in data and "profiles" not in data:
                data = {
                    "device": data.get("device", {}),
                    "current_profile": "Default",
                    "profiles": {"Default": {"buttons": data["buttons"]}},
                }
            return self._merge(_DEFAULT, data)
        self._write(_DEFAULT)
        return json.loads(json.dumps(_DEFAULT))

    def _write(self, data: dict) -> None:
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def save(self) -> None:
        self._write(self.config)

    # ── Deep merge: saved values win over defaults ────────────────────────────

    def _merge(self, base: dict, override: dict) -> dict:
        result = {**base}
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._merge(result[k], v)
            else:
                result[k] = v
        return result

    # ── Current profile helper ────────────────────────────────────────────────

    @property
    def _current_buttons(self) -> dict:
        profile = self.config["current_profile"]
        return self.config["profiles"][profile]["buttons"]

    # ── Button accessors ──────────────────────────────────────────────────────

    def get_device_config(self) -> dict:
        return self.config["device"]

    def get_button(self, button_id: int) -> dict:
        return self._current_buttons.get(str(button_id), {})

    def set_button_action(self, button_id: int, event: str, action: Optional[dict]) -> None:
        key = str(button_id)
        self._current_buttons.setdefault(key, {"name": f"Button {button_id}"})
        self._current_buttons[key][event] = action
        self.save()

    def set_button_name(self, button_id: int, name: str) -> None:
        key = str(button_id)
        self._current_buttons.setdefault(key, {})
        self._current_buttons[key]["name"] = name
        self.save()

    # ── Profile management ────────────────────────────────────────────────────

    def list_profiles(self) -> list[str]:
        return list(self.config["profiles"].keys())

    def get_current_profile(self) -> str:
        return self.config["current_profile"]

    def set_current_profile(self, name: str) -> None:
        if name not in self.config["profiles"]:
            raise KeyError(f"Profile '{name}' does not exist")
        self.config["current_profile"] = name
        self.save()

    def create_profile(self, name: str, copy_from: Optional[str] = None) -> None:
        if name in self.config["profiles"]:
            raise ValueError(f"El perfil '{name}' ya existe")
        if copy_from and copy_from in self.config["profiles"]:
            self.config["profiles"][name] = copy.deepcopy(self.config["profiles"][copy_from])
        else:
            self.config["profiles"][name] = {
                "buttons": {
                    str(i): {"name": f"Button {i}", "press": None, "hold": None, "release": None}
                    for i in range(1, 7)
                }
            }
        self.save()

    def delete_profile(self, name: str) -> None:
        if len(self.config["profiles"]) <= 1:
            raise ValueError("No se puede eliminar el último perfil")
        if name not in self.config["profiles"]:
            raise KeyError(f"Profile '{name}' does not exist")
        del self.config["profiles"][name]
        if self.config["current_profile"] == name:
            self.config["current_profile"] = next(iter(self.config["profiles"]))
        self.save()

    def rename_profile(self, old: str, new: str) -> None:
        if old not in self.config["profiles"]:
            raise KeyError(f"Profile '{old}' does not exist")
        if new in self.config["profiles"]:
            raise ValueError(f"El perfil '{new}' ya existe")
        self.config["profiles"] = {
            (new if k == old else k): v
            for k, v in self.config["profiles"].items()
        }
        if self.config["current_profile"] == old:
            self.config["current_profile"] = new
        self.save()
