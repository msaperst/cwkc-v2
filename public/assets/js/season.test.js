const fs = require('fs');
const path = require('path');
const $ = require('jquery');

describe('2026 contest lifecycle', () => {
    const start = new Date('2026-11-30T00:00:00-05:00');
    const deadline = new Date('2026-12-07T20:00:00-05:00');
    let originalAjax;

    beforeEach(() => {
        originalAjax = $.ajax;
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
        const main = loadWithFreshReady(new Date('2026-11-29T23:59:59-05:00'));
        expect(main.getContestPhase(new Date(start.getTime() - 1))).toBe('upcoming');
        expect(main.getContestPhase(start)).toBe('active');
        expect(main.getContestPhase(new Date(deadline.getTime() - 1))).toBe('active');
        expect(main.getContestPhase(deadline)).toBe('ended');
    });

    test('pre-start page makes no CSV request and keeps form links disabled', () => {
        loadWithFreshReady(new Date('2026-11-29T23:59:55-05:00'));
        expect($.ajax).not.toHaveBeenCalled();
        expect($('#countdown-text').text()).toBe('The Cup Starts In');
        expect($('#uva_total_amount').text()).toBe('0');
        expect($('.enable-during-contest')[0].style.pointerEvents).toBe('none');

        jest.advanceTimersByTime(2000);
        expect($.ajax).not.toHaveBeenCalled();
    });

    test('open pre-start tab switches countdown and begins polling at kickoff', () => {
        loadWithFreshReady(new Date('2026-11-29T23:59:59-05:00'));
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
        loadWithFreshReady(new Date('2026-12-07T20:00:01-05:00'));
        expect($.ajax).toHaveBeenCalledTimes(1);
        jest.advanceTimersByTime(10000);
        expect($.ajax).toHaveBeenCalledTimes(1);
        expect($('#countdown').text()).toContain('2026 Commonwealth Kiddush Cup');
        expect($('.enable-during-contest')[0].style.pointerEvents).toBe('none');
    });

    test('published scoreboard has a single zeroed 2026 row with no 2025 donor names', () => {
        const csv = fs.readFileSync(path.join(__dirname, '../csv/results.csv'), 'utf8');
        const rows = Papa.parse(csv, {header: true, skipEmptyLines: true}).data;
        expect(rows).toHaveLength(1);
        expect(Object.keys(rows[0])).toHaveLength(28);
        for (const [key, value] of Object.entries(rows[0])) {
            if (key.endsWith('_donor_names')) {
                expect(value).toBe('');
            } else {
                expect(value).toBe('0');
            }
        }
    });
});
