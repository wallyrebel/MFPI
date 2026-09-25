"""Calendar-date handling for game listings.

High school football listings are date-first facts: a Friday game must stay a
Friday game on every page. Two conversions have moved games to Saturday:

* Scorebook Live marks a game without a published kickoff time as 23:59 in its
  own (Pacific) offset. Converting that marker to Central yields 01:59 the next
  morning, so the source-local date is the real calendar date.
* Formatting a Central evening kickoff in UTC (the Workers runtime timezone)
  also crosses midnight. Callers should use :func:`calendar_date` or the
  ``calendar_date`` field published in snapshots instead of formatting a
  timestamp in whatever zone the server happens to run.
"""

from __future__ import annotations

from datetime import date, datetime

from .config import CENTRAL

# Wall-clock times a source uses to mean "date only, time not published".
DATE_ONLY_MARKERS = frozenset({(23, 59), (0, 0)})

# Published snapshots before MFPI-3.2 kept only the Central-converted time, so
# a 23:59 Pacific marker reads 01:59 Central. No Mississippi high school game
# kicks off between midnight and 5 a.m., so such a Central wall-clock time is a
# converted end-of-day marker belonging to the previous calendar date.
LEGACY_CONVERTED_MARKER_LAST_HOUR = 4


def calendar_date(value: datetime) -> date:
    """Return the game's calendar date without timezone drift."""

    if value.tzinfo is None:
        return value.date()
    if (value.hour, value.minute) in DATE_ONLY_MARKERS:
        return value.date()
    return value.astimezone(CENTRAL).date()


def calendar_date_from_snapshot(value: str, explicit: str | None = None) -> date:
    """Calendar date for a published game row.

    ``explicit`` is the ``calendar_date`` field written by current snapshots.
    Older snapshots only carry a Central ISO timestamp.
    """

    if explicit:
        return date.fromisoformat(explicit)
    parsed = datetime.fromisoformat(value)
    local = parsed.astimezone(CENTRAL) if parsed.tzinfo else parsed
    if local.hour <= LEGACY_CONVERTED_MARKER_LAST_HOUR:
        return date.fromordinal(local.date().toordinal() - 1)
    return local.date()
