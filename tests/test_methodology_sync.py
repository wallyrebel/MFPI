"""The published methodology must describe the formula the code runs."""

from __future__ import annotations

import re
from pathlib import Path

from mfpi.config import COMPONENT_WEIGHTS, FORMULA_VERSION

ROOT = Path(__file__).resolve().parent.parent
LABELS = {
    "performance": "Opponent-adjusted performance",
    "sos": "MFPI strength of schedule",
    "maxpreps_rank": "Media rank",
    "maxpreps_sos": "Media strength of schedule",
    "record": "Record",
    "offense": "Points scored",
    "defense": "Points allowed",
    "recent": "Recent form",
}


def test_weights_sum_to_one() -> None:
    assert abs(sum(COMPONENT_WEIGHTS.values()) - 1.0) < 1e-12


def test_methodology_page_weights_match_code() -> None:
    page = (ROOT / "app" / "methodology" / "page.tsx").read_text(encoding="utf-8")
    for key, label in LABELS.items():
        match = re.search(rf"\['(\d+)%', '{re.escape(label)}'", page)
        assert match, label
        assert int(match.group(1)) == round(COMPONENT_WEIGHTS[key] * 100), label


def test_methodology_markdown_matches_code() -> None:
    doc = (ROOT / "METHODOLOGY.md").read_text(encoding="utf-8")
    assert FORMULA_VERSION.split("-")[1] in doc.splitlines()[0]
    rows = {name.lower(): weight for name, weight in re.findall(r"^\| ([^|]+?) \| (\d+)% \|", doc, flags=re.M)}
    for key, label in LABELS.items():
        assert int(rows[label.lower()]) == round(COMPONENT_WEIGHTS[key] * 100), label
