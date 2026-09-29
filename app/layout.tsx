import type { Metadata } from 'next';
import './globals.css';
import { ExternalScript } from './ads/external-script';
import { GoogleAnalytics } from './analytics';
import { AdvertisingBanner } from './advertising-banner';
import { adsConfig, siteUrl } from './site';
import { ConsentDefaults, GoogleCmpTag } from './ads/consent';

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: 'Mississippi Football Rankings | MHSAA High School Football',
    template: '%s | Mississippi Football Power Index',
  },
  description: 'Mississippi football rankings for every MHSAA high school team in Classes 1A–7A. Compare statewide ratings, records, scores and strength of schedule with MFPI.',
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
    title: 'Mississippi Football Rankings | MHSAA High School Football',
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
    title: 'Mississippi Football Rankings | MHSAA High School Football',
    description: 'Weekly Mississippi high school football rankings with scores, margin of victory, and strength of schedule.',
    images: ['/mfpi-social-card.png'],
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        {adsConfig.client && <meta name="google-adsense-account" content={adsConfig.client} />}
        <ConsentDefaults />
        {adsConfig.client && (
          <ExternalScript
            src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${adsConfig.client}`}
            crossOrigin="anonymous"
          />
        )}
      </head>
      <body>
        <GoogleAnalytics />
        <GoogleCmpTag />
        <AdvertisingBanner />
        {children}
      </body>
    </html>
  );
}
