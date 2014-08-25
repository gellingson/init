# migration 20140825a [step 1 of 3]
#
# creates the zipcode table
#
# EMPTY SCRIPT because it is easier to copy from an existing stage
# (or run the schema script to create everything)
#
# MIGRATION INSTRUCTIONS:
#
# 1. create zipcode table [this script, but DOES NOTHING - use mysqldump instead]
# 	 in mysql, dir=init/sql: source migration/20130825a.sql
# 2. import zipcodes
# 	 in shell, dir=init/sql/zipsilver: python3 zip_import.py
# 3. alter tables & run various updates
# 	 in mysql, dir=init/sql: source migration/20130825b.sql
#
