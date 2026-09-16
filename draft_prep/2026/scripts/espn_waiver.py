#!/usr/bin/env python3
"""Eat GLORP (ESPN, private league) in-season waiver helper.

Shows YOUR roster + positional depth, then the best available players on the wire
ranked by ESPN's percent-rostered signal (a proxy for waiver relevance), flagging
the ones that fill a position you're thin at.

Availability comes from ESPN's free-agent filter (kona_player_info + an
X-Fantasy-Filter header for FREEAGENT/WAIVERS status). This is a PRIVATE league, so
reads need your espn_s2 + SWID cookies - see load_cookies() (env vars or a local
.espn_cookies.json, which is git-ignored).

Usage:  python espn_waiver.py [--pos RB] [--limit 25]
Std-lib only (urllib/json).
"""
import urllib.request, urllib.error, json, os, argparse

LEAGUE_ID = '686982204'
SEASON    = 2026
MY_TEAM   = 'Eat GLORP'
SCRIPTS   = os.path.dirname(os.path.abspath(__file__))
BASE      = f'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/segments/0/leagues/{LEAGUE_ID}'

POS = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'D/ST'}
PROTEAM = {1:'ATL',2:'BUF',3:'CHI',4:'CIN',5:'CLE',6:'DAL',7:'DEN',8:'DET',9:'GB',
           10:'TEN',11:'IND',12:'KC',13:'LV',14:'LAR',15:'MIA',16:'MIN',17:'NE',
           18:'NO',19:'NYG',20:'NYJ',21:'PHI',22:'ARI',23:'PIT',24:'LAC',25:'SF',
           26:'SEA',27:'TB',28:'WSH',29:'CAR',30:'JAX',33:'BAL',34:'HOU',0:'FA'}
SKILL_POS = ('QB', 'RB', 'WR', 'TE', 'K')
DEPTH_TGT = {'QB': 2, 'RB': 5, 'WR': 5, 'TE': 2, 'K': 1}   # thin = strictly below this


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


def my_roster():
    d = espn_get(BASE + '?view=mTeam&view=mRoster')
    for t in d.get('teams', []):
        name = (t.get('name') or f"{t.get('location','')} {t.get('nickname','')}").strip()
        if name.lower() == MY_TEAM.lower():
            rec = (t.get('record') or {}).get('overall') or {}
            by_pos = {}
            for e in (t.get('roster') or {}).get('entries', []):
                p = e['playerPoolEntry']['player']
                by_pos.setdefault(POS.get(p.get('defaultPositionId'), '?'), []).append(p.get('fullName'))
            return name, rec, by_pos
    raise SystemExit(f"Team {MY_TEAM!r} not found in league {LEAGUE_ID}.")


def free_agents(limit):
    xff = {"players": {"filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
                       "limit": limit, "offset": 0,
                       "sortPercOwned": {"sortAsc": False, "sortPriority": 1}}}
    d = espn_get(BASE + '?view=kona_player_info', xff)
    out = []
    for pe in d.get('players', []):
        p = pe['player']
        own = p.get('ownership') or {}
        out.append({'name': p.get('fullName'), 'pos': POS.get(p.get('defaultPositionId'), '?'),
                    'team': PROTEAM.get(p.get('proTeamId'), '?'),
                    'owned': round(own.get('percentOwned', 0), 1),
                    'trend': round(own.get('percentChange', 0), 1)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pos', help='filter available list to one position (QB/RB/WR/TE/K)')
    ap.add_argument('--limit', type=int, default=25)
    args = ap.parse_args()
    want = args.pos.upper() if args.pos else None

    name, rec, by_pos = my_roster()
    print(f"=== {name} (ESPN) - record {rec.get('wins',0)}-{rec.get('losses',0)}"
          f"{('-'+str(rec['ties'])) if rec.get('ties') else ''} ===")
    for pos in SKILL_POS + ('D/ST',):
        names = ', '.join(sorted(by_pos.get(pos, [])))
        thin = ' <-- THIN' if pos in DEPTH_TGT and len(by_pos.get(pos, [])) < DEPTH_TGT[pos] else ''
        print(f"  {pos:<5} ({len(by_pos.get(pos, []))}) {names}{thin}")
    thin_pos = {p for p in SKILL_POS if len(by_pos.get(p, [])) < DEPTH_TGT.get(p, 0)}

    hdr = f"position {want}" if want else "all skill positions"
    print(f"\n=== BEST AVAILABLE ({hdr}) - free agents by % rostered ===")
    print("  (! = fills a position you're thin at; trend = weekly change in % rostered)")
    shown = 0
    for f in free_agents(max(args.limit * 3, 60)):
        if f['pos'] not in SKILL_POS or (want and f['pos'] != want):
            continue
        flag = ' !' if f['pos'] in thin_pos else ''
        print(f"  {f['name']:<24} {f['pos']:<3} {f['team']:<4} owned {f['owned']:>5}%  "
              f"trend {f['trend']:+5.1f}{flag}")
        shown += 1
        if shown >= args.limit:
            break
    if not shown:
        print("  (none available at that filter)")


if __name__ == '__main__':
    main()
