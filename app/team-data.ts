import snapshotData from '../data/current/overall.json';
import {
  calendarDate,
  centralDateTime,
  dataStatus,
  longDay,
  ratingChange,
  record as recordFromGames,
  scoringAverages,
  shortDate,
  type DataStatus,
} from './lib/format';

export type ComponentValue = {
  raw: number | null;
  normalized: number;
  weight: number;
  contribution: number;
};

export type GameResult = {
  date: string;
  calendar_date?: string;
  home: string;
  away: string;
  home_score: number;
  away_score: number;
  neutral?: boolean;
  overtime?: boolean;
  forfeit?: boolean;
  game_id?: string;
  source?: string;
};

export type Team = {
  team_id: string;
  slug: string;
  team: string;
  classification: string;
  region: string;
  record: string;
  games_played: number;
  state_rank: number;
  class_rank: number;
  mfpi: number;
  mfpi_unrounded: number;
  previous_state_rank: number | null;
  previous_class_rank: number | null;
  previous_mfpi: number | null;
  state_rank_change: number | null;
  class_rank_change: number | null;
  mfpi_change: number | null;
  pf_per_game: number | null;
  pa_per_game: number | null;
  pending_games?: number;
  data_status?: string;
  up_games: number;
  same_class_games: number;
  down_games: number;
  class_schedule_delta: number;
  schedule_direction: string;
  maxpreps_state_rank: number | null;
  maxpreps_rating: number | null;
  maxpreps_strength: number | null;
  components: Record<string, ComponentValue>;
  game_results: GameResult[];
  bye_adjustment?: { previous_weight: number; previous_mfpi: number; recalculated_mfpi: number; adjustment: number } | null;
  explanation: string;
};

export type SnapshotMeta = {
  season: number;
  week: number;
  generated_at: string;
  cutoff_at: string;
  formula_version: string;
  status: string;
  run_id?: string;
  validation_status?: string;
  coverage_percentage: number;
  verified_games?: number;
  expected_games?: number;
  missing_games?: number;
  data_sources: { name: string; url?: string; retrieved_at?: string; source_updated_at?: string }[];
  /** Display names for opponents that are played but not ranked, such as
   *  out-of-state teams carrying synthetic "external-…" ids. */
  opponent_names?: Record<string, string>;
};

type Snapshot = { metadata: SnapshotMeta; rankings: Team[] };

/** A listing from games.json (written by snapshots since this change). */
export type LedgerGame = {
  game_id: string;
  calendar_date: string;
  home: string;
  away: string;
  home_name: string;
  away_name: string;
  home_score: number | null;
  away_score: number | null;
  status_category: string;
  counts_toward_record: boolean;
};

// Source abbreviations that are not the school's name. Everything else is
// shown exactly as the MHSAA classification list gives it.
const DISPLAY_NAME_OVERRIDES: Record<string, string> = {
  diberville: "D'Iberville High School",
};

const snapshot = snapshotData as unknown as Snapshot;
for (const row of snapshot.rankings) {
  row.team = DISPLAY_NAME_OVERRIDES[row.team_id] ?? row.team;
}

// games.json is optional: snapshots published before it existed simply have
// no pending-listing detail. import.meta.glob returns {} when it is absent.
const ledgerModules = import.meta.glob('../data/current/games.json', { eager: true, import: 'default' }) as Record<string, { games: LedgerGame[] }>;
const ledger: LedgerGame[] = Object.values(ledgerModules)[0]?.games ?? [];

export const metadata = snapshot.metadata;
export const teams = snapshot.rankings;
export const hasLedger = ledger.length > 0;

const byId = new Map(teams.map((row) => [row.team_id, row]));
const bySlug = new Map(teams.map((row) => [row.slug, row]));

export const CLASSES = ['7A', '6A', '5A', '4A', '3A', '2A', '1A'] as const;

/** Human-readable component labels and what each one measures. */
export const COMPONENT_LABELS: Record<string, [string, string]> = {
  performance: ['Opponent-adjusted performance', 'Margin of victory or defeat, adjusted for opponent strength and site.'],
  sos: ['MFPI strength of schedule', 'Average current rating of every opponent played.'],
  maxpreps_rank: ['Media rank (MaxPreps)', 'Statewide ordinal rank in the MaxPreps Mississippi rankings, as a percentile.'],
  maxpreps_sos: ['Media strength of schedule (MaxPreps)', 'Published MaxPreps schedule-strength value.'],
  record: ['Record', 'Wins plus half credit for ties, over games played.'],
  offense: ['Points scored', 'Points per game, capped at 49 in each game.'],
  defense: ['Points allowed', 'Defensive value derived from points allowed per game.'],
  recent: ['Recent form', 'Opponent-adjusted performance across the last three games.'],
};

export function getTeamBySlug(slug: string): Team | undefined {
  return bySlug.get(slug);
}

export function getTeamById(teamId: string): Team | undefined {
  return byId.get(teamId);
}

const opponentNames = snapshot.metadata.opponent_names ?? {};

export function teamLabel(teamId: string): string {
  const ranked = byId.get(teamId);
  if (ranked) return ranked.team;
  const named = opponentNames[teamId];
  if (named) return named;
  // Out-of-state and other non-MHSAA opponents are listed by name; the
  // classification column is what marks them as outside the MHSAA. Only an
  // opponent the feed never named falls through here, and a synthetic
  // "external-…" id must never surface as if it were a team name.
  return teamId.startsWith('external-') ? 'Opponent' : teamId;
}

export function classTeams(classification: string): Team[] {
  return teams
    .filter((row) => row.classification === classification)
    .sort((a, b) => a.class_rank - b.class_rank);
}

export type TeamGame = {
  day: string;
  opponentId: string;
  /** Route key for the opponent. Equal to team_id today, but the route is
   *  keyed on slug, so links must not assume the two stay identical. */
  opponentSlug: string | null;
  opponent: string;
  /** Opponent's rank in the current snapshot, not at game time. */
  opponentRank: number | null;
  opponentClass: string | null;
  pointsFor: number;
  pointsAgainst: number;
  won: boolean;
  tie: boolean;
  site: 'Home' | 'Away' | 'Neutral';
  overtime: boolean;
  forfeit: boolean;
  /** Either team is credited with another game on this date: a listing under review. */
  underReview: boolean;
};

// Team/date pairs with more than one counted game. One listing may belong to a
// same-named school; both teams' pages say so until it is resolved.
const doubleBooked = new Set<string>();
for (const row of teams) {
  const seen = new Set<string>();
  for (const game of row.game_results) {
    const day = calendarDate(game.date, game.calendar_date);
    if (seen.has(day)) doubleBooked.add(`${row.team_id}|${day}`);
    seen.add(day);
  }
}

export function doubleBookedDays(team: Team): string[] {
  return [...doubleBooked].filter((key) => key.startsWith(`${team.team_id}|`)).map((key) => key.split('|')[1]);
}

/** A team's counted (verified, completed) games, oldest first. */
export function teamGames(team: Team): TeamGame[] {
  return team.game_results
    .map((game): TeamGame => {
      const isHome = game.home === team.team_id;
      const opponentId = isHome ? game.away : game.home;
      const pointsFor = isHome ? game.home_score : game.away_score;
      const pointsAgainst = isHome ? game.away_score : game.home_score;
      const opponent = byId.get(opponentId);
      const day = calendarDate(game.date, game.calendar_date);
      return {
        day,
        opponentId,
        opponentSlug: opponent?.slug ?? null,
        opponent: opponent?.team ?? teamLabel(opponentId),
        opponentRank: opponent?.state_rank ?? null,
        opponentClass: opponent?.classification ?? null,
        pointsFor,
        pointsAgainst,
        won: pointsFor > pointsAgainst,
        tie: pointsFor === pointsAgainst,
        site: game.neutral ? 'Neutral' : isHome ? 'Home' : 'Away',
        overtime: Boolean(game.overtime),
        forfeit: Boolean(game.forfeit),
        underReview: doubleBooked.has(`${team.team_id}|${day}`) || doubleBooked.has(`${opponentId}|${day}`),
      };
    })
    .sort((a, b) => a.day.localeCompare(b.day));
}

/** Listings for this team that do not count toward its record (pending, postponed, cancelled, scheduled). */
export function otherListings(team: Team): (LedgerGame & { opponentId: string; opponentName: string; home: string })[] {
  return ledger
    .filter((game) => (game.home === team.team_id || game.away === team.team_id) && !game.counts_toward_record)
    .map((game) => {
      const home = game.home === team.team_id;
      const opponentId = home ? game.away : game.home;
      return { ...game, opponentId, opponentName: byId.get(opponentId)?.team ?? (home ? game.away_name : game.home_name) };
    })
    .sort((a, b) => a.calendar_date.localeCompare(b.calendar_date));
}

export function teamStatus(team: Team): DataStatus {
  return dataStatus(team);
}

/** Actual scoring averages over played games; null when there are none. */
export function teamScoring(team: Team) {
  return scoringAverages(team.team_id, team.game_results);
}

export function teamRecordFromGames(team: Team) {
  return recordFromGames(team.team_id, team.game_results);
}

export function teamRatingChange(team: Team): number | null {
  return ratingChange(team.mfpi, team.previous_mfpi);
}

export function formatGameDate(day: string): string {
  return shortDate(day);
}

export function longDate(value: string): string {
  return centralDateTime(value, false);
}

export { longDay };
