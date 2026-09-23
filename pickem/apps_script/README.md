# NFL Pick'em — Google Form auto-updater (Apps Script)

Builds and weekly-updates a Google Form with structured pick options, pulling
DraftKings spreads + over/unders (via ESPN) automatically. Runs entirely inside
Google — no local script needed once set up.

## Why Apps Script (and this specific ESPN endpoint)

ESPN's `site.api.espn.com` blocks Google's servers with a 403, but
`cdn.espn.com/core/nfl/schedule` accepts the Apps Script request and carries the
same DraftKings odds. Apps Script can't change its User-Agent, so `Code.gs` uses
the `cdn.espn.com` host on purpose — don't switch it to `site.api.*`.

## One-time setup

1. Go to <https://script.google.com> → **New project**.
2. Delete the default `myFunction` code, paste in all of `Code.gs`.
3. In the toolbar function dropdown, select **`setupForm`**, click **Run**.
4. Approve the permission prompts (it needs to create Forms + fetch ESPN).
5. Open **View → Logs** (or Execution log). It prints the form's **Edit URL**
   and **Live URL**. Open the Edit URL — the form is built and this week's lines
   are already loaded. Share the Live URL with your group.

## Set the time zone first

So the trigger fires at 2pm **Pacific**: open **Project Settings** (gear icon) →
**Time zone** → choose **(GMT-08:00) Los Angeles**. (The included
`appsscript.json` already sets `America/Los_Angeles` if you edit via clasp.)

## Each week

Pick one:

- **Automatic (recommended):** run **`createWeeklyTrigger`** once. Every
  **Tuesday ~2pm Pacific** it refreshes the lines **and texts the group** the
  form link (`weeklyPublish`). Change the day/hour at the bottom of `Code.gs`.
- **Manual refresh (no text):** run **`updateCurrentWeek`** any time to re-pull
  the lines. Handy if lines moved and you want to bump the form without texting.
- **Force a specific week:** in the editor console run `updateWeek(5)`.
- **Publish + text now:** run **`weeklyPublish`** to do both on demand.

Updating never recreates the form (the URL stays the same) — it just refreshes
the pick dropdowns, the week title, and the lines list in the body.

## What the form contains

- Title: **"Week N Pick'em"** (auto-set), rules/payouts in the description.
- Collects respondent **email** + a **Name** field.
- **Pick #1–5**: dropdowns listing every bet that week — both spread sides plus
  Over/Under per game, e.g. `GB -7.5`, `ATL +7.5`, `ATL @ GB Over 46.5`, plus a
  **`No pick`** option (for late entries or games that already kicked off; scored
  as 0).
- **Points to Bet on Pick #1–5**: dropdowns 1–6.
- **SUPER-PICK**: dropdown (Pick #1–5 or N/A).

If a game has no spread posted yet, its O/U still appears and the game is noted
in the form description so you know to check back.

## Response tracking (one sheet for the whole season)

`setupForm` also creates a single linked Google Sheet (its URL is printed in the
log) that **all** responses flow into, all season. An on-submit trigger stamps
each new row with a **`Week`** column, taken from whatever week the form is
currently set to — so you can filter/sort results by week without players ever
picking the week themselves. The `Week` column is added to the right of the
Forms-generated columns the first time someone submits.

The same on-submit trigger **emails each respondent a confirmation** listing the
picks they just submitted, so they know it registered and can remember their
picks. Resubmitting creates a new row; the confirmation tells players their most
recent submission is the one that counts — so season scoring should dedupe by
keeping the latest submission per email per week.

## Emailing the group (free, via Gmail)

Each weekly run emails everyone the form link (and that week's lines). It uses
Gmail through Apps Script — no cost, no extra account. Consumer Gmail allows
~100 recipients/day, far more than a friend group needs.

1. In `Code.gs`, open `setEmailConfig()`, put your group's addresses in the
   comma-separated string, and **run it once**. (The list is saved in Script
   Properties; you can blank the code back out. Re-run any time to change it.)
2. Run **`testEmail`** to confirm delivery.

Recipients are **BCC'd** (they don't see each other's addresses); the To is your
own address. If no recipients are configured, `weeklyPublish` still updates the
form fine and just skips the email.

## Auto-scoring (`Scoring.gs`)

Add `Scoring.gs` as a second file in the same Apps Script project (**+ next to
Files → Script**, name it `Scoring`, paste). It shares globals with `Code.gs`.
It creates three tabs in the same spreadsheet: **Picks**, **Scores**,
**Standings**.

**Weekly flow — run `runScoring()`** (does all three steps for the current week),
or run them individually:

1. **`syncPicks()`** — copies form responses into the **Picks** tab, keeping only
   the **latest submission per person per week**. Re-runnable.
2. **`scoreWeek(n)`** — grades the Picks for week `n` against ESPN's final scores
   and writes a per-player row to **Scores** (each pick's result + signed points,
   the weekly total, and notes). Re-run after late games finish.
3. **`updateStandings()`** — totals every Scores row into the **Standings** tab.

**Scoring rules (in `Scoring.gs` config):** wins add the points bet, losses
subtract them; a winning/losing super-pick swings by an extra 6; a **push is
treated as a loss** (set `PUSH_SUBTRACTS = false` to make pushes neutral).

**Manual picks** (e.g. picks taken by text before the form was ready): add a row
directly in the **Picks** tab and set its **Source** column to `manual`.
`syncPicks()` never overwrites manual rows. Use the **exact option format** so
grading can parse them:

- Spread: `GB -7.5` or `ATL +7.5` (ESPN abbreviation + signed number)
- Total: `ATL @ GB Over 46.5` / `... Under 46.5`
- No pick: `No pick`

Anything unparseable or not matching a game is flagged in the Scores **Notes**
column (result `error`, 0 points) so you can fix it and re-run.

**Pending games:** picks on games that aren't final yet score as `pending` (0)
and are noted; just re-run `scoreWeek(n)` once they finish.

## Local preview (optional)

`../pull_lines.py` prints the same week's lines as a table in your terminal, for
a quick sanity check before/after an update. See its header for usage.

## Notes / caveats

- ESPN's API is unofficial (no SLA) but stable; low risk for a weekly hobby form.
- Lines move all week — the Tuesday trigger picks a settled-ish time; re-run
  `updateCurrentWeek` if you want fresher numbers before publishing.
- Grading reads the number straight from each pick string (ESPN drops the line
  once a game is final), so picks must keep the option format shown above.
