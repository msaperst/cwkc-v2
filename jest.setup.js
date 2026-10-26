// jest.setup.js
global.$ = require('jquery');
global.Papa = require('papaparse');
// Load the same generated config script as the production HTML.
require('./public/assets/js/season-config.js');

// Mock document.ready to call the callback immediately
$.fn.ready = function(callback) {
    callback();
    return this;
};