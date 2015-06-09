# migration 20150609
#
# add new table query_list (stores sets of saved queries)
#
# MIGRATION INSTRUCTIONS:
#
# Just run this.

create table query_list(
id        int unsigned not null auto_increment,
list_ref  varchar(30) not null,
seq       int unsigned,
query_id  int unsigned not null,
primary key (id),
index listidx(list_ref),
foreign key (query_id) references saved_query(id));
