#!/usr/bin/env python3
"""Pull NFL betting lines (spread + over/under) for a given week from ESPN.

ESPN's public scoreboard API republishes DraftKings lines, so this gives us the
DK numbers through a stable, no-auth endpoint. Output is a clean table plus
CSV/JSON files you can eyeball before pushing anything into the Google Form.

Usage:
    python pull_lines.py                 # auto-detect the current week
    python pull_lines.py --week 3        # a specific regular-season week
    python pull_lines.py --week 1 --season 2026 --seasontype 2
    python pull_lines.py --week 3 --out-dir ./out   # also write CSV + JSON

seasontype: 1=preseason, 2=regular season (default), 3=postseason
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone

import requests

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
# NOTE: ESPN's edge (Akamai) blocks browser-spoofed User-Agents with a 403 but
# lets the default python-requests UA through. So we deliberately send NO custom
# User-Agent here. Don't "helpfully" add a Mozilla UA — it will break the call.
HEADERS = {}


def fetch_scoreboard(season=None, week=None, seasontype=2):
    """Fetch the ESPN scoreboard. With no season/week, ESPN returns the current slate."""
    params = {}
    if season is not None:
        params["dates"] = season
    if week is not None:
        params["week"] = week
        params["seasontype"] = seasontype
    resp = requests.get(SCOREBOARD_URL, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def parse_game(event):
    """Pull one game's matchup + odds out of an ESPN event object.

    Returns a dict; `spread`/`over_under` are None when ESPN hasn't posted a line
    yet, so the caller can flag the game rather than silently dropping it.
    """
    comp = event["competitions"][0]
    competitors = comp["competitors"]
    home = next(c for c in competitors if c["homeAway"] == "home")
    away = next(c for c in competitors if c["homeAway"] == "away")

    home_abbr = home["team"]["abbreviation"]
    away_abbr = away["team"]["abbreviation"]

    row = {
        "date_utc": event.get("date"),
        "away": away_abbr,
        "away_name": away["team"].get("displayName"),
        "home": home_abbr,
        "home_name": home["team"].get("displayName"),
        "matchup": f"{away_abbr} @ {home_abbr}",
        "spread": None,        # e.g. "BUF -3" or "PK"
        "favorite": None,      # team abbr favored, or None for pick'em
        "spread_points": None, # numeric magnitude, e.g. 3.0
        "over_under": None,
        "provider": None,
    }

    odds_list = comp.get("odds") or []
    if odds_list:
        odds = odds_list[0]
        row["provider"] = (odds.get("provider") or {}).get("name")
        details = odds.get("details")  # "BUF -3", "PK", "EVEN", ...
        row["spread"] = details
        row["over_under"] = odds.get("overUnder")

        if details and details.upper() not in ("PK", "EVEN", "EVEN "):
            # details is typically "<ABBR> -<pts>"
            parts = details.split()
            if len(parts) == 2:
                fav, pts = parts
                row["favorite"] = fav
                try:
                    row["spread_points"] = abs(float(pts))
                except ValueError:
                    pass
        elif details:
            row["favorite"] = "PICK"
            row["spread_points"] = 0.0

    return row


def format_kickoff(date_utc):
    if not date_utc:
        return "TBD"
    try:
        dt = datetime.fromisoformat(date_utc.replace("Z", "+00:00")).astimezone(timezone.utc)
        return dt.strftime("%a %m/%d %H:%MZ")
    except ValueError:
        return date_utc


def print_table(week_num, games):
    print(f"\nNFL lines - Week {week_num}  ({len(games)} games)")
    print("=" * 62)
    print(f"{'Kickoff':<16} {'Matchup':<12} {'Spread':<12} {'O/U':<6}")
    print("-" * 62)
    for g in games:
        spread = g["spread"] or "-- no line --"
        ou = g["over_under"] if g["over_under"] is not None else "--"
        print(f"{format_kickoff(g['date_utc']):<16} {g['matchup']:<12} {spread:<12} {ou:<6}")
    print("=" * 62)

    missing = [g["matchup"] for g in games if not g["spread"] or g["over_under"] is None]
    if missing:
        print(f"\n[!] {len(missing)} game(s) missing a spread or total: {', '.join(missing)}")
        print("    ESPN may not have posted these yet - re-run later or fill manually.")


def write_outputs(out_dir, season, week_num, games):
    import os
    os.makedirs(out_dir, exist_ok=True)
    base = f"nfl_lines_{season or 'current'}_wk{week_num}"

    json_path = os.path.join(out_dir, base + ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"season": season, "week": week_num, "games": games}, f, indent=2)

    csv_path = os.path.join(out_dir, base + ".csv")
    fields = ["matchup", "away", "home", "date_utc", "spread",
              "favorite", "spread_points", "over_under", "provider"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for g in games:
            w.writerow(g)

    print(f"\nWrote {csv_path}")
    print(f"Wrote {json_path}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Pull NFL betting lines from ESPN for a week.")
    p.add_argument("--week", type=int, help="Week number. Omit to auto-detect the current week.")
    p.add_argument("--season", type=int, help="Season year, e.g. 2026. Omit for current.")
    p.add_argument("--seasontype", type=int, default=2,
                   help="1=preseason, 2=regular (default), 3=postseason.")
    p.add_argument("--out-dir", help="If set, also write CSV + JSON here.")
    args = p.parse_args(argv)

    try:
        data = fetch_scoreboard(season=args.season, week=args.week, seasontype=args.seasontype)
    except requests.RequestException as e:
        print(f"ERROR fetching from ESPN: {e}", file=sys.stderr)
        return 1

    week_num = (data.get("week") or {}).get("number", args.week or "?")
    events = data.get("events", [])
    if not events:
        print("No games returned for that week.", file=sys.stderr)
        return 1

    games = [parse_game(e) for e in events]
    games.sort(key=lambda g: g["date_utc"] or "")

    print_table(week_num, games)
    if args.out_dir:
        write_outputs(args.out_dir, args.season, week_num, games)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
