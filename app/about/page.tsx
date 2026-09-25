import type { Metadata } from 'next';
import Link from 'next/link';
import { SiteFooter, SiteHeader } from '../site-nav';
import { editorEmail, publisher } from '../site';
import { longDate, metadata as snapshotMeta, teams } from '../team-data';

export const metadata: Metadata = {
  title: 'About the Mississippi Football Power Index',
  description: 'Who publishes MFPI, what it calculates, where its data comes from, how often it updates, and how corrections and review work.',
  alternates: { canonical: '/about' },
};

export default function AboutPage() {
  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <article className="mf-doc">
          <p className="eyebrow">About</p>
          <h1>About MFPI</h1>
          <p className="mf-doc-meta">
            Week {snapshotMeta.week}, {snapshotMeta.season} · updated {longDate(snapshotMeta.generated_at)}
          </p>

          <p>
            The Mississippi Football Power Index is an independent computer rating of high school football teams in
            Mississippi. It currently rates {teams.length} teams across MHSAA Classes 1A through 7A.
          </p>

          <h2>Who publishes it</h2>
          <p>
            MFPI is an independent Mississippi sports analytics project{publisher.operatorName ? <>, operated by {publisher.operatorName}</> : null}.
            The site&apos;s editor maintains the rankings, reviews analysis before publication and handles corrections;
            reach the editor at <a href={`mailto:${editorEmail}`}>{editorEmail}</a>. MFPI is free to read, with no
            paywall or account, and is supported by advertising and direct sponsors. Sponsorship never influences how a
            team is rated.
          </p>
          <p>
            MFPI is not affiliated with, sponsored by or endorsed by the Mississippi High School Activities Association
            (MHSAA), MaxPreps, Google, or any school or school district.
          </p>

          <h2>What MFPI calculates</h2>
          <p>
            A win-loss record does not tell you much on its own. A 4–0 team that has played four winless opponents and
            a 3–1 team that has played the toughest schedule in the state are not the same team. MFPI puts every program
            on one scale by asking two questions at once: whom did you play, and how did you do against them? MFPI
            itself calculates the opponent-adjusted team ratings, strength of schedule, every component percentile, the
            final 1–100 rating, statewide and class ranks, and the week-to-week comparisons. It is a rating of results
            so far, not a poll, a prediction or a betting line, and it has no official standing with the MHSAA.
          </p>

          <h2>Where the underlying facts come from</h2>
          <ul>
            <li><strong>Teams, classes and regions:</strong> the official{' '}
              <a href="https://www.misshsaa.com/2024/11/19/2025-27-football-regions/" rel="noopener">MHSAA 2025–27 football classifications</a>.</li>
            <li><strong>Schedules and scores:</strong> the official <a href="https://scores.misshsaa.com/" rel="noopener">MHSAA score center</a>.</li>
            <li><strong>Media rank and media strength of schedule (20% of the rating):</strong> the{' '}
              <a href="https://www.maxpreps.com/ms/football/rankings/1/" rel="noopener">MaxPreps Mississippi football rankings</a>.</li>
            <li><strong>Filling gaps:</strong> when the MHSAA score center has no final for a game that should be over,
              MaxPreps team schedules are checked, and a result is accepted only when both teams and the date agree.
              MaxPreps ratings are also used as a starting estimate for out-of-state opponents.</li>
          </ul>
          <p>
            Each team page lists every counted game, score, site and opponent, so the underlying results can be checked.
            How conflicts and missing data are handled is described on the{' '}
            <Link href="/corrections">corrections and standards page</Link>.
          </p>

          <h2>How often it updates</h2>
          <p>
            Ratings are recalculated once a week in season, after a Tuesday 11:00 a.m. Central cutoff. The weekly run is
            automated and can start a little after the cutoff. A run is published only after its data passes validation;
            if it fails, the previous week stays up and the page shows its real date. When fewer than 95% of the games
            due by the cutoff have verified scores, the rankings are published as <strong>provisional</strong> and say so.
            A team with no verified results has its rating marked provisional on its own page.
          </p>

          <h2>People and automation</h2>
          <p>
            Data collection, matching, calculation and validation are automated. Weekly Analysis articles are drafted
            automatically from the published data and appear on the site only after a named editor has reviewed them.
            Source conflicts, team-identity questions and corrections are decided by a person.
          </p>

          <p>
            The full calculation is documented on the <Link href="/methodology">methodology page</Link>. Questions and
            corrections: <Link href="/contact">contact</Link>.
          </p>
        </article>
        <SiteFooter />
      </main>
    </>
  );
}
