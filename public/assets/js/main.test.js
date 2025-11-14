const fs = require('fs');
const $ = require('jquery');

const main = require('./main');
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

        main.loadScores('mock CSV');
        expect($('#score1').text()).toBe('1,000');
        expect($('#score2').text()).toBe('2,000');
    });

    test('updateClock updates DOM countdown', () => {
        const future = new Date(new Date().getTime() + 5000); // 5 seconds ahead
        main.updateClock(future);
        expect($('.seconds').text()).toBeDefined();
    });
});

describe('Fetch functions', () => {
    beforeAll(() => {
        // Mock jQuery $.ajax globally
        $.ajax = jest.fn((options) => {
            // Immediately call the success callback with some mock data
            if (options.success) {
                const mockCSV = 'score1,score2,names,points\n1000,2000,"Max Saperstone, Becca Goldberg",-';
                options.success(mockCSV);
            }
        });
    });

    test('getResultsData updates DOM via loadScores', () => {
        document.body.innerHTML = `
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