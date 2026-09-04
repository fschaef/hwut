export function double(n: number): number {
  if (n < 0) {
    return -2 * n;
  }
  return 2 * n;
}
export function neverCalled(n: number): number {
  return n + 1;
}
console.log("out:", double(5));
