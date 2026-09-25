import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { SiteFooter, SiteHeader } from '../../../site-nav';
import { archive, findArchive, loadLatest, loadSnapshot } from '../../../archive-data';
import { getTeamById } from '../../../team-data';
import { centralDateTime, formatRatingChange, ratingChange } from '../../../lib/format';

type Params = { params: Promise<{ season: string; week: string }> };

export function generateStaticParams() {
  return archive.map((entry) => ({ season: String(entry.season), week: entry.slug }));
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { season, week } = await params;
  const entry = findArchive(Number(season), week);
  if (!entry) return {};
  return {
    title: `${season} Week ${entry.week} Mississippi Football Rankings`,
    description: `The Mississippi Football Power Index rankings for ${season} Week ${entry.week}, as published, for all MHSAA Class 1A–7A teams.`,
    alternates: { canonical: `/archive/${season}/${week}` },
  };
}

export default async function ArchiveWeek({ params }: Params) {
  const { season, week } = await params;
  const entry = findArchive(Number(season), week);
  if (!entry) notFound();
  const [snapshot, original] = await Promise.all([loadLatest(entry), loadSnapshot(entry.original)]);
  const meta = snapshot.metadata;
  const revisions = await Promise.all(entry.revisions.map(async (path) => ({ path, meta: (await loadSnapshot(path)).metadata })));
  const rows = [...snapshot.rankings].sort((a, b) => a.state_rank - b.state_rank);
  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <article className="mf-doc mf-archive-doc">
          <p className="eyebrow">Archive · {meta.status === 'CORRECTED' ? 'Corrected publication' : 'Original publication'}</p>
          <h1>{season} Week {entry.week} rankings</h1>
          <p className="mf-doc-meta">
            Cutoff {centralDateTime(meta.cutoff_at)} · Formula {meta.formula_version} · {rows.length} teams
            {meta.verified_games !== undefined && ` · ${meta.verified_games} of ${meta.expected_games} games verified`}
          </p>
          <p>
            Originally published {centralDateTime(original.metadata.generated_at)}.
            {revisions.length > 0
              ? <> Reissued as an audited correction{revisions.length > 1 ? 's' : ''}: {revisions.map((revision) => `${revision.path.match(/revision-\d+/)?.[0]} on ${centralDateTime(revision.meta.generated_at)}`).join('; ')}. The latest revision is shown; the original is preserved in the data archive.</>
              : ' This week has not been corrected.'}
            {' '}Records here are records at this week&apos;s cutoff, not current records. See the <Link href="/">current rankings</Link>.
          </p>
        </article>
        <div className="table-scroll mf-archive-table" role="region" aria-label={`Week ${entry.week} rankings`} tabIndex={0}>
          <table className="mf-weights-table">
            <thead>
              <tr><th scope="col">Rank</th><th scope="col">Team</th><th scope="col">Class</th><th scope="col">Record at cutoff</th><th scope="col">MFPI</th><th scope="col">Rating change</th><th scope="col">Rank move</th></tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const current = getTeamById(row.team_id);
                const move = row.state_rank_change;
                return (
                  <tr key={row.team_id}>
                    <td className="tabular">{row.state_rank}</td>
                    <td>{current ? <Link href={`/team/${current.slug}`}>{current.team}</Link> : row.team}</td>
                    <td>{row.classification}</td>
                    <td className="tabular">{row.games_played === 0 ? '—' : row.record}</td>
                    <td className="tabular">{row.mfpi.toFixed(1)}</td>
                    <td className="tabular">{formatRatingChange(ratingChange(row.mfpi, row.previous_mfpi ?? null))}</td>
                    <td className="tabular">{move === null || move === undefined ? 'NEW' : move === 0 ? '—' : `${move > 0 ? '▲' : '▼'} ${Math.abs(move)}`}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <SiteFooter />
      </main>
    </>
  );
}
