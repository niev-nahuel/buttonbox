from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    PRESS = "PRESS"
    RELEASE = "RELEASE"
    HOLD = "HOLD"
    RELEASE_AFTER_HOLD = "RELEASE_AFTER_HOLD"


@dataclass
class ButtonEvent:
    button_id: int
    event_type: EventType

    @classmethod
    def parse(cls, line: str) -> Optional["ButtonEvent"]:
        """Parse 'BTN:<id>:<EVENT>' lines from the Pico."""
        try:
            parts = line.strip().split(":")
            if len(parts) == 3 and parts[0] == "BTN":
                return cls(button_id=int(parts[1]), event_type=EventType(parts[2]))
        except (ValueError, KeyError):
            pass
        return None
