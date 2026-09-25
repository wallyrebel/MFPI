import type { SnapshotMeta, Team } from './team-data';

// Every immutable weekly publication, loaded on demand. Originals and audited
// correction revisions are both kept; the latest revision is the one shown,
// and the page says when a correction was issued.
type WeeklySnapshot = { metadata: SnapshotMeta; rankings: Team[] };

const loaders = import.meta.glob(
  ['../data/*/week-*/overall.json', '../data/*/week-*/corrections/revision-*/overall.json'],
  { import: 'default' },
) as Record<string, () => Promise<WeeklySnapshot>>;

export type ArchiveEntry = {
  season: number;
  week: number;
  /** URL segment, e.g. "week-04". */
  slug: string;
  original: string;
  revisions: string[];
};

function parse(path: string) {
  const match = /data\/(\d{4})\/week-(\d{2})\/(?:corrections\/(revision-\d{2})\/)?overall\.json$/.exec(path);
  return match ? { season: Number(match[1]), week: Number(match[2]), revision: match[3] ?? null } : null;
}

export const archive: ArchiveEntry[] = (() => {
  const entries = new Map<string, ArchiveEntry>();
  for (const path of Object.keys(loaders)) {
    const info = parse(path);
    if (!info) continue;
    const key = `${info.season}-${info.week}`;
    const entry = entries.get(key) ?? {
      season: info.season, week: info.week, slug: `week-${String(info.week).padStart(2, '0')}`, original: '', revisions: [],
    };
    if (info.revision) entry.revisions.push(path);
    else entry.original = path;
    entries.set(key, entry);
  }
  for (const entry of entries.values()) entry.revisions.sort();
  return [...entries.values()].filter((entry) => entry.original).sort((a, b) => b.season - a.season || b.week - a.week);
})();

export function findArchive(season: number, slug: string): ArchiveEntry | undefined {
  return archive.find((entry) => entry.season === season && entry.slug === slug);
}

export async function loadSnapshot(path: string): Promise<WeeklySnapshot> {
  return loaders[path]();
}

/** The latest audited publication for a week (a correction if one exists). */
export async function loadLatest(entry: ArchiveEntry) {
  return loadSnapshot(entry.revisions.at(-1) ?? entry.original);
}

/** The latest audited snapshot of the week before `week`, for comparisons. */
export async function loadPreviousWeek(season: number, week: number): Promise<WeeklySnapshot | null> {
  const entry = archive.find((item) => item.season === season && item.week === week - 1);
  return entry ? loadLatest(entry) : null;
}
