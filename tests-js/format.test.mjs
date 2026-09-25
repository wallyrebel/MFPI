// Display logic acceptance tests. Run: npm run test:site
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  calendarDate, shortDate, ratingChange, formatRatingChange, rankSentence, ratingSentence,
  stat, dataStatus, scoringAverages, round1, record,
} from '../app/lib/format.ts';

const snapshot = JSON.parse(readFileSync(new URL('../data/current/overall.json', import.meta.url), 'utf8'));

test('Friday night games stay on Friday regardless of server timezone', () => {
  assert.equal(calendarDate('2026-08-28T19:00:00-05:00'), '2026-08-28');
  assert.equal(shortDate(calendarDate('2026-09-11T19:00:00-05:00')), 'Sep 11');
  // Legacy date-only marker converted from 23:59 Pacific.
  assert.equal(calendarDate('2026-08-29T01:59:00-05:00'), '2026-08-28');
  assert.equal(calendarDate('2026-09-01T01:59:00-05:00'), '2026-08-31');
  assert.equal(calendarDate('2026-08-29T01:59:00-05:00', '2026-08-28'), '2026-08-28');
});

test('rank unchanged while rating increases (Tupelo regression)', () => {
  const tupelo = snapshot.rankings.find((row) => row.team_id === 'tupelo');
  assert.equal(rankSentence(tupelo.state_rank, tupelo.previous_state_rank), 'State ranking: unchanged at No. 1.');
  const change = ratingChange(tupelo.mfpi, tupelo.previous_mfpi);
  assert.ok(change > 0);
  assert.match(ratingSentence(tupelo.mfpi, change), /^MFPI rating: increased 3\.1 points to 96\.2\.$/);
});

test('rating unchanged while rank changes, and never -0.0', () => {
  assert.equal(ratingChange(11.6, 11.62793597), 0);
  assert.equal(formatRatingChange(ratingChange(11.6, 11.62793597)), '0.0');
  assert.equal(rankSentence(218, 221), 'State ranking: up 3 spots to No. 218 (from No. 221).');
  assert.equal(ratingSentence(11.6, 0), 'MFPI rating: unchanged at 11.6.');
});

test('missing previous snapshot reads NEW / not comparable', () => {
  assert.equal(ratingChange(50, null), null);
  assert.equal(formatRatingChange(null), 'NEW');
  assert.equal(rankSentence(5, null), 'State ranking: new at No. 5.');
  assert.match(ratingSentence(50, null), /not comparable/);
});

test('unknown data is never a fabricated zero (Cleveland Central regression)', () => {
  const cc = snapshot.rankings.find((row) => row.team_id === 'cleveland-central');
  assert.equal(dataStatus(cc), 'unavailable');
  assert.equal(scoringAverages(cc.team_id, cc.game_results), null);
  assert.equal(stat(null), '—');
  assert.equal(stat(Number.NaN), '—');
  assert.equal(dataStatus({ data_status: 'preseason', games_played: 0 }), 'preseason');
});

test('forfeits and unscored listings are excluded from actual scoring averages', () => {
  const games = [
    { home: 'a', away: 'b', home_score: 21, away_score: 7 },
    { home: 'c', away: 'a', home_score: 0, away_score: 2, forfeit: true },
    { home: 'a', away: 'd', home_score: null, away_score: null },
  ];
  assert.deepEqual(scoringAverages('a', games), { pointsFor: 21, pointsAgainst: 7, games: 1 });
  assert.deepEqual(record('a', games), { wins: 2, losses: 0, ties: 0 });
});

test('page averages match the exported snapshot for every team without forfeits', () => {
  for (const row of snapshot.rankings) {
    if (row.game_results.some((game) => game.forfeit) || row.games_played === 0) continue;
    const averages = scoringAverages(row.team_id, row.game_results);
    assert.equal(averages.pointsFor, row.pf_per_game, `${row.team_id} PF`);
    assert.equal(averages.pointsAgainst, row.pa_per_game, `${row.team_id} PA`);
  }
  assert.equal(round1(46.25), 46.2);
  assert.equal(round1(12.75), 12.8);
});

test('rounding: displayed rating change reconciles with displayed ratings', () => {
  for (const row of snapshot.rankings) {
    if (row.previous_mfpi === null) continue;
    const change = ratingChange(row.mfpi, row.previous_mfpi);
    assert.equal(round1(row.previous_mfpi + change), row.mfpi, row.team_id);
  }
});
