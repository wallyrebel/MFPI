import RankingsDashboard, { type ComponentValue, type Ranking, type Snapshot } from './rankings-dashboard';
import snapshotData from '../data/current/overall.json';

type SourceRanking = Omit<Ranking, 'media_state_rank' | 'media_strength' | 'components'> & {
  maxpreps_state_rank: number | null;
  maxpreps_rating: number | null;
  maxpreps_strength: number | null;
  components: Record<string, ComponentValue>;
};

type SourceSnapshot = Omit<Snapshot, 'rankings'> & { rankings: SourceRanking[] };

export default function Home() {
  const snapshot = snapshotData as SourceSnapshot;
  const publicSourceNames = [
    'Official MHSAA classifications and scores',
    'Media Rank and Strength of Schedule',
    'Secondary score verification',
  ];
  const publicSnapshot: Snapshot = {
    ...snapshot,
    metadata: {
      ...snapshot.metadata,
      data_sources: snapshot.metadata.data_sources.map((source, index) => ({
        name: source.name.includes('demo') ? source.name : (publicSourceNames[index] ?? 'Public football data'),
        retrieved_at: source.retrieved_at,
        configured: source.configured,
      })),
    },
    rankings: snapshot.rankings.map((ranking) => {
      const {
        maxpreps_state_rank: media_state_rank,
        maxpreps_rating: unusedMediaRating,
        maxpreps_strength: media_strength,
        components: sourceComponents,
        ...publicRanking
      } = ranking;
      const {
        maxpreps_rank: media_rank,
        maxpreps_sos: media_sos,
        ...components
      } = sourceComponents;
      void unusedMediaRating;

      return {
        ...publicRanking,
        media_state_rank,
        media_strength,
        components: { ...components, media_rank, media_sos },
        explanation: '',
      };
    }),
  };

  return <RankingsDashboard snapshot={publicSnapshot} />;
}
