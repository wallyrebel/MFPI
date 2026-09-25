import { adsConfig } from '../site';
import { adsTxt } from '../lib/ads';

// Served as plain text at /ads.txt so the application's HTML fallback is never
// returned for it. Contents come only from the configured publisher ID.
export function GET() {
  return new Response(adsTxt(adsConfig), {
    headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'public, max-age=3600' },
  });
}
