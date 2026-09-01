#!/usr/bin/env python3
"""DyNasty (Sleeper) defense-streaming helper.

Lists the D/STs currently available in the league with their upcoming matchup,
so you can stream a defense against a weak opponent each week.

Availability comes from the Sleeper public read API: a team defense's player_id
IS the team abbreviation, so "available" = all 32 teams minus every DEF id that
shows up on a roster (no need for the 5 MB /players/nfl dump).

Matchups come from ESPN's public CDN scoreboard (Sleeper doesn't expose the NFL
schedule). Re-run each week; it reads the current week from Sleeper automatically.

Scoring note: unlike Gridiron Grind, THIS league scores points- and yards-allowed
heavily (shutout +5, and a sliding scale down to -4 for 35+ pts / -7 for 550+ yds),
on top of sacks/turnovers/TDs. So target good defenses facing WEAK, LOW-SCORING,
turnover-prone offenses (see TARGETS) — game script matters as much as the D itself.

Usage:  python sleeper_defense_streaming.py
Std-lib only (urllib/json).
"""
import urllib.request, urllib.error, json, time

LEAGUE_ID = '1358499663992348672'          # DyNasty (10-team, 1QB, .5 PPR, 2 FLEX)
SLEEPER   = 'https://api.sleeper.app/v1'
ESPN_SB   = 'https://cdn.espn.com/core/nfl/scoreboard?xhr=1'

ALL_TEAMS = {'ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET',
             'GB','HOU','IND','JAX','KC','LV','LAC','LAR','MIA','MIN','NE','NO',
             'NYG','NYJ','PHI','PIT','SEA','SF','TB','TEN','WAS'}

# ESPN uses a few different abbreviations than Sleeper -> normalize ESPN -> Sleeper.
ESPN2SLEEPER = {'WSH': 'WAS', 'JAC': 'JAX', 'LVR': 'LV'}

# Weak / low-scoring / turnover-prone offenses to attack (revisit with real data
# after ~Week 4). Streaming a good D INTO one of these is the play.
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


def current_week():
    st = get(f'{SLEEPER}/state/nfl')
    # in-season use 'week'; during the preseason 'week' can be 0, so fall back to 1
    return st.get('week') or st.get('display_week') or 1, st.get('season')


def owned_defenses():
    rosters = get(f'{SLEEPER}/league/{LEAGUE_ID}/rosters')
    owned = set()
    for r in rosters:
        for pid in (r.get('players') or []):
            if pid in ALL_TEAMS:                      # a DEF's player_id is its team code
                owned.add(pid)
    return owned


def matchups(week, season):
    d = get(f'{ESPN_SB}&week={week}&year={season}&seasontype=2')
    out = {}
    for e in d.get('content', {}).get('sbData', {}).get('events', []):
        comp = e['competitions'][0]['competitors']
        m = {c['homeAway']: norm(c['team']['abbreviation']) for c in comp}
        home, away = m.get('home'), m.get('away')
        if home and away:
            out[home] = ('vs ' + away, away)
            out[away] = ('@' + home, home)
    return out


def main():
    week, season = current_week()
    owned = owned_defenses()
    avail = sorted(ALL_TEAMS - owned)
    games = matchups(week, season)

    print(f"=== AVAILABLE D/ST - Week {week} {season} ===   (* faces a weak/low-scoring offense)")
    rows = []
    for tm in avail:
        matchup, opp = games.get(tm, ('bye', None))
        rows.append((tm, matchup, opp))
    # bye teams last, then TARGET matchups first, then alphabetical
    for tm, matchup, opp in sorted(rows, key=lambda x: (x[1] == 'bye', opp_rank(x[2]), x[0])):
        star = '  * TARGET' if opp in TARGETS else ''
        print(f"{tm:<4} {matchup:<9}{star}")

    onbye = [tm for tm, matchup, _ in rows if matchup == 'bye']
    if onbye:
        print(f"\n(on bye this week: {', '.join(onbye)})")


def opp_rank(opp):
    return 0 if opp in TARGETS else 1


if __name__ == '__main__':
    main()
