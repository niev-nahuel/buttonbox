# Import all action modules so their @register_action decorators run.
from . import command_action, http_action, keyboard_action, script_action

__all__ = ["command_action", "http_action", "keyboard_action", "script_action"]
