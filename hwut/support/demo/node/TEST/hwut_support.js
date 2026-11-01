// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: WHERE THE NODE TEST SUPPORT STANDS -- no test, a helper every test
//          here that uses the support requires. The port's location is named
//          on ONE line of this directory, the line marked below.
//
//     const support = require('./hwut_support.js');
//     const { HwutRunner } = support('hwut_runner');
//
// NODE_PATH, node's own mechanism, wins: where it names the port's directory
// a module is found as 'require("hwut_runner")' finds it in a test of the
// user's own. Only where it does not is the module taken from the marked
// line's path, relative to this file.
//_____________________________________________________________________________
'use strict';
const path = require('path');

/* RETURN: object, the exports of the support module 'name' ('hwut_runner',
 *         'hwut_vterm', ...), if it is found by NODE_PATH or by the marked
 *         line's path;
 *         throws node's MODULE_NOT_FOUND error, else -- or whatever the
 *         module threw while it was loaded. */
function support(name) {
    try {
        return require(name);
    } catch (error) {
        //  Only the module ITSELF missing hands over to the fallback; a
        //  module that is found and fails says so.
        if (error.code !== 'MODULE_NOT_FOUND' || !String(error.message).includes(`'${name}'`)) throw error;
    }
    return require(path.resolve(__dirname, '../../../test_writing/node', name));  // HWUT-SUPPORT-PATH
}

module.exports = support;
