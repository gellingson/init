# migration 20141023
#
# add saved_query table
#
# MIGRATION INSTRUCTIONS:
#
# Just run this.

create table saved_query(
id        int unsigned not null auto_increment,
querytype char(1) not null,
user_id   int,
ref       varchar(24),
descr     varchar(80),
query     varchar(2048),
mark_date datetime,
primary key (id),
unique index (user_id, ref),
foreign key (user_id) references auth_user(id));

create table saved_listing(
id        int unsigned not null auto_increment,
user_id   int,
listing_id int unsigned,
status    char(1) NOT NULL,
note      varchar(2048),
primary key (id),
unique index (user_id, listing_id),
foreign key (user_id) references auth_user(id),
foreign key (listing_id) references listing(id)
);

create table action_log(
id                int unsigned not null auto_increment,
user_id           int,
listing_id        int unsigned,
action            char(1) not null,
reason            varchar(255),
adjustment        int,
action_timestamp  datetime not null,
primary key (id),
index (user_id, listing_id),
index (listing_id),
foreign key (user_id) references auth_user(id),
foreign key (listing_id) references listing(id));

alter table listing add column (dynamic_quality integer);

