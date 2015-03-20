# migration 20150304
#
# add static_quality column to listing table
#
# MIGRATION INSTRUCTIONS:
#
# Just run this.

alter table listing add column (static_quality int);
