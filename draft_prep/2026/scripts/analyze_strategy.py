#!/usr/bin/env python3
# Gridiron Grind - strategy trend analyzer.
# Re-run each year after appending the new season's rows to the source CSVs.
# Reads: standings.csv, espn_draft.csv, faab_claims.csv, trades.csv, proj_hist.csv
# Writes: strategy_success.csv, overunderpay.csv, trend_report.md
import csv,re,os,math,statistics
from datetime import date
from collections import defaultdict

def find(f):
    for p in (os.path.join('source_data',f), f, os.path.join('..','source_data',f)):
        if os.path.exists(p): return p
    raise FileNotFoundError(f)
def rd(f): return list(csv.DictReader(open(find(f),encoding='utf-8')))
def norm(n):
    n=n.lower().replace('.','').replace(chr(39),'')
    n=re.sub(r'\b(jr|sr|ii|iii|iv|v)\b','',n); return re.sub(r'\s+',' ',n).strip()
def corr(xs,ys):
    n=len(xs)
    if n<3: return 0.0
    mx=sum(xs)/n; my=sum(ys)/n
    num=sum((x-mx)*(y-my) for x,y in zip(xs,ys)); den=(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))**.5
    return num/den if den else 0.0
def pval(r,n):
    if n<4 or abs(r)>=.999: return 0.0
    t=r*math.sqrt((n-2)/(1-r*r)); return math.erfc(abs(t)/math.sqrt(2))

# position map
POS={}
for f in ['player_values_2026.csv','proj_hist.csv','faab_claims.csv','current_rosters.csv']:
    try:
        for r in rd(f):
            if r.get('pos'): POS.setdefault(norm(r['player']),r['pos'])
    except FileNotFoundError: pass
POS.update({norm(k):v for k,v in {'AJ Dillon':'RB','Alexander Mattison':'RB','Chase Claypool':'WR','Chigoziem Okonkwo':'TE','Clyde Edwards-Helaire':'RB','Damien Harris':'RB','Graham Gano':'K','Greg Zuerlein':'K','Jahan Dotson':'WR','Jake Moody':'K','Jeff Wilson':'RB','Jonathan Mingo':'WR','Kendre Miller':'RB','Luke Musgrave':'TE','Marquise Brown':'WR','Michael Gallup':'WR','Michael Thomas':'WR','Rashaad Penny':'RB','Robert Woods':'WR','Rondale Moore':'WR','Russell Wilson':'QB','Skyy Moore':'WR','Tim Patrick':'WR','Treylon Burks':'WR','Tyler Boyd':'WR','Tyquan Thornton':'WR','Will Shipley':'RB'}.items()})
gp=lambda nm: 'D/ST' if 'D/ST' in nm else POS.get(norm(nm),'?')

# outcomes
out={}
for r in rd('standings.csv'): out[(r['owner'],r['season'])]={'wins':int(r['wins']),'regRank':int(r['regRank'])}

# auction seasons = seasons present in espn_draft
draft=rd('espn_draft.csv')
auction_seasons=sorted(set(r['season'] for r in draft))

# ---- draft metrics per team-season ----
D=defaultdict(lambda:defaultdict(float)); Dtot=defaultdict(float); Dbids=defaultdict(list)
for r in draft:
    k=(r['ffOwner'],r['season']); b=int(r['bid']); D[k][gp(r['player'])]+=b; Dtot[k]+=b; Dbids[k].append(b)
# faab metrics
F=defaultdict(lambda:{'spend':0,'n':0,'rb':0,'late':0,'max':0})
for r in rd('faab_claims.csv'):
    k=(r['owner'],r['season']); b=int(r['winBid']); y=int(r['season'])
    F[k]['spend']+=b; F[k]['n']+=1; F[k]['max']=max(F[k]['max'],b)
    if gp(r['player'])=='RB': F[k]['rb']+=b
    try:
        wk=(date.fromisoformat(r['date'])-date(y,9,1)).days//7+1
        if wk>=12: F[k]['late']+=b
    except Exception: pass
# trades
T=defaultdict(int)
for r in rd('trades.csv'):
    if r.get('owner') and r['owner']!='?': T[(r['owner'],r['season'])]+=1

def build_rows(seasons):
    rows=[]
    for k in out:
        if k[1] not in seasons or Dtot[k]==0: continue
        bids=sorted(Dbids[k],reverse=True); tot=Dtot[k]
        f=F[k]; ftot=f['spend'] or 1
        rows.append(dict(owner=k[0],season=k[1],
            RB=D[k]['RB']/tot, WR=D[k]['WR']/tot, TE=D[k]['TE']/tot, QB=D[k]['QB']/tot,
            top2=sum(bids[:2])/tot, studN=sum(1 for b in bids if b>=40),
            faabN=f['n'], faabSp=f['spend'], faabRBsh=f['rb']/ftot, faabLate=f['late']/ftot,
            trades=T.get(k,0), wins=out[k]['wins'], regRank=out[k]['regRank']))
    return rows

METRICS=[('RB','draft RB share'),('WR','draft WR share'),('TE','draft TE share'),
         ('faabN','FAAB volume'),('faabLate','FAAB late-spend share'),('faabRBsh','FAAB RB share'),('trades','trade count')]
allrows=build_rows(set(auction_seasons))
# ---- trend report ----
season_list=', '.join(auction_seasons)
lines=['# Strategy Trend Report','',f'Auction seasons analyzed: {season_list}  (n={len(allrows)} team-seasons pooled)','',
 'Correlation of each strategy metric with WINS. Pooled, then by season (watch for the story shifting/strengthening).','']
hdr='| metric | POOLED r | p | '+' | '.join(auction_seasons)+' |'
lines.append(hdr); lines.append('|'+'---|'*(3+len(auction_seasons)))
for key,label in METRICS:
    pr=corr([x[key] for x in allrows],[x['wins'] for x in allrows]); pp=pval(pr,len(allrows))
    yr=[]
    for s in auction_seasons:
        rr=build_rows({s}); yr.append(f'{corr([x[key] for x in rr],[x["wins"] for x in rr]):+.2f}' if len(rr)>=4 else 'na')
    lines.append(f'| {label} | {pr:+.2f} | {pp:.2f} | '+' | '.join(yr)+' |')
# over/underpay (pooled + by year)
def overunder(seasons):
    proj=defaultdict(dict); allp=defaultdict(list)
    for r in rd('proj_hist.csv'):
        pj=float(r['projPoints'] or 0); proj[r['season']][norm(r['player'])]=(r['pos'],pj); allp[r['season']].append((r['pos'],pj))
    repl={'QB':14,'RB':34,'WR':40,'TE':14}
    agg=defaultdict(lambda:{'paid':0.0,'fair':0.0,'n':0})
    for s in seasons:
        if s not in proj: continue
        base={}
        for pos in repl:
            pl=sorted([pj for p,pj in allp[s] if p==pos and pj>0],reverse=True); base[pos]=pl[min(repl[pos],len(pl))-1] if pl else 0
        vor={}
        for nn,(pos,pj) in proj[s].items():
            if pos in base and pj>0: vor[nn]=max(0.0,pj-base[pos])
        tot=sum(vor.values()) or 1; pool=12*200-12*16
        fair={nn:1+vor[nn]/tot*pool for nn in vor}
        for r in draft:
            if r['season']!=s: continue
            if r.get('keeper')=='true': continue
            nn=norm(r['player'])
            if nn in fair:
                f=fair[nn]; t='STUD' if f>=20 else ('MID' if f>=6 else 'SLEEP'); b=int(r['bid'])
                agg[t]['paid']+=b; agg[t]['fair']+=f; agg[t]['n']+=1
    return {t:(agg[t]['paid']/agg[t]['fair'] if agg[t]['fair'] else 0, agg[t]['n']) for t in ('STUD','MID','SLEEP')}
proj_seasons=sorted(set(r['season'] for r in rd('proj_hist.csv')))
lines += ['','## Over/underpay by tier (paid / fair value), needs proj_hist for the season','',
          '| tier | POOLED | '+' | '.join(proj_seasons)+' |','|'+'---|'*(2+len(proj_seasons))]
pooled=overunder(set(proj_seasons))
for t in ('STUD','MID','SLEEP'):
    yr=[f'{overunder({s})[t][0]:.2f}x' if overunder({s})[t][1] else 'na' for s in proj_seasons]
    lines.append(f'| {t} | {pooled[t][0]:.2f}x | '+' | '.join(yr)+' |')
open('trend_report.md','w').write('\n'.join(lines))
print('\n'.join(lines))
print('\nWROTE trend_report.md')
