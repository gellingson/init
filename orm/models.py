
# coding: utf-8
from decimal import Decimal
import re

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy import String, text
from sqlalchemy.sql.functions import func
from sqlalchemy.orm import reconstructor
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr


# id column is used on most but not all tables, so make a mixin
class IDMixIn(object):
    id = Column(Integer, primary_key=True)


# mixin to handle push/consume word lists: converts space-separated word
# list to a python list. Does not convert back; suitable only as refdata
class ConsumePushMixIn(object):
    def __init__(self):
        self.consume_list = []
        self.push_list = []

    @reconstructor
    def init_on_load(self):
        if self.consume_words:
            self.consume_list = self.consume_words.split(':')
        else:
            self.consume_list = []
        if self.push_words:
            self.push_list = self.push_words.split(':')
        else:
            self.push_list = []


# extend the base to automagically get non-camelcase tablename
class Base(object):

    @declared_attr
    def __tablename__(cls):
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def convert_datetime(value):
        return value.strftime("%Y-%m-%dT%H:%M:%S")

    def get_iter(self):
        for c in self.__table__.columns:
            if getattr(self, c.name) and isinstance(c.type, DateTime):
                value = Listing.convert_datetime(getattr(self, c.name))
            elif getattr(self, c.name) and isinstance(getattr(self, c.name),
                                                      Decimal):
                value = str(getattr(self, c.name))
            else:
                value = getattr(self, c.name)

            yield(c.name, value)

    def iterfunc(self):
        """Returns an iterable that supports .next()
        so we can do dict(sa_instance)
        """
        return self.get_iter()

    def fromdict(self, values):
        """Merge items in values dict into our object if one of our columns
        """
        for c in self.__table__.columns:
            if c.name in values:
                setattr(self, c.name, values[c.name])

    def __str__(self):
        return str(dict(self))

Base = declarative_base(cls=Base)
metadata = Base.metadata
Base.__iter__ = Base.iterfunc


class Classified(IDMixIn, Base):

    status = Column(String(1), nullable=False)
    markers = Column(String(24))
    primary_classified_id = Column(Integer)
    textid = Column(String(32), nullable=False)
    full_name = Column(String(1024), nullable=False)
    base_url = Column(String(1024))
    custom_pull_func = Column(String(1024))
    extract_car_list_func = Column(String(1024))
    listing_from_list_item_func = Column(String(1024))
    parse_listing_func = Column(String(1024))
    anchor = Column(String(1024))
    inventory_url = Column(String(1024))
    owner_account_id = Column(Integer)


class Dealership(IDMixIn, Base):

    status = Column(String(1), nullable=False)
    markers = Column(String(24))
    primary_dealership_id = Column(Integer)
    textid = Column(String(32), nullable=False)
    full_name = Column(String(1024), nullable=False)
    base_url = Column(String(1024))
    extract_car_list_func = Column(String(1024))
    listing_from_list_item_func = Column(String(1024))
    parse_listing_func = Column(String(1024))
    inventory_url = Column(String(1024))
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(255))
    state = Column(String(255))
    zip = Column(String(255))
    phone = Column(String(30))
    owner_info = Column(String(255))
    license_info = Column(String(255))
    owner_account_id = Column(Integer)
    lat = Column(Numeric(10, 7))
    lon = Column(Numeric(10, 7))


class DealershipActivityLog(IDMixIn, Base):

    dealership_id = Column(Integer)
    activity_timpestamp = Column(DateTime)
    action_code = Column(String(32))
    message = Column(String(1024))


class InventoryImportLog(IDMixIn, Base):

    source_type = Column(String(1))
    source_id = Column(Integer)
    import_timestamp = Column(DateTime)
    message = Column(String(1024))


class Listing(IDMixIn, Base):

    markers = Column(String(24))
    status = Column(String(1), nullable=False)
    model_year = Column(String(4))
    make = Column(String(255))
    model = Column(String(255))
    price = Column(Integer)
    listing_text = Column(String(2048))
    pic_href = Column(String(2048))
    listing_href = Column(String(2048))
    source_type = Column(String(1))
    source_id = Column(Integer)
    source_textid = Column(String(255))
    local_id = Column(String(255))
    stock_no = Column(String(255))
    location_text = Column(String(50))
    zip = Column(String(10))
    source = Column(String(50))
    color = Column(String(20))
    int_color = Column(String(20))
    vin = Column(String(20))
    mileage = Column(Integer)
    listing_date = Column(DateTime, default=func.now())
    removal_date = Column(DateTime)
    last_update = Column(DateTime,
                         server_default=text(
                             'CURRENT TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    lat = Column(Numeric(10, 7))
    lon = Column(Numeric(10, 7))
    tags = Column(String(2048))

    def __init__(self):
        self.tagset = set()

    @reconstructor
    def init_on_load(self):
        if self.tags:
            self.tagset = set(self.tags.split(' '))
        else:
            self.tagset = set()

    def add_tag(self, tag):
        self.tagset.add(tag)
        # writethrough to the underlying column now
        # GEE TODO: would be more efficient to writethrough only @ write hook?
        self.tags = ' '.join(self.tagset)

    def add_tags(self, tags):
        if tags:
            self.tagset = self.tagset.union(tags)
            # writethrough to the underlying column now
            # GEE TODO: more efficient to writethrough only @ write hook?
            self.tags = ' '.join(self.tagset)

    def remove_tag(self, tag):
        # .remove() would raise KeyError if not found; .discard() does not
        self.tagset.discard(tag)
        # writethrough to the underlying column now
        # GEE TODO: would be more efficient to writethrough only @ write hook?
        self.tags = ' '.join(self.tagset)

    def has_tag(self, tag):
        return tag in self.tagset

    def add_markers(self, more_markers):
        if not self.markers:
            self.markers = more_markers
        elif not more_markers:
            pass
        else:  # both have contents: merge
            self.markers = ''.join(set(self.markers.append(more_markers)))


class ListingSourceinfo(IDMixIn, Base):
    source_type = Column(String(1))
    source_id = Column(Integer)
    local_id = Column(String(255))
    proc_time = Column(DateTime, default=func.now())
    listing_id = Column(Integer,
                        ForeignKey('listing.id'))
    entry = Column(Text)
    detail_enc = Column(String(1))
    detail_html = Column(Text)

class NonCanonicalMake(IDMixIn, ConsumePushMixIn, Base):

    non_canonical_name = Column(String(1024), index=True)
    canonical_name = Column(String(1024))
    consume_words = Column(String(1024))
    push_words = Column(String(1024))


class NonCanonicalModel(IDMixIn, ConsumePushMixIn, Base):

    non_canonical_make_id = Column(Integer,
                                   ForeignKey('non_canonical_make.id'))
    non_canonical_name = Column(String(50), index=True)
    canonical_name = Column(String(50))
    consume_words = Column(String(100))
    push_words = Column(String(100))


class ConceptTag(IDMixIn, Base):

    tag = Column(String(20))
    syn_of_tag_id = Column(Integer, ForeignKey('concept_tag.id'))
    display_tag = Column(String(20))

    # GEE TODO: implement recursive pull of implied tags
    def implied_tags(level=9):
        # default level limit is just to catch if something is wonky
        return []

class ConceptImplies(IDMixIn, Base):

    has_tag_id = Column(Integer, ForeignKey('concept_tag.id'))
    implies_tag_id = Column(Integer, ForeignKey('concept_tag.id'))


class Tbl02Model(Base):

    model_id = Column(Integer, primary_key=True)
    model_make_id = Column(String(32), nullable=False, index=True)
    model_name = Column(String(64), nullable=False, index=True)
    model_trim = Column(String(64), nullable=False, index=True)
    model_year = Column(Integer, nullable=False, index=True)
    model_body = Column(String(64), index=True)
    model_engine_position = Column(String(8), index=True)
    model_engine_cc = Column(Integer)
    model_engine_cyl = Column(Integer)
    model_engine_type = Column(String(32))
    model_engine_valves_per_cyl = Column(Integer)
    model_engine_power_ps = Column(Integer)
    model_engine_power_rpm = Column(Integer)
    model_engine_torque_nm = Column(Integer)
    model_engine_torque_rpm = Column(Integer)
    model_engine_bore_mm = Column(Numeric(6, 1))
    model_engine_stroke_mm = Column(Numeric(6, 1))
    model_engine_compression = Column(String(8))
    model_engine_fuel = Column(String(32), index=True)
    model_top_speed_kph = Column(Integer)
    model_0_to_100_kph = Column(Numeric(4, 1))
    model_drive = Column(String(16), index=True)
    model_transmission_type = Column(String(32))
    model_seats = Column(Integer)
    model_doors = Column(Integer)
    model_weight_kg = Column(Integer)
    model_length_mm = Column(Integer)
    model_width_mm = Column(Integer)
    model_height_mm = Column(Integer)
    model_wheelbase_mm = Column(Integer)
    model_lkm_hwy = Column(Numeric(4, 1))
    model_lkm_mixed = Column(Numeric(4, 1))
    model_lkm_city = Column(Numeric(4, 1))
    model_fuel_cap_l = Column(Integer)
    model_sold_in_us = Column(Integer, index=True)
    model_co2 = Column(Integer)
    model_make_display = Column(String(32))


class Zipcode(Base):

    zip = Column(String(5), primary_key=True, server_default=text("''"))
    city_upper = Column(String(100))
    city = Column(String(100))
    state_code = Column(String(2), index=True)
    state = Column(String(100))
    country = Column(String(100))
    county_upper = Column(String(100))
    county = Column(String(100))
    lat = Column(Numeric(10, 7))
    lon = Column(Numeric(10, 7))

class ZipcodeTemp(Base):

    zip = Column(String(5), primary_key=True, server_default=text("''"))
    city = Column(String(100))
    state_code = Column(String(2), index=True)
    lat = Column(Numeric(10, 7))
    lon = Column(Numeric(10, 7))


class SavedQuery(IDMixIn, Base):
    querytype = Column(String(1), nullable=False)
    user_id = Column(Integer,
                     ForeignKey('auth_user.id'))
    listing_id = Column(Integer,
                        ForeignKey('listing.id'))
    status = Column(String(1), nullable=False)
    ref = Column(String(24))
    descr = Column(String(80))
    note = Column(String(2048))


class SavedListing(IDMixIn, Base):
    user_id = Column(Integer,
                     ForeignKey('auth_user.id'))
    listing_id = Column(Integer,
                        ForeignKey('listing.id'))
    status = Column(String(1), nullable=False)
    note = Column(String(2048))
