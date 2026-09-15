import type { Metadata } from 'next';
import Link from 'next/link';
import { SiteFooter, SiteHeader } from '../site-nav';

export const metadata: Metadata = {
  title: 'Contact',
  description: 'Reach the Mississippi Football Power Index with a score correction, a missing game, or a question about the rating.',
  alternates: { canonical: '/contact' },
};

const CONTACT = 'editor@sportsmississippi.com';

export default function ContactPage() {
  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <article className="mf-doc">
          <p className="eyebrow">Contact</p>
          <h1>Contact MFPI</h1>

          <p>
            Email <a href={`mailto:${CONTACT}`}>{CONTACT}</a>. Messages are read by the person who maintains the
            rankings, and corrections are usually reflected in the next weekly run.
          </p>

          <h2>Reporting a wrong or missing score</h2>
          <p>
            This is the most useful thing you can send. A single missing game can move a team several places, and one
            wrong score distorts every opponent it touches. To make a correction quick to verify, include:
          </p>
          <ul>
            <li>Both team names, as they appear on the rankings page</li>
            <li>The date of the game</li>
            <li>The final score, and whether it went to overtime</li>
            <li>A link or source, if you have one — a box score, official result or news report</li>
          </ul>
          <p>
            Corrections are verified against official results rather than entered by hand, so a score that has not been
            reported anywhere may not be fixable until it is. Confirmed corrections are published as an audited
            correction run, not edited in silently.
          </p>

          <h2>Other questions</h2>
          <ul>
            <li>
              <strong>Why did my team drop after a win?</strong> Ratings are relative. If the teams around you had
              better results, or the opponent you beat rated lower than expected, you can win and still slide. The
              breakdown on each team page shows which component moved.
            </li>
            <li>
              <strong>Why is a team we beat rated above us?</strong> Head-to-head is one input among several. Schedule
              strength and margin across every game carry more weight than a single result.
            </li>
            <li>
              <strong>Advertising and sponsorship.</strong> Advertise on an individual team page or across the entire
              site. <Link href="/advertise">View advertising options</Link> and email for details.
            </li>
            <li>
              <strong>Media and reuse.</strong> You are welcome to cite MFPI ratings with attribution and a link.
            </li>
          </ul>

          <h2>What this site is</h2>
          <p>
            MFPI is an independent project, not an official product of the MHSAA or any school. More detail is on the{' '}
            <Link href="/about">about page</Link>, and the calculation is documented on the{' '}
            <Link href="/methodology">methodology page</Link>. See also the{' '}
            <Link href="/privacy">privacy policy</Link>.
          </p>
        </article>
        <SiteFooter />
      </main>
    </>
  );
}
