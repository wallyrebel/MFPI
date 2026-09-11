import snapshotData from '../data/current/overall.json';

export type ComponentValue = {
  raw: number;
  normalized: number;
  weight: number;
  contribution: number;
};

export type GameResult = {
  date: string;
  home: string;
  away: string;
  home_score: number;
  away_score: number;
  neutral?: boolean;
  overtime?: boolean;
  forfeit?: boolean;
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
  state_rank_change: number;
  class_rank_change: number;
  mfpi_change: number;
  pf_per_game: number;
  pa_per_game: number;
  up_games: number;
  same_class_games: number;
  down_games: number;
  schedule_direction: string;
  maxpreps_state_rank: number | null;
  maxpreps_rating: number | null;
  maxpreps_strength: number | null;
  components: Record<string, ComponentValue>;
  game_results: GameResult[];
  explanation: string;
};

type Snapshot = {
  metadata: {
    season: number;
    week: number;
    generated_at: string;
    formula_version: string;
    coverage_percentage: number;
    verified_games: number;
    expected_games: number;
    /** Display names for opponents that are played but not ranked, such as
     *  out-of-state teams carrying synthetic "external-…" ids. */
    opponent_names?: Record<string, string>;
  };
  rankings: Team[];
};

const snapshot = snapshotData as unknown as Snapshot;

export const metadata = snapshot.metadata;
export const teams = snapshot.rankings;

const byId = new Map(teams.map((row) => [row.team_id, row]));
const bySlug = new Map(teams.map((row) => [row.slug, row]));

export const CLASSES = ['7A', '6A', '5A', '4A', '3A', '2A', '1A'] as const;

/** Human-readable component labels and what each one measures. */
export const COMPONENT_LABELS: Record<string, [string, string]> = {
  performance: ['Opponent-adjusted performance', 'Margin of victory or defeat, adjusted for opponent strength and site.'],
  sos: ['MFPI strength of schedule', 'Average current rating of every opponent played.'],
  maxpreps_rank: ['Media rank', 'Statewide ordinal rank from the media feed, as a percentile.'],
  maxpreps_sos: ['Media strength of schedule', 'Published schedule-strength value from the media feed.'],
  record: ['Record', 'Wins plus half credit for ties, over games played.'],
  offense: ['Points scored', 'Points per game, capped at 49 in each game.'],
  defense: ['Points allowed', 'Defensive value derived from points allowed per game.'],
  recent: ['Recent form', 'Opponent-adjusted performance across the last three games.'],
};

export function getTeamBySlug(slug: string): Team | undefined {
  return bySlug.get(slug);
}

const opponentNames = snapshot.metadata.opponent_names ?? {};

export function teamLabel(teamId: string): string {
  const ranked = byId.get(teamId);
  if (ranked) return ranked.team;
  const named = opponentNames[teamId];
  if (named) return named;
  // A synthetic id must never reach the page as a team name.
  return teamId.startsWith('external-') ? 'Non-MHSAA opponent' : teamId;
}

export function classTeams(classification: string): Team[] {
  return teams
    .filter((row) => row.classification === classification)
    .sort((a, b) => a.class_rank - b.class_rank);
}

export type TeamGame = {
  date: string;
  opponentId: string;
  /** Route key for the opponent. Equal to team_id today, but the route is
   *  keyed on slug, so links must not assume the two stay identical. */
  opponentSlug: string | null;
  opponent: string;
  opponentRank: number | null;
  opponentClass: string | null;
  pointsFor: number;
  pointsAgainst: number;
  won: boolean;
  tie: boolean;
  site: 'Home' | 'Away' | 'Neutral';
  overtime: boolean;
  forfeit: boolean;
};

/** A team's completed games, oldest first. */
export function teamGames(team: Team): TeamGame[] {
  return team.game_results
    .map((game): TeamGame => {
      const isHome = game.home === team.team_id;
      const opponentId = isHome ? game.away : game.home;
      const pointsFor = isHome ? game.home_score : game.away_score;
      const pointsAgainst = isHome ? game.away_score : game.home_score;
      const opponent = byId.get(opponentId);
      return {
        date: game.date,
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
      };
    })
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function formatGameDate(value: string): string {
  return new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function longDate(value: string): string {
  return new Date(value).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}
