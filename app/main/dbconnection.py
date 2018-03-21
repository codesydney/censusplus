import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager

#schema name in DB
SCHEMA_DATA = "census_2016_data"
SCHEMA_WEB = "census_2016_web"
SCHEMA_BDYS = "census_2016_bdys"
SCHEMA_PUBLIC = "public"

# create database connection pool
'''
pool = ThreadedConnectionPool(
    3, 5,
    database="d1l2hpefphgah3",
    user="zohdghtrwzqtiz",
    password="7b7df36d4c206a3601cbf365ec83462af9118e9abff84d18ab219ca31eb49d57",
    host="ec2-184-72-219-186.compute-1.amazonaws.com",
    port=5432)
'''
pool = ThreadedConnectionPool(
    3, 5,
    database="opend",
    user="postgres",
    password="123456",
    host="localhost",
    port=5432)


@contextmanager
def get_db_connection():
    """
    psycopg2 connection context manager.
    Fetch a connection from the connection pool and release it.
    """
    try:
        connection = pool.getconn()
        yield connection
    finally:
        pool.putconn(connection)

@contextmanager
def get_db_cursor(commit=False):
    """
    psycopg2 connection.cursor context manager.
    Creates a new cursor and closes it, committing changes if specified.
    """
    with get_db_connection() as connection:
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cursor
            if commit:
                connection.commit()
        finally:
            cursor.close()