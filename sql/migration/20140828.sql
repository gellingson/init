# migration 20140828
#
# adds tags column to listings
#
# MIGRATION INSTRUCTIONS:
#
# Just run this. Code will add tags over time.

alter table listing add (tags varchar(2048));
