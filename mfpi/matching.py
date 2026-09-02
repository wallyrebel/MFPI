from __future__ import annotations

import difflib
import re
import unicodedata
from collections.abc import Iterable

from .models import Team

GENERIC_SUFFIXES = (
    " junior senior high school",
    " senior high school",
    " high school",
    " high",
    " attendance center",
    " school",
)

EXPLICIT_ALIASES = {
    "c clinton": "clinton",
    "diberville senior high sch": "diberville",
    "forrest county agricultural hi sch": "forrest county agricultural",
    "forrest county ahs": "forrest county agricultural",
    "fca hs": "forrest county agricultural",
    "fca": "forrest county agricultural",
    "saint martin": "st martin",
    "st andrews": "st andrews",
    "tupelo christian": "tupelo christian prep",
    "h w byers": "byers",
    "h w byers high": "byers",
    "picayune memorial": "picayune",
    "poplarville jr sr": "poplarville",
    "kosciusko senior": "kosciusko",
    "north pike senior": "north pike",
    "north side": "northside",
    "leake": "leake central",
    "south pike senior": "south pike",
    "winona secondary": "winona",
    "jefferson co": "jefferson county",
    "presbyterian christian school": "presbyterian christian",
    "canton public": "canton",
    "coahoma county jr sr": "coahoma county",
    "thomas e edwards": "edwards",
    "st andrews episcopal": "st andrews",
    "franklin county": "franklin",
    "m s palmer": "palmer",
    "ashland middle": "ashland",
    "french camp academy": "french camp",
    "resurrection catholic": "resurrection",
    "christian collegiate academy": "christian collegiate",
}


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("&", " and ")
    text = text.replace("'", "")
    text = re.sub(r"\(\s*\d+\s*[-–]\s*\d+\s*\)", " ", text)
    text = re.sub(r"\(([^)]*)\)", r" \1 ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\bsaint\b", "st", text)
    text = re.sub(r"\s+", " ", text).strip()
    for suffix in GENERIC_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            break
    return EXPLICIT_ALIASES.get(text, text)


def team_slug(value: str) -> str:
    return normalize_name(value).replace(" ", "-")


def display_name(value: str) -> str:
    small = {"and", "of", "the"}
    words = re.sub(r"\s+", " ", value.strip()).split(" ")
    rendered: list[str] = []
    for index, word in enumerate(words):
        upper = word.upper()
        if upper in {"JZ", "HW"}:
            rendered.append(".".join(upper) + ".")
        elif word.lower() in small and index:
            rendered.append(word.lower())
        elif word.lower().startswith("mc") and len(word) > 2:
            rendered.append("Mc" + word[2:].title())
        else:
            rendered.append(word.title())
    return " ".join(rendered).replace("St ", "St. ").replace("D Iberville", "D'Iberville")


def generated_aliases(name: str) -> tuple[str, ...]:
    normalized = normalize_name(name)
    variants = {name, normalized}
    if normalized.startswith("st "):
        variants.add("saint " + normalized[3:])
    if " agricultural" in normalized:
        variants.add(normalized.replace(" agricultural", " ag"))
    return tuple(sorted(variants))


class TeamMatcher:
    def __init__(self, teams: Iterable[Team]) -> None:
        self.teams = list(teams)
        self._by_alias: dict[str, Team] = {}
        for team in self.teams:
            values = {team.canonical_name, team.display_name, *team.aliases}
            for value in values:
                key = normalize_name(value)
                existing = self._by_alias.get(key)
                if existing is not None and existing.team_id != team.team_id:
                    raise ValueError(f"Duplicate normalized alias {key!r}: {existing.team_id} and {team.team_id}")
                self._by_alias[key] = team

    def match(self, incoming_name: str) -> tuple[Team | None, float, str]:
        key = normalize_name(incoming_name)
        if key in self._by_alias:
            return self._by_alias[key], 1.0, "alias"
        candidates = difflib.get_close_matches(key, self._by_alias.keys(), n=2, cutoff=0.88)
        if not candidates:
            return None, 0.0, "unmatched"
        best_score = difflib.SequenceMatcher(None, key, candidates[0]).ratio()
        second_score = difflib.SequenceMatcher(None, key, candidates[1]).ratio() if len(candidates) > 1 else 0.0
        if best_score >= 0.94 and best_score - second_score >= 0.04:
            return self._by_alias[candidates[0]], best_score, "fuzzy"
        return None, best_score, "ambiguous"
