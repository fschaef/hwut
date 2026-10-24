#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "book and tree disagree: every page says it alike"
#     features = ["book-discrepancy-said-alike"]
#     choices  = ["run", "run_fail", "report", "report_fail", "machine"]
# }
#
# ---------------------------------------------------------------------------
#
# A TEST deleted and a CHOICE taken out, both still in the book: what
# 'hwut.run' and 'hwut.report' say of them, called INSIDE the TEST
# directory (ruled 2026-10-19, the book's reviewers' "report and hwut.run
# output differ"):
#
#   - the directory is named from the tree's root ('TEST'), on every page;
#   - the cases stand in one order, by test, then choice: 'test-a.sh y'
#     before 'test-b.sh', with and without '--fail', flow and HINTS;
#   - '--fail' selects them: no 'the selection is empty' NOTE;
#   - the report's heading keeps the directory's date under '--fail';
#   - JSON, JUnit and TAP give the page's word ('no-app', 'no-choice'),
#     the HINTS category and its phrase -- one table, no second spelling.
#
# MEASURED 2026-10-19 before: 'run --fail' said the selection was empty;
# 'report --fail' put 'test-b.sh' first and dated '<no date>'; the report
# named '.'; the machine formats said 'test-vanished'.
#
# THE DATE AND THE TIMES ARE THE MACHINE'S: shown as '<date>', '<t>'.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/hwut/bin"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "book and tree disagree: every page says it alike;"
        echo "CHOICES: run, run_fail, report, report_fail, machine;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/TEST"
cd "$WORK"
printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n}\n' \
       > hwut-root.conf
for t in a b; do
    printf '#! /bin/bash\n# @hwut { title = "%s" choices = ["x", "y"] }\necho "$1"; echo "<hwut-end>"\n' \
           $t > TEST/test-$t.sh
done
chmod +x TEST/*.sh
cd TEST
"$BIN/hwut.play" --all --plain > /dev/null 2>&1; "$BIN/hwut.accept" --whole > /dev/null 2>&1
"$BIN/hwut.run" > /dev/null 2>&1
rm test-b.sh
sed -i 's/"x", "y"/"x"/' test-a.sh

shown() {
    sed -E "s/[0-9]{4}y[0-9]{2}m[0-9]{2}d [0-9]{2}h[0-9]{2}/<date>/; \
            s/\"when\": \"[^\"]*\"/\"when\": \"<date>\"/; \
            s/[0-9]+\.[0-9]+ \[sec\]/<t> [sec]/g; s/, [0-9:]+$/, <t>/"
}
case "$1" in
    run)         "$BIN/hwut.run" --no-colour 2>&1 | shown ;;
    run_fail)    "$BIN/hwut.run" --fail --no-colour 2>&1 | shown ;;
    report)      "$BIN/hwut.report" --plain 2>&1 | shown ;;
    report_fail) "$BIN/hwut.report" --fail --plain 2>&1 | shown ;;
    machine)
        for format in json junit tap; do
            echo "== --format=$format"
            "$BIN/hwut.report" --format=$format 2>&1 | shown
        done ;;
esac
echo "<hwut-end>"
