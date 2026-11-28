package demo

import "testing"

func TestSign(t *testing.T) {
	if Sign(-3) != -1 || Sign(5) != 1 {
		t.Fatal("sign")
	}
}
