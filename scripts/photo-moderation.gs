// Replace the existing handler in each bound response spreadsheet.
function triggerGithubAction(e) {
  const properties = PropertiesService.getScriptProperties();
  const repo = properties.getProperty('GITHUB_REPO');
  const token = properties.getProperty('GITHUB_DISPATCH_TOKEN');
  if (!repo || !token || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)) {
    throw new Error('Missing or invalid GitHub dispatch properties');
  }
  // Form-submit events have namedValues; change events do not.
  try {
    const recipients = properties.getProperty('PHOTO_REVIEW_EMAILS');
    if (recipients && e && e.namedValues && e.range) {
      const sheet = e.range.getSheet();
      const url = sheet.getParent().getUrl() + '#gid=' + sheet.getSheetId()
        + '&range=A' + e.range.getRow();
      MailApp.sendEmail(recipients, 'CWKC photo submission to review',
        'Review the submitted photo privately:\n' + url
        + '\n\nConfirm publication permission, enter Image Alt Text, and set Image Approved to Yes.');
    }
  } finally {
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
}
