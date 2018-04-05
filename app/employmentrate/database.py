###########################################################################
# Modified the table for Employment Rate- Albert Molina 05-04-2018        #
###########################################################################

from flask import g
import sqlite3
import os.path


def connect_db_employment():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, "NSW_EMPLOYMENT_RATE.sqlite")
    sql = sqlite3.connect(db_path)
    #sql = sqlite3.connect('NSW_BIRTH_RATE.sqlite')
    sql.row_factory = sqlite3.Row
    return sql

def get_db_employment():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db_employment()
    return g.sqlite_db
