# Annual Refresh Guide — adding a new season & re-checking the story

Goal: after a season ends, add that year's data, re-run the analysis, and see if the
strategy findings hold, strengthen, or shift. Two data platforms: **Fleaflicker**
(scoring/rosters/FAAB/trades) and **ESPN** (auction draft + projections/values).

League IDs: Fleaflicker `78455` · ESPN `216270753`.
Owner handle -> name: BurrowingMule=Derek, Ryan505=Ryan, Brotesk=Alec, Iyano1911=Ian,
rickbraaten=Rick, Chance145=Chance, ajg21=Andy, madmax101010=Dawkins, JGERK=Gerk,
SimonMiller=Simon, Joles=Joles, zach_montoya=Zach, levp=Peter.
(ESPN display names differ, e.g. Ian = IanP123 — used by the draft-day tool's "my team" field.)

## STEP 1 — Pull the new season (needs a logged-in browser session)
All pulls are JSON APIs hit through the browser (Fleaflicker is public; ESPN needs your login).

Fleaflicker (replace YYYY):
- Standings:  `/api/FetchLeagueStandings?sport=NFL&league_id=78455&season=YYYY`
- Trades:     `/api/FetchTrades?sport=NFL&league_id=78455&filter=TRADES_COMPLETED&result_offset=0` (paginate via resultOffsetNext)
- FAAB:       `/api/FetchLeagueTransactions?sport=NFL&league_id=78455&result_offset=0` (paginate; keep type==TRANSACTION_CLAIM with bidAmount; bids per team in waiverResolutionTeams). Feed is newest-first — page until dates pass the target season. Don't treat a rate-limited/empty page as end-of-feed (use resultOffsetNext).
- Rosters:    `/api/FetchRoster?sport=NFL&league_id=78455&team_id=TID` (per team)
- Games (H2H/luck): `/api/FetchLeagueScoreboard?...&season=YYYY&scoring_period=W` per week
- Player pts (FAAB hit/miss): `/api/FetchLeagueBoxscore?...&fantasy_game_id=GID&scoring_period=W`; points at slot.away/home.viewingActualPoints.value

ESPN (base `https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/YYYY/segments/0/leagues/216270753`):
- Auction draft: `?view=mDraftDetail` (picks: playerId, bidAmount, keeper, teamId) + `?view=mTeam` (team->owner) + names via `/seasons/YYYY/players?view=players_wl` (x-fantasy-filter filterIds)
- Projections & values: `?view=kona_player_info` with header x-fantasy-filter; per player ownership.auctionValueAverage and projected stats (statSourceId==1).

## STEP 2 — Append rows to the source CSVs (in source_data/)
Add ONLY the new season's rows (keep prior years): standings.csv, espn_draft.csv,
faab_claims.csv, trades.csv, proj_hist.csv. Optional: games/boxscore feed H2H/luck.

## STEP 3 — Re-run the analysis
From this folder:
1. `python scripts/analyze_strategy.py`  -> regenerates `analysis/trend_report.md` (correlations POOLED + BY YEAR; over/underpay by tier by year).
2. `python scripts/build_wb.py`           -> rebuilds `Gridiron_Grind_History.xlsx`.

Then read `analysis/trend_report.md` and compare new pooled r-values / the new season's column to prior years:
- Does the **RB-draft** edge stay positive / grow / fade?
- Does **late-FAAB** stay positive? (It went negative in 2025 — one more year will clarify.)
- Does **sleeper overpay (2.6x)** persist?
As n grows past ~50-60 team-seasons, borderline signals (p~0.05-0.15) firm up or wash out.

## STEP 4 — Rebuild the forward-looking draft prep (fresh each year)
Keeper values, league-adjusted prices, predicted keepers, and the draft board need that
year's rosters + projections + auction values: recompute keeper_analysis / predicted_keepers
/ league_adjusted_values / draft_board via the same VOR logic (keeper cost = last year's
price + $7; waiver base $1; confirm keeper count for the year), then refresh the embedded
PLAYERS array in `Draft_Day_Tool.html`.

## Notes
- Scoring is full PPR; roster QB/2RB/2WR/TE/FLEX/K/DST, 12 teams, $200 auction.
- Keep the owner handle->name map above in sync if managers change.
- Strategy findings are small-sample; the point of this refresh is to watch them converge.
