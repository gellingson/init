#!/usr/bin/env python3
#
# logtest.py
#
# moving logging setup code out of importer.py so I can monkey around
# with it easily without breaking stuff

import logging
import os
import sys

LOG = logging.getLogger(__name__)  # will configure further in main()

FOO = "hi"

def main():
    global FOO
    FOO = "there"
    # start logging: config the local __name__ logger
    formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
    fh = None
    try:
        fh = logging.FileHandler(os.path.join(os.environ.get('OGL_LOGDIR',
                                                             '/tmp'),
                                              'testlog'))
    except:
        print("HEY, CREATING THE FH FAILED")
        fh = logging.StreamHandler()  # fall back to stderr
    fh.setFormatter(formatter)
    LOG.addHandler(fh)
    LOG.setLevel('INFO')
    
    # the following code attempts to modify the elasticsearch logger;
    # note that the technique works, BUT the msg string is built
    # dynamically from args, SO without dipping into testing the
    # contents of args params we can't actually filter on strings like
    # "404" or "DELETE" -- so it's possible but annoyingly hard to
    # suppress a particular message
    es_filter = logging.Filter()
    def filter_404s(record):
        print("MESSAGE IS:" + record.msg)
        if "404" in record.msg:
            return 0
        return 1
    es_filter.filter = filter_404s
    es_logger = logging.getLogger('elasticsearch')
    es_logger.addFilter(es_filter)
    es_logger.setLevel('INFO')
    es_logger.addHandler(fh)
    es_logger.info("hi there")

    LOG.info("hi there via LOG")
    es_logger.info("hi there 404")
    LOG.info("hi there 404 via LOG")
    
    LOG.info('fubar barfu')
    LOG.debug('fubar barfu-debug')
    LOG.warn('fubar barfu-warn')
    LOG.warn('fubar barfu-warn 404 message')

    foo()


def foo():
    LOG.info("doing foo")
    LOG.info(FOO)


if __name__ == "__main__":
    status = main()
    sys.exit(status)
