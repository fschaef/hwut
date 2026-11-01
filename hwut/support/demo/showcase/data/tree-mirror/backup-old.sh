#! /bin/bash
# backup-old.sh SRC DST -- the backup step as it stood in the old cron job.
cp -r "$1"/* "$2"/ && echo "copied $1 -> $2"
