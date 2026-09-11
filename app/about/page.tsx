import type { Metadata } from 'next';
import Link from 'next/link';
import { SiteFooter, SiteHeader } from '../site-nav';
import { longDate, metadata as snapshotMeta, teams } from '../team-data';

export const metadata: Metadata = {
  title: 'About the Mississippi Football Power Index',
  description: 'Who publishes MFPI, what the rating is, where the scores come from, and how often it updates.',
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

          <h2>What MFPI is</h2>
          <p>
            A win-loss record does not tell you much on its own. A 4–0 team that has played four winless opponents and
            a 3–1 team that has played the toughest schedule in the state are not the same team, and the standings
            cannot tell them apart. MFPI exists to put every program on one scale by asking two questions at once: whom
            did you play, and how did you do against them?
          </p>
          <p>
            The answer is a single number from roughly 1 to 100. It is a rating, not a prediction or a poll, and it
            carries no official standing with the MHSAA. It is one more piece of information for coaches, players,
            parents and fans who follow Mississippi high school football.
          </p>

          <h2>What MFPI is not</h2>
          <ul>
            <li>It is not an official MHSAA product and carries no playoff seeding weight.</li>
            <li>It is not a human poll. No votes, no ballots, no preseason expectations baked in.</li>
            <li>It is not a betting product, and it does not publish point spreads or projections.</li>
          </ul>

          <h2>Where the scores come from</h2>
          <p>
            Team lists and classifications come from official MHSAA sources. Scores come from the official MHSAA score
            center with secondary verification against published media results, and every run reports its own coverage:
            this week&rsquo;s snapshot verified {snapshotMeta.verified_games} of {snapshotMeta.expected_games} expected games,
            or {snapshotMeta.coverage_percentage.toFixed(1)}%. Media rank and strength-of-schedule inputs come from a
            statewide media feed.
          </p>
          <p>
            Every team page shows its own source data: each completed game, the score, the site, and the opponent&rsquo;s
            classification and rating. If something looks wrong, the underlying games are right there to check.
          </p>

          <h2>How often it updates</h2>
          <p>
            Ratings are recalculated weekly in season, after the week&rsquo;s results are in and verified. When a score is
            corrected after publication, the run is reissued as an audited correction rather than edited silently — the
            snapshot records its own status and formula version.
          </p>

          <h2>Corrections</h2>
          <p>
            Published high school scores contain errors, and MFPI inherits them. If you find a wrong score, a missing
            game, or a team in the wrong classification, send the detail and a source and it will be checked against
            the next run. Corrections are welcome from anyone — coaches, statisticians, parents or fans.
          </p>
          <p>
            Write to <a href="mailto:editor@sportsmississippi.com">editor@sportsmississippi.com</a>, or see the{' '}
            <Link href="/contact">contact page</Link>. The full calculation is documented on the{' '}
            <Link href="/methodology">methodology page</Link>.
          </p>

          <h2>Who publishes it</h2>
          <p>
            MFPI is published by the Mississippi Football Power Index, an independent Mississippi sports analytics
            project. It is free to read, with no paywall, subscription or account required, and is supported by
            advertising and direct sponsors. Sponsorship never influences how a team is rated.
          </p>
        </article>
        <SiteFooter />
      </main>
    </>
  );
}
