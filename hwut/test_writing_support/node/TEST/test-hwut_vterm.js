// @hwut {
//     title      = "A terminal's screen read by a test: libvterm through koffi."
//     choices {
//         attributes { features = ["node-vterm"] }
//         colours    { features = ["node-vterm"] }
//         events     { features = ["node-vterm"] }
//         keys       { features = ["node-vterm"] }
//         missing    { features = ["node-vterm"] }
//         regions    { features = ["node-vterm"] }
//         screen     { features = ["node-vterm"] }
//         text       { features = ["node-vterm"] }
//         unnoticed  { features = ["node-vterm"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: The node port of 'python/TEST/test-hwut_vterm.py', choice for
//          choice, held against its GOOD files by '.link'. WANTS 'libvterm'
//          and the npm package 'koffi' ('npm install' in '..'); where either
//          is missing every choice but 'missing' says so in one line. The
//          two applications run on the pseudo-terminal are the Python test's
//          own -- the system under test -- run by 'python3 -c'.
//_____________________________________________________________________________
'use strict';
const path = require('path');
const { HwutRunner } = require(path.join(__dirname, '..', 'hwut_runner.js'));
const hwutVterm      = require(path.join(__dirname, '..', 'hwut_vterm.js'));
const { Screen, Terminal, LibraryMissing, IndexError, KeyError, ATTRIBUTE_SGR_DB } = hwutVterm;
const { strRepr, bytesRepr, tupleRepr, listRepr, boolText, noneOr } = require(path.join(__dirname, '..', 'pytext.js'));

const ESC    = '\x1b';
const PYTHON = 'python3';
const say    = text => console.log(text);
/* RETURN: string, a colour as Python prints the tuple, or 'None'. */
const colourText = rgb => rgb === null ? 'None' : tupleRepr(rgb);

/* RETURN: undefined. Every row that holds something, framed, then the cursor. */
function shown(screen) {
    screen.line_list().forEach((line, row) => { if (line) say(`    ${row} |${line}|`); });
    say(`    cursor ${tupleRepr(screen.cursor())}`);
}

/* RETURN: function, 'f' run on a library that is there; one line where it is not. */
function probe(f) {
    return () => {
        try { f(); }
        catch (error) {
            if (!(error instanceof LibraryMissing)) throw error;
            say(`NOT PROBED: ${error.message}`);
        }
    };
}

function runText() {
    new Screen(4, 12).use(screen => {
        say('-- plain, then carriage return and line feed');
        screen.feed(Buffer.from('hello\r\nworld'));
        shown(screen);
    });
    new Screen(4, 12).use(screen => {
        say('-- UTF-8: two bytes, one cell; a wide character, two');
        screen.feed(Buffer.from('ä日x', 'utf8'));
        shown(screen);
        for (let column = 0; column < 4; column += 1) {
            const cell = screen.cell(0, column);
            say(`    column ${column}: ${strRepr(cell.text).padEnd(6)} width ${cell.width}`);
        }
    });
    new Screen(3, 5).use(screen => {
        say('-- seven characters on five columns: the line wraps');
        screen.feed(Buffer.from('abcdefg'));
        shown(screen);
    });
    new Screen(2, 4).use(screen => {
        say('-- a str is sent as UTF-8; the bytes taken are counted');
        say(`    taken: ${screen.feed('aä')}`);
        say('-- a place off the screen');
        try { screen.cell(2, 0); }
        catch (error) {
            if (!(error instanceof IndexError)) throw error;
            say(`    IndexError: ${error.message}`);
        }
    });
}

function runScreen() {
    new Screen(5, 20).use(screen => {
        say("-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'");
        screen.feed(Buffer.from('first line\r\nsecond line\r\nthird line'));
        screen.feed(Buffer.from(ESC + '[2;4H' + 'X'));
        shown(screen);
        say('-- erase to the end of that line');
        screen.feed(Buffer.from(ESC + '[K'));
        shown(screen);
        say('-- clear the screen, home, one word');
        screen.feed(Buffer.from(ESC + '[2J' + ESC + '[H' + 'clean'));
        shown(screen);
    });
}

function runAttributes() {
    new Screen(3, 20).use(screen => {
        for (const [name, code] of Object.entries(ATTRIBUTE_SGR_DB))
            screen.feed(`${ESC}[${code}m${name[0]}${ESC}[0m`);
        say('-- one cell per attribute, set by its own code');
        Object.keys(ATTRIBUTE_SGR_DB).forEach((name, column) => {
            const cell = screen.cell(0, column);
            //  'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
            let said = cell.attribute_text() || '(none)';
            if (name === 'conceal') said = 'conceal, or (none) on libvterm 0.1';
            say(`    ${strRepr(cell.text)}  ${said}`);
        });
        say('-- bold, underline and reverse at once; then reset');
        screen.feed(`\r\n${ESC}[1;4;7mA${ESC}[0mB`);
        for (const column of [0, 1]) {
            const cell = screen.cell(1, column);
            say(`    ${strRepr(cell.text)}  ${cell.attribute_text() || '(none)'}`);
        }
        say('-- double underline (SGR 21) is underlined');
        screen.feed(`${ESC}[21mD`);
        say(`    ${strRepr('D')}  ${screen.cell(1, 2).attribute_text()}`);
    });
}

function runColours() {
    new Screen(2, 20).use(screen => {
        screen.feed(`d${ESC}[31mr${ESC}[0m${ESC}[38;5;196mp${ESC}[0m${ESC}[38;2;10;20;30mt${ESC}[0m`);
        screen.feed(`${ESC}[48;2;1;2;3mb${ESC}[0m`);
        ['default', 'indexed 31', 'palette 196', 'direct 10;20;30', 'background 1;2;3'].forEach((what, column) => {
            const cell = screen.cell(0, column);
            //  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: that one
            //  is a colour and mostly red is the claim, not its shade.
            let said;
            if (what === 'indexed 31') {
                const [red, green, blue] = cell.foreground;
                said = `fg mostly red: ${boolText(red > 2 * Math.max(green, blue))}`;
            } else {
                said = `fg ${colourText(cell.foreground)}  bg ${colourText(cell.background)}`;
            }
            say(`    ${what.padEnd(18)} ${strRepr(cell.text)}  ${said}`);
        });
    });
}

//  THE APPLICATION UNDER OBSERVATION -- the Python test's own: it says what
//  it sees, asks the terminal where the cursor is, then names every key
//  until 'q'.
const SEEING_APP = String.raw`
import os, sys, tty, termios
print("streams are terminals: %s %s %s"
      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))
try:    os.close(os.open("/dev/tty", os.O_RDWR)); print("controlling terminal: yes")
except OSError: print("controlling terminal: no")
print("size: %d columns, %d rows" % tuple(os.get_terminal_size()))
print("TERM=%s COLUMNS=%s" % (os.environ.get("TERM"), os.environ.get("COLUMNS")))
old = termios.tcgetattr(0); tty.setraw(0)
sys.stdout.write("\x1b[6;9H\x1b[6n"); sys.stdout.flush()
reply = b""
while not reply.endswith(b"R"): reply += os.read(0, 1)
sys.stdout.write("\r\x1b[7;1Hthe terminal answered: %r" % reply); sys.stdout.flush()
while True:
    key = os.read(0, 32)
    sys.stdout.write("\x1b[9;1H\x1b[Kread: %r" % key); sys.stdout.flush()
    if key == b"q": break
termios.tcsetattr(0, termios.TCSADRAIN, old)
print("\r\nleaving"); sys.exit(3)
`;

//  AN APPLICATION WITH A HEAD, A BODY AND A FOOT -- the Python test's own:
//  'n' counts in the body, 'f' rewrites the foot, 'r' redraws everything
//  unchanged, 'q' leaves.
const DRAWING_APP = String.raw`
import os, sys, tty, termios
old = termios.tcgetattr(0); tty.setraw(0)
count, foot = 0, "q=quit"
def draw():
    out = "\x1b[2J\x1b[1;1H\x1b[7m the head \x1b[0m"
    out += "\x1b[3;1Hcount: %d\x1b[4;1H(press n)" % count
    out += "\x1b[8;1H%s" % foot
    sys.stdout.write(out); sys.stdout.flush()
draw()
while True:
    key = os.read(0, 1)
    if   key == b"n": count += 1
    elif key == b"f": foot = "q=quit  f=pressed"
    elif key == b"q": break
    draw()
termios.tcsetattr(0, termios.TCSADRAIN, old)
`;

function runUnnoticed() {
    process.env.COLUMNS = '300';
    new Terminal(10, 44).use(terminal => {
        say(`-- still running after its first screen: ${boolText(terminal.run([PYTHON, '-c', SEEING_APP]))}`);
        shown(terminal);
        terminal.send('q');
        say(`-- after 'q': exit status ${noneOr(terminal.wait())}`);
        shown(terminal);
    });
}

function runKeys() {
    new Terminal(10, 44).use(terminal => {
        let pressed = '(start)';
        terminal.region('read', 8);
        terminal.on_change((name, lineList) => say(`    ${pressed.padEnd(22)} ${lineList[0]}`));
        terminal.run([PYTHON, '-c', SEEING_APP]);
        for (const [key, modifierList] of [['up', []], ['enter', []], ['tab', []], ['escape', []],
                                           ['f5', []], ['delete', []], ['c', ['ctrl']], ['x', ['alt']],
                                           ['up', ['shift']]]) {
            pressed = [...modifierList, key].join(' ');
            terminal.press(key, modifierList);
        }
        pressed = "send 'ä'";
        terminal.send('ä');
        pressed = "send 'q'";
        terminal.send('q');
        terminal.wait();
    });
}

function runRegions() {
    //  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
    //  ONE report on a loaded machine too.
    new Terminal(8, 30, 0.3).use(terminal => {
        terminal.region('head', 0);
        terminal.region('body', 2, 2);
        terminal.region('foot', -1);
        terminal.on_change((name, lineList) => say(`    changed  ${name.padEnd(5)} ${listRepr(lineList, true)}`));
        for (const [said, act] of [['run',                         () => terminal.run([PYTHON, '-c', DRAWING_APP])],
                                   ["'n'",                         () => terminal.send('n')],
                                   ["'n'",                         () => terminal.send('n')],
                                   ["'r': a redraw, nothing new",  () => terminal.send('r')],
                                   ["'f'",                         () => terminal.send('f')],
                                   ["'nnn', typed at once",        () => terminal.send('nnn')],
                                   ["'q'",                         () => terminal.send('q')]]) {
            say(`-- ${said}`);
            act();
        }
        say(`-- exit status ${noneOr(terminal.wait())}; a region asked by name: ${listRepr(terminal.region_text('body'), true)}`);
        try { terminal.region_text('nosuch'); }
        catch (error) {
            if (!(error instanceof KeyError)) throw error;
            say(`-- no such region: KeyError ${error.message}`);
        }
    });
}

function runEvents() {
    new Terminal(4, 20).use(terminal => {
        terminal.on_event(event => say(`    ${event}`));
        for (const [said, data] of [["'ab'",                         'ab'],
                                    ["a line feed and 'c'",          '\r\nc'],
                                    ['the cursor to row 4, hidden',  ESC + '[4;1H' + ESC + '[?25l'],
                                    ['the alternate screen',         ESC + '[?1049h'],
                                    ['the bell',                     '\x07'],
                                    ['nothing that draws: a reset of attributes', ESC + '[0m']]) {
            say(`-- fed: ${said}`);
            terminal.feed(data);
        }
        say('-- asked where the cursor is, nobody running: the answer waits');
        terminal.feed(ESC + '[2;5H' + ESC + '[6n');
        say(`    answer() = ${bytesRepr(terminal.answer())}`);
        say('-- a key pressed with nobody running');
        terminal.press('f1', [], 0);
        say(`    answer() = ${bytesRepr(terminal.answer())}`);
    });
}

function runMissing() {
    process.env[hwutVterm.LIBRARY_VARIABLE] = '/nowhere/libvterm.so';
    hwutVterm._forget_library();
    try {
        new Screen();
        say('a Screen stands on a library that is not there');
    } catch (error) {
        if (!(error instanceof LibraryMissing)) throw error;
        //  THE SYSTEM'S OWN WORDS for the failed load are left out; what this
        //  module says -- the line, and the way to install -- stands.
        const lineList = error.message.split('\n');
        say(`LibraryMissing: ${lineList[0].split(' -- ')[0]}`);
        for (const line of lineList.slice(1)) say(line);
    }
}

new HwutRunner({
    argv:       process.argv.slice(1),
    title:      "A terminal's screen read by a test: libvterm through koffi.",
    choice_map: {
        text:       probe(runText),
        screen:     probe(runScreen),
        attributes: probe(runAttributes),
        colours:    probe(runColours),
        unnoticed:  probe(runUnnoticed),
        keys:       probe(runKeys),
        regions:    probe(runRegions),
        events:     probe(runEvents),
        missing:    runMissing,
    },
}).run();
