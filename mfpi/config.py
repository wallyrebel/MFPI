from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

FORMULA_VERSION = "MFPI-3.2"
BYE_PREVIOUS_WEIGHT = 0.90
CENTRAL = ZoneInfo("America/Chicago")

COMPONENTS = (
    "performance",
    "sos",
    "maxpreps_rank",
    "maxpreps_sos",
    "record",
    "offense",
    "defense",
    "recent",
)

COMPONENT_WEIGHTS = {
    "performance": 0.35,
    "sos": 0.20,
    "maxpreps_rank": 0.10,
    "maxpreps_sos": 0.10,
    "record": 0.05,
    "offense": 0.08,
    "defense": 0.08,
    "recent": 0.04,
}

# A modest enrollment-class assumption expressed in football points and used
# only as a fading SRS prior. Results and opponent chains replace it quickly.
CLASS_PRIOR_POINTS = {
    "7A": 7.5,
    "6A": 5.0,
    "5A": 2.5,
    "4A": 0.0,
    "3A": -2.5,
    "2A": -5.0,
    "1A": -7.5,
}


@dataclass(frozen=True)
class Settings:
    season: int = 2026
    week: int = 1
    season_start: str = "2026-08-27"
    cutoff_hour: int = 13
    cutoff_minute: int = 0
    home_field_points: float = 2.0
    margin_scale: float = 42.0
    offense_cap: int = 49
    defense_cap: int = 49
    recent_weights: tuple[float, ...] = (1.0, 0.70, 0.50)
    coverage_threshold: float = 0.95
    max_iterations: int = 100
    convergence_tolerance: float = 0.01

    def default_cutoff(self) -> datetime:
        first = datetime(
            self.season,
            9,
            2,
            self.cutoff_hour,
            self.cutoff_minute,
            tzinfo=CENTRAL,
        )
        return first + timedelta(days=7 * (self.week - 1))


def weights_for_games(games_played: int) -> dict[str, float]:
    if games_played < 0:
        raise ValueError("games_played must not be negative")
    return dict(COMPONENT_WEIGHTS)


def ranking_week(at: datetime | None = None, season: int = 2026) -> int:
    """Return the ranking week at the Wednesday 1 p.m. Central boundary."""

    local = (at or datetime.now(tz=CENTRAL)).astimezone(CENTRAL)
    first_cutoff = Settings(season=season).default_cutoff()
    if local < first_cutoff:
        return 1
    elapsed_weeks = int((local - first_cutoff).total_seconds() // (7 * 24 * 60 * 60))
    return elapsed_weeks + 1


def class_prior_points(classification: str | None) -> float:
    return CLASS_PRIOR_POINTS.get(classification or "", 0.0)
