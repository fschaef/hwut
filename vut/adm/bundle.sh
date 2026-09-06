#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# bundle.sh -- pack a source tree into a unified diff against /dev/null.
#
# Comment convention: every function comment opens with the RETURN block.
# Bash has no docstrings, so '#' replaces the Python '"""' boundary; the
# RETURN-first form is unchanged.
# ---------------------------------------------------------------------------
set -euo pipefail

# --- Configuration & State -------------------------------------------------
SELECT_MODE="git"             # git | find | since | list
SINCE_REF=""
LIST_FILE=""
DEPS=0
DIRS=()
EXTENSIONS=()
EXTRA_FILES=()
EXCLUDE_PATTERNS=(.git TMP __pycache__ .ruff_cache OUT
                  .mypy_cache .pytest_cache '*.egg-info' .venv node_modules)
EXCLUDE_GIVEN=0
EXCLUDE_PATH_GLOBS=()
EXCLUDE_NAME_GLOBS=()
OUTPUT_FILE=""
MAX_FILE_BYTES=262144         # 0 disables
MAX_PART_BYTES=0              # 0 disables splitting
BINARY_MODE="skip"            # skip | git
COMPLETE=0
CHMOD_SCRIPT=0
# Pruned even under --complete: a bundled .git would be enormous and could not
# be re-applied into a repository anyway. Name it in an explicit -x to include.
HARD_PRUNE=(.git)
DRY_RUN=0
TOP_N=10
VERIFY_FILES=()
PROFILE=""
PROFILE_FILE=".bundlerc"

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Selection:
  -d DIR1 [DIR2 ...]   Directories to search (space-separated)
  -e EXT1 [EXT2 ...]   Extensions to include; none given means every file
  -f FILE1 [FILE2 ...] Extra static files to append
      --use-find       Select with find(1) instead of 'git ls-files'; needed
                       outside a git working tree and for untracked trees
  -g, --git            Select from 'git ls-files' (the default; accepted for
                       symmetry with --use-find)
      --since REF      Select only files changed since REF (implies --git)
      --from-list FILE Bundle exactly the paths listed in FILE (one per line)
      --deps           Add every Python module the selection IMPORTS, and
                       what those import, transitively. Bundling one
                       directory otherwise bundles a package that will not
                       import. The closure is 'adm/dependency.py', which
                       reads the tree with 'adm/import_graph.py' -- one
                       analysis, one place.

Exclusion:
  -x NAME1 [NAME2 ...] Directory names to prune, with everything below. Matched
                       against a path component only, never the whole path;
                       globs allowed ('*.egg-info'). First -x replaces the
                       default, further -x accumulate.
                       (Default: ${EXCLUDE_PATTERNS[*]})
  -X GLOB1 [GLOB2 ...] Exclude by whole path glob ('vut/*/TEST/GOOD/*')
      --exclude GLOB1 [GLOB2 ...]
                       Exclude by BASE NAME glob ('*.log', 'ON-HOLD-*').
                       Matched against the file's own name only, never a
                       directory and never the path -- so '--exclude *.txt'
                       drops every .txt wherever it stands, and leaves the
                       directories holding them alone.
  -S BYTES             Skip files larger than BYTES; 0 disables (Default: ${MAX_FILE_BYTES})
  -a, --complete       Complete dump: no pruning, no size cap, binary members
                       included, untracked files included. '.git' stays pruned.
      --binary         Render binary files as git literal patches instead of
                       skipping them (implied by --complete)

Modes:
      --chmod-script   Write '<output>.chmod.sh' beside the bundle: one
                       'chmod a+x' per executable member. A PATCH CARRIES NO
                       MODE, so every executable arrives as a plain file and
                       the receiving tree cannot run its own tests until this
                       script is run. Implied by --complete.

Output:
  -o FILE              Output filename, '-' for stdout
                       (Default: dump-<first-dir-name>.txt)
      --max-bytes N    Split output into parts of at most N bytes each
  -p NAME              Load argument vector NAME from ${PROFILE_FILE}
  -n, --dry-run        Report what would be bundled; write nothing
  -N NUM               Largest files to list in dry-run (Default: ${TOP_N})
      --verify FILE... Recompute FILE's content crc64, and re-hash its
                       manifest against the working tree
  -h, --help           Show this help message

Within a follower list, '--' takes the next token literally.
EOF
}

die() { echo "Error: $*" >&2; exit 1; }

# --- Parsing Subsystem -----------------------------------------------------
SHIFT_COUNT=0

# RETURN: nothing, the collected followers are appended to the named array
#         and SHIFT_COUNT is set to the number of tokens consumed.
#
# Collection stops at the first token beginning with '-'. A token that is
# exactly '--' is dropped and the token after it is taken literally, which is
# how a value beginning with '-' is passed.
command_line_get_nominus_followers() {
    local -n target_array=$1
    local n=1
    shift 2
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--" ]]; then
            [[ $# -gt 1 ]] || die "'--' at end of argument list"
            target_array+=("$2"); shift 2; n=$((n + 2)); continue
        fi
        [[ "$1" =~ ^- ]] && break
        target_array+=("$1"); shift; n=$((n + 1))
    done
    SHIFT_COUNT=$n
}

# RETURN: nothing, the named variable holds the single follower value and
#         SHIFT_COUNT is set to 2.
command_line_get_follower() {
    local -n target_var=$1
    [[ $# -ge 3 ]] || die "$2 requires an argument"
    target_var="$3"
    SHIFT_COUNT=2
}

# RETURN: nothing, all global option variables are set from the argument list.
#
# Exits with status 1 on an unknown option.
command_line_parse() {
    while [[ $# -gt 0 ]]; do
        local arg="$1"
        case "$arg" in
            -d) command_line_get_nominus_followers DIRS "$@"; shift "$SHIFT_COUNT" ;;
            -e) command_line_get_nominus_followers EXTENSIONS "$@"; shift "$SHIFT_COUNT" ;;
            -f) command_line_get_nominus_followers EXTRA_FILES "$@"; shift "$SHIFT_COUNT" ;;
            -x) [[ $EXCLUDE_GIVEN -eq 0 ]] && EXCLUDE_PATTERNS=() && EXCLUDE_GIVEN=1
                command_line_get_nominus_followers EXCLUDE_PATTERNS "$@"; shift "$SHIFT_COUNT" ;;
            -X) command_line_get_nominus_followers EXCLUDE_PATH_GLOBS "$@"; shift "$SHIFT_COUNT" ;;
            --exclude) command_line_get_nominus_followers EXCLUDE_NAME_GLOBS "$@"; shift "$SHIFT_COUNT" ;;
            --verify) command_line_get_nominus_followers VERIFY_FILES "$@"; shift "$SHIFT_COUNT" ;;
            -o) command_line_get_follower OUTPUT_FILE "$@"; shift "$SHIFT_COUNT" ;;
            -N) command_line_get_follower TOP_N "$@"; shift "$SHIFT_COUNT" ;;
            -S) command_line_get_follower MAX_FILE_BYTES "$@"; shift "$SHIFT_COUNT" ;;
            -p) command_line_get_follower PROFILE "$@"; shift "$SHIFT_COUNT" ;;
            --max-bytes) command_line_get_follower MAX_PART_BYTES "$@"; shift "$SHIFT_COUNT" ;;
            --since) command_line_get_follower SINCE_REF "$@"; shift "$SHIFT_COUNT"
                     SELECT_MODE="since" ;;
            --from-list) command_line_get_follower LIST_FILE "$@"; shift "$SHIFT_COUNT"
                         SELECT_MODE="list" ;;
            -g|--git) SELECT_MODE="git"; shift ;;
            --use-find) SELECT_MODE="find"; shift ;;
            --deps) DEPS=1; shift ;;
            --binary) BINARY_MODE="git"; shift ;;
            --chmod-script) CHMOD_SCRIPT=1; shift ;;
            -a|--complete) COMPLETE=1; BINARY_MODE="git"; MAX_FILE_BYTES=0
                           EXCLUDE_PATTERNS=(); EXCLUDE_GIVEN=1
                           EXCLUDE_PATH_GLOBS=(); EXTENSIONS=()
                           CHMOD_SCRIPT=1; shift ;;
            -n|--dry-run) DRY_RUN=1; shift ;;
            -h|--help) print_usage; exit 0 ;;
            *) echo "Error: Unknown option '$arg'" >&2; print_usage >&2; exit 1 ;;
        esac
    done
}

# RETURN: the argument vector recorded for PROFILE, one token per output line,
#         read from the first ${PROFILE_FILE} found from CWD upwards.
#
# Exits with status 1 if no such file or no such profile exists. A profile is
# a line of the form 'name: -d vut/engine -e py txt'.
profile_arguments() {
    local name="$1" dir line
    dir=$(pwd)
    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/$PROFILE_FILE" ]]; then
            line=$(sed -n "s/^[[:space:]]*${name}[[:space:]]*:[[:space:]]*//p" \
                   "$dir/$PROFILE_FILE" | head -n1)
            [[ -n "$line" ]] || die "profile '$name' not found in $dir/$PROFILE_FILE"
            printf '%s\n' $line
            return 0
        fi
        dir=$(dirname "$dir")
    done
    die "no $PROFILE_FILE found from $(pwd) upwards"
}

# RETURN: nothing, OUTPUT_FILE holds a name derived from the first search
#         directory when -o was not given.
output_file_determine() {
    [[ -n "$OUTPUT_FILE" ]] && return 0
    local dir_name="files"
    [[ ${#DIRS[@]} -gt 0 ]] && dir_name=$(basename "$(realpath -m "${DIRS[0]}")")
    OUTPUT_FILE="dump-${dir_name}.txt"
}

# --- Path Handling ---------------------------------------------------------
# RETURN: the argument with any './' prefix and duplicate slashes removed.
#
# Exits with status 1 on an absolute path: a bundle member must be relative to
# the tree root, or the emitted 'a/<path>' header is unapplicable.
path_normalise() {
    local p="$1"
    [[ "$p" == /* ]] && die "absolute path in bundle: '$p' (run from the tree root)"
    p="${p#./}"
    printf '%s' "${p//\/\//\/}"
}

# RETURN: 0, if any component of the path matches an exclude pattern
#         1, else
path_is_pruned() {
    local path="$1" comp pat
    local IFS=/
    for comp in $path; do
        for pat in "${HARD_PRUNE[@]}" ${EXCLUDE_PATTERNS[@]+"${EXCLUDE_PATTERNS[@]}"}; do
            [[ "$comp" == $pat ]] && return 0
        done
    done
    return 1
}

# RETURN: 0, if the whole path matches an exclude glob given with -X
#         1, else
path_is_glob_excluded() {
    local path="$1" glob
    for glob in ${EXCLUDE_PATH_GLOBS[@]+"${EXCLUDE_PATH_GLOBS[@]}"}; do
        [[ "$path" == $glob ]] && return 0
    done
    return 1
}

# RETURN: 0, if the file's OWN NAME matches an exclude glob given with
#            --exclude
#         1, else
#
# The base name only: '--exclude *.log' drops 'a/b/run.log' and leaves the
# directory 'a/log/' alone. That is the difference from -x, which matches any
# path component, and from -X, which matches the whole path.
path_is_name_excluded() {
    local path="$1" glob base
    base="${path##*/}"
    for glob in ${EXCLUDE_NAME_GLOBS[@]+"${EXCLUDE_NAME_GLOBS[@]}"}; do
        [[ "$base" == $glob ]] && return 0
    done
    return 1
}

# RETURN: 0, if the path ends in one of the wanted extensions or none was given
#         1, else
path_has_wanted_extension() {
    [[ ${#EXTENSIONS[@]} -eq 0 ]] && return 0
    local path="$1" ext
    for ext in "${EXTENSIONS[@]}"; do
        [[ "$path" == *."$ext" ]] && return 0
    done
    return 1
}

# --- Selection -------------------------------------------------------------
# RETURN: NUL-separated candidate paths as produced by find(1) under DIRS.
select_find() {
    [[ ${#DIRS[@]} -gt 0 ]] || return 0
    local name_args=() prune_args=() i all=("${HARD_PRUNE[@]}")
    all+=(${EXCLUDE_PATTERNS[@]+"${EXCLUDE_PATTERNS[@]}"})
    if [[ ${#EXTENSIONS[@]} -eq 0 ]]; then name_args=("-name" "*")
    else
        for i in "${!EXTENSIONS[@]}"; do
            [[ "$i" -gt 0 ]] && name_args+=("-o")
            name_args+=("-name" "*.${EXTENSIONS[$i]}")
        done
    fi
    prune_args=("-type" "d" "(")
    for i in "${!all[@]}"; do
        [[ "$i" -gt 0 ]] && prune_args+=("-o")
        prune_args+=("-name" "${all[$i]}")
    done
    prune_args+=(")")
    find "${DIRS[@]}" \( "${prune_args[@]}" \) -prune \
         -o -type f \( "${name_args[@]}" \) -print0
}

# RETURN: NUL-separated candidate paths tracked by git under DIRS.
#
# Exits with status 1 outside a git working tree.
select_git() {
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
        || die "git selection needs a git working tree; use --use-find outside one"
    if [[ $COMPLETE -eq 1 ]]; then
        # Everything on disk, ignored files included: 'complete' means complete.
        { git ls-files -z -- ${DIRS[@]+"${DIRS[@]}"}
          git ls-files -z --others -- ${DIRS[@]+"${DIRS[@]}"}; } | LC_ALL=C sort -zu
    else
        git ls-files -z -- ${DIRS[@]+"${DIRS[@]}"}
    fi
}

# RETURN: NUL-separated candidate paths changed since SINCE_REF and still
#         present in the working tree.
#
# Exits with status 1 outside a git working tree or on an unknown reference.
select_since() {
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
        || die "--since needs a git working tree"
    git rev-parse --verify --quiet "$SINCE_REF" >/dev/null \
        || die "unknown reference '$SINCE_REF'"
    { git diff --name-only -z "$SINCE_REF" -- ${DIRS[@]+"${DIRS[@]}"}
      git ls-files -z --others --exclude-standard -- ${DIRS[@]+"${DIRS[@]}"}; } \
    | LC_ALL=C sort -zu
}

# RETURN: NUL-separated candidate paths read from LIST_FILE, blank lines and
#         '#' comment lines dropped.
select_list() {
    [[ -f "$LIST_FILE" ]] || die "list file '$LIST_FILE' not found"
    grep -v -e '^[[:space:]]*$' -e '^[[:space:]]*#' "$LIST_FILE" | tr '\n' '\0'
}

# --- Filtering -------------------------------------------------------------
# Filter verdicts, filled by candidates_filter.
ACCEPTED=()
REJ_PRUNED=()
REJ_GLOB=()
REJ_NAME=()
REJ_LARGE=()
REJ_BINARY=()
REJ_MISSING=()

# Per-path caches, filled once and read by both candidates_filter and
# member_render so a file is 'grep -Iq'-tested or 'stat'-sized once, not
# twice.
declare -A TEXT_CACHE=()
declare -A SIZE_CACHE=()

# RETURN: 0, if the file holds no NUL byte or is empty
#         1, else
#
# The verdict is cached in TEXT_CACHE keyed by path: the expensive part is
# the 'grep' fork, and this function is called once per accepted file from
# candidates_filter and again from member_render.
file_is_text() {
    local path="$1"
    if [[ ! -v TEXT_CACHE[$path] ]]; then
        if [[ -s "$path" ]]; then
            grep -Iq . "$path" && TEXT_CACHE[$path]=0 || TEXT_CACHE[$path]=1
        else
            TEXT_CACHE[$path]=0
        fi
    fi
    return "${TEXT_CACHE[$path]}"
}

# RETURN: nothing, SIZE_CACHE holds the byte size of every (normalised) path
#         reachable from the named array, gathered in chunked 'stat' calls
#         instead of one fork per file. A path that does not exist is simply
#         left unset -- callers already reject those before touching size.
sizes_prefetch() {
    local -n paths_ref=$1
    local -a norm=()
    local p size name n i step=500
    for p in ${paths_ref[@]+"${paths_ref[@]}"}; do
        norm+=("$(path_normalise "$p")")
    done
    n=${#norm[@]}
    i=0
    while [[ $i -lt $n ]]; do
        while read -r size name; do
            SIZE_CACHE["$name"]="$size"
        done < <(stat -c '%s %n' -- "${norm[@]:i:step}" 2>/dev/null)
        i=$((i + step))
    done
}

# RETURN: nothing, ACCEPTED and the REJ_* arrays hold the normalised candidate
#         paths sorted into one bucket each.
#
# Reads NUL-separated paths from standard input. Duplicates are dropped, so
# the same file named by -f and by the search never appears twice.
candidates_filter() {
    local path size
    local -A seen=()
    while IFS= read -r -d '' path; do
        path=$(path_normalise "$path")
        [[ -n "$path" ]] || continue
        [[ -n "${seen[$path]:-}" ]] && continue
        seen["$path"]=1
        if   path_is_pruned "$path";         then REJ_PRUNED+=("$path")
        elif path_is_glob_excluded "$path";  then REJ_GLOB+=("$path")
        elif path_is_name_excluded "$path";  then REJ_NAME+=("$path")
        elif ! path_has_wanted_extension "$path"; then :
        elif [[ ! -f "$path" ]];             then REJ_MISSING+=("$path")
        elif ! file_is_text "$path" && [[ "$BINARY_MODE" == "skip" ]]
                                             then REJ_BINARY+=("$path")
        else
            size="${SIZE_CACHE[$path]:-}"
            [[ -n "$size" ]] || size=$(stat -c%s "$path")
            if [[ "$MAX_FILE_BYTES" -gt 0 && "$size" -gt "$MAX_FILE_BYTES" ]]; then
                REJ_LARGE+=("$path")
            else
                ACCEPTED+=("$path")
            fi
        fi
    done
}

# RETURN: nothing, ACCEPTED and the REJ_* arrays are filled from the selection
#         mode in force, with EXTRA_FILES appended to the candidate stream.
candidates_collect() {
    local stream; stream=$(mktemp)
    { case "$SELECT_MODE" in
        find)  select_find ;;
        git)   select_git ;;
        since) select_since ;;
        list)  select_list ;;
      esac
      local file
      for file in ${EXTRA_FILES[@]+"${EXTRA_FILES[@]}"}; do
          printf '%s\0' "$file"
      done
    } | LC_ALL=C sort -z > "$stream"

    # --deps: every module the selection imports, transitively. Added to
    # the candidate stream, so the filters judge them as they judge the
    # rest -- a dependency is not exempt from --exclude or the size cap.
    if (( DEPS )); then
        local seeds deps
        seeds=$(mktemp); deps=$(mktemp)
        tr '\0' '\n' < "$stream" | grep -e '\.py$' > "$seeds" || true
        if [[ -s "$seeds" ]]; then
            if ! xargs -a "$seeds" python3 "$(dirname "$0")/dependency.py" \
                 > "$deps"; then
                echo "Warning: --deps: some modules could not be read;" \
                     "see the FAULT lines above" >&2
            fi
            { cat "$stream"; tr '\n' '\0' < "$deps"; } \
                | LC_ALL=C sort -zu > "$stream.deps"
            mv "$stream.deps" "$stream"
        fi
        rm -f "$seeds" "$deps"
    fi
    local all_paths=() p
    while IFS= read -r -d '' p; do all_paths+=("$p"); done < "$stream"
    sizes_prefetch all_paths
    # No pipe into candidates_filter: a pipeline stage is a subshell and its
    # verdict arrays would be discarded at its exit.
    candidates_filter < "$stream"
    rm -f "$stream"
}

# --- Content Signature -----------------------------------------------------
# RETURN: 16 upper-case hex digits, the CRC-64/XZ of the bytes read from
#         standard input (ECMA-182 polynomial 0xC96C5795D7870F42, reflected,
#         initial and final value all-ones -- the 'xz' checksum, so
#         'xz --check=crc64' and any CRC-64/XZ implementation answer the same
#         number for the same bytes).
#
# Exits with status 1 where python3 is absent: this tree is a Python project,
# and a signature computed by two different means is two signatures.
crc64_stdin() {
    command -v python3 >/dev/null 2>&1 \
        || die "crc64 needs python3; no interpreter found"
    local out
    out=$(python3 -c '
import sys

POLYNOMIAL = 0xC96C5795D7870F42

# T0 is the ordinary single-byte table. T[i] is T0 applied (i+1) times to a
# byte at shift position i with every further input byte zero, which is what
# lets 8 input bytes be folded in per outer-loop iteration instead of 1 --
# same reflected-CRC arithmetic, 8x fewer Python-level loop iterations.
T0 = []
for index in range(256):
    entry = index
    for _ in range(8):
        entry = (entry >> 1) ^ POLYNOMIAL if entry & 1 else entry >> 1
    T0.append(entry)

TABLES = [T0]
for _ in range(7):
    prev = TABLES[-1]
    TABLES.append([T0[prev[b] & 0xFF] ^ (prev[b] >> 8) for b in range(256)])
T0, T1, T2, T3, T4, T5, T6, T7 = TABLES

def crc64_byte_at_a_time(data, crc):
    for byte in data:
        crc = T0[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc

def crc64_slice_by_8(data, crc):
    n = len(data)
    limit = n - (n % 8)
    i = 0
    while i < limit:
        crc ^= int.from_bytes(data[i:i + 8], "little")
        crc = (T7[crc & 0xFF] ^ T6[(crc >> 8) & 0xFF] ^ T5[(crc >> 16) & 0xFF] ^
               T4[(crc >> 24) & 0xFF] ^ T3[(crc >> 32) & 0xFF] ^
               T2[(crc >> 40) & 0xFF] ^ T1[(crc >> 48) & 0xFF] ^
               T0[(crc >> 56) & 0xFF])
        i += 8
    return crc64_byte_at_a_time(data[i:], crc)

# Self-test once per invocation (a few hundred bytes, negligible cost): the
# sliced path must agree with the reference byte-at-a-time path. A CRC used
# to detect a truncated or corrupted bundle must not itself be silently wrong.
_probe = bytes(range(256)) * 3
assert crc64_slice_by_8(_probe, 0xFFFFFFFFFFFFFFFF) == \
       crc64_byte_at_a_time(_probe, 0xFFFFFFFFFFFFFFFF), \
       "crc64 slicing-by-8 table disagrees with the reference implementation"

crc = 0xFFFFFFFFFFFFFFFF
while True:
    block = sys.stdin.buffer.read(1 << 20)
    if not block: break
    crc = crc64_slice_by_8(block, crc)
sys.stdout.write("%016X" % (crc ^ 0xFFFFFFFFFFFFFFFF))
') || die "crc64 computation failed"
    printf '%s' "$out"
}

# RETURN: 16 upper-case hex digits, the CRC-64/XZ of the CONTENT of the given
#         bundle -- everything from its first 'diff --git' line to its end,
#         the introductory comment and the manifest excluded.
#
# THE COMMENT CANNOT BE PART OF WHAT IT REPORTS. The signature stands in the
# header, so a signature over the whole file could never be recomputed from
# the file. What it covers is exactly what 'git apply' and 'patch' read: the
# diff. A member's own line may begin with '#', but only as '+#', so the
# first line at column zero beginning 'diff --git ' is the content's start
# and cannot be forged by a member's text.
bundle_content_crc64() {
    sed -n '/^diff --git /,$p' "$1" | crc64_stdin
}

# --- Member Rendering ------------------------------------------------------
# RETURN: 0, if the file is non-empty and its last byte is not a newline
#         1, else
#
# Command substitution strips trailing newlines, so byte counts are compared
# instead of tail output.
file_lacks_final_newline() {
    local file="$1"
    [[ -s "$file" ]] || return 1
    # One 'tail' fork instead of tail|od|tr: the trailing 'x' after tail's
    # own output survives $()'s trailing-newline stripping, so a final '\n'
    # in the file is still visible in the captured string.
    [[ "$(tail -c1 -- "$file"; printf x)" != $'\n'x ]]
}

# RETURN: nothing, the diff representation of FILE is appended to TARGET.
#
# An empty file gets header and null index line but no hunk: emitting a
# '@@ -0,0 +1,0 @@' hunk corrupts the patch for 'git apply'.
member_render() {
    local file="$1" target="$2"
    if ! file_is_text "$file"; then
        # A binary member cannot be expressed as '+'-prefixed lines. git knows
        # the literal-patch encoding (deflate, base85); delegate rather than
        # reimplement it. 'git diff' reports difference with status 1.
        git diff --no-index --binary -- /dev/null "$file" >> "$target" || true
        return 0
    fi
    if [[ ! -s "$file" ]]; then
        {
            printf 'diff --git a/%s b/%s\n' "$file" "$file"
            printf '%s\n' 'new file mode 100644'
            printf '%s\n' 'index 0000000000000000000000000000000000000000..e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'
        } >> "$target"
        return 0
    fi
    {
        printf 'diff --git a/%s b/%s\n' "$file" "$file"
        printf '%s\n' 'new file mode 100644'
        printf '%s\n' '--- /dev/null'
        printf '+++ b/%s\n' "$file"
    } >> "$target"
    local nlines
    nlines=$(wc -l < "$file" | tr -d ' ')
    file_lacks_final_newline "$file" && nlines=$((nlines + 1))
    printf '@@ -0,0 +1,%s @@\n' "$nlines" >> "$target"
    sed 's/^/+/' "$file" >> "$target"
    if file_lacks_final_newline "$file"; then
        printf '\n%s\n' '\ No newline at end of file' >> "$target"
    fi
}

# --- Writing ---------------------------------------------------------------
# RETURN: nothing, the ignored header banner and the manifest for the given
#         member paths are written to TARGET.
#
# Everything before the first 'diff --git' is skipped by 'git apply' and by
# 'patch', so the manifest travels inside the bundle without disturbing it.
header_write() {
    local target="$1" part="$2" total="$3" crc="$4" content_bytes="$5"; shift 5
    local members=("$@") path
    {
        printf '%s\n' '# This bundle is a unified diff against /dev/null. To undump:'
        printf '%s\n' '#   git apply <this-file>          # recreates files and directories'
        printf '%s\n' '#   patch -p1 < <this-file>        # alternative, if git is unavailable'
        printf '%s\n' '# Lines beginning with "#" are ignored by both tools.'
        printf '%s\n' '# To check a bundle against the working tree: bundle.sh --verify <this-file>'
        printf '%s\n' '# The crc64 below covers the CONTENT ONLY -- these comment lines are not'
        printf '%s\n' '# in it, so it can be recomputed from the bundle: --verify does that.'
        printf '# bundle: %s  part %s of %s\n' "$(basename "$OUTPUT_FILE")" "$part" "$total"
        printf '# members: %s\n' "${#members[@]}"
        printf '# crc64 %s  %s bytes of content (from the first "diff --git")\n' \
               "$crc" "$content_bytes"
        if [[ ${#members[@]} -gt 0 ]]; then
            # One 'sha256sum' fork for every member of this part, not one
            # fork per member -- sha256sum already emits 'hash  path' in
            # the order given, so its own output is simply reformatted.
            sha256sum -- "${members[@]}" | while read -r hash path; do
                printf '# sha256 %s  %s\n' "$hash" "$path"
            done
        fi
    } >> "$target"
}

# RETURN: the argument with '.<part>of<total>' inserted before its extension,
#         or unchanged when TOTAL is 1.
part_name() {
    local name="$1" part="$2" total="$3"
    [[ "$total" -eq 1 ]] && { printf '%s' "$name"; return 0; }
    local base="${name%.*}" ext="${name##*.}"
    [[ "$base" == "$name" ]] && { printf '%s.%sof%s' "$name" "$part" "$total"; return 0; }
    printf '%s.%sof%s.%s' "$base" "$part" "$total" "$ext"
}

WRITTEN_PARTS=()
CHMOD_FILE=""
WRITTEN_CRC=""
WRITTEN_BYTES=""

# RETURN: nothing, "$scratch/m.<index>" holds the render of PATHS[<index>]
#         for every index, rendered concurrently rather than one at a time.
#
# Every index writes to its own file with no shared state, so this is safe
# to parallelise. Bounded with bash's own job control -- a background job
# per file, capped at nproc, drained with 'wait -n' as the cap is hit -- so
# no xargs -P and no GNU parallel are assumed. A failure in any one render
# is caught via a marker file, since a background job's exit status does not
# otherwise reach the caller, and re-raised as a single 'die' once every job
# has finished.
members_render_all() {
    local scratch="$1"; shift
    local paths=("$@")
    local n=${#paths[@]}
    local max_jobs
    max_jobs=$(nproc 2>/dev/null) || max_jobs=4
    [[ "$max_jobs" =~ ^[0-9]+$ && "$max_jobs" -ge 1 ]] || max_jobs=4
    local i running=0
    for ((i = 0; i < n; i++)); do
        ( member_render "${paths[$i]}" "$scratch/m.$i" \
          || : > "$scratch/FAILED.$i" ) &
        running=$((running + 1))
        if [[ "$running" -ge "$max_jobs" ]]; then
            wait -n
            running=$((running - 1))
        fi
    done
    wait
    compgen -G "$scratch/FAILED.*" >/dev/null 2>&1 \
        && die "rendering failed for one or more members"
    return 0
}

# RETURN: nothing, '<output>.chmod.sh' is written beside the bundle, holding
#         one 'chmod a+x' per executable member, and CHMOD_FILE names it.
#         Nothing is written where no member is executable, or where the
#         bundle goes to stdout.
#
# A UNIFIED DIFF CARRIES NO MODE. Every member arrives as a plain file, so a
# tree unpacked from a bundle cannot run its own tests, its own launchers or
# its own filters until the bits are restored -- and the failure is silent:
# 'permission denied' from a suite reads as a broken tree, not a missing
# chmod.
chmod_script_write() {
    local path exec_list=()
    for path in ${ACCEPTED[@]+"${ACCEPTED[@]}"}; do
        [[ -x "$path" ]] && exec_list+=("$path")
    done
    [[ ${#exec_list[@]} -gt 0 ]] || return 0
    [[ "$OUTPUT_FILE" == "-" ]] && return 0

    CHMOD_FILE="${WRITTEN_PARTS[0]}.chmod.sh"
    {
        echo "#! /bin/sh"
        echo "# Restore the execute bits a unified diff cannot carry."
        echo "# Run from the root the bundle was applied into."
        echo "set -e"
        for path in "${exec_list[@]}"; do
            printf 'chmod a+x "%s"\n' "$path"
        done
        echo "echo \"execute bits restored: ${#exec_list[@]} file(s)\""
    } > "$CHMOD_FILE"
    chmod a+x "$CHMOD_FILE"
}

# RETURN: nothing, the bundle is written to OUTPUT_FILE, or to several
#         '.NofM.' parts when --max-bytes forces a split, and WRITTEN_PARTS
#         holds the names written.
#
# Members are rendered once into a scratch directory and measured, so the
# split respects the emitted size rather than the raw file size. A single
# member larger than the limit occupies a part of its own.
bundle_write() {
    local scratch; scratch=$(mktemp -d)
    local n=${#ACCEPTED[@]}
    members_render_all "$scratch" ${ACCEPTED[@]+"${ACCEPTED[@]}"}

    # Sizes of the just-rendered files, batch-stat'd (chunked, so an
    # enormous member count can't overflow one command line) instead of one
    # 'stat' fork per file.
    local -A rendered_size=()
    if [[ $n -gt 0 ]]; then
        local rendered_files=() i step=500 j size name
        for ((i = 0; i < n; i++)); do rendered_files+=("$scratch/m.$i"); done
        j=0
        while [[ $j -lt $n ]]; do
            while read -r size name; do
                rendered_size["$name"]="$size"
            done < <(stat -c '%s %n' -- "${rendered_files[@]:j:step}")
            j=$((j + step))
        done
    fi

    local i sizes=() parts_of=() part=1 running=0
    for ((i = 0; i < n; i++)); do
        sizes[i]="${rendered_size[$scratch/m.$i]}"
        if [[ "$MAX_PART_BYTES" -gt 0 && $running -gt 0 \
              && $((running + sizes[i])) -gt "$MAX_PART_BYTES" ]]; then
            part=$((part + 1)); running=0
        fi
        parts_of[i]=$part
        running=$((running + sizes[i]))
    done
    local total=$part p name members=() idx
    for ((p = 1; p <= total; p++)); do
        name=$(part_name "$OUTPUT_FILE" "$p" "$total")
        members=()
        for idx in "${!parts_of[@]}"; do
            [[ "${parts_of[$idx]}" -eq "$p" ]] && members+=("${ACCEPTED[$idx]}")
        done
        #  THE CONTENT IS ASSEMBLED FIRST, then signed, then the header is
        #  written before it: a signature over the content cannot be
        #  computed while the header that carries it is already in the file.
        : > "$scratch/body"
        for idx in "${!parts_of[@]}"; do
            [[ "${parts_of[$idx]}" -eq "$p" ]] && cat "$scratch/m.$idx" >> "$scratch/body"
        done
        local crc content_bytes
        crc=$(crc64_stdin < "$scratch/body")
        content_bytes=$(stat -c%s "$scratch/body")
        [[ "$p" -eq 1 ]] && { WRITTEN_CRC="$crc"; WRITTEN_BYTES="$content_bytes"; }
        : > "$scratch/out"
        header_write "$scratch/out" "$p" "$total" "$crc" "$content_bytes" \
                     ${members[@]+"${members[@]}"}
        cat "$scratch/body" >> "$scratch/out"
        if [[ "$name" == "-" ]]; then cat "$scratch/out"
        else cp "$scratch/out" "$name"; fi
        WRITTEN_PARTS+=("$name")
    done
    rm -rf "$scratch"
}

# --- Verification ----------------------------------------------------------
# RETURN: 0, if every manifest entry of every given bundle matches the file of
#           that name in the working tree
#         1, else
#
# Differences are reported one per line as MISSING or DIFFERS with the path.
verify_bundles() {
    local bundle hash path actual bad=0 checked=0
    local stated_crc actual_crc stated_bytes actual_bytes crc_bad=0
    for bundle in "${VERIFY_FILES[@]}"; do
        [[ -f "$bundle" ]] || die "bundle '$bundle' not found"

        #  THE BUNDLE'S OWN INTEGRITY FIRST. The manifest answers whether the
        #  working tree still matches; the crc64 answers whether the bundle
        #  itself arrived whole. A truncated bundle would otherwise report
        #  every missing member as a tree difference.
        stated_crc=$(sed -n 's/^# crc64 \([0-9A-F]*\) .*/\1/p' "$bundle" | head -n1)
        if [[ -z "$stated_crc" ]]; then
            echo "NO CRC   $bundle -- written before bundle.sh carried one"
        else
            stated_bytes=$(sed -n 's/^# crc64 [0-9A-F]*  \([0-9]*\) .*/\1/p' \
                           "$bundle" | head -n1)
            actual_crc=$(bundle_content_crc64 "$bundle")
            actual_bytes=$(sed -n '/^diff --git /,$p' "$bundle" | wc -c | tr -d ' ')
            if [[ "$actual_crc" == "$stated_crc" ]]; then
                echo "CRC64 OK $bundle  ${actual_crc}  ${actual_bytes} bytes"
            else
                echo "CRC64 MISMATCH  $bundle"
                echo "    stated: ${stated_crc}  ${stated_bytes} bytes"
                echo "    actual: ${actual_crc}  ${actual_bytes} bytes"
                crc_bad=$((crc_bad + 1))
            fi
        fi

        while read -r _ _ hash path; do
            #  A TRUNCATED BUNDLE ends mid-manifest: the last line read is
            #  half a line, and reporting it as a missing file would name a
            #  file nobody asked for. The crc64 above already said what is
            #  wrong with such a bundle.
            [[ -n "$path" && -n "$hash" ]] || continue
            checked=$((checked + 1))
            if [[ ! -f "$path" ]]; then
                echo "MISSING  $path"; bad=$((bad + 1)); continue
            fi
            actual=$(sha256sum "$path" | cut -d' ' -f1)
            [[ "$actual" == "$hash" ]] || { echo "DIFFERS  $path"; bad=$((bad + 1)); }
        done < <(grep '^# sha256 ' "$bundle")
    done
    echo "Verified: ${checked} members, ${bad} mismatch(es)," \
         "${crc_bad} bundle(s) with a broken crc64"
    [[ $bad -eq 0 && $crc_bad -eq 0 ]]
}

# --- Dry Run ---------------------------------------------------------------
# RETURN: nothing, the named bucket is printed indented, one entry per line.
print_bucket() {
    local title="$1"; shift
    echo "== $title (${#@}) =="
    [[ $# -eq 0 ]] && { echo "    (none)"; return 0; }
    printf '    %s\n' "$@"
}

# RETURN: nothing, a report of accepted and rejected candidates, the largest
#         files and the resulting part count is printed.
dry_run_report() {
    local path
    if [[ "$SELECT_MODE" == "find" && ${#DIRS[@]} -gt 0 ]]; then
        local pruned=() prune_args=("-type" "d" "(") i
        for i in "${!EXCLUDE_PATTERNS[@]}"; do
            [[ "$i" -gt 0 ]] && prune_args+=("-o")
            prune_args+=("-name" "${EXCLUDE_PATTERNS[$i]}")
        done
        prune_args+=(")")
        mapfile -t pruned < <(find "${DIRS[@]}" \( "${prune_args[@]}" \) -prune -print)
        print_bucket "Directories pruned, incl. subtrees (${EXCLUDE_PATTERNS[*]:-<none>})" \
            ${pruned[@]+"${pruned[@]}"}
    fi
    print_bucket "Pruned by directory name (${EXCLUDE_PATTERNS[*]:-<none>})" \
        ${REJ_PRUNED[@]+"${REJ_PRUNED[@]}"}
    print_bucket "Excluded by path glob (${EXCLUDE_PATH_GLOBS[*]:-<none>})" \
        ${REJ_GLOB[@]+"${REJ_GLOB[@]}"}
    print_bucket "Excluded by base name (${EXCLUDE_NAME_GLOBS[*]:-<none>})" \
        ${REJ_NAME[@]+"${REJ_NAME[@]}"}
    print_bucket "Skipped, larger than ${MAX_FILE_BYTES} bytes" \
        ${REJ_LARGE[@]+"${REJ_LARGE[@]}"}
    print_bucket "Skipped, binary" ${REJ_BINARY[@]+"${REJ_BINARY[@]}"}
    print_bucket "Skipped, not found" ${REJ_MISSING[@]+"${REJ_MISSING[@]}"}
    print_bucket "Included" ${ACCEPTED[@]+"${ACCEPTED[@]}"}
    echo "== Largest ${TOP_N} included files =="
    if [[ ${#ACCEPTED[@]} -eq 0 ]]; then echo "    (none)"; else
        local shown_n=0
        while read -r size name; do
            [[ $shown_n -ge "$TOP_N" ]] && break
            printf '    %8s  %s\n' "$(numfmt --to=iec --suffix=B "$size")" "$name"
            shown_n=$((shown_n + 1))
        done < <(stat -c '%s %n' -- "${ACCEPTED[@]}" | LC_ALL=C sort -rn)
    fi
    local raw=0 size
    for path in ${ACCEPTED[@]+"${ACCEPTED[@]}"}; do
        size=$(stat -c%s "$path"); raw=$((raw + size))
    done

    #  THE EMITTED SIZE, measured by rendering: a diff carries a header
    #  per member and a '+' on every line, and a binary member rendered
    #  as a literal patch is LARGER than the file it came from. The raw
    #  total answers a different question than the one asked.
    local scratch emitted=0 n=${#ACCEPTED[@]}
    scratch=$(mktemp -d)
    members_render_all "$scratch" ${ACCEPTED[@]+"${ACCEPTED[@]}"}
    if [[ $n -gt 0 ]]; then
        local rendered_files=() i step=500 j size name
        for ((i = 0; i < n; i++)); do rendered_files+=("$scratch/m.$i"); done
        j=0
        while [[ $j -lt $n ]]; do
            while read -r size name; do
                emitted=$((emitted + size))
            done < <(stat -c '%s %n' -- "${rendered_files[@]:j:step}")
            j=$((j + step))
        done
    fi
    rm -rf "$scratch"

    local parts=1
    [[ "$MAX_PART_BYTES" -gt 0 ]] && parts=$(( (emitted / MAX_PART_BYTES) + 1 ))
    local exec_n=0
    for path in ${ACCEPTED[@]+"${ACCEPTED[@]}"}; do
        [[ -x "$path" ]] && exec_n=$((exec_n + 1))
    done
    echo "Total: ${#ACCEPTED[@]} files, $(numfmt --to=iec --suffix=B "$raw") raw"
    echo "Bundle: $(numfmt --to=iec --suffix=B "$emitted") emitted," \
         "~${parts} part(s), ${exec_n} executable member(s) [mode: ${SELECT_MODE}]"
    [[ $exec_n -gt 0 && $CHMOD_SCRIPT -eq 0 ]] && \
        echo "Note: ${exec_n} member(s) are executable and a diff carries no" \
             "mode -- consider --chmod-script"
    echo "Tip: rerun with --from-list after editing the 'Included' list into a file."
}

# --- Statistics ------------------------------------------------------------
# RETURN: nothing, one line of per-extension counts and one summary line are
#         printed for the written bundle.
statistics_report() {
    local -A ext_count=()
    local path base ext summary="" count size name
    for path in ${ACCEPTED[@]+"${ACCEPTED[@]}"}; do
        base=$(basename "$path")
        case "$base" in ?*.*) ext="${base##*.}" ;; *) ext="(no ext)" ;; esac
        ext_count["$ext"]=$(( ${ext_count["$ext"]:-0} + 1 ))
    done
    while read -r count ext; do
        [[ -n "$summary" ]] && summary+=", "
        summary+="\"*.${ext}\": ${count}"
    done < <(for ext in "${!ext_count[@]}"; do
                 printf '%s %s\n' "${ext_count[$ext]}" "$ext"
             done | LC_ALL=C sort -rn -k1,1)
    size=0
    for name in "${WRITTEN_PARTS[@]}"; do
        [[ "$name" == "-" ]] && continue
        size=$((size + $(stat -c%s "$name")))
    done
    echo "Files: ${summary:-(none)}"
    echo "Total: ${#ACCEPTED[@]} files, dump size: $(numfmt --to=iec --suffix=B "$size")"
}

# --- Main Execution Path ---------------------------------------------------
main() {
    local argv=() prof_args=() i=1
    # A profile is expanded in place of its '-p NAME', so that options given
    # on the command line still override it by coming later.
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "-p" ]]; then
            [[ $# -ge 2 ]] || die "-p requires an argument"
            mapfile -t prof_args < <(profile_arguments "$2")
            argv+=(${prof_args[@]+"${prof_args[@]}"}); shift 2; continue
        fi
        argv+=("$1"); shift
    done
    command_line_parse ${argv[@]+"${argv[@]}"}
    if [[ ${#VERIFY_FILES[@]} -gt 0 ]]; then verify_bundles; return $?; fi
    output_file_determine
    echo "(1) collecting candidates [mode: ${SELECT_MODE}]" >&2
    candidates_collect
    if [[ $DRY_RUN -eq 1 ]]; then dry_run_report; return 0; fi
    [[ ${#ACCEPTED[@]} -gt 0 ]] || die "no files selected; try -n to see why"
    echo "(2) rendering ${#ACCEPTED[@]} members" >&2
    bundle_write
    echo "Success: bundle written to ${WRITTEN_PARTS[*]}" >&2
    [[ $CHMOD_SCRIPT -eq 1 ]] && chmod_script_write
    statistics_report
    #  Not for a bundle that went to stdout: there is no file to read back,
    #  and reading '-' would take the terminal for a bundle. The signature
    #  stands in the header either way.
    if [[ "${WRITTEN_PARTS[0]}" != "-" ]]; then
        echo "Content:   crc64 ${WRITTEN_CRC} over ${WRITTEN_BYTES} bytes"
    fi
    echo "To undump: git apply ${WRITTEN_PARTS[0]}   (or: patch -p1 < ${WRITTEN_PARTS[0]})"
    [[ -n "$CHMOD_FILE" ]] && \
        echo "Then:      sh ${CHMOD_FILE}   -- a diff carries no execute bit"
}

main "$@"
