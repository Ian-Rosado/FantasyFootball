#!/usr/bin/env python3
"""Rest-of-season + playoff PPG projection for your roster, any of the three leagues.

Per player:
  baseline   = recency-weighted PPG  (0.6*last3 + 0.4*season), in the league's scoring
  def mult   = mean over player-games vs a defense of (game_pts / that player's season avg),
               clamped 0.6-1.5, >=5 games else neutral 1.0  -> controls for player quality,
               so it's "points allowed over expected", not raw points allowed
  proj(week) = baseline * mult(opponent that week, position)
ROS PPG = mean of proj over the remaining regular-season weeks (ex-byes); playoff PPG likewise
over the league's playoff weeks. Opportunity + matchup only — not injuries or game-script.

Scoring is a full/half-PPR approximation from Sleeper's weekly points (pts_ppr / pts_half_ppr);
close for these leagues but not each league's exact bonuses. Early-season samples (and anything
two months out, i.e. the playoff numbers) are the softest. Std-lib only.

Usage:  python roster_projection.py --league {gg,dynasty,glorp}
"""
import urllib.request, json, os, time, tempfile, collections, re, argparse

SLEEPER='https://api.sleeper.app/v1'; STATS='https://api.sleeper.com/stats/nfl'
ESPN='https://cdn.espn.com/core/nfl/scoreboard?xhr=1'; SEASON=2026
ESPN2SL={'WSH':'WAS','JAC':'JAX','LVR':'LV'}
SCRIPTS=os.path.dirname(os.path.abspath(__file__))
ESPN_POS={1:'QB',2:'RB',3:'WR',4:'TE',5:'K',16:'D/ST'}

LEAGUES={
  'gg':      {'name':'Gridiron Grind / CRANKY',  'src':'fleaflicker', 'id':'78455',
              'team':'CRANKY',      'pts':'pts_ppr',      'playoffs':[15,16,17]},
  'dynasty': {'name':'DyNasty / Team L.O.B',      'src':'sleeper',     'id':'1358499663992348672',
              'user':'IanPooHead',  'pts':'pts_half_ppr', 'playoffs':None},   # read from settings
  'glorp':   {'name':'Eat GLORP',                 'src':'espn',        'id':'686982204',
              'team':'Eat GLORP',   'pts':'pts_ppr',      'playoffs':[15,16]},
}

def get(u, hdr=None):
    h={'User-Agent':'Mozilla/5.0'}; h.update(hdr or {})
    return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=h)))

def get_retry(u, hdr=None):
    for a in range(4):
        try: return get(u,hdr)
        except Exception: time.sleep(3*(a+1))
    raise SystemExit(f'API unavailable: {u}')

def norm(a): return ESPN2SL.get(a,a)

def nkey(name):
    n=(name or '').lower()
    n=re.sub(r'\b(jr|sr|ii|iii|iv|v)\b','',n)
    n=re.sub(r"[.\-'’]",'',n)
    return re.sub(r'\s+',' ',n).strip()

def espn_cookies():
    s2,swid=os.environ.get('ESPN_S2'),os.environ.get('ESPN_SWID')
    if s2 and swid: return s2,swid
    p=os.path.join(SCRIPTS,'.espn_cookies.json')
    if os.path.exists(p):
        c=json.load(open(p,encoding='utf-8')); return c['espn_s2'],c['SWID']
    raise SystemExit('No ESPN cookies (.espn_cookies.json or ESPN_S2/ESPN_SWID).')


def load_players():
    cache=os.path.join(tempfile.gettempdir(),'sleeper_players_nfl.json')
    if os.path.exists(cache): return json.load(open(cache,encoding='utf-8'))
    p=get(f'{SLEEPER}/players/nfl'); json.dump(p,open(cache,'w',encoding='utf-8')); return p


def roster(cfg, players):
    """Return list of (name, pos, sleeper_pid or None) for my team in this league."""
    byname={}
    for pid,p in players.items():
        byname.setdefault(nkey(p.get('full_name')), pid)
    if cfg['src']=='sleeper':
        users=get(f"{SLEEPER}/league/{cfg['id']}/users")
        uid=next(u['user_id'] for u in users if u.get('display_name','').lower()==cfg['user'].lower())
        rs=get(f"{SLEEPER}/league/{cfg['id']}/rosters")
        mine=next(r for r in rs if r.get('owner_id')==uid)
        out=[]
        for pid in (mine.get('players') or []):
            p=players.get(pid,{}); pos=p.get('position')
            if pos and pos!='DEF': out.append((p.get('full_name') or pid,pos,pid))
        return out
    if cfg['src']=='fleaflicker':
        d=get_retry(f"https://www.fleaflicker.com/api/FetchLeagueRosters?sport=NFL&league_id={cfg['id']}")
        mine=next(r for r in d['rosters'] if r['team']['name']==cfg['team'])
        out=[]
        for pl in mine.get('players',[]):
            pp=pl['proPlayer']; pos=pp['position']
            if pos=='D/ST': continue
            out.append((pp['nameFull'],pos,byname.get(nkey(pp['nameFull']))))
        return out
    if cfg['src']=='espn':
        s2,swid=espn_cookies()
        base=f'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/segments/0/leagues/{cfg["id"]}'
        d=get(base+'?view=mTeam&view=mRoster',{'Cookie':f'espn_s2={s2}; SWID={swid}'})
        out=[]
        for t in d.get('teams',[]):
            nm=(t.get('name') or '').strip()
            if nm.lower()!=cfg['team'].lower(): continue
            for e in (t.get('roster') or {}).get('entries',[]):
                p=e['playerPoolEntry']['player']; pos=ESPN_POS.get(p.get('defaultPositionId'))
                if not pos or pos=='D/ST': continue
                out.append((p.get('fullName'),pos,byname.get(nkey(p.get('fullName')))))
        return out


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--league',required=True,choices=list(LEAGUES))
    cfg=LEAGUES[ap.parse_args().league]
    players=load_players()
    cur=get(f'{SLEEPER}/state/nfl').get('week') or 10
    PTS=cfg['pts']

    playoffs=cfg['playoffs']
    if playoffs is None:  # read Sleeper playoff start
        start=get(f"{SLEEPER}/league/{cfg['id']}").get('settings',{}).get('playoff_week_start',15)
        playoffs=list(range(start,start+3))

    # schedule: team -> {week: opp_def}
    sched=collections.defaultdict(dict)
    for w in range(1,18):
        try: d=get(f'{ESPN}&week={w}&year={SEASON}&seasontype=2')
        except Exception: continue
        for e in d.get('content',{}).get('sbData',{}).get('events',[]):
            m={x['homeAway']:norm(x['team']['abbreviation']) for x in e['competitions'][0]['competitors']}
            h,a=m.get('home'),m.get('away')
            if h and a: sched[h][w]=a; sched[a][w]=h

    # weekly games weeks 1..cur-1
    games=collections.defaultdict(list)   # pid -> [(week,pts,opp)]
    for w in range(1,cur):
        for s in get_retry(f'{STATS}/{SEASON}/{w}?season_type=regular'):
            if not isinstance(s,dict): continue
            stx=s.get('stats') or {}
            if stx.get('gp',0)!=1: continue
            pid=s['player_id']; tm=players.get(pid,{}).get('team')
            games[pid].append((w, stx.get(PTS,0.0), sched.get(tm,{}).get(w)))

    savg={pid:(sum(p for _,p,_ in g)/len(g) if g else 0.0) for pid,g in games.items()}
    def baseline(pid):
        g=[p for _,p,_ in sorted(games.get(pid,[]))]
        if not g: return 0.0
        return 0.6*(sum(g[-3:])/min(3,len(g)))+0.4*(sum(g)/len(g)) if len(g)>=3 else sum(g)/len(g)

    ratios=collections.defaultdict(list)
    for pid,gl in games.items():
        pos=players.get(pid,{}).get('position')
        if pos not in ('QB','RB','WR','TE','K') or savg.get(pid,0)<4: continue
        for _,pts,opp in gl:
            if opp: ratios[(opp,pos)].append(pts/savg[pid])
    def mult(dfn,pos):
        r=ratios.get((dfn,pos),[]); return max(0.6,min(1.5,sum(r)/len(r))) if len(r)>=5 else 1.0

    def project(pid,pos,weeks):
        tm=players.get(pid,{}).get('team'); b=baseline(pid); v=[]
        for w in weeks:
            opp=sched.get(tm,{}).get(w)
            if opp: v.append(b*mult(opp,pos))
        return (sum(v)/len(v) if v else 0.0), len(v)

    reg=list(range(cur,15))
    print(f"=== {cfg['name']} — full-/half-PPR PPG | thru Wk{cur-1} | playoffs {playoffs} ===")
    print(f"{'Player':<24}{'Pos':<4}{'Base':>6}{'ROS':>7}{'(g)':>4}{'Playoff':>9}{'(g)':>4}")
    rows=[]
    for nm,pos,pid in roster(cfg,players):
        if not pid: rows.append((pos,nm,None,None,0,None,0)); continue
        rpp,rg=project(pid,pos,reg); ppp,pg=project(pid,pos,playoffs)
        rows.append((pos,nm,baseline(pid),rpp,rg,ppp,pg))
    order={'QB':0,'RB':1,'WR':2,'TE':3,'K':4}
    for pos,nm,b,rpp,rg,ppp,pg in sorted(rows,key=lambda x:(order.get(x[0],9),-(x[3] or 0))):
        if b is None: print(f"{nm:<24}{pos:<4}  (no stats match)"); continue
        print(f"{nm:<24}{pos:<4}{b:6.1f}{rpp:7.1f}{rg:4}{ppp:9.1f}{pg:4}")


if __name__=='__main__':
    main()
