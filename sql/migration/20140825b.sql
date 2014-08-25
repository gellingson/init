# migration 20140825
#
# switches phone to text (int is not big enough)
# adds the zip code table and lat/lon fields to relevant tables.
# populates the dealership lat/lon from the zip code where we have one.
#
# NOT creating the zip code table because it will be either
# a) formed from schema.sql or
# b) formed when copying over the populated zipcode table
#
# NOT populating the zip codes; see the zipsilver dir for that.
#
# MIGRATION INSTRUCTIONS:
#
# 1. create zipcode table
# 	 in mysql, dir=init/sql: source migration/20130825a.sql
# 2. import zipcodes
# 	 in shell, dir=init/sql/zipsilver: python3 zip_import.py
# 3. alter tables & run various updates
# 	 in mysql, dir=init/sql: source migration/20130825b.sql [this script]
#

alter table dealership modify phone varchar(30);
alter table dealership add (lat decimal(10,7), lon decimal(10,7));
alter table listing add (lat decimal(10,7), lon decimal(10,7));

update dealership d, zipcode z set d.lat = z.lat, d.lon = z.lon where z.zip = d.zip and d.zip is not null and (d.lat is null or d.lon is null);

# catch up listings to have the id linkages to dealerships/classifieds
# (may not already be reliably id linked b/c we have been using the textid links)
update listing l, dealership d set l.source_type = 'D', l.source_id = d.id where l.source_textid = d.textid and l.source_id is null;
update listing l, classified c set l.source_type = 'C', l.source_id = c.id where l.source_textid = c.textid and l.source_id is null;

# then update the dealership-based listings to location of the dealership
update listing l, dealership d set l.lat = d.lat, l.lon = d.lon where l.source_type = 'D' and (l.lat is null or l.lon is null) and l.source_id = d.id and (d.lat is not null or d.lon is not null);

# cannot update classified listings because we have not been populating any location info as we pulled listings
