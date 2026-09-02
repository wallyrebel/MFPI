import RankingsDashboard, { type Snapshot } from './rankings-dashboard';
import snapshotData from '../data/current/overall.json';

export default function Home() {
  return <RankingsDashboard snapshot={snapshotData as Snapshot} />;
}
