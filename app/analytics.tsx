import { gaMeasurementId } from './site';

// Plain script tags rather than `next/script`: React hoists the async loader
// into <head>, and this keeps the tag independent of the vinext client runtime.
export function GoogleAnalytics() {
  if (!gaMeasurementId) return null;
  return (
    <>
      <script async src={`https://www.googletagmanager.com/gtag/js?id=${gaMeasurementId}`} />
      <script
        dangerouslySetInnerHTML={{
          __html: `window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','${gaMeasurementId}');`,
        }}
      />
    </>
  );
}
