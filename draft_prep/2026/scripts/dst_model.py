#!/usr/bin/env python3
"""Per-matchup D/ST projection engine - recency-weighted, SOS-adjusted, league-agnostic.

This replaces the old hand-maintained "attack these offenses" list with a data-driven
model. It is deliberately SIMPLER than the player model, because a backtest (weeks 7-10,
n=114 per league) showed what actually predicts weekly D/ST scoring:

    predictor                     GG     DyNasty  GLORP
    opponent generosity          +0.13   +0.22    +0.15   <- the signal
    defense's own recent form    -0.05    ~         ~      <- essentially none
    full two-sided log5 model    +0.04   +0.20    +0.14   <- no better, often worse

Weekly D/ST scoring is mostly noise (a defensive TD is 6 pts and near-random), and the
one thing that carries week to week is the OPPONENT - how much D/ST production an offense
surrenders. So we project a streamer as roughly what an average defense scores against
that offense, recency-weighted and strength-of-schedule-adjusted, with only a light tilt
for the defense's own quality (which helps a little in the points/yards-allowed leagues
and not at all in GG; a single 0.3 weight is near-optimal for all three):

    proj_pts(D vs O) = adj_off_allowed[O] + def_weight * (adj_def_form[D] - league_avg)

  * off_allowed[O]  = D/ST fantasy pts (IN THIS LEAGUE'S SCORING) that offense O surrenders
                      per game, recency-weighted
  * def_form[D]     = D/ST fantasy pts D itself puts up per game, recency-weighted
  * adj_*           = divided by the strength of the opponents faced (SOS: generosity racked
                      up against bad offenses / weak defenses is discounted)
  * league_avg      = per-team-game mean D/ST points across the window

Everything comes from ONE free source: Sleeper's weekly DEF stat lines
(api.sleeper.com/stats/nfl/<season>/<week>?position[]=DEF). Each line carries what that
defense generated AND the `opponent` it faced, so a week's lines joined on opponent give,
for every team, both its own output and (from its opponent's line) what it surrendered.
Scoring is league-specific, so `build` takes the caller's scoring function - see
dst_streamer.py, which wires this to Gridiron Grind / DyNasty / Eat GLORP.

Honest expectation: even the best predictor here is weak (r ~0.13-0.22). This finds the
better side of a coin flip, not a sure thing - which is exactly why swapping weekly and
chasing the matchup (not holding a "good defense") is the right play. Std-lib only.
"""
import urllib.request, urllib.error, json, time, math

STATS = 'https://api.sleeper.com/stats/nfl'
STATE = 'https://api.sleeper.app/v1/state/nfl'

ALL_TEAMS = {'ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB','HOU',
             'IND','JAX','KC','LV','LAC','LAR','MIA','MIN','NE','NO','NYG','NYJ','PHI',
             'PIT','SEA','SF','TB','TEN','WAS'}
_FIX = {'JAC':'JAX','LVR':'LV','WSH':'WAS','LA':'LAR','OAK':'LV','SD':'LAC','STL':'LAR'}

# Box-score components we project. Counting stats are log5'd from both sides; the two
# "allowed" components (points, yards) are projected as continuous values for tier scoring.
COUNTING = ['sack', 'int', 'ff', 'fum_rec', 'def_td', 'safe', 'blk_kick']
ALLOWED  = ['pts_allow', 'yds_allow']
# Rare events get shrunk hard toward league mean (one fluky return TD shouldn't crown a D).
RARE = {'def_td', 'safe', 'blk_kick'}


def norm(ab):
    ab = (ab or '').upper()
    return _FIX.get(ab, ab)


def _get(url, tries=4):
    last = None
    for a in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})))
        except urllib.error.URLError as e:
            last = e
            time.sleep(1.5 * (a + 1))
    raise SystemExit(f"Sleeper stats API unavailable ({last}). Wait a minute and retry.")


def current_week():
    st = _get(STATE)
    return int(st.get('week') or st.get('display_week') or 1), str(st.get('season') or '2026')


def _row_components(stats):
    """Pull a defense's generated components out of one Sleeper DEF stat line."""
    g = lambda k: float(stats.get(k) or 0.0)
    return {
        'sack':      g('sack'),
        'int':       g('int'),
        'ff':        g('ff'),
        'fum_rec':   g('fum_rec'),
        # Sleeper's DEFENSIVE scoring TDs. NOTE: the bare `td` key is the team's OFFENSIVE
        # TDs (TDs the team scored on offense), not defensive - do not include it.
        'def_td':    g('def_td') + g('def_st_td') + g('fum_rec_ez_tds'),
        'safe':      g('safe'),
        'blk_kick':  g('blk_kick'),
        'pts_allow': g('pts_allow'),
        'yds_allow': g('yds_allow'),
    }


def load_week(season, week):
    """{team: {'gen': {...}, 'opp': ABBR}} for one week, or {} if not played yet."""
    try:
        rows = _get(f'{STATS}/{season}/{week}?season_type=regular&position[]=DEF')
    except SystemExit:
        return {}
    out = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        tm = norm(r.get('team') or r.get('player_id'))
        st = r.get('stats') or {}
        if tm not in ALL_TEAMS or not st:
            continue
        out[tm] = {'gen': _row_components(st), 'opp': norm(r.get('opponent'))}
    return out


def _wmean(pairs):
    """Weighted mean of (value, weight) pairs; None if no weight."""
    num = sum(v * w for v, w in pairs)
    den = sum(w for _, w in pairs)
    return (num / den) if den else None


def build(season, through_week, score_fn, lookback=6, half_life=2.5, def_weight=0.3,
          sos_frac=0.5):
    """Recency-weighted, SOS-adjusted D/ST point model through `through_week`.

    `score_fn(components, None) -> fantasy points` scores one game's box-score components in
    the target league's rules (so the model is league-specific). Returns:
      off_allowed[O] -> adjusted D/ST points offense O surrenders per game  (the signal)
      def_form[D]    -> adjusted D/ST points defense D puts up per game       (light tilt)
      lg             -> league per-team-game average D/ST points
      def_weight     -> how much def_form shifts the projection (see project())

    lookback  : completed weeks of form to pull.
    half_life : recency weight = 0.5 ** (age_in_weeks / half_life). Smaller = trendier.
    """
    weeks = range(max(1, through_week - lookback + 1), through_week + 1)
    data = {w: load_week(season, w) for w in weeks}
    data = {w: d for w, d in data.items() if d}            # drop weeks not yet played
    weeks = sorted(data)
    if not weeks:
        raise SystemExit("No completed-week DEF stats available to build the model.")
    newest = max(weeks)
    wt = lambda w: 0.5 ** ((newest - w) / half_life)

    # Each team-week -> this defense's D/ST fantasy points in the league's scoring.
    pts = {w: {tm: score_fn(rec['gen'], None) for tm, rec in data[w].items()} for w in weeks}
    lg = _wmean([(pts[w][tm], wt(w)) for w in weeks for tm in pts[w]]) or 0.0

    own, opps_faced = {t: [] for t in ALL_TEAMS}, {t: [] for t in ALL_TEAMS}  # defense role
    surr, def_faced = {t: [] for t in ALL_TEAMS}, {t: [] for t in ALL_TEAMS}  # offense role
    for w in weeks:
        for tm, rec in data[w].items():
            opp = rec['opp']
            own[tm].append((pts[w][tm], wt(w)))
            if opp in ALL_TEAMS:
                opps_faced[tm].append(opp)
                surr[opp].append((pts[w][tm], wt(w)))       # opp's offense surrendered pts[tm]
                def_faced[opp].append(tm)

    raw_form = {t: (_wmean(own[t]) if own[t] else lg) for t in ALL_TEAMS}
    raw_surr = {t: (_wmean(surr[t]) if surr[t] else lg) for t in ALL_TEAMS}

    # SOS, one iteration. An offense's surrendered points are inflated if it faced strong
    # defenses (high raw_form); divide that out. A defense's own form is inflated if it faced
    # generous offenses (high raw_surr); divide that out. Additive centering, clamped.
    def adj(raw_self, faced, strength):
        out = {}
        for t in ALL_TEAMS:
            if faced[t]:
                opp_str = sum(strength[o] for o in faced[t]) / len(faced[t])
                shift = max(-6.0, min(6.0, opp_str - lg))   # how tough a slate, in points
            else:
                shift = 0.0
            out[t] = raw_self[t] - sos_frac * shift          # partial correction (tuned)
        return out

    off_allowed = adj(raw_surr, def_faced, raw_form)         # harder D faced -> credited up
    def_form    = adj(raw_form, opps_faced, raw_surr)        # softer O faced -> discounted
    return {'off_allowed': off_allowed, 'def_form': def_form, 'lg': lg,
            'def_weight': def_weight, 'weeks': weeks}


def project(model, defense, offense):
    """Projected D/ST fantasy points for `defense` facing `offense`, in the league's scoring."""
    return model['off_allowed'][offense] + model['def_weight'] * (model['def_form'][defense] - model['lg'])


# --- tier scoring helpers (used by the per-league scoring adapters) ------------------

def tier_points(value, tiers, sd):
    """Expected points from a stepped tier table given a continuous projected `value`.

    tiers: list of (low, high, points) with high=None for the open top bucket. Instead of
    reading one bucket off the point estimate (knife-edge), spread `value` with a normal of
    width `sd` and sum points * P(value in bucket) - a defense projected near a boundary
    gets a blend, which is how these outcomes actually behave.
    """
    def cdf(x):
        return 0.5 * (1 + math.erf((x - value) / (sd * math.sqrt(2))))
    exp = 0.0
    for lo, hi, pts in tiers:
        p_lo = cdf(lo - 0.5) if lo > 0 else 0.0
        p_hi = cdf(hi + 0.5) if hi is not None else 1.0
        exp += pts * max(0.0, p_hi - p_lo)
    return exp


def prob_shutout(pts_allow_proj, sd=9.0):
    """P(points allowed == 0) ~ normal mass below 0.5, for GG's +10 shutout bonus."""
    return max(0.0, 0.5 * (1 + math.erf((0.5 - pts_allow_proj) / (sd * math.sqrt(2)))))
