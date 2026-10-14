function double(n) { if (n < 0) { return -2 * n; } return 2 * n; }
function neverCalled(n) { return n + 1; }
console.log("out:", double(4));
