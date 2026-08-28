#! /usr/bin/env python
#
# @hwut {
#     title      = "The HTML generator feeder"
# }
#
import io
import sys
import asyncio
import argparse

# Adjust path to find vut
sys.path.insert(0, "../../../../../")

import vut.engine.compare.feeder.html_feeder as html_feeder
from   vut.engine.compare.configuration      import Configuration


SIGNATURE = 'mmiFiE-j4bsvTLp0iGNZEAJF9GErpfkXjVZc9Xw0yi8'

nominal = """
There once was a ((Object)) made of ((Material)),
Who pondered the things that it said.
"Even the largest fahrt," it began with a roar,
"Starts with 1.0 gas atom leaving the door."
Then it dissolved into raindrops of bread.

A ((Persona)) in a ((Location)) maze,
Observed the electric 0.5 blue haze.
"I think, therefore I am... not quite sure,"
He whispered while scrubbing the floor of the pure,
"For a bug in the code ends 100.0 days."

##! potpourri
The ((Animal)) in the desert was dry,
With a telescope aimed at the sky.
"That which does not kill us makes us 42.0 percent strange,"
((Object)) noted while rearranging the range,
Then ate a gold watch and started to fly.
####

##! potpourri
A ((Object)) sat down on a chair,
To contemplate why it was there.
"To be, or not to be... a small grape,"
It sighed as it shifted its 3.14159 geological shape,
"Is a question that leaves me quite bare."
####

A ((hole in the wall)) looked out at its arse,
And watched the transparent 10.0 years pass.
"The unexamined life is a pane in the neck,"
It muttered while counting a solitary speck,
Then turned into liquid and sat on the grass.
"""

subject = """
There once was a ((mouse)) made of ((Glass)),
Who pondered the things that it said.
"Even the largest fahrt," it began with a roar,
"Starts with 1.05 gas atom leaving the door."
Then it dissolved into raindrops of bread.

A ((Monk)) in a ((Monastery)) maze,
Observed the electric 0.51 blue haze.
"I think, therefore I am... not quite sure,"
"For a bug in the code ends 102.0 days."

##! potpourri
"That which does not kill us makes us 42.1 percent strange,"
The ((Animal)) in the desert was dry,
With a telescope aimed at the sky.
A ((mouse)) noted while rearranging the range,
Then ate a gold watch and started to fly.
####

##! potpourri
A ((Object)) sat down on a chair,
To contemplate why it was there.
"To be, or not to be... a small grape,"
"Is a question that leaves me quite bare."
It sighed as it shifted its 3.14 geological shape,
####

A ((Window)) looked out at its glas,
"The unexamined life is a pane in the heck,"
It muttered pendant que counting a solitary speck,
Then turned into butter and sat on the grass.
"""

if __name__ == "__main__":
    if "--hwut-info" in sys.argv:
        print("The HTML generator feeder;")
        sys.exit()
    parser = argparse.ArgumentParser(description="VUT UI Feeder Test Script")

    parser.add_argument("--inspect", type=int, help="Print cell data for a specific line number to stdout instead of HTML")
    parser.add_argument("--hwut-info", action="store_true", help="Show test purpose")
    
    args = parser.parse_args()
    
    s_stream = io.StringIO(subject)
    n_stream = io.StringIO(nominal)

    if args.hwut_info:
        print("Testing UI-feeder producing HTML with hovers and Analogy Provenance tracking.")
    else:
        asyncio.run(html_feeder.run(s_stream, n_stream, sys.stdout, Configuration()))

    import time
    time.sleep(0.01)
    print("<!-- terminated -->")

