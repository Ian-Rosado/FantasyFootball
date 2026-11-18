#!/usr/bin/env python3
"""Gridiron Grind (Fleaflicker) high-score finder — every big team-week in league history.

Scans every scoring period of every season (REGULAR SEASON + POSTSEASON) on the
Fleaflicker league and lists every team-week at or above a point THRESHOLD, with the
full starting lineup and points-by-player for each one.

Fleaflicker is where all of Gridiron Grind's actual matchups/scoring live for EVERY
year (league 78455) — the 2023 move to ESPN was only the auction draft, so the scoring
history is one continuous Fleaflicker record from 2009 to the current season.

One cheap data source (std-lib only, public API, no auth):
  * team-week totals  -> FetchLeagueScoreboard  (1 call per season-week; detects hits)
  * starting lineups  -> FetchLeagueBoxscore     (1 call per qualifying team-week)

200 is a genuinely rare bar in this league (full PPR, 9 starters, ~130/wk average).
As of the 2026 season there have been three: GERK 200.5 (2022 Wk8), Bijannaise 224.25
(2024 Wk17, playoffs), Mr. Kim's Kans 225.7 (2026 Wk5).

Usage:  python high_scores.py [--threshold 200] [--season N | --from 2009 --to 2026]
        --threshold   minimum team-week score to report (default 200)
        --season N    scan a single season only
        --from / --to inclusive season range (default 2009 .. current year)
        --league ID   Fleaflicker league id (default 78455 = Gridiron Grind)
        --no-rosters  list the qualifying team-weeks only, skip the player breakdowns
"""
import urllib.request, urllib.error, json, time, argparse, sys
from datetime import date

FL_BASE = 'https://www.fleaflicker.com/api'


def fl_api(path):
    """Fleaflicker call with a short backoff (the API rate-limits on rapid runs)."""
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(FL_BASE + path, headers={'User-Agent': 'gg-high-scores/1.0'})
            return json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503):
                time.sleep(2 + attempt * 2)
                continue
            raise
        except urllib.error.URLError as e:
            last = e
            time.sleep(2 + attempt * 2)
    raise SystemExit(f"Fleaflicker API unavailable ({last}). It rate-limits on rapid "
                     "repeat runs — wait a minute and try again.")


def scan_season(league, season, threshold):
    """Return a list of qualifying team-weeks for one season (all scoring periods)."""
    hits = []
    for sp in range(1, 21):
        d = fl_api(f'/FetchLeagueScoreboard?sport=NFL&league_id={league}&season={season}&scoring_period={sp}')
        games = d.get('games', [])
        if not games:
            break
        for g in games:
            gid = g.get('id')
            for side in ('home', 'away'):
                opp = 'away' if side == 'home' else 'home'
                score = (g.get(side + 'Score', {}).get('score', {}) or {}).get('value')
                if score is not None and score >= threshold:
                    hits.append({
                        'season': season, 'week': sp, 'game_id': gid, 'side': side,
                        'team': g.get(side, {}).get('name'), 'score': round(score, 2),
                        'opp': g.get(opp, {}).get('name'),
                        'opp_score': (g.get(opp + 'Score', {}).get('score', {}) or {}).get('value'),
                        'result': g.get(side + 'Result'),
                    })
        time.sleep(0.3)
    return hits


def print_lineup(league, hit):
    """Fetch the boxscore for a qualifying team-week and print its starting lineup."""
    d = fl_api(f'/FetchLeagueBoxscore?sport=NFL&league_id={league}&fantasy_game_id={hit["game_id"]}')
    side = hit['side']
    print(f'  {"SLOT":9} {"PLAYER":24} {"PTS":>7}')
    print(f'  {"-"*9} {"-"*24} {"-"*7}')
    total = 0.0
    for grp in d.get('lineups', []):
        if grp.get('group') != 'START':
            continue
        for s in grp.get('slots', []):
            pos = s['position']['label']
            cell = s.get(side)
            pp = cell.get('proPlayer') if cell else None
            pts = (cell.get('viewingActualPoints', {}) or {}).get('value') if cell else None
            name = pp['nameFull'] if pp else '(empty)'
            if pts is not None:
                total += pts
            print(f'  {pos:9} {name:24} {("%.1f" % pts) if pts is not None else "-":>7}')
    print(f'  {"":9} {"TOTAL":24} {round(total, 2):>7}')


def main():
    ap = argparse.ArgumentParser(description='Find every Gridiron Grind team-week at/above a score threshold.')
    ap.add_argument('--threshold', type=float, default=200.0, help='minimum team-week score (default 200)')
    ap.add_argument('--season', type=int, help='scan a single season only')
    ap.add_argument('--from', dest='from_season', type=int, default=2009, help='first season (default 2009)')
    ap.add_argument('--to', dest='to_season', type=int, default=date.today().year, help='last season (default current year)')
    ap.add_argument('--league', default='78455', help='Fleaflicker league id (default 78455)')
    ap.add_argument('--no-rosters', action='store_true', help='list qualifying weeks only, skip player breakdowns')
    args = ap.parse_args()

    # UTF-8 stdout so emoji/accented team names don't crash on Windows.
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    seasons = [args.season] if args.season else range(args.from_season, args.to_season + 1)

    all_hits = []
    for season in seasons:
        hits = scan_season(args.league, season, args.threshold)
        all_hits.extend(hits)
        print(f'scanned {season}: {len(hits)} week(s) >= {args.threshold:g}', file=sys.stderr)

    all_hits.sort(key=lambda h: (h['season'], h['week'], -h['score']))

    print(f'\n{"="*58}')
    print(f'  {len(all_hits)} team-week(s) scored >= {args.threshold:g}  (league {args.league})')
    print(f'{"="*58}')
    for h in all_hits:
        res = {'WIN': 'W', 'LOSE': 'L', 'TIE': 'T'}.get(h.get('result'), '?')
        opp_sc = h.get('opp_score')
        opp_sc = f'{opp_sc:g}' if opp_sc is not None else '?'
        print(f'\n{h["season"]} Week {h["week"]}  —  {h["team"]}  {h["score"]:g}  '
              f'({res} vs {h.get("opp")} {opp_sc})')
        if not args.no_rosters:
            print_lineup(args.league, h)


if __name__ == '__main__':
    main()
