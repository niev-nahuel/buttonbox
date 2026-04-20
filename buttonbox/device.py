"""
Async serial device manager.
Auto-detects the Pico by USB VID, reads lines, and reconnects on disconnect.
"""
import asyncio
import logging
from typing import Awaitable, Callable, Optional

import serial
import serial.tools.list_ports

log = logging.getLogger(__name__)

PICO_VID = 0x2E8A  # Raspberry Pi Foundation


def _find_pico_port() -> Optional[str]:
    for info in serial.tools.list_ports.comports():
        if info.vid == PICO_VID:
            return info.device
    return None


class DeviceManager:
    def __init__(self, config: dict, on_line: Callable[[str], Awaitable[None]]):
        self._config  = config
        self._on_line = on_line
        self._running = False
        self._conn: Optional[serial.Serial] = None

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                await self._connect_and_read()
            except serial.SerialException as exc:
                log.warning("Serial error: %s — retrying in 2 s", exc)
                await asyncio.sleep(2)
            except Exception as exc:  # noqa: BLE001
                log.error("Unexpected device error: %s — retrying in 2 s", exc)
                await asyncio.sleep(2)

    async def _connect_and_read(self) -> None:
        port = self._config.get("port") or _find_pico_port()
        if not port:
            log.debug("Pico not found — scanning again in 2 s")
            await asyncio.sleep(2)
            return

        baud = self._config.get("baud_rate", 115200)
        log.info("Connecting to %s @ %d baud …", port, baud)

        loop = asyncio.get_running_loop()
        self._conn = await loop.run_in_executor(
            None, lambda: serial.Serial(port, baud, timeout=1)
        )
        log.info("Connected to %s", port)

        try:
            while self._running:
                raw = await loop.run_in_executor(None, self._conn.readline)
                if raw:
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if line:
                        await self._on_line(line)
        finally:
            self._conn.close()
            self._conn = None
            log.info("Disconnected from %s", port)

    def stop(self) -> None:
        self._running = False
        if self._conn and self._conn.is_open:
            self._conn.close()
