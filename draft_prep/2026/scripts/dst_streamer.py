#!/usr/bin/env python3
"""Unified D/ST streamer for all three leagues - projection-driven, no static lists.

Builds a recency-weighted, strength-of-schedule-adjusted projection for EVERY defense in
EVERY upcoming matchup (see dst_model.py), scores it in the chosen league's exact rules
(pulled live from each platform, including the points/yards-allowed tiers), and prints the
best available streamers each week plus any defense worth grabbing and holding.

  python dst_streamer.py --league gg        # Gridiron Grind  (Fleaflicker 78455)
  python dst_streamer.py --league dynasty    # DyNasty         (Sleeper)
  python dst_streamer.py --league glorp      # Eat GLORP       (ESPN 686982204)
      [--week N] [--ahead 2] [--lookback 6] [--half-life 2.5] [--all]

Scoring is fetched fresh from each league every run, so a rules change is picked up
automatically. The model reads recent form fresh each week - swap a defense weekly and
just take the top available play. Std-lib only (ESPN league is private -> needs cookies,
same .espn_cookies.json as the other ESPN scripts).
"""
import urllib.request, urllib.error, json, os, argparse
import dst_model as M

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ESPN_SB = 'https://cdn.espn.com/core/nfl/scoreboard?xhr=1'


def _get(url, headers=None):
    h = {'User-Agent': 'Mozilla/5.0'}
    if headers:
        h.update(headers)
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h)))


# ---------------------------------------------------------------- schedule (future weeks)
def scoreboard(week, season):
    """{team: ('vs X'/'@X', opp_abbrev)} for a week, from ESPN's public CDN (no auth)."""
    d = _get(f'{ESPN_SB}&week={week}&year={season}&seasontype=2').get('content', {}).get('sbData', {})
    out = {}
    for e in d.get('events', []):
        comp = e['competitions'][0]
        m = {c['homeAway']: M.norm(c['team']['abbreviation']) for c in comp['competitors']}
        home, away = m.get('home'), m.get('away')
        if home and away:
            out[home] = ('vs ' + away, away)
            out[away] = ('@' + home, home)
    return out


# ------------------------------------------------------------------- league scoring rules
def gg_score(p, _s):
    pts = p['sack']*2 + p['int']*2 + p['ff']*2 + p['fum_rec']*1 + p['safe']*7 + \
          p['def_td']*6 + p['blk_kick']*2
    pts += 10 * M.prob_shutout(p['pts_allow'])          # GG's only points-allowed element
    return pts


DYN_PA = [(0,0,5),(1,6,4),(7,13,3),(14,20,1),(21,27,0),(28,34,-1),(35,None,-4)]
DYN_YD = [(0,99,5),(100,199,3),(200,299,2),(300,349,0),(350,399,-1),
          (400,449,-3),(450,499,-5),(500,549,-6),(550,None,-7)]

def dyn_score(p, _s):
    pts = p['sack']*1 + p['int']*2 + p['ff']*1 + p['fum_rec']*2 + p['safe']*2 + \
          p['def_td']*6 + p['blk_kick']*2
    pts += M.tier_points(p['pts_allow'], DYN_PA, sd=9.0)
    pts += M.tier_points(p['yds_allow'], DYN_YD, sd=55.0)
    return pts


ESPN_PA = [(0,0,5),(1,6,4),(7,13,3),(14,17,1),(18,None,0)]
ESPN_YD = [(0,99,5),(100,199,3),(200,299,2),(300,None,0)]

def glorp_score(p, _s):
    pts = p['sack']*1 + p['int']*2 + p['fum_rec']*2 + p['safe']*2 + \
          p['def_td']*6 + p['blk_kick']*2            # ESPN GLORP doesn't score forced fumbles
    pts += M.tier_points(p['pts_allow'], ESPN_PA, sd=9.0)
    pts += M.tier_points(p['yds_allow'], ESPN_YD, sd=55.0)
    return pts


# ------------------------------------------------------------ availability + my roster
def gg_rosters(cfg):
    r = _get(f"https://www.fleaflicker.com/api/FetchLeagueRosters?sport=NFL&league_id={cfg['id']}")
    owned, mine = set(), set()
    for ro in r['rosters']:
        tname = (ro.get('team') or {}).get('name', '')
        defs = {M.norm(pl.get('proPlayer', {}).get('proTeamAbbreviation'))
                for pl in ro.get('players', [])
                if pl.get('proPlayer', {}).get('position') == 'D/ST'}
        defs.discard('')
        owned |= defs
        if tname.lower() == cfg['team'].lower():
            mine |= defs
    return owned, mine


def dyn_rosters(cfg):
    users = _get(f"https://api.sleeper.app/v1/league/{cfg['id']}/users")
    my_id = next((u['user_id'] for u in users
                  if u.get('display_name', '').lower() == cfg['team'].lower()), None)
    owned, mine = set(), set()
    for ro in _get(f"https://api.sleeper.app/v1/league/{cfg['id']}/rosters"):
        defs = {M.norm(pid) for pid in (ro.get('players') or []) if M.norm(pid) in M.ALL_TEAMS}
        owned |= defs
        if ro.get('owner_id') == my_id:
            mine |= defs
    return owned, mine


_PROTEAM = {1:'ATL',2:'BUF',3:'CHI',4:'CIN',5:'CLE',6:'DAL',7:'DEN',8:'DET',9:'GB',10:'TEN',
            11:'IND',12:'KC',13:'LV',14:'LAR',15:'MIA',16:'MIN',17:'NE',18:'NO',19:'NYG',
            20:'NYJ',21:'PHI',22:'ARI',23:'PIT',24:'LAC',25:'SF',26:'SEA',27:'TB',28:'WAS',
            29:'CAR',30:'JAX',33:'BAL',34:'HOU'}

def _espn_cookies():
    s2, swid = os.environ.get('ESPN_S2'), os.environ.get('ESPN_SWID')
    if s2 and swid:
        return s2, swid
    path = os.path.join(SCRIPTS, '.espn_cookies.json')
    if os.path.exists(path):
        c = json.load(open(path, encoding='utf-8'))
        return c['espn_s2'], c['SWID']
    raise SystemExit("No ESPN cookies (set ESPN_S2/ESPN_SWID or create .espn_cookies.json).")


def glorp_rosters(cfg):
    s2, swid = _espn_cookies()
    url = (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/"
           f"segments/0/leagues/{cfg['id']}?view=mTeam&view=mRoster")
    try:
        d = _get(url, {'Cookie': f'espn_s2={s2}; SWID={swid}'})
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise SystemExit(f"ESPN auth failed ({e.code}) - refresh .espn_cookies.json.")
        raise
    owned, mine = set(), set()
    for t in d.get('teams', []):
        name = (t.get('name') or f"{t.get('location','')} {t.get('nickname','')}").strip()
        defs = {_PROTEAM.get(e['playerPoolEntry']['player'].get('proTeamId'))
                for e in (t.get('roster') or {}).get('entries', [])
                if e['playerPoolEntry']['player'].get('defaultPositionId') == 16}
        defs.discard(None)
        owned |= defs
        if name.lower() == cfg['team'].lower():
            mine |= defs
    return owned, mine


# def_weight: how much the defense's OWN form tilts the (opponent-driven) projection.
# Backtest-tuned per league - ~0 for GG (it barely scores points/yards allowed, so a
# defense's quality doesn't transfer), higher where points+yards allowed are scored heavily.
LEAGUES = {
    'gg':      {'name': 'Gridiron Grind (Fleaflicker)', 'id': '78455', 'team': 'CRANKY',
                'score': gg_score, 'rosters': gg_rosters, 'def_weight': 0.0},
    'dynasty': {'name': 'DyNasty (Sleeper)', 'id': '1358499663992348672', 'team': 'IanPooHead',
                'score': dyn_score, 'rosters': dyn_rosters, 'def_weight': 0.4},
    'glorp':   {'name': 'Eat GLORP (ESPN)', 'id': '686982204', 'team': 'Eat GLORP',
                'score': glorp_score, 'rosters': glorp_rosters, 'def_weight': 0.3},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--league', required=True, choices=LEAGUES)
    ap.add_argument('--week', type=int, default=0, help='first week to show (default: current)')
    ap.add_argument('--ahead', type=int, default=2, help='extra weeks to look ahead')
    ap.add_argument('--lookback', type=int, default=6, help='completed weeks of form to use')
    ap.add_argument('--half-life', type=float, default=2.5, help='recency half-life (weeks)')
    ap.add_argument('--all', action='store_true', help='show every available D, not just top 5')
    args = ap.parse_args()
    cfg = LEAGUES[args.league]

    cur, season = M.current_week()
    start = args.week or cur
    weeks = list(range(start, start + args.ahead + 1))

    # Model is built from weeks BEFORE the first one we're projecting, in this league's scoring.
    model = M.build(season, start - 1, cfg['score'], lookback=args.lookback,
                    half_life=args.half_life, def_weight=cfg['def_weight'])
    owned, mine = cfg['rosters'](cfg)
    available = M.ALL_TEAMS - owned
    sched = {w: scoreboard(w, season) for w in weeks}

    def proj_pts(team, w):
        mu = sched[w].get(team)
        if not mu:
            return None                                   # bye
        return M.project(model, team, mu[1])             # already in league points

    print(f"{cfg['name']} D/ST - weeks {weeks}, season {season}. OWN projection: "
          f"opponent generosity, recency-weighted + SOS-adjusted (model from weeks "
          f"{model['weeks']}, def_weight {cfg['def_weight']}).")
    print("Heads up: weekly D/ST is mostly noise (backtest r~.1-.22) - this picks the better "
          "side of a coin flip. Swapping a D is free, so stream the top available each week.\n")

    def ranked(w):
        c = [(proj_pts(t, w), t) for t in available if sched[w].get(t)]
        return sorted(((p, t) for p, t in c if p is not None), reverse=True)

    topN, keep = {}, (99 if args.all else 5)
    print('=== BEST AVAILABLE EACH WEEK (grab the top play before rivals do) ===')
    for w in weeks:
        r = ranked(w)[:keep]
        topN[w] = [t for _, t in r]
        print(f"  Wk{w}: " + ' | '.join(f"{t} {p:.1f} {sched[w][t][0]}" for p, t in r))

    import collections
    appear = collections.Counter(t for w in weeks for t in topN[w][:5])
    holds = sorted((t for t, n in appear.items() if n >= 2),
                   key=lambda t: -sum(proj_pts(t, w) or 0 for w in weeks if t in topN[w]))
    if holds:
        print('\n=== MULTI-WEEK HOLDS (top-5 in 2+ of these weeks - grab and keep) ===')
        for t in holds:
            wl = ', '.join(f"Wk{w} {proj_pts(t, w):.1f}" for w in weeks if sched[w].get(t))
            print(f"  {t:<4} {wl}")

    if mine:
        print('\n=== YOUR ROSTERED D/ST (for comparison) ===')
        for t in sorted(mine, key=lambda t: -sum(proj_pts(t, w) or 0 for w in weeks)):
            cells = []
            for w in weeks:
                p = proj_pts(t, w)
                mu = sched[w].get(t, ('bye', None))[0]
                cells.append(f"{mu} {'-' if p is None else f'{p:.1f}'}")
            print(f"  {t:<4} " + '  |  '.join(cells))


if __name__ == '__main__':
    main()
