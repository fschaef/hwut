// web/errors.js -- error codes of the web backend: range 2000..2999
'use strict';
const E_BAD_REQUEST     = 2001;
const E_UNAUTHORIZED    = 2002;
const E_DEVICE_OFFLINE  = 2010;
const E_SESSION_EXPIRED = 1004;
module.exports = { E_BAD_REQUEST, E_UNAUTHORIZED, E_SESSION_EXPIRED, E_DEVICE_OFFLINE };
