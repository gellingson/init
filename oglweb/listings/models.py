# this has been generated using python manage.py inspectdb > models.py
# and hand-edited to just the table(s) we want. NOT removing managed=False yet.
#
# Also note: You'll have to insert the output of 'django-admin.py sqlcustom [app_label]'
# into your database.

# GEE do I need this following line??
from __future__ import unicode_literals

#builtin modules used
import datetime
import inspect
import iso8601

# third party modules used
from bunch import Bunch
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from jsonfield import JSONCharField

# OGL modules used

# this is to convert to jsonable: pull only attrs, not methods/complex internals
# from a model object and export as Bunch
def props(obj):
    pr = Bunch()
    for name in dir(obj):
        value = getattr(obj, name)
        if not name.startswith('__') and not name == 'user' and not inspect.ismethod(value):
            pr[name] = value
            return pr


class SavedListing(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    listing = models.ForeignKey('Listing')
    status = models.CharField(max_length=1)
    note = models.CharField(max_length=2048, blank=True)

    def __str__(self):
        return "{} {}".format(self.id, self.note)

    class Meta:
        managed = False
        db_table = 'saved_listing'

    # generate a Bunch() dict with JSON-serializable values
    # (ie no Datetime, Decimal, etc); also have just ids for
    # relations rather than the full structs
    def to_jsonable(self):
        jsonable = Bunch()
        jsonable.id = self.id
        jsonable.status = self.status
        jsonable.note = self.note
        jsonable.user_id = self.user.id
        jsonable.listing_id = self.listing.id
        return jsonable

    def from_jsonable(self, jsonable, load_relations=False):
        # might not already be a Bunch(), just a plain dict
        self.id = jsonable.get('id', None)
        self.user.id = jsonable['user_id']
        self.listing.id = jsonable['listing_id']
        self.status = jsonable['status']
        self.note = jsonable.get('note', None)
        if load_relations:
            self.user.load()
            self.listing.load()
        return self

class SavedQuery(models.Model):
    querytype = models.CharField(max_length=1)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True)
    ref = models.CharField(max_length=24)
    descr = models.CharField(max_length=80)
    query = JSONCharField(max_length=2048)
    mark_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.ref

    class Meta:
        managed = False
        db_table = 'saved_query'

    # generate a Bunch() dict with JSON-serializable values
    # (ie no Datetime, Decimal, etc); also have just ids for
    # relations rather than the full structs
    def to_jsonable(self):
        print("converting to jsonable: {}".format(self.ref))
        jsonable = Bunch()
        jsonable.id = self.id
        jsonable.querytype = self.querytype
        jsonable.ref = self.ref
        jsonable.descr = self.descr
        jsonable.query = self.query
        # handle non-JSONable types & any other type-specific oddities
        if self.__dict__.get('user', None) and self.user.is_authenticated():
            jsonable.user_id = self.user.id
        else:
            jsonable.user_id = None
        if self.mark_date:
            jsonable.mark_date = self.mark_date.isoformat()
        else:
            jsonable.mark_date = None
        return jsonable

    def from_jsonable(self, jsonable, load_relations=False):
        print("converting from jsonable: {}".format(jsonable['ref']))
        # might not already be a Bunch(), just a plain dict
        self.id = jsonable.get('id', None)
        self.querytype = jsonable.get('querytype', 'R')
        self.user = User()
        self.user.id = jsonable.get('user_id', None)
        self.ref = jsonable.get('ref', jsonable.get('id', None))  # old field name
        self.descr = jsonable.get('descr', jsonable.get('desc', None))  # old field name
        self.query = jsonable['query']
        date_string = jsonable.get('mark_date', None)
        if date_string:
            self.mark_date = iso8601.parse(self.mark_date)
        else:
            self.mark_date = None
        if load_relations and self.user.id:
            self.user.load()
        return self


class Classified(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    status = models.CharField(max_length=1)
    markers = models.CharField(max_length=24, blank=True)
    primary_classified_id = models.IntegerField(blank=True, null=True)
    textid = models.CharField(max_length=32)
    full_name = models.CharField(max_length=1024)
    base_url = models.CharField(max_length=1024, blank=True)
    custom_pull_func = models.CharField(max_length=1024, blank=True)
    extract_car_list_func = models.CharField(max_length=1024, blank=True)
    listing_from_list_item_func = models.CharField(max_length=1024, blank=True)
    parse_listing_func = models.CharField(max_length=1024, blank=True)
    inventory_url = models.CharField(max_length=1024, blank=True)
    owner_account_id = models.IntegerField(blank=True, null=True)
                                                 
    def __str__(self):
        return self.full_name

    class Meta:
        managed = False
        db_table = 'classified'


class Dealership(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    status = models.CharField(max_length=1)
    markers = models.CharField(max_length=24, blank=True)
    primary_dealership_id = models.IntegerField(blank=True, null=True)
    textid = models.CharField(max_length=32)
    full_name = models.CharField(max_length=1024)
    base_url = models.CharField(max_length=1024, blank=True)
    extract_car_list_func = models.CharField(max_length=1024, blank=True)
    listing_from_list_item_func = models.CharField(max_length=1024, blank=True)
    parse_listing_func = models.CharField(max_length=1024, blank=True)
    inventory_url = models.CharField(max_length=1024, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=255, blank=True)
    zip = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    owner_info = models.CharField(max_length=255, blank=True)
    license_info = models.CharField(max_length=255, blank=True)
    owner_account_id = models.IntegerField(blank=True, null=True)
    lat = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    lon = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)

    def __str__(self):
        return self.full_name

    class Meta:
        managed = False
        db_table = 'dealership'


class DealershipActivityLog(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    dealership_id = models.IntegerField(blank=True, null=True)
    activity_timpestamp = models.DateTimeField(blank=True, null=True)
    action_code = models.CharField(max_length=32, blank=True)
    message = models.CharField(max_length=1024, blank=True)

    class Meta:
        managed = False
        db_table = 'dealership_activity_log'


class InventoryImportLog(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    source_type = models.CharField(max_length=1, blank=True)
    source_id = models.IntegerField(blank=True, null=True)
    import_timestamp = models.DateTimeField(blank=True, null=True)
    message = models.CharField(max_length=1024, blank=True)

    class Meta:
        managed = False
        db_table = 'inventory_import_log'


class Listing(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    status = models.CharField(max_length=1, blank=True)
    markers = models.CharField(max_length=24, blank=True)
    model_year = models.CharField(max_length=4, blank=True)
    make = models.CharField(max_length=255, blank=True)
    model = models.CharField(max_length=255, blank=True)
    price = models.IntegerField(blank=True, null=True)
    listing_text = models.CharField(max_length=2048, blank=True)
    pic_href = models.CharField(max_length=2048, blank=True)
    listing_href = models.CharField(max_length=2048, blank=True)
    source_type = models.CharField(max_length=1, blank=True)
    source_id = models.IntegerField(blank=True, null=True)
    source_textid = models.CharField(max_length=255, blank=True)
    local_id = models.CharField(max_length=255, blank=True)
    stock_no = models.CharField(max_length=255, blank=True)
    lat = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    lon = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    location_text = models.CharField(max_length=50, blank=True)
    zip = models.CharField(max_length=10, blank=True)
    source = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, blank=True)
    int_color = models.CharField(max_length=20, blank=True)
    vin = models.CharField(max_length=20, blank=True)
    mileage = models.IntegerField(blank=True, null=True)
    tags = models.CharField(max_length=2048, blank=True)
    listing_date = models.DateTimeField(blank=True, null=True)
    removal_date = models.DateTimeField(blank=True, null=True)
    last_update = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return "{} {} {} ({}, {})".format(self.model_year, self.make, self.model, self.source_textid, str(self.id))

    class Meta:
        managed = False
        db_table = 'listing'


class Make(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    text_id = models.CharField(max_length=255, blank=True)
    canonical_name = models.CharField(max_length=255, blank=True)
    first_model_year = models.IntegerField(blank=True, null=True)
    last_model_year = models.IntegerField(blank=True, null=True)
    acquired_by = models.IntegerField(blank=True, null=True)
    last_update = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'make'


class Makemodel(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    text_id = models.CharField(max_length=255, blank=True)
    make_id = models.IntegerField(blank=True, null=True)
    canonical_model_name = models.CharField(max_length=255, blank=True)
    first_model_year = models.IntegerField(blank=True, null=True)
    last_model_year = models.IntegerField(blank=True, null=True)
    last_update = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'makemodel'


class Makemodelyear(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    make_id = models.IntegerField(blank=True, null=True)
    makemodel_id = models.IntegerField(blank=True, null=True)
    make_text_id = models.CharField(max_length=32)
    makemodel_text_id = models.CharField(max_length=64)
    model_trim = models.CharField(max_length=64)
    model_year = models.IntegerField()
    model_body = models.CharField(max_length=64, blank=True)
    model_engine_position = models.CharField(max_length=8, blank=True)
    model_engine_cc = models.IntegerField(blank=True, null=True)
    model_engine_cyl = models.IntegerField(blank=True, null=True)
    model_engine_type = models.CharField(max_length=32, blank=True)
    model_engine_valves_per_cyl = models.IntegerField(blank=True, null=True)
    model_engine_power_ps = models.IntegerField(blank=True, null=True)
    model_engine_power_rpm = models.IntegerField(blank=True, null=True)
    model_engine_torque_nm = models.IntegerField(blank=True, null=True)
    model_engine_torque_rpm = models.IntegerField(blank=True, null=True)
    model_engine_bore_mm = models.DecimalField(max_digits=6, decimal_places=1, blank=True, null=True)
    model_engine_stroke_mm = models.DecimalField(max_digits=6, decimal_places=1, blank=True, null=True)
    model_engine_compression = models.CharField(max_length=8, blank=True)
    model_engine_fuel = models.CharField(max_length=32, blank=True)
    model_top_speed_kph = models.IntegerField(blank=True, null=True)
    model_0_to_100_kph = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    model_drive = models.CharField(max_length=16, blank=True)
    model_transmission_type = models.CharField(max_length=32, blank=True)
    model_seats = models.IntegerField(blank=True, null=True)
    model_doors = models.IntegerField(blank=True, null=True)
    model_weight_kg = models.IntegerField(blank=True, null=True)
    model_length_mm = models.IntegerField(blank=True, null=True)
    model_width_mm = models.IntegerField(blank=True, null=True)
    model_height_mm = models.IntegerField(blank=True, null=True)
    model_wheelbase_mm = models.IntegerField(blank=True, null=True)
    model_lkm_hwy = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    model_lkm_mixed = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    model_lkm_city = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    model_fuel_cap_l = models.IntegerField(blank=True, null=True)
    model_sold_in_us = models.IntegerField(blank=True, null=True)
    model_co2 = models.IntegerField(blank=True, null=True)
    model_make_display = models.CharField(max_length=32, blank=True)

    class Meta:
        managed = False
        db_table = 'makemodelyear'


class Tbl02Models(models.Model):
    model_id = models.IntegerField(primary_key=True)
    model_make_id = models.CharField(max_length=32)
    model_name = models.CharField(max_length=64)
    model_trim = models.CharField(max_length=64)
    model_year = models.IntegerField()
    model_body = models.CharField(max_length=64, blank=True)
    model_engine_position = models.CharField(max_length=8, blank=True)
    model_engine_cc = models.IntegerField(blank=True, null=True)
    model_engine_cyl = models.IntegerField(blank=True, null=True)
    model_engine_type = models.CharField(max_length=32, blank=True)
    model_engine_valves_per_cyl = models.IntegerField(blank=True, null=True)
    model_engine_power_ps = models.IntegerField(blank=True, null=True)
    model_engine_power_rpm = models.IntegerField(blank=True, null=True)
    model_engine_torque_nm = models.IntegerField(blank=True, null=True)
    model_engine_torque_rpm = models.IntegerField(blank=True, null=True)
    model_engine_bore_mm = models.DecimalField(max_digits=6, decimal_places=1, blank=True, null=True)
    model_engine_stroke_mm = models.DecimalField(max_digits=6, decimal_places=1, blank=True, null=True)
    model_engine_compression = models.CharField(max_length=8, blank=True)
    model_engine_fuel = models.CharField(max_length=32, blank=True)
    model_top_speed_kph = models.IntegerField(blank=True, null=True)
    model_0_to_100_kph = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    model_drive = models.CharField(max_length=16, blank=True)
    model_transmission_type = models.CharField(max_length=32, blank=True)
    model_seats = models.IntegerField(blank=True, null=True)
    model_doors = models.IntegerField(blank=True, null=True)
    model_weight_kg = models.IntegerField(blank=True, null=True)
    model_length_mm = models.IntegerField(blank=True, null=True)
    model_width_mm = models.IntegerField(blank=True, null=True)
    model_height_mm = models.IntegerField(blank=True, null=True)
    model_wheelbase_mm = models.IntegerField(blank=True, null=True)
    model_lkm_hwy = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    model_lkm_mixed = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    model_lkm_city = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    model_fuel_cap_l = models.IntegerField(blank=True, null=True)
    model_sold_in_us = models.IntegerField(blank=True, null=True)
    model_co2 = models.IntegerField(blank=True, null=True)
    model_make_display = models.CharField(max_length=32, blank=True)

    class Meta:
        managed = False
        db_table = 'tbl_02_models'

class NonCanonicalMake(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    non_canonical_name = models.CharField(max_length=1024, blank=True)
    canonical_name = models.CharField(max_length=1024, blank=True)
    consume_words = models.CharField(max_length=1024, blank=True)
    push_words = models.CharField(max_length=1024, blank=True)

    def __str__(self):
        return "{} -> {} remove: {} add: {}".format(self.non_canonical_name, self.canonical_name, self.consume_words, self.push_words)

    class Meta:
        managed = False
        db_table = 'non_canonical_make'


class NonCanonicalModel(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    non_canonical_make = models.ForeignKey(NonCanonicalMake, blank=True, null=True)
    non_canonical_name = models.CharField(unique=True, max_length=50, blank=True)
    canonical_name = models.CharField(max_length=50, blank=True)
    consume_words = models.CharField(max_length=100, blank=True)
    push_words = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return "{} -> {} remove: {} add: {}".format(self.non_canonical_name, self.canonical_name, self.consume_words, self.push_words)

    class Meta:
        managed = False
        db_table = 'non_canonical_model'


class ConceptImplies(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    has_tag = models.ForeignKey('ConceptTag', related_name='has_tag')
    implies_tag = models.ForeignKey('ConceptTag', related_name='implies_tag')

    def __str__(self):
        return '{} -> {}'.format(self.has_tag, self.implies_tag)

    class Meta:
        managed = False
        db_table = 'concept_implies'


class ConceptTag(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    tag = models.CharField(unique=True, max_length=20)
    syn_of_tag = models.ForeignKey('self', blank=True, null=True)
    display_tag = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return '{} [{}]'.format(self.tag, self.syn_of_tag)

    class Meta:
        managed = False
        db_table = 'concept_tag'

        
class Zipcode(models.Model):
    zip = models.CharField(primary_key=True, max_length=5)
    city_upper = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state_code = models.CharField(max_length=2, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    county_upper = models.CharField(max_length=100, blank=True)
    county = models.CharField(max_length=100, blank=True)
    lat = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    lon = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'zipcode'
