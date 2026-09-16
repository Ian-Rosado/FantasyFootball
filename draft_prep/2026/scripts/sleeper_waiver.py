#!/usr/bin/env python3
"""DyNasty (Sleeper) in-season waiver helper.

Shows YOUR roster + positional depth, then the best available players on the
wire ranked by Sleeper's leaguewide trending-add signal (a live "who is the
league adding right now" proxy for waiver relevance), flagging the ones that
fill a position you're thin at.

Method (same roster-diff trick as sleeper_defense_streaming.py, generalized to
all positions):
  * owned      = union of every roster's players  (/league/{id}/rosters)
  * available  = full NFL player pool - owned      (/players/nfl, cached ~daily)
  * priority   = trending adds intersected w/ available (/players/nfl/trending/add)

This is a DYNASTY league (10-team, 1QB, .5 PPR, 2 FLEX). Trending adds are a
leaguewide (mostly-redraft) signal, so it skews win-now; weight youth/upside
yourself for dynasty holds. Std-lib only (urllib/json).

Usage:  python sleeper_waiver.py [--pos RB] [--limit 25]
"""
import urllib.request, urllib.error, json, os, time, tempfile, argparse

LEAGUE_ID = '1358499663992348672'          # DyNasty
MY_USER   = 'IanPooHead'                    # Ian = "Team L.O.B"
SLEEPER   = 'https://api.sleeper.app/v1'
CACHE     = os.path.join(tempfile.gettempdir(), 'sleeper_players_nfl.json')
CACHE_TTL = 24 * 3600                        # Sleeper asks that /players/nfl be pulled <=1x/day
SKILL_POS = ('QB', 'RB', 'WR', 'TE', 'K')    # DyNasty has no IDP; ignore DL/LB/DB trends
# rough "healthy depth" per position for a 10-team 1QB/2FLEX roster — thin = at/below this
DEPTH_TGT = {'QB': 2, 'RB': 5, 'WR': 5, 'TE': 2, 'K': 1}


def get(url):
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            return json.load(urllib.request.urlopen(req))
        except urllib.error.URLError as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"Sleeper API unavailable ({last}). If you re-ran this several times, wait a minute and retry.")


def load_players():
    if os.path.exists(CACHE) and (time.time() - os.path.getmtime(CACHE)) < CACHE_TTL:
        return json.load(open(CACHE, encoding='utf-8')), 'cache'
    players = get(f'{SLEEPER}/players/nfl')
    try:
        json.dump(players, open(CACHE, 'w', encoding='utf-8'))
    except OSError:
        pass
    return players, 'fetched'


def pinfo(players, pid):
    p = players.get(pid, {})
    nm = p.get('full_name') or p.get('last_name') or pid
    return nm, (p.get('position') or '?'), (p.get('team') or 'FA')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pos', help='filter available list to one position (QB/RB/WR/TE/K)')
    ap.add_argument('--limit', type=int, default=25)
    args = ap.parse_args()
    want_pos = args.pos.upper() if args.pos else None

    users = get(f'{SLEEPER}/league/{LEAGUE_ID}/users')
    me = next((u for u in users if u.get('display_name', '').lower() == MY_USER.lower()), None)
    if not me:
        raise SystemExit(f"User {MY_USER} not found in league {LEAGUE_ID}.")
    my_id = me['user_id']

    rosters = get(f'{SLEEPER}/league/{LEAGUE_ID}/rosters')
    owned = set()
    my_roster = None
    for r in rosters:
        owned.update(r.get('players') or [])
        if r.get('owner_id') == my_id:
            my_roster = r

    players, src = load_players()

    # --- your roster by position ---
    my_by_pos = {}
    for pid in (my_roster.get('players') or []):
        _, pos, _ = pinfo(players, pid)
        my_by_pos.setdefault(pos, []).append(pid)
    s = (my_roster.get('settings') or {})
    print(f"=== Team L.O.B ({MY_USER}) - record {s.get('wins',0)}-{s.get('losses',0)}"
          f"{('-'+str(s['ties'])) if s.get('ties') else ''} ===   (players/nfl from {src})")
    for pos in SKILL_POS + ('DEF',):
        pids = my_by_pos.get(pos, [])
        names = ', '.join(sorted(pinfo(players, p)[0] for p in pids))
        thin = ' <-- THIN' if pos in DEPTH_TGT and len(pids) < DEPTH_TGT[pos] else ''
        print(f"  {pos:<4} ({len(pids)}) {names}{thin}")
    thin_pos = {p for p in SKILL_POS if len(my_by_pos.get(p, [])) < DEPTH_TGT.get(p, 0)}

    # --- best available (trending adds intersected with availability) ---
    trend = get(f'{SLEEPER}/players/nfl/trending/add?lookback_hours=24&limit=100')
    hdr = f"position {want_pos}" if want_pos else "all skill positions"
    print(f"\n=== BEST AVAILABLE ({hdr}) - trending adds not rostered in DyNasty ===")
    print("  (! = fills a position you're thin at)")
    shown = 0
    for t in trend:
        pid = t['player_id']
        if pid in owned:
            continue
        nm, pos, team = pinfo(players, pid)
        if pos not in SKILL_POS:
            continue
        if want_pos and pos != want_pos:
            continue
        flag = ' !' if pos in thin_pos else ''
        print(f"  {nm:<24} {pos:<3} {team:<4} adds/24h {t['count']:>7}{flag}")
        shown += 1
        if shown >= args.limit:
            break
    if not shown:
        print("  (none — nobody trending is available at that filter)")


if __name__ == '__main__':
    main()
