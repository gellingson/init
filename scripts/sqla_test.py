#!/usr/local/bin/python3

from orm.models import Classified
from orm.session import session

c = session.query(Classified).get(3)
print(c)
