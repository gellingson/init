#
# schema.sql
#
# This script will create (the latest) schema for a new instance of carsdb.
#
# NOTES:
#
# THIS WILL DESTROY ALL EXISTING VERSIONS OF THESE TABLES, LOSING ALL DATA!!
#
# (well actually, we move the current tables to _backup versions, but we
# overwrite the backups, so... do it 2x and all is lost!)
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
# has both id and textid for source (text) for now since our tables of sources
# may not be complete yet
#
# note also no real attempt yet to support deduping
#
# status chars:
# F for sale
# P pending sale
# S sold
# R removed (maybe sold, maybe not)
# T test record, ignore for most cases
# X removed, not a valid listing [generally means admin-flagged as importing script error, fraud, etc]
#
# markers chars:
#
# P pending deletion (used during reconciliation of existing and current listing sets for a source)
#
# for RSS we do not need anything more, I think. If I want to support/track have-seen or sublists for a user
# on the server side then we would need a table that joined a user and listings somehow.
drop table listing_backup;
rename table listing to listing_backup;
create table listing (
id	   		   int unsigned not null auto_increment,
markers        varchar(24),
status		   char(1) NOT NULL,
model_year 	   varchar(4),
make		   varchar(255),
model 		   varchar(255),
price		   int,
listing_text   varchar(2048),
pic_href	   varchar(2048),
listing_href   varchar(2048),
source_type    char,
source_id	   int,
source_textid  varchar(255),
local_id	   varchar(255),
stock_no	   varchar(255),
listing_date   DATETIME,
removal_date   DATETIME,
last_update    DATETIME,
primary key (id)
);

# MAKE
#
# Canonical list of car makers.
# GEE TODO what about name changes/nicknames/synonyms,
# e.g. GM/GMC or Alfa/Alfa Romeo or Honda/Datsun?
#
drop table make_backup;
rename table make to make_backup;
create table make(
id                int unsigned not null auto_increment,
text_id      	  varchar(255),
canonical_name 	  varchar(255),
first_model_year  int(4),
last_model_year   int(4),
acquired_by       int(4),
last_update       DATETIME,
primary key (id),
key text_id (text_id)
);

# MAKEMODEL
#
# Make & model combos; will have exactly 1 entry for this combination.
# GEE TODO: what about synonyms (e.g. vette/corvette or mx-5/miata)?
#
drop table makemodel_backup;
rename table makemodel to makemodel_backup;
create table makemodel(
id                      int unsigned not null auto_increment,
text_id      	        varchar(255),
make_id                 int,
canonical_model_name    varchar(255),
first_model_year        int(4),
last_model_year         int(4),
last_update       DATETIME,
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
drop table makemodelyear_backup;
rename table makemodelyear to makemodelyear_backup;
create table makemodelyear(
id                int unsigned not null auto_increment,
make_id int,
makemodel_id int,
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
index makemodelyear (make_id, makemodel_id, model_year)
);

# DEALERSHIP
#
#
#
# statuses: (hmm, I need some sort of DO layer!)
#
# I ACTIVE & INDEXING (open; not known to be out of business)
# A ALIVE (we think) but NOT indexing for some reason, possibly temporary
# D DEAD (out of business, we think)
# E EVIL (flagged as not a place to do business with)
#
# Markers (e.g. inventory types) (can have multiple letters as appropriate):
# S SPECIALTY (commonly carries classic, exotic, or other unique inventory)
# C CLASSIC
# X EXOTIC
# H High listing quality
# L Low listing quality
# I high Integrity/quality dealership
# Y shadY seeming dealership

# TODO: denormalize last_import?

drop table dealership_backup;
rename table dealership to dealership_backup;
create table dealership(
id                int unsigned not null auto_increment,
status           char(1) not null,
markers          varchar(24),
primary_dealership_id int default NULL,
textid varchar(32) NOT NULL,
full_name varchar(1024) NOT NULL,
base_url varchar(1024),
extract_car_list_func varchar(1024),
listing_from_list_item_func varchar(1024),
parse_listing_func varchar(1024),
inventory_url varchar(1024),
address_line1 varchar(255),
address_line2 varchar(255),
city varchar(255),
state varchar(255),
zip varchar(255),
phone int(15),
owner_info varchar(255),
license_info varchar(255),
owner_account_id int,
primary key (id)
);

drop table classified_backup;
rename table classified to classified_backup;
create table classified(
id                int unsigned not null auto_increment,
status           char(1) not null,
markers          varchar(24),
primary_classified_id int default NULL,
textid varchar(32) NOT NULL,
full_name varchar(1024) NOT NULL,
base_url varchar(1024),
custom_pull_func varchar(1024),
extract_car_list_func varchar(1024),
listing_from_list_item_func varchar(1024),
parse_listing_func varchar(1024),
inventory_url varchar(1024),
owner_account_id int,
primary key (id)
);

drop table dealership_activity_log_backup;
rename table dealership_activity_log to dealership_activity_log_backup;
create table dealership_activity_log(
id                int unsigned not null auto_increment,
dealership_id int,
activity_timpestamp datetime,
action_code varchar(32),
message varchar(1024),
primary key (id)
);


# source_type has values [d=dealership, c=classified, ...?]
drop table inventory_import_log_backup;
rename table inventory_import_log to inventory_import_log_backup;
create table inventory_import_log(
id                int unsigned not null auto_increment,
source_type  char(1),
source_id    int,
import_timestamp datetime,
message varchar(1024),
primary key (id)
);

# non_canonical_make
#
# if we see make.upper() = non_canonical_name, replace with
# canonical_name, and
# - consume any following words in the consume_words string if they lead the presumed-model string
#      for example: if "alfa" [canonical Alfa Romeo] consume "romeo"
# - push any words in the push_words onto the front of hte presumed-model string
#      for example: if "vette" [canonical Chevrolet] push "corvette"
drop table non_canonical_make_backup;
rename table non_canonical_make to non_canonical_make_backup;
create table non_canonical_make(
id                int unsigned not null auto_increment,
non_canonical_name  varchar(1024),
canonical_name		varchar(1024),
consume_words		varchar(1024),
push_words			varchar(1024),
primary key (id),
index ncn(non_canonical_name));
