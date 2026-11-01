// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// THE PRODUCER OF 'protocol.sh clean' -- no test, the service it feeds into
// 'protocol.pype'. Five clients talk to it at once, each a goroutine: a
// request, a moment, its response; then 'shutdown'. Every line is written
// as it happens (Go's stdout is not buffered); the order is the scheduler's.
// It prints no '<hwut-end>': the pype's '<eof>' does.
// _____________________________________________________________________________

package main

import (
	"fmt"
	"math/rand/v2"
	"sync"
	"time"
)

var lock sync.Mutex

// RETURN: nothing; 'text' is printed as one line, never torn by another.
func say(text string) {
	lock.Lock()
	defer lock.Unlock()
	fmt.Println(text)
}

// RETURN: nothing; waits up to 20 ms, drawn at random.
func pause() {
	time.Sleep(time.Duration(rand.Float64() * 0.02 * float64(time.Second)))
}

// RETURN: nothing; the five clients have talked, and 'shutdown' is said.
func main() {
	var group sync.WaitGroup
	for n := 1; n <= 5; n++ {
		group.Add(1)
		go func(n int) {
			defer group.Done()
			pause()
			say(fmt.Sprintf("request %d", n))
			pause()
			say(fmt.Sprintf("response %d", n))
		}(n)
	}
	group.Wait()
	say("shutdown")
}
