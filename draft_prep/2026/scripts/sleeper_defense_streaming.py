#!/usr/bin/env python3
"""DyNasty (Sleeper) defense-streaming helper - multi-week, projection-ranked.

Shows AVAILABLE D/STs (and your own) with PROJECTED points for this week and the next
1-2 - computed in THIS league's exact scoring - alongside each week's opponent. Ranks by
total projected points across the window, so the payoff is the lookahead: spotting a
defense worth grabbing now for its run of upcoming matchups, not just this week's top play.

Data sources (std-lib only):
  * availability -> Sleeper rosters (a DEF's player_id IS its team code; available =
    32 teams minus every rostered DEF id).  api.sleeper.app/v1
  * projections  -> Sleeper's projections endpoint gives raw projected stat lines per DEF
    (sacks, INTs, fumbles, pts-allowed tiers, ...); we multiply by the league's
    scoring_settings to get points in DyNasty's scoring.  api.sleeper.com/projections
  * opponents    -> ESPN public CDN scoreboard (Sleeper doesn't expose the NFL schedule).

This league scores points/yards allowed heavily on top of sacks/turnovers/TDs, so the
projections (which bake all that in) are a better guide than an opponent heuristic - the
same reason the ESPN script switched to projections. Re-run each week.

Usage:  python sleeper_defense_streaming.py [--week N] [--ahead 2]
"""
import urllib.request, urllib.error, json, time, argparse

LEAGUE_ID   = '1358499663992348672'          # DyNasty (10-team, 1QB, .5 PPR, 2 FLEX)
MY_USER     = 'IanPooHead'                     # Ian = "Team L.O.B"
SLEEPER     = 'https://api.sleeper.app/v1'
SLEEPER_PROJ = 'https://api.sleeper.com/projections/nfl'
ESPN_SB     = 'https://cdn.espn.com/core/nfl/scoreboard?xhr=1'

ALL_TEAMS = {'ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET',
             'GB','HOU','IND','JAX','KC','LV','LAC','LAR','MIA','MIN','NE','NO',
             'NYG','NYJ','PHI','PIT','SEA','SF','TB','TEN','WAS'}
ESPN2SLEEPER = {'WSH': 'WAS', 'JAC': 'JAX', 'LVR': 'LV'}   # ESPN abbrev -> Sleeper abbrev


def get(url):
    last = None
    for attempt in range(4):
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
    return (st.get('week') or st.get('display_week') or 1), str(st.get('season') or '2026')


def scoring_settings():
    return get(f'{SLEEPER}/league/{LEAGUE_ID}').get('scoring_settings', {})


def owned_and_mine():
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
            out[home], out[away] = 'vs ' + away, '@' + home
    return out


def projections(week, season, scoring):
    """{team_abbrev: projected fantasy points in this league's scoring} for a week."""
    pl = get(f'{SLEEPER_PROJ}/{season}/{week}?season_type=regular&position[]=DEF')
    out = {}
    for p in pl:
        team = p.get('player_id')            # a DEF's player_id IS its team code
        stats = p.get('stats') or {}
        out[team] = sum(v * scoring[k] for k, v in stats.items() if k in scoring)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week', type=int, default=0, help='first week to show (default: auto)')
    ap.add_argument('--ahead', type=int, default=2, help='extra weeks to look ahead')
    args = ap.parse_args()

    cur_week, season = nfl_state()
    start = args.week or cur_week
    weeks = list(range(start, start + args.ahead + 1))

    scoring = scoring_settings()
    owned, mine = owned_and_mine()
    available = ALL_TEAMS - owned
    sb = {w: scoreboard(w, season) for w in weeks}
    pr = {w: projections(w, season, scoring) for w in weeks}

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
    print(f"DyNasty (Sleeper) D/ST - weeks {weeks}, season {season}. Projected pts "
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

    def best_avail(w):
        cands = [(pr[w].get(t), t) for t in available if not onbye(w, t) and pr[w].get(t) is not None]
        return max(cands) if cands else (None, None)

    print('\n=== LOOKAHEAD ===')
    tw_p, tw_t = best_avail(start)
    if tw_t:
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
