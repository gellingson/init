#
# grants.sql
#
# This script has the create user & grant statements to set up two users:
# 	   carsdbadmin: owner of the carsdb schema
#	   carsdbuser:  user the app runs under
#
# NOTES:
#
# NOTES:
# mysql/mariadb gives a counterintuitive "0 rows updated" message after
# each grant statement. Ignore that; it's (probably) working.
#
# Note the seeming overreach of granting *.* to carsdbadmin. We should be
# able to grant carsdb.* but that doesn't seem to grant create privileges...
# can't find a syntax for granting db-level privs :(
#
# Not sure about the sequencing of these grants and ensuring carsdbuser
# will get privs on all the tables. Rinse and repeat as neccessary, or
# rejigger this.
#
# This script contains dummy passwords appropriate only for a local dev db.
# Modify for any important, production or publically-reachable instance!
#
# You will need to run this script as root (or a similarly-priv'd user).
#
# See git for history.

create user 'carsdbadmin' identified by 'carsdbowner';

grant all privileges on *.* to carsdbadmin@localhost;

create user 'carsdbuser' identified by 'carsdbusage';

grant select, insert, update, delete on carsdb.* to carsdbuser@localhost;

