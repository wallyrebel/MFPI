import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { SiteFooter, SiteHeader } from '../../site-nav';
import { siteUrl } from '../../site';
import { pageAds } from '../../ads/page-ads';
import { loadPreviousWeek } from '../../archive-data';
import { centralDateTime, formatRatingChange, rankSentence, ratingSentence, shortDate, stat } from '../../lib/format';
import {
  COMPONENT_LABELS,
  classTeams,
  doubleBookedDays,
  formatGameDate,
  getTeamBySlug,
  hasLedger,
  longDate,
  metadata as snapshotMeta,
  otherListings,
  teamGames,
  teamRatingChange,
  teamScoring,
  teamStatus,
  teams,
  type Team,
  type TeamGame,
} from '../../team-data';

type Params = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return teams.map((row) => ({ slug: row.slug }));
}

function groupLabel(row: Team) {
  return `Class ${row.classification}${row.region ? `, Region ${row.region}` : ''}`;
}

const cutoffLabel = shortDate(new Date(snapshotMeta.cutoff_at).toLocaleDateString('en-CA', { timeZone: 'America/Chicago' }));

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  const row = getTeamBySlug(slug);
  if (!row) return {};
  const title = `${row.team} Football — Rankings, Record & Schedule`;
  const recordText = teamStatus(row) === 'unavailable' ? 'with season results not yet available' : `at ${row.record}`;
  const description = `${row.team} is No. ${row.state_rank} in the ${snapshotMeta.season} Mississippi Football Power Index ${recordText} (${groupLabel(row)}). Week ${snapshotMeta.week} rating, schedule, scores and strength of schedule.`;
  return {
    title,
    description,
    alternates: { canonical: `/team/${row.slug}` },
    openGraph: { type: 'article', url: `${siteUrl}/team/${row.slug}`, title, description },
    twitter: { card: 'summary_large_image', title, description },
  };
}

function resultText(game: TeamGame) {
  const letter = game.tie ? 'T' : game.won ? 'W' : 'L';
  const where = game.site === 'Home' ? 'vs.' : game.site === 'Away' ? 'at' : 'vs. (neutral)';
  return `${letter} ${game.pointsFor}–${game.pointsAgainst} ${where} ${game.opponent} (${formatGameDate(game.day)})`;
}

function OpponentLink({ game }: { game: TeamGame }) {
  return game.opponentSlug ? <Link href={`/team/${game.opponentSlug}`}>{game.opponent}</Link> : <>{game.opponent}</>;
}

export default async function TeamPage({ params }: Params) {
  const { slug } = await params;
  const row = getTeamBySlug(slug);
  if (!row) notFound();

  const status = teamStatus(row);
  const unavailable = status === 'unavailable';
  const provisional = unavailable || snapshotMeta.status === 'PROVISIONAL';
  const games = teamGames(row);
  const listings = otherListings(row);
  const scoring = teamScoring(row);
  const ratingDelta = teamRatingChange(row);
  const peers = classTeams(row.classification);
  const overall = teams.findIndex((peer) => peer.team_id === row.team_id);
  const ahead = teams[overall - 1];
  const behind = teams[overall + 1];

  // "Strongest win": the defeated MHSAA opponent with the best *current* MFPI
  // rank. Out-of-state and non-MHSAA opponents have no MFPI rank.
  const mhsaaWins = games.filter((game) => game.won && game.opponentRank !== null);
  const bestWin = [...mhsaaWins].sort((a, b) => a.opponentRank! - b.opponentRank!)[0];
  const otherWins = games.filter((game) => game.won && game.opponentRank === null);
  const recent = [...games].reverse().slice(0, 3);
  const nonMhsaaGames = games.filter((game) => game.opponentRank === null).length;
  const conflictDays = doubleBookedDays(row);

  const previous = await loadPreviousWeek(snapshotMeta.season, snapshotMeta.week);
  const previousRow = previous?.rankings.find((item) => item.team_id === row.team_id);
  const componentMoves = previousRow
    ? Object.entries(row.components)
        .filter(([key]) => COMPONENT_LABELS[key] && previousRow.components[key])
        .map(([key, value]) => ({ key, delta: value.contribution - previousRow.components[key].contribution }))
        .filter((item) => Math.abs(item.delta) >= 0.1)
        .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
        .slice(0, 3)
    : [];

  const orderedComponents = Object.entries(row.components)
    .filter(([key]) => COMPONENT_LABELS[key])
    .sort((a, b) => b[1].weight - a[1].weight);

  const ads = pageAds(
    { kind: 'team', substantive: games.length > 0, teamDataStatus: status },
    ['team-mid', 'team-bottom'],
  );

  const structuredData = {
    '@context': 'https://schema.org',
    '@type': 'SportsTeam',
    name: row.team,
    sport: 'American Football',
    url: `${siteUrl}/team/${row.slug}`,
    memberOf: { '@type': 'SportsOrganization', name: `MHSAA Class ${row.classification}` },
    description: `${row.team} is ranked No. ${row.state_rank} of ${teams.length} in the Mississippi Football Power Index${unavailable ? '' : ` with a ${row.record} record`}.`,
  };

  return (
    <>
      <SiteHeader />
      {ads.script}
      <main className="page-shell">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, '\\u003c') }} />

        <nav className="mf-crumbs" aria-label="Breadcrumb">
          <Link href="/">Rankings</Link> <span>/</span> <Link href="/teams">Teams</Link> <span>/</span> <span>{row.team}</span>
        </nav>

        <section className="mf-team-hero">
          <div>
            <p className="eyebrow">{groupLabel(row)} · Week {snapshotMeta.week}, {snapshotMeta.season}</p>
            <h1>{row.team}</h1>
            {unavailable && (
              <p className="mf-data-notice" role="note">
                <strong>Season data incomplete.</strong> No verified results are linked to {row.team} for the Week{' '}
                {snapshotMeta.week} cutoff ({cutoffLabel}). Its record and scoring averages are unavailable, and its
                rating is provisional — it rests on class, media and neutral inputs rather than games.
              </p>
            )}
            {conflictDays.length > 0 && (
              <p className="mf-data-notice" role="note">
                <strong>Listing under review.</strong> {row.team} is credited with two games on{' '}
                {conflictDays.map(formatGameDate).join(', ')}. One of those listings may belong to a same-named school; until
                it is resolved it affects this team&apos;s record and rating and its opponents&apos;.
              </p>
            )}
            <p className="hero-copy">
              {row.team} is <strong>No. {row.state_rank}</strong> of {teams.length} teams in the Mississippi Football
              Power Index and <strong>No. {row.class_rank}</strong> of {peers.length} in Class {row.classification}.{' '}
              {unavailable
                ? <>Its record at the cutoff is unavailable.</>
                : <>Record at the Week {snapshotMeta.week} cutoff: <strong>{row.record}</strong> in {row.games_played} verified game{row.games_played === 1 ? '' : 's'}.</>}
            </p>
            <ul className="mf-movement" aria-label="Movement since last week">
              <li>{rankSentence(row.state_rank, row.previous_state_rank)}</li>
              <li>{rankSentence(row.class_rank, row.previous_class_rank, `Class ${row.classification} ranking`)}</li>
              <li>{ratingSentence(row.mfpi, ratingDelta)}{provisional && ' (provisional)'}</li>
            </ul>
          </div>
          <aside className="run-card">
            <span className="run-card-label">MFPI rating</span>
            <strong className="mf-big-score">{row.mfpi.toFixed(1)}</strong>
            {provisional && <span className="mf-provisional-tag">Provisional</span>}
            <dl>
              <div><dt>Statewide</dt><dd>No. {row.state_rank}</dd></div>
              <div><dt>Class {row.classification}</dt><dd>No. {row.class_rank}</dd></div>
              <div><dt>Record</dt><dd>{unavailable ? '—' : row.record}</dd></div>
              <div><dt>Points/game</dt><dd>{stat(scoring?.pointsFor)}</dd></div>
              <div><dt>Allowed/game</dt><dd>{stat(scoring?.pointsAgainst)}</dd></div>
              <div><dt>Media rank</dt><dd>{row.maxpreps_state_rank ? `No. ${row.maxpreps_state_rank}` : '—'}</dd></div>
              <div><dt>Previous rating</dt><dd>{row.previous_mfpi === null ? '—' : row.previous_mfpi.toFixed(1)}</dd></div>
              <div><dt>Rating change</dt><dd>{formatRatingChange(ratingDelta)}</dd></div>
            </dl>
          </aside>
        </section>

        <section className="rankings-panel mf-story">
          <div className="rankings-title-row">
            <div><p className="eyebrow">Week {snapshotMeta.week} explanation</p><h2>Why {row.team} is ranked here</h2></div>
          </div>
          <div className="mf-story-body">
            {unavailable ? (
              <p>
                MFPI cannot describe results for {row.team} yet: the official score feed has no verified games linked to
                this team for this cutoff. That is a data gap, not a record of 0–0 and not evidence that no games were
                played. When results are linked, this page will show them and the rating will be recalculated in the next
                weekly run. If you have a score, please <Link href="/contact">send a correction</Link>.
              </p>
            ) : (
              <>
                <h3>Strongest result</h3>
                <p>
                  {bestWin ? (
                    <>A {bestWin.pointsFor}–{bestWin.pointsAgainst} win over <OpponentLink game={bestWin} /> on{' '}
                      {formatGameDate(bestWin.day)} ({bestWin.site.toLowerCase()}), an opponent currently No. {bestWin.opponentRank} statewide.</>
                  ) : (
                    <>No wins over MHSAA opponents in the verified results{otherWins.length > 0
                      ? <>; its {otherWins.length === 1 ? 'win came' : 'wins came'} against non-MHSAA opponents ({otherWins.map((game) => game.opponent).join(', ')}).</>
                      : '.'}</>
                  )}{' '}
                  <span className="secondary">&ldquo;Strongest&rdquo; means the defeated MHSAA opponent with the best current MFPI rank, not its rank when the game was played.</span>
                </p>
                <h3>Recent results</h3>
                <p>{recent.map(resultText).join('; ')}. Recent-form percentile: {row.components.recent?.normalized.toFixed(1) ?? '—'}.</p>
                <h3>Schedule strength</h3>
                <p>
                  MFPI strength-of-schedule percentile {row.components.sos.normalized.toFixed(1)} (100 = the strongest
                  completed schedule statewide). Classification path: {row.schedule_direction.toLowerCase()} —{' '}
                  {row.up_games} game{row.up_games === 1 ? '' : 's'} against higher classes, {row.same_class_games} in Class{' '}
                  {row.classification}, {row.down_games} against lower classes
                  {nonMhsaaGames > 0 && <>, and {nonMhsaaGames} against non-MHSAA or out-of-state opponents (rated by results, not by class)</>}.
                </p>
              </>
            )}
            <h3>What changed this week</h3>
            <p>
              Rank and rating are separate measures. {rankSentence(row.state_rank, row.previous_state_rank)}{' '}
              {ratingSentence(row.mfpi, ratingDelta)}{' '}
              {row.bye_adjustment
                ? <>This was a confirmed bye, so the score keeps 90% of last week&apos;s {row.bye_adjustment.previous_mfpi.toFixed(2)} and 10% of this week&apos;s recalculated {row.bye_adjustment.recalculated_mfpi.toFixed(2)}.</>
                : null}
              {componentMoves.length > 0 && (
                <> Largest component changes since Week {snapshotMeta.week - 1}:{' '}
                  {componentMoves.map((item) => `${COMPONENT_LABELS[item.key][0].replace(' (MaxPreps)', '').toLowerCase()} ${item.delta > 0 ? '+' : '−'}${Math.abs(item.delta).toFixed(1)} pts`).join('; ')}.
                  Opponents&apos; ratings are re-solved every week, so these can move without a new game.</>
              )}
              {!previousRow && ' No comparable previous snapshot exists for this team.'}
            </p>
            <h3>Limitations</h3>
            <p>
              Ratings use only verified final scores through {centralDateTime(snapshotMeta.cutoff_at)}.{' '}
              {row.pending_games ? `${row.pending_games} listing(s) for this team were still awaiting a verified score. ` : ''}
              Media rank and media strength of schedule (from MaxPreps) contribute 20%. MFPI does not consider injuries,
              rosters or weather, and it is not a prediction.
            </p>
          </div>
        </section>

        {ads.slot('team-mid')}

        <section className="rankings-panel">
          <div className="rankings-title-row">
            <div><p className="eyebrow">{snapshotMeta.season} season</p><h2>Schedule &amp; results</h2></div>
            <span className="secondary">
              {unavailable ? 'Results unavailable' : `${row.record} · ${games.length} verified game${games.length === 1 ? '' : 's'}`}
            </span>
          </div>
          <div className="table-scroll" role="region" aria-label={`${row.team} results`} tabIndex={0}>
            <div className="table-head mf-game-grid"><span>Date</span><span>Opponent</span><span>Site</span><span>Result</span><span>Score</span><span>Opp. class</span></div>
            {games.map((game, index) => (
              <div className="mf-game-grid mf-game-row" key={`${game.day}-${index}`}>
                <span className="tabular">{formatGameDate(game.day)}</span>
                <span className="mf-game-opp">
                  <OpponentLink game={game} />
                  {game.opponentRank !== null && <small title="Current MFPI rank">No. {game.opponentRank}</small>}
                  {game.overtime && <small>OT</small>}
                  {game.forfeit && <small>Forfeit</small>}
                  {game.underReview && <small className="mf-review-tag">Under review</small>}
                </span>
                <span className="secondary">{game.site}</span>
                <span className={game.tie ? 'movement flat' : game.won ? 'mf-win' : 'mf-loss'}>{game.tie ? 'T' : game.won ? 'W' : 'L'}</span>
                <span className="tabular">{game.pointsFor}–{game.pointsAgainst}</span>
                <span className="secondary">{game.opponentClass ?? 'Non-MHSAA'}</span>
              </div>
            ))}
            {listings.map((game) => (
              <div className="mf-game-grid mf-game-row mf-game-pending" key={game.game_id}>
                <span className="tabular">{formatGameDate(game.calendar_date)}</span>
                <span className="mf-game-opp">{game.opponentName}</span>
                <span className="secondary">{game.home === row.team_id ? 'Home' : 'Away'}</span>
                <span className="secondary">—</span>
                <span className="secondary">{listingLabel(game.status_category)}</span>
                <span className="secondary">—</span>
              </div>
            ))}
            {games.length === 0 && listings.length === 0 && (
              <p className="table-note">
                Results unavailable: no verified games are linked to {row.team} in this snapshot.
                {!hasLedger && ' Unscored or postponed listings are not recorded in this snapshot.'}
              </p>
            )}
          </div>
          <p className="table-note">
            Dates are game dates in Central time. Opponent ranks are current MFPI ranks, not ranks at game time. Scores
            come from the official MHSAA score center, with MaxPreps team schedules used only to fill gaps. Week{' '}
            {snapshotMeta.week} statewide coverage: {snapshotMeta.coverage_percentage.toFixed(1)}% ({snapshotMeta.verified_games}{' '}
            of {snapshotMeta.expected_games} game listings due by the cutoff verified).
          </p>
        </section>

        <section className="method-card">
          <div>
            <p className="eyebrow">Why {row.team} rates {row.mfpi.toFixed(1)}</p>
            <h2>Rating breakdown</h2>
            <p className="method-copy">
              Each component becomes a statewide percentile, then carries its weight into the final score. Points are how
              many of the {row.mfpi.toFixed(1)} rating points come from that component
              {row.bye_adjustment ? ' before the bye-week adjustment' : ''}.
              {unavailable && ' With no verified games, game-based components sit at a neutral 50th percentile.'}
            </p>
          </div>
          <div className="component-grid mf-component-grid">
            {orderedComponents.map(([key, value]) => {
              const [label, note] = COMPONENT_LABELS[key];
              return (
                <div className="component-card" key={label}>
                  <span>{label}</span>
                  <strong>{value.normalized.toFixed(1)}</strong>
                  <small>{(value.weight * 100).toFixed(0)}% weight · {value.contribution.toFixed(1)} pts{value.raw === null ? ' · no data (neutral)' : ''}</small>
                  <i><b style={{ width: `${Math.max(0, Math.min(100, value.normalized))}%` }} /></i>
                  <small className="mf-component-note">{note}</small>
                </div>
              );
            })}
          </div>
        </section>

        {ads.slot('team-bottom')}

        <section className="mf-neighbors">
          <h2>Nearby in the statewide rankings</h2>
          <div>
            {ahead && <Link href={`/team/${ahead.slug}`}><small>No. {ahead.state_rank} · ahead</small><strong>{ahead.team}</strong><span>{teamStatus(ahead) === 'unavailable' ? 'Results unavailable' : ahead.record} · MFPI {ahead.mfpi.toFixed(1)}</span></Link>}
            {behind && <Link href={`/team/${behind.slug}`}><small>No. {behind.state_rank} · behind</small><strong>{behind.team}</strong><span>{teamStatus(behind) === 'unavailable' ? 'Results unavailable' : behind.record} · MFPI {behind.mfpi.toFixed(1)}</span></Link>}
          </div>
          <h2>Others in Class {row.classification}</h2>
          <div className="mf-peer-list">
            {peers.filter((peer) => peer.team_id !== row.team_id).slice(0, 14).map((peer) => (
              <Link key={peer.team_id} href={`/team/${peer.slug}`}>{peer.team}</Link>
            ))}
          </div>
        </section>

        <p className="table-note">
          Rankings generated {longDate(snapshotMeta.generated_at)} · Formula {snapshotMeta.formula_version} ·{' '}
          <Link href="/corrections">Report a correction</Link>
        </p>
        <SiteFooter />
      </main>
    </>
  );
}

function listingLabel(category: string) {
  switch (category) {
    case 'unresolved': return 'Score not verified';
    case 'scheduled': return 'Scheduled';
    case 'postponed': return 'Postponed';
    case 'canceled': return 'Canceled';
    case 'suspended': return 'Suspended';
    case 'no_contest': return 'No contest';
    case 'in_progress': return 'In progress';
    case 'exhibition': return 'Exhibition (not counted)';
    default: return 'Not counted';
  }
}
