#! /usr/bin/env python3
"""schedule.py -- when does a job run? Local wall-clock schedules in a zone.

    schedule.py daily   <zone> <first-day> <n> <HH:MM>   one run per local day
    schedule.py monthly <zone> <first-month> <n> <day>  one run per month

daily:   at HH:MM local; where that time does not exist (the clock jumps
         forward over it) at the first minute after the gap; where it
         exists twice (the clock falls back) once, at the first of the two.
monthly: on <day> of each month, clamped to the month's last day.
Prints one run per line: local time, zone abbreviation, UTC offset, UTC."""
import sys
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def exists(naive, zone):
    """RETURN: True if the wall-clock time 'naive' occurs in 'zone'."""
    aware = naive.replace(tzinfo=zone)
    back  = aware.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
    return back == naive


def show(naive, zone):
    aware = naive.replace(tzinfo=zone, fold=0)
    utc   = aware.astimezone(timezone.utc)
    print("%s %s %s %s" % (naive.strftime("%Y-%m-%d %H:%M"), aware.tzname(),
                           aware.strftime("%z"), utc.strftime("%Y-%m-%dT%H:%MZ")))


def daily(zone, first, n, hhmm):
    hour, minute = map(int, hhmm.split(":"))
    for k in range(n):
        day   = first + timedelta(days=k)
        naive = datetime(day.year, day.month, day.day, hour, minute)
        while not exists(naive, zone):
            naive += timedelta(minutes=1)
        show(naive, zone)


def monthly(zone, first, n, mday):
    year, month = first.year, first.month
    for _ in range(n):
        last = monthrange(year, month)[1]
        show(datetime(year, month, min(mday, last), 0, 0), zone)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


mode, zone, first, n, arg = sys.argv[1:6]
zone = ZoneInfo(zone)
if mode == "daily":
    daily(zone, date.fromisoformat(first), int(n), arg)
else:
    monthly(zone, date.fromisoformat(first + "-01"), int(n), int(arg))
