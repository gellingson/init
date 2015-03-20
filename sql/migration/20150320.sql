# migration 20150320
#
# add score_adjustment column to classified & dealership tables
#
# MIGRATION INSTRUCTIONS:
#
# Just run this.

alter table classified add column (score_adjustment int);
alter table dealership add column (score_adjustment int);

