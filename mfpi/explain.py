"""Deterministic wording for rank and rating movement.

Rank movement and rating change are different facts and are always named
separately: a team can hold No. 1 while its rating rises, or move several
places while its rating is unchanged.
"""

from __future__ import annotations

from typing import Any


def _spots(value: int) -> str:
    return f"{value} spot{'s' if value != 1 else ''}"


def rank_sentence(state_rank: int, previous_state_rank: int | None) -> str:
    if previous_state_rank is None:
        return f"State ranking: new at No. {state_rank} (no comparable previous snapshot)."
    change = previous_state_rank - state_rank
    if change > 0:
        return f"State ranking: up {_spots(change)} to No. {state_rank} (from No. {previous_state_rank})."
    if change < 0:
        return f"State ranking: down {_spots(-change)} to No. {state_rank} (from No. {previous_state_rank})."
    return f"State ranking: unchanged at No. {state_rank}."


def rating_sentence(mfpi: float, mfpi_change: float | None) -> str:
    if mfpi_change is None:
        return f"MFPI rating: {mfpi:.1f} (not comparable; no previous rating)."
    if mfpi_change > 0:
        return f"MFPI rating: increased {mfpi_change:.1f} points to {mfpi:.1f}."
    if mfpi_change < 0:
        return f"MFPI rating: decreased {abs(mfpi_change):.1f} points to {mfpi:.1f}."
    return f"MFPI rating: unchanged at {mfpi:.1f}."


def ranking_explanation(row: dict[str, Any]) -> str:
    """Build the stored explanation from a serialized ranking row."""

    name = row["team"]
    parts = [
        rank_sentence(row["state_rank"], row.get("previous_state_rank")),
        rating_sentence(row["mfpi"], row.get("mfpi_change")),
    ]
    status = row.get("data_status", "complete")
    if row.get("games_played", 0) == 0:
        if status == "preseason":
            parts.append(f"{name} has no games due before this cutoff; its provisional rating uses class, media and neutral inputs.")
        else:
            parts.append(
                f"No verified results are linked to {name} for this cutoff, so its rating is provisional "
                "and rests on class, media and neutral inputs rather than games."
            )
    else:
        components = row["components"]
        parts.append(
            f"Opponent-adjusted performance percentile {components['performance']['normalized']:.1f}; "
            f"schedule-strength percentile {components['sos']['normalized']:.1f}."
        )
        pending = row.get("pending_games", 0)
        if pending:
            parts.append(f"{pending} listing{'s' if pending != 1 else ''} due by the cutoff still lack a verified result.")
    if row.get("bye_adjustment"):
        parts.append("Confirmed bye: MFPI retains 90% of last week's score plus 10% of this week's recalculation.")
    return " ".join(parts)


def display_rating_change(row: dict[str, Any]) -> float | None:
    """Rating change as readers see it: displayed rating minus displayed previous rating.

    Older snapshots stored a full-precision difference in ``mfpi_change``;
    ``previous_mfpi`` (already one decimal) gives the display-consistent value.
    """

    previous = row.get("previous_mfpi")
    if previous is None:
        return None
    return round(round(row["mfpi"], 1) - round(previous, 1), 1) + 0.0
