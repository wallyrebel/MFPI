import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { SiteFooter, SiteHeader } from '../../../site-nav';
import { findDraft } from '../../../lib/articles';
import { ArticleView } from '../../article-view';

// Local editorial preview only. In a production build findDraft() always
// returns undefined, so this route is a 404 and drafts are never public.
export const metadata: Metadata = { title: 'Draft preview', robots: { index: false, follow: false } };

type Params = { params: Promise<{ slug: string }> };

export default async function DraftPreview({ params }: Params) {
  const article = findDraft((await params).slug);
  if (!article) notFound();
  return (
    <>
      <SiteHeader />
      <main className="page-shell">
        <ArticleView article={article} />
        <SiteFooter />
      </main>
    </>
  );
}
