import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { SiteFooter, SiteHeader } from '../../site-nav';
import { siteUrl } from '../../site';
import { pageAds } from '../../ads/page-ads';
import { findPublished, publishedArticles } from '../../lib/articles';
import { ArticleView } from '../article-view';

type Params = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return publishedArticles.map((article) => ({ slug: article.slug }));
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const article = findPublished((await params).slug);
  if (!article) return {};
  return {
    title: article.title,
    description: article.dek,
    alternates: { canonical: `/analysis/${article.slug}` },
    openGraph: { type: 'article', url: `${siteUrl}/analysis/${article.slug}`, title: article.title, description: article.dek, publishedTime: article.published_at ?? undefined },
  };
}

export default async function ArticlePage({ params }: Params) {
  const article = findPublished((await params).slug);
  if (!article) notFound();
  const ads = pageAds(
    // Automated articles have no human reviewer, so they stay ad-free.
    { kind: 'article', substantive: article.sections.length >= 3, reviewStatus: article.status, reviewedBy: article.reviewed_by },
    ['article-mid', 'article-bottom'],
  );
  const middle = Math.max(1, Math.floor(article.sections.length / 2) - 1);
  return (
    <>
      <SiteHeader />
      {ads.script}
      <main className="page-shell">
        <ArticleView article={article} between={{ [middle]: ads.slot('article-mid'), [article.sections.length - 1]: ads.slot('article-bottom') }} />
        <SiteFooter />
      </main>
    </>
  );
}
