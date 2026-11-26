// Bound to each private Forms response spreadsheet; see docs/photos.md.
const PHOTO_APPROVAL_TAB = 'Photo approvals';
const PHOTO_RESPONSE_TAB = 'Form Responses 1';
const PHOTO_APPROVAL_HEADERS = ['Drive file ID', 'Approved', 'Alt text', 'Review photo'];
const PHOTO_QUESTIONS = ['submit your photo here!', 'please submit photos of your event!'];

function normalizePhotoField(value) {
  return String(value || '').normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase();
}

function photoColumn(headers, prefixes) {
  const matches = headers.map((value, index) => ({value: normalizePhotoField(value), index}))
    .filter(({value}) => prefixes.some(prefix => value === prefix
      || value.startsWith(prefix + ' ') || (prefix.endsWith(':') && value.startsWith(prefix))));
  if (matches.length !== 1) throw new Error('Missing or ambiguous photo response column');
  return matches[0].index;
}

function uploadedPhotoIds(value) {
  return [...new Set(String(value || '').split(/[,\n]/).filter(part => part.trim()).map(part => {
    const url = part.trim();
    const open = /^https:\/\/drive\.google\.com\/open\?(?:[^#]*&)?id=([A-Za-z0-9_-]{10,128})(?:[&#].*)?$/.exec(url);
    const file = /^https:\/\/drive\.google\.com\/file\/d\/([A-Za-z0-9_-]{10,128})(?:\/view)?\/?(?:[?#].*)?$/.exec(url);
    const match = open || file;
    if (!match) throw new Error('Unexpected Drive upload link');
    return match[1];
  }))];
}

function photoApprovalSheet(spreadsheet) {
  let sheet = spreadsheet.getSheetByName(PHOTO_APPROVAL_TAB);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(PHOTO_APPROVAL_TAB);
    sheet.getRange(1, 1, 1, PHOTO_APPROVAL_HEADERS.length).setValues([PHOTO_APPROVAL_HEADERS]);
    sheet.setFrozenRows(1);
  }
  const headers = sheet.getRange(1, 1, 1, PHOTO_APPROVAL_HEADERS.length).getDisplayValues()[0];
  if (headers.slice(0, 3).join('|') !== PHOTO_APPROVAL_HEADERS.slice(0, 3).join('|')
      || (headers[3] && headers[3] !== PHOTO_APPROVAL_HEADERS[3])) {
    throw new Error('Invalid Photo approvals header');
  }
  if (!headers[3]) sheet.getRange(1, 4).setValue(PHOTO_APPROVAL_HEADERS[3]);
  return sheet;
}

function setupPhotoApprovals() {
  const lock = LockService.getDocumentLock();
  lock.waitLock(30000);
  try {
    photoApprovalSheet(SpreadsheetApp.getActiveSpreadsheet());
    SpreadsheetApp.flush();
  } finally {
    lock.releaseLock();
  }
}

function queuePhotoSubmission(event) {
  const responseSheet = event.range.getSheet();
  const spreadsheet = responseSheet.getParent();
  const width = responseSheet.getLastColumn();
  const headers = responseSheet.getRange(1, 1, 1, width).getDisplayValues()[0];
  const values = responseSheet.getRange(event.range.getRow(), 1, 1, width).getDisplayValues()[0];
  const photoIndex = photoColumn(headers, PHOTO_QUESTIONS);
  if (normalizePhotoField(headers[photoIndex]).startsWith(PHOTO_QUESTIONS[0])) {
    const releaseIndex = photoColumn(headers, ['photo release:']);
    if (normalizePhotoField(values[releaseIndex]) !== 'yes') return null;
  }
  const ids = uploadedPhotoIds(values[photoIndex]);
  if (!ids.length) return null;
  const lock = LockService.getDocumentLock();
  lock.waitLock(30000);
  try {
    const sheet = photoApprovalSheet(spreadsheet);
    const last = sheet.getLastRow();
    const existing = new Set(last > 1
      ? sheet.getRange(2, 1, last - 1, 1).getDisplayValues().flat() : []);
    const rows = ids.filter(id => !existing.has(id)).map(id => [
      id, 'No', '', 'https://drive.google.com/open?id=' + id
    ]);
    if (!rows.length) return null;
    sheet.getRange(last + 1, 1, rows.length, 4).setValues(rows);
    SpreadsheetApp.flush();
    return {count: rows.length, url: spreadsheet.getUrl() + '#gid=' + sheet.getSheetId()};
  } finally {
    lock.releaseLock();
  }
}

function dispatchPhotoSheetChange() {
  const properties = PropertiesService.getScriptProperties();
  const repo = properties.getProperty('GITHUB_REPO');
  const token = properties.getProperty('GITHUB_DISPATCH_TOKEN');
  if (!repo || !token || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)) {
    throw new Error('Missing or invalid GitHub dispatch properties');
  }
  const response = UrlFetchApp.fetch('https://api.github.com/repos/' + repo + '/dispatches', {
    method: 'post',
    contentType: 'application/json',
    headers: {Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json'},
    payload: JSON.stringify({event_type: 'sheet-change'}),
    muteHttpExceptions: true
  });
  if (response.getResponseCode() !== 204) {
    throw new Error('GitHub dispatch HTTP ' + response.getResponseCode());
  }
}

// Keep the existing installable spreadsheet On form submit function name.
function notifyGitHubOfParticipation(e) {
  if (!e || !e.range) throw new Error('Requires a spreadsheet form-submit trigger');
  if (e.range.getSheet().getName() !== PHOTO_RESPONSE_TAB) return;
  try {
    const pending = queuePhotoSubmission(e);
    const recipients = PropertiesService.getScriptProperties().getProperty('PHOTO_REVIEW_EMAILS');
    if (pending && recipients) {
      MailApp.sendEmail(recipients, 'CWKC photos awaiting review',
        pending.count + ' new photo(s) awaiting approval. Review privately at:\n' + pending.url
        + '\n\nConfirm public-display permission, add alt text, and set Approved to Yes.');
    }
  } finally {
    // Participation dispatch still runs if notification or queue creation fails.
    dispatchPhotoSheetChange();
  }
}

// Add an installable spreadsheet On edit trigger for this function.
function notifyGitHubOfPhotoEdit(e) {
  if (!e || !e.range) throw new Error('Requires a spreadsheet edit trigger');
  const sheetName = e.range.getSheet().getName();
  if (sheetName === PHOTO_RESPONSE_TAB
      || (sheetName === PHOTO_APPROVAL_TAB && e.range.getLastRow() > 1
          && e.range.getColumn() <= 3)) {
    dispatchPhotoSheetChange();
  }
}
