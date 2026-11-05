#!/usr/bin/env python3
"""Underlying-usage trend reader — tell a player's opportunity story, not his season rank.

Season-long fantasy rank is a lagging, blunt number: it buries missed games, role
changes, and rising usage. This pulls each player's RECENT weekly opportunity from
Sleeper's (free) stats endpoint and shows the trend that actually predicts production:

  * snap share   = off_snp / tm_off_snp            (are they on the field?)
  * carry share  = rush_att / team RB rush_att      (RB workload)
  * target share = rec_tgt / team targets           (pass-game role; most predictive)
  * air-yards sh. = rec_air_yd / team air yards
  * WOPR         = 1.5*target_share + 0.7*air_share  (best forward-looking WR/TE metric)
  * efficiency   = yards per carry / per target      (real vs. empty volume)

It then prints a one-line read with trend arrows (role rising / steady / fading), so a
rank-238 RB who's actually a 66%-snap lead back (see: Jonah Coleman) reads correctly.

Data: Sleeper weekly stats (api.sleeper.com/stats/nfl/<season>/<week>) + the /players/nfl
map (cached ~daily in the OS temp dir). Works for any NFL player, any league. Std-lib only.

Usage:  python usage_trends.py "Jonah Coleman" "Tre Harris" [--weeks 5] [--season 2026]
"""
import urllib.request, json, os, time, tempfile, argparse

SLEEPER  = 'https://api.sleeper.app/v1'
STATS    = 'https://api.sleeper.com/stats/nfl'
CACHE    = os.path.join(tempfile.gettempdir(), 'sleeper_players_nfl.json')
CACHE_TTL = 24 * 3600


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})))


def load_players():
    if os.path.exists(CACHE) and (time.time() - os.path.getmtime(CACHE)) < CACHE_TTL:
        return json.load(open(CACHE, encoding='utf-8'))
    p = get(f'{SLEEPER}/players/nfl')
    try:
        json.dump(p, open(CACHE, 'w', encoding='utf-8'))
    except OSError:
        pass
    return p


def current_week():
    st = get(f'{SLEEPER}/state/nfl')
    return st.get('week') or st.get('display_week') or 1


def arrow(recent, early):
    if recent is None or early is None:
        return ' '
    d = recent - early
    return '^' if d > 0.06 else ('v' if d < -0.06 else '=')


def pct(x):
    return f'{100*x:.0f}%' if x is not None else '-'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('players', nargs='+', help='player full names, e.g. "Jonah Coleman"')
    ap.add_argument('--weeks', type=int, default=5, help='how many recent weeks to show')
    ap.add_argument('--season', default='2026')
    args = ap.parse_args()

    players = load_players()
    # name -> (id, team, pos)
    def find(name):
        n = name.lower()
        hits = [(pid, p) for pid, p in players.items()
                if (p.get('full_name') or '').lower() == n]
        if not hits:  # loose contains fallback
            hits = [(pid, p) for pid, p in players.items()
                    if n in (p.get('full_name') or '').lower()]
        return hits[0] if len(hits) == 1 else (hits[0] if hits else None)

    cur = current_week()
    weeks = list(range(max(1, cur - args.weeks + 1), cur + 1))

    # pull each week's full stat line once; build team totals + per-player lookup
    wk_stats, team_tot = {}, {}
    for w in weeks:
        try:
            rows = get(f'{STATS}/{args.season}/{w}?season_type=regular')
        except Exception:
            rows = []
        byid = {s['player_id']: (s.get('stats') or {}) for s in rows if isinstance(s, dict)}
        wk_stats[w] = byid
        tt = {}
        for pid, st in byid.items():
            tm = players.get(pid, {}).get('team')
            pos = players.get(pid, {}).get('position')
            if not tm:
                continue
            d = tt.setdefault(tm, {'rb_att': 0.0, 'tgt': 0.0, 'air': 0.0})
            if pos == 'RB':
                d['rb_att'] += st.get('rush_att', 0) or 0
            d['tgt'] += st.get('rec_tgt', 0) or 0
            d['air'] += st.get('rec_air_yd', 0) or 0
        team_tot[w] = tt

    for name in args.players:
        hit = find(name)
        if not hit:
            print(f'\n=== {name}: not found ===')
            continue
        pid, p = hit
        tm, pos = p.get('team'), p.get('position')
        print(f"\n=== {p.get('full_name')} ({pos}, {tm}) - last {len(weeks)} weeks ===")
        print('Wk | snap% | car cShare | tgt tShare | airYd | WOPR | yd  | fpts')
        snaps, shares = [], []
        for w in weeks:
            st = wk_stats[w].get(pid, {})
            tt = team_tot[w].get(tm, {})
            snp, tmsnp = st.get('off_snp'), st.get('tm_off_snp')
            snap_sh = (snp / tmsnp) if snp and tmsnp else None
            att = st.get('rush_att', 0) or 0
            cshare = (att / tt['rb_att']) if tt.get('rb_att') else None
            tgt = st.get('rec_tgt', 0) or 0
            tshare = (tgt / tt['tgt']) if tt.get('tgt') else None
            air = st.get('rec_air_yd', 0) or 0
            ashare = (air / tt['air']) if tt.get('air') else None
            wopr = (1.5 * (tshare or 0) + 0.7 * (ashare or 0)) if tshare is not None else None
            yd = (st.get('rush_yd', 0) or 0) + (st.get('rec_yd', 0) or 0)
            fpts = st.get('pts_ppr')
            played = snp or att or tgt
            if not played:
                print(f'{w:<2} |   DNP (bye/inactive/upcoming)')
                continue
            snaps.append(snap_sh)
            shares.append(tshare if pos in ('WR', 'TE') else cshare)
            print(f"{w:<2} | {pct(snap_sh):>5} | {att:>3} {pct(cshare):>5} | {tgt:>3} {pct(tshare):>5} | "
                  f"{int(air):>5} | {('%.2f'%wopr) if wopr is not None else '  -':>4} | {int(yd):>3} | "
                  f"{('%.1f'%fpts) if fpts is not None else '-'}")

        # trend read: compare the most recent played week to the first played week in window
        if len(snaps) >= 2:
            metric = 'target share' if pos in ('WR', 'TE') else 'carry share'
            sa, sha = arrow(snaps[-1], snaps[0]), arrow(shares[-1], shares[0])
            verdict = ('role RISING - buy' if '^' in (sa + sha) else
                       'role FADING - caution' if 'v' in (sa + sha) else 'role steady')
            print(f"  read: snap% {sa}  {metric} {sha}  ->  {verdict}")
        else:
            print('  read: not enough recent games to trend (injury/bye).')


if __name__ == '__main__':
    main()
