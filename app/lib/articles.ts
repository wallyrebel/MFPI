// Weekly Analysis articles from content/analysis/*.json.
//
// Only articles a named person has reviewed and published are public. Drafts
// are never routed, listed, put in the sitemap, or given ads in a production
// build; `npm run dev` shows them under /analysis/preview/<slug> for review.

export type ArticleSection = {
  heading: string;
  paragraphs?: string[];
  table?: { columns: string[]; rows: string[][] };
};

export type Article = {
  slug: string;
  kind: string;
  title: string;
  dek: string;
  status: 'draft' | 'in_review' | 'published';
  season: number;
  week: number;
  snapshot_run_id?: string;
  snapshot_generated_at: string;
  formula_version: string;
  author: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  published_at: string | null;
  sources: { label: string; url: string }[];
  limitations: string[];
  sections: ArticleSection[];
};

const modules = import.meta.glob('../../content/analysis/*.json', { eager: true, import: 'default' }) as Record<string, Article>;

export const allArticles: Article[] = Object.values(modules);

export function isPublished(article: Article): boolean {
  return article.status === 'published' && Boolean(article.reviewed_by?.trim()) && Boolean(article.reviewed_at) && Boolean(article.published_at);
}

export const publishedArticles: Article[] = allArticles
  .filter(isPublished)
  .sort((a, b) => (b.published_at ?? '').localeCompare(a.published_at ?? ''));

export const draftPreviewEnabled = import.meta.env.DEV;

export function findPublished(slug: string): Article | undefined {
  return publishedArticles.find((article) => article.slug === slug);
}

export function findDraft(slug: string): Article | undefined {
  return draftPreviewEnabled ? allArticles.find((article) => article.slug === slug && !isPublished(article)) : undefined;
}

/** Split text into plain strings and [[team-id]] / [[risers-and-fallers:slug]] references. */
export function tokens(text: string): ({ text: string } | { team: string } | { article: string })[] {
  const out: ({ text: string } | { team: string } | { article: string })[] = [];
  const pattern = /\[\[([^\]]+)\]\]/g;
  let last = 0;
  for (let match = pattern.exec(text); match; match = pattern.exec(text)) {
    if (match.index > last) out.push({ text: text.slice(last, match.index) });
    const ref = match[1];
    out.push(ref.includes(':') ? { article: ref.split(':')[1] } : { team: ref });
    last = match.index + match[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}
