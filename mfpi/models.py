from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Team:
    team_id: str
    canonical_name: str
    display_name: str
    classification: str | None
    region: str | None = None
    city: str = ""
    state: str = "MS"
    aliases: tuple[str, ...] = ()
    active: bool = True
    season: int = 2026
    source_team_id: str | None = None

    @property
    def ranked(self) -> bool:
        return self.active and self.classification in {f"{n}A" for n in range(1, 8)}

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["aliases"] = list(self.aliases)
        return value


@dataclass(frozen=True)
class Game:
    game_id: str
    date: datetime
    home_team_id: str
    away_team_id: str
    home_score: int | None
    away_score: int | None
    neutral_site: bool = False
    overtime: bool = False
    forfeit: bool = False
    source: str = "unknown"
    source_timestamp: datetime | None = None
    verified: bool = True
    status: str = "COMPLETED"
    expected_status: str | None = None
    contest_type: str | None = None

    @property
    def completed(self) -> bool:
        return self.status == "COMPLETED" and self.home_score is not None and self.away_score is not None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["date"] = self.date.isoformat()
        value["source_timestamp"] = self.source_timestamp.isoformat() if self.source_timestamp else None
        return value


@dataclass(frozen=True)
class RawGame:
    game_id: str
    date: datetime
    home_name: str
    away_name: str
    home_source_id: str | None
    away_source_id: str | None
    home_score: int | None
    away_score: int | None
    neutral_site: bool = False
    overtime: bool = False
    forfeit: bool = False
    source: str = "mhsaa_score_center"
    source_timestamp: datetime | None = None
    status: str = "UPCOMING"
    expected_status: str | None = None
    contest_type: str | None = None
    home_city: str = ""
    away_city: str = ""


@dataclass(frozen=True)
class MaxPrepsRanking:
    state_rank: int
    team_name: str
    record: str
    rating: float
    strength: float
    team_url: str = ""


@dataclass(frozen=True)
class MaxPrepsSignal:
    team_id: str
    state_rank: int
    rating: float
    strength: float
    source_name: str
    source_url: str = ""


@dataclass(frozen=True)
class MaxPrepsScoreObservation:
    game_id: str
    date: datetime
    home_name: str
    away_name: str
    home_score: int | None
    away_score: int | None
    status: str
    forfeit: bool
    source_url: str
    observed_from_team_id: str
    retrieved_at: datetime

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["date"] = self.date.isoformat()
        value["retrieved_at"] = self.retrieved_at.isoformat()
        return value


@dataclass
class ComponentValue:
    raw: float | None
    normalized: float
    weight: float = 0.0
    contribution: float = 0.0

    def to_dict(self) -> dict[str, float | None]:
        return {
            "raw": None if self.raw is None else round(self.raw, 6),
            "normalized": round(self.normalized, 6),
            "weight": round(self.weight, 6),
            "contribution": round(self.contribution, 6),
        }


@dataclass
class RankingRow:
    team: Team
    games_played: int
    wins: int
    losses: int
    ties: int
    points_for: int
    points_against: int
    capped_points_for: int
    capped_margin: float
    up_games: int
    same_class_games: int
    down_games: int
    class_schedule_delta: float
    components: dict[str, ComponentValue]
    mfpi: float
    state_rank: int = 0
    class_rank: int = 0
    previous_state_rank: int | None = None
    previous_class_rank: int | None = None
    previous_mfpi: float | None = None
    explanation: str = ""
    maxpreps_state_rank: int | None = None
    maxpreps_rating: float | None = None
    maxpreps_strength: float | None = None

    @property
    def record(self) -> str:
        return f"{self.wins}-{self.losses}" + (f"-{self.ties}" if self.ties else "")

    @property
    def schedule_direction(self) -> str:
        if self.up_games + self.same_class_games + self.down_games == 0:
            return "No class data"
        if self.class_schedule_delta > 0.25:
            return "Playing up"
        if self.class_schedule_delta < -0.25:
            return "Playing down"
        return "Mostly same class"

    def to_dict(self) -> dict[str, Any]:
        state_change = None if self.previous_state_rank is None else self.previous_state_rank - self.state_rank
        class_change = None if self.previous_class_rank is None else self.previous_class_rank - self.class_rank
        mfpi_change = None if self.previous_mfpi is None else self.mfpi - self.previous_mfpi
        return {
            "team_id": self.team.team_id,
            "slug": self.team.team_id,
            "team": self.team.display_name,
            "classification": self.team.classification,
            "region": self.team.region,
            "record": self.record,
            "games_played": self.games_played,
            "state_rank": self.state_rank,
            "class_rank": self.class_rank,
            "mfpi": round(self.mfpi, 1),
            "mfpi_unrounded": round(self.mfpi, 8),
            "previous_state_rank": self.previous_state_rank,
            "state_rank_change": state_change,
            "previous_class_rank": self.previous_class_rank,
            "class_rank_change": class_change,
            "previous_mfpi": None if self.previous_mfpi is None else round(self.previous_mfpi, 1),
            "mfpi_change": None if mfpi_change is None else round(mfpi_change, 1),
            "pf_per_game": round(self.points_for / self.games_played, 1) if self.games_played else 0.0,
            "pa_per_game": round(self.points_against / self.games_played, 1) if self.games_played else 0.0,
            "up_games": self.up_games,
            "same_class_games": self.same_class_games,
            "down_games": self.down_games,
            "class_schedule_delta": round(self.class_schedule_delta, 3),
            "schedule_direction": self.schedule_direction,
            "maxpreps_state_rank": self.maxpreps_state_rank,
            "maxpreps_rating": self.maxpreps_rating,
            "maxpreps_strength": self.maxpreps_strength,
            "components": {name: value.to_dict() for name, value in self.components.items()},
            "explanation": self.explanation,
        }


@dataclass
class ValidationIssue:
    code: str
    severity: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationReport:
    issues: list[ValidationIssue]
    expected_games: int
    verified_games: int
    missing_games: int
    coverage: float

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "CRITICAL" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "expected_games": self.expected_games,
            "verified_games": self.verified_games,
            "missing_games": self.missing_games,
            "coverage_percentage": round(self.coverage * 100, 2),
            "issues": [issue.to_dict() for issue in self.issues],
        }
