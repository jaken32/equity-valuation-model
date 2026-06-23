"""Load :class:`Assumptions` from a YAML file."""
from __future__ import annotations

from pathlib import Path

from .model.assumptions import Assumptions

_DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "default_assumptions.yaml"


def load_assumptions(path: str | Path | None = None) -> Assumptions:
    """Load assumptions from ``path``, or the packaged defaults if omitted."""
    config_path = Path(path) if path else _DEFAULT_CONFIG
    if not config_path.exists():
        if path is None:
            return Assumptions()
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyYAML is required to load config files.") from exc

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return Assumptions.from_dict(data)
