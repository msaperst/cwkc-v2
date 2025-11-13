const deadline = new Date(Date.parse('December 7, 2025 8:00 PM GMT-0500'));
const startTime = new Date(Date.parse('December 1, 2025 12:00 AM GMT-0500'));
// const year = new Date().getFullYear();
const year = 2025;
const speedPxPerSec = 50;

let timerInterval;  // interval to track countdown
let refreshInterval;    // interval to track page refresh
let countdownUntil; // when we are counting down to

/**
 * retrieve our results data (stored in the CSV)
 */
function getResultsData() {
    $.ajax({
        type: 'GET',
        url: `./assets/csv/results.csv?${Date.parse(new Date())}`,
        dataType: 'text',
        success: function(data) {
            loadScores(data);
        },
    });
}

/**
 * Loads in CSV data (not a file itself, raw data from one), and processes it. We are
 * expecting a list of key-values where each key is the score area (with indicated school)
 * of the field, and the value is the score. Each value will be placed in the appropriate
 * cell, as a correlating ID for each key exists.
 * @param data raw CSV data
 */
function loadScores(data) {
    Papa.parse(data, {
        header: true,
        complete: function(results) {
            // loop through the results, and place each value in the appropriate location
            $.each(results.data[0], function(key, value) {
                const span = $(`#${key}`);
                const parentHasDollar = span.parent().text().includes('$');

                const numValue = parseFloat(String(value).replace(/,/g, ''));

                if (!isNaN(numValue) && isFinite(numValue)) {
                    // It's numeric
                    let formatted = numValue;

                    if (parentHasDollar) {
                        formatted = numValue.toFixed(2); // 2 decimal places if money
                    }

                    // Add commas
                    formatted = formatted.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');

                    span.text(formatted);
                } else {
                    // Not numeric, split up values, and place each one in a span
                    // TODO - only empty/change these if there are different values - avoids flickering
                    span.empty();

                    const values = value.split(',').map(v => v.trim());
                    $.each(values, function(_, value) {
                        const container = $('<span>').text(value).css('margin-right', values.length > 1 ? '2rem' : '0');
                        span.append(container);
                    });
                    if (values.length > 1) {
                        const totalWidth = span[0].scrollWidth;
                        const duration = totalWidth / speedPxPerSec;
                        span.css({
                            'padding-left': '100%',
                            'display': 'inline-block',
                            'white-space': 'nowrap',
                            'animation': 'scroll-left ' + duration + 's linear infinite',
                        });
                    }
                }
            });

            // clear out any winners
            $('[data-points] .bg-hoo-blue\\/100').removeClass('bg-hoo-blue/100').addClass('bg-white/5');
            $('[data-points] .bg-hokie-maroon\\/50').removeClass('bg-hokie-maroon/50').addClass('bg-white/5');

            // track the scores as we go
            let uvaScore = 0;
            let techScore = 0;

            // loop through each of the scored areas
            $('[data-points]').each(function() {
                // determine how many points for the area
                const points = parseInt($(this).attr('data-points'));
                $(this).find('span.points').html(`(${points} Point${points > 1 ? 's' : ''})`);

                // determine who is winning in each area
                const values = $(this).find('.rounded-xl span');
                // if UVA (left column) has a higher number, mark it as a winner and add the points
                if (getNumber(values[0]) > getNumber(values[1])) {
                    $(values[0]).parent().removeClass('bg-white/5').addClass('bg-hoo-blue/100');
                    uvaScore += points;
                }
                // if Tech (right column) has a higher number, mark it as a winner and add the points
                if (getNumber(values[0]) < getNumber(values[1])) {
                    $(values[1]).parent().removeClass('bg-white/5').addClass('bg-hokie-maroon/50');

                    techScore += points;
                }
            });

            // record each teams total points
            $('#hooTotal').html(uvaScore);
            $('#hokieTotal').html(techScore);

            // update the timer/score
            updateClock(countdownUntil);
        },
        error: function(error) {
            console.error('Error parsing CSV:', error);
        },
    });
}

/**
 * Takes a css selector and returns a floating value from the element's contents
 * @param element css selector
 * @returns {number} floating point number
 */
function getNumber(element) {
    return parseFloat($(element).html().replace(/,/g, ''));
}

/**
 * takes a number, and if it has a decimal place, rounds it to two
 * places, otherwise leaves it with none
 */
function formatNumber(num) {
    num = parseFloat(num.replace(/,/g, ''));
    // Check if the number is an integer by comparing it to its integer part
    if (Number.isInteger(num)) {
        return num; // Return as-is if it's an integer
    } else {
        return parseFloat(num.toFixed(2)); // Format to 2 decimal places if float
    }
}

/**
 * Returns an array of values for now much time is remaining
 * @param endTime the time to determine the difference against
 * @returns {{total: number, days: number, hours: number, minutes: number, seconds: number}} time left
 */
function getTimeRemaining(endTime) {
    const t = Date.parse(endTime) - Date.parse(new Date());
    const seconds = Math.floor((t / 1000) % 60);
    const minutes = Math.floor((t / 1000 / 60) % 60);
    const hours = Math.floor((t / (1000 * 60 * 60)) % 24);
    const days = Math.floor(t / (1000 * 60 * 60 * 24));
    return {
        'total': t,
        'days': days,
        'hours': hours,
        'minutes': minutes,
        'seconds': seconds,
    };
}

/**
 * Ticks down how much time is left until `endTime`. If no time is remaining,
 * the clock is stopped and a winner is determined
 * @param endTime the time to tick down to
 */
function updateClock(endTime) {
    const timeRemaining = getTimeRemaining(endTime);

    if (timeRemaining.total <= 0) {
        clearInterval(timerInterval);
        clearInterval(refreshInterval);
        const winner = getNumber('#hooTotal') > getNumber('#hokieTotal') ? 'Hoos' : 'Hokies';
        const clock = $('#countdown');
        clock.html(winner + ` win the ${year} Commonwealth Kiddush Cup!<br/><br/><small>and a big THANK YOU to everyone who gave!</small>`);
        clock.addClass(winner.toLowerCase().slice(0, -1)).removeClass('bg-primary');
    }

    $('.days').html(timeRemaining.days);
    $('.hours').html(('0' + timeRemaining.hours).slice(-2));
    $('.minutes').html(('0' + timeRemaining.minutes).slice(-2));
    $('.seconds').html(('0' + timeRemaining.seconds).slice(-2));
}

// Helper for ordinal suffix (st, nd, rd, th)
function getOrdinal(n) {
    const s = ['th', 'st', 'nd', 'rd'];
    const v = n % 100;
    return s[(v - 20) % 10] || s[v] || s[0];
}

function getDate(date) {
    const optionsDate = { month: 'long', day: 'numeric', timeZone: 'America/New_York' };
    const dateFormatter = new Intl.DateTimeFormat('en-US', optionsDate);

    // Get month and day with ordinal
    const endParts = dateFormatter.formatToParts(date);
    const endMonth = endParts.find(p => p.type === 'month').value;
    const endDay = endParts.find(p => p.type === 'day').value;
    return `${endMonth} ${endDay}${getOrdinal(Number(endDay))}`;
}

function setTimes() {
    $('#start-date').html(getDate(startTime));
    $('#end-date').html(getDate(deadline));

    // Format date for Eastern Time
    const optionsTime = {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
        timeZone: 'America/New_York',
        timeZoneName: 'short',
    };

    // Extract formatted parts
    const timeFormatter = new Intl.DateTimeFormat('en-US', optionsTime);

    // Get time in EST/EDT
    const time = timeFormatter.format(deadline);

    $('#end-time').html(time);
}

$(document).ready(() => {
    if (startTime > new Date()) {    // if in the future, show how many days until it starts
        countdownUntil = startTime;
        updateClock(countdownUntil);
        $('#countdown-text').html('The Cup Starts In');
    } else {    // if not, show how many days until it ends
        countdownUntil = deadline;
        if (deadline > new Date()) {    // if we're still in the window, start the timer
            updateClock(countdownUntil);
            $('#countdown-text').html('The Cup Ends In');
        } else {    // otherwise, wipe out the timer, and wait for the results
            $('#countdown').html('');
        }
    }
    // set an interval to keep the timer ticker (what we tick down to is set above)
    timerInterval = setInterval(() => updateClock(countdownUntil), 1000);

    // set our dates
    setTimes();

    // retrieve our results data (stored in the CSV)
    getResultsData();
    refreshInterval = setInterval(getResultsData, 5000);

    // set the year we're interested in
    $('#year').html(year);

    // enable/disable our form links
    if (startTime > new Date() || deadline < new Date()) {
        const collection = document.getElementsByClassName('enable-during-contest');
        for (let i = 0, len = collection.length; i < len; i++) {
            collection[i].style['pointerEvents'] = 'none';
        }
    }
});

// export for testing
if (typeof module !== 'undefined') {
    module.exports = {
        getNumber,
        formatNumber,
        getTimeRemaining,
        getOrdinal,
        getDate,
        loadScores,
        updateClock,
        setTimes,
        getResultsData,
    };
}
