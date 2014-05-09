#
# schema.sql
#
# This script will create (the latest) schema for a new instance of carsdb.
#
# NOTES:
#
# THIS WILL DESTROY ALL EXISTING VERSIONS OF THESE TABLES, LOSING ALL DATA!!
#
# Reference data population will be in subscripts; this just creates structures.
#
# At this point there is not much need for upgrade scripts; we can
# drop-and-recreate everything easily enough.
#
# When we need to start doing upgrades we will put those in separate scripts.
#
# See git for history.
#
# intended usage:
# 1. create the data (normally named 'carsdb')
# 2. create a user (normally named 'carsdbadmin') and grant them privs
# 3. run this script as that user
# 4. have a separate user (normally named 'carsdbuser') with appropriate
#    privs on all these objects (see grants.sql)
#
# (see also grants.sql)

# TABLES:

# LISTING
#
# this is a first hack at a single-table structure just so we can set up some
# persistence-related features (like identifying new listings, or when to drop
# listings off of a feed)
#
# if we want to be relational, obviously source should be a FK to a site list, etc. That will
# if we are going to pretend to NoSQL this then, well, ...
#
# note also no attempt yet to support deduping
#
# status chars:
# F for sale
# P pending sale
# S sold
# R removed (maybe sold, maybe not)
# T test record, ignore for most cases
#
# for RSS we do not need anything more, I think. If I want to support/track have-seen or sublists for a user
# on the server side then we would need a table that joined a user and listings somehow.
drop table listing;
create table listing (
id	   		 smallint unsigned not null auto_increment,
status		 char(1),
model_year 	 year,
make		 varchar(255),
model 		 varchar(255),
price		 numeric(12,2),
listing_text varchar(2048),
pic_href	 varchar(2048),
listing_href varchar(2048),
source		 varchar(255),
source_id	 varchar(255),
stock_no	 varchar(255),
listing_date DATETIME,
removal_date DATETIME,
last_update  DATETIME,
primary key (id)
);

# MAKE
#
# Canonical list of car makers.
# GEE TODO what about name changes/nicknames/synonyms,
# e.g. GM/GMC or Alfa/Alfa Romeo or Honda/Datsun?
#
drop table make;
create table make(
id                smallint unsigned not null auto_increment,
text_id      	  varchar(255),
canonical_name 	  varchar(255),
first_model_year  number,
last_model_year   number,
acquired_by       number,
last_update       DATETIME,
primary key (id),
key text_id (text_id)
);

# MAKEMODEL
#
# Make & model combos; will have exactly 1 entry for this combination.
# GEE TODO: what about synonyms (e.g. vette/corvette or mx-5/miata)?
#
drop table makemodel;
create table makemodel(
id                      smallint unsigned not null auto_increment,
text_id      	        varchar(255),
make_id                 number,
canonical_model_name    varchar(255),
first_model_year        number,
last_model_year         number,
primary key (id),
key text_id (text_id)
);

# MAKEMODELYEAR
#
# Will contain multiple rows for a given make/model/year combo to reflect
# various trim levels, body styles, etc.
# Initially populated from carqueryapi data but a separate table because
# a) we'll need to merge carqueryapi and other data, so this can be the
# 	 derived merged copy to run from
# b) I'm not in love with the carqueryapi schema and want to isolate us
#
drop table makemodelyear;
create table makemodelyear(
id                smallint unsigned not null auto_increment,
make_id number,
makemodel_id number,
make_text_id varchar(32) NOT NULL,
makemodel_text_id varchar(64) NOT NULL,
model_trim varchar(64) NOT NULL,
model_year int(4) NOT NULL,
model_body varchar(64) DEFAULT NULL,
model_engine_position varchar(8) DEFAULT NULL,
model_engine_cc int(4) DEFAULT NULL,
model_engine_cyl int(1) DEFAULT NULL,
model_engine_type varchar(32) DEFAULT NULL,
model_engine_valves_per_cyl int(2) DEFAULT NULL,
model_engine_power_ps int(2) DEFAULT NULL,
model_engine_power_rpm int(8) DEFAULT NULL,
model_engine_torque_nm int(2) DEFAULT NULL,
model_engine_torque_rpm int(8) DEFAULT NULL,
model_engine_bore_mm decimal(6,1) DEFAULT NULL,
model_engine_stroke_mm decimal(6,1) DEFAULT NULL,
model_engine_compression varchar(8) DEFAULT NULL,
model_engine_fuel varchar(32) DEFAULT NULL,
model_top_speed_kph int(2) DEFAULT NULL,
model_0_to_100_kph decimal(4,1) DEFAULT NULL,
model_drive varchar(16) DEFAULT NULL,
model_transmission_type varchar(32) DEFAULT NULL,
model_seats int(1) DEFAULT NULL,
model_doors int(1) DEFAULT NULL,
model_weight_kg int(2) DEFAULT NULL,
model_length_mm int(2) DEFAULT NULL,
model_width_mm int(2) DEFAULT NULL,
model_height_mm int(2) DEFAULT NULL,
model_wheelbase_mm int(2) DEFAULT NULL,
model_lkm_hwy decimal(4,1) DEFAULT NULL,
model_lkm_mixed decimal(4,1) DEFAULT NULL,
model_lkm_city decimal(4,1) DEFAULT NULL,
model_fuel_cap_l int(2) DEFAULT NULL,
model_sold_in_us tinyint(4) DEFAULT NULL,
model_co2 int(6) DEFAULT NULL,
model_make_display varchar(32) DEFAULT NULL,
primary key (id),
index makemodelyear (make_id, makemodel_id, model_year),
);
