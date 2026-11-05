---
name: fantasy-analytics
description: >-
  Evaluate fantasy football players by their UNDERLYING USAGE and recent trends — snap
  share, carry share, target share, air yards, WOPR, efficiency — instead of season-long
  rank, which is a lagging number that buries missed games and role changes. Use this
  whenever assessing ANY waiver add, trade, drop, or start/sit in Ian's fantasy leagues
  (Gridiron Grind / Fleaflicker 78455, DyNasty / Sleeper, Eat GLORP / ESPN 686982204), or
  whenever asked whether a player is a buy/sell, a good pickup, a breakout, a sell-high, or
  whether a trade is fair. Trigger even when the user just names players and asks "is X for
  Y fair?", "who should I pick up?", "should I start X?", or "is X droppable?" — pull the
  recent opportunity story BEFORE quoting any ranking.
---

# Fantasy analytics: tell the usage story, not the rank

## Why this exists
Season-long fantasy rank is a **lagging, blunt** number. It averages in missed games,
preseason noise, and stale roles, so it systematically misreads exactly the players whose
value is moving — the ones you actually make waiver/trade decisions about. Example that
motivated this skill: **Jonah Coleman** sat at season rank ~238, which reads like a scrub —
but he missed Weeks 1–6 on IR, and on return his snap share went 49% → 66% and his carry
share 50% → 61% in two weeks. He's a **lead back ascending into a feature role**, and his
trade value is legitimately high. The rank told the opposite story.

So: **before you quote a ranking, pull the recent opportunity and tell the story.**

## The metrics that matter (and why)
Opportunity predicts future production better than efficiency does — efficiency describes
what happened, opportunity says what's likely next. Weight them in this order:

- **Target share** (and **WOPR** = `1.5·target-share + 0.7·air-yards-share`) — the best
  forward-looking signal for WR/TE. WOPR **>0.7 is stud territory**, 0.5–0.7 solid, <0.4 thin.
- **Carry share + snap share + goal-line/short-yardage work** — the RB workload picture.
  An RB north of ~**60% snap share** with the backfield's lead carry share is a feature back.
- **The TREND, not the level** — a *rising* snap/carry/target share reveals a role change
  weeks before season rank catches up. This is the whole point. A falling share is a warning
  even if the name is big.
- **Efficiency separates real from empty volume** — yards per route run / targets per route
  run (TPRR ~**20% baseline, 25%+ elite**), yards per carry, yards per target. Use it to tell
  a genuinely good player from one just inheriting volume — but don't let one hot low-volume
  week (noise) outweigh a stable opportunity share (signal).
- **Context** — defense-vs-position and the **Vegas implied team total** for the weeks that
  matter (shootout = passing volume; favored blowout = rushing/game-script).

## Workflow — do this before any buy/sell/start-sit call
1. **Pull recent usage** for the player(s) in question:
   `python draft_prep/2026/scripts/usage_trends.py "Player Name" ["Other Name"] [--weeks 5]`
   It reads Sleeper's free weekly stats and prints snap %, carry share, target share, air
   yards, WOPR, efficiency, fantasy points, and a trend read (role rising / steady / fading).
2. **Explain a low/high rank** — if a season rank looks off, check *why*: missed games (rank
   understates current role — a buy signal) vs. genuinely bad usage (rank is right).
3. **Layer the matchup** — defense-vs-position + implied team total for the relevant weeks
   (this week for start/sit; Weeks 15–16/17 for playoff-schedule trade targets).
4. **Tell the story, then recommend** — 2–3 sentences on role trajectory + opportunity +
   what it means, *then* the call. Never lead with a season rank in isolation.

## Data sources (the aides)
- **`usage_trends.py`** (Sleeper weekly stats) — snaps, carry/target share, air yards, WOPR,
  efficiency, trend. **Primary tool.** Works for any NFL player in any of the three leagues.
- **Sleeper stats endpoint** directly for custom pulls:
  `https://api.sleeper.com/stats/nfl/<season>/<week>?season_type=regular` — per-player stat
  lines (`off_snp`, `tm_off_snp`, `rush_att`, `rec_tgt`, `rec_air_yd`, efficiency splits).
- **ESPN `percentChange`** (weekly change in % rostered, from `espn_waiver.py`) — market
  momentum: who the industry is adding/dropping right now.
- **nflverse / `nfl-data-py`** — gold-standard deeper metrics (routes run, true YPRR, EPA,
  red-zone touches) when the Sleeper fields aren't enough. Heavier (data downloads); reach
  for it only when a decision genuinely hinges on route-level or red-zone data.
- **Web search** for the injury/depth-chart news that *explains* a usage change (confirm the
  "why" behind a rising or falling role before acting on it).

## Guardrails (lessons learned the hard way on this project)
- **Never value a player on name/reputation or a prior season.** Use 2026 production and
  current role only. (Repeated misses here: Brian Thomas Jr. assumed a stud while near-cut;
  Marvin Harrison Jr. assumed on Arizona when he's on Houston; Travis Etienne assumed a JAX
  workhorse when he's an injured NO committee back.)
- **A low season rank is usually missed games, not a bad role** — always verify against the
  last few weeks before calling someone droppable or a bad trade target.
- **Opportunity is more stable and predictive than efficiency** — a hot efficiency spike on
  low volume is noise; a rising opportunity share is signal.
- **In 1-QB leagues, QBs are devalued** (streamable off waivers), so discount QB value in
  trades accordingly — and don't flag a single-QB roster as a "need" ([[no-backup-qb-1qb-leagues]]).
