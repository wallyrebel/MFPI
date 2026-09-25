// Same-name listing problems the site owner has confirmed. The import code
// (mfpi/matching.py REVIEWED_GAME_SIDES) fixes them from the next weekly run;
// until then, pages built from the older snapshot explain what is wrong.
export const CONFIRMED_DOUBLE_BOOKINGS: Record<string, string> = {
  'houston|2026-09-11':
    'The Sept. 11 game against Tupelo was played by an out-of-state school also named Houston. It is removed from this team’s record starting with the next weekly rankings.',
};

/** Teams whose results the feed lists under another name; link confirmed, applies next run. */
export const CONFIRMED_IDENTITY_NOTES: Record<string, string> = {
  'cleveland-central':
    'The official score feed lists this school as “Cleveland.” That link has been confirmed, and its games will count starting with the next weekly rankings.',
};
