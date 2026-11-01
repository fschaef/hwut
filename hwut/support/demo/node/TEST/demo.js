#! /usr/bin/env node
//
// @hwut {
//     title   = "Demo: what hwut tolerates, and where it is said"
//     choices {
//         plain       { features = ["demo-passes-on-every-run", "exact-comparison"] }
//         tolerance   { features = ["demo-passes-on-every-run", "equivalence-pattern", "numeric-ratio"]
//                       tolerance {
//                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
//                           numeric_ratio = 0.01
//                       } }
//         constraints { features = ["demo-passes-on-every-run", "constraints"]
//                       tolerance {
//                           constraints = ["load >= 0 and load <= 100",
//                                          "even % 2 == 0",
//                                          "twice == 2 * once"]
//                       } }
//         analogies   { features = ["demo-passes-on-every-run", "analogies"] }
//         race        { features = ["demo-passes-on-every-run", "order-free-block"] }
//         pool        { features = ["demo-passes-on-every-run", "potpourri-subset-duplicates"] }
//         progress    { features = ["demo-passes-on-every-run", "visible-nothing"]
//                       tolerance { nothing = ["[.]+"] } }
//         lisp        { features = ["demo-passes-on-every-run", "analogy-markers"]
//                       tolerance { analogy = ["{", "}"] } }
//         clusters    { features = ["demo-passes-on-every-run", "point-cloud-pair-distance"] }
//     }
// }
//
/*
______________________________________________________________________________
A TEST APPLICATION OF HWUT, FOR READING -- the template for every language.

    hwut.run                   runs every choice below, compares with GOOD/
    hwut.play demo.js plain    runs one choice and records it in OUT/
    hwut.accept demo.js plain  blesses that recording as GOOD; it runs
                               nothing. Where a GOOD stands, the change
                               is 'hwut.merge's -- or '--force' (also
                               '--as-is') replaces it whole.
    hwut.merge                 shows OUTPUT against GOOD, key by key
    hwut.config.show demo.js   prints what hwut READ from the header above

The header above is the whole configuration: a title, and one scope per
choice. hwut calls 'node demo.js <choice>' and compares what it prints on
stdout with 'GOOD/demo.js--<choice>.txt' -- a '.link' to the Python demo's
GOOD: the same choice prints the same text in either language.
'<hwut-end>' closes the stream: a stream without it never COMPLETED and is
not accepted.

Every run is seeded by the clock ('Math.random'), so the output differs
from run to run -- and every choice passes anyway. Each shows WHY:

plain        nothing varies; nothing is tolerated. The output must equal
             GOOD, line by line.

tolerance    'eq_pattern': a greeting drawn at random; any greeting the
             pattern names is EQUIVALENT to any other.
             'numeric_ratio': a value drawn from [19.91, 20.09]. The band
             belongs to the GOOD's number, |n| x ratio: GOOD 19.91 against
             20.09 differs by 0.18, inside 19.91 x 0.01 = 0.1991. Every pair
             from the interval passes; 20.30 would not.

constraints  '((name: value))' BINDS a value; the expressions under
             'constraints' judge it, not the GOOD's value. 'load' may be
             anything from 0 to 100; 'even' any even number; 'twice' must be
             twice 'once', whatever 'once' is. A law over two variables is
             checked once both are bound. A binding that breaks its law is
             red.

race         '##! potpourri' ... '####' opens a block whose lines may arrive
             in ANY order -- three workers print as they finish. The same
             lines must stand on both sides, each once; the order is free.
             The program prints the markers, and so does GOOD. (node's
             workers are coroutines on one event loop, each waking after a
             drawn delay: the order is the timers', as Python's is the
             scheduler's.)

analogies    '((x))' is a placeholder: '((a7f3))' against GOOD's '((91c2))'
             is equivalent where the mapping holds throughout the stream --
             the same handle opened, read and closed. A handle that changes
             in mid-stream is red.

pool         '##! potpourri subset duplicates': four workers share twelve
             jobs; who takes how many is the timers'. 'subset': a worker
             that got no job is no fault -- every line of the run must
             stand in GOOD, not every line of GOOD in the run.
             'duplicates': a worker named twice is one line. The GOOD was
             recorded from a run in which all four worked.

progress     'nothing': a line made only of what the pattern names counts
             as no line. A download prints dots while it waits -- none, or
             a few lines of them -- and the dots are no fact.

lisp         'analogy = ["{", "}"]': the output is Lisp, where '((' is
             syntax, so the placeholder is marked otherwise. An object is
             printed with its address, '{10044C1F33}'; the address differs
             per run, and must be the same object throughout.

clusters     '##! point-cloud limit=0.3 pair dist=Linf': three centroids of
             a clustering, in whatever order the run finds them. 'pair':
             each centroid pairs with ONE point of GOOD -- two centroids in
             one cluster are red. 'dist=Linf': within 0.3 in x AND in y.
______________________________________________________________________________
*/
'use strict';

const GREETING_LIST = ['hello', 'bonjour', 'hallo', 'buongiorno', 'hola', 'ahoj'];
const say = text => console.log(text);

/* RETURN: number, a float drawn evenly from [low, high]. */
const uniform = (low, high) => low + (high - low) * Math.random();
/* RETURN: number, an integer drawn evenly from [low, high], both included. */
const randint = (low, high) => low + Math.floor(Math.random() * (high - low + 1));
/* RETURN: any, one element of 'list', drawn evenly. */
const choice  = list => list[Math.floor(Math.random() * list.length)];
/* RETURN: Promise, resolved after 'seconds'. */
const sleep   = seconds => new Promise(resolve => setTimeout(resolve, seconds * 1000));
/* RETURN: string, 'x' with 'digits' decimals, right-aligned in 'width'
 *         columns -- Python's '%<width>.<digits>f'. */
const fixed   = (x, digits, width = 0) => x.toFixed(digits).padStart(width);

/* RETURN: number, a float drawn from the normal distribution of 'mu' and
 *         'sigma' (Box-Muller). */
function gauss(mu, sigma) {
    const u = 1.0 - Math.random(), v = Math.random();
    return mu + sigma * Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

/* RETURN: array of two integers, distinct, drawn evenly from [low, high). */
function sampleTwo(low, high) {
    const first = randint(low, high - 1);
    let second;
    do { second = randint(low, high - 1); } while (second === first);
    return [first, second];
}

/* RETURN: undefined. Prints what never varies. */
function plain() {
    say('the first line');
    say('the second line: 1 2 3');
}

/* RETURN: undefined. Prints a greeting and a value, both drawn at random. */
function tolerance() {
    say(`greeting: ${choice(GREETING_LIST)}, world`);
    say(`value:    ${fixed(uniform(19.91, 20.09), 2)}`);
}

/* RETURN: undefined. Prints bindings, each drawn at random, each lawful. */
function constraints() {
    say(`load  ((load: ${fixed(uniform(0.0, 100.0), 1)})) %`);
    say(`even  ((even: ${2 * randint(0, 500)}))`);
    const once = randint(1, 50);
    say(`once  ((once: ${once}))`);
    say(`twice ((twice: ${2 * once}))`);
}

/* RETURN: undefined. Prints two handles, each drawn at random, each used
 *         consistently from opening to closing. */
function analogies() {
    const [first, second] = sampleTwo(0x1000, 0x10000).map(n => n.toString(16).padStart(4, '0'));
    say(`open  ((${first})) input.txt`);
    say(`open  ((${second})) output.txt`);
    say(`read  ((${first})) 17 lines`);
    say(`write ((${second})) 17 lines`);
    say(`close ((${first}))`);
    say(`close ((${second}))`);
}

/* RETURN: Promise of undefined, resolved once three workers have printed as
 *         they finished; the order is the timers', the facts are not. The
 *         program frames the unordered block itself: '##! potpourri' ...
 *         '####'. */
async function race() {
    const work = async (name, jobs) => {
        await sleep(uniform(0.0, 0.02));
        say(`worker ${name} done: ${jobs} jobs`);
    };
    say('start');
    say('##! potpourri');
    await Promise.all([['A', 3], ['B', 5], ['C', 2]].map(([name, jobs]) => work(name, jobs)));
    say('####');
    say('all joined');
}

/* RETURN: Promise of undefined, resolved once four workers have taken
 *         twelve jobs from one queue, each reporting the job it finished.
 *         Who takes how many is the timers'. */
async function pool() {
    const jobQueue = Array.from({ length: 12 }, (_, i) => i);
    const doneList = [];
    const work = async name => {
        while (jobQueue.length) {
            jobQueue.shift();
            await sleep(uniform(0.0, 0.005));
            doneList.push(`job done by worker ${name}`);
        }
    };
    await Promise.all([...'ABCD'].map(work));
    say('twelve jobs, four workers:');
    say('##! potpourri subset duplicates');
    for (const line of doneList) say(line);
    say('####');
    say(`jobs done: ${doneList.length}`);
}

/* RETURN: undefined. A download that prints dots while it waits; how many
 *         is the network's. */
function progress() {
    say('connecting to mirror');
    for (let n = randint(0, 3); n > 0; n -= 1) say('.'.repeat(randint(1, 8)));
    say('connected');
    say('received 1024 bytes');
}

/* RETURN: undefined. A Lisp session at its prompt: two objects, each printed
 *         with its address '{...}', drawn anew per run, and each used again. */
function lisp() {
    const [table, thread] = sampleTwo(0x1000000000, 0x1100000000).map(n => n.toString(16).toUpperCase());
    say('* (defvar *cache* (make-hash-table))');
    say(`#<HASH-TABLE :TEST EQL :COUNT 0 {${table}}>`);
    say('* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name "worker"))');
    say(`#<THREAD "worker" RUNNING {${thread}}>`);
    say('* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))');
    say(`#<THREAD "worker" RUNNING {${thread}}>`);
    say('* *cache*');
    say(`#<HASH-TABLE :TEST EQL :COUNT 1 {${table}}>`);
}

/* RETURN: undefined. Clusters 90 noisy points around three centres and
 *         prints the centroids in the order the run found them. */
function clusters() {
    const centreList = [[1.0, 1.0], [5.0, 4.0], [9.0, 1.0]];
    const pointList  = [];
    for (const [x, y] of centreList)
        for (let i = 0; i < 30; i += 1) pointList.push([x + gauss(0.0, 0.3), y + gauss(0.0, 0.3)]);
    for (let i = pointList.length - 1; i > 0; i -= 1) {           // shuffled
        const j = Math.floor(Math.random() * (i + 1));
        [pointList[i], pointList[j]] = [pointList[j], pointList[i]];
    }
    const d2 = (p, c) => (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2;
    //  The start: one point at random, then twice the point farthest from
    //  every start chosen so far -- one start per cluster.
    let centroidList = [choice(pointList)];
    while (centroidList.length < 3) {
        const far = p => Math.min(...centroidList.map(c => d2(p, c)));
        centroidList.push(pointList.reduce((best, p) => far(p) > far(best) ? p : best));
    }
    for (let round = 0; round < 10; round += 1) {
        const memberList = [[], [], []];
        for (const p of pointList) {
            let nearest = 0;
            for (let i = 1; i < 3; i += 1) if (d2(p, centroidList[i]) < d2(p, centroidList[nearest])) nearest = i;
            memberList[nearest].push(p);
        }
        centroidList = memberList.map(m => [m.reduce((s, p) => s + p[0], 0) / m.length,
                                            m.reduce((s, p) => s + p[1], 0) / m.length]);
    }
    say('centroids (x y), in the order found:');
    say('##! point-cloud limit=0.3 pair dist=Linf');
    for (const [x, y] of centroidList) say(`    ${fixed(x, 2, 5)} ${fixed(y, 2, 5)}`);
    say('####');
}

const CHOICE_DB = { plain, tolerance, constraints, analogies, race, pool, progress, lisp, clusters };

/* RETURN: Promise of undefined; the choice named on the command line run
 *         and '<hwut-end>' printed after it -- exit status 1 and the
 *         choices named, where it names none of them. */
async function main() {
    const word = process.argv[2] || '';
    if (!Object.prototype.hasOwnProperty.call(CHOICE_DB, word)) {
        say(`choices: ${Object.keys(CHOICE_DB).join(', ')}`);
        process.exit(1);
    }
    await CHOICE_DB[word]();
    say('<hwut-end>');
}

main();
