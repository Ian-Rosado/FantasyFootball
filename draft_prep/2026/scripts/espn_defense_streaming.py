#!/usr/bin/env python3
"""Eat GLORP (ESPN, private league) defense-streaming helper - multi-week, projection-ranked.

Shows AVAILABLE D/STs (and your own) with ESPN's PROJECTED points for this week and
the next 1-2 - in THIS league's scoring - alongside each week's opponent. Ranks by
total projected points across the window, so the payoff is the lookahead: spotting a
defense worth grabbing now not because it's the top play this week, but because it has
the best run of matchups over the next couple weeks (grab it before rivals do).

Availability: the league's rosters (mRoster) -> every rostered D/ST's pro team, subtracted
from the 32 NFL teams. Projections + opponents: ESPN's kona_player_info (per week) and the
public CDN scoreboard. Private league, so reads need your espn_s2 + SWID cookies - see
load_cookies() (env vars or a git-ignored .espn_cookies.json).

Note: unlike the Fleaflicker/Sleeper defense scripts (which flag opponents from a
hand-maintained TARGETS list), this one uses ESPN's real weekly projections - more
accurate, and the reason it lives only on the ESPN side (ESPN uniquely exposes them).

Usage:  python espn_defense_streaming.py [--week N] [--ahead 2]
Std-lib only (urllib/json).
"""
import urllib.request, urllib.error, json, os, argparse

LEAGUE_ID = '686982204'
SEASON    = 2026
MY_TEAM   = 'Eat GLORP'
SCRIPTS   = os.path.dirname(os.path.abspath(__file__))
BASE      = f'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/segments/0/leagues/{LEAGUE_ID}'
ESPN_SB   = 'https://cdn.espn.com/core/nfl/scoreboard?xhr=1'

PROTEAM = {1:'ATL',2:'BUF',3:'CHI',4:'CIN',5:'CLE',6:'DAL',7:'DEN',8:'DET',9:'GB',
           10:'TEN',11:'IND',12:'KC',13:'LV',14:'LAR',15:'MIA',16:'MIN',17:'NE',
           18:'NO',19:'NYG',20:'NYJ',21:'PHI',22:'ARI',23:'PIT',24:'LAC',25:'SF',
           26:'SEA',27:'TB',28:'WSH',29:'CAR',30:'JAX',33:'BAL',34:'HOU'}
ALL_TEAMS = set(PROTEAM.values())


def load_cookies():
    s2, swid = os.environ.get('ESPN_S2'), os.environ.get('ESPN_SWID')
    if s2 and swid:
        return s2, swid
    path = os.path.join(SCRIPTS, '.espn_cookies.json')
    if os.path.exists(path):
        c = json.load(open(path, encoding='utf-8'))
        return c['espn_s2'], c['SWID']
    raise SystemExit("No ESPN cookies. Set ESPN_S2 + ESPN_SWID env vars, or create "
                     f"{path} (copy .espn_cookies.example.json). Private-league reads need them.")


def espn_get(url, xff=None):
    s2, swid = load_cookies()
    h = {'User-Agent': 'Mozilla/5.0', 'Cookie': f'espn_s2={s2}; SWID={swid}'}
    if xff:
        h['X-Fantasy-Filter'] = json.dumps(xff)
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h)))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise SystemExit(f"ESPN auth failed ({e.code}). Your espn_s2/SWID cookies are likely "
                             "expired - grab fresh ones from the browser and update .espn_cookies.json.")
        raise


def cdn_get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})))


def owned_and_mine():
    d = espn_get(BASE + '?view=mTeam&view=mRoster')
    owned, mine = set(), set()
    for t in d.get('teams', []):
        name = (t.get('name') or f"{t.get('location','')} {t.get('nickname','')}").strip()
        defs = {PROTEAM.get(e['playerPoolEntry']['player'].get('proTeamId'))
                for e in (t.get('roster') or {}).get('entries', [])
                if e['playerPoolEntry']['player'].get('defaultPositionId') == 16}
        defs.discard(None)
        owned |= defs
        if name.lower() == MY_TEAM.lower():
            mine |= defs
    return owned, mine


def scoreboard(week):
    d = cdn_get(f'{ESPN_SB}&week={week}&year={SEASON}&seasontype=2')
    out = {}
    for e in d.get('content', {}).get('sbData', {}).get('events', []):
        m = {c['homeAway']: c['team']['abbreviation'] for c in e['competitions'][0]['competitors']}
        home, away = m.get('home'), m.get('away')
        if home and away:
            out[home], out[away] = 'vs ' + away, '@' + home
    return out


def projections(week):
    """{team_abbrev: projected fantasy points} for a week, in this league's scoring."""
    xff = {'players': {'filterStatus': {'value': ['ONTEAM', 'FREEAGENT', 'WAIVERS']},
                       'filterSlotIds': {'value': [16]}, 'limit': 50,
                       'sortPercOwned': {'sortAsc': False, 'sortPriority': 1}}}
    d = espn_get(BASE + f'?view=kona_player_info&scoringPeriodId={week}', xff)
    out = {}
    for pe in d.get('players', []):
        p = pe['player']
        ab = PROTEAM.get(p.get('proTeamId'))
        if ab is None:
            continue
        for s in p.get('stats', []):
            if s.get('scoringPeriodId') == week and s.get('statSourceId') == 1:
                out[ab] = s.get('appliedTotal')
    return out


def detect_week():
    d = cdn_get(ESPN_SB).get('content', {}).get('sbData', {})
    n = (d.get('week') or {}).get('number', 1)
    evs = d.get('events', [])
    done = evs and all(e['competitions'][0].get('status', {}).get('type', {}).get('completed')
                       for e in evs if e.get('competitions'))
    return n + 1 if done else n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week', type=int, default=0, help='first week to show (default: auto)')
    ap.add_argument('--ahead', type=int, default=2, help='extra weeks to look ahead')
    args = ap.parse_args()

    start = args.week or detect_week()
    weeks = list(range(start, start + args.ahead + 1))

    owned, mine = owned_and_mine()
    available = ALL_TEAMS - owned
    sb = {w: scoreboard(w) for w in weeks}
    pr = {w: projections(w) for w in weeks}

    def onbye(w, t):
        return t not in sb[w]

    def cell(w, t):
        if onbye(w, t):
            return f"{'bye':<7}{'':>5}"
        p = pr[w].get(t)
        return f"{sb[w][t]:<7}{('-' if p is None else f'{p:.1f}'):>5}"

    def total(t):
        return sum(pr[w].get(t) or 0 for w in weeks if not onbye(w, t))

    hdr = 'D/ST  ' + '  '.join(f'{("Wk"+str(w)):<12}' for w in weeks) + '  Total'
    print(f"Eat GLORP (ESPN) D/ST - weeks {weeks}, season {SEASON}. ESPN projected pts "
          f"(this league's scoring) + opponent; ranked by total across the window.\n")

    print('=== AVAILABLE D/ST (best total projected first) ===')
    print(hdr)
    avail_sorted = sorted(available, key=lambda t: -total(t))
    for t in avail_sorted:
        print(f"{t:<5} " + '  '.join(cell(w, t) for w in weeks) + f"  {total(t):5.1f}")

    if mine:
        print('\n=== YOUR ROSTERED D/ST ===')
        print(hdr)
        for t in sorted(mine, key=lambda t: -total(t)):
            print(f"{t:<5} " + '  '.join(cell(w, t) for w in weeks) + f"  {total(t):5.1f}")

    # Lookahead: the this-week best vs the best over the window, and each later week's best.
    def best_avail(w):
        cands = [(pr[w].get(t), t) for t in available if not onbye(w, t) and pr[w].get(t) is not None]
        return max(cands) if cands else (None, None)

    print('\n=== LOOKAHEAD ===')
    tw_p, tw_t = best_avail(start)
    print(f"  Best available THIS week (Wk{start}): {tw_t} ({tw_p:.1f})")
    print(f"  Best available by {len(weeks)}-week total: {avail_sorted[0]} ({total(avail_sorted[0]):.1f})")
    for w in weeks[1:]:
        p, t = best_avail(w)
        if t:
            print(f"  Best available Wk{w}: {t} ({p:.1f})  [{sb[w].get(t,'bye')}]")
    if avail_sorted[0] != tw_t:
        print(f"  -> {avail_sorted[0]} isn't the top Week {start} play but has the best run - "
              f"a grab-ahead if you can hold it.")


if __name__ == '__main__':
    main()
