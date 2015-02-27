# UTCDateTime.py
#
# Fix some serious python/sqlalchemy ugliness
#
# MySQL stores all datetime values as (implied) UTC datetimes.
# SQLAlchemy's DateTime format, however, generates NAIVE datetime objects
# when it retrieves these datetimes, thus generating ALL SORTS of nastiness
# such as misinterpreting the datetime contents and/or raising exceptions
# when a tz-aware datetime (such as we use EVERYWHERE else) is compared
# against a datetime value retrieved from MySQL.
#
# Thus this type which forces python to provide UTC datetimes into MySQL
# and generates tz-aware (UTC) datetime objects when retrieving them.
#
# From: http://stackoverflow.com/questions/2528189/can-sqlalchemy-datetime-objects-only-be-naive

from sqlalchemy import types
from dateutil.tz import tzutc
from datetime import datetime

class UTCDateTime(types.TypeDecorator):

    impl = types.DateTime

    def process_bind_param(self, value, engine):
        if value is not None:
            return value.astimezone(tzutc())

    def process_result_value(self, value, engine):
        if value is not None:
            return datetime(value.year, value.month, value.day,
                            value.hour, value.minute, value.second,
                            value.microsecond, tzinfo=tzutc())

