"""One vocabulary for what a game listing means.

Source feeds use their own status words. MFPI reduces them to categories so a
postponed game is never a loss, a missing score is never 0-0, and a future or
exhibition contest never counts toward a record.
"""

from __future__ import annotations

from datetime import datetime

from .models import Game

FINAL = "final"
FORFEIT = "forfeit"
SCHEDULED = "scheduled"
IN_PROGRESS = "in_progress"
POSTPONED = "postponed"
CANCELED = "canceled"
SUSPENDED = "suspended"
NO_CONTEST = "no_contest"
EXHIBITION = "exhibition"
UNRESOLVED = "unresolved"

CATEGORIES = (
    FINAL, FORFEIT, SCHEDULED, IN_PROGRESS, POSTPONED, CANCELED,
    SUSPENDED, NO_CONTEST, EXHIBITION, UNRESOLVED,
)

_STATUS_WORDS = {
    "CANCELLED": CANCELED,
    "CANCELED": CANCELED,
    "POSTPONED": POSTPONED,
    "SUSPENDED": SUSPENDED,
    "NO_CONTEST": NO_CONTEST,
    "NOCONTEST": NO_CONTEST,
    "IN_PROGRESS": IN_PROGRESS,
    "LIVE": IN_PROGRESS,
}


def is_exhibition(game: Game) -> bool:
    contest = (game.contest_type or "").lower()
    return any(label in contest for label in ("jamboree", "scrimmage", "exhibition"))


def status_category(game: Game, cutoff: datetime) -> str:
    """Classify a listing as seen at the ranking cutoff."""

    if is_exhibition(game):
        return EXHIBITION
    word = _STATUS_WORDS.get((game.status or "").upper().replace(" ", "_"))
    if word:
        return word
    if game.completed:
        return FORFEIT if game.forfeit else FINAL
    if game.date > cutoff:
        return SCHEDULED
    # Past the cutoff with no terminal status and no confirmed score. This is
    # a data gap, not evidence the game was played, cancelled, or lost.
    return UNRESOLVED


def counts_toward_record(game: Game, cutoff: datetime) -> bool:
    return game.verified and game.date <= cutoff and status_category(game, cutoff) in {FINAL, FORFEIT}


def counts_toward_scoring(game: Game, cutoff: datetime) -> bool:
    """Public points-for/against statistics use only games actually played."""

    return game.verified and game.date <= cutoff and status_category(game, cutoff) == FINAL


def expected_by_cutoff(game: Game, cutoff: datetime) -> bool:
    """Listings that should have a verified result by the cutoff."""

    return game.date <= cutoff and status_category(game, cutoff) not in {
        EXHIBITION, CANCELED, POSTPONED, NO_CONTEST, SCHEDULED,
    }
