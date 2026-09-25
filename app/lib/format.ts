// Pure display helpers shared by every page. No imports, so the Node test
// runner can load this file directly (see tests-js/).

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const LONG_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/**
 * The calendar date of a game, as YYYY-MM-DD, with no timezone conversion.
 *
 * Snapshot timestamps are Central wall-clock strings. Formatting them with
 * `new Date(...)` on the server (UTC) moved every Friday-night game to
 * Saturday. Older snapshots also stored "time not published" markers from a
 * Pacific-time feed as 01:59 Central the next morning; no game kicks off
 * between midnight and 5 a.m., so those belong to the previous date.
 */
export function calendarDate(iso: string, explicit?: string | null): string {
  if (explicit && /^\d{4}-\d{2}-\d{2}$/.test(explicit)) return explicit;
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/.exec(iso);
  if (!match) return iso.slice(0, 10);
  const [, y, m, d, hh] = match;
  const hour = hh === undefined ? 12 : Number(hh);
  if (hour <= 4) {
    const previous = new Date(Date.UTC(Number(y), Number(m) - 1, Number(d) - 1));
    return previous.toISOString().slice(0, 10);
  }
  return `${y}-${m}-${d}`;
}

export function shortDate(day: string): string {
  const [, m, d] = day.split('-').map(Number);
  return `${MONTHS[m - 1]} ${d}`;
}

export function longDay(day: string): string {
  const [y, m, d] = day.split('-').map(Number);
  return `${LONG_MONTHS[m - 1]} ${d}, ${y}`;
}

/** A real instant (generated_at, cutoff_at) shown in Central time. */
export function centralDateTime(iso: string, withTime = true): string {
  const options: Intl.DateTimeFormatOptions = withTime
    ? { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago', timeZoneName: 'short' }
    : { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'America/Chicago' };
  return new Intl.DateTimeFormat('en-US', options).format(new Date(iso));
}

export function centralWeekdayTime(iso: string): string {
  return new Intl.DateTimeFormat('en-US', {
    weekday: 'short', hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago', timeZoneName: 'short',
  }).format(new Date(iso));
}

/** Whole days between two instants, floored. */
export function ageInDays(fromIso: string, now: Date): number {
  return Math.floor((now.getTime() - new Date(fromIso).getTime()) / 86_400_000);
}

/**
 * One-decimal rounding that matches Python's round(), which the snapshot and
 * CSV exports use: exact halves go to the even digit (46.25 -> 46.2). Plain
 * Math.round would show 46.3 on the page and 46.2 in the export.
 */
export function round1(value: number): number {
  const scaled = value * 10;
  const floor = Math.floor(scaled);
  const diff = scaled - floor;
  if (Math.abs(diff - 0.5) < 1e-9) return (floor % 2 === 0 ? floor : floor + 1) / 10;
  return Math.round(scaled) / 10;
}

/**
 * Rating change as readers see it: displayed rating minus displayed previous
 * rating, so "93.1 -> 96.2" always reads +3.1. Never returns -0.
 */
export function ratingChange(mfpi: number, previousMfpi: number | null | undefined): number | null {
  if (previousMfpi === null || previousMfpi === undefined) return null;
  const change = round1(round1(mfpi) - round1(previousMfpi));
  return change === 0 ? 0 : change;
}

export function formatRatingChange(change: number | null): string {
  if (change === null) return 'NEW';
  if (change === 0) return '0.0';
  return `${change > 0 ? '+' : '−'}${Math.abs(change).toFixed(1)}`;
}

export function rankSentence(rank: number, previousRank: number | null | undefined, scope = 'State ranking'): string {
  if (previousRank === null || previousRank === undefined) return `${scope}: new at No. ${rank}.`;
  const change = previousRank - rank;
  const spots = (n: number) => `${n} spot${n === 1 ? '' : 's'}`;
  if (change > 0) return `${scope}: up ${spots(change)} to No. ${rank} (from No. ${previousRank}).`;
  if (change < 0) return `${scope}: down ${spots(-change)} to No. ${rank} (from No. ${previousRank}).`;
  return `${scope}: unchanged at No. ${rank}.`;
}

export function ratingSentence(mfpi: number, change: number | null): string {
  if (change === null) return `MFPI rating: ${mfpi.toFixed(1)} (not comparable; no previous rating).`;
  if (change > 0) return `MFPI rating: increased ${change.toFixed(1)} points to ${mfpi.toFixed(1)}.`;
  if (change < 0) return `MFPI rating: decreased ${Math.abs(change).toFixed(1)} points to ${mfpi.toFixed(1)}.`;
  return `MFPI rating: unchanged at ${mfpi.toFixed(1)}.`;
}

/** Display a statistic that may be unavailable; never invent a zero. */
export function stat(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined || !Number.isFinite(value) ? '—' : value.toFixed(digits);
}

export type DataStatus = 'complete' | 'partial' | 'unavailable' | 'preseason';

/** Older snapshots lack data_status; zero games is then "unavailable", never a verified 0-0. */
export function dataStatus(team: { data_status?: string | null; games_played: number; pending_games?: number | null }): DataStatus {
  const known = team.data_status;
  if (known === 'complete' || known === 'partial' || known === 'unavailable' || known === 'preseason') return known;
  if (team.games_played === 0) return 'unavailable';
  return team.pending_games ? 'partial' : 'complete';
}

export type ScoredGame = { home: string; away: string; home_score: number | null; away_score: number | null; forfeit?: boolean };

/**
 * Actual points for/against per game over games that were played. Forfeits
 * (administrative results) and unscored listings are excluded, and no games
 * means no average rather than 0.0. The MFPI's capped inputs are separate.
 */
export function scoringAverages(teamId: string, games: ScoredGame[]): { pointsFor: number; pointsAgainst: number; games: number } | null {
  let pf = 0;
  let pa = 0;
  let n = 0;
  for (const game of games) {
    if (game.forfeit || game.home_score === null || game.away_score === null) continue;
    const home = game.home === teamId;
    pf += home ? game.home_score : game.away_score;
    pa += home ? game.away_score : game.home_score;
    n += 1;
  }
  if (n === 0) return null;
  return { pointsFor: round1(pf / n), pointsAgainst: round1(pa / n), games: n };
}

export function record(teamId: string, games: ScoredGame[]): { wins: number; losses: number; ties: number } {
  let wins = 0;
  let losses = 0;
  let ties = 0;
  for (const game of games) {
    if (game.home_score === null || game.away_score === null) continue;
    const home = game.home === teamId;
    const f = home ? game.home_score : game.away_score;
    const a = home ? game.away_score : game.home_score;
    if (f > a) wins += 1;
    else if (f < a) losses += 1;
    else ties += 1;
  }
  return { wins, losses, ties };
}

export function ordinal(value: number): string {
  const tens = value % 100;
  const suffix = tens >= 11 && tens <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[value % 10] ?? 'th';
  return `${value}${suffix}`;
}
