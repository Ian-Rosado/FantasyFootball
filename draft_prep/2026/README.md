# Gridiron Grind — 2026 Draft Prep

Tools and analysis for the Gridiron Grind fantasy football auction draft
(ESPN league `216270753`, history from Fleaflicker league `78455`).

## Draft-day tool (the main event)

`Draft_Day_Tool.html` — a live auction dashboard: budget/roster tracker, per-position
budget bars vs a chosen plan (A RB-Heavy / B Two-Stud / C Balanced), an "on the block"
verdict engine, a value board (VOR-on-projections + league-adjusted prices), a positional
competition panel (who still needs what, projected clearing price of the best player left,
and how many of *your* tier remain within budget), and live sync from the ESPN draft.

### Run it with live ESPN sync (recommended)
1. Double-click **`Start_Draft_Tool.bat`** — it launches `serve_draft.py` (a tiny local
   server) and opens the tool at `http://localhost:8000/Draft_Day_Tool.html`.
   *(The .bat points at a local Python venv; edit the `PYEXE` line if your Python moves.)*
2. In the tool, expand "Show / install the sync bookmarklet" and drag **⚡ GG Live Sync**
   to your bookmarks bar.
3. During the draft, click **⚡ GG Live Sync** on your ESPN tab every few picks. The tool
   updates itself within a few seconds — no copy/paste.

### Run it without a server (fallback)
Open `Draft_Day_Tool.html` directly, use the blue **GG Draft Sync** bookmark (copies the
draft), then click **📋 Import from clipboard** in the tool. Manual entry (type player +
price, Won/Lost) always works too.

## Analysis & data
- `source_data/` — raw inputs (standings, drafts, FAAB, trades, projections, values).
- `analysis/` — derived outputs (records, luck, H2H, keeper values, league-adjusted prices,
  over/underpay by tier, strategy correlations, predicted keepers, draft board, scenarios)
  plus `trend_report.md`.
- `scripts/analyze_strategy.py` — recomputes the strategy correlations + over/underpay,
  writes `trend_report.md`. Re-run after adding a new season.
- `scripts/build_wb.py` — rebuilds `Gridiron_Grind_History.xlsx`.
- `docs/FINDINGS_SUMMARY.md` — the plain-language takeaways.
- `docs/REFRESH_GUIDE.md` — how to add next season's data and re-run everything.

## Key 2026 decisions (see docs for detail)
- **Keeper:** Puka Nacua ($58) — highest surplus on the roster (+18 value over cost).
- **Plan:** RB-forward; WR2 efficient; punt QB/TE; save FAAB for the stretch run.
