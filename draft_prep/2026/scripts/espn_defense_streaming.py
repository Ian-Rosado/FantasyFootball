#!/usr/bin/env python3
"""Eat GLORP (ESPN, private league) defense-streaming helper - multi-week.

Shows which D/STs are AVAILABLE in the league alongside their matchups for this
week and the next 1-2, plus YOUR rostered defenses' upcoming schedule, so you can
spot a rough week and grab a good streaming matchup before rivals do.

Availability: read the league's rosters (ESPN mRoster view), collect every rostered
D/ST's pro team, and subtract from the 32 NFL teams. Matchups come from ESPN's public
CDN scoreboard. This is a PRIVATE league, so reads need your espn_s2 + SWID cookies -
see load_cookies() (env vars or a local .espn_cookies.json, which is git-ignored).

Scoring note: this league scores points- and yards-allowed heavily (PA0 +5 ... plus
YA tiers) on top of sacks/turnovers/return TDs. So target good defenses facing WEAK,
LOW-SCORING offenses (* = opponent in TARGETS, a hand-maintained list to refresh).

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

# ESPN proTeamId -> abbreviation (matches the CDN scoreboard's abbreviations).
PROTEAM = {1:'ATL',2:'BUF',3:'CHI',4:'CIN',5:'CLE',6:'DAL',7:'DEN',8:'DET',9:'GB',
           10:'TEN',11:'IND',12:'KC',13:'LV',14:'LAR',15:'MIA',16:'MIN',17:'NE',
           18:'NO',19:'NYG',20:'NYJ',21:'PHI',22:'ARI',23:'PIT',24:'LAC',25:'SF',
           26:'SEA',27:'TB',28:'WSH',29:'CAR',30:'JAX',33:'BAL',34:'HOU'}
ALL_TEAMS = set(PROTEAM.values())

# Weak / low-scoring / turnover-prone offenses to attack. HAND-MAINTAINED - refresh
# from current data every couple weeks. Streaming a good D INTO one is the play.
TARGETS = {'LV', 'CLE', 'CAR', 'NO', 'TEN', 'NYG', 'NYJ', 'IND', 'ARI'}


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


def espn_get(url):
    s2, swid = load_cookies()
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0',
                                               'Cookie': f'espn_s2={s2}; SWID={swid}'})
    try:
        return json.load(urllib.request.urlopen(req))
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
        defs = set()
        for e in (t.get('roster') or {}).get('entries', []):
            p = e['playerPoolEntry']['player']
            if p.get('defaultPositionId') == 16:                 # 16 = D/ST
                ab = PROTEAM.get(p.get('proTeamId'))
                if ab:
                    defs.add(ab)
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
            out[home] = ('vs ' + away, away)
            out[away] = ('@' + home, home)
    return out


def detect_week():
    d = cdn_get(ESPN_SB).get('content', {}).get('sbData', {})
    n = (d.get('week') or {}).get('number', 1)
    evs = d.get('events', [])
    done = evs and all(e['competitions'][0].get('status', {}).get('type', {}).get('completed')
                       for e in evs if e.get('competitions'))
    return n + 1 if done else n


def cell(games, team):
    mu, opp = games.get(team, ('bye', None))
    return f"{mu:<7}{'*' if opp in TARGETS else ' '}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week', type=int, default=0, help='first week to show (default: auto)')
    ap.add_argument('--ahead', type=int, default=2, help='extra weeks to look ahead')
    args = ap.parse_args()

    start = args.week or detect_week()
    weeks = list(range(start, start + args.ahead + 1))

    owned, mine = owned_and_mine()
    available = ALL_TEAMS - owned
    sched = {w: scoreboard(w) for w in weeks}

    def weak_weeks(t):
        return sum(1 for w in weeks if sched[w].get(t, ('', None))[1] in TARGETS)

    print(f"Eat GLORP (ESPN) D/ST - weeks {weeks}, season {SEASON}.  * = opponent is a "
          f"weak/low-scoring offense (good for this league's pts/yards-allowed scoring).\n")
    hdr = 'D/ST  ' + '  '.join(f'Wk{w:<6}' for w in weeks)

    print('=== AVAILABLE D/ST - matchup grid (most good matchups first) ===')
    print(hdr)
    for team in sorted(available, key=lambda t: (-weak_weeks(t), t)):
        print(f"{team:<5} " + '  '.join(cell(sched[w], team) for w in weeks))

    if mine:
        print('\n=== YOUR ROSTERED D/ST - upcoming schedule ===')
        print(hdr)
        for team in sorted(mine):
            print(f"{team:<5} " + '  '.join(cell(sched[w], team) for w in weeks))

    later = weeks[1:]
    preempt = [t for t in sorted(available)
               if any(sched[w].get(t, ('', None))[1] in TARGETS for w in later)]
    if preempt:
        print('\n=== GRAB-AHEAD: available now, weak opponent in an upcoming week ===')
        for t in preempt:
            hits = [f"Wk{w} {sched[w][t][0]}" for w in later
                    if sched[w].get(t, ('', None))[1] in TARGETS]
            print(f"  {t:<4} " + ', '.join(hits))


if __name__ == '__main__':
    main()
