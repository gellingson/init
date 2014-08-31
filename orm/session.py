#
# for handy use in the repr(), basically.
#

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sqla_db_string = 'mysql+pymysql://{}:{}@{}/{}'.format(os.environ['OGL_DB_USERACCOUNT'],
                                                      os.environ['OGL_DB_USERACCOUNT_PASSWORD'],
                                                      os.environ['OGL_DB_HOST'],
                                                      os.environ['OGL_DB'])
engine = create_engine(sqla_db_string)
Session = sessionmaker(bind=engine)
session = Session()
