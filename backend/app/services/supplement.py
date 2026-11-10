"""Verified extra facts for schemes where the myScheme record has nothing.

myScheme has no field for the documents list, helpline, grievance route, fee or last date. For the
most-asked schemes those are written by hand in app/data/scheme_supplement.json, each from an official
page named in `sources`. Anything not in that file is reported to the person as "not available",
never guessed.

The file is keyed by myScheme slug. Fields (all optional):
  documents, documents_note, fee, last_date, approval_time, status_check, payment, helpline,
  grievance, notes   (text, or a list of text lines)
  sources            (official URLs the values were taken from; never shown to the model)
  verified           (date the values were last checked)
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PATH = Path(__file__).resolve().parents[1] / "data" / "scheme_supplement.json"
_MODEL_FIELDS = ("documents", "documents_note", "fee", "last_date", "approval_time", "status_check", "payment", "helpline", "grievance", "notes")


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("scheme supplement unreadable: %s", exc)
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict) and not k.startswith("_")}


def get_supplement(slug: str | None) -> dict[str, Any]:
    """The verified extra facts for a scheme, limited to the fields the model may state."""
    rec = _load().get((slug or "").strip())
    if not rec:
        return {}
    return {k: rec[k] for k in _MODEL_FIELDS if rec.get(k)}


def supplemented_slugs() -> list[str]:
    return list(_load())
