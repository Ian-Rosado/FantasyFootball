/**
 * NFL Pick'em — Google Form auto-updater
 * ---------------------------------------
 * Pulls the week's NFL betting lines (DraftKings spreads + over/unders, via
 * ESPN) and builds/updates a Google Form with structured pick options.
 *
 * WHY THIS ENDPOINT: ESPN's site.api.* blocks Google's servers (403), but
 * cdn.espn.com/core/nfl/schedule accepts the Apps Script User-Agent and carries
 * the same DraftKings odds. UrlFetchApp cannot override its User-Agent, so we
 * MUST use the cdn.espn.com host here — do not "simplify" this to site.api.*.
 *
 * ONE-TIME SETUP:
 *   1. Run setupForm() once. Grant permissions when prompted.
 *   2. Check the Execution Log for the form's Edit URL and Live (viewform) URL.
 *   3. (Optional) Run createWeeklyTrigger() to auto-update every week.
 *
 * WEEKLY (if not using the trigger):
 *   Run updateCurrentWeek()  — auto-detects the current week and refreshes lines.
 *   Or updateWeek(3)         — force a specific week number.
 *   Or weeklyPublish()       — refresh lines AND email the group the form link.
 *
 * EMAIL NOTIFICATIONS (free, via Gmail):
 *   Run setEmailConfig() once with your group's addresses, then testEmail().
 */

// ----------------------------- Config ---------------------------------------

var CONFIG = {
  seasonType: 2, // 1=preseason, 2=regular, 3=postseason
  pointsChoices: ['1', '2', '3', '4', '5', '6'],
  numPicks: 5,
  // Carried over from the existing form. Edit freely.
  rules:
    "Make 5 picks, against the spread or over/under. Assign 10 total points to " +
    "your bets with at least 1 point on each pick. Weekly payouts as follows:\n" +
    "1st - $25\n2nd - $10\n3rd - ($5)\n4th - ($5)\n5th - ($5)\n6th - ($10)\nLast - ($10)\n\n" +
    "Each player gets 3 SUPER-PICKS to use throughout the regular season. When " +
    "you use a SUPER-PICK, 6 additional points will be placed on your pick. " +
    "You can only use 1 SUPER-PICK per week. You MUST use all 3 of your " +
    "SUPER-PICKS throughout the regular season."
};

// Shown in every pick dropdown so a required pick can be left as "no pick"
// (late entries, or games that already kicked off). Scored as 0.
var NO_PICK_LABEL = 'No pick';

// Script Property keys (persist state between runs).
var PROP_FORM_ID = 'PICKEM_FORM_ID';
var PROP_PICK_ITEM_IDS = 'PICKEM_PICK_ITEM_IDS';
var PROP_SS_ID = 'PICKEM_SPREADSHEET_ID';
var PROP_CURRENT_WEEK = 'PICKEM_CURRENT_WEEK';
var PROP_LAST_LINES = 'PICKEM_LAST_LINES'; // formatted lines block, reused in the email

// ----------------------------- ESPN fetch -----------------------------------

/**
 * Fetch the schedule JSON. Pass week=null to get ESPN's current week.
 * Returns the parsed object.
 */
function espnFetch_(week) {
  var url = 'https://cdn.espn.com/core/nfl/schedule?xhr=1&seasontype=' + CONFIG.seasonType;
  if (week != null) url += '&week=' + week;
  var resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  var code = resp.getResponseCode();
  if (code !== 200) {
    throw new Error('ESPN fetch failed (HTTP ' + code + '). URL: ' + url);
  }
  return JSON.parse(resp.getContentText());
}

/** Read the week/year ESPN currently considers active. */
function currentWeekParams_() {
  var d = espnFetch_(null);
  var p = (d.content && d.content.parameters) || {};
  return { week: p.week, year: p.year, seasontype: p.seasontype };
}

// ----------------------------- Parsing --------------------------------------

/**
 * Flatten ESPN's schedule payload into a sorted list of games:
 *   { away, home, awayName, homeName, kickoff, details, overUnder, favorite }
 */
function parseGames_(json) {
  var schedule = (json.content && json.content.schedule) || {};
  var games = [];
  for (var date in schedule) {
    var block = schedule[date];
    var glist = block.games || [];
    for (var i = 0; i < glist.length; i++) {
      var comp = glist[i].competitions[0];
      var comps = comp.competitors;
      var home = null, away = null;
      for (var j = 0; j < comps.length; j++) {
        if (comps[j].homeAway === 'home') home = comps[j];
        else away = comps[j];
      }
      if (!home || !away) continue;

      var odds = (comp.odds && comp.odds[0]) || null;
      var details = odds ? odds.details : null; // "GB -7.5", "PK", "EVEN"
      var favorite = null;
      if (details && details.toUpperCase() !== 'PK' && details.toUpperCase() !== 'EVEN') {
        var parts = details.split(' ');
        if (parts.length === 2) favorite = parts[0];
      }

      games.push({
        away: away.team.abbreviation,
        home: home.team.abbreviation,
        awayName: away.team.displayName,
        homeName: home.team.displayName,
        kickoff: comp.date || glist[i].date,
        details: details,
        overUnder: odds ? odds.overUnder : null,
        favorite: favorite
      });
    }
  }
  games.sort(function (a, b) {
    return (a.kickoff || '').localeCompare(b.kickoff || '');
  });
  return games;
}

/**
 * Build the flat list of selectable bets for a week.
 * 4 per game (both spread sides + Over + Under), grouped by kickoff.
 * Games missing a spread still contribute their O/U (and are returned in
 * `missing` so the caller can flag them).
 */
function buildBetOptions_(games) {
  var options = [];
  var missing = [];
  for (var i = 0; i < games.length; i++) {
    var g = games[i];
    var matchup = g.away + ' @ ' + g.home;

    if (g.favorite) {
      var absPts = Math.abs(parseFloat(g.details.split(' ')[1]));
      var dog = (g.favorite === g.home) ? g.away : g.home;
      options.push(g.favorite + ' -' + absPts);
      options.push(dog + ' +' + absPts);
    } else if (g.details) {
      // pick'em
      options.push(g.home + ' PK (' + matchup + ')');
      options.push(g.away + ' PK (' + matchup + ')');
    } else {
      missing.push(matchup);
    }

    if (g.overUnder != null) {
      options.push(matchup + ' Over ' + g.overUnder);
      options.push(matchup + ' Under ' + g.overUnder);
    } else if (missing.indexOf(matchup) === -1) {
      missing.push(matchup);
    }
  }
  // Always offer a "No pick" out, for late entries or games already started.
  options.push(NO_PICK_LABEL);
  return { options: options, missing: missing };
}

/**
 * Human-readable lines block shown in the form body (where the old screenshots
 * were). One row per game, sorted by kickoff, in the script's time zone.
 */
function buildLinesText_(games) {
  var tz = Session.getScriptTimeZone();
  var lines = ['THIS WEEK’S LINES (DraftKings via ESPN):'];
  for (var i = 0; i < games.length; i++) {
    var g = games[i];
    var when = g.kickoff
      ? Utilities.formatDate(new Date(g.kickoff), tz, 'EEE M/d h:mma')
      : 'TBD';
    var spread = g.details ? g.details : 'line TBD';
    var ou = (g.overUnder != null) ? ('O/U ' + g.overUnder) : 'O/U TBD';
    lines.push(when + '  ' + g.away + ' @ ' + g.home + '  —  ' + spread + ', ' + ou);
  }
  return lines.join('\n');
}

// ----------------------------- Form setup -----------------------------------

/** ONE-TIME: create the form structure and remember its ids. */
function setupForm() {
  var props = PropertiesService.getScriptProperties();
  if (props.getProperty(PROP_FORM_ID)) {
    throw new Error('A form already exists for this script (id ' +
      props.getProperty(PROP_FORM_ID) + '). Delete that property to start over.');
  }

  var form = FormApp.create('NFL Pick’em');
  form.setDescription(CONFIG.rules);
  form.setCollectEmail(true);   // collect respondent email
  form.setLimitOneResponsePerUser(false);
  form.setAllowResponseEdits(true);

  // All responses flow into ONE spreadsheet for the whole season.
  var ss = SpreadsheetApp.create('NFL Pick’em — Responses');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
  props.setProperty(PROP_SS_ID, ss.getId());
  // Stamp each new response's row with the current week (see onFormSubmitSheet).
  installSubmitTrigger_(ss);

  // Name
  form.addTextItem().setTitle('Name').setRequired(true);

  // 5 x (Pick dropdown + Points dropdown)
  var pickItemIds = [];
  for (var n = 1; n <= CONFIG.numPicks; n++) {
    var pick = form.addListItem().setTitle('Pick #' + n).setRequired(true);
    pick.setChoiceValues(['(lines load when the week is updated)']);
    pickItemIds.push(pick.getId());

    form.addListItem()
      .setTitle('Points to Bet on Pick #' + n)
      .setChoiceValues(CONFIG.pointsChoices)
      .setRequired(true);
  }

  // SUPER-PICK
  var superChoices = [];
  for (var s = 1; s <= CONFIG.numPicks; s++) superChoices.push('Pick #' + s);
  superChoices.push('N/A');
  form.addListItem()
    .setTitle('SUPER-PICK (optional — adds 6 points to the chosen pick)')
    .setChoiceValues(superChoices);

  props.setProperty(PROP_FORM_ID, form.getId());
  props.setProperty(PROP_PICK_ITEM_IDS, JSON.stringify(pickItemIds));

  // Populate this week's lines immediately.
  updateCurrentWeek();

  Logger.log('SETUP COMPLETE');
  Logger.log('Edit URL  : ' + form.getEditUrl());
  Logger.log('Live URL  : ' + form.getPublishedUrl());
  Logger.log('Sheet URL : ' + ss.getUrl());
}

// ----------------------------- Weekly update --------------------------------

/** Update the form for ESPN's current week. Use this on the trigger. */
function updateCurrentWeek() {
  updateWeek(null);
}

/** Update the form for a specific week (or null for current). */
function updateWeek(week) {
  var props = PropertiesService.getScriptProperties();
  var formId = props.getProperty(PROP_FORM_ID);
  if (!formId) throw new Error('Run setupForm() first.');

  if (week == null) week = currentWeekParams_().week;

  var json = espnFetch_(week);
  var games = parseGames_(json);
  var built = buildBetOptions_(games);
  if (built.options.length === 0) {
    throw new Error('No bet options built for week ' + week + ' (no lines posted yet?).');
  }

  props.setProperty(PROP_CURRENT_WEEK, String(week)); // stamped onto each response row

  var form = FormApp.openById(formId);
  form.setTitle('Week ' + week + ' Pick’em');

  var linesText = buildLinesText_(games);
  props.setProperty(PROP_LAST_LINES, linesText); // reused by the weekly email

  var stamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'EEE MMM d, h:mm a');
  var desc = CONFIG.rules +
    '\n\n' + linesText +
    '\n\n— Lines: DraftKings via ESPN, pulled ' + stamp + '. —';
  if (built.missing.length) {
    desc += '\nNote: no line yet for ' + built.missing.join(', ') + '.';
  }
  form.setDescription(desc);

  var pickItemIds = JSON.parse(props.getProperty(PROP_PICK_ITEM_IDS));
  for (var i = 0; i < pickItemIds.length; i++) {
    form.getItemById(pickItemIds[i]).asListItem().setChoiceValues(built.options);
  }

  Logger.log('Updated to Week ' + week + ': ' + built.options.length +
    ' bet options across ' + games.length + ' games.' +
    (built.missing.length ? ' Missing: ' + built.missing.join(', ') : ''));
}

// ----------------------- Response-sheet week stamping -----------------------

/** Install a per-submission trigger on the response spreadsheet (idempotent). */
function installSubmitTrigger_(ss) {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'onFormSubmitSheet') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  ScriptApp.newTrigger('onFormSubmitSheet')
    .forSpreadsheet(ss)
    .onFormSubmit()
    .create();
}

/**
 * On each submission: (1) stamp the form's current week into a "Week" column on
 * the new response row (week comes from Script Properties, never the respondent,
 * so it's always correct), and (2) email the respondent a confirmation listing
 * their picks so they know it registered and can remember what they chose.
 */
function onFormSubmitSheet(e) {
  var sheet = e.range.getSheet();
  var row = e.range.getRow();
  var week = PropertiesService.getScriptProperties().getProperty(PROP_CURRENT_WEEK) || '';

  var lastCol = sheet.getLastColumn();
  var headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  var col = headers.indexOf('Week') + 1;
  if (col === 0) { // no Week column yet — add one to the right
    col = lastCol + 1;
    sheet.getRange(1, col).setValue('Week');
  }
  sheet.getRange(row, col).setValue(week);

  sendConfirmation_(headers, sheet.getRange(row, 1, 1, sheet.getLastColumn()).getValues()[0], week);
}

/**
 * Email the respondent a copy of their submission. Finds their address in the
 * auto-collected "Email address" column; skips (with a log) if it's missing.
 */
function sendConfirmation_(headers, rowVals, week) {
  var email = null;
  var pairs = [];
  for (var i = 0; i < headers.length; i++) {
    var h = String(headers[i]).trim();
    var v = rowVals[i];
    if (/email/i.test(h) && !email && v) { email = String(v).trim(); continue; }
    if (h === 'Timestamp' || h === 'Week' || v === '' || v == null) continue;
    pairs.push(h + ': ' + v);
  }
  if (!email) {
    Logger.log('No respondent email found on row; skipping confirmation.');
    return;
  }

  var subject = 'Your Week ' + week + ' Pick’em picks are in';
  var body =
    'Thanks — your Week ' + week + ' picks are registered. Here’s what we got:\n\n' +
    pairs.join('\n') +
    '\n\nNeed to change a pick? Submit the form again before kickoff — your most ' +
    'recent submission is the one that counts. Good luck!';
  MailApp.sendEmail({ to: email, subject: subject, body: body });
  Logger.log('Confirmation sent to ' + email);
}

// ------------------------- Weekly publish + email ---------------------------

/**
 * The scheduled entry point: refresh the current week's lines AND email the
 * group the form link. Kept separate from updateCurrentWeek() so a manual
 * refresh never fires an email.
 */
function weeklyPublish() {
  updateCurrentWeek();

  var props = PropertiesService.getScriptProperties();
  var week = props.getProperty(PROP_CURRENT_WEEK);
  var lines = props.getProperty(PROP_LAST_LINES) || '';
  var form = FormApp.openById(props.getProperty(PROP_FORM_ID));
  var url = form.getPublishedUrl();

  var subject = 'Week ' + week + ' Pick’em is live';
  var body =
    'Week ' + week + ' Pick’em is open — make your 5 picks here:\n' +
    url + '\n\n' +
    lines + '\n\n' +
    'Get your picks in before kickoff. Good luck!';
  sendGroupEmail_(subject, body);
}

/**
 * Email everyone in EMAIL_RECIPIENTS (comma-separated, set via setEmailConfig).
 * Recipients are BCC'd so they don't see each other's addresses. No-ops (and
 * logs) if no recipients are configured, so the weekly run still succeeds.
 * Free via Gmail — consumer accounts allow ~100 recipients/day.
 */
function sendGroupEmail_(subject, body) {
  var list = (PropertiesService.getScriptProperties().getProperty('EMAIL_RECIPIENTS') || '')
    .split(',').map(function (s) { return s.trim(); }).filter(String);

  if (!list.length) {
    Logger.log('No EMAIL_RECIPIENTS configured; skipping email. Run setEmailConfig() to add them.');
    return;
  }
  MailApp.sendEmail({
    to: Session.getEffectiveUser().getEmail(), // the To is you; the group is BCC'd
    bcc: list.join(','),
    subject: subject,
    body: body
  });
  Logger.log('Emailed ' + list.length + ' recipient(s).');
}

/**
 * ONE-TIME email setup. Put your group's addresses here (comma-separated), run
 * once, then you can blank them out again — they're saved in Script Properties.
 * Re-run any time to change the list.
 */
function setEmailConfig() {
  PropertiesService.getScriptProperties().setProperty(
    'EMAIL_RECIPIENTS',
    'friend1@example.com, friend2@example.com'
  );
  Logger.log('Email recipients saved.');
}

/** Send a test email to the whole list to confirm it works. */
function testEmail() {
  sendGroupEmail_('Pick’em test', 'If you got this, email notifications work.');
}

// ----------------------------- Trigger --------------------------------------

/**
 * Install the weekly trigger: Tuesdays ~2pm in the script's time zone. Set the
 * project time zone to America/Los_Angeles (Project Settings → Time zone) so
 * this fires at 2pm Pacific. Points at weeklyPublish (update + email).
 * Safe to re-run; clears any prior weeklyPublish/updateCurrentWeek triggers.
 */
function createWeeklyTrigger() {
  var existing = ScriptApp.getProjectTriggers();
  for (var i = 0; i < existing.length; i++) {
    var fn = existing[i].getHandlerFunction();
    if (fn === 'weeklyPublish' || fn === 'updateCurrentWeek') {
      ScriptApp.deleteTrigger(existing[i]);
    }
  }
  ScriptApp.newTrigger('weeklyPublish')
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.TUESDAY)
    .atHour(14)
    .nearMinute(0)
    .create();
  Logger.log('Weekly trigger installed: Tuesdays ~2pm (' + Session.getScriptTimeZone() + ').');
}
