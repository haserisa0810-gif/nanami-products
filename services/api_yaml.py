from __future__ import annotations

from typing import Any

import yaml


def build_handoff_yaml(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
