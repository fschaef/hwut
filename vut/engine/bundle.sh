#!/usr/bin/env bash
print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -d DIR1 [DIR2 ...]   Directories to search (space-separated)
  -e EXT1 [EXT2 ...]   Extensions to include (space-separated)
  -f FILE1 [FILE2 ...] Extra static files to append (space-separated)
  -x PAT1 [PAT2 ...]   Patterns to exclude via grep -v (Default: ${EXCLUDE_PATTERNS[*]})
  -o FILE              Output filename (Default: dump-<first-dir-name>.txt)
  -h, --help           Show this help message
EOF
}


set -euo pipefail

# --- Configuration & State ---
EXTRA_FILES=()
EXCLUDE_PATTERNS=("OUT")
OUTPUT_FILE=""
EXTENSIONS=()
DIRS=()

# --- Parsing Subsystem ---

SHIFT_COUNT=0

command_line_get_nominus_followers() {
    local -n target_array=$1
    local n=1
    shift 2

    while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
        target_array+=("$1")
        shift
        n=$((n + 1))
    done

    SHIFT_COUNT=$n
}

command_line_get_follower() {
    local -n target_var=$1
    if [[ $# -lt 3 ]]; then
        echo "Error: $2 requires an argument" >&2
        exit 1
    fi
    target_var="$3"
    SHIFT_COUNT=2
}

command_line_parse() {
    while [[ $# -gt 0 ]]; do
        local arg="$1"
        case "$arg" in
            -d) command_line_get_nominus_followers DIRS "$@"; shift "$SHIFT_COUNT" ;;
            -e) command_line_get_nominus_followers EXTENSIONS "$@"; shift "$SHIFT_COUNT" ;;
            -f) command_line_get_nominus_followers EXTRA_FILES "$@"; shift "$SHIFT_COUNT" ;;
            -x) EXCLUDE_PATTERNS=()
                command_line_get_nominus_followers EXCLUDE_PATTERNS "$@"; shift "$SHIFT_COUNT" ;;
            -o) command_line_get_follower OUTPUT_FILE "$@"; shift "$SHIFT_COUNT" ;;
            -h|--help) print_usage; exit 0 ;;
            *) echo "Error: Unknown option '$arg'" >&2; print_usage >&2; exit 1 ;;
        esac
    done
}

# Derive OUTPUT_FILE from the first search directory when -o was not given.
output_file_determine() {
    [[ -n "$OUTPUT_FILE" ]] && return 0
    local dir_name="files"
    if [[ ${#DIRS[@]} -gt 0 ]]; then
        dir_name=$(basename "$(realpath -m "${DIRS[0]}")")
    fi
    OUTPUT_FILE="dump-${dir_name}.txt"
}

# --- Core Processing & Formatting ---

# Returns success if FILE is non-empty and its last byte is NOT a newline.
# Command substitution strips trailing newlines, so we compare byte counts
# instead of capturing tail output.
file_lacks_final_newline() {
    local file="$1"
    [[ -s "$file" ]] || return 1
    local last
    last=$(tail -c1 "$file" | od -An -tu1 | tr -d ' ')
    [[ "$last" != "10" ]]
}

# Returns 0 if the file was dumped, 1 if it was skipped.
dump_file_contents() {
    local file="$1"
    local out_target="$2"

    if [[ -f "$file" ]]; then
        # An empty file has no hunk in git's format: just the diff header and
        # a null index line. Emitting a '@@ -0,0 +1,0 @@' hunk corrupts the
        # patch for `git apply`.
        if [[ ! -s "$file" ]]; then
            {
                printf 'diff --git a/%s b/%s\n' "$file" "$file"
                printf '%s\n' 'new file mode 100644'
                printf '%s\n' 'index 0000000000000000000000000000000000000000..e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'
            } >> "$out_target"
            return 0
        fi

        # Git-diff style header: every line of content becomes an added (+) line,
        # so the whole bundle reads as a unified diff against /dev/null.
        {
            printf 'diff --git a/%s b/%s\n' "$file" "$file"
            printf '%s\n' 'new file mode 100644'
            printf '%s\n' '--- /dev/null'
            printf '+++ b/%s\n' "$file"
        } >> "$out_target"

        # Hunk header with correct added-line count.
        local nlines
        nlines=$(wc -l < "$file" | tr -d ' ')
        # Account for a missing final newline (counts as one more content line).
        if file_lacks_final_newline "$file"; then
            nlines=$((nlines + 1))
        fi
        printf '@@ -0,0 +1,%s @@\n' "$nlines" >> "$out_target"

        # Prefix every content line with '+'. GNU sed preserves a missing
        # final newline, so add one explicitly before the marker.
        sed 's/^/+/' "$file" >> "$out_target"

        # Match git's exact format for a missing final newline.
        if file_lacks_final_newline "$file"; then
            printf '\n%s\n' '\ No newline at end of file' >> "$out_target"
        fi
    else
        echo "Warning: File '$file' not found. Skipping." >&2
        return 1
    fi
}

# --- Search Strategy & Collection ---

build_find_extensions() {
    local -n find_args=$1
    for i in "${!EXTENSIONS[@]}"; do
        [[ "$i" -gt 0 ]] && find_args+=("-o")
        find_args+=("-name" "*.${EXTENSIONS[$i]}")
    done
}

collect_target_files() {
    local list_file="$1"

    if [[ ${#DIRS[@]} -gt 0 && ${#EXTENSIONS[@]} -gt 0 ]]; then
        local find_name_args=()
        build_find_extensions find_name_args

        if [[ ${#EXCLUDE_PATTERNS[@]} -gt 0 ]]; then
            local grep_args=()
            local pattern
            for pattern in "${EXCLUDE_PATTERNS[@]}"; do
                grep_args+=("-e" "$pattern")
            done
            find "${DIRS[@]}" \( "${find_name_args[@]}" \) -print0 \
                | grep -z -v "${grep_args[@]}" >> "$list_file" || true
        else
            find "${DIRS[@]}" \( "${find_name_args[@]}" \) -print0 >> "$list_file"
        fi
    fi

    for file in "${EXTRA_FILES[@]}"; do
        printf "%s\0" "$file" >> "$list_file"
    done
}

# --- Statistics ---

declare -A EXT_COUNT=()
TOTAL_COUNT=0

statistics_register() {
    local base ext
    base=$(basename "$1")
    case "$base" in
        ?*.*) ext="${base##*.}" ;;
        *)    ext="(no ext)" ;;
    esac
    EXT_COUNT["$ext"]=$(( ${EXT_COUNT["$ext"]:-0} + 1 ))
    TOTAL_COUNT=$((TOTAL_COUNT + 1))
}

# Prints: Files: "*.txt": 321, "*.py": 2, ... (sorted by count, descending)
statistics_report() {
    local summary="" count ext
    while read -r count ext; do
        [[ -n "$summary" ]] && summary+=", "
        summary+="\"*.${ext}\": ${count}"
    done < <(
        for ext in "${!EXT_COUNT[@]}"; do
            printf '%s %s\n' "${EXT_COUNT[$ext]}" "$ext"
        done | sort -rn -k1,1
    )

    local size
    size=$(numfmt --to=iec --suffix=B "$(stat -c%s "$OUTPUT_FILE")")

    echo "Files: ${summary:-(none)}"
    echo "Total: ${TOTAL_COUNT} files, dump size: ${size}"
}

# --- Main Execution Path ---

main() {
    echo "(1) parsing command line"
    command_line_parse "$@"
    output_file_determine

    local file_list_tmp
    file_list_tmp=$(mktemp)

    echo "(2) collecting and sorting files"
    collect_target_files "$file_list_tmp"
    sort -z -o "$file_list_tmp" "$file_list_tmp"

    local temp_payload
    temp_payload=$(mktemp)

    # Header banner: '#' lines are ignored by `git apply` and `patch`
    # (everything before the first 'diff --git' is skipped), so they are
    # safe to keep in the bundle as an inline how-to-undump hint.
    cat << 'EOF' > "$temp_payload"
# This bundle is a unified diff against /dev/null. To undump:
#   git apply <this-file>          # recreates files and directories
#   patch -p1 < <this-file>        # alternative, if git is unavailable
# Lines beginning with '#' are ignored by both tools.
EOF

    echo "(3) dumping file contents"
    while IFS= read -r -d '' file; do
        if dump_file_contents "$file" "$temp_payload"; then
            statistics_register "$file"
        fi
    done < "$file_list_tmp"

    mv "$temp_payload" "$OUTPUT_FILE"
    rm -f "$file_list_tmp"

    echo "Success: Concatenated bundle written to $OUTPUT_FILE"
    statistics_report
    echo "To undump: git apply $OUTPUT_FILE   (or: patch -p1 < $OUTPUT_FILE)"
}

main "$@"
