#!/usr/bin/env python3
"""Gridiron Grind (Fleaflicker) in-season waiver helper.

Pulls the current free-agent pool from the Fleaflicker public API, plus each
team's roster needs and every manager's historical FAAB bidding tendencies, so
you can size waiver bids sensibly.

Usage:  python waiver_bids.py [--top 40]
Std-lib only (urllib/csv). League + your handle + FAAB history are wired below.
Re-run any week; the free-agent pool updates automatically.
"""
import urllib.request, json, csv, collections, statistics as st, os, argparse, time

LEAGUE_ID = '78455'
MY_OWNER   = 'Iyano1911'          # Ian = "CRANKY" (teamId 689370)
BASE       = 'https://www.fleaflicker.com/api'
HERE       = os.path.dirname(os.path.abspath(__file__))
FAAB_CSV   = os.path.join(HERE, '..', 'source_data', 'faab_claims.csv')

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

def free_agents(top):
    out, off = [], 0
    while len(out) < top:
        d = api(f'/FetchPlayerListing?sport=NFL&league_id={LEAGUE_ID}'
                f'&filter.freeAgentOnly=true&sort=SORT_DRAFT_RANKING&result_offset={off}')
        pl = d.get('players', [])
        for p in pl:
            pp = p['proPlayer']
            out.append({'name': pp['nameFull'], 'pos': pp['position'],
                        'team': pp.get('proTeamAbbreviation'),
                        'rankDraft': (p.get('rankDraft') or {}).get('ordinal'),
                        'posRank': (p.get('rankFantasy') or {}).get('ordinal'),
                        'owned': round(pp.get('percentOwnedRatio', 0) * 100)})
        off = d.get('resultOffsetNext')
        if not off or not pl:
            break
    return out

def faab_history():
    tid2owner, bids = {}, collections.defaultdict(list)
    with open(FAAB_CSV, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            tid2owner[r['teamId']] = r['owner']
            if r.get('winBid'):
                bids[r['owner']].append(int(r['winBid']))
    return tid2owner, bids

def rosters(tid2owner):
    r = api(f'/FetchLeagueRosters?sport=NFL&league_id={LEAGUE_ID}')
    teams = []
    for ro in r['rosters']:
        tm, cnt = ro['team'], collections.Counter()
        for pl in ro.get('players', []):
            pos = pl.get('proPlayer', {}).get('position')
            if pos:
                cnt[pos] += 1
        teams.append({'name': tm['name'], 'owner': tid2owner.get(str(tm['id']), '?'),
                      'budget': int((tm.get('waiverAcquisitionBudget') or {}).get('value', 0)), 'cnt': cnt})
    return teams

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=40)
    top = ap.parse_args().top
    tid2owner, bids = faab_history()

    print('=== TOP FREE AGENTS (by draft rank) ===')
    for f in sorted(free_agents(top), key=lambda x: x['rankDraft'] or 9999)[:top]:
        print(f"{str(f['rankDraft']):>4} {f['pos']:<4} {f['name']:<26} {str(f['team']):<4} "
              f"posRank {str(f['posRank']):<5} owned {f['owned']:>3}%")

    print('\n=== ROSTER COUNTS (positional needs) ===')
    for t in sorted(rosters(tid2owner), key=lambda x: x['owner'] != MY_OWNER):
        c = t['cnt']; me = '  <-- YOU' if t['owner'] == MY_OWNER else ''
        print(f"{t['name']:<26} {t['owner']:<14} QB{c.get('QB',0)} RB{c.get('RB',0)} "
              f"WR{c.get('WR',0)} TE{c.get('TE',0)} K{c.get('K',0)} D/ST{c.get('D/ST',0)}  ${t['budget']}{me}")

    print('\n=== FAAB BIDDING TENDENCIES (from faab_claims.csv) ===')
    for o in sorted(bids, key=lambda x: -sum(bids[x])):
        b = bids[o]
        print(f"{o:<14} claims {len(b):>3} | avg ${sum(b)/len(b):4.1f} | median ${st.median(b):>4} "
              f"| max ${max(b):>3} | top3 {sorted(b, reverse=True)[:3]}")

if __name__ == '__main__':
    main()
