#!/usr/bin/env python3
"""Gridiron Grind (Fleaflicker) defense-streaming helper — multi-week.

Shows which D/STs are AVAILABLE in the league (32 NFL defenses minus every one
already rostered) alongside their matchup THIS week and the next 1-2 weeks, so you
can both stream now and grab a defense with a good upcoming matchup before rivals do.

Two cheap data sources (std-lib only), instead of paginating the whole FA pool
(which trips the Fleaflicker API rate limit):
  * availability  -> Fleaflicker FetchLeagueRosters   (1 call)
  * schedule      -> ESPN public CDN scoreboard        (1 call per week shown)

Scoring note: this league scores NO points/yards allowed (only a shutout bonus),
so stream for SACKS + TURNOVERS + defensive TDs. Target sack-prone O-lines and
turnover-prone QBs. The opponent-quality flag (*) below is a HAND-MAINTAINED list
(ATTACK_OFFENSES) — the schedule is fully live, but that list must be refreshed
from current data (Week 1-2: eye test + who's giving up sacks/turnovers). It is a
tilt, not gospel.

Usage:  python defense_streaming.py [--week N] [--ahead 2] [--top 0]
        --week   first week to show (default: auto-detect the upcoming week)
        --ahead  extra weeks to look ahead (default 2)
"""
import urllib.request, urllib.error, json, time, argparse

LEAGUE_ID = '78455'
SEASON    = 2026
FL_BASE   = 'https://www.fleaflicker.com/api'
ESPN_SB   = 'https://cdn.espn.com/core/nfl/scoreboard?xhr=1&year={yr}&seasontype=2&week={wk}'

ALL_TEAMS = {'ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB',
             'HOU','IND','JAC','KC','LAC','LAR','LV','MIA','MIN','NE','NO','NYG','NYJ',
             'PHI','PIT','SEA','SF','TB','TEN','WAS'}
ESPN_FIX  = {'WSH': 'WAS', 'JAX': 'JAC'}   # ESPN abbrev -> Fleaflicker abbrev

# Sack-/turnover-prone offenses to ATTACK. HAND-MAINTAINED HEURISTIC — refresh
# every couple weeks from current data (sacks allowed, giveaways, bad QB play).
# Seeded from 2026 Week 1-2 reality (e.g. Cleveland/Watson = 5 sacks + INT in Wk1).
ATTACK_OFFENSES = {'CLE', 'CAR', 'NO', 'NYG', 'NYJ', 'TEN', 'LV'}


def fl_api(path):
    """Fleaflicker call with a short backoff (few calls now, so this rarely trips)."""
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(FL_BASE + path, headers={'User-Agent': 'Mozilla/5.0'})
            return json.load(urllib.request.urlopen(req))
        except urllib.error.URLError as e:
            last = e
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f"Fleaflicker API unavailable ({last}). Wait ~a minute (rate limit) and retry.")


def espn_get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})))


def rostered_defenses():
    r = fl_api(f'/FetchLeagueRosters?sport=NFL&league_id={LEAGUE_ID}')
    out = set()
    for ro in r['rosters']:
        for pl in ro.get('players', []):
            pp = pl.get('proPlayer', {})
            if pp.get('position') == 'D/ST':
                out.add(pp.get('proTeamAbbreviation'))
    return out


def scoreboard(week):
    """Return {team: (matchup_str, opponent)} for one week, plus whether it's all final."""
    sb = espn_get(ESPN_SB.format(yr=SEASON, wk=week))
    d = sb.get('content', {}).get('sbData', {})
    games, all_final = {}, True
    for ev in d.get('events', []):
        comp = ev['competitions'][0]
        st = comp.get('status', {}).get('type', {}).get('completed')
        if not st:
            all_final = False
        home = next(t for t in comp['competitors'] if t['homeAway'] == 'home')
        away = next(t for t in comp['competitors'] if t['homeAway'] == 'away')
        ha = ESPN_FIX.get(home['team']['abbreviation'], home['team']['abbreviation'])
        aa = ESPN_FIX.get(away['team']['abbreviation'], away['team']['abbreviation'])
        games[ha] = ('vs ' + aa, aa)
        games[aa] = ('@' + ha, ha)
    return games, all_final


def detect_week():
    """Upcoming week: ESPN's current week, advanced by 1 if that week is already complete."""
    sb = espn_get('https://cdn.espn.com/core/nfl/scoreboard?xhr=1')
    d = sb.get('content', {}).get('sbData', {})
    n = (d.get('week') or {}).get('number', 1)
    done = all(e['competitions'][0].get('status', {}).get('type', {}).get('completed')
               for e in d.get('events', []) if e.get('competitions'))
    return n + 1 if (done and d.get('events')) else n


def cell(games, team):
    mu, opp = games.get(team, ('bye', None))
    star = '*' if opp in ATTACK_OFFENSES else ' '
    return f"{mu:<7}{star}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week', type=int, default=0, help='first week to show (default: auto)')
    ap.add_argument('--ahead', type=int, default=2, help='extra weeks to look ahead')
    args = ap.parse_args()

    start = args.week or detect_week()
    weeks = list(range(start, start + args.ahead + 1))

    rostered = rostered_defenses()
    available = sorted(ALL_TEAMS - rostered)
    sched = {w: scoreboard(w)[0] for w in weeks}

    print(f"League 78455 - showing weeks {weeks} (season {SEASON}).  * = opponent is a "
          f"sack/turnover-prone offense (hand-maintained list).")
    print(f"Rostered D/STs ({len(rostered)}): {' '.join(sorted(rostered))}\n")

    hdr = 'D/ST  ' + '  '.join(f'Wk{w:<6}' for w in weeks)
    print('=== AVAILABLE D/ST - matchup grid ===')
    print(hdr)
    # sort so defenses with the most attackable matchups across the window float up
    def score(team):
        return -sum(1 for w in weeks if sched[w].get(team, ('', None))[1] in ATTACK_OFFENSES)
    for team in sorted(available, key=lambda t: (score(t), t)):
        row = '  '.join(cell(sched[w], team) for w in weeks)
        print(f"{team:<5} {row}")

    # Pre-emptive pickups: available now, and a starred matchup in a LATER week
    later = weeks[1:]
    preempt = [t for t in available
               if any(sched[w].get(t, ('', None))[1] in ATTACK_OFFENSES for w in later)]
    if preempt:
        print('\n=== GRAB-AHEAD: available now, good matchup in an upcoming week ===')
        for t in preempt:
            hits = [f"Wk{w} {sched[w][t][0]}" for w in later
                    if sched[w].get(t, ('', None))[1] in ATTACK_OFFENSES]
            print(f"  {t:<4} {', '.join(hits)}")


if __name__ == '__main__':
    main()
