import logging
import subprocess
import sys
from pathlib import Path
from .base import BaseAction, register_action

log = logging.getLogger(__name__)

_INTERPRETERS = {".py": sys.executable, ".sh": "bash", ".bash": "bash", ".ps1": "powershell"}


@register_action("script")
class ScriptAction(BaseAction):
    def execute(self) -> None:
        path       = self.config.get("path", "")
        interpreter = self.config.get("interpreter") or _INTERPRETERS.get(Path(path).suffix, "bash")
        args       = self.config.get("args", [])
        try:
            subprocess.Popen([interpreter, path, *args])
        except Exception as exc:  # noqa: BLE001
            log.error("Script failed: %s", exc)

    @classmethod
    def describe(cls) -> str:
        return "Run a Python or shell script"

    @classmethod
    def example(cls) -> dict:
        return {"type": "script", "path": "/home/user/my_script.py", "args": []}
