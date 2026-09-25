import type { Metadata } from 'next';
import Link from 'next/link';
import { SiteFooter, SiteHeader } from '../site-nav';
import { publishedArticles } from '../lib/articles';
import { archive } from '../archive-data';
import { centralDateTime } from '../lib/format';

export const metadata: Metadata = {
  title: 'Weekly Analysis',
  description: 'Reviewed weekly analysis of the Mississippi Football Power Index: what moved the rankings, risers and fallers, and how the rankings have performed.',
  alternates: { canonical: '/analysis' },
};

export default function AnalysisIndex() {
  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <article className="mf-doc">
          <p className="eyebrow">Weekly Analysis</p>
          <h1>Weekly Analysis</h1>
          <p>
            Each week MFPI&apos;s published rankings are turned into short, data-grounded analysis: what moved at the top,
            which teams rose and fell and why, and — once enough games have been played — how the rankings published
            before kickoff held up against the results that followed. Every number comes from verified scores and
            published snapshots. Articles are drafted from the data and published only after a named editor reviews them.
          </p>

          <h2>Latest analysis</h2>
          {publishedArticles.length === 0 ? (
            <p>
              No analysis has been published yet this season. Reviewed articles will appear here; the{' '}
              <Link href="/">current rankings</Link> and the <Link href="/archive">weekly archive</Link> are always available.
            </p>
          ) : (
            <ul className="mf-article-list">
              {publishedArticles.map((article) => (
                <li key={article.slug}>
                  <Link href={`/analysis/${article.slug}`}><strong>{article.title}</strong></Link>
                  <span>{article.dek}</span>
                  <small>Published {centralDateTime(article.published_at!, false)} · Reviewed by {article.reviewed_by}</small>
                </li>
              ))}
            </ul>
          )}

          <h2>Weekly rankings archive</h2>
          <p>Every published week is preserved as it was released, including audited corrections.</p>
          <ul>
            {archive.map((entry) => (
              <li key={`${entry.season}-${entry.slug}`}>
                <Link href={`/archive/${entry.season}/${entry.slug}`}>{entry.season} Week {entry.week}</Link>
                {entry.revisions.length > 0 && ` (corrected ${entry.revisions.length === 1 ? 'once' : `${entry.revisions.length} times`})`}
              </li>
            ))}
          </ul>
        </article>
        <SiteFooter />
      </main>
    </>
  );
}
