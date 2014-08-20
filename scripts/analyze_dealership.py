#!/usr/local/bin/python3
#
# analyze_dealership.py
#
# analyzes a dealership website and/or specific inventory page
#
# for a dealership it tries to ID an inventory page, then analyze it
# if passed a specific inventory URL it analyzes its contents
#
# this is intended as a tool to allow a human to quickly set up
# automated imports of the dealership inventory. It is not YET a
# completely automated pull.
#
# NOTES:
# pulled this stuff out of the main import.this is the main import package

# builtin modules used
import sys
import argparse
import re
import json
import urllib.request, urllib.error, urllib.parse
import os
import errno
import logging

# third party modules used
from bunch import Bunch
from bs4 import BeautifulSoup

# OGL modules used

# consider this script to be internal to inventory.importer module
from inventory.importer import *


def check_page(url):


    return True


# ============================================================================
# MAIN
# ============================================================================

def process_command_line():
    # initialize the parser object:
    parser = argparse.ArgumentParser(description='Imports car listings')
    parser.add_argument('--log_level', default='INFO',
                        choices=('DEBUG','INFO','WARNING','ERROR', 'CRITICAL'),
                        help='set the logging level')
    parser.add_argument('action',
                        choices=('site','page'),
                        help='site: check site; page: check specific page')
    parser.add_argument('sources', nargs='*', help='the source(s) to take action on')

    return parser.parse_args()


def main():
    args = process_command_line()

    # start logging
    logging.basicConfig(level=args.log_level.upper())

    # now do what the user requested (the action)
    if args.action == 'page':
        for source in args.sources:
            check_page(source)

    return True
    
if __name__ == "__main__":
    status = main()
    sys.exit(status)
