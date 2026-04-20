"""
Core daemon: reads button events from the device and dispatches actions.
"""
import asyncio
import logging

from . import actions as _actions_pkg  # noqa: F401 — triggers registration
from .actions.base import build_action
from .config import ConfigManager
from .device import DeviceManager
from .events import ButtonEvent

log = logging.getLogger(__name__)

# Events the user can bind actions to (subset exposed in config)
_EVENT_KEY_MAP = {
    "PRESS":              "press",
    "HOLD":               "hold",
    "RELEASE":            "release",
    "RELEASE_AFTER_HOLD": "release",  # falls back to the same key as RELEASE
}


class ButtonBoxDaemon:
    def __init__(self, config: ConfigManager):
        self._config = config
        self._device = DeviceManager(config.get_device_config(), self._on_line)

    async def _on_line(self, line: str) -> None:
        event = ButtonEvent.parse(line)
        if event is None:
            return

        event_key  = _EVENT_KEY_MAP.get(event.event_type.value)
        btn_config = self._config.get_button(event.button_id)
        action_cfg = btn_config.get(event_key) if event_key else None

        if not action_cfg:
            return

        try:
            action = build_action(action_cfg)
            if action:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, action.execute)
        except Exception as exc:  # noqa: BLE001
            log.error("Action error [BTN%s %s]: %s", event.button_id, event_key, exc)

    async def run(self) -> None:
        log.info("ButtonBox daemon running — waiting for device …")
        await self._device.run()

    def stop(self) -> None:
        self._device.stop()
