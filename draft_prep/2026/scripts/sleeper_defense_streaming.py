#!/usr/bin/env python3
"""DyNasty (Sleeper) defense-streaming helper - multi-week.

Shows which D/STs are AVAILABLE in the league alongside their matchups for this
week and the next 1-2, plus YOUR rostered defenses' upcoming schedule, so you can
spot a rough week and grab a good streaming matchup before rivals do.

Availability comes from the Sleeper public read API: a team defense's player_id
IS the team abbreviation, so "available" = all 32 teams minus every DEF id that
shows up on a roster (no need for the 5 MB /players/nfl dump). Matchups come from
ESPN's public CDN scoreboard (Sleeper doesn't expose the NFL schedule).

Scoring note: unlike Gridiron Grind, THIS league scores points- and yards-allowed
heavily (shutout +5, sliding down to -4 for 35+ pts / -7 for 550+ yds), on top of
sacks/turnovers/TDs. So target good defenses facing WEAK, LOW-SCORING, turnover-prone
offenses (* = opponent is in TARGETS) - game script matters as much as the D itself.
TARGETS is a hand-maintained list; refresh it from current data every couple weeks.

Usage:  python sleeper_defense_streaming.py [--week N] [--ahead 2]
        --week   first week to show (default: auto-detect from Sleeper)
        --ahead  extra weeks to look ahead (default 2)
Std-lib only (urllib/json).
"""
import urllib.request, urllib.error, json, time, argparse

LEAGUE_ID = '1358499663992348672'          # DyNasty (10-team, 1QB, .5 PPR, 2 FLEX)
MY_USER   = 'IanPooHead'                     # Ian = "Team L.O.B"
SLEEPER   = 'https://api.sleeper.app/v1'
ESPN_SB   = 'https://cdn.espn.com/core/nfl/scoreboard?xhr=1'

ALL_TEAMS = {'ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET',
             'GB','HOU','IND','JAX','KC','LV','LAC','LAR','MIA','MIN','NE','NO',
             'NYG','NYJ','PHI','PIT','SEA','SF','TB','TEN','WAS'}

# ESPN uses a few different abbreviations than Sleeper -> normalize ESPN -> Sleeper.
ESPN2SLEEPER = {'WSH': 'WAS', 'JAC': 'JAX', 'LVR': 'LV'}

# Weak / low-scoring / turnover-prone offenses to attack. HAND-MAINTAINED HEURISTIC -
# refresh from current data every couple weeks. Streaming a good D INTO one is the play.
TARGETS = {'LV', 'CLE', 'CAR', 'NO', 'TEN', 'NYG', 'NYJ', 'IND', 'ARI'}


def get(url):
    last = None
    for attempt in range(4):                          # retry w/ backoff for transient failures
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            return json.load(urllib.request.urlopen(req))
        except urllib.error.URLError as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"API unavailable ({last}). If you re-ran this several times, wait a minute and retry.")


def norm(ab):
    return ESPN2SLEEPER.get(ab, ab)


def nfl_state():
    st = get(f'{SLEEPER}/state/nfl')
    # in-season use 'week'; during the preseason 'week' can be 0, so fall back to 1
    return (st.get('week') or st.get('display_week') or 1), st.get('season')


def owned_and_mine():
    """Return (all owned DEF team codes, set of MY rostered DEF team codes)."""
    users = get(f'{SLEEPER}/league/{LEAGUE_ID}/users')
    my_id = next((u['user_id'] for u in users
                  if u.get('display_name', '').lower() == MY_USER.lower()), None)
    owned, mine = set(), set()
    for r in get(f'{SLEEPER}/league/{LEAGUE_ID}/rosters'):
        defs = {pid for pid in (r.get('players') or []) if pid in ALL_TEAMS}
        owned |= defs
        if r.get('owner_id') == my_id:
            mine |= defs
    return owned, mine


def scoreboard(week, season):
    d = get(f'{ESPN_SB}&week={week}&year={season}&seasontype=2')
    out = {}
    for e in d.get('content', {}).get('sbData', {}).get('events', []):
        m = {c['homeAway']: norm(c['team']['abbreviation']) for c in e['competitions'][0]['competitors']}
        home, away = m.get('home'), m.get('away')
        if home and away:
            out[home] = ('vs ' + away, away)
            out[away] = ('@' + home, home)
    return out


def cell(games, team):
    mu, opp = games.get(team, ('bye', None))
    return f"{mu:<7}{'*' if opp in TARGETS else ' '}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week', type=int, default=0, help='first week to show (default: auto)')
    ap.add_argument('--ahead', type=int, default=2, help='extra weeks to look ahead')
    args = ap.parse_args()

    cur_week, season = nfl_state()
    start = args.week or cur_week
    weeks = list(range(start, start + args.ahead + 1))

    owned, mine = owned_and_mine()
    available = ALL_TEAMS - owned
    sched = {w: scoreboard(w, season) for w in weeks}

    def weak_weeks(team):
        return sum(1 for w in weeks if sched[w].get(team, ('', None))[1] in TARGETS)

    print(f"DyNasty (Sleeper) D/ST - weeks {weeks}, season {season}.  * = opponent is a "
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
