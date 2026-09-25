'use client';

import { useEffect, useRef, useState } from 'react';

declare global {
  interface Window { adsbygoogle?: unknown[] }
}

// One labelled display unit. Space is reserved to limit layout shift; an
// unfilled or blocked unit collapses (see .ad-slot rules in globals.css), so a
// missing ad never leaves a large empty block or covers content.
export function AdSlot({ client, slot, placement }: { client: string; slot: string; placement: string }) {
  const pushed = useRef(false);
  const unit = useRef<HTMLModElement>(null);
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    if (pushed.current) return;
    pushed.current = true;
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch {
      // A blocked or failed ad script must never break the page.
    }
    // If the ad script never answers (blocked, offline, consent-limited), give
    // the reserved space back rather than leave an empty block.
    const timer = window.setTimeout(() => {
      if (!unit.current?.getAttribute('data-ad-status')) setCollapsed(true);
    }, 5000);
    return () => window.clearTimeout(timer);
  }, []);
  return (
    <aside className="ad-slot" aria-label="Advertisement" data-placement={placement} hidden={collapsed}>
      <span className="ad-label">Advertisement</span>
      <ins
        ref={unit}
        className="adsbygoogle"
        style={{ display: 'block' }}
        data-ad-client={client}
        data-ad-slot={slot}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </aside>
  );
}
