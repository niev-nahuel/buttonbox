from abc import ABC, abstractmethod
from typing import Dict, Optional, Type

# Global registry populated by @register_action decorators
ACTION_REGISTRY: Dict[str, Type["BaseAction"]] = {}


def register_action(name: str):
    """Class decorator that registers an action under *name*."""
    def decorator(cls: Type["BaseAction"]) -> Type["BaseAction"]:
        ACTION_REGISTRY[name] = cls
        return cls
    return decorator


def build_action(config: Optional[dict]) -> Optional["BaseAction"]:
    """Instantiate an action from a config dict, or return None if config is falsy."""
    if not config:
        return None
    action_type = config.get("type")
    cls = ACTION_REGISTRY.get(action_type)
    if cls is None:
        raise ValueError(
            f"Unknown action type '{action_type}'. "
            f"Available: {sorted(ACTION_REGISTRY)}"
        )
    return cls(config)


class BaseAction(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def execute(self) -> None:
        """Perform the action synchronously (called from a thread executor)."""

    @classmethod
    @abstractmethod
    def describe(cls) -> str:
        """One-line human-readable description shown in the CLI."""

    @classmethod
    @abstractmethod
    def example(cls) -> dict:
        """Example config dict shown in the CLI wizard."""
