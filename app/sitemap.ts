import type { MetadataRoute } from 'next';
import { siteUrl } from './site';
import { archive } from './archive-data';
import { publishedArticles } from './lib/articles';
import { metadata as snapshotMeta, teams } from './team-data';

// Public, substantive pages only. Drafts and previews never appear here.
export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date(snapshotMeta.generated_at);

  const staticPages: MetadataRoute.Sitemap = [
    { url: `${siteUrl}/`, changeFrequency: 'weekly', priority: 1, lastModified },
    { url: `${siteUrl}/teams`, changeFrequency: 'weekly', priority: 0.7, lastModified },
    { url: `${siteUrl}/analysis`, changeFrequency: 'weekly', priority: 0.7, lastModified },
    { url: `${siteUrl}/archive`, changeFrequency: 'weekly', priority: 0.5, lastModified },
    { url: `${siteUrl}/methodology`, changeFrequency: 'monthly', priority: 0.6 },
    { url: `${siteUrl}/corrections`, changeFrequency: 'weekly', priority: 0.4, lastModified },
    { url: `${siteUrl}/about`, changeFrequency: 'monthly', priority: 0.5 },
    { url: `${siteUrl}/advertise`, changeFrequency: 'monthly', priority: 0.3 },
    { url: `${siteUrl}/contact`, changeFrequency: 'yearly', priority: 0.3 },
    { url: `${siteUrl}/privacy`, changeFrequency: 'yearly', priority: 0.2 },
  ];

  const teamPages: MetadataRoute.Sitemap = teams.map((row) => ({
    url: `${siteUrl}/team/${row.slug}`,
    changeFrequency: 'weekly' as const,
    priority: 0.8,
    lastModified,
  }));

  const articles: MetadataRoute.Sitemap = publishedArticles.map((article) => ({
    url: `${siteUrl}/analysis/${article.slug}`,
    changeFrequency: 'monthly' as const,
    priority: 0.6,
    lastModified: new Date(article.published_at!),
  }));

  const weeks: MetadataRoute.Sitemap = archive.map((entry) => ({
    url: `${siteUrl}/archive/${entry.season}/${entry.slug}`,
    changeFrequency: 'yearly' as const,
    priority: 0.3,
  }));

  return [...staticPages, ...teamPages, ...articles, ...weeks];
}
