#! /bin/bash
#
# @hwut {
#     title    = "Commit messages: the history keeps the commit-message law"
#     features = ["message-law"]
#     choices {
#         good   { tolerance { constraints = ["broken == 0"] } }
#         broken { tolerance { constraints = ["broken > 0"] } }
#     }
# }
#
# ____________________________________________________________________________
# SUBJECT  the commit-message law per commit of a git repository built from
#          one fixture history (good/broken)
# REQUIREMENT: every commit message of the repository keeps the house law
# (Conventional Commits, the 50/72 rule, a DCO sign-off):
#   H1 'type(scope): subject' with a known type   H2 header <= 50, no '.'
#   B1 a blank second line   B2 body lines <= 72   S1 'Signed-off-by:'
#
# HOW: the artifact is a REPOSITORY. The test application builds a real git
# repository in a scratch directory from the fixture <choice>/commits.txt
# (messages separated by '%%'), with fixed authors and dates, and REPORTS
# its history: 'git log --reverse' with a '@@commit <hash>' line before and
# an '@@end' line after each raw message. It judges nothing.
# 'commit-law.pype' holds the LAW as the parts of a message -- OUTSIDE,
# HEADER, GAP, BODY -- and prints one verdict row per commit, oldest first,
# and every breach. The pype, not this script, prints '<hwut-end>'.
#
# CHOICES
#   good     six commits, every one lawful.
#   broken   six commits, five break the law: a 70-character header; 'Fixed
#            the UART bug.' (no type, final '.', no sign-off); a body glued
#            to its header; a 140-character body line; a missing sign-off.
#
# HWUT CONCEPTS
#   pype         the law over the line stream, as modes; the application
#                provokes and reports only (book ch. 8 -- here the stream is
#                not concurrent, it is a little grammar).
#   analogies    '((hash))'. A hash depends on every byte before it: edit
#                one message, and every later hash changes. Bound as
#                analogies, the diff shows only the message that changed --
#                and each hash must stay consistent between its row and its
#                BREACH lines.
#   constraints  'broken == 0' for good -- the requirement; 'broken > 0' for
#                broken -- the breaches are reported, the BREACH lines say
#                which. The commit count is exact text ('commits: 6').
#
# READING THE GOOD: the XX cells of the table (under H2 and B2 the measured
# length that breaks the rule), then the BREACH lines, then the law.
# ____________________________________________________________________________
HERE=$(cd "$(dirname "$0")" && pwd)
case "$1" in
    good|broken) ;;
    *) echo "choices: good, broken"; exit 1 ;;
esac
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 LC_ALL=C TZ=UTC
export GIT_AUTHOR_NAME="Bench Bot" GIT_AUTHOR_EMAIL="bot@example.com"
export GIT_COMMITTER_NAME="Bench Bot" GIT_COMMITTER_EMAIL="bot@example.com"
git -C "$work" -c init.defaultBranch=main init -q

# one message per '%%'-separated block of the fixture
awk -v dir="$work" 'BEGIN { n = 1 } /^%%$/ { n++; next } { print > (dir "/msg." n) }' \
    "$HERE/../$1/commits.txt"
n=1
while [ -f "$work/msg.$n" ]; do
    echo "change $n" >> "$work/log.txt"
    export GIT_AUTHOR_DATE="2024-05-0${n}T10:00:00+0000" GIT_COMMITTER_DATE="2024-05-0${n}T10:00:00+0000"
    git -C "$work" add log.txt
    git -C "$work" commit -q --cleanup=verbatim -F "$work/msg.$n"
    n=$((n + 1))
done

git -C "$work" log --reverse --format='@@commit %h%n%B%n@@end' | hwut.pype "$HERE/commit-law.pype"
