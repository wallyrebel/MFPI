import type { Metadata } from 'next';
import { publisher, siteUrl } from './site';
import RankingsDashboard, { type Ranking, type Snapshot } from './rankings-dashboard';
import { pageAds } from './ads/page-ads';
import { ageInDays, centralWeekdayTime } from './lib/format';
import { metadata as snapshotMeta, teamRatingChange, teamScoring, teamStatus, teams } from './team-data';

const title = `Mississippi Football Rankings ${snapshotMeta.season} | MHSAA 1A–7A | MFPI`;
const description = `View ${snapshotMeta.season} Mississippi high school football rankings for all ${teams.length} MHSAA teams in Classes 1A–7A. Compare weekly MFPI ratings, records, scores and schedule strength.`;

export const metadata: Metadata = {
  title: { absolute: title },
  description,
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    url: `${siteUrl}/`,
    siteName: 'Mississippi Football Rankings',
    title,
    description,
    images: [{ url: '/mfpi-social-card.png', width: 1200, height: 630, alt: 'Mississippi Football Power Index' }],
  },
  twitter: { card: 'summary_large_image', title, description, images: ['/mfpi-social-card.png'] },
};

export default function Home() {
  const publicSnapshot: Snapshot = {
    metadata: {
      ...snapshotMeta,
      cutoff_label: centralWeekdayTime(snapshotMeta.cutoff_at),
      data_sources: snapshotMeta.data_sources.map((source) => ({
        name: source.name,
        retrieved_at: source.retrieved_at,
      })),
    },
    rankings: teams.map((team): Ranking => {
      const scoring = teamScoring(team);
      const { maxpreps_rank: media_rank, maxpreps_sos: media_sos, ...components } = team.components;
      return {
        team_id: team.team_id,
        slug: team.slug,
        team: team.team,
        classification: team.classification,
        region: team.region,
        record: team.record,
        games_played: team.games_played,
        data_status: teamStatus(team),
        state_rank: team.state_rank,
        class_rank: team.class_rank,
        mfpi: team.mfpi,
        mfpi_unrounded: team.mfpi_unrounded,
        previous_state_rank: team.previous_state_rank,
        state_rank_change: team.state_rank_change,
        class_rank_change: team.class_rank_change,
        rating_change: teamRatingChange(team),
        pf_per_game: scoring?.pointsFor ?? null,
        pa_per_game: scoring?.pointsAgainst ?? null,
        media_state_rank: team.maxpreps_state_rank,
        media_strength: team.maxpreps_strength,
        up_games: team.up_games,
        same_class_games: team.same_class_games,
        down_games: team.down_games,
        class_schedule_delta: team.class_schedule_delta,
        schedule_direction: team.schedule_direction,
        components: { ...components, media_rank, media_sos },
        bye_adjustment: team.bye_adjustment ?? null,
      };
    }),
  };

  // Rendered per request, so the age shown is the snapshot's real age.
  const age = ageInDays(snapshotMeta.generated_at, new Date());
  const ads = pageAds({ kind: 'rankings', substantive: teams.length > 0 }, ['rankings-top', 'rankings-bottom']);

  return (
    <>

      <RankingsDashboard
        snapshot={publicSnapshot}
        ageDays={age}
        adTop={ads.slot('rankings-top')}
        adBottom={ads.slot('rankings-bottom')}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@graph': [
              {
                '@type': 'WebSite',
                '@id': `${siteUrl}/#website`,
                name: 'Mississippi Football Rankings',
                alternateName: ['Mississippi Football Power Index', 'MFPI'],
                url: `${siteUrl}/`,
                description,
                inLanguage: 'en-US',
                publisher: { '@id': `${siteUrl}/#publisher` },
              },
              {
                '@type': 'Organization',
                '@id': `${siteUrl}/#publisher`,
                name: publisher.organization,
                url: `${siteUrl}/about`,
              },
              {
                '@type': 'CollectionPage',
                '@id': `${siteUrl}/#rankings`,
                url: `${siteUrl}/`,
                name: title,
                description,
                dateModified: snapshotMeta.generated_at,
                isPartOf: { '@id': `${siteUrl}/#website` },
                mainEntity: {
                  '@type': 'ItemList',
                  name: `${snapshotMeta.season} Week ${snapshotMeta.week} Mississippi high school football top 25`,
                  itemListOrder: 'https://schema.org/ItemListOrderAscending',
                  numberOfItems: Math.min(25, teams.length),
                  itemListElement: teams.slice(0, 25).map((team) => ({
                    '@type': 'ListItem',
                    position: team.state_rank,
                    name: team.team,
                    url: `${siteUrl}/team/${team.slug}`,
                  })),
                },
              },
            ],
          }).replace(/</g, '\\u003c'),
        }}
      />
    </>
  );
}
