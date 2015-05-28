# utils.py
#
# this is for utilities so small and generic they aren't worth breaking out
#
#

import datetime
import iso8601
import locale
import pytz
import time

# force_date()
#
# always returns a TZ-aware datetime.datetime object
#
# converts from a string as needed. Adds TZ=UTC to datetime objects w/o TZ.
# Throws an exception if we are stuck and no default param is supplied.
#
# if passed a string, tries iso8601 format first then the %Y-%m-%dT%H:%M:%S
# format used by elasticsearch. Note that this does NOT understand timestamp,
# ie we do NOT try: datetime.datetime.fromtimestamp()
#
# pass default=None to return None if the date doesn't parse/convert.
# passing default=False will just throw an exception.
#
def force_date(maybedate, default=False):
    if isinstance(maybedate, datetime.datetime):
        if maybedate.tzinfo and maybedate.tzinfo.utcoffset(maybedate) != None:
            # Fuck python's datetime class; it truly sucks. Note that the
            # != None above is REQUIRED, because the utcoffset() method may
            # in fact return something that evaluates to False (probably 0)
            # for non-naive datetimes, so this IF statement ** fails **:
            # if maybedate.tzinfo and maybedate.tzinfo.utcoffset(maybedate):
            # this shit has been documented as confusing since at least 2010
            # but... come on. How hard would it be to have an is_naive() or
            # is_localized() method, and some decent handling around that
            # property? Fuck...
            return maybedate
        else:
            return pytz.utc.localize(maybedate)
    if isinstance(maybedate, str):
        try:
            return iso8601.parse_date(maybedate)
        except:
            pass
        try:
            return datetime.datetime.strptime(maybedate,
                                              '%Y-%m-%dT%H:%M:%S').replace(tzinfo=pytz.UTC)
        except:
            pass

    if default != False:
        return default
    raise ValueError


# now_utc()
#
# just a tiny convenience method to return a TZ-aware datetime
#
# UNBELIEVABLE that datetime's builtin utcnow() method returns a NAIVE obj!
#
def now_utc():
    return datetime.datetime.now(pytz.UTC)


# utc_to_local_tz()
#
# tiny convenience method to take a proper TZ-aware datetime in UTC
# (what I normally use!) to a naive datetime in the locale of the
# currently-executing code
#
def utc_to_local_tz(utc_dt):
    return utc_dt.replace(tzinfo=pytz.utc).astimezone(tz=None)


# utc_to_naive_local_tz(utctime)
#
# ... as above then strip out that tz to make a naive datetime
# (ie one which can be compared to the output of datetime.now(),
# which I NEVER want to use but some libraries (e.g. humanize) do
#
def utc_to_naive_local_tz(utctime):
    return utc_to_local_tz(utctime).replace(tzinfo=None)


# extract_int()
#
# extract an int from an input string if at all possible
#
# handles locale issues (e.g. optional 1000s separaters) and
# coerces a float to an int if necessary; returns None if it fails
#
def extract_int(s, locale_to_use='en_US.UTF-8'):
    if not s:
        return None
    locale.setlocale(locale.LC_ALL, locale_to_use)
    try:
        return locale.atoi(s)
    except ValueError:
        try:
            return int(locale.atof(s))
        except ValueError:
            return None
    return None  # should be unreached
        
