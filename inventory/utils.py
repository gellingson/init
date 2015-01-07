#!/usr/bin/env python3
#
# inventory utility classes
#
# yeah, each class should probably be pulled into its own module

# builtin modules used
import datetime
import logging
import pytz
import time

# third party modules used
import iso8601
import sqlalchemy

# GuessDate class:
#
# guesses a date from the object passed in & returns a datetime
#
# NOTES:
# inputs handled:
#     string with any of these date formats:
#     datetime
#     number (int or float) containing utime info
# to force a ValueException on failure to parse, call with default=False.
# datetime returned will be TZ-aware & in UTC unless instructed otherwise.
# optimization: string format most recently successful is retained and tried
# first if guess_date() is called again within the same process space.
# this is a class to cleanly encapsulate storing date format(s) across calls
#
# some practical info/common inputs:
# ebay uses iso8601 date & time strings with trailing Z indicating UTC
# 3taps uses unix timestamps in ints
#
# SEE ALSO: force_date() method in oglweb.listings.utils
#
class GuessDate(object):
    def __init__(self):
        self._successful_format = None
        self._formats = [
            'timestamp',  # mock format string, use datetime.fromtimestamp()
            'iso8601', # mock format string, use iso8601.parse_date()
            '%Y-%m-%dT%H:%M:%S', # used by eBay
        ]

    def _try(self, maybedate, format):
        d = None
        try:
            if format == 'timestamp':
                # specialcasing this as a mock format
                d = datetime.datetime.fromtimestamp(float(maybedate))  # UTC
            elif format == 'iso8601':
                d = iso8601.parse_date(maybedate)
            else:
                d = datetime.datetime.strptime(maybedate,
                                               format).replace(tzinfo=tzinfo)
        except (ValueError, TypeError):
            pass
        return d

    def __call__(self, maybedate, default=None, tzinfo=pytz.UTC):
        if isinstance(maybedate, datetime.datetime):
            if maybedate.tzinfo and maybedate.tzinfo.utcoffset(maybedate) != None:
                # any TZ-aware/localized datetime will be returned as-is, not
                # converted to the specified TZ
                d = maybedate
            else:
                # assume we are in UTC & the date was intended that way
                # UNSAFE TZ HANDLING, but in our usage better than failing
                d = pytz.utc.localize(maybedate)
        elif isinstance(maybedate, str):

            # try whatever worked last time
            fmt = self._successful_format
            d = self._try(maybedate, fmt)

            if not d:
                # try everything else
                for format in self._formats:
                    if format != fmt:  # tried that one already above...
                        d = self._try(maybedate, format)
                        if d:
                            self._successful_format = format  # try 1st next time
                            break

        elif isinstance(maybedate, float) or isinstance(maybedate, int):
            try:
                d = datetime.datetime.fromtimestamp(maybedate)
            except ValueError:
                pass
        else:
            pass # we're screwed -- fall through to the fail

        if not d:
            if default==False:  # caller wants exception on failure to parse
                raise ValueError
            else:
                d = default
        return d

# create a file global callable for the class
guessDate = GuessDate()

LOG = logging.getLogger(__name__)

class ImportReport(object):
    def __init__(self):
        self.counts = {}
        self.accepted_lsinfos = []
        self.rejected_lsinfos = []

    def add_accepted_lsinfo(self, lsinfo):
        self.accepted_lsinfos.append(lsinfo)

    def add_accepted_lsinfos(self, lsinfos):
        self.accepted_lsinfos += lsinfos

    def add_rejected_lsinfo(self, lsinfo):
        self.rejected_lsinfos.append(lsinfo)
        
    def add_rejected_lsinfos(self, lsinfos):
        self.rejected_lsinfos += lsinfos

    def text_report(self, classified, logger=None):
        return

    def db_report(self, classified, session):
        return

