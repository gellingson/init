
# test script to play with mysql

import MySQLdb as db



con = db.connect('localhost', 'carsdbuser', 'car4U', 'carsdb')

with con:
    cur = con.cursor(db.cursors.DictCursor)
    cur.execute("SELECT * FROM listing")
    rows = cur.fetchall()
    for row in rows:
        print row["id"], row["model_year"], row['make']
