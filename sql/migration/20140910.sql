# migration 20140910
#
# adds anchor column to classified
# adds several new columns to listing
# adds listing_info
#
# MIGRATION INSTRUCTIONS:
#
# Just run this. Moves over anchor values from previous column.

create table listing_sourceinfo(
id	   		   int unsigned not null auto_increment,
source_type    char,
source_id      int unsigned,
local_id       varchar(255),
proc_time      datetime,
listing_id     int unsigned,
entry		   text,
detail_enc     char,
detail_html    text,
primary key (id),
foreign key (listing_id) references listing(id),
index (source_type, source_id, proc_time)
);

alter table classified add (anchor varchar(1024));

update classified set anchor = extract_car_list_func;

alter table listing add (
location_text  varchar(50),
zip            varchar(10),
source         varchar(50),
color          varchar(20),
int_color      varchar(20),
vin            varchar(20),
mileage        int unsigned
);

alter table zipcode drop index states;

alter table zipcode add index statecityidx(state_code, city_upper);
