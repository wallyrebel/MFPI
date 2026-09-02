from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from .config import CENTRAL
from .matching import display_name, generated_aliases, normalize_name, team_slug
from .models import MaxPrepsRanking, MaxPrepsScoreObservation, MaxPrepsSignal, RawGame, Team

MHSAA_CLASSIFICATIONS_URL = "https://www.misshsaa.com/2024/11/19/2025-27-football-regions/"
SCORE_API_URL = "https://api.scorebooklive.com/v2/graphql"
MAXPREPS_RANKINGS_URL = "https://www.maxpreps.com/ms/football/rankings/{page}/"
MAXPREPS_ROOT = "https://www.maxpreps.com"

# Schools can remain in a two-year MHSAA classification document after ending
# their football program. Keep them matchable for historical schedule data, but
# never include them in the current ranked-team universe.
INACTIVE_FOOTBALL_PROGRAMS = frozenset({"thrasher", "leake-county"})

SCORES_QUERY = """
query MFPIScores($date: ISO8601Date!, $genderSport: [GenderSportEnum!]!, $level: [LevelEnum!]!, $after: String) {
  contests(date: $date, genderSport: $genderSport, level: $level, orderBy: SCOREBOARD, withoutPlaceholderTeams: true, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id date status expectedStatus longStatusText divisionText contestTypeLabel isTbd
      contestParticipants {
        id location result score
        participant { __typename ... on Team { id name locationText } }
      }
    }
  }
}
"""


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None


class _MaxPrepsRankingsParser(HTMLParser):
    FIELDS = {"rank", "team", "overall", "rating", "strength"}

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, str]] = []
        self._row: dict[str, str] | None = None
        self._field: str | None = None
        self._text: list[str] = []
        self._ignored_team_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "tr":
            self._row = {}
        elif tag == "td" and self._row is not None:
            classes = set((values.get("class") or "").split())
            self._field = next((name for name in self.FIELDS if name in classes), None)
            self._text = []
        elif tag == "a" and self._row is not None and self._field == "team" and values.get("href"):
            self._row["team_url"] = values["href"] or ""
        elif (
            tag in {"div", "span"}
            and self._row is not None
            and self._field == "team"
            and "photo-or-initial" in set((values.get("class") or "").split())
        ):
            self._ignored_team_tag = tag

    def handle_data(self, data: str) -> None:
        if self._field is not None and self._ignored_team_tag is None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == self._ignored_team_tag:
            self._ignored_team_tag = None
            return
        if tag == "td" and self._row is not None and self._field is not None:
            self._row[self._field] = " ".join("".join(self._text).split())
            self._field = None
            self._text = []
        elif tag == "tr" and self._row is not None:
            if self._row.get("rank", "").isdigit() and self._row.get("team"):
                self.rows.append(self._row)
            self._row = None


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.documents: list[str] = []
        self._capturing = False
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script" and "ld+json" in (values.get("type") or "").lower():
            self._capturing = True
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capturing:
            self.documents.append("".join(self._text))
            self._capturing = False
            self._text = []


def _request_bytes(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 3,
) -> bytes:
    combined = {
        "Accept": "application/json,text/html;q=0.9",
        "User-Agent": "MFPI/1.0 (+local weekly rankings; contact repository owner)",
        **(headers or {}),
    }
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, data=data, headers=combined, method=method)
            with urlopen(request, timeout=45) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(0.5 * (2**attempt))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _city(location_text: str | None) -> str:
    return (location_text or "").split(",", 1)[0].strip()


class MHSAAClassificationProvider:
    def __init__(self, transport: Callable[..., bytes] = _request_bytes) -> None:
        self.transport = transport

    def fetch(self, cache_path: Path | None = None, refresh: bool = False) -> list[Team]:
        if cache_path and cache_path.exists() and not refresh:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            teams = [Team(**{**item, "aliases": tuple(item.get("aliases", []))}) for item in payload["teams"]]
            return [replace(team, active=False) if team.team_id in INACTIVE_FOOTBALL_PROGRAMS else team for team in teams]
        html = self.transport(MHSAA_CLASSIFICATIONS_URL).decode("utf-8", errors="replace")
        teams = self.parse(html)
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "source": MHSAA_CLASSIFICATIONS_URL,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "teams": [team.to_dict() for team in teams],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return teams

    @staticmethod
    def parse(html: str) -> list[Team]:
        parser = _TableParser()
        parser.feed(html)
        teams: list[Team] = []
        used_ids: set[str] = set()
        for row in parser.rows:
            if len(row) < 3 or not row[1].strip().isdigit() or not row[2].strip().isdigit():
                continue
            class_number = int(row[1])
            if class_number not in range(1, 8):
                continue
            official_name = row[0].strip()
            if not official_name or official_name.lower() in {"school", "school name"}:
                continue
            class_name = f"{class_number}A"
            region = row[2].strip()
            active = normalize_name(official_name) not in INACTIVE_FOOTBALL_PROGRAMS
            canonical_source = official_name
            rendered_name = display_name(official_name)
            aliases = generated_aliases(official_name)
            # MHSAA lists two distinct 2A schools as “Enterprise.” Their region
            # and score-center names are the only reliable disambiguators.
            if normalize_name(official_name) == "enterprise" and class_name == "2A":
                if region == "6":
                    canonical_source = "Enterprise Clarke"
                    rendered_name = "Enterprise (Clarke)"
                    aliases = ("Enterprise Clarke", "Enterprise High School Clarke")
                elif region == "7":
                    canonical_source = "Enterprise Brookhaven"
                    rendered_name = "Enterprise (Brookhaven)"
                    aliases = ("Enterprise Brookhaven", "Enterprise (Brookhaven)", "Enterprise Lincoln")
            slug = team_slug(canonical_source)
            if slug in used_ids:
                raise ValueError(f"Duplicate official team id after normalization: {official_name!r}")
            used_ids.add(slug)
            teams.append(
                Team(
                    team_id=slug,
                    canonical_name=normalize_name(canonical_source),
                    display_name=rendered_name,
                    classification=class_name,
                    region=region,
                    aliases=aliases,
                    active=active,
                    season=2026,
                )
            )
        if len(teams) < 150:
            raise ValueError(f"Official classification parse yielded only {len(teams)} teams")
        return teams


@dataclass(frozen=True)
class MaxPrepsFetch:
    rankings: list[MaxPrepsRanking]
    retrieved_at: datetime
    source_updated_at: str | None
    used_cache: bool = False


class MaxPrepsRankingProvider:
    """Fetch every paginated Mississippi football ranking from MaxPreps."""

    def __init__(self, transport: Callable[..., bytes] = _request_bytes, request_delay: float = 0.10) -> None:
        self.transport = transport
        self.request_delay = request_delay

    @staticmethod
    def parse(html: str) -> list[MaxPrepsRanking]:
        parser = _MaxPrepsRankingsParser()
        parser.feed(html)
        rankings: list[MaxPrepsRanking] = []
        for row in parser.rows:
            try:
                rankings.append(
                    MaxPrepsRanking(
                        state_rank=int(row["rank"]),
                        team_name=row["team"],
                        record=row.get("overall", ""),
                        rating=float(row["rating"]),
                        strength=float(row.get("strength") or 0.0),
                        team_url=row.get("team_url", ""),
                    )
                )
            except (KeyError, ValueError) as error:
                raise ValueError(f"Invalid MaxPreps ranking row: {row}") from error
        return rankings

    @staticmethod
    def _updated_at(html: str) -> str | None:
        match = re.search(r"Last updated:(?:<!-- -->)?\s*([^<]+)", html, flags=re.IGNORECASE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _read_cache(cache_path: Path) -> MaxPrepsFetch:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        rankings = [MaxPrepsRanking(**item) for item in payload["rankings"]]
        ranks = [row.state_rank for row in rankings]
        if len(rankings) < 200 or len(ranks) != len(set(ranks)):
            raise ValueError(f"Cached MaxPreps statewide data is incomplete or duplicated ({len(rankings)} rows)")
        return MaxPrepsFetch(
            rankings=rankings,
            retrieved_at=_parse_timestamp(payload["retrieved_at"]),
            source_updated_at=payload.get("source_updated_at"),
            used_cache=True,
        )

    def fetch(self, cache_path: Path) -> MaxPrepsFetch:
        retrieved_at = datetime.now(timezone.utc)
        rankings: list[MaxPrepsRanking] = []
        source_updated_at: str | None = None
        try:
            for page in range(1, 21):
                html = self.transport(MAXPREPS_RANKINGS_URL.format(page=page)).decode("utf-8", errors="replace")
                page_rows = self.parse(html)
                if page == 1:
                    source_updated_at = self._updated_at(html)
                if not page_rows:
                    if page == 1:
                        raise ValueError("MaxPreps first rankings page contained no rows")
                    break
                rankings.extend(page_rows)
                if len(page_rows) < 25:
                    break
                time.sleep(self.request_delay)
            else:
                raise ValueError("MaxPreps pagination exceeded 20 pages")

            ranks = [row.state_rank for row in rankings]
            if len(rankings) < 200 or len(ranks) != len(set(ranks)):
                raise ValueError(f"MaxPreps statewide parse was incomplete or duplicated ({len(rankings)} rows)")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "source": MAXPREPS_RANKINGS_URL.format(page=1),
                        "retrieved_at": retrieved_at.isoformat(),
                        "source_updated_at": source_updated_at,
                        "rankings": [asdict(row) for row in rankings],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            return MaxPrepsFetch(rankings, retrieved_at, source_updated_at)
        except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError, json.JSONDecodeError):
            if cache_path.exists():
                return self._read_cache(cache_path)
            raise


@dataclass(frozen=True)
class MaxPrepsScoreFetch:
    games: list[MaxPrepsScoreObservation]
    retrieved_at: datetime
    source_urls: list[str]
    cached_team_ids: tuple[str, ...] = ()
    failed_team_ids: tuple[str, ...] = ()


class MaxPrepsScoreProvider:
    """Read MaxPreps team schedules only for unresolved MHSAA games."""

    _SCORE_RE = re.compile(r"\b(won|lost|tied)\b.*?\bby a score of\s+(\d+)-(\d+)", re.IGNORECASE)
    _ACTOR_RE = re.compile(
        r"\bthe (.+?) varsity (?:boys )?football team (won|lost|tied)\b",
        re.IGNORECASE,
    )

    def __init__(self, transport: Callable[..., bytes] = _request_bytes, request_delay: float = 0.10) -> None:
        self.transport = transport
        self.request_delay = request_delay

    @staticmethod
    def _schedule_url(team_url: str) -> str:
        absolute = urljoin(MAXPREPS_ROOT, team_url)
        path = urlparse(absolute).path.rstrip("/")
        if path.endswith("/schedule"):
            return absolute
        if not path.endswith("/football"):
            raise ValueError(f"Unexpected MaxPreps football team URL: {team_url}")
        return absolute.rstrip("/") + "/schedule/"

    @staticmethod
    def _event_objects(value: Any):
        if isinstance(value, dict):
            event_type = value.get("@type")
            if event_type == "SportsEvent" or isinstance(event_type, list) and "SportsEvent" in event_type:
                yield value
            for child in value.values():
                yield from MaxPrepsScoreProvider._event_objects(child)
        elif isinstance(value, list):
            for child in value:
                yield from MaxPrepsScoreProvider._event_objects(child)

    @staticmethod
    def _team_name(value: Any) -> str:
        return value.get("name", "").strip() if isinstance(value, dict) else ""

    @staticmethod
    def _team_url(value: Any) -> str:
        return value.get("url", "").strip() if isinstance(value, dict) else ""

    @staticmethod
    def _same_team_url(left: str, right: str) -> bool:
        return urlparse(urljoin(MAXPREPS_ROOT, left)).path.rstrip("/").lower() == urlparse(
            urljoin(MAXPREPS_ROOT, right)
        ).path.rstrip("/").lower()

    @staticmethod
    def _game_id(event_url: str) -> str:
        contest_id = parse_qs(urlparse(event_url).query).get("c", [])
        return contest_id[0] if contest_id else event_url

    @classmethod
    def parse(
        cls,
        html: str,
        *,
        source_team_id: str,
        source_team_name: str,
        source_team_url: str,
        retrieved_at: datetime,
    ) -> list[MaxPrepsScoreObservation]:
        parser = _JsonLdParser()
        parser.feed(html)
        observations: list[MaxPrepsScoreObservation] = []
        seen_urls: set[str] = set()

        for document in parser.documents:
            try:
                decoded = json.loads(document)
            except json.JSONDecodeError:
                continue
            for event in cls._event_objects(decoded):
                event_url = str(event.get("url") or "")
                if not event_url or event_url in seen_urls:
                    continue
                seen_urls.add(event_url)
                home = event.get("homeTeam")
                away = event.get("awayTeam")
                home_name = cls._team_name(home)
                away_name = cls._team_name(away)
                start = event.get("startDate")
                if not home_name or not away_name or not start:
                    continue

                if cls._same_team_url(cls._team_url(home), source_team_url):
                    source_side = "home"
                elif cls._same_team_url(cls._team_url(away), source_team_url):
                    source_side = "away"
                elif normalize_name(home_name) == normalize_name(source_team_name):
                    source_side = "home"
                elif normalize_name(away_name) == normalize_name(source_team_name):
                    source_side = "away"
                else:
                    continue

                description = str(event.get("description") or "")
                lowered = description.lower()
                event_status = str(event.get("eventStatus") or "").lower()
                forfeit = "forfeit" in lowered
                status = "UPCOMING"
                source_score: int | None = None
                opponent_score: int | None = None
                actor_match = cls._ACTOR_RE.search(description)
                actor_side = source_side
                if actor_match:
                    actor_name = actor_match.group(1)
                    if normalize_name(actor_name) == normalize_name(home_name):
                        actor_side = "home"
                    elif normalize_name(actor_name) == normalize_name(away_name):
                        actor_side = "away"

                score_match = cls._SCORE_RE.search(description)
                if score_match:
                    result, high_text, low_text = score_match.groups()
                    high, low = int(high_text), int(low_text)
                    if result.lower() == "won":
                        source_score, opponent_score = high, low
                    elif result.lower() == "lost":
                        source_score, opponent_score = low, high
                    else:
                        source_score, opponent_score = high, low
                    status = "COMPLETED"
                elif forfeit and re.search(r"\b(won|lost)\b", lowered):
                    source_won = bool(re.search(r"\bwon\b", lowered))
                    source_score, opponent_score = ((2, 0) if source_won else (0, 2))
                    status = "COMPLETED"
                elif "eventcancelled" in event_status or "canceled" in lowered or "cancelled" in lowered:
                    status = "CANCELLED"
                elif "eventpostponed" in event_status or "postponed" in lowered:
                    status = "POSTPONED"

                if actor_side == "home":
                    home_score, away_score = source_score, opponent_score
                else:
                    home_score, away_score = opponent_score, source_score
                observations.append(
                    MaxPrepsScoreObservation(
                        game_id=cls._game_id(event_url),
                        date=_parse_timestamp(str(start)).astimezone(CENTRAL),
                        home_name=home_name,
                        away_name=away_name,
                        home_score=home_score,
                        away_score=away_score,
                        status=status,
                        forfeit=forfeit,
                        source_url=event_url,
                        observed_from_team_id=source_team_id,
                        retrieved_at=retrieved_at,
                    )
                )
        return observations

    @staticmethod
    def _read_cache(cache_path: Path) -> tuple[list[MaxPrepsScoreObservation], datetime]:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        retrieved_at = _parse_timestamp(payload["retrieved_at"])
        games = [
            MaxPrepsScoreObservation(
                **{
                    **item,
                    "date": _parse_timestamp(item["date"]),
                    "retrieved_at": _parse_timestamp(item["retrieved_at"]),
                }
            )
            for item in payload.get("games", [])
        ]
        return games, retrieved_at

    def fetch(self, team_sources: dict[str, MaxPrepsSignal], cache_dir: Path) -> MaxPrepsScoreFetch:
        retrieved_at = datetime.now(timezone.utc)
        games: list[MaxPrepsScoreObservation] = []
        source_urls: list[str] = []
        cached_team_ids: list[str] = []
        failed_team_ids: list[str] = []

        for index, (team_id, signal) in enumerate(sorted(team_sources.items())):
            cache_path = cache_dir / f"{team_id}.json"
            try:
                schedule_url = self._schedule_url(signal.source_url)
                html = self.transport(schedule_url).decode("utf-8", errors="replace")
                parsed = self.parse(
                    html,
                    source_team_id=team_id,
                    source_team_name=signal.source_name,
                    source_team_url=signal.source_url,
                    retrieved_at=retrieved_at,
                )
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(
                    json.dumps(
                        {
                            "source": schedule_url,
                            "retrieved_at": retrieved_at.isoformat(),
                            "games": [game.to_dict() for game in parsed],
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                games.extend(parsed)
                source_urls.append(schedule_url)
            except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError, json.JSONDecodeError):
                if cache_path.exists():
                    cached_games, _ = self._read_cache(cache_path)
                    games.extend(cached_games)
                    cached_team_ids.append(team_id)
                    source_urls.append(str(json.loads(cache_path.read_text(encoding="utf-8")).get("source", "")))
                else:
                    failed_team_ids.append(team_id)
            if index + 1 < len(team_sources):
                time.sleep(self.request_delay)

        return MaxPrepsScoreFetch(
            games=games,
            retrieved_at=retrieved_at,
            source_urls=sorted({url for url in source_urls if url}),
            cached_team_ids=tuple(cached_team_ids),
            failed_team_ids=tuple(failed_team_ids),
        )

@dataclass(frozen=True)
class ScoreFetch:
    games: list[RawGame]
    retrieved_at: datetime
    raw_files: list[str]


class MHSAAOfficialScoreProvider:
    def __init__(self, transport: Callable[..., bytes] = _request_bytes, request_delay: float = 0.05) -> None:
        self.transport = transport
        self.request_delay = request_delay

    def _page(self, game_date: date, after: str | None) -> dict[str, Any]:
        body = json.dumps(
            {
                "query": SCORES_QUERY,
                "variables": {
                    "date": game_date.isoformat(),
                    "genderSport": ["FOOTBALL"],
                    "level": ["VARSITY"],
                    "after": after,
                },
            }
        ).encode("utf-8")
        payload = self.transport(
            SCORE_API_URL,
            method="POST",
            data=body,
            headers={"Content-Type": "application/json", "x-client-policy": "ms-mhsaa"},
        )
        decoded = json.loads(payload)
        if decoded.get("errors"):
            raise RuntimeError(f"MHSAA score query returned errors: {decoded['errors']}")
        return decoded

    def fetch_range(
        self,
        start_date: date,
        end_date: date,
        cache_dir: Path,
        *,
        refresh_recent_days: int = 14,
    ) -> ScoreFetch:
        if end_date < start_date:
            raise ValueError("end_date must not be before start_date")
        retrieved_at = datetime.now(timezone.utc)
        games: list[RawGame] = []
        raw_files: list[str] = []
        current = start_date
        while current <= end_date:
            cache_path = cache_dir / f"{current.isoformat()}.json"
            recent = (end_date - current).days <= refresh_recent_days
            if cache_path.exists() and not recent:
                decoded = json.loads(cache_path.read_text(encoding="utf-8"))
            else:
                nodes: list[dict[str, Any]] = []
                after: str | None = None
                while True:
                    page = self._page(current, after)
                    contests = page["data"]["contests"]
                    nodes.extend(contests["nodes"])
                    info = contests["pageInfo"]
                    if not info["hasNextPage"]:
                        break
                    after = info["endCursor"]
                    time.sleep(self.request_delay)
                decoded = {
                    "source": SCORE_API_URL,
                    "source_policy": "ms-mhsaa",
                    "retrieved_at": retrieved_at.isoformat(),
                    "date": current.isoformat(),
                    "nodes": nodes,
                }
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(decoded, indent=2) + "\n", encoding="utf-8")
            raw_files.append(str(cache_path))
            games.extend(self.parse_nodes(decoded.get("nodes", []), retrieved_at))
            current += timedelta(days=1)
        unique = {game.game_id: game for game in games}
        return ScoreFetch(list(unique.values()), retrieved_at, raw_files)

    @staticmethod
    def parse_nodes(nodes: list[dict[str, Any]], retrieved_at: datetime) -> list[RawGame]:
        games: list[RawGame] = []
        for node in nodes:
            participants = [p for p in node.get("contestParticipants", []) if p.get("participant", {}).get("__typename") == "Team"]
            if len(participants) != 2:
                continue
            by_location = {p.get("location"): p for p in participants}
            home = by_location.get("HOME")
            away = by_location.get("AWAY")
            neutral = False
            if home is None or away is None:
                home, away = participants[0], participants[1]
                neutral = True
            home_team = home["participant"]
            away_team = away["participant"]
            status = node.get("status") or "UPCOMING"
            long_status = (node.get("longStatusText") or "").lower()
            games.append(
                RawGame(
                    game_id=str(node["id"]),
                    date=_parse_timestamp(node["date"]),
                    home_name=home_team["name"],
                    away_name=away_team["name"],
                    home_source_id=str(home_team.get("id")) if home_team.get("id") is not None else None,
                    away_source_id=str(away_team.get("id")) if away_team.get("id") is not None else None,
                    home_score=home.get("score"),
                    away_score=away.get("score"),
                    neutral_site=neutral,
                    overtime="overtime" in long_status or " ot" in long_status,
                    forfeit="forfeit" in long_status or status == "FORFEIT",
                    source_timestamp=retrieved_at,
                    status=status,
                    expected_status=node.get("expectedStatus"),
                    contest_type=node.get("contestTypeLabel"),
                    home_city=_city(home_team.get("locationText")),
                    away_city=_city(away_team.get("locationText")),
                )
            )
        return games
