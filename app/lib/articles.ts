// Weekly Analysis articles from content/analysis/*.json.
//
// Published articles are either reviewed by a named person
// (publication_mode "reviewed") or automated weekly analysis published under
// the operator's standing approval (publication_mode "automated"), which is
// labelled as such and carries no ads. Drafts are never routed, listed or put
// in the sitemap in production; `npm run dev` shows them under
// /analysis/preview/<slug>.

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
  publication_mode?: 'reviewed' | 'automated';
  approved_by?: string | null;
  updated_at?: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  published_at: string | null;
  sources: { label: string; url: string }[];
  limitations: string[];
  sections: ArticleSection[];
};

const modules = import.meta.glob('../../content/analysis/*.json', { eager: true, import: 'default' }) as Record<string, Article>;

export const allArticles: Article[] = Object.values(modules);

export function isAutomated(article: Article): boolean {
  return article.publication_mode === 'automated';
}

export function isPublished(article: Article): boolean {
  if (article.status !== 'published' || !article.published_at) return false;
  if (isAutomated(article)) return Boolean(article.approved_by?.trim()) && !article.reviewed_by;
  return Boolean(article.reviewed_by?.trim()) && Boolean(article.reviewed_at);
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
