"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
"""

import vut.engine.compare.main                                  as     compare
from   vut.engine.compare.configuration                         import Configuration
from   vut.engine.compare.engine.chunk_pair_list                import ChunkPairList
from   vut.user_interface.difference_display.console.canvas     import ConsoleUI, E_LinePairSelectionMode
import vut.system.terminal.size                                 as     terminal_size
from   vut.user_interface.difference_display.console.interaction_mode_diff_display import InteractionModeDiff

from   io import StringIO

subject_txt = \
"""Sah ein Röslein 1.005 Knab stehen
Röslein auf der     ((Wiese))
War jung morgenschön, wtf,
Lief er ganz schnell es von nah zu sehn
Schaut's mit 1000 Freuden
Röslein, Tülplein, Röslein orange
Röslein auf der ((Wiese))
"""

nominal_txt = \
"""
Sah ein Knab 1 Röslein stehen, hm,
Röslein   auf der   ((Heiden))
War so jung und morgenschön
Lief er schnell es nah zu sehn
Schaut's mit vielen Freuden (who cares)
Röslein, Röslein, Röslein rot
Röslein auf der ((Heiden))
"""

subject_modified_txt = \
"""Sah ein Röslein ein Knab stehen
Röslein   auf der   Heiden 
War jung morgenschön
Röslein, Tülplein, Röslein orange
"""

subject_comment_txt = \
"""## Wilhem the Tell
Sah ein Röslein ein Knab stehen
Röslein   auf der   Heiden 
War jung morgenschön
## Was willst Du mit dem Dolche sprich
Röslein, Tülplein, Röslein orange
Das sollst Du mir am Kreuz bereun##
"""

nominal_comment_txt = \
"""Sah ein Röslein ein Knab stehen
## So fragt ihn ernst der Wüterich
Röslein   auf der   Heiden 
War jung morgenschön
Das Land vom Tyrannen befrein ##
Röslein, Tülplein, Röslein orange
"""


analogy_subject = \
"""
Knabe sprach: ((wir)) breche ((dich)),
((Röslein)) ((auf)) der ((Wiese))!
((Röslein)) sprach: Ich steche ((dich)),
daß du ewig denkst an mich,
und ((wir)) will's nicht leiden.
((Röslein)), ((Röslein)), ((Tülplein)) rot,
((Röslein)) ((unter)) der ((Wiese)).
"""

analogy_nominal = \
"""
Knabe sprach: ((ich)) breche ((dich)),
((Röslein)) ((auf)) der ((Heiden))!
((Röslein)) sprach: Ich steche ((dich)),
daß du ewig denkst an mich,
und ((ich)) will's nicht leiden.
((Röslein)), ((Röslein)), ((Röslein)) rot,
((Röslein)) ((auf)) der ((Heiden)).
"""

mix_subject = \
"""
Zwei
Vier
Fünf
"""

mix_nominal = \
"""
Eins
Zwei
Drei
Vier
Fünf
"""

nominal_error_txt = \
"""
eins
zwei
drei
vier
fuenf
sechs
sieben
acht 
neun
zehn
elf
zwölf
dreizehn
vierzehn
fuenfzehn
sechzehn
siebzehn
achtzehn
neunzehn
zwanzig
einundzwanzig
zweiundzwanzig
"""

subject_error_txt = \
"""
eins           !!
zwei           !!
drei
vier           !!
fuenf
sechs
sieben         !!
acht 
neun
zehn
elf            !!
zwölf
dreizehn
vierzehn
fuenfzehn
sechzehn       !!
siebzehn
achtzehn
neunzehn
zwanzig
einundzwanzig
zweiundzwanzig !!
"""

subject_error2_txt = \
"""
eins
zwei
drei
vier     
fuenf !!
sechs
sieben
acht 
neun
zehn
elf
zwölf
dreizehn
vierzehn
fuenfzehn
sechzehn
siebzehn
achtzehn !!
neunzehn  
zwanzig        
einundzwanzig
zweiundzwanzig
"""

config = Configuration()
config.pattern_finder.numeric_tolerance_ratio = 0.01
config.pattern_finder.equivalent_pattern_list = ["rot|orange", "Röslein|Tülplein"]
config.pattern_finder.visible_nothing_pattern_list = [", hm,", ", wtf,", "[ ]*\(who cares\)"]

def test_core(subject_txt, nominal_txt, offset, mode, level):
    global config
    terminal_width  = 80
    terminal_height = 30
    subject = StringIO(subject_txt)
    nominal = StringIO(nominal_txt)

    print("|" + "=" * (terminal_width -2) + "|")
    la = list(compare.associate(config, subject, nominal))

    terminal_size.set_size_fixed(terminal_height, terminal_width)
    canvas = ConsoleUI(ChunkPairList(la), InteractionModeDiff)
    canvas.set_selection_mode(mode, level)
    canvas._display_content()

def test(subject_txt, nominal_txt, offset=0, mode=E_LinePairSelectionMode.PLAIN, level=0, both=True):
    if True:
        test_core(subject_txt, nominal_txt, offset, mode, level)
    if both: 
        test_core(nominal_txt, subject_txt, offset, mode, level)

