# migration 20141227
#
# add keep_days column to classified table
#
# MIGRATION INSTRUCTIONS:
#
# Just run this.

alter table classified add column (keep_days int);
update classified set keep_days = 21 where textid in ('autod', 'carsd');
update classified set keep_days = 31 where textid = 'hmngs';
update classified set keep_days = 14 where textid = 'craig';

alter table saved_query add column (params    varchar(2048));
