const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../scripts/photo-moderation.gs'), 'utf8');

function handler(overrides = {}) {
    const properties = {
        GITHUB_REPO: 'example/cwkc',
        GITHUB_DISPATCH_TOKEN: 'synthetic-token',
        PHOTO_REVIEW_EMAILS: 'reviewer@example.invalid',
        ...overrides,
    };
    const mail = jest.fn();
    const dispatch = jest.fn().mockReturnValue({getResponseCode: () => 204});
    const context = vm.createContext({
        PropertiesService: {getScriptProperties: () => ({getProperty: key => properties[key]})},
        MailApp: {sendEmail: mail},
        UrlFetchApp: {fetch: dispatch},
    });
    vm.runInContext(source, context);
    return {run: context.triggerGithubAction, mail, dispatch};
}

function submission() {
    return {
        namedValues: {'Name': ['Synthetic attendee']},
        range: {
            getRow: () => 5,
            getSheet: () => ({
                getSheetId: () => 123,
                getParent: () => ({getUrl: () => 'https://docs.google.com/spreadsheets/d/synthetic/edit'}),
            }),
        },
    };
}

test('submission emails the private response row and dispatches the existing event', () => {
    const {run, mail, dispatch} = handler();
    run(submission());
    expect(mail).toHaveBeenCalledTimes(1);
    expect(mail.mock.calls[0][0]).toBe('reviewer@example.invalid');
    expect(mail.mock.calls[0][2]).toContain('#gid=123&range=A5');
    expect(mail.mock.calls[0][2]).toContain('enter Image Alt Text, and set Image Approved to Yes.');
    expect(mail.mock.calls[0][2]).not.toContain('Synthetic attendee');
    expect(dispatch).toHaveBeenCalledWith('https://api.github.com/repos/example/cwkc/dispatches',
        expect.objectContaining({payload: JSON.stringify({event_type: 'sheet-change'})}));
});

test('manual approval changes dispatch without sending another email', () => {
    const {run, mail, dispatch} = handler();
    run({changeType: 'EDIT'});
    expect(mail).not.toHaveBeenCalled();
    expect(dispatch).toHaveBeenCalledTimes(1);
});

test('review email is optional and its failure cannot prevent dispatch', () => {
    const optional = handler({PHOTO_REVIEW_EMAILS: ''});
    optional.run(submission());
    expect(optional.mail).not.toHaveBeenCalled();
    expect(optional.dispatch).toHaveBeenCalledTimes(1);

    const failed = handler();
    failed.mail.mockImplementation(() => { throw new Error('mail unavailable'); });
    expect(() => failed.run(submission())).toThrow('mail unavailable');
    expect(failed.dispatch).toHaveBeenCalledTimes(1);
});

test('invalid configuration or failed dispatch produces a clear error', () => {
    const invalid = handler({GITHUB_REPO: ''});
    expect(() => invalid.run(submission())).toThrow('Missing or invalid');
    expect(invalid.dispatch).not.toHaveBeenCalled();

    const failed = handler();
    failed.dispatch.mockReturnValue({getResponseCode: () => 403});
    expect(() => failed.run({changeType: 'EDIT'})).toThrow('GitHub dispatch HTTP 403');
});
