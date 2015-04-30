# migration 20150320
#
# allow longer colors (e.g. Liquid Silver Metallic)
#
# MIGRATION INSTRUCTIONS:
#
# Just run this.

alter table listing
modify column color varchar(30),
modify column int_color varchar(30);

# table for more listing info. Will have 0-1 rows per listing
create table listing_extras (
id            int unsigned not null auto_increment,
listing_id    int unsigned,
pics          text,
raw_fields    text,
useful_fields text,
raw_texts     text,
useful_texts  text,
primary key   id,
foreign key   (listing_id) references listing(id)
);
