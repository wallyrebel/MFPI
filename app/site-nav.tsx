import Link from 'next/link';

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand" href="/">
          <span className="brand-mark">M</span>
          <div><strong>Mississippi Football</strong><small>POWER INDEX</small></div>
        </Link>
        <nav className="mf-nav" aria-label="Site">
          <Link href="/">Rankings</Link>
          <Link href="/teams">Teams</Link>
          <Link href="/methodology">Methodology</Link>
          <Link href="/about">About</Link>
          <Link href="/advertise">Advertise</Link>
          <Link href="/contact">Contact</Link>
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
        <span>Official MHSAA classifications and scores · Media rank and strength of schedule</span>
      </div>
      <nav aria-label="Footer">
        <Link href="/">Rankings</Link>
        <Link href="/teams">Teams</Link>
        <Link href="/methodology">Methodology</Link>
        <Link href="/about">About</Link>
        <Link href="/advertise">Advertise</Link>
        <Link href="/contact">Contact</Link>
        <Link href="/privacy">Privacy</Link>
      </nav>
    </footer>
  );
}
