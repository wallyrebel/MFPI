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
  ['10%', 'Media rank', 'The statewide ordinal rank from the media feed, converted to a higher-is-better percentile.'],
  ['10%', 'Media strength of schedule', 'The published schedule-strength value. An opening 0.0 is treated as unavailable rather than as the weakest schedule in the state.'],
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
            now? Roughly eighty percent of the answer comes from MHSAA classifications, schedules and scores. The
            remaining twenty percent comes from statewide media rank and strength-of-schedule inputs.
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
