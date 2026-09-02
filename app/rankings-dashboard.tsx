'use client';

import { useMemo, useState } from 'react';

export type ComponentValue = { raw: number | null; normalized: number; weight: number; contribution: number };
export type Ranking = {
  team_id: string;
  team: string;
  classification: string;
  region: string;
  record: string;
  state_rank: number;
  class_rank: number;
  mfpi: number;
  mfpi_unrounded: number;
  state_rank_change: number | null;
  class_rank_change: number | null;
  mfpi_change: number | null;
  pf_per_game: number;
  pa_per_game: number;
  media_state_rank: number | null;
  media_strength: number | null;
  up_games: number;
  same_class_games: number;
  down_games: number;
  class_schedule_delta: number;
  schedule_direction: string;
  components: Record<string, ComponentValue>;
  explanation: string;
};

export type Snapshot = {
  metadata: {
    season: number;
    week: number;
    generated_at: string;
    cutoff_at: string;
    formula_version: string;
    status: string;
    validation_status: string;
    coverage_percentage: number;
    expected_games?: number;
    verified_games?: number;
    missing_games?: number;
    data_sources: { name: string; retrieved_at?: string; configured?: boolean }[];
  };
  rankings: Ranking[];
};

const componentLabels: Record<string, string> = {
  performance: 'Opponent-adjusted performance',
  sos: 'Strength of schedule percentile',
  media_rank: 'Media rank',
  media_sos: 'Media strength of schedule',
  record: 'Record',
  offense: 'Offense',
  defense: 'Defense',
  recent: 'Recent form',
};

function movement(value: number | null) {
  if (value === null) return <span className="movement new">NEW</span>;
  if (value === 0) return <span className="movement flat">—</span>;
  return <span className={value > 0 ? 'movement up' : 'movement down'}>{value > 0 ? '▲' : '▼'} {Math.abs(value)}</span>;
}

function publicExplanation(row: Ranking) {
  if (row.state_rank_change !== null) {
    const direction = row.state_rank_change > 0 ? 'rose' : row.state_rank_change < 0 ? 'fell' : 'held';
    return `${row.team} ${direction} at No. ${row.state_rank} with an MFPI of ${row.mfpi.toFixed(1)}. Its opponent-adjusted performance percentile is ${row.components.performance.normalized.toFixed(1)}, its SOS percentile is ${row.components.sos.normalized.toFixed(1)}, and its Media Rank is ${row.media_state_rank ? `No. ${row.media_state_rank}` : 'unavailable'}.`;
  }

  const mediaContribution = row.components.media_rank.contribution + row.components.media_sos.contribution;
  return `${row.team} enters at No. ${row.state_rank} with an MFPI of ${row.mfpi.toFixed(1)}; opponent-adjusted performance contributes ${row.components.performance.contribution.toFixed(2)} points and Media Rank and Strength of Schedule contribute ${mediaContribution.toFixed(2)} points. The schedule has ${row.up_games} up, ${row.same_class_games} same-class, and ${row.down_games} down game(s).`;
}

export default function RankingsDashboard({ snapshot }: { snapshot: Snapshot }) {
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
      if (sort === 'mfpi') return b.mfpi_unrounded - a.mfpi_unrounded;
      if (sort === 'sos') return b.components.sos.normalized - a.components.sos.normalized;
      if (sort === 'media') return (a.media_state_rank ?? Number.MAX_SAFE_INTEGER) - (b.media_state_rank ?? Number.MAX_SAFE_INTEGER);
      if (sort === 'media-sos') return (b.media_strength ?? -Infinity) - (a.media_strength ?? -Infinity);
      return scope === 'Overall' ? a.state_rank - b.state_rank : a.class_rank - b.class_rank;
    });
  }, [scope, sort, snapshot.rankings]);

  const strongestSchedules = [...snapshot.rankings]
    .sort((a, b) => b.components.sos.normalized - a.components.sos.normalized)
    .slice(0, 3);
  const movers = snapshot.rankings.filter((row) => row.state_rank_change !== null);
  const biggestRiser = [...movers].sort((a, b) => (b.state_rank_change ?? 0) - (a.state_rank_change ?? 0))[0];
  const biggestFaller = [...movers].sort((a, b) => (a.state_rank_change ?? 0) - (b.state_rank_change ?? 0))[0];

  return (
    <main>
      <header className="site-header">
        <div className="header-inner">
          <a className="brand" href="#top" aria-label="MFPI home">
            <span className="brand-mark">M</span>
            <span><strong>Mississippi Football</strong><small>POWER INDEX</small></span>
          </a>
          <div className="run-status"><span />{snapshot.metadata.validation_status} · {snapshot.metadata.coverage_percentage.toFixed(0)}% coverage</div>
        </div>
      </header>

      <div id="top" className="page-shell">
        {isDemo && <div className="demo-banner"><strong>Demonstration rankings</strong><span>The live MHSAA team, schedule, and score feeds are connected. Official publication waits only for the 95% verified-results threshold.</span></div>}
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
            <h1>Every team.<br />One explainable number.</h1>
            <p className="hero-copy">Computer rankings built from scores, opponent-adjusted margin, schedule strength, and recent form, with Media Rank and Strength of Schedule contributing 20%.</p>
          </div>
          <aside className="run-card">
            <span className="run-card-label">Latest {isProvisional ? 'provisional' : 'validated'} run</span>
            <strong>{generated}</strong>
            <dl>
              <div><dt>Formula</dt><dd>{snapshot.metadata.formula_version}</dd></div>
              <div><dt>Cutoff</dt><dd>Wed · 1:00 PM CT</dd></div>
              <div><dt>Teams</dt><dd>{snapshot.rankings.length}</dd></div>
            </dl>
          </aside>
        </section>

        <section className="signal-grid" aria-label="Weekly signals">
          <article><span>Largest riser</span><strong>{biggestRiser?.team ?? 'Available in Week 2'}</strong><small>{biggestRiser ? `Up ${biggestRiser.state_rank_change} spots` : 'First snapshot establishes the baseline'}</small></article>
          <article><span>Largest faller</span><strong>{biggestFaller?.team ?? 'Available in Week 2'}</strong><small>{biggestFaller ? `Down ${Math.abs(biggestFaller.state_rank_change ?? 0)} spots` : 'Movement begins after another official run'}</small></article>
          <article className="schedule-card"><span>Strongest schedule</span><strong>{strongestSchedules[0]?.team}</strong><small>No. 1 SOS · {strongestSchedules[0]?.components.sos.normalized.toFixed(1)} percentile</small></article>
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
              <button key={label} className={scope === label ? 'active' : ''} onClick={() => { setScope(label); setSort('rank'); }}>{label}</button>
            ))}
          </nav>

          <div className="table-scroll">
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
                    <span className="team-cell"><strong>{row.team}</strong><small>{row.classification} · Region {row.region}</small></span>
                    <span className="tabular">{row.record}</span>
                    <strong className="mfpi-score">{row.mfpi.toFixed(1)}</strong>
                    <span className="tabular secondary">{row.mfpi_change === null ? 'NEW' : `${row.mfpi_change > 0 ? '+' : ''}${row.mfpi_change.toFixed(1)}`}</span>
                    <span className="tabular secondary">{row.components.sos.normalized.toFixed(1)}</span>
                    <span className="tabular secondary">{row.media_state_rank ? `#${row.media_state_rank}` : '—'}</span>
                    <span className="tabular secondary">{row.media_strength?.toFixed(1) ?? '—'}</span>
                    <span className="tabular secondary">{row.pf_per_game.toFixed(1)}</span>
                    <span className="tabular secondary">{row.pa_per_game.toFixed(1)}</span>
                    <span className="tabular secondary" title={row.schedule_direction}>{row.class_schedule_delta > 0 ? '+' : ''}{row.class_schedule_delta.toFixed(1)}</span>
                  </summary>
                  <div className="team-details">
                    <p>{publicExplanation(row)}</p>
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
          <p className="table-note">SOS is a statewide percentile: 100 means the strongest verified schedule in this week&apos;s field, not a perfect or absolute schedule grade. Select a team row to see every component and its exact MFPI contribution.</p>
        </section>

        <section className="method-card">
          <div><p className="eyebrow">How MFPI thinks</p><h2>Strong opponents matter.<br />Runaway scores don’t.</h2></div>
          <div className="method-copy"><p>A 70-point margin is compressed with a diminishing-return curve. A 4A team facing 7A opponents gets stronger schedule credit than one facing 1A opponents; the 7A-to-1A starting assumption fades as real results connect the state.</p><p>Media Rank and Strength of Schedule each contribute 10%. Rankings use full-precision scores, and class lists reuse the statewide calculation rather than recalculating a smaller pool.</p></div>
        </section>

        <footer><span>MFPI · Local weekly ranking desk</span><span>Formula {snapshot.metadata.formula_version} · No human voting</span></footer>
      </div>
    </main>
  );
}
