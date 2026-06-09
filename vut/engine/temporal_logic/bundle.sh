#!/usr/bin/env bash
#

# Exit immediately if a command exits with a non-zero status
set -e

# Default values
EXTRA_FILES=()
EXCLUDE_PATTERN="OUT"
OUTPUT_FILE="component.txt"
EXTENSIONS=()
DIRS=()

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -d DIR1 [DIR2 ...]   Directories to search (space-separated after flag)
  -e EXT1 [EXT2 ...]   Extensions to include, e.g., "py" "lua" (space-separated after flag)
  -f FILE1 [FILE2 ...] Extra static files to append (space-separated after flag)
  -x PATTERN           Pattern to exclude via grep -v (Default: $EXCLUDE_PATTERN)
  -o FILE              Output filename (Default: $OUTPUT_FILE)
  -h                   Show this help message

Example: 
   ./bundle.sh -d ./luau/ ./parser/ -e py txt lua -f README.txt DISCUSSIONS.txt -x OUT -o component-reactive-engine.txt
EOF
}

# Parse command-line options supporting multi-value parameters
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d)
            shift
            while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
                DIRS+=("$1")
                shift
            done
            ;;
        -e)
            shift
            while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
                EXTENSIONS+=("$1")
                shift
            done
            ;;
        -f)
            shift
            while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
                EXTRA_FILES+=("$1")
                shift
            done
            ;;
        -x)
            EXCLUDE_PATTERN="$2"
            shift 2
            ;;
        -o)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -h)
            print_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option $1" >&2
            print_usage >&2
            exit 1
            ;;
    esac
done

# Initialize or clear the output file
: > "$OUTPUT_FILE"

# Process files from find if directories and extensions are provided
if [ ${#DIRS[@]} -gt 0 ] && [ ${#EXTENSIONS[@]} -gt 0 ]; then
    # Construct find arguments for extensions: -name "*.ext1" -o -name "*.ext2"
    FIND_NAME_ARGS=()
    for i in "${!EXTENSIONS[@]}"; do
        if [ "$i" -gt 0 ]; then
            FIND_NAME_ARGS+=("-o")
        fi
        FIND_NAME_ARGS+=("-name" "*.${EXTENSIONS[$i]}")
    done

    find "${DIRS[@]}" \( "${FIND_NAME_ARGS[@]}" \) -print0 | 
        grep -z -v "$EXCLUDE_PATTERN" | 
        while IFS= read -r -d '' file; do
            if [ -f "$file" ]; then
                echo "FILE: $file" >&2
                echo "---- BEGIN FILE: $file ----"
                cat "$file"
                echo ""
                echo "--- END FILE: $file ---"
            fi
        done >> "$OUTPUT_FILE"
elif [ ${#DIRS[@]} -gt 0 ] || [ ${#EXTENSIONS[@]} -gt 0 ]; then
    echo "Warning: Both directories (-d) and extensions (-e) must be defined to run find query. Skipping tree search." >&2
fi

# Process the explicit extra files
for file in "${EXTRA_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "FILE: $file" >&2
        echo "---- BEGIN FILE: $file ----"
        cat "$file"
        echo ""
        echo "--- END FILE: $file ---"
    fi
done >> "$OUTPUT_FILE"

echo "Success: Compiled output written to $OUTPUT_FILE"
