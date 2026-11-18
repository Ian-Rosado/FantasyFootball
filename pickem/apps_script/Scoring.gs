/**
 * NFL Pick'em — Auto-scoring
 * --------------------------
 * Second file in the same Apps Script project as Code.gs (they share globals,
 * so this reuses espnFetch_, PROP_SS_ID, NO_PICK_LABEL, etc.).
 *
 * Pipeline:
 *   syncPicks()        Form Responses -> normalized "Picks" tab (latest per
 *                      person/week). Manual rows are never overwritten.
 *   scoreWeek(n)       Grade "Picks" for week n against ESPN final scores ->
 *                      "Scores" tab. Re-runnable (updates rows in place).
 *   updateStandings()  Sum "Scores" across weeks -> "Standings" tab.
 *   runScoring()       Do all three for the current week.
 *
 * Grading is self-contained in the pick STRING (e.g. "GB -7.5",
 * "ATL @ GB Over 46.5") because ESPN drops the odds once a game is final — the
 * number the player saw is baked into their pick.
 *
 * SCORING RULES (locked with the commissioner):
 *   - Wins ADD the points bet; losses SUBTRACT them (signed).
 *   - Super-pick adds +6 to that one pick's points (swings both ways).
 *   - Push = treated as a loss (subtracts). Flip PUSH_SUBTRACTS to make pushes
 *     neutral (0) instead.
 */

// -------------------------------- Config ------------------------------------

var PICKS_SHEET = 'Picks';
var SCORES_SHEET = 'Scores';
var STANDINGS_SHEET = 'Standings';

var SUPER_PICK_BONUS = 6;
// true  -> a push subtracts the points (treated as a loss)
// false -> a push is neutral (0 for that pick)
var PUSH_SUBTRACTS = true;

var PICKS_HEADERS = ['Week', 'Email', 'Name', 'Source', 'UpdatedAt',
  'Pick 1', 'Pts 1', 'Pick 2', 'Pts 2', 'Pick 3', 'Pts 3',
  'Pick 4', 'Pts 4', 'Pick 5', 'Pts 5', 'SuperPick'];

var SCORES_HEADERS = ['Week', 'Email', 'Name', 'Source',
  'P1', 'R1', 'Pts1', 'P2', 'R2', 'Pts2', 'P3', 'R3', 'Pts3',
  'P4', 'R4', 'Pts4', 'P5', 'R5', 'Pts5', 'Super', 'Weekly Total', 'Notes'];

// ------------------------------ Sheet helpers -------------------------------

function ss_() {
  return SpreadsheetApp.openById(
    PropertiesService.getScriptProperties().getProperty(PROP_SS_ID));
}

function getOrCreateSheet_(name, headers) {
  var ss = ss_();
  var sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  if (headers && sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, headers.length).setValues([headers]);
    sh.setFrozenRows(1);
  }
  return sh;
}

/** The Forms-linked response sheet: the one whose header row contains 'Pick #1'. */
function responseSheet_() {
  var sheets = ss_().getSheets();
  for (var i = 0; i < sheets.length; i++) {
    var sh = sheets[i];
    if (sh.getLastRow() < 1) continue;
    var headers = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
    if (headers.indexOf('Pick #1') !== -1) return sh;
  }
  throw new Error('Could not find the form response sheet (no "Pick #1" header).');
}

/** Map header text -> 0-based column index, for a header row array. */
function headerIndex_(headers) {
  var idx = {};
  for (var i = 0; i < headers.length; i++) idx[String(headers[i]).trim()] = i;
  return idx;
}

/** First index whose header matches a predicate (for fuzzy headers). */
function findHeader_(headers, pred) {
  for (var i = 0; i < headers.length; i++) if (pred(String(headers[i]).trim())) return i;
  return -1;
}

// -------------------------------- syncPicks ---------------------------------

/**
 * Pull the latest form submission per (email, week) into the Picks tab.
 * Manual rows (Source = 'manual') are left untouched.
 */
function syncPicks() {
  var resp = responseSheet_();
  var data = resp.getDataRange().getValues();
  if (data.length < 2) { Logger.log('No form responses yet.'); return; }

  var h = data[0];
  var cTime = findHeader_(h, function (x) { return x === 'Timestamp'; });
  var cEmail = findHeader_(h, function (x) { return /email/i.test(x); });
  var cName = findHeader_(h, function (x) { return x === 'Name'; });
  var cWeek = findHeader_(h, function (x) { return x === 'Week'; });
  var cSuper = findHeader_(h, function (x) { return /^SUPER-?PICK/i.test(x); });
  var cPick = [], cPts = [];
  for (var n = 1; n <= 5; n++) {
    cPick[n] = findHeader_(h, function (x) { return x === 'Pick #' + n; });
    cPts[n] = findHeader_(h, function (x) { return x === 'Points to Bet on Pick #' + n; });
  }

  // Keep the latest row per email|week by timestamp.
  var latest = {};
  for (var r = 1; r < data.length; r++) {
    var row = data[r];
    var email = String(row[cEmail] || '').trim().toLowerCase();
    var week = String(row[cWeek] || '').trim();
    if (!email || !week) continue; // week is stamped on submit; skip if absent
    var key = email + '|' + week;
    var ts = row[cTime] instanceof Date ? row[cTime].getTime() : new Date(row[cTime]).getTime();
    if (!latest[key] || ts >= latest[key].ts) latest[key] = { ts: ts, row: row };
  }

  var picks = getOrCreateSheet_(PICKS_SHEET, PICKS_HEADERS);
  var pData = picks.getDataRange().getValues();
  var pIdx = {}; // email|week -> {rowNum, source}
  for (var pr = 1; pr < pData.length; pr++) {
    var k = String(pData[pr][1]).trim().toLowerCase() + '|' + String(pData[pr][0]).trim();
    pIdx[k] = { rowNum: pr + 1, source: String(pData[pr][3]).trim().toLowerCase() };
  }

  var upserted = 0, skipped = 0;
  for (var key2 in latest) {
    var existing = pIdx[key2];
    if (existing && existing.source === 'manual') { skipped++; continue; } // protect manual

    var row2 = latest[key2].row;
    var out = [
      String(row2[cWeek]).trim(),
      String(row2[cEmail]).trim(),
      cName >= 0 ? row2[cName] : '',
      'form',
      new Date()
    ];
    for (var m = 1; m <= 5; m++) {
      out.push(cPick[m] >= 0 ? row2[cPick[m]] : '');
      out.push(cPts[m] >= 0 ? row2[cPts[m]] : '');
    }
    out.push(cSuper >= 0 ? row2[cSuper] : '');

    if (existing) picks.getRange(existing.rowNum, 1, 1, out.length).setValues([out]);
    else picks.appendRow(out);
    upserted++;
  }
  Logger.log('syncPicks: ' + upserted + ' form row(s) synced, ' +
    skipped + ' manual row(s) preserved.');
}

// ------------------------------ Pick parsing --------------------------------

/**
 * Parse a pick string into a structured bet.
 * Returns {kind:'spread', team, line} | {kind:'total', a, b, over, line}
 *       | {kind:'none'} | {kind:'error', raw}
 */
function parsePick_(s) {
  s = String(s == null ? '' : s).trim();
  if (!s || s.toLowerCase() === NO_PICK_LABEL.toLowerCase()) return { kind: 'none' };

  // Total: "ATL @ GB Over 46.5"
  var mt = s.match(/^([A-Za-z]{2,4})\s*@\s*([A-Za-z]{2,4})\s+(Over|Under)\s+([0-9]+(?:\.[0-9]+)?)$/i);
  if (mt) {
    return { kind: 'total', a: mt[1].toUpperCase(), b: mt[2].toUpperCase(),
             over: /over/i.test(mt[3]), line: parseFloat(mt[4]) };
  }
  // Pick'em: "GB PK (ATL @ GB)"
  var mp = s.match(/^([A-Za-z]{2,4})\s+PK\b/i);
  if (mp) return { kind: 'spread', team: mp[1].toUpperCase(), line: 0 };

  // Spread: "GB -7.5" / "ATL +7.5"
  var ms = s.match(/^([A-Za-z]{2,4})\s+([+-][0-9]+(?:\.[0-9]+)?)$/);
  if (ms) return { kind: 'spread', team: ms[1].toUpperCase(), line: parseFloat(ms[2]) };

  return { kind: 'error', raw: s };
}

// ------------------------------- Results ------------------------------------

/** Fetch a week's final scores from ESPN (cdn host; Apps-Script-safe). */
function fetchResults_(week) {
  var json = espnFetch_(week);
  var sched = (json.content && json.content.schedule) || {};
  var byTeam = {}, games = [];
  for (var date in sched) {
    var glist = sched[date].games || [];
    for (var i = 0; i < glist.length; i++) {
      var comp = glist[i].competitions[0];
      var cs = comp.competitors;
      var home = null, away = null;
      for (var j = 0; j < cs.length; j++) {
        if (cs[j].homeAway === 'home') home = cs[j]; else away = cs[j];
      }
      if (!home || !away) continue;
      var completed = !!(comp.status && comp.status.type && comp.status.type.completed);
      var hs = parseInt(home.score, 10), as = parseInt(away.score, 10);
      var ha = home.team.abbreviation, aa = away.team.abbreviation;
      games.push({ home: ha, away: aa, homeScore: hs, awayScore: as, completed: completed });
      byTeam[ha] = { teamScore: hs, oppScore: as, completed: completed };
      byTeam[aa] = { teamScore: as, oppScore: hs, completed: completed };
    }
  }
  return { byTeam: byTeam, games: games };
}

function findGame_(games, t1, t2) {
  for (var i = 0; i < games.length; i++) {
    var g = games[i];
    if ((g.home === t1 && g.away === t2) || (g.home === t2 && g.away === t1)) return g;
  }
  return null;
}

/** Grade one parsed pick. Returns 'win'|'loss'|'push'|'none'|'pending'|'error'. */
function gradePick_(p, results) {
  if (p.kind === 'none') return 'none';
  if (p.kind === 'error') return 'error';

  if (p.kind === 'spread') {
    var g = results.byTeam[p.team];
    if (!g) return 'error';
    if (!g.completed) return 'pending';
    var v = (g.teamScore - g.oppScore) + p.line; // covers if > 0
    return v > 0 ? 'win' : (v === 0 ? 'push' : 'loss');
  }
  if (p.kind === 'total') {
    var gm = findGame_(results.games, p.a, p.b);
    if (!gm) return 'error';
    if (!gm.completed) return 'pending';
    var total = gm.homeScore + gm.awayScore;
    var diff = p.over ? (total - p.line) : (p.line - total);
    return diff > 0 ? 'win' : (diff === 0 ? 'push' : 'loss');
  }
  return 'error';
}

/** Signed points a result contributes, given the (super-adjusted) points bet. */
function contribution_(result, pts) {
  switch (result) {
    case 'win': return pts;
    case 'loss': return -pts;
    case 'push': return PUSH_SUBTRACTS ? -pts : 0;
    default: return 0; // none / pending / error
  }
}

// ------------------------------- scoreWeek ----------------------------------

/** Grade the Picks tab for a week and write per-player rows to Scores. */
function scoreWeek(week) {
  week = String(week);
  var picks = getOrCreateSheet_(PICKS_SHEET, PICKS_HEADERS);
  var pData = picks.getDataRange().getValues();
  if (pData.length < 2) { Logger.log('No picks to score.'); return; }
  var ph = headerIndex_(pData[0]);

  var results = fetchResults_(week);
  var scores = getOrCreateSheet_(SCORES_SHEET, SCORES_HEADERS);
  var sData = scores.getDataRange().getValues();
  var sIdx = {};
  for (var sr = 1; sr < sData.length; sr++) {
    sIdx[String(sData[sr][1]).trim().toLowerCase() + '|' + String(sData[sr][0]).trim()] = sr + 1;
  }

  var scored = 0, pendingTotal = 0;
  for (var r = 1; r < pData.length; r++) {
    if (String(pData[r][ph['Week']]).trim() !== week) continue;

    var email = pData[r][ph['Email']];
    var name = pData[r][ph['Name']];
    var source = pData[r][ph['Source']];
    var superVal = String(pData[r][ph['SuperPick']] || '');

    var out = [week, email, name, source];
    var weekTotal = 0, notes = [];

    for (var n = 1; n <= 5; n++) {
      var pickStr = pData[r][ph['Pick ' + n]];
      var basePts = Number(pData[r][ph['Pts ' + n]]) || 0;
      var pts = basePts + (superVal === ('Pick #' + n) ? SUPER_PICK_BONUS : 0);

      var parsed = parsePick_(pickStr);
      var res = gradePick_(parsed, results);
      var contrib = contribution_(res, pts);
      weekTotal += contrib;

      if (res === 'pending') { pendingTotal++; notes.push('Pick ' + n + ' pending'); }
      if (res === 'error') notes.push('Pick ' + n + ' unparseable/no-match: "' + pickStr + '"');

      out.push(pickStr, res, contrib);
    }
    out.push(superVal, weekTotal, notes.join('; '));

    var key = String(email).trim().toLowerCase() + '|' + week;
    if (sIdx[key]) scores.getRange(sIdx[key], 1, 1, out.length).setValues([out]);
    else scores.appendRow(out);
    scored++;
  }

  Logger.log('scoreWeek ' + week + ': scored ' + scored + ' player(s).' +
    (pendingTotal ? ' ' + pendingTotal + ' pick(s) still pending (games not final) — re-run after they finish.' : ''));
}

// ----------------------------- updateStandings ------------------------------

/** Aggregate every Scores row into season standings. */
function updateStandings() {
  var scores = getOrCreateSheet_(SCORES_SHEET, SCORES_HEADERS);
  var data = scores.getDataRange().getValues();
  var byPlayer = {};
  for (var r = 1; r < data.length; r++) {
    var email = String(data[r][1]).trim().toLowerCase();
    if (!email) continue;
    if (!byPlayer[email]) byPlayer[email] = { name: data[r][2], email: data[r][1], total: 0, weeks: 0 };
    byPlayer[email].name = data[r][2] || byPlayer[email].name;
    byPlayer[email].total += Number(data[r][20]) || 0; // 'Weekly Total' column
    byPlayer[email].weeks += 1;
  }
  var rows = [];
  for (var e in byPlayer) rows.push(byPlayer[e]);
  rows.sort(function (a, b) { return b.total - a.total; });

  var sh = getOrCreateSheet_(STANDINGS_SHEET, ['Rank', 'Name', 'Email', 'Season Total', 'Weeks']);
  if (sh.getLastRow() > 1) sh.getRange(2, 1, sh.getLastRow() - 1, 5).clearContent();
  var out = rows.map(function (p, i) { return [i + 1, p.name, p.email, p.total, p.weeks]; });
  if (out.length) sh.getRange(2, 1, out.length, 5).setValues(out);
  Logger.log('Standings updated for ' + out.length + ' player(s).');
}

// ------------------------------- Convenience --------------------------------

/** Sync + score + standings for the current ESPN week. */
function runScoring() {
  var week = currentWeekParams_().week;
  syncPicks();
  scoreWeek(week);
  updateStandings();
}
