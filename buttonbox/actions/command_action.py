import logging
import subprocess
from .base import BaseAction, register_action

log = logging.getLogger(__name__)


@register_action("command")
class CommandAction(BaseAction):
    def execute(self) -> None:
        cmd   = self.config.get("command", "")
        shell = self.config.get("shell", True)
        bg    = self.config.get("background", True)
        try:
            if bg:
                subprocess.Popen(cmd, shell=shell)
            else:
                subprocess.run(cmd, shell=shell, check=True)
        except Exception as exc:  # noqa: BLE001
            log.error("Command failed: %s", exc)

    @classmethod
    def describe(cls) -> str:
        return "Run a shell command (Linux/Windows)"

    @classmethod
    def example(cls) -> dict:
        return {
            "type": "command",
            "command": "notify-send 'ButtonBox' 'Button pressed!'",
            "background": True,
        }
