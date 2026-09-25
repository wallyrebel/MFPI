import type { Metadata } from 'next';
import './globals.css';
import { GoogleAnalytics } from './analytics';
import { AdvertisingBanner } from './advertising-banner';
import { adsConfig, siteUrl } from './site';
import { GoogleCmpTag } from './ads/consent';

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: 'Mississippi Football Power Index | Mississippi Football Rankings',
    template: '%s | Mississippi Football Power Index',
  },
  description: 'Weekly Mississippi high school football rankings for every MHSAA team, powered by an explainable Mississippi Football Power Index using scores, margin of victory, and strength of schedule.',
  category: 'Sports',
  authors: [{ name: 'Mississippi Football Power Index' }],
  creator: 'Mississippi Football Power Index',
  publisher: 'Mississippi Football Power Index',
  keywords: [
    'Mississippi Football Power Index',
    'Mississippi football rankings',
    'Mississippi high school football rankings',
    'MHSAA football rankings',
    'Mississippi football scores',
    'Mississippi football strength of schedule',
  ],
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    url: siteUrl,
    siteName: 'Mississippi Football Power Index',
    title: 'Mississippi Football Power Index | Mississippi Football Rankings',
    description: 'Weekly, explainable Mississippi high school football rankings for all MHSAA classifications.',
    images: [
      {
        url: '/mfpi-social-card.png',
        width: 1200,
        height: 630,
        alt: 'Mississippi Football Power Index',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Mississippi Football Power Index | Mississippi Football Rankings',
    description: 'Weekly Mississippi high school football rankings with scores, margin of victory, and strength of schedule.',
    images: ['/mfpi-social-card.png'],
  },
  robots: { index: true, follow: true },
  // Site ownership verification for AdSense. Independent of whether ad slots
  // render: the meta tag loads no ad code.
  other: adsConfig.client ? { 'google-adsense-account': adsConfig.client } : undefined,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <GoogleAnalytics />
        <GoogleCmpTag />
        <AdvertisingBanner />
        {children}
      </body>
    </html>
  );
}
