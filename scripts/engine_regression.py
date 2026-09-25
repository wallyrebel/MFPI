# Compare ratings from two copies of the engine on identical inputs rebuilt from
# data/current (games, media signals, previous week). Usage:
#   git worktree add /tmp/mfpi-base <ref>
#   python scripts/engine_regression.py /tmp/mfpi-base /tmp/base.json
#   python scripts/engine_regression.py . /tmp/head.json
# then compare the two JSON files; identical files mean identical ranks/ratings.
import json, sys
from datetime import datetime
sys.path.insert(0, sys.argv[1])
from mfpi.models import Team, Game, MaxPrepsSignal
from mfpi.config import Settings
from mfpi.engine import calculate_rankings
from mfpi.fixtures import demo_dataset
d = json.load(open('data/current/overall.json'))
prev = json.load(open('data/2026/week-03/overall.json'))
teams = [Team(r['team_id'], r['team'].lower(), r['team'], r['classification'], r['region']) for r in d['rankings']]
for eid, name in d['metadata']['opponent_names'].items():
    teams.append(Team(eid, name.lower(), name, None))
seen = {}
for r in d['rankings']:
    for g in r['game_results']:
        k = (g['date'], g['home'], g['away'])
        seen[k] = Game(f"{len(seen)}", datetime.fromisoformat(g['date']), g['home'], g['away'], g['home_score'], g['away_score'],
                       neutral_site=g['neutral'], overtime=g['overtime'], forfeit=g['forfeit'])
signals = {r['team_id']: MaxPrepsSignal(r['team_id'], r['maxpreps_state_rank'], r['maxpreps_rating'], r['maxpreps_strength'], 'x')
           for r in d['rankings'] if r['maxpreps_state_rank']}
cutoff = datetime.fromisoformat(d['metadata']['cutoff_at'])
previous = {r['team_id']: r for r in prev['rankings']}
res = calculate_rankings(teams, list(seen.values()), cutoff, Settings(week=4), previous, signals,
                         confirmed_bye_team_ids={'falkner'})
dt, dg = demo_dataset()
demo = calculate_rankings(dt, dg, datetime.fromisoformat('2026-09-01T11:00:00-05:00'), Settings())
out = {'live': [(r.team.team_id, r.state_rank, r.class_rank, round(r.mfpi, 10), r.record, r.games_played) for r in res.rankings],
       'demo': [(r.team.team_id, r.state_rank, round(r.mfpi, 10)) for r in demo.rankings],
       'srs_iterations': res.iterations}
json.dump(out, open(sys.argv[2], 'w'))
