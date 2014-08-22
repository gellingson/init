"""
WSGI config for oglweb project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/dev/howto/deployment/wsgi/
"""

# django wants to access the db through mysqldb, so we have to "monkey patch"
# in pymysql as if it were mysqldb.
# GEE question: I don't recall why I needed this under apache wsgi but not
# under the django test web server?
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oglweb.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
