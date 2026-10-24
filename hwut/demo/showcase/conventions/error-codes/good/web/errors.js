// web/errors.js -- error codes of the web backend: range 2000..2999
'use strict';
const E_BAD_REQUEST     = 2001;
const E_UNAUTHORIZED    = 2002;
const E_RATE_LIMIT      = 2003;
const E_DEVICE_OFFLINE  = 2010;
module.exports = { E_BAD_REQUEST, E_UNAUTHORIZED, E_RATE_LIMIT, E_DEVICE_OFFLINE };
