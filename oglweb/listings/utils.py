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
# format used by elasticsearch. 
#
# pass default=None to return None if the date doesn't parse/convert.
# passing default=False will just throw an exception.
#
def force_date(maybedate, default=False):
    if isinstance(maybedate, datetime.datetime):
        if maybedate.tzinfo and maybedate.tzinfo.utcoffset(maybedate):
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
