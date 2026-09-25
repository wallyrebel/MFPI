import type { Metadata } from 'next';
import Link from 'next/link';
import { SiteFooter, SiteHeader } from '../site-nav';
import { longDate, metadata as snapshotMeta, teams } from '../team-data';

export const metadata: Metadata = {
  title: 'MFPI Methodology',
  description: 'How the Mississippi Football Power Index is calculated: component weights, percentile scaling, opponent-adjusted margin, the class prior and bye-week handling.',
  alternates: { canonical: '/methodology' },
};

const WEIGHTS: Array<[string, string, string]> = [
  ['35%', 'Opponent-adjusted performance', 'Margin of victory or defeat, adjusted for the strength of the opponent and for the site of the game.'],
  ['20%', 'MFPI strength of schedule', 'The average current rating of every completed opponent. This is a rating average, not opponent win percentage.'],
  ['10%', 'Media rank', 'The team’s statewide rank in the MaxPreps Mississippi football rankings (MHSAA 1A–7A teams only), converted to a higher-is-better percentile.'],
  ['10%', 'Media strength of schedule', 'The schedule-strength value published in the MaxPreps rankings. An opening 0.0 is treated as unavailable rather than as the weakest schedule in the state.'],
  ['8%', 'Points scored', 'Points per game, capped at 49 in any single game so a running-clock blowout does not pay extra.'],
  ['8%', 'Points allowed', 'Defensive value derived from points allowed per game, capped the same way.'],
  ['5%', 'Record', 'Wins plus half credit for ties, over games played.'],
  ['4%', 'Recent form', 'The last three opponent-adjusted performances, weighted 1.00, 0.70 and 0.50 newest first.'],
];

export default function MethodologyPage() {
  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <article className="mf-doc">
          <p className="eyebrow">Methodology · Formula {snapshotMeta.formula_version}</p>
          <h1>How MFPI is calculated</h1>
          <p className="mf-doc-meta">
            Week {snapshotMeta.week}, {snapshotMeta.season} · {teams.length} rated teams · updated {longDate(snapshotMeta.generated_at)}
          </p>

          <p>
            MFPI asks one question: based on whom a team played and how it performed, how strong is that team right
            now? Eighty percent of the answer comes from MHSAA classifications, schedules and scores. The remaining
            twenty percent comes from the MaxPreps Mississippi rankings&apos; statewide rank and strength-of-schedule
            values.
          </p>

          <h2>The eight components</h2>
          <p>
            Each raw component becomes a <strong>statewide percentile</strong> among active MHSAA 1A–7A teams. Ties
            receive average rank, and missing early-season values are transparently neutral rather than punitive. The
            weighted sum is constrained to 1.0–100.0 and displayed to one decimal, while the ranking itself uses full
            precision.
          </p>
          <table className="mf-weights-table">
            <thead>
              <tr><th>Weight</th><th>Component</th><th>What it measures</th></tr>
            </thead>
            <tbody>
              {WEIGHTS.map(([weight, name, note]) => (
                <tr key={name}><td className="tabular">{weight}</td><td>{name}</td><td>{note}</td></tr>
              ))}
            </tbody>
          </table>

          <h2>Opponent-adjusted margin</h2>
          <p>
            From each team&rsquo;s perspective, the margin in a game is compressed rather than taken at face value, then
            placed against the opponent&rsquo;s current rating and adjusted for where the game was played. A road team
            receives a small bonus and a home team a small penalty; the recorded score never changes. Compressing the
            margin gives blowouts diminishing returns, so a 60-point win is worth more than a 30-point win but not
            twice as much.
          </p>
          <p>
            Team ratings and opponent ratings are solved together, repeating until every team&rsquo;s rating stops moving,
            then centred across the state. This is why beating a strong team by a little can be worth more than beating
            a weak team by a lot.
          </p>

          <h2>The enrollment-class starting assumption</h2>
          <p>
            Early in a season the statewide game graph is barely connected — teams have played two or three opponents,
            and those opponents have played almost nobody in common. Until that resolves, MFPI assumes larger
            enrollment classes are stronger on average, on a sliding scale from 7A down to 1A.
          </p>
          <p>
            This is a <strong>fading prior, not a permanent bonus</strong>. It carries the weight of about two games
            through a team&rsquo;s first two games, one game through five, and almost nothing after that. Real margins and
            opponent chains progressively replace it, and an excellent lower-class team can and does pass higher-class
            teams. Playing up or down follows directly: face a higher class and both your opponent-adjusted performance
            and your schedule strengthen.
          </p>

          <h2>Confirmed bye weeks</h2>
          <p>
            A team that does not play should not swing wildly on other teams&rsquo; results. On a confirmed bye with
            unchanged verified results, the published score is 90% of the previous week&rsquo;s rating and 10% of the fresh
            recalculation. The adjustment is symmetric — it dampens gains and losses equally.
          </p>
          <p>
            It protects the score, not the rank: other teams can still pass an idle team. A bye also has to be proven,
            not assumed. A team&rsquo;s schedule must show games before and after the empty week; simply missing from a feed
            is not a bye, and neither is a cancellation or postponement. Teams with no previous games get no
            protection.
          </p>

          <h2>Data sources</h2>
          <ul>
            <li>Teams, classifications and regions: the official MHSAA 2025–27 football classification list. Only active
              MHSAA Class 1A–7A programs are ranked; MAIS, out-of-state and other opponents appear on schedules but are
              never ranked.</li>
            <li>Schedules and scores: the official MHSAA score center. A game counts only when it is final with both
              scores. Jamborees and scrimmages never count.</li>
            <li>Media rank and media strength of schedule: the MaxPreps Mississippi football rankings, matched to the
              MHSAA list exactly once per team.</li>
            <li>Gaps: when the MHSAA score center lacks a final for a game that should be over, MaxPreps team schedules
              are checked. A result is accepted only for the same two teams on the scheduled date or one day either side,
              and conflicting reports are rejected. An absent score is never read as a cancellation.</li>
            <li>Out-of-state opponents: a published MaxPreps rating, when available, gives a capped starting estimate
              that fades as real results connect.</li>
          </ul>

          <h2>Missing data and provisional ratings</h2>
          <p>
            A missing score is never treated as 0–0 or as a loss, and postponed or cancelled games do not count. A
            component with no data for a team (for example scoring averages before its first verified game) sits at a
            neutral 50th percentile rather than a punitive zero. When fewer than 95% of the games due by the cutoff have
            verified scores, the whole week is labelled <strong>provisional</strong>. A team with no verified results is
            shown as &ldquo;results unavailable&rdquo;, its averages are shown as &mdash;, and its rating is labelled provisional
            because it rests on class, media and neutral inputs rather than games.
          </p>

          <h2>How changes and dates are shown</h2>
          <p>
            Rank movement is last week&apos;s rank minus this week&apos;s. Rating change is this week&apos;s displayed
            one-decimal rating minus last week&apos;s displayed rating, so the numbers on a page always add up. They are
            reported separately: a team can hold its rank while its rating rises. Both compare against the latest audited
            publication of the previous week; a team with no comparable previous row is shown as NEW. Game dates are
            calendar dates in Central time. Opponent ranks shown beside past games are their current ranks, not their
            ranks on game day.
          </p>

          <h2>Ranking, ties and corrections</h2>
          <p>
            State and class lists use the same MFPI score — a class rating is never recalculated separately. Ties break
            on unrounded rating, then opponent-adjusted performance, then strength of schedule, then head-to-head where
            applicable, then capped scoring margin, and finally team name so output is deterministic. Weekly movement
            compares against the previous published snapshot; a team absent from it shows as NEW.
          </p>
          <p>
            When a score is corrected after publication, the week is reissued as an audited correction run rather than
            edited in place. Each snapshot records its own formula version, status and coverage — this week verified{' '}
            {snapshotMeta.verified_games} of {snapshotMeta.expected_games} expected games.
          </p>

          <p>
            See the <Link href="/">full rankings</Link>, browse <Link href="/teams">every team</Link>, or read more{' '}
            <Link href="/about">about the project</Link>.
          </p>
        </article>
        <SiteFooter />
      </main>
    </>
  );
}
