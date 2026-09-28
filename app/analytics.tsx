import { ExternalScript } from './ads/external-script';
import { gaMeasurementId } from './site';


// ExternalScript prevents React from moving this loader before consent defaults.
// Consent defaults are initialized in the root head.
// Consent defaults are pushed to the data layer before the config command.
export function GoogleAnalytics() {
  if (!gaMeasurementId) return null;
  return (
    <>

      <ExternalScript src={`https://www.googletagmanager.com/gtag/js?id=${gaMeasurementId}`} />
      <script
        dangerouslySetInnerHTML={{
          __html: `window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','${gaMeasurementId}');`,
        }}
      />
    </>
  );
}
