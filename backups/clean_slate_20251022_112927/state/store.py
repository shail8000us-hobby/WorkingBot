from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore

from bot.config.aliases import strip_legacy_keys, upgrade_mapping
from bot.utils.atomic_file import atomic_write_json
from bot.utils.logging_setup import get_logger


class StateStore:
    """Thread-safe helper around JSON-backed state files."""

    def flush(self) -> None:
        """No-op flush for now (API compatibility)."""
        pass

    """
    Minimal JSON-backed state.
    Shape:
      {
        "last_price": 0.0,
        "reference_level": 109800.0,
        "open_positions": []
      }
    """

    def __init__(
        self,
        path: Path,
        *,
        default: Optional[Dict[str, Any]] = None,
        validator: Optional[Callable[[Dict[str, Any]], bool]] = None,
        logger_name: str = "state",
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.log = get_logger(logger_name)
        self._default_data = default or {
            "last_price": 0.0,
            "reference_level": 109800.0,
            "open_positions": [],
        }
        self._validator = validator

    def _clone_default(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self._default_data))

    def _validate(self, payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            self.log.error("State payload is not a JSON object")
            return False
        if self._validator and not self._validator(payload):
            self.log.error("State payload failed schema validation")
            return False
        return True

    def locked_read(self) -> Dict[str, Any]:
        if not self.path.exists():
            return self._clone_default()
        fh = None
        try:
            fh = self.path.open('r', encoding='utf-8')
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_SH)
            raw = fh.read()
        except FileNotFoundError:
            return self._clone_default()
        except Exception as exc:
            self.log.error(f"Failed to read {self.path}: {exc}")
            return self._clone_default()

        if not raw.strip():
            return self._clone_default()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            self.log.error(f"Failed to decode JSON from {self.path}: {exc}")
            return self._clone_default()
        finally:
            if fh is not None:
                try:
                    if fcntl is not None:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)  # type: ignore[arg-type]
                except Exception:
                    pass
                fh.close()

        if not self._validate(data):
            return self._clone_default()
        upgrade_mapping(data, record=False)
        return data

    def load(self) -> Dict[str, Any]:
        return self.locked_read()

    def save(self, data: Dict[str, Any]) -> None:
        try:
            upgrade_mapping(data, record=False)
            strip_legacy_keys(data)
            atomic_write_json(self.path, data, indent=2)
        except Exception as e:
            self.log.error(f"Failed to save state: {e}")


DEFAULT_STATE = {
    "last_price": 0.0,
    "reference_level": 109800.0,
    "open_positions": [],
}

DEFAULT_POSITIONS = {
    "positions": [],
    "summary": {},
}


def _positions_validator(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    positions = payload.get("positions", [])
    return isinstance(positions, list)


def load_state_file(path: Path) -> Dict[str, Any]:
    store = StateStore(Path(path), default=DEFAULT_STATE)
    return store.locked_read()


def load_positions_file(path: Path) -> Dict[str, Any]:
    store = StateStore(Path(path), default=DEFAULT_POSITIONS, validator=_positions_validator)
    return store.locked_read()


__all__ = [
    "StateStore",
    "load_state_file",
    "load_positions_file",
]
