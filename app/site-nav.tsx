import Link from 'next/link';
import { adsConfig } from './site';
import { PrivacyChoicesButton } from './ads/privacy-choices';

const PRIMARY = [
  ['/', 'Rankings'],
  ['/teams', 'Teams'],
  ['/analysis', 'Analysis'],
  ['/methodology', 'Methodology'],
  ['/about', 'About'],
  ['/advertise', 'Advertise'],
  ['/contact', 'Contact'],
] as const;

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">M</span>
          <div><strong>Mississippi Football</strong><small>POWER INDEX</small></div>
        </Link>
        <nav className="mf-nav" aria-label="Site">
          {PRIMARY.map(([href, label]) => <Link key={href} href={href}>{label}</Link>)}
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mf-footer">
      <div>
        <strong>MFPI · Mississippi Football Power Index</strong>
        <span>Independent rankings from official MHSAA classifications and scores, with MaxPreps media rank and strength of schedule. Not affiliated with or endorsed by the MHSAA or MaxPreps.</span>
      </div>
      <nav aria-label="Footer">
        <Link href="/">Rankings</Link>
        <Link href="/teams">Teams</Link>
        <Link href="/analysis">Analysis</Link>
        <Link href="/archive">Archive</Link>
        <Link href="/methodology">Methodology</Link>
        <Link href="/corrections">Corrections</Link>
        <Link href="/about">About</Link>
        <Link href="/advertise">Advertise</Link>
        <Link href="/contact">Contact</Link>
        <Link href="/privacy">Privacy</Link>
        {adsConfig.googleCmp && <PrivacyChoicesButton />}
      </nav>
    </footer>
  );
}
