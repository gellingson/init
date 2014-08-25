import os
import pymysql as db

con = db.connect(os.environ['OGL_DB_HOST'],
                 os.environ['OGL_DB_USERACCOUNT'],
                 os.environ['OGL_DB_USERACCOUNT_PASSWORD'],
                 os.environ['OGL_DB'],
                 charset='utf8')
ins = con.cursor(db.cursors.DictCursor)

with open("ZIPSILVER.txt") as f:
    for line in f:
        if line[0] != 'Z': # header
            fields = line.split(',')
            ins.execute("""insert into zipcode values (%s, %s, %s, %s, '', '', %s, %s, %s, %s)""",
                        fields)

con.commit()
