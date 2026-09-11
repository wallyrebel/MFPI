import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { SiteFooter, SiteHeader } from '../../site-nav';
import { siteUrl } from '../../site';
import {
  COMPONENT_LABELS,
  classTeams,
  formatGameDate,
  getTeamBySlug,
  longDate,
  metadata as snapshotMeta,
  teamGames,
  teams,
  type Team,
} from '../../team-data';

type Params = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return teams.map((row) => ({ slug: row.slug }));
}

function groupLabel(row: Team) {
  return `Class ${row.classification}${row.region ? `, Region ${row.region}` : ''}`;
}

function movementWord(change: number) {
  if (change > 0) return `up ${change} spot${change === 1 ? '' : 's'}`;
  if (change < 0) return `down ${Math.abs(change)} spot${change === -1 ? '' : 's'}`;
  return 'unchanged';
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  const row = getTeamBySlug(slug);
  if (!row) return {};
  const title = `${row.team} Football — Rankings, Record & Schedule`;
  const description = `${row.team} is No. ${row.state_rank} in the ${snapshotMeta.season} Mississippi Football Power Index at ${row.record} (${groupLabel(row)}). Week ${snapshotMeta.week} rating, full schedule, scores and strength of schedule.`;
  return {
    title,
    description,
    alternates: { canonical: `/team/${row.slug}` },
    openGraph: { type: 'article', url: `${siteUrl}/team/${row.slug}`, title, description },
    twitter: { card: 'summary_large_image', title, description },
  };
}

export default async function TeamPage({ params }: Params) {
  const { slug } = await params;
  const row = getTeamBySlug(slug);
  if (!row) notFound();

  const games = teamGames(row);
  const peers = classTeams(row.classification);
  const overall = teams.findIndex((peer) => peer.team_id === row.team_id);
  const ahead = teams[overall - 1];
  const behind = teams[overall + 1];

  const wins = games.filter((game) => game.won).length;
  const losses = games.filter((game) => !game.won && !game.tie).length;
  const ranked = games.filter((game) => game.opponentRank !== null);
  const bestWin = ranked
    .filter((game) => game.won)
    .sort((a, b) => a.opponentRank! - b.opponentRank!)[0];
  const margin = games.length
    ? games.reduce((sum, game) => sum + (game.pointsFor - game.pointsAgainst), 0) / games.length
    : 0;

  const orderedComponents = Object.entries(row.components)
    .filter(([key]) => COMPONENT_LABELS[key])
    .sort((a, b) => b[1].weight - a[1].weight);

  const structuredData = {
    '@context': 'https://schema.org',
    '@type': 'SportsTeam',
    name: row.team,
    sport: 'American Football',
    url: `${siteUrl}/team/${row.slug}`,
    memberOf: { '@type': 'SportsOrganization', name: `MHSAA Class ${row.classification}` },
    description: `${row.team} is ranked No. ${row.state_rank} of ${teams.length} in the Mississippi Football Power Index with a ${row.record} record.`,
  };

  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, '\\u003c') }} />

        <nav className="mf-crumbs" aria-label="Breadcrumb">
          <Link href="/">Rankings</Link> <span>/</span> <Link href="/teams">Teams</Link> <span>/</span> <span>{row.team}</span>
        </nav>

        <section className="mf-team-hero">
          <div>
            <p className="eyebrow">{groupLabel(row)} · Week {snapshotMeta.week}, {snapshotMeta.season}</p>
            <h1>{row.team}</h1>
            <p className="hero-copy">
              {row.team} is <strong>No. {row.state_rank}</strong> of {teams.length} ranked teams in the Mississippi
              Football Power Index and <strong>No. {row.class_rank}</strong> of {peers.length} in Class{' '}
              {row.classification}, at {row.record} through {row.games_played} game
              {row.games_played === 1 ? '' : 's'}. Its rating is {row.mfpi.toFixed(1)}, {movementWord(row.state_rank_change)}{' '}
              from last week.
            </p>
            <p className="hero-copy">
              {row.team} averages {row.pf_per_game.toFixed(1)} points scored and {row.pa_per_game.toFixed(1)} allowed
              {games.length > 0 && <> ({margin >= 0 ? '+' : ''}{margin.toFixed(1)} per game)</>}.
              {bestWin
                ? <> Its best result is a {bestWin.pointsFor}–{bestWin.pointsAgainst} win over <Link href={`/team/${bestWin.opponentSlug}`}>{bestWin.opponent}</Link> (No. {bestWin.opponentRank}).</>
                : <> It has not yet beaten a ranked Mississippi opponent.</>}
              {' '}The schedule so far is {row.schedule_direction.toLowerCase()}, with {row.up_games} game
              {row.up_games === 1 ? '' : 's'} up in class, {row.same_class_games} against its own class and{' '}
              {row.down_games} down.
            </p>
          </div>
          <aside className="run-card">
            <span className="run-card-label">MFPI rating</span>
            <strong className="mf-big-score">{row.mfpi.toFixed(1)}</strong>
            <dl>
              <div><dt>Statewide</dt><dd>No. {row.state_rank}</dd></div>
              <div><dt>Class {row.classification}</dt><dd>No. {row.class_rank}</dd></div>
              <div><dt>Record</dt><dd>{row.record}</dd></div>
              <div><dt>Points/game</dt><dd>{row.pf_per_game.toFixed(1)}</dd></div>
              <div><dt>Allowed/game</dt><dd>{row.pa_per_game.toFixed(1)}</dd></div>
              <div><dt>Media rank</dt><dd>{row.maxpreps_state_rank ? `No. ${row.maxpreps_state_rank}` : '—'}</dd></div>
              <div><dt>Week change</dt><dd>{row.state_rank_change === 0 ? '—' : `${row.state_rank_change > 0 ? '▲' : '▼'} ${Math.abs(row.state_rank_change)}`}</dd></div>
            </dl>
          </aside>
        </section>

        <section className="rankings-panel">
          <div className="rankings-title-row">
            <div><p className="eyebrow">{snapshotMeta.season} season</p><h2>Schedule &amp; results</h2></div>
            <span className="secondary">{wins}–{losses} · {games.length} completed game{games.length === 1 ? '' : 's'}</span>
          </div>
          <div className="table-scroll">
            <div className="table-head mf-game-grid"><span>Date</span><span>Opponent</span><span>Site</span><span>Result</span><span>Score</span><span>Opp. class</span></div>
            {games.map((game, index) => (
              <div className="mf-game-grid mf-game-row" key={`${game.date}-${index}`}>
                <span className="tabular">{formatGameDate(game.date)}</span>
                <span className="mf-game-opp">
                  {game.opponentSlug
                    ? <Link href={`/team/${game.opponentSlug}`}>{game.opponent}</Link>
                    : <span>{game.opponent}</span>}
                  {game.opponentRank !== null && <small>No. {game.opponentRank}</small>}
                  {game.overtime && <small>OT</small>}
                  {game.forfeit && <small>Forfeit</small>}
                </span>
                <span className="secondary">{game.site}</span>
                <span className={game.tie ? 'movement flat' : game.won ? 'mf-win' : 'mf-loss'}>{game.tie ? 'T' : game.won ? 'W' : 'L'}</span>
                <span className="tabular">{game.pointsFor}–{game.pointsAgainst}</span>
                <span className="secondary">{game.opponentClass ?? 'Non-MHSAA'}</span>
              </div>
            ))}
            {games.length === 0 && (
              <p className="table-note">
                No completed games for {row.team} in the current snapshot yet. Its rating is carried from preseason
                inputs until results are published.
              </p>
            )}
          </div>
          <p className="table-note">
            Scores come from official MHSAA results with secondary verification. Week {snapshotMeta.week} coverage is{' '}
            {snapshotMeta.coverage_percentage.toFixed(1)}% ({snapshotMeta.verified_games} of {snapshotMeta.expected_games} expected games verified).
          </p>
        </section>

        <section className="method-card">
          <div>
            <p className="eyebrow">Why {row.team} rates {row.mfpi.toFixed(1)}</p>
            <h2>Rating breakdown</h2>
            <p className="method-copy">
              Each component becomes a statewide percentile, then carries its weight into the final score. The
              contribution column is how many of the {row.mfpi.toFixed(1)} points come from that component.
            </p>
          </div>
          <div className="component-grid mf-component-grid">
            {orderedComponents.map(([key, value]) => {
              const [label, note] = COMPONENT_LABELS[key];
              return (
                // Key on the public label: the raw keys name the upstream data source.
                <div className="component-card" key={label}>
                  <span>{label}</span>
                  <strong>{value.normalized.toFixed(1)}</strong>
                  <small>{(value.weight * 100).toFixed(0)}% weight · {value.contribution.toFixed(1)} pts</small>
                  <i><b style={{ width: `${Math.max(0, Math.min(100, value.normalized))}%` }} /></i>
                  <small className="mf-component-note">{note}</small>
                </div>
              );
            })}
          </div>
        </section>

        <section className="mf-neighbors">
          <h2>Nearby in the statewide rankings</h2>
          <div>
            {ahead && <Link href={`/team/${ahead.slug}`}><small>No. {ahead.state_rank} · ahead</small><strong>{ahead.team}</strong><span>{ahead.record} · MFPI {ahead.mfpi.toFixed(1)}</span></Link>}
            {behind && <Link href={`/team/${behind.slug}`}><small>No. {behind.state_rank} · behind</small><strong>{behind.team}</strong><span>{behind.record} · MFPI {behind.mfpi.toFixed(1)}</span></Link>}
          </div>
          <h2>Others in Class {row.classification}</h2>
          <div className="mf-peer-list">
            {peers.filter((peer) => peer.team_id !== row.team_id).slice(0, 14).map((peer) => (
              <Link key={peer.team_id} href={`/team/${peer.slug}`}>{peer.team}</Link>
            ))}
          </div>
        </section>

        <p className="table-note">Rankings generated {longDate(snapshotMeta.generated_at)} · Formula {snapshotMeta.formula_version}</p>
        <SiteFooter />
      </main>
    </>
  );
}
