import { gaMeasurementId } from './site';
import { ConsentDefaults } from './ads/consent';

// Plain script tags rather than `next/script`: React hoists the async loader
// into <head>, and this keeps the tag independent of the vinext client runtime.
// Consent defaults are pushed to the data layer before the config command.
export function GoogleAnalytics() {
  if (!gaMeasurementId) return <ConsentDefaults />;
  return (
    <>
      <ConsentDefaults />
      <script async src={`https://www.googletagmanager.com/gtag/js?id=${gaMeasurementId}`} />
      <script
        dangerouslySetInnerHTML={{
          __html: `window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','${gaMeasurementId}');`,
        }}
      />
    </>
  );
}
