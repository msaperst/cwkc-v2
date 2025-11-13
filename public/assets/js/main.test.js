const fs = require('fs');
const $ = require('jquery');
const {
    getNumber,
    formatNumber,
    getTimeRemaining,
    getOrdinal,
    getDate,
    loadScores,
    updateClock,
    setTimes,
    getResultsData,
} = require('./main');

describe('Utility functions', () => {

    beforeAll(() => {
        // Mock jQuery $.ajax globally
        $.ajax = jest.fn((options) => {
            // Immediately call the success callback with some mock data
            if (options.success) {
                const mockCSV = 'score1,score2\n1000,2000';
                options.success(mockCSV);
            }
        });
    });

    test('getNumber parses numbers with commas', () => {
        document.body.innerHTML = `<span id="num">1,234.56</span>`;
        expect(getNumber($('#num'))).toBe(1234.56);
    });

    test('formatNumber formats numbers correctly', () => {
        expect(formatNumber('1234')).toBe(1234);
        expect(formatNumber('1234.5')).toBe(1234.50);
        expect(formatNumber('1,234.5678')).toBe(1234.57);
    });

    test('getTimeRemaining returns correct structure', () => {
        const now = new Date();
        const future = new Date(now.getTime() + 1000 * 60 * 60 * 24 + 1000 * 65); // 1 day, 1 min 5 sec
        const result = getTimeRemaining(future);
        expect(result).toHaveProperty('days');
        expect(result).toHaveProperty('hours');
        expect(result).toHaveProperty('minutes');
        expect(result).toHaveProperty('seconds');
        expect(result).toHaveProperty('total');
    });

    test('getOrdinal returns correct suffix', () => {
        expect(getOrdinal(1)).toBe('st');
        expect(getOrdinal(2)).toBe('nd');
        expect(getOrdinal(3)).toBe('rd');
        expect(getOrdinal(4)).toBe('th');
        expect(getOrdinal(11)).toBe('th');
        expect(getOrdinal(22)).toBe('nd');
    });

    test('getDate formats date correctly', () => {
        const testDate = new Date('2025-12-07T20:00:00-05:00');
        const result = getDate(testDate);
        expect(result).toMatch(/December 7/);
    });
});

describe('DOM functions', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <span id="score1"></span>
            <span id="score2"></span>
            <div data-points="5">
                <span class="rounded-xl">
                    <span>10</span><span>20</span>
                </span>
            </div>
            <div id="hooTotal"></div>
            <div id="hokieTotal"></div>
            <div class="days"></div>
            <div class="hours"></div>
            <div class="minutes"></div>
            <div class="seconds"></div>
        `;
    });

    test('loadScores parses CSV data and updates DOM', () => {
        // Mock Papa.parse
        Papa.parse = jest.fn((data, { complete }) => {
            complete({ data: [{ score1: '1000', score2: '2000' }] });
        });

        loadScores('mock CSV');
        expect($('#score1').text()).toBe('1,000');
        expect($('#score2').text()).toBe('2,000');
    });

    test('updateClock updates DOM countdown', () => {
        const future = new Date(new Date().getTime() + 5000); // 5 seconds ahead
        updateClock(future);
        expect($('.seconds').text()).toBeDefined();
    });
});

describe('Fetch functions', () => {
    test('getResultsData fetches and updates DOM', () => {
        // Mock loadScores so we can spy on it
        const { loadScores } = require('./cup');
        const loadScoresSpy = jest.spyOn(require('./cup'), 'loadScores');

        // Call function
        getResultsData();

        // Verify loadScores was called with CSV data
        expect(loadScoresSpy).toHaveBeenCalledWith(expect.stringContaining('score1,score2'));

        loadScoresSpy.mockRestore();
    });

    test('getResultsData updates DOM via loadScores', () => {
        document.body.innerHTML = `
        <span id="score1"></span>
        <span id="score2"></span>
    `;

        // Call the function
        getResultsData();

        // Check that the DOM was updated
        expect($('#score1').text()).toBe('1,000');
        expect($('#score2').text()).toBe('2,000');
    });
});