import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Mississippi Football Power Index',
  description: 'Explainable, computer-generated MHSAA football rankings.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
