# CLAUDE.md — Gridiron Grind Draft Prep (2026)

Project context for Claude Code. This folder holds the data, analysis, and the live
draft-day tool for Ian's long-running fantasy football league ("Gridiron Grind").

## What this project is
Ian is a manager in a 12-team, full-PPR **auction** keeper league. Each year he does
heavy pre-draft prep by hand. This project automates it: pull all league history, build
an analysis workbook + value model, and provide a **live draft-day dashboard** that keeps
him on plan during the auction (he tends to go off-script mid-draft).

- **League format:** 12 teams, full PPR. Starters: QB, 2×RB, 2×WR, TE, FLEX(RB/WR/TE), K, D/ST. 16 roster spots. **$200 auction** budget.
- **Keepers:** ONE keeper in 2026 (was two in prior years). Keeper cost = last year's price **+ $7**. Waiver-wire players cost **$1** base (then +$7 if kept). Confirm keeper count each year.
- **Platforms:** League history/scoring/FAAB/trades live on **Fleaflicker** (league `78455`, public JSON API). The auction draft + projections/values live on **ESPN** (league `216270753`, needs login). League moved to ESPN auction in 2023.

## Owner map (keep in sync)
Fleaflicker handle -> name: BurrowingMule=Derek, Ryan505=Ryan, Brotesk=Alec, Iyano1911=Ian,
rickbraaten=Rick, Chance145=Chance, ajg21=Andy, madmax101010=Dawkins, JGERK=Gerk,
SimonMiller=Simon, Joles=Joles, zach_montoya=Zach, levp=Peter.
**ESPN display names differ** — Ian is `IanP123` (teamId 12). The draft-day tool matches
"my team" by substring against the ESPN display name, so it must be an ESPN name.

## Repo layout (draft_prep/2026/)
- `Draft_Day_Tool.html` — the live auction dashboard (single self-contained file). **Main deliverable.**
- `serve_draft.py` — tiny local server: serves the tool + relays the live draft (POST/GET `/draft`, CORS-open).
- `Start_Draft_Tool.bat` — double-click launcher: starts the server via Ian's venv Python and opens the tool. **PYEXE is hard-coded** to `C:\Users\nai19\Documents\GitHub\venv_ianrosadodotcom\Scripts\python.exe` (update if the venv moves).
- `source_data/` — raw inputs: standings, draft (snake 2013-22), espn_draft (auction 2023-25 w/ bid+keeper), faab_claims (2021-25), trades, current_rosters, proj_hist, player_values_2026.
- `analysis/` — derived outputs: champions, manager_alltime, luck_*, h2h_matrix, trades_bymanager, faab_by_manager, keeper_analysis, predicted_keepers, league_adjusted_values, draft_board_2026, overunderpay, strategy_success, scenarios, and `trend_report.md`.
- `scripts/analyze_strategy.py` — recomputes strategy correlations + over/underpay by tier, writes `trend_report.md`. Re-run yearly.
- `scripts/build_wb.py` — rebuilds `Gridiron_Grind_History.xlsx` (21 tabs).
- `scripts/high_scores.py` — **history query**: scans every scoring period of every season (regular season + postseason) on Fleaflicker and lists every team-week at/above a `--threshold` (default 200) with the full starting lineup + points-by-player, plus opponent/result. Public API, std-lib only. All GG matchups live on Fleaflicker for *every* year (the 2023 ESPN move was draft-only), so it's one continuous 2009→current record. As of 2026 there are three 200+ weeks: GERK 200.5 (2022 Wk8), Bijannaise 224.25 (2024 Wk17 playoffs), Mr. Kim's Kans 225.7 (2026 Wk5). `python high_scores.py [--threshold 200] [--season N | --from 2009 --to 2026] [--no-rosters]`.
- `scripts/waiver_bids.py` — **in-season** waiver helper: pulls the live Fleaflicker free-agent pool + each team's roster needs + every manager's historical FAAB tendencies (from `faab_claims.csv`) so you can size bids. `python waiver_bids.py [--top 40]`.
- `scripts/dst_streamer.py` + `scripts/dst_model.py` — **in-season, multi-week D/ST streamer for ALL THREE leagues** (`--league gg|dynasty|glorp`), projection-driven, **no static lists**. `dst_model.py` is a shared engine; `dst_streamer.py` wires it to each league's availability, schedule, and **scoring pulled live each run** (Fleaflicker `FetchLeagueRules` → GG's sack 2 / INT 2 / FF 2 / FR 1 / safety 7 / def-TD 6 / +10 shutout; Sleeper `scoring_settings`; ESPN `mSettings` statId overrides — so a rules change is picked up automatically). **The model** (see the big docstring in `dst_model.py`): a backtest (weeks 7–10, n=114/league) showed weekly D/ST scoring is mostly noise and the *only* predictor that carries week-to-week is **opponent generosity** — how many D/ST points an offense surrenders (GG r≈.13, DyNasty .22, GLORP .15); the defense's own recent form and a full two-sided log5 component model add ~nothing. So each streamer is projected as *what an average D scores vs that offense*, **recency-weighted** (half-life 2.5 wks) and **SOS-adjusted** (gentle, `sos_frac` 0.25 — full SOS over-corrected on the sample), plus a small **per-league `def_weight`** tilt for the defense's own quality (`gg` 0.0 — GG barely scores pts/yds allowed so defense quality doesn't transfer; `dynasty` 0.4, `glorp` 0.3 — they score pts+yds allowed heavily). All inputs come from ONE free source: Sleeper weekly DEF stat lines (`api.sleeper.com/stats/nfl/<season>/<week>?position[]=DEF`), which carry each D's output **and** its `opponent`, so a week joined on opponent gives both what each team's D generated and what its offense surrendered. **Caveat baked into the output header:** even the best predictor is weak (r≈.1–.22) — this finds the better side of a coin flip, which is exactly why you stream weekly and chase the matchup instead of holding a "good defense." Output matches the other streamers: BEST AVAILABLE EACH WEEK (top 5) + MULTI-WEEK HOLDS + YOUR ROSTERED. ⚠️ Known Sleeper-stats gotcha: the bare `td` key is the team's **offensive** TDs, not defensive — def TDs are `def_td`/`def_st_td`/`fum_rec_ez_tds`. `python dst_streamer.py --league gg [--week N] [--ahead 2] [--lookback 6] [--half-life 2.5] [--all]`. (ESPN is private → needs `.espn_cookies.json`, same as the other ESPN scripts. Replaced the old per-league `defense_streaming.py` / `sleeper_defense_streaming.py` / `espn_defense_streaming.py`.)
- `scripts/waiver_bids.py` uses the public Fleaflicker API (std-lib only) and can rate-limit on rapid repeat runs — wait a minute if you get the "API unavailable" message.
- `scripts/sleeper_waiver.py` — **in-season** waiver helper for DyNasty (Sleeper): generalizes the roster-diff trick to all positions (owned = union of every roster's players; available = the `/players/nfl` pool minus owned, cached ~daily in the OS temp dir), ranks the best available skill players by Sleeper's leaguewide trending-add signal, and prints Team L.O.B's roster by position (flagging spots below a minimum depth). `python sleeper_waiver.py [--pos RB] [--limit 25]`.
- `scripts/usage_trends.py` — **underlying-usage reader** for any NFL player, any league: pulls recent weekly opportunity from Sleeper's free stats endpoint (`api.sleeper.com/stats/nfl/<season>/<week>`) and prints snap share, carry share, target share, air yards, **WOPR** (`1.5·tgt-share + 0.7·air-share`), efficiency, fantasy points, and a trend read (role rising / steady / fading). Built because season-long rank is a lagging number that buries missed games and role changes — e.g. Jonah Coleman reads rank ~238 but is a 66%-snap lead back ascending. Use it before any buy/sell/start-sit/trade call. `python usage_trends.py "Jonah Coleman" "Puka Nacua" [--weeks 5]`. Methodology (which metrics predict production and why, data sources, guardrails) lives in the **`fantasy-analytics` skill** (`.claude/skills/fantasy-analytics/`), which should drive every waiver/trade/start-sit decision.
- `scripts/roster_projection.py` — **rest-of-season + playoff PPG projection** for your roster in any of the three leagues (`--league gg|dynasty|glorp`). Per player: `baseline` = recency-weighted PPG (`0.6·last3 + 0.4·season`), times a **defense-vs-position multiplier** = mean over all player-games vs a defense of `(game pts / that player's season avg)`, clamped 0.6–1.5 (so it's *points allowed over expected*, controlling for the quality of players each defense faced — not raw points allowed). Projects each remaining week and averages over the rest of the regular season and the league's playoff weeks (GG 15–17, GLORP 15–16, DyNasty read from Sleeper `playoff_week_start`). One engine, three roster sources (Fleaflicker / Sleeper player_ids / ESPN mRoster, names matched to Sleeper ids); scoring is a full/half-PPR approximation from Sleeper points (GG/GLORP `pts_ppr`, DyNasty `pts_half_ppr`). Models opportunity + matchup only — not injuries or game-script — and the playoff numbers (two months out) are the softest. `python roster_projection.py --league gg`.
- `scripts/espn_waiver.py` — **in-season** waiver helper for Eat GLORP (ESPN): prints your roster by position (flagging thin spots) then the best available free agents by **% rostered** (with weekly trend), via ESPN's `kona_player_info` view + an `X-Fantasy-Filter` header for FREEAGENT/WAIVERS status. `python espn_waiver.py [--pos RB] [--limit 25]`.
- **ESPN private-league auth:** Eat GLORP is a *private* league, so the ESPN-reading scripts (`espn_waiver.py` and `dst_streamer.py --league glorp`) need your `espn_s2` + `SWID` cookies. They load from `ESPN_S2`/`ESPN_SWID` env vars or a local `scripts/.espn_cookies.json` (copy `.espn_cookies.example.json`). That file is **git-ignored** (`scripts/.gitignore`) — never commit it. Cookies expire; on a 401 the scripts tell you to refresh them from the browser. ESPN `lm-api-reads.fantasy.espn.com` read endpoints work with these; the CDN scoreboard needs no auth.
- `Gridiron_Grind_History.xlsx` — the full history workbook (generated artifact).
- `docs/FINDINGS_SUMMARY.md` — plain-language takeaways w/ confidence tags.
- `docs/REFRESH_GUIDE.md` — step-by-step to add a new season and re-run everything.

## Draft Day Tool — architecture
Single HTML file, vanilla JS, state persisted in `localStorage` key `gg_draft_2026_v2`.
Key modules (all in the one `<script>`):
- **Value model:** each player has `f` (fair $), `lp` (league-adjusted price), `e` (raw ESPN auction value), `k` (predicted keeper owner). Embedded `PLAYERS` array (300 players). **`f` is now a market blend** (mean of ESPN + external sites, currently FFToday) — `scripts/reblend_values.py`. The old VOR-on-projections `fairValue` ran ~15-20% hot vs. the real auction (the league bleeds budget into $1-sleeper overpays, draining the stud tier), so raw VOR was replaced with the blend. VOR `fairValue` is still kept side-by-side in `league_adjusted_values.csv` for reference.
- **Keepers (`KEEPERS`):** editable list of rivals' kept players `{n, team, cost}` — **update when keepers lock in** (`team` = a substring of that team's ESPN name so it matches the live feed). Kept players get `status()==='kept'`: hidden from the board / tier board / competition / datalist / inflation pool. `leagueTeams()` builds the normalized 12-team view — each team's synced auction picks **plus its keeper** (roster slot + cost), plus teams not yet in the feed — so keepers correctly reduce that team's open positional slots and budget, and the league-wide needs/inflation math. My own keeper stays on my roster across syncs (the feed carries auction wins only).
- **Plans (`PLANS`):** A RB-Heavy, B Two-Stud, C Balanced — a **disjoint** $ split across lineup slots that sums to $200: QB, RB (2 STARTERS), WR (2 starters), TE, **FLEX**, **BENCH**, K, D/ST. `slotSpend()` (via `assign()`) buckets each pick into its slot, so flex and bench have their own budget lines instead of hiding inside RB/WR. Drives the budget bars + `planLeft()` guardrails (comp `$ left (adj)` and the verdict use the slot a player would fill — starter, else flex, else bench).
- **Tiers (`SPOOL` / `TIERCUT` / `PTIER`):** starter pool per position (QB12/RB30/WR40/TE12), split into elite/mid/value. RB elite tightened to top 7 (`TIERCUT`). Each plan shops a tier per position (`PTIER`). These are plain constants — tune freely.
- **Inflation (`inflation()`):** applied = `max(realized, forward)`, clamped 0.7–1.8×. *Realized* = what the room has actually paid ÷ fair (tracks a hot/cold room; needs ≥4 picks). *Forward* = (all teams' $ remaining) ÷ (fair value of the players still needed) — captures that all budget MUST be spent on the pool, so it floors prices at ~1.14× from pick 1 (fixes the cold-start "prices look low"). Teams not yet in the sync feed are topped up as full $200/16 spots via `NTEAMS`. Feeds both the verdict value-cap and the competition projected prices.
- **`posDemand(pos)`:** per-position premium (up to +35%) from how many rival teams still need the position AND have ≥$3 left. Multiplies into both the competition projected price and the verdict value-cap.
- **Strategy Advisor (`posInflation()` / `recommendPlan()` / `renderAdvisor()`):** the live "when to switch plans" call — a banner under the top stats. `posInflation()` = realized inflation PER position (sold $ ÷ fair). `recommendPlan()` compares RB vs WR: if RBs are clearing ≥0.15 hotter than WR (and ≥1.15×), or you still need RB starters but 0 elite/mid RB is left in budget, it recommends **Plan C** (stop chasing elite RBs, go balanced + RB volume); if WR is the hot tier, it points back to **Plan A**. When the recommendation differs from the current plan it turns red with a one-click **Switch** button. This is the antidote to tunnel-visioning on elite RBs.
- **Verdict engine (`renderVerdict`):** "on the block" read = value cap (`fair × inflation × posDemand`) ∧ affordability cap; warns on sleeper trap (league overpays $1 fliers ~2.6×), TE/QB overpay, off-plan, above-value.
- **Competition panel (`renderComp`):** per position — **tms need** (teams still short a starter) and **slots open** (total unfilled starter slots), both league-wide across all `NTEAMS` (incl. teams not yet in the feed; starters only, excl. FLEX) so you can weigh demand against the tier supply; projected clearing price of best player left (`fair × inflation × posDemand`); how many of YOUR plan-tier remain affordable (+ count in next tier down); **$ left (adj)** = plan budget for the spot rescaled to actual money via `planLeft()` (overspend one position and the rest drop, capped at target); and a state-aware **read** (set ✓ / on track / punt–wait / last-in-tier / drop-a-tier / priced-out — no longer flags punts as "behind"). The plan **budget bars** (`renderBars`) show `$ spent · $ left`. Below the table is a **tier board**: the top-2 still-populated tiers per position (rolls elite→mid→value as they empty) listing the actual remaining players with projected prices — dimmed = over your current cap, ◄ = your plan's target tier.
- **Live sync:** three input paths, most-to-least automated:
  1. **⚡ GG Live Sync** bookmarklet — click **once at the start** of the ESPN draft. It hooks the live draft **websocket** and POSTs each sale to `http://localhost:8000/draft` as it happens; the tool polls `/draft` every 3s and auto-imports (only when served over http, i.e. launched via Start_Draft_Tool). Zero further clicks.
  2. **📌 GG Draft Sync** bookmarklet (no-server fallback) — arms the same websocket feed; each click copies the picks-so-far to the clipboard for the **📋 Import from clipboard** button.
  3. Manual paste box, or type player+price and Won/Lost.
  - **How the live feed works (learned Aug 2026, verified in a mock):** during a live auction ESPN's REST `mDraftDetail`/roster endpoints stay EMPTY — picks stream over `wss://fantasydraft.espn.com/game-1/league-<id>/JOIN` as space-delimited text. The event that matters is `SOLD <teamId> <playerId> <?> <price> <?>` (teamId is the real ESPN teamId — NOT the draft-slot column number; price is field #4). Bookmarklets dual-hook `WebSocket` (constructor override for reconnects + `send` patch for the current socket), map `teamId`→owner via `?view=mTeam` and `playerId`→name via `?view=kona_player_info`, accumulate, and emit the `{teams:[{owner,picks:[{n,p,price,keeper}]}]}` shape the tool imports. Anything sold before you click is missed → click early, type early picks by hand.

## How to run (draft day)
1. Double-click `Start_Draft_Tool.bat` → server window (keep OPEN) + browser opens `http://localhost:8000/Draft_Day_Tool.html`.
2. Drag **⚡ GG Live Sync** to the bookmarks bar (one time — re-drag if the tool's bookmarklet code changed).
3. Set Plan + confirm keeper (Puka pre-loaded $58). Click ⚡ **once, right when the ESPN draft room opens** — from then on every sale flows in automatically; keep the ESPN tab open.
Fallbacks if the server isn't running: open the HTML directly + use 📌 copy bookmark (click to refresh) + 📋 Import from clipboard, or manual entry.

## Key findings (see docs/FINDINGS_SUMMARY.md for detail + confidence tags)
- Draft **RB** is the best (weak) predictor of wins (r≈+0.32, n=36); paying up for TE/QB hurts.
- League **overpays $1 sleepers ~2.6×**, pays ~fair for studs, slight discount mid-tier → mid-tier is the value zone.
- **TE has the SMALLEST** elite-to-replacement drop-off; the real cliff is RB/WR (debunks the "TE premium" instinct).
- Save FAAB for late; volume > big splashes.
- Strategy signals are small-sample (3 auction seasons) — treat as tilts, not laws. `trend_report.md` tracks whether they firm up.

## 2026 decisions
- **Keeper: Puka Nacua ($58)** — keep for the locked elite-WR1 certainty, NOT for surplus. The old "+18 surplus" was an artifact of the hot VOR model; at blended market value Puka is ~$55, so keeping is ~break-even (−$3). Re-checked every other rostered player against market — none clears positive (Kenneth Walker −$11, Ja'Marr Chase −$16 at his $70 cost, McLaurin −$15); it's Puka or keep-none. Ian is at a keeper disadvantage: rivals lock real bargains (Simon/JSN +$16, Gerk/Rice +$16, Alec/Olave +$15, Dawkins/Bowers +$12).
- **Plan:** RB-forward, WR2 efficient, punt QB/TE ($7 TE), save FAAB for the stretch.

## Annual refresh (see docs/REFRESH_GUIDE.md)
Append the new season to `source_data/*.csv`, run `scripts/analyze_strategy.py` then
`scripts/build_wb.py`, re-pull that year's rosters/projections/values, recompute the
forward-looking prep, and re-inject the tool's `PLAYERS` array. Then refresh the
market blend: pull external auction values into `source_data/auction_values_external.csv`
(update the `FFTODAY` dict in `scripts/reblend_values.py`) and run
`scripts/reblend_values.py` — it rewrites the tool's `f`/`lp`, the keeper CSVs, and the
draft board from the ESPN+external blend. Then hand-retune `analysis/scenarios.csv`
targets and the tool's `PLANS` position budgets to the new market — and drop any target
that `predicted_keepers.csv` shows a rival keeping (kept players are off the auction board).

## Gotchas / constraints learned
- Fleaflicker `recordPostseason.rank` is unreliable — derive champions from the `isChampionshipGame` winner instead.
- ESPN preseason `auctionValueAverage` is deflated — primary value model is VOR-on-projections; ESPN `e` kept side-by-side only.
- Browsers **block a web page from opening a local file**, so the tool must be served (localhost) for true one-click; the `file://` "open" bookmarklet was abandoned.
- Windows `py`/`python` are often the **Microsoft Store stub** — the launcher points straight at the venv python to avoid it.
- ESPN **live auctions are NOT exposed via the read API** — `mDraftDetail.picks` and rosters stay empty until the draft finalizes; live picks come only over the draft websocket (see Live sync above). REST is still fine for a post-draft record.
- ESPN `players_wl` returns an inconsistent page size (saw 50 vs 11,610) and ignores the `filterIds` header; use `?view=kona_player_info` for a stable full player map, and expect rate-limiting under rapid calls.
- Opening the ESPN draft in a **second/duplicate tab** demotes it — the shadow tab's websocket goes stale even though the DOM keeps updating. Test live sync in a single tab.
- `git` could not run from the sandbox (no access to the repo's `.git` + no user creds) — commits/PRs happen on Ian's machine.

## Next steps / backlog
- [x] **Live sync working (Aug 2026)** — rebuilt ⚡/📌 on the draft websocket (`SOLD` events) after confirming REST is empty mid-draft; verified pick/team/price decode against a live mock. Still TODO: confirm end-to-end POST reaches the running server on Ian's drafting laptop, and check keeper (Puka) vs the pre-loaded $58 keeper.
- [ ] **Draft-night opening statement** — a fun, data-driven trash-talk/storyline doc (rivalry H2H, luck, best/worst FAAB picks). Deferred repeatedly; still wanted.
- [ ] Tune tiers after live use (`SPOOL`/`TIERCUT`/`PTIER`) if elite/mid lines feel off.
- [ ] Optional: script the ESPN/Fleaflicker pulls into `scripts/` so the yearly refresh is one command (currently browser-driven).
- [ ] Consider auto-refresh of `PLAYERS` from `player_values_2026.csv` at server start (so the tool never drifts from the data).
- [ ] After the 2026 season, add it to the CSVs and watch whether the RB-draft / late-FAAB / sleeper-overpay signals hold.

## Conventions
- Full PPR scoring; $200 auction; one keeper (2026); keeper cost = last price + $7; waiver base $1.
- Value units: `f`/`lp`/`e` are dollars. Tiers by fair value. Server port 8000. localStorage key `gg_draft_2026_v2`.
