import Link from 'next/link';
import { SiteFooter, SiteHeader } from './site-nav';

// Error pages never carry ad code.
export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <article className="mf-doc">
          <p className="eyebrow">404</p>
          <h1>Page not found</h1>
          <p>
            That page does not exist. Try the <Link href="/">current rankings</Link>, the{' '}
            <Link href="/teams">team directory</Link>, or the <Link href="/archive">weekly archive</Link>.
          </p>
        </article>
        <SiteFooter />
      </main>
    </>
  );
}
