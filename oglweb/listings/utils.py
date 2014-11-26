# utils.py
#
# this is for utilities so small and generic they aren't worth breaking out
#
#

import datetime
import iso8601
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
