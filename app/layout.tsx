import type { Metadata } from 'next';
import './globals.css';

const siteUrl = 'https://www.mississippifootballrankings.com';

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: 'Mississippi Football Power Index | Mississippi Football Rankings',
    template: '%s | Mississippi Football Power Index',
  },
  description: 'Weekly Mississippi high school football rankings for every MHSAA team, powered by an explainable Mississippi Football Power Index using scores, margin of victory, and strength of schedule.',
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
  },
  twitter: {
    card: 'summary',
    title: 'Mississippi Football Power Index | Mississippi Football Rankings',
    description: 'Weekly Mississippi high school football rankings with scores, margin of victory, and strength of schedule.',
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
