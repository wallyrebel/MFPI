import type { Metadata } from 'next';
import Link from 'next/link';
import { SiteFooter, SiteHeader } from '../site-nav';
import { archive, loadLatest, loadSnapshot } from '../archive-data';
import { centralDateTime } from '../lib/format';

export const metadata: Metadata = {
  title: 'Weekly Rankings Archive',
  description: 'Every published week of the Mississippi Football Power Index, preserved as released, with audited corrections noted.',
  alternates: { canonical: '/archive' },
};

export default async function ArchiveIndex() {
  const rows = await Promise.all(archive.map(async (entry) => {
    const [original, latest] = await Promise.all([loadSnapshot(entry.original), loadLatest(entry)]);
    return { entry, original: original.metadata, latest: latest.metadata, leader: latest.rankings.find((row) => row.state_rank === 1) };
  }));
  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <article className="mf-doc">
          <p className="eyebrow">Archive</p>
          <h1>Weekly rankings archive</h1>
          <p>
            Each weekly publication is immutable. When a published week needs a correction, MFPI issues an audited
            revision and keeps the original; nothing is edited silently. Movement on each archived week is measured
            against the latest audited publication of the week before it.
          </p>
          <div className="table-scroll" role="region" aria-label="Archived weeks" tabIndex={0}>
            <table className="mf-weights-table">
              <thead><tr><th scope="col">Week</th><th scope="col">Published</th><th scope="col">Formula</th><th scope="col">No. 1</th><th scope="col">Corrections</th></tr></thead>
              <tbody>
                {rows.map(({ entry, original, latest, leader }) => (
                  <tr key={`${entry.season}-${entry.slug}`}>
                    <td><Link href={`/archive/${entry.season}/${entry.slug}`}>{entry.season} Week {entry.week}</Link></td>
                    <td>{centralDateTime(original.generated_at)}</td>
                    <td>{latest.formula_version}</td>
                    <td>{leader?.team ?? '—'}</td>
                    <td>{entry.revisions.length ? `${entry.revisions.length} audited revision${entry.revisions.length > 1 ? 's' : ''}` : 'None'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
        <SiteFooter />
      </main>
    </>
  );
}
