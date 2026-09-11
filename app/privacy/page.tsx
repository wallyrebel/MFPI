import type { Metadata } from 'next';
import { SiteFooter, SiteHeader } from '../site-nav';

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description: 'How the Mississippi Football Power Index handles visitor data, cookies, analytics and advertising.',
  alternates: { canonical: '/privacy' },
};

const CONTACT = 'editor@sportsmississippi.com';

export default function PrivacyPage() {
  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <article className="mf-doc">
          <p className="eyebrow">Legal</p>
          <h1>Privacy Policy</h1>
          <p className="mf-doc-meta">Last updated September 11, 2026</p>

          <p>
            This policy explains what information is collected when you visit the Mississippi Football Power Index
            (&ldquo;MFPI&rdquo;, &ldquo;we&rdquo;, &ldquo;this site&rdquo;) at www.mississippifootballrankings.com, and how that information is
            used. MFPI is an independent publication and is not affiliated with the MHSAA or any school or school
            district.
          </p>

          <h2>Information we collect</h2>
          <p>
            This site does not ask you to create an account, and it has no contact form, newsletter signup, comment
            system, or payment processing. We do not knowingly collect names, email addresses, postal addresses or
            payment details from visitors.
          </p>
          <p>
            Like most websites, our hosting provider and our analytics and advertising partners automatically receive
            standard technical information when you load a page. That can include your IP address, browser type and
            version, device type, operating system, the page you requested, the referring page, and the date and time of
            the request.
          </p>

          <h2>Cookies and similar technologies</h2>
          <p>
            Cookies are small files stored on your device. This site uses them for analytics and, where ads are shown,
            for advertising. You can block or delete cookies in your browser settings; the rankings remain fully
            readable with cookies disabled.
          </p>

          <h2>Analytics</h2>
          <p>
            We use Google Analytics 4 to understand which pages are read and how visitors arrive. Google Analytics sets
            cookies and processes technical data such as IP address, pages viewed, approximate location derived from IP,
            and session duration. We use this only in aggregate, to decide what to publish. We do not attempt to
            identify individual visitors.
          </p>
          <p>
            You can opt out of Google Analytics across all sites by installing Google&rsquo;s{' '}
            <a href="https://tools.google.com/dlpage/gaoptout" target="_blank" rel="noreferrer noopener">
              browser opt-out add-on
            </a>.
          </p>

          <h2>Advertising and sponsors</h2>
          <p>
            This site may display advertising supplied by Google, including Google AdSense, and by other third-party ad
            vendors and networks. Third-party vendors, including Google, use cookies to serve ads based on your prior
            visits to this and other websites.
          </p>
          <p>
            Google&rsquo;s use of advertising cookies enables it and its partners to serve ads to you based on your visit to
            this site and other sites on the internet. You can opt out of personalized advertising at{' '}
            <a href="https://www.google.com/settings/ads" target="_blank" rel="noreferrer noopener">Google Ads Settings</a>.
            You can also opt out of a third-party vendor&rsquo;s use of cookies at{' '}
            <a href="https://optout.aboutads.info/" target="_blank" rel="noreferrer noopener">aboutads.info</a> or{' '}
            <a href="https://optout.networkadvertising.org/" target="_blank" rel="noreferrer noopener">the NAI opt-out page</a>.
          </p>
          <p>
            This site also carries direct sponsor placements sold by us. Those are static images and links; they do not
            set cookies or track you, and sponsorship never influences how a team is rated.
          </p>

          <h2>Visitors in the EEA, UK and Switzerland</h2>
          <p>
            Where required, advertising and analytics cookies that are not strictly necessary are set only with consent,
            collected through a consent notice before those cookies load. You may withdraw consent at any time by
            clearing cookies for this site. Our lawful basis is your consent for analytics and advertising cookies, and
            legitimate interest in the secure operation of the site for basic server logs.
          </p>

          <h2>Your choices</h2>
          <ul>
            <li>Block or delete cookies in your browser settings.</li>
            <li>Use the Google Analytics opt-out add-on linked above.</li>
            <li>Turn off personalized advertising in Google Ads Settings.</li>
            <li>Use your browser&rsquo;s private or incognito mode.</li>
            <li>
              If you are a California resident, you may request information about the categories of personal
              information disclosed, and opt out of the sale or sharing of personal information, by writing to the
              address below.
            </li>
          </ul>

          <h2>Children</h2>
          <p>
            This site publishes statistics about high school athletic teams, not about individual minors, and it is not
            directed at children under 13. We do not knowingly collect personal information from children under 13. If
            you believe a child has provided personal information, contact us and we will delete it.
          </p>

          <h2>Data retention and security</h2>
          <p>
            We do not operate a visitor database. Analytics data is retained by Google under the retention period set
            for our property, after which it is deleted by Google. The site is served over HTTPS.
          </p>

          <h2>External links</h2>
          <p>
            Pages may link to outside sources, including media and athletic association sites. We are not responsible
            for the content or privacy practices of those sites.
          </p>

          <h2>Changes</h2>
          <p>
            We may update this policy as the site changes. The &ldquo;last updated&rdquo; date above always reflects the current
            version.
          </p>

          <h2>Contact</h2>
          <p>
            Questions about this policy, or requests concerning your data, can be sent to{' '}
            <a href={`mailto:${CONTACT}`}>{CONTACT}</a>.
          </p>
        </article>
        <SiteFooter />
      </main>
    </>
  );
}
