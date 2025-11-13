// jest.setup.js
global.$ = require('jquery');
global.Papa = require('papaparse');

// Mock document.ready to call the callback immediately
$.fn.ready = function(callback) {
    callback();
    return this;
};