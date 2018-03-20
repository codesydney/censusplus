###########################################################################
# Modified the table for Employment Rate- Albert Molina 13-03-2018        #
###########################################################################

from flask import g
import sqlite3

def connect_db():
    sql = sqlite3.connect('NSW_EMPLOYMENT_RATE.sqlite')
    sql.row_factory = sqlite3.Row
    return sql

def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db