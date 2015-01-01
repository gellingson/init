
# test script to play with web.py (and mysql)

import web
import MySQLdb as db
import time

render = web.template.render('templates/')

urls = (
    '/', 'index',
    '/listall', 'list',
    '/testfeed', 'feed'
    )

class index:
    def GET(self):
        name = 'Bob'
        return render.index(name)

    
class list:
    def GET(self):
        date = time.strftime("%a, %d %b %Y %H:%M:%S +0200")
        db = web.database(dbn='mysql', user='carsdbuser', pw='', db='carsdb')
        listings = db.select('listing')

        return render.list(posts=listings, date=date)
    
class feed:
    def GET(self):
        date = time.strftime("%a, %d %b %Y %H:%M:%S +0200")
        db = web.database(dbn='mysql', user='carsdbuser', pw='', db='carsdb')
        listings = db.select('listing')

        web.header('Content-Type', 'application/xml')
        return render.feed(posts=listings, date=date)
    
if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()   

