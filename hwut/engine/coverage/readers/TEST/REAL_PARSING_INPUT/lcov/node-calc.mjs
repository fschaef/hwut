// A branch taken and one not, a function never called.
export function double(n) {
  if (n < 0) {
    return -2 * n;
  }
  return 2 * n;
}

export function neverCalled(n) {
  return n + 1;
}
