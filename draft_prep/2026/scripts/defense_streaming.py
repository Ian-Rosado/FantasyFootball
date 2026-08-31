#!/usr/bin/env python3
"""Gridiron Grind (Fleaflicker) defense-streaming helper.

Lists the D/STs currently on the wire with their upcoming matchup + ownership.

Scoring note: this league scores NO points/yards allowed (only a shutout bonus),
so stream for SACKS + TURNOVERS + defensive TDs. Target sack-prone O-lines and
turnover-prone QBs (see TARGETS), and favor blitz-heavy, ball-hawking units.

The Fleaflicker player listing only exposes the CURRENT week's game, so for
multi-week planning cross-reference the NFL schedule. Re-run each week.

Usage:  python defense_streaming.py
"""
import urllib.request, json, time

LEAGUE_ID = '78455'
BASE = 'https://www.fleaflicker.com/api'
# sack- / turnover-prone offenses to attack (revisit with real data after ~Week 4)
TARGETS = {'LV', 'CLE', 'CHI', 'NO', 'CAR', 'TEN', 'NYG', 'NYJ', 'ARI'}

import urllib.error
def api(path):
    last = None
    for attempt in range(4):                       # retry w/ backoff: the public API rate-limits rapid calls
        try:
            req = urllib.request.Request(BASE + path, headers={'User-Agent': 'Mozilla/5.0'})
            return json.load(urllib.request.urlopen(req))
        except urllib.error.URLError as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"Fleaflicker API unavailable ({last}). If you ran this several times in a row, "
                     "wait ~a minute (rate limit) and retry.")

def opponent(games, team):
    for g in games or []:
        gm = g.get('game', {})
        away = gm.get('away', {}).get('abbreviation')
        home = gm.get('home', {}).get('abbreviation')
        if away == team:
            return '@' + home, home
        if home == team:
            return 'vs ' + away, away
    return 'bye', None

def main():
    rows, off = [], 0
    while True:
        d = api(f'/FetchPlayerListing?sport=NFL&league_id={LEAGUE_ID}'
                f'&filter.freeAgentOnly=true&sort=SORT_DRAFT_RANKING&result_offset={off}')
        pl = d.get('players', [])
        for p in pl:
            pp = p['proPlayer']
            if pp['position'] == 'D/ST':
                matchup, opp_team = opponent(p.get('requestedGames'), pp['proTeamAbbreviation'])
                rows.append((pp['proTeamAbbreviation'], matchup, opp_team,
                             round(pp.get('percentOwnedRatio', 0) * 100)))
        off = d.get('resultOffsetNext')
        if not off or not pl:
            break

    print('=== AVAILABLE D/ST — this week ===   (* faces a sack/turnover-prone offense)')
    for team, matchup, opp_team, owned in sorted(rows, key=lambda x: -x[3]):
        star = '  * TARGET' if opp_team in TARGETS else ''
        print(f"{team:<4} {matchup:<9} owned {owned:>3}%{star}")

if __name__ == '__main__':
    main()
