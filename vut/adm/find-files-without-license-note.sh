# SPDX-License: MIT
#
# Find the files that do not contain the License note and print a 'make-format' string
# that makes the IDE jump to the first line of the file.
# (C) Frank-Rene Schaefer
grep -riL "SPDX-License: MIT" . \
     --include "*.py" \
     --exclude-dir "external" \
     | awk '{print $0 ":1:1:";}'
