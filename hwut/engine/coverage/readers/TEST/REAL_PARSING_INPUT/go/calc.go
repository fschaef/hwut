package demo

// Sign returns -1, 0 or 1.
func Sign(n int) int {
	if n < 0 {
		return -1
	} else if n == 0 {
		return 0
	}
	return 1
}

// Unused is never called.
func Unused(n int) int {
	return n * 2
}
