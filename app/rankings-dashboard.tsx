'use client';

import Link from 'next/link';
import { useMemo, useState, type ReactNode } from 'react';
import { formatRatingChange, rankSentence, ratingSentence, stat } from './lib/format';
import { SiteFooter, SiteHeader } from './site-nav';

export type ComponentValue = { raw: number | null; normalized: number; weight: number; contribution: number };
export type Ranking = {
  team_id: string;
  slug: string;
  team: string;
  classification: string;
  region: string;
  record: string;
  games_played: number;
  data_status: string;
  state_rank: number;
  class_rank: number;
  mfpi: number;
  mfpi_unrounded: number;
  previous_state_rank: number | null;
  state_rank_change: number | null;
  class_rank_change: number | null;
  /** Displayed rating minus displayed previous rating (lib/format ratingChange). */
  rating_change: number | null;
  /** Actual points per played game; null when no eligible games. */
  pf_per_game: number | null;
  pa_per_game: number | null;
  media_state_rank: number | null;
  media_strength: number | null;
  up_games: number;
  same_class_games: number;
  down_games: number;
  class_schedule_delta: number;
  schedule_direction: string;
  components: Record<string, ComponentValue>;
  bye_adjustment?: { previous_weight: number; previous_mfpi: number; recalculated_mfpi: number; adjustment: number } | null;
};

export type Snapshot = {
  metadata: {
    season: number;
    week: number;
    generated_at: string;
    cutoff_at: string;
    cutoff_label: string;
    formula_version: string;
    status: string;
    coverage_percentage: number;
    expected_games?: number;
    verified_games?: number;
    missing_games?: number;
    data_sources: { name: string; retrieved_at?: string }[];
  };
  rankings: Ranking[];
};

const componentLabels: Record<string, string> = {
  performance: 'Opponent-adjusted performance',
  sos: 'Strength of schedule percentile',
  media_rank: 'Media rank (MaxPreps)',
  media_sos: 'Media strength of schedule',
  record: 'Record',
  offense: 'Offense',
  defense: 'Defense',
  recent: 'Recent form',
};

function movement(value: number | null) {
  if (value === null) return <span className="movement new">NEW</span>;
  if (value === 0) return <span className="movement flat" aria-label="No change">—</span>;
  return <span className={value > 0 ? 'movement up' : 'movement down'} aria-label={`${value > 0 ? 'Up' : 'Down'} ${Math.abs(value)}`}>{value > 0 ? '▲' : '▼'} {Math.abs(value)}</span>;
}

function publicExplanation(row: Ranking) {
  const parts = [rankSentence(row.state_rank, row.previous_state_rank), ratingSentence(row.mfpi, row.rating_change)];
  if (row.data_status === 'unavailable') {
    parts.push('No verified results are linked to this team for this cutoff, so the rating is provisional and rests on class, media and neutral inputs.');
  } else {
    parts.push(`Opponent-adjusted performance percentile ${row.components.performance.normalized.toFixed(1)}; SOS percentile ${row.components.sos.normalized.toFixed(1)}; media rank ${row.media_state_rank ? `No. ${row.media_state_rank}` : 'unavailable'}.`);
  }
  return parts.join(' ');
}

export default function RankingsDashboard({ snapshot, ageDays, adTop, adBottom }: { snapshot: Snapshot; ageDays: number; adTop?: ReactNode; adBottom?: ReactNode }) {
  const [scope, setScope] = useState('Overall');
  const [sort, setSort] = useState('rank');
  const isDemo = snapshot.metadata.data_sources.some((source) => source.name.includes('demo'));
  const isProvisional = snapshot.metadata.status === 'PROVISIONAL';
  const generated = new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago', timeZoneName: 'short',
  }).format(new Date(snapshot.metadata.generated_at));

  const displayed = useMemo(() => {
    const rows = scope === 'Overall' ? snapshot.rankings : snapshot.rankings.filter((row) => row.classification === scope);
    return [...rows].sort((a, b) => {
      if (sort === 'team') return a.team.localeCompare(b.team);
      if (sort === 'mfpi') return b.mfpi_unrounded - a.mfpi_unrounded || a.state_rank - b.state_rank;
      if (sort === 'sos') return b.components.sos.normalized - a.components.sos.normalized || a.state_rank - b.state_rank;
      if (sort === 'media') return (a.media_state_rank ?? Number.MAX_SAFE_INTEGER) - (b.media_state_rank ?? Number.MAX_SAFE_INTEGER) || a.state_rank - b.state_rank;
      if (sort === 'media-sos') return (b.media_strength ?? -Infinity) - (a.media_strength ?? -Infinity) || a.state_rank - b.state_rank;
      return scope === 'Overall' ? a.state_rank - b.state_rank : a.class_rank - b.class_rank;
    });
  }, [scope, sort, snapshot.rankings]);

  const strongestSchedule = [...snapshot.rankings]
    .sort((a, b) => b.components.sos.normalized - a.components.sos.normalized)[0];
  const movers = snapshot.rankings.filter((row) => row.state_rank_change !== null);
  const biggestRiser = [...movers].sort((a, b) => (b.state_rank_change ?? 0) - (a.state_rank_change ?? 0))[0];
  const biggestFaller = [...movers].sort((a, b) => (a.state_rank_change ?? 0) - (b.state_rank_change ?? 0))[0];

  return (
    <main>
      <aside className="sponsor-strip" aria-label="Sponsored advertisement">
        <div className="sponsor-inner">
          <p className="sponsor-label">Sponsored By</p>
          <a
            className="sponsor-ad"
            href="https://langstonlott.com/attorneys/casey-lott/"
            rel="sponsored"
            aria-label="Visit Casey Lott at Langston and Lott"
          >
            {/* The vinext client shim currently fails to hydrate next/image here. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/casey-lott-sponsor.png"
              alt="Injury Law, Casey Lott, 662-888-8888"
              width="600"
              height="245"
            />
          </a>
        </div>
      </aside>

      <SiteHeader />

      <div id="top" className="page-shell">
        {isDemo && <div className="demo-banner"><strong>Demonstration rankings</strong><span>The live MHSAA team, schedule, and score feeds are connected. Official publication waits only for the 95% verified-results threshold.</span></div>}
        {ageDays > 8 && (
          <div className="provisional-banner" role="status">
            <strong>Rankings not updated this week</strong>
            <span>These are the Week {snapshot.metadata.week} rankings from {generated}, {ageDays} days ago. The next update is published only after its data passes validation.</span>
          </div>
        )}
        {isProvisional && (
          <div className="provisional-banner">
            <strong>Live provisional rankings</strong>
            <span>
              All {snapshot.rankings.length} MHSAA teams are ranked from currently verified results and the latest media update. {snapshot.metadata.verified_games ?? 'Some'} of {snapshot.metadata.expected_games ?? 'the expected'} games are final; rankings refresh as remaining scores are confirmed.
            </span>
          </div>
        )}

        <section className="hero">
          <div>
            <p className="eyebrow">{snapshot.metadata.season} · Week {snapshot.metadata.week}</p>
            <h1>Mississippi Football<br />Rankings</h1>
            <p className="hero-copy">The Mississippi Football Power Index is an explainable weekly ranking of every MHSAA Class 1A–7A team, built from verified scores, opponent-adjusted margin, schedule strength and recent form, with MaxPreps&apos; statewide media rank and strength of schedule contributing 20%. Rankings update every Tuesday after the 11 a.m. Central cutoff.</p>
            <p className="hero-links"><Link href="/analysis">Weekly analysis</Link> · <Link href="/methodology">How it works</Link> · <Link href="/archive">Past weeks</Link></p>
          </div>
          <aside className="run-card">
            <span className="run-card-label">Latest {isProvisional ? 'provisional' : 'validated'} run</span>
            <strong>{generated}</strong>
            <dl>
              <div><dt>Formula</dt><dd>{snapshot.metadata.formula_version}</dd></div>
              <div><dt>Cutoff</dt><dd>{snapshot.metadata.cutoff_label}</dd></div>
              <div><dt>Coverage</dt><dd>{snapshot.metadata.verified_games ?? '—'} of {snapshot.metadata.expected_games ?? '—'} games</dd></div>
              <div><dt>Teams</dt><dd>{snapshot.rankings.length}</dd></div>
            </dl>
          </aside>
        </section>

        {adTop}

        <section className="signal-grid" aria-label="Weekly signals">
          <article><span>Largest riser</span><strong>{biggestRiser?.team ?? 'Available in Week 2'}</strong><small>{biggestRiser ? `Up ${biggestRiser.state_rank_change} spots` : 'First snapshot establishes the baseline'}</small></article>
          <article><span>Largest faller</span><strong>{biggestFaller?.team ?? 'Available in Week 2'}</strong><small>{biggestFaller ? `Down ${Math.abs(biggestFaller.state_rank_change ?? 0)} spots` : 'Movement begins after another official run'}</small></article>
          <article className="schedule-card"><span>Strongest schedule</span><strong>{strongestSchedule?.team}</strong></article>
        </section>

        <section className="rankings-panel" aria-labelledby="rankings-title">
          <div className="rankings-title-row">
            <div><p className="eyebrow">Computer rankings</p><h2 id="rankings-title">{scope === 'Overall' ? 'Statewide' : `Class ${scope}`}</h2></div>
            <label className="sort-control">Sort
              <select value={sort} onChange={(event) => setSort(event.target.value)}>
                <option value="rank">State rank</option><option value="mfpi">MFPI score</option><option value="sos">SOS percentile</option><option value="media">Media rank</option><option value="media-sos">Media strength of schedule</option><option value="team">Team name</option>
              </select>
            </label>
          </div>

          <nav className="class-tabs" aria-label="Classification">
            {['Overall', '7A', '6A', '5A', '4A', '3A', '2A', '1A'].map((label) => (
              <button key={label} type="button" aria-pressed={scope === label} className={scope === label ? 'active' : ''} onClick={() => { setScope(label); setSort('rank'); }}>{label}</button>
            ))}
          </nav>

          <div className="table-scroll" role="region" aria-label="Rankings table" tabIndex={0}>
            <div className="table-head ranking-grid">
              <span>Rank</span><span>Move</span><span>Team</span><span>Record</span><span>MFPI</span><span>Δ</span><span>SOS pct.</span><span>Media #</span><span>Media SOS</span><span>PF/G</span><span>PA/G</span><span>Class path</span>
            </div>
            {displayed.map((row) => {
              const rowMovement = scope === 'Overall' ? row.state_rank_change : row.class_rank_change;
              return (
                <details className="ranking-entry" key={row.team_id}>
                  <summary className="ranking-grid">
                    <strong className="rank-number">{scope === 'Overall' ? row.state_rank : row.class_rank}</strong>
                    <span>{movement(rowMovement)}</span>
                    <span className="team-cell"><strong><Link href={`/team/${row.slug}`}>{row.team}</Link></strong><small>{row.classification} · Region {row.region}{row.data_status === 'unavailable' && <> · <em className="mf-provisional-inline">results unavailable</em></>}</small></span>
                    <span className="tabular">{row.data_status === 'unavailable' ? '—' : row.record}</span>
                    <strong className="mfpi-score">{row.mfpi.toFixed(1)}</strong>
                    <span className="tabular secondary">{formatRatingChange(row.rating_change)}</span>
                    <span className="tabular secondary">{row.components.sos.normalized.toFixed(1)}</span>
                    <span className="tabular secondary">{row.media_state_rank ? `#${row.media_state_rank}` : '—'}</span>
                    <span className="tabular secondary">{row.media_strength?.toFixed(1) ?? '—'}</span>
                    <span className="tabular secondary">{stat(row.pf_per_game)}</span>
                    <span className="tabular secondary">{stat(row.pa_per_game)}</span>
                    <span className="tabular secondary" title={row.schedule_direction}>{row.class_schedule_delta > 0 ? '+' : ''}{row.class_schedule_delta.toFixed(1)}</span>
                  </summary>
                  <div className="team-details">
                    <p>{publicExplanation(row)}</p>
                    {row.bye_adjustment && (
                      <p className="schedule-detail"><strong>Bye-week protection:</strong> 90% of last week&apos;s {row.bye_adjustment.previous_mfpi.toFixed(2)} + 10% of this week&apos;s recalculated {row.bye_adjustment.recalculated_mfpi.toFixed(2)} = {row.mfpi.toFixed(1)} MFPI. The components below total the recalculated score; the bye adjustment is {row.bye_adjustment.adjustment >= 0 ? '+' : ''}{row.bye_adjustment.adjustment.toFixed(2)} points.</p>
                    )}
                    <p className="schedule-detail"><strong>{row.schedule_direction}:</strong> {row.up_games} up · {row.same_class_games} same · {row.down_games} down</p>
                    <div className="component-grid">
                      {Object.entries(row.components).map(([name, value]) => (
                        <div key={name} className="component-card">
                          <span>{componentLabels[name]}</span><strong>{value.normalized.toFixed(1)}</strong>
                          <small>{(value.weight * 100).toFixed(0)}% weight · +{value.contribution.toFixed(2)}</small>
                          <i><b style={{ width: `${Math.max(2, value.normalized)}%` }} /></i>
                        </div>
                      ))}
                    </div>
                  </div>
                </details>
              );
            })}
          </div>
          <p className="table-note">SOS is a statewide percentile: 100 means the strongest verified schedule in this week&apos;s field, not a perfect or absolute schedule grade. Δ is the change in the displayed rating since last week. PF/G and PA/G are actual points per played game; — means no verified games. Select a team row to see its component contributions and any bye-week adjustment.</p>
        </section>

        {adBottom}

        <section className="method-card">
          <div><p className="eyebrow">How MFPI thinks</p><h2>Strong opponents matter.<br />Runaway scores don’t.</h2></div>
          <div className="method-copy"><p>A 70-point margin is compressed with a diminishing-return curve. A 4A team facing 7A opponents gets stronger schedule credit than one facing 1A opponents; the 7A-to-1A starting assumption fades as real results connect the state.</p><p>MaxPreps&apos; statewide media rank and strength of schedule each contribute 10%. On a confirmed bye, MFPI retains 90% of the previous week&apos;s score and uses 10% of the recalculated score. Other teams can still pass an idle team. Rankings use full-precision scores, and class lists reuse the statewide calculation.</p></div>
        </section>

        <SiteFooter />
      </div>
    </main>
  );
}
