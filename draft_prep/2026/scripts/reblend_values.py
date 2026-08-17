#!/usr/bin/env python3
"""Reblend the value model with external market auction values.

Old model `fairValue` was VOR scaled to the full $2400 pool, which runs ~15-20%
hot vs. the real auction market (the league bleeds budget into $1-sleeper
overpays). This blends our ESPN auction values with external market sources so
the tool's fair values / clearing prices / verdicts track reality.

Blend = mean of available market sources per player: ESPN (player_values_2026)
+ FFToday (12-team $200 PPR). Re-run yearly with fresh external pulls.

Outputs:
- Draft_Day_Tool.html   -> PLAYERS[].f / .lp recomputed from the blend
- analysis/keeper_analysis.csv, predicted_keepers.csv -> surplus at market
- analysis/league_adjusted_values.csv -> adds blendedValue column
- source_data/auction_values_external.csv -> the external pull (reproducibility)
"""
import re, csv, json, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # draft_prep/2026

# --- External source: FFToday 2026, 12-team $200 PPR (pulled 2026-08-17) ---
FFTODAY = {
 "Puka Nacua":52,"Jahmyr Gibbs":51,"Bijan Robinson":51,"Ja'Marr Chase":51,
 "Amon-Ra St. Brown":48,"Jaxon Smith-Njigba":46,"Christian McCaffrey":43,
 "Jonathan Taylor":38,"Drake London":38,"Justin Jefferson":34,"CeeDee Lamb":34,
 "James Cook":33,"Rashee Rice":33,"Omarion Hampton":30,"De'Von Achane":30,
 "Chris Olave":30,"Garrett Wilson":30,"Ashton Jeanty":29,"Saquon Barkley":29,
 "A.J. Brown":29,"Chase Brown":28,"Nico Collins":28,"Brock Bowers":28,
 "Jeremiyah Love":27,"Josh Allen":26,"Derrick Henry":26,"Zay Flowers":26,
 "DeVonta Smith":26,"Trey McBride":26,"Kenneth Walker":25,"Kyren Williams":25,
 "George Pickens":25,"Cam Skattebo":24,"Breece Hall":23,"Malik Nabers":23,
 "Josh Jacobs":22,"Emeka Egbuka":22,"Tetairoa McMillan":22,"Javonte Williams":21,
 "Davante Adams":21,"Jameson Williams":21,"Bucky Irving":20,"Ladd McConkey":19,
 "D.J. Moore":19,"Travis Etienne":18,"Bhayshul Tuten":18,"Jaylen Waddle":18,
 "Mike Evans":17,"Christian Watson":17,"Tee Higgins":17,"Luther Burden III":17,
 "Rome Odunze":17,"D'Andre Swift":16,"Alec Pierce":16,"DK Metcalf":16,
 "Colston Loveland":16,"Quinshon Judkins":15,"Terry McLaurin":14,"Tyler Warren":14,
 "Drake Maye":13,"Lamar Jackson":13,"Jayden Daniels":13,"Jaylen Warren":13,
 "Michael Pittman Jr.":13,"Harold Fannin Jr.":13,"Jalen Hurts":12,
 "David Montgomery":12,"TreVeyon Henderson":12,"Tony Pollard":12,
 "Marvin Harrison Jr.":12,"Courtland Sutton":12,"Jayden Reed":12,"Chuba Hubbard":11,
 "Jadarian Price":11,"Rhamondre Stevenson":11,"Rachaad White":11,"Carnell Tate":11,
 "Kyle Pitts":11,"J.K. Dobbins":10,"Wan'Dale Robinson":10,"Jakobi Meyers":10,
 "Chris Godwin":10,"Travis Kelce":10,"Joe Burrow":9,"Bo Nix":9,"Rico Dowdle":9,
 "RJ Harvey":9,"Aaron Jones":9,"Khalil Shakir":9,"Michael Wilson":9,"Josh Downs":9,
 "Xavier Worthy":9,"Brian Thomas Jr.":9,"Romeo Doubs":9,"Jordan Addison":9,
 "Sam LaPorta":9,"Mark Andrews":9,"Dak Prescott":8,"Kenneth Gainwell":8,
 "Kyle Monangai":8,"Jordyn Tyson":8,"Parker Washington":8,"Quentin Johnston":8,
 "Brock Purdy":7,"Jared Goff":7,"Caleb Williams":7,"Jacory Croskey-Merritt":7,
 "Blake Corum":7,"Matthew Golden":7,"KC Concepcion":7,"Makai Lemon":7,
 "Jake Ferguson":7,"Justin Herbert":6,"Tyler Shough":6,"Jordan Mason":6,
 "Jonathon Brooks":6,"Tyrone Tracy Jr.":6,"Alvin Kamara":6,"Rashid Shaheed":6,
 "Tre Tucker":6,"Jerry Jeudy":6,"Deebo Samuel":6,"Tucker Kraft":6,
 "Trevor Lawrence":5,"Jaxson Dart":5,"Woody Marks":5,"Tyjae Spears":5,
 "Dylan Sampson":5,"Zach Charbonnet":5,"Ty Johnson":5,"Jalen Coker":5,
 "Rashod Bateman":5,"De'Zhaun Stribling":5,"Jayden Higgins":5,"Jalen McMillan":5,
 "Dallas Goedert":5,"Dalton Schultz":5,"Hunter Henry":5,"Isiah Pacheco":4,
 "Stefon Diggs":4,"Germie Bernard":4,"Calvin Ridley":4,"Jalen Nailor":4,
 "Malik Washington":4,"Dalton Kincaid":4,"Patrick Mahomes":3,"Matthew Stafford":3,
 "Chris Rodriguez Jr.":3,"Justice Hill":3,"Tyler Allgeier":3,"Brian Robinson Jr.":3,
 "Samaje Perine":3,"Braelon Allen":3,"Keaton Mitchell":3,"Adonai Mitchell":3,
 "Omar Cooper Jr.":3,"Caleb Douglas":3,"Denzel Boston":3,"Ryan Flournoy":3,
 "Jauan Jennings":3,"Xavier Legette":3,"Juwan Johnson":3,"Isaiah Likely":3,
 "Pat Freiermuth":3,"Kyler Murray":2,"Sam Darnold":2,"Baker Mayfield":2,
 "Ray Davis":2,"Tank Bigsby":2,"Emari Demercado":2,"MarShawn Lloyd":2,
 "Cooper Kupp":2,"Andrei Iosivas":2,"Greg Dulcich":2,"George Kittle":2,
}

def norm(name):
    n = (name or "").lower().strip()
    n = n.replace(".", "").replace("'", "").replace("’", "")
    n = n.replace("-", " ")
    for suf in [" jr", " sr", " iii", " ii", " iv", " v"]:
        if n.endswith(suf):
            n = n[:-len(suf)]
    return " ".join(n.split())

FFT = {norm(k): v for k, v in FFTODAY.items()}

# --- ESPN values from our source data ---
espn = {}
with open(os.path.join(HERE, "source_data", "player_values_2026.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        try:
            espn[norm(r["player"])] = float(r["auctionValue"])
        except (ValueError, KeyError):
            pass

def blend(name):
    """Mean of available market sources (ESPN, FFToday). None if neither."""
    k = norm(name)
    vals = [v for v in (espn.get(k), FFT.get(k)) if v is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals))

# --- 1. Tool PLAYERS array ---
tool_path = os.path.join(HERE, "Draft_Day_Tool.html")
html = open(tool_path, encoding="utf-8").read()
m = re.search(r"PLAYERS=(\[.*?\]);", html, re.S)
players = json.loads(m.group(1))
changed = 0
for p in players:
    b = blend(p["n"])
    if b is not None:
        p["f"] = b
        p["lp"] = max(1, round(b * 0.98))
        changed += 1
new_arr = "PLAYERS=" + json.dumps(players, separators=(",", ":"), ensure_ascii=False) + ";"
html = html[:m.start()] + new_arr + html[m.end():]
open(tool_path, "w", encoding="utf-8", newline="").write(html)

# --- 2. keeper_analysis.csv (recompute value/surplus at market) ---
ka_path = os.path.join(HERE, "analysis", "keeper_analysis.csv")
ka = list(csv.DictReader(open(ka_path, encoding="utf-8")))
for r in ka:
    b = blend(r["player"])
    if b is None:
        b = 1
    r["value2026"] = b
    r["surplus"] = round(b - float(r["keeperCost"]), 1)
with open(ka_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["owner", "player", "pos", "kept2025", "keeperCost", "value2026", "surplus"])
    w.writeheader(); w.writerows(ka)

# --- 3. predicted_keepers.csv = each owner's marquee keeper ---
# Only real assets are keeper-worthy (value >= 20); pick the highest surplus
# among those. If the best is deeply underwater (< -10) or nobody qualifies,
# the owner is predicted to keep none. (Argmax over ALL players would pick a
# near-zero $6 scrub over an elite at slight negative -- nonsense.)
VALUE_FLOOR, SURPLUS_FLOOR = 20.0, -10.0
best = {}
for r in ka:
    o = r["owner"]; s = float(r["surplus"])
    if float(r["value2026"]) < VALUE_FLOOR:
        continue
    if o not in best or s > float(best[o]["surplus"]):
        best[o] = r
with open(os.path.join(HERE, "analysis", "predicted_keepers.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["owner", "keeper", "pos", "keeperCost", "value2026", "surplus"])
    w.writeheader()
    for o in sorted(set(r["owner"] for r in ka)):
        r = best.get(o)
        if r and float(r["surplus"]) >= SURPLUS_FLOOR:
            w.writerow({"owner": o, "keeper": r["player"], "pos": r["pos"],
                        "keeperCost": r["keeperCost"], "value2026": r["value2026"], "surplus": r["surplus"]})
        else:
            w.writerow({"owner": o, "keeper": "(keep none)", "pos": "", "keeperCost": "", "value2026": "", "surplus": ""})

# --- 4. league_adjusted_values.csv: add blendedValue column ---
lav_path = os.path.join(HERE, "analysis", "league_adjusted_values.csv")
lav = list(csv.DictReader(open(lav_path, encoding="utf-8")))
fn = list(lav[0].keys()) + (["blendedValue"] if "blendedValue" not in lav[0] else [])
for r in lav:
    b = blend(r["player"])
    r["blendedValue"] = b if b is not None else ""
with open(lav_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fn); w.writeheader(); w.writerows(lav)

# --- 4b. draft_board_2026.csv: blended value + realistic recommended max bid ---
db_path = os.path.join(HERE, "analysis", "draft_board_2026.csv")
db = list(csv.DictReader(open(db_path, encoding="utf-8")))
fn2 = list(db[0].keys()) + (["blendedValue"] if "blendedValue" not in db[0] else [])
for r in db:
    b = blend(r["player"])
    r["blendedValue"] = b if b is not None else ""
    if b is not None:
        r["recMaxBid"] = max(1, round(b))  # fair market = don't-overpay ceiling
with open(db_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fn2); w.writeheader(); w.writerows(db)

# --- 5. Persist the external pull ---
with open(os.path.join(HERE, "source_data", "auction_values_external.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["player", "source", "auctionValue"])
    for k, v in FFTODAY.items():
        w.writerow([k, "fftoday_2026_ppr12_200", v])

# --- Summary ---
print(f"PLAYERS updated: {changed}/{len(players)}")
print("\nKey players (blended fair):")
for nm in ["Puka Nacua","Jahmyr Gibbs","Bijan Robinson","Christian McCaffrey",
           "De'Von Achane","Ashton Jeanty","Omarion Hampton","Kyren Williams"]:
    print(f"  {nm:24s} blended=${blend(nm)}")
print("\nIan keeper board (market):")
for r in ka:
    if r["owner"] == "Ian":
        print(f"  {r['player']:26s} cost=${r['keeperCost']:>2} val=${r['value2026']:>2} surplus={r['surplus']}")
