'use client';

type GoogleFc = { callbackQueue: unknown[]; showRevocationMessage?: () => void };
declare global {
  interface Window { googlefc?: GoogleFc }
}

/** Reopens the certified CMP so a visitor can change or withdraw consent. */
export function PrivacyChoicesButton() {
  return (
    <button
      type="button"
      className="mf-link-button"
      onClick={() => {
        const fc = (window.googlefc = window.googlefc || ({ callbackQueue: [] } as GoogleFc));
        fc.callbackQueue = fc.callbackQueue || [];
        fc.callbackQueue.push(() => window.googlefc?.showRevocationMessage?.());
      }}
    >
      Privacy and cookie settings
    </button>
  );
}
