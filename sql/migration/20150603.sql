# migration 20150603
#
# add fields to saved_query to support recommended query usage
#
# also fix subtle bug where refs get truncated when writing to saved_query
#
# MIGRATION INSTRUCTIONS:
#
# Just run this.

alter table saved_query add column (note      varchar(255));
alter table saved_query add column (status    char(1));
alter table saved_query modify ref varchar(30);
