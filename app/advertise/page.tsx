import type { Metadata } from 'next';
import { SiteFooter, SiteHeader } from '../site-nav';
import { advertisingEmail } from '../site';

const description = 'Advertise your business on an individual team page or across the entire Mississippi Football Power Index site. Email for details.';

export const metadata: Metadata = {
  title: 'Advertise',
  description,
  alternates: { canonical: '/advertise' },
  openGraph: { title: 'Advertise with MFPI', description, url: '/advertise' },
  twitter: { title: 'Advertise with MFPI', description },
};

export default function AdvertisePage() {
  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <article className="mf-doc advertise-page">
          <p className="eyebrow">Advertising</p>
          <h1>Advertise with MFPI</h1>
          <p className="advertise-intro">
            Put your business in front of fans following Mississippi high school football.
            Choose an individual team page or advertise across the entire site.
          </p>

          <div className="advertise-options">
            <section>
              <h2>Individual team page</h2>
              <p>
                Feature your business on the page of a team you choose, alongside its
                rankings, record, and game results.
              </p>
              <p>Connect with readers following a local program.</p>
            </section>
            <section>
              <h2>Entire site</h2>
              <p>
                Advertise across MFPI to reach readers following teams throughout Mississippi.
              </p>
              <p>Give your business a presence beyond a single team page.</p>
            </section>
          </div>

          <section className="advertise-contact">
            <h2>Let’s talk advertising</h2>
            <p>
              Email for details, availability, and pricing. Include your business name and
              let us know whether you’re interested in a team page or the entire site.
            </p>
            <a className="advertise-email-button" href={`mailto:${advertisingEmail}`}>
              Email for advertising details
            </a>
            <p className="advertise-email-address">
              <a href={`mailto:${advertisingEmail}`}>{advertisingEmail}</a>
            </p>
          </section>
        </article>
        <SiteFooter />
      </main>
    </>
  );
}
