import type { Metadata } from 'next';
import Link from 'next/link';
import { SiteFooter, SiteHeader } from '../site-nav';
import { CLASSES, classTeams, longDate, metadata as snapshotMeta, teams } from '../team-data';

export const metadata: Metadata = {
  title: 'All Mississippi Football Teams',
  description: 'Every ranked Mississippi high school football team by MHSAA classification, with record and MFPI rating. Links to each team page.',
  alternates: { canonical: '/teams' },
};

export default function TeamsIndexPage() {
  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <article className="mf-doc">
          <p className="eyebrow">Team directory</p>
          <h1>All ranked teams</h1>
          <p className="mf-doc-meta">
            {teams.length} teams · Week {snapshotMeta.week}, {snapshotMeta.season} · updated {longDate(snapshotMeta.generated_at)}
          </p>
          <p>
            Every team MFPI currently rates, grouped by MHSAA classification. Each team page carries its full schedule
            and scores, a breakdown of how its rating is built, and how it moved this week.
          </p>
        </article>

        {CLASSES.map((group) => {
          const rows = classTeams(group);
          if (rows.length === 0) return null;
          return (
            <section className="mf-directory" key={group} id={group}>
              <h2>Class {group} <small>{rows.length} teams</small></h2>
              <div>
                {rows.map((row) => (
                  <Link key={row.team_id} href={`/team/${row.slug}`}>
                    <span className="mf-dir-rank tabular">{row.class_rank}</span>
                    <span className="mf-dir-name">{row.team}</span>
                    <span className="mf-dir-meta tabular">{row.record} · {row.mfpi.toFixed(1)}</span>
                  </Link>
                ))}
              </div>
            </section>
          );
        })}

        <SiteFooter />
      </main>
    </>
  );
}
