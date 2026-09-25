import type { Metadata } from 'next';
import Link from 'next/link';
import { SiteFooter, SiteHeader } from '../site-nav';
import { editorEmail } from '../site';
import { archive, loadSnapshot } from '../archive-data';
import { calendarDate, centralDateTime } from '../lib/format';
import { metadata as snapshotMeta, teamStatus, teams } from '../team-data';

export const metadata: Metadata = {
  title: 'Corrections and Editorial Standards',
  description: 'How MFPI handles score corrections, source conflicts and missing data, what is automated and what a person reviews, and the log of audited corrections.',
  alternates: { canonical: '/corrections' },
};

function doubleBooked() {
  const found: { team: string; slug: string; day: string }[] = [];
  for (const team of teams) {
    const counts = new Map<string, number>();
    for (const game of team.game_results) {
      const day = calendarDate(game.date, game.calendar_date);
      counts.set(day, (counts.get(day) ?? 0) + 1);
    }
    for (const [day, count] of counts) if (count > 1) found.push({ team: team.team, slug: team.slug, day });
  }
  return found;
}

export default async function CorrectionsPage() {
  const log = (await Promise.all(archive.flatMap((entry) => entry.revisions.map(async (path) => {
    const [revision, original] = await Promise.all([loadSnapshot(path), loadSnapshot(entry.original)]);
    return { entry, path, revised: revision.metadata, original: original.metadata };
  })))).sort((a, b) => b.revised.generated_at.localeCompare(a.revised.generated_at));
  const unavailable = teams.filter((team) => teamStatus(team) === 'unavailable');
  const conflicts = doubleBooked();

  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <article className="mf-doc">
          <p className="eyebrow">Standards</p>
          <h1>Corrections and editorial standards</h1>

          <h2>Report an error</h2>
          <p>
            Email <a href={`mailto:${editorEmail}`}>{editorEmail}</a> with both team names, the date, the final score
            and a source link if you have one (an official result, a school post, or a news report). Corrections are
            handled by the site&apos;s editor and are checked against official results before they are applied.
          </p>

          <h2>How corrections are published</h2>
          <p>
            Published weeks are never edited in place. A confirmed correction to an already-published week is issued as a
            numbered, audited revision that records when it was made; the original stays in the{' '}
            <Link href="/archive">archive</Link>. A correction that arrives later simply flows into the next weekly run.
            Correcting a score can legitimately change rankings; changing the formula requires a new formula version and
            is never applied to past weeks.
          </p>

          <h2>What is automated and what a person does</h2>
          <ul>
            <li><strong>Automated:</strong> fetching schedules and scores, matching teams, calculating ratings, and a
              validation audit that blocks publication when data is inconsistent (for example a missing team, a score
              that differs between two teams&apos; pages, or a record that disagrees with its games).</li>
            <li><strong>Automated, then reviewed:</strong> Weekly Analysis articles are drafted from the data and are
              published only after a named editor reviews them. The reviewer&apos;s name is shown on each article.</li>
            <li><strong>By a person:</strong> resolving source conflicts, confirming team identities that a name alone
              cannot settle, and deciding corrections.</li>
          </ul>

          <h2>Missing data and conflicts</h2>
          <p>
            A missing score is shown as unavailable — never as 0–0 and never as a loss. Postponed and cancelled games do
            not count. When the official MHSAA score center lacks a final, MFPI checks MaxPreps team schedules and
            accepts a result only when both teams and the date agree; conflicting reports are held back. A team whose
            results are not yet linked is labelled &ldquo;results unavailable&rdquo; and its rating is marked provisional.
          </p>

          <h2>Known data issues in the current rankings</h2>
          <p className="mf-doc-meta">Week {snapshotMeta.week}, generated {centralDateTime(snapshotMeta.generated_at)}</p>
          <ul>
            <li>
              {snapshotMeta.verified_games} of {snapshotMeta.expected_games} game listings due by the cutoff had verified
              scores; the remaining {snapshotMeta.missing_games ?? 0} are treated as unavailable.
            </li>
            {unavailable.map((team) => (
              <li key={team.team_id}>
                <Link href={`/team/${team.slug}`}>{team.team}</Link>: no verified results linked for this cutoff; rating is
                provisional. Under review.
              </li>
            ))}
            {conflicts.map((item) => (
              <li key={`${item.slug}-${item.day}`}>
                <Link href={`/team/${item.slug}`}>{item.team}</Link> is credited with two games on {item.day}; one listing
                may belong to a same-named school. Under review; it affects this team and its opponents.
              </li>
            ))}
          </ul>

          <h2>Correction log</h2>
          {log.length === 0 ? <p>No published week has been corrected.</p> : (
            <ul>
              {log.map(({ entry, path, revised, original }) => (
                <li key={path}>
                  <Link href={`/archive/${entry.season}/${entry.slug}`}>{entry.season} Week {entry.week}</Link>:{' '}
                  {path.match(/revision-\d+/)?.[0]} issued {centralDateTime(revised.generated_at)} (original published{' '}
                  {centralDateTime(original.generated_at)}; formula {original.formula_version}
                  {original.formula_version !== revised.formula_version ? ` → ${revised.formula_version}` : ''}).
                </li>
              ))}
            </ul>
          )}
        </article>
        <SiteFooter />
      </main>
    </>
  );
}
