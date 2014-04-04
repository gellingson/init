
# test script to play with web.py (withOUT mysql)

import web

urls = (
    '/', 'index',
    '/testfeed', 'feed'
    )

class index:
    def GET(self):
        return "Hello, world!"

if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()   

