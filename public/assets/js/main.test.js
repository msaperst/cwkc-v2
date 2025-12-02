const fs = require('fs');
const $ = require('jquery');

const main = require('./main');

describe('Main', () => {
    const OriginalPapaParse = Papa.parse;
    const OriginalAjax = $.ajax;

    afterEach(() => {
        jest.clearAllMocks();
        jest.resetAllMocks();
        jest.restoreAllMocks();

        Papa.parse = OriginalPapaParse;
        $.ajax = OriginalAjax;
    });

    describe('Utility functions', () => {
        test('getNumber parses numbers with commas', () => {
            document.body.innerHTML = `<span id="num">1,234.56</span>`;
            expect(main.getNumber($('#num'))).toBe(1234.56);
        });

        test('formatNumber formats numbers correctly', () => {
            expect(main.formatNumber('1234')).toBe(1234);
            expect(main.formatNumber('1234.5')).toBe(1234.50);
            expect(main.formatNumber('1,234.5678')).toBe(1234.57);
        });

        test('getTimeRemaining returns correct structure', () => {
            const now = new Date();
            const future = new Date(now.getTime() + 1000 * 60 * 60 * 24 + 1000 * 65); // 1 day, 1 min 5 sec
            const result = main.getTimeRemaining(future);
            expect(result).toHaveProperty('days');
            expect(result).toHaveProperty('hours');
            expect(result).toHaveProperty('minutes');
            expect(result).toHaveProperty('seconds');
            expect(result).toHaveProperty('total');
        });

        test('getOrdinal returns correct suffix', () => {
            expect(main.getOrdinal(1)).toBe('st');
            expect(main.getOrdinal(2)).toBe('nd');
            expect(main.getOrdinal(3)).toBe('rd');
            expect(main.getOrdinal(4)).toBe('th');
            expect(main.getOrdinal(11)).toBe('th');
            expect(main.getOrdinal(22)).toBe('nd');
        });

        test('getDate formats date correctly', () => {
            const testDate = new Date('2025-12-07T20:00:00-05:00');
            const result = main.getDate(testDate);
            expect(result).toMatch(/December 7/);
        });
    });

    describe('DOM functions', () => {
        let originalDateNow;

        beforeEach(() => {
            originalDateNow = Date;

            document.body.innerHTML = `
            <span id="score1"></span>
            <span id="score2"></span>
            <div id="hooHigher" data-points="5">
                <span class="rounded-xl hooPoints">
                    <span>10</span>
                </span>
                <span class="points">
                </span>
                <span class="rounded-xl hokiePoints">
                    <span>5</span>
                </span>
            </div>
            <div id="hokieHigher" data-points="1">
                <span class="rounded-xl hooPoints">
                    <span>5</span>
                </span>
                <span class="points">
                </span>
                <span class="rounded-xl hokiePoints">
                    <span>10</span>
                </span>
            </div>
            <div id="hooTotal">3</div>
            <div id="hokieTotal">2</div>
            <div id="countdown" class="bg-primary">
                <span id="countdown-text"></span>
                <div class="days"></div>
                <div class="hours"></div>
                <div class="minutes"></div>
                <div class="seconds"></div>
            </div>
        `;
            // Mock Papa.parse
            Papa.parse = jest.fn((data, { complete }) => {
                complete({ data: [{ score1: '1000', score2: '2000' }] });
            });

            // Mock intervals so clearInterval() doesn't complain
            global.timerInterval = setInterval(() => {
            }, 1000);
            global.refreshInterval = setInterval(() => {
            }, 1000);
        });

        afterEach(() => {
            global.Date = originalDateNow;
            jest.clearAllMocks();
            jest.restoreAllMocks();
            clearInterval(global.timerInterval);
            clearInterval(global.refreshInterval);
        });

        test('loadScores parses CSV data and updates DOM', () => {
            main.loadScores('mock CSV');
            expect($('#score1').text()).toBe('1,000');
            expect($('#score2').text()).toBe('2,000');
        });

        test('loadScores property states points', () => {
            main.loadScores('mock CSV');
            expect($('#hooHigher span.points').text()).toBe('(5 Points)');
            expect($('#hokieHigher span.points').text()).toBe('(1 Point)');
        });

        test('loadScores sets uva as winner', () => {
            main.loadScores('mock CSV');
            expect($('#hooHigher span.hooPoints').hasClass('bg-hoo-blue/100')).toBeTruthy();
            expect($('#hooHigher span.hokiePoints').hasClass('bg-hokie-maroon/50')).toBeFalsy();
        });

        test('loadScores sets vt as winner', () => {
            main.loadScores('mock CSV');
            expect($('#hokieHigher span.hooPoints').hasClass('bg-hoo-blue/100')).toBeFalsy();
            expect($('#hokieHigher span.hokiePoints').hasClass('bg-hokie-maroon/50')).toBeTruthy();
        });

        test('loadScores sets proper total points', () => {
            main.loadScores('mock CSV');
            expect($('#hooTotal').text()).toBe('5');
            expect($('#hokieTotal').text()).toBe('1');
        });

        test('updateClock updates DOM countdown', () => {
            const future = new Date(Date.now() + 5000); // 5 seconds ahead
            main.updateClock(future);
            expect($('.seconds').text()).toBeDefined();
        });

        test('updateClock handles expired countdown when it\'s it tie and updates DOM correctly', () => {
            document.body.innerHTML = `
            <div id="hooTotal">2</div>
            <div id="hokieTotal">2</div>
            <div id="countdown">
                <div class="days"></div>
                <div class="hours"></div>
                <div class="minutes"></div>
                <div class="seconds"></div>
            </div>
        `;

            // Create an end time in the past
            const past = new Date(Date.now() - 10000);

            // Spy so we can assert clearInterval() was invoked
            const clearSpy = jest.spyOn(global, 'clearInterval');

            main.updateClock(past);

            // Clear interval should be called twice
            expect(clearSpy).toHaveBeenCalledTimes(2);

            expect($('#countdown').html()).toContain('It\'s a tie for the 2025 Commonwealth Kiddush Cup!');
            expect($('#countdown').hasClass('bg-hoo-blue')).toBe(false);
            expect($('#countdown').hasClass('bg-hokie-maroon')).toBe(false);

            expect($('.days').length).toBe(0);
            expect($('.hours').length).toBe(0);
            expect($('.minutes').length).toBe(0);
            expect($('.seconds').length).toBe(0);

            clearSpy.mockRestore();
        });

        test('updateClock handles expired countdown when hoos win and updates DOM correctly', () => {
            document.body.innerHTML = `
            <div id="hooTotal">3</div>
            <div id="hokieTotal">2</div>
            <div id="countdown">
                <div class="days"></div>
                <div class="hours"></div>
                <div class="minutes"></div>
                <div class="seconds"></div>
            </div>
        `;

            // Create an end time in the past
            const past = new Date(Date.now() - 10000);

            // Spy so we can assert clearInterval() was invoked
            const clearSpy = jest.spyOn(global, 'clearInterval');

            main.updateClock(past);

            // Clear interval should be called twice
            expect(clearSpy).toHaveBeenCalledTimes(2);

            expect($('#countdown').html()).toContain('Hoos win the 2025 Commonwealth Kiddush Cup!');
            expect($('#countdown').hasClass('bg-hoo-blue')).toBe(true);
            expect($('#countdown').hasClass('bg-hokie-maroon')).toBe(false);

            clearSpy.mockRestore();
        });

        test('updateClock handles expired countdown when hokies win and updates DOM correctly', () => {
            document.body.innerHTML = `
            <div id="hooTotal">2</div>
            <div id="hokieTotal">3</div>
            <div id="countdown">
                <div class="days"></div>
                <div class="hours"></div>
                <div class="minutes"></div>
                <div class="seconds"></div>
            </div>
        `;

            // Create an end time in the past
            const past = new Date(Date.now() - 10000);

            // Spy so we can assert clearInterval() was invoked
            const clearSpy = jest.spyOn(global, 'clearInterval');

            main.updateClock(past);

            // Clear interval should be called twice
            expect(clearSpy).toHaveBeenCalledTimes(2);

            expect($('#countdown').html()).toContain('Hokies win the 2025 Commonwealth Kiddush Cup!');
            expect($('#countdown').hasClass('bg-hoo-blue')).toBe(false);
            expect($('#countdown').hasClass('bg-hokie-maroon')).toBe(true);

            clearSpy.mockRestore();
        });

        test('Contest finished (countdown past deadline)', () => {
            // Mock Date so that "now" is after the deadline, hitting the else branch
            const mockNow = new Date('2025-12-08T12:00:00-05:00');
            global.Date = class extends Date {
                constructor(...args) {
                    if (args.length === 0) return mockNow;
                    return new originalDateNow(...args);
                }

                static now() {
                    return mockNow.getTime();
                }
            };

            // require main.js again to trigger $(document).ready()
            jest.isolateModules(() => {
                require('./main');
            });

            // Check that the countdown div was cleared
            expect($('#countdown').html()).toBe('');
            // Since the else branch clears the timer, the countdown-text should remain unchanged
            expect($('#countdown-text').text()).toBe('');
        });

        test('Contest ongoing (still before deadline)', () => {
            const mockNow = new Date('2025-12-05T12:00:00-05:00'); // before deadline
            global.Date = class extends Date {
                constructor(...args) {
                    if (args.length === 0) return mockNow;
                    return new originalDateNow(...args);
                }

                static now() {
                    return mockNow.getTime();
                }
            };

            jest.isolateModules(() => {
                require('./main');
            });

            // Check that the countdown-text was updated for ongoing contest
            expect($('#countdown-text').text()).toBe('The Cup Ends In');
            expect($('#countdown').html()).not.toBe('');
        });
    });

    describe('Fetch functions', () => {
        test('getResultsData updates DOM via loadScores', () => {
            $.ajax = jest.fn((options) => {
                // Immediately call the success callback with some mock data
                if (options.success) {
                    const mockCSV = 'score1,score2,names,points\n1000,2000,"Max Saperstone, Becca Goldberg",-';
                    options.success(mockCSV);
                }
            });

            document.body.innerHTML = `
        <span>$<span id="hooTotal"></span></span>
        <span>$<span id="hokieTotal"></span></span>
        <span>$<span id="score1"></span></span>
        <span><span id="score2"></span></span>
        <span><span id="names"></span></span>
        <span><span id="points"></span></span>
    `;

            // Call the function
            main.getResultsData();

            // Check that the DOM was updated
            expect($('#score1').text()).toBe('1,000.00');
            expect($('#score2').text()).toBe('2,000');
            expect($('#names').text()).toBe('Max SaperstoneBecca Goldberg');
            expect($('#points').text()).toBe('-');
        });
    });
});