const fs = require('fs');
const path = require('path');
const $ = require('jquery');

describe('contest lifecycle', () => {
    const start = new Date(globalThis.CWKC_SEASON.start);
    const deadline = new Date(globalThis.CWKC_SEASON.end);
    let originalAjax;

    beforeEach(() => {
        originalAjax = $.ajax;
        delete globalThis.CWKC_REHEARSAL_VIEW_UNTIL;
        jest.useFakeTimers();
        document.body.innerHTML = `
            <div id="countdown"><span id="countdown-text"></span>
                <span class="days"></span><span class="hours"></span>
                <span class="minutes"></span><span class="seconds"></span></div>
            <div id="hooTotal">0</div><div id="hokieTotal">0</div>
            <span id="uva_total_amount">0</span><span id="vt_total_amount">0</span>
            <a class="enable-during-contest" href="#photos">Photo submission</a>
            <span class="year"></span><span id="start-date"></span>
            <span id="end-date"></span><span id="end-time"></span>
        `;
        $.ajax = jest.fn();
    });

    afterEach(() => {
        delete globalThis.CWKC_REHEARSAL_VIEW_UNTIL;
        $.ajax = originalAjax;
        jest.clearAllTimers();
        jest.useRealTimers();
        jest.restoreAllMocks();
    });

    function loadWithFreshReady(now) {
        jest.setSystemTime(now);
        let isolatedMain;
        // The project's jest.setup.js runs document.ready immediately.
        jest.isolateModules(() => {
            isolatedMain = require('./main');
        });
        return isolatedMain;
    }

    test('phase boundaries are inclusive at kickoff and exclusive at the deadline', () => {
        const main = loadWithFreshReady(new Date(start.getTime() - 1000));
        expect(main.getContestPhase(new Date(start.getTime() - 1))).toBe('upcoming');
        expect(main.getContestPhase(start)).toBe('active');
        expect(main.getContestPhase(new Date(deadline.getTime() - 1))).toBe('active');
        expect(main.getContestPhase(deadline)).toBe('ended');
    });

    test('approved short-lived rehearsal shows real live scoreboard before kickoff', () => {
        const now = new Date(start.getTime() - 60000);
        globalThis.CWKC_REHEARSAL_VIEW_UNTIL =
            new Date(now.getTime() + 30000).toISOString();

        const main = loadWithFreshReady(now);
        expect(main.getContestPhase(now)).toBe('active');
        expect($('#countdown-text').text()).toBe('The Cup Ends In');
        expect($.ajax).toHaveBeenCalledTimes(1);
        expect($('.enable-during-contest')[0].style.pointerEvents).toBe('');

        // The same published site automatically reverts to prelaunch phase
        // when its temporary marker expires; the official dates stay fixed.
        expect(main.getContestPhase(new Date(now.getTime() + 29999))).toBe('active');
        expect(main.getContestPhase(new Date(now.getTime() + 30000))).toBe('upcoming');
        expect(main.getContestPhase(start)).toBe('active');
    });

    test('unapproved or late rehearsal marker cannot activate site early', () => {
        const now = new Date(start.getTime() - 60000);
        globalThis.CWKC_REHEARSAL_VIEW_UNTIL =
            new Date(start.getTime() + 3600000).toISOString();
        const main = loadWithFreshReady(now);
        expect(main.getContestPhase(now)).toBe('upcoming');
        expect($.ajax).not.toHaveBeenCalled();
        expect($('.enable-during-contest')[0].style.pointerEvents).toBe('none');
    });

    test('pre-start page makes no CSV request and keeps form links disabled', () => {
        loadWithFreshReady(new Date(start.getTime() - 5000));
        expect($.ajax).not.toHaveBeenCalled();
        expect($('#countdown-text').text()).toBe('The Cup Starts In');
        expect($('#uva_total_amount').text()).toBe('0');
        expect($('.enable-during-contest')[0].style.pointerEvents).toBe('none');

        jest.advanceTimersByTime(2000);
        expect($.ajax).not.toHaveBeenCalled();
    });

    test('open pre-start tab switches countdown and begins polling at kickoff', () => {
        loadWithFreshReady(new Date(start.getTime() - 1000));
        expect($.ajax).not.toHaveBeenCalled();

        jest.advanceTimersByTime(1000);
        expect($('#countdown-text').text()).toBe('The Cup Ends In');
        expect($('#countdown').text()).not.toMatch(/win|tie/i);
        expect($('.enable-during-contest')[0].style.pointerEvents).toBe('');
        expect($.ajax).toHaveBeenCalledTimes(1);

        jest.advanceTimersByTime(5000);
        expect($.ajax).toHaveBeenCalledTimes(2);
        expect($('#countdown-text').text()).toBe('The Cup Ends In');
    });

    test('page opened during event immediately fetches live scores', () => {
        loadWithFreshReady(start);
        expect($('#countdown-text').text()).toBe('The Cup Ends In');
        expect($.ajax).toHaveBeenCalledTimes(1);
        expect($('.enable-during-contest')[0].style.pointerEvents).toBe('');
    });

    test('page opened after deadline fetches final scores only once', () => {
        loadWithFreshReady(new Date(deadline.getTime() + 1000));
        expect($.ajax).toHaveBeenCalledTimes(1);
        jest.advanceTimersByTime(10000);
        expect($.ajax).toHaveBeenCalledTimes(1);
        expect($('#countdown').text()).toContain(`${globalThis.CWKC_SEASON.year} Commonwealth Kiddush Cup`);
        expect($('.enable-during-contest')[0].style.pointerEvents).toBe('none');
    });

    test('published scoreboard retains a readable, single-row metric schema', () => {
        const csv = fs.readFileSync(path.join(__dirname, '../csv/results.csv'), 'utf8');
        const rows = Papa.parse(csv, {header: true, skipEmptyLines: true}).data;
        expect(rows).toHaveLength(1);
        expect(Object.keys(rows[0])).toHaveLength(26);
        expect(rows[0]).toHaveProperty('uva_hanukkah_photos');
        expect(rows[0]).toHaveProperty('vt_hanukkah_photos');
        expect(rows[0]).toHaveProperty('uva_most_donors_class_2026');
        expect(rows[0]).not.toHaveProperty('uva_most_undergraduates');
        expect(rows[0]).not.toHaveProperty('uva_mitzvah_memories');
        for (const [key, value] of Object.entries(rows[0])) {
            if (key.endsWith('_donor_names')) {
                expect(typeof value).toBe('string');
            } else {
                // Results can be nonzero during the cup; tests must not force
                // production totals back to zero after collection begins.
                expect(value).not.toBe('');
                expect(Number.isFinite(Number(value))).toBe(true);
            }
        }
    });
});
