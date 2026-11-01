#! /bin/sh
# run.sh -- start the service in its region, in its data directory
[ -n "$APP_REGION" ] || { echo "run.sh: set APP_REGION" >&2; exit 1; }
cd "${APP_DATA_DIR:-/var/lib/bench}" || exit 1
exec python3 /opt/bench/service/app.py --region "$APP_REGION"
