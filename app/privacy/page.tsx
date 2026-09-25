import type { Metadata } from 'next';
import Link from 'next/link';
import { SiteFooter, SiteHeader } from '../site-nav';
import { adsConfig, editorEmail, gaMeasurementId } from '../site';

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description: 'How the Mississippi Football Power Index handles visitor data, cookies, analytics, consent and advertising.',
  alternates: { canonical: '/privacy' },
};

export default function PrivacyPage() {
  const adsOn = adsConfig.enabled;
  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <article className="mf-doc">
          <p className="eyebrow">Legal</p>
          <h1>Privacy Policy</h1>
          <p className="mf-doc-meta">Last updated September 25, 2026</p>

          <p>
            This policy explains what information is collected when you visit the Mississippi Football Power Index
            (&ldquo;MFPI&rdquo;, &ldquo;we&rdquo;, &ldquo;this site&rdquo;) at www.mississippifootballrankings.com, and how it is used.
            MFPI is an independent publication and is not affiliated with the MHSAA, MaxPreps, or any school or school
            district.
          </p>

          <h2>What this site collects</h2>
          <p>
            There is no account, contact form, newsletter signup, comment system or payment processing. The site&apos;s
            own code sets no cookies and uses no browser storage. If you email us, we use your message and address only to
            reply and, for a correction, to check the score you sent.
          </p>
          <p>
            The site is hosted on Cloudflare. Like any web host, Cloudflare receives standard request data — IP address,
            browser and device type, the page requested, the referring page and the time — to deliver and secure the site.
          </p>

          <h2>Analytics</h2>
          {gaMeasurementId ? (
            <p>
              We use Google Analytics 4 to understand which pages are read and how visitors arrive. It can set cookies and
              processes technical data such as IP address, pages viewed, approximate location derived from IP, and session
              length. We use it only in aggregate and do not try to identify individual visitors. You can opt out across
              all sites with Google&apos;s{' '}
              <a href="https://tools.google.com/dlpage/gaoptout" rel="noopener">browser opt-out add-on</a>.
            </p>
          ) : <p>This site does not currently use an analytics service.</p>}

          <h2>Advertising and sponsors</h2>
          <p>
            <strong>Current status:</strong>{' '}
            {adsOn
              ? 'Google AdSense ads are shown on eligible pages (rankings, team and reviewed article pages). Utility pages such as this one, error pages and pages without substantive content carry no ads.'
              : 'Google AdSense ads are not currently shown on this site. This section describes what applies when they are, and this notice will change when they start.'}
          </p>
          <p>
            When advertising from Google is displayed, third-party vendors, including Google, use cookies to serve ads
            based on your prior visits to this and other websites. Google&apos;s use of advertising cookies enables it and
            its partners to serve ads based on your visits to this site and other sites on the internet. You can opt out
            of personalized advertising in{' '}
            <a href="https://adssettings.google.com/" rel="noopener">Google Ads Settings</a>, and opt out of some
            third-party vendors&apos; use of cookies at{' '}
            <a href="https://optout.aboutads.info/" rel="noopener">aboutads.info</a>. Learn more about{' '}
            <a href="https://policies.google.com/technologies/partner-sites" rel="noopener">how Google uses information from sites that use its services</a>.
          </p>
          <p>
            Direct sponsor placements (such as the &ldquo;Sponsored by&rdquo; banner) are static images and ordinary links
            hosted on this site. They set no cookies and do not track you. Sponsorship never influences how a team is rated.
          </p>

          <h2>Consent in the EEA, the UK and Switzerland</h2>
          <p>
            For visitors in the European Economic Area, the United Kingdom and Switzerland, Google&apos;s tags on this site
            start with analytics and advertising storage <em>denied</em> (Google Consent Mode). In that state Google
            Analytics does not set analytics cookies, although Google may still receive cookieless measurement requests.
            {adsConfig.googleCmp
              ? ' Consent is collected through Google’s certified consent management platform. You can change or withdraw your choice at any time with the “Privacy and cookie settings” link at the bottom of every page.'
              : ' Personalized advertising will not be served in these regions until a Google-certified consent management platform is in place; this policy will describe it when it is.'}
          </p>

          <h2>Your choices</h2>
          <ul>
            <li>Block or delete cookies in your browser settings; the rankings remain fully readable without cookies.</li>
            <li>Use the Google Analytics opt-out add-on linked above.</li>
            <li>Turn off personalized advertising in Google Ads Settings.</li>
            {adsConfig.googleCmp && <li>Use &ldquo;Privacy and cookie settings&rdquo; in the site footer to review or withdraw consent.</li>}
            <li>
              You may ask what personal information we hold about you (in practice, only email you have sent us) and ask
              us to delete it. California residents may request information about categories of personal information
              disclosed and opt out of the sale or sharing of personal information by writing to the address below.
            </li>
          </ul>

          <h2>Children</h2>
          <p>
            This site publishes statistics about high school teams, not individual students, and it is not directed at
            children under 13. We do not knowingly collect personal information from children under 13. If you believe a
            child has sent us personal information, contact us and we will delete it.
          </p>

          <h2>Retention and security</h2>
          <p>
            We do not operate a visitor database. Analytics data is kept by Google for the retention period set on our
            property. Email is kept only as long as needed to respond. The site is served over HTTPS.
          </p>

          <h2>External links</h2>
          <p>
            Pages link to outside sources such as the MHSAA and MaxPreps. We are not responsible for their content or
            privacy practices.
          </p>

          <h2>Changes</h2>
          <p>
            We update this policy when the site changes; the date above shows the current version. See also the{' '}
            <Link href="/about">about page</Link>.
          </p>

          <h2>Contact</h2>
          <p>
            Questions about this policy or requests about your data: <a href={`mailto:${editorEmail}`}>{editorEmail}</a>.
          </p>
        </article>
        <SiteFooter />
      </main>
    </>
  );
}
