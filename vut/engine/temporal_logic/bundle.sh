#!/usr/bin/env bash

set -euo pipefail

# --- Configuration & State ---
EXTRA_FILES=()
EXCLUDE_PATTERN="OUT"
OUTPUT_FILE="component.txt"
EXTENSIONS=()
DIRS=()
COMPRESS_OUTPUT=false

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -d DIR1 [DIR2 ...]   Directories to search (space-separated after flag)
  -e EXT1 [EXT2 ...]   Extensions to include, e.g., "py" "lua" (space-separated after flag)
  -f FILE1 [FILE2 ...] Extra static files to append (space-separated after flag)
  -x PATTERN           Pattern to exclude via grep -v (Default: ${EXCLUDE_PATTERN})
  -o FILE              Output filename (Default: ${OUTPUT_FILE})
  -c                   Enable compressed text output (Gzip + Base64)
  -h, --help           Show this help message

Example:
   ./bundle.sh -d ./luau/ ./parser/ -e py txt lua -f README.txt -x OUT -o target.txt -c
EOF
}

# --- Parsing Subsystem ---

# These functions assign caller variables via nameref AND report how many
# positional args to shift. They must run in the CURRENT shell (not in a
# $(...) command substitution subshell), or the nameref assignments are lost.
# The shift count is therefore returned via the SHIFT_COUNT global, not stdout.
SHIFT_COUNT=0

command_line_get_nominus_followers() {
    local -n target_array=$1
    local n=1 # Start count at 1 to account for the flag itself (e.g., -d)

    # Shift away the array reference name ($1) and the flag ($2)
    shift 2

    # Consume following arguments until the next flag
    while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
        target_array+=("$1")
        shift
        n=$((n + 1))
    done

    SHIFT_COUNT=$n
}

command_line_get_follower() {
    local -n target_var=$1
    # $2 is the flag, $3 is the provided argument
    if [[ $# -lt 3 ]]; then
        echo "Error: $2 requires an argument" >&2
        exit 1
    fi
    target_var="$3"

    SHIFT_COUNT=2 # Shift 2: the flag + its argument
}

command_line_parse() {
    while [[ $# -gt 0 ]]; do
        local arg="$1"
        case "$arg" in
            -d) command_line_get_nominus_followers DIRS "$@"; shift "$SHIFT_COUNT" ;;
            -e) command_line_get_nominus_followers EXTENSIONS "$@"; shift "$SHIFT_COUNT" ;;
            -f) command_line_get_nominus_followers EXTRA_FILES "$@"; shift "$SHIFT_COUNT" ;;
            -x) command_line_get_follower EXCLUDE_PATTERN "$@"; shift "$SHIFT_COUNT" ;;
            -o) command_line_get_follower OUTPUT_FILE "$@"; shift "$SHIFT_COUNT" ;;
            -c) COMPRESS_OUTPUT=true; shift 1 ;;
            -h|--help) print_usage; exit 0 ;;
            *) echo "Error: Unknown option '$arg'" >&2; print_usage >&2; exit 1 ;;
        esac
    done
}

# --- Core Processing & Formatting ---

get_human_size() {
    local file="$1"
    if [[ -f "$file" ]]; then
        printf "%8s" "$(du -sh "$file" | cut -f1)"
    else
        printf "%8s" "0B"
    fi
}

format_file_header() {
    local file="$1"
    local size
    size=$(get_human_size "$file")
    printf "[%s] ---- BEGIN FILE: %s ----\n" "$size" "$file"
}

format_file_footer() {
    local file="$1"
    local size
    size=$(get_human_size "$file")
    printf "[%s] --- END FILE: %s ---\n\n" "$size" "$file"
}

dump_file_contents() {
    local file="$1"
    local out_target="$2"

    if [[ -f "$file" ]]; then
        format_file_header "$file" >> "$out_target"
        cat "$file" >> "$out_target"

        # Append empty line only if file does not end with a newline
        if [[ -s "$file" ]] && [[ "$(tail -c1 "$file")" != $'\n' ]]; then
            echo "" >> "$out_target"
        fi

        format_file_footer "$file" >> "$out_target"
    else
        echo "Warning: File '$file' not found. Skipping." >&2
    fi
}

# --- Search Strategy ---

build_find_extensions() {
    local -n find_args=$1
    for i in "${!EXTENSIONS[@]}"; do
        [[ "$i" -gt 0 ]] && find_args+=("-o")
        find_args+=("-name" "*.${EXTENSIONS[$i]}")
    done
}

process_directory_tree() {
    local out_target="$1"
    if [[ ${#DIRS[@]} -gt 0 && ${#EXTENSIONS[@]} -gt 0 ]]; then
        local find_name_args=()
        build_find_extensions find_name_args

        find "${DIRS[@]}" \( "${find_name_args[@]}" \) -print0 \
            | grep -z -v "$EXCLUDE_PATTERN" \
            | while IFS= read -r -d '' file; do
                dump_file_contents "$file" "$out_target"
              done
    elif [[ ${#DIRS[@]} -gt 0 || ${#EXTENSIONS[@]} -gt 0 ]]; then
        echo "Warning: Both directories (-d) and extensions (-e) must be defined to run find query. Skipping tree search." >&2
    fi
}

process_explicit_files() {
    local out_target="$1"
    for file in "${EXTRA_FILES[@]}"; do
        dump_file_contents "$file" "$out_target"
    done
}

# --- Output Handling ---

remove_trailing_empty_lines() {
    local target="$1"
    # Strips contiguous empty lines at the end of the file safely
    sed -e :a -e '/^\n*$/{$d;N;ba' -e '}' "$target" > "${target}.tmp"
    mv "${target}.tmp" "$target"
}

apply_text_compression() {
    local target="$1"
    if [[ "$COMPRESS_OUTPUT" == true ]]; then
        local temp_binary
        temp_binary=$(mktemp)

        gzip -c "$target" > "$temp_binary"

        cat << 'EOF' > "$target"
# BUNDLE-ARCHIVE-V1
Unpack-Command: tail -n +4 "<PATH-TO-THIS-FILE>" | base64 -d | gunzip > unpacked_output.txt
--- END HEADER ---
EOF
        base64 "$temp_binary" >> "$target"
        rm -f "$temp_binary"
    fi
}

# --- Main Execution Path ---

main() {
    echo "(1) parsing command line"
    command_line_parse "$@"

    local temp_payload
    temp_payload=$(mktemp)

    echo "(2) process directory trees"
    process_directory_tree "$temp_payload"

    echo "(3) process explicit files"
    process_explicit_files "$temp_payload"

    echo "(4) ensure ending newline, remove empty lines at ends of files"
    remove_trailing_empty_lines "$temp_payload"

    echo "(5) apply optional compression"
    apply_text_compression "$temp_payload"

    mv "$temp_payload" "$OUTPUT_FILE"
    echo "Success: Compiled output written to $OUTPUT_FILE (Compressed: $COMPRESS_OUTPUT)"
}

main "$@"
