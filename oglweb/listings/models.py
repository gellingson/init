# this has been generated using python manage.py inspectdb > models.py
# and hand-edited to just the table(s) we want. NOT removing managed=False yet.
#
# Also note: You'll have to insert the output of 'django-admin.py sqlcustom [app_label]'
# into your database.

# GEE do I need this following line??
from __future__ import unicode_literals

import datetime
from django.db import models
from django.utils import timezone


class Classified(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    flags = models.TextField(blank=True)  # This field type is a guess.
    primary_classified_id = models.IntegerField(blank=True, null=True)
    textid = models.CharField(max_length=32)
    full_name = models.CharField(max_length=1024)
    base_url = models.CharField(max_length=1024, blank=True)
    extract_car_list_func = models.CharField(max_length=1024, blank=True)
    listing_from_list_item_func = models.CharField(max_length=1024, blank=True)
    parse_listing_func = models.CharField(max_length=1024, blank=True)
    inventory_url = models.CharField(max_length=1024, blank=True)
    owner_account_id = models.IntegerField(blank=True, null=True)
    custom_pull_func = models.CharField(max_length=1024, blank=True)
    def __str__(self):
        return self.full_name

    class Meta:
        managed = False
        db_table = 'classified'


class Dealership(models.Model):
    id = models.IntegerField(primary_key=True)  # AutoField?
    flags = models.TextField(blank=True)  # This field type is a guess.
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
    phone = models.IntegerField(blank=True, null=True)
    owner_info = models.CharField(max_length=255, blank=True)
    license_info = models.CharField(max_length=255, blank=True)
    owner_account_id = models.IntegerField(blank=True, null=True)
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
    model_year = models.TextField(blank=True)  # This field type is a guess.
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
