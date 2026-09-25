import { adsConfig } from '../site';
import { consentDefaultsScript } from '../lib/ads';

/**
 * Consent Mode v2 defaults (denied in the EEA, UK and Switzerland). Rendered
 * before any Google tag so analytics and ad storage wait for a consent signal
 * from the certified CMP in those regions.
 */
export function ConsentDefaults() {
  return <script dangerouslySetInnerHTML={{ __html: consentDefaultsScript() }} />;
}

/**
 * Google's own certified CMP (Privacy & messaging). It is loaded on every page,
 * including ad-free ones, so a visitor can give, refuse or withdraw consent
 * anywhere. The message itself, its regions and its consent-mode integration
 * are configured in the AdSense account.
 */
export function GoogleCmpTag() {
  if (!adsConfig.googleCmp) return null;
  const publisherId = adsConfig.client.replace(/^ca-/, '');
  return (
    <>
      <script async src={`https://fundingchoicesmessages.google.com/i/${publisherId}?ers=1`} />
      <script
        dangerouslySetInnerHTML={{
          __html: "(function(){function signalGooglefcPresent(){if(!window.frames['googlefcPresent']){if(document.body){const iframe=document.createElement('iframe');iframe.style='width:0;height:0;border:none;z-index:-1000;left:-1000px;top:-1000px;';iframe.style.display='none';iframe.name='googlefcPresent';document.body.appendChild(iframe);}else{setTimeout(signalGooglefcPresent,0);}}}signalGooglefcPresent();})();",
        }}
      />
    </>
  );
}
