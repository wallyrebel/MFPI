'use client';

// An onLoad handler opts out of React's automatic script hoisting. Keep Google
// tags after the consent defaults in the document, including during SSR.
export function ExternalScript({ src, crossOrigin }: { src: string; crossOrigin?: 'anonymous' }) {
  return <script async src={src} crossOrigin={crossOrigin} onLoad={() => {}} />;
}
