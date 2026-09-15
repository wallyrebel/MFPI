import Link from 'next/link';
import { advertisingEmail } from './site';

export function AdvertisingBanner() {
  return (
    <aside className="advertise-banner" aria-label="Advertising opportunities">
      <div className="advertise-banner-inner">
        <a className="advertise-banner-cta" href={`mailto:${advertisingEmail}`}>
          Advertise Here
        </a>
        <p>Promote your business on a team page or across the site.</p>
        <Link className="advertise-banner-details" href="/advertise">View options</Link>
      </div>
    </aside>
  );
}
