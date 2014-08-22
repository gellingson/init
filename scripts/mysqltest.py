
# test script to play with mysql

import MySQLdb as db



con = None
try:
    con = db.connect(os.environ['OGL_DB_HOST'],
                     os.environ['OGL_DB_USERACCOUNT'],
                     os.environ['OGL_DB_USERACCOUNT_PASSWORD'],
                     os.environ['OGL_DB'],
                     charset='utf8')
except KeyError:
    print("Please set environment variables for OGL DB connectivity and rerun.")
            sys.exit(1)

with con:
    cur = con.cursor(db.cursors.DictCursor)
    cur.execute("SELECT * FROM listing")
    rows = cur.fetchall()
    for row in rows:
        print row["id"], row["model_year"], row['make']
