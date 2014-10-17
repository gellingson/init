#!/usr/bin/env python3
# GEE monkeypatch swapping pymysql in for mysqldb (since pymysql works with python3)
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oglweb.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
