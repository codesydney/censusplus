from flask import render_template, flash, redirect, request, url_for, jsonify, Response, current_app 
from app import bootstrap, arguments #,db
from . import main 
#from .models import nsw_addresses
from .forms import MainForm, TryAgainForm
#from .mapfuncs import get_boundary
import json
import urllib.request
from app.population import views as population_views
from app.birthrate import views as birthrate_views
#from sqlalchemy import text


from datetime import datetime
import ast
import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extensions import AsIs
from contextlib import contextmanager

import operator
import re
from datetime import datetime

#schema name in DB
SCHEMA_DATA = "census_2016_data"
SCHEMA_WEB = "census_2016_web"
SCHEMA_BDYS = "census_2016_bdys"
SCHEMA_PUBLIC = "public"

# create database connection pool

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
'''
# get the boundary name that suits each (tiled map) zoom level and its minimum value to colour in
def get_boundary(zoom_level):

    '''
    if zoom_level < 7:
        boundary_name = "ste"
        min_display_value = 2025
    elif zoom_level < 9:
        boundary_name = "sa4"
        min_display_value = 675
    elif zoom_level < 11:
        boundary_name = "sa3"
        min_display_value = 225
    elif zoom_level < 14:
        boundary_name = "sa2"
        min_display_value = 75
    elif zoom_level < 17:
        boundary_name = "sa1"
        min_display_value = 25
    else:
        boundary_name = "mb"
        min_display_value = 5

    return boundary_name, min_display_value
    '''

    #BinLiu: alway show suburb boundary.
    return "ssc",5

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

#########################################
## The above codes are for maps
#########################################

@main.route('/', methods=['GET', 'POST'])
@main.route('/index', methods=['GET', 'POST'])
def index():
    #print("==>main/views.py::index: enter")
    form = MainForm()
    tryagainform = TryAgainForm()
    
    if form.validate_on_submit() and form.Submit1.data:
        InputAddress = form.InputAddress.data

        #************* Get the suburb name and mb code of the chosen address ****************** 
        with get_db_cursor() as pg_cur:

            sql_template = "SELECT add.locality_name, add.mb_2016_code " \
                "from {0}.nsw_addresses as add " \
                "where add.address = '%s' " \
                .format('public')
            sql = pg_cur.mogrify(sql_template, (AsIs(InputAddress),))            

            print("views.py::index line 120: ",end=' ')
            print(sql)

            try:
                pg_cur.execute(sql)
            except psycopg2.Error:
                return "I can't SELECT:<br/><br/>" + sql

            rows = pg_cur.fetchall()

            #if there is no address in table matched this input value.
            if not rows:
                print("views.py::index: The result of address is empty")
                return render_template('mainform.html', form=tryagainform)

            for row in rows:
                InputSuburb = row['locality_name']
                mb_2016_code = row['mb_2016_code']

            #get ssc code from mb code
            #I seperate this query from the above one 
            #because different year may have different correspondence between suburb and other area.
            sql_template = "SELECT ms.ssc_code " \
                "from {0}.mb_ssc_2016 as ms " \
                "where mb_code_2016 = ( '%s') " \
                .format('public')
            sql = pg_cur.mogrify(sql_template, (AsIs(mb_2016_code),))            

            print("views.py::index line 154: ",end=' ')
            print(sql)

            try:
                pg_cur.execute(sql)
            except psycopg2.Error:
                return "I can't SELECT:<br/><br/>" + sql

            rows = pg_cur.fetchall()

            #if there is no address in table matched this input value.
            if not rows:
                print("views.py::index: The result of address is empty")
                return render_template('mainform.html', form=tryagainform)

            for row in rows:
                InputSSC = row['ssc_code']

        print("view.py::index: InputSSC = "+InputSSC)

        result_data = get_result_data(InputSSC, InputSuburb);

        return render_template('result.html',
                                #resultform=resultform,
                                InputSuburb=InputSuburb,
                                #birth_rate_list=birth_rate_list,
                                #population_list=population_list,
                                mb_2016_code=mb_2016_code,
                                InputSSC=InputSSC,
                                result_data=result_data,
                                mapstats="g1")                             
                                
    #elif resultform.validate_on_submit() and resultform.Submit2.data:   
         #return redirect(url_for('main.index'))
    else:       
        return render_template('mainform.html',
                                form=form)


def get_result_data(InputSSC, InputSuburb):
    """get different census data from db.
    """
    result_data = [];

    #with db.engine as pg_cur:
    with get_db_cursor() as pg_cur:

        search_stats_tuple = tuple(["G"+str(no) for no in range(1,10)]) 
        #the max value can be set up to 109. They are all in table: census_2016_data.ccs_g1
        print ("views.py::get_result_data: search_stats_tuple = ",search_stats_tuple);

        sql_template = "SELECT sequential_id AS id, " \
              "lower(table_number) AS \"table\", " \
              "replace(long_id, '_', ' ') AS description, " \
              "column_heading_description AS type, " \
              "'values' as maptype " \
              "FROM {0}.metadata_stats " \
              "WHERE sequential_id IN %s " \
              "ORDER BY sequential_id".format('census_2016_data')

        sql = pg_cur.mogrify(sql_template, (AsIs(search_stats_tuple),)) 

        print("===>views.py::get_result_data: sql:", sql)
    
        try:
            #pg_cur.execute(sql, (search_stats_tuple,))
            pg_cur.execute(sql)
        except psycopg2.Error:
            return "I can't SELECT:<br/><br/>" + sql

        # Retrieve the results of the query
        rows = pg_cur.fetchall()
    

    #rows = db.engine.execute(sql)    

    # output is the main content, row_output is the content from each record returned
    response_dict = []

    # For each row returned assemble a dictionary
    #no = 1;
    for row in rows:
        feature_dict = dict(row)
        #no%5 determine the colour of panel head in result page.
        feature_dict["no"] = int(re.sub("[A-Za-z]","",feature_dict["id"]))
        feature_dict["id"] = feature_dict["id"].lower()
        feature_dict["table"] = feature_dict["table"].lower()
        #print(feature_dict)
        # add dict to output array of metadata
        response_dict.append(feature_dict)
        #no += 1

    # output_array.append(output_dict)

    # print("Got metadata for {0} in {1}".format(boundary_name, datetime.now() - start_time))

    # # Assemble the JSON
    # response_dict["boundaries"] = output_array

    #sort response_dict by id: g1~g108
    response_dict.sort(key=operator.itemgetter('no'))
    print("views:py::get_result_data: response_dict = ",response_dict)


    #get values of census item from g1 to g108
    with get_db_cursor() as pg_cur:

        search_stats_tuple = tuple(["G"+str(no) for no in range(1,10)]) 
        #the max value can be set up to 109. They are all in table: census_2016_data.ccs_g1
        print ("views.py::get_result_data: search_stats_tuple = ",search_stats_tuple);

        #hardcode
        sql_template2 = "SELECT tab.g1, tab.g2, tab.g3, tab.g4, tab.g5, tab.g6, tab.g7, tab.g8, tab.g9 " \
              "FROM {0}.%s_%s AS tab " \
              "WHERE tab.region_id = '%s'" \
              .format('census_2016_data')
        #print("==>main/views.py::get_data: enter line 389")

        sql2 = pg_cur.mogrify(sql_template2, (AsIs("ssc"), AsIs("g01"), AsIs(InputSSC)))
        #hardcode
        

        print("===>views.py::get_result_metadata: sql2:", sql2)
    
        try:
            pg_cur.execute(sql2)
        except psycopg2.Error:
            return "I can't SELECT:<br/><br/>" + sql2

        # Retrieve the results of the query
        value_row = pg_cur.fetchone()
    
        value_dict = dict(value_row);
        print("views.py::get_result_metadata the result of sql2:",value_dict)

        for response_item in response_dict:
            if response_item["no"]<=9: #now only get the first 9 items. 9 is hardcode
               for key, value in value_dict.items():
                    if key == response_item["id"]:
                        response_item["value"] = int(value)
                        response_item["suburb"] = InputSuburb
                        response_item["year"] = "2016"

    return response_dict;

@main.route('/autocomplete', methods=['GET'])
def autocomplete():
    search = request.args.get('q')
    with get_db_cursor() as pg_cur:

        sql_template = "SELECT nsw_addresses.address " \
            "from {0}.nsw_addresses " \
            "where tsv_address @@ plainto_tsquery('%s') " \
            "limit 5 ".format('public')
        sql = pg_cur.mogrify(sql_template, (AsIs(search),))            

        print("views.py::autocomplete: ",end=' ')
        print(sql)

        try:
            pg_cur.execute(sql)
        except psycopg2.Error:
            return "I can't SELECT:<br/><br/>" + sql

        # Retrieve the results of the query
        rows = pg_cur.fetchall()

    addresslist = []
    for row in rows:
        addresslist.append(row['address'])
    return jsonify(matching_results=addresslist)


@main.route('/about', methods=['GET'])
def about():
    """about page
    """
    return render_template('about.html');


#######################################
# the following is for showing the map
#######################################
@main.route("/get-bdy-names")
def get_boundary_name():
    # Get parameters from querystring
    min_val = int(request.args.get('min'))
    max_val = int(request.args.get('max'))

    boundary_zoom_dict = dict()

    for zoom_level in range(min_val, max_val + 1):
        boundary_dict = dict()
        boundary_dict["name"], boundary_dict["min"] = get_boundary(zoom_level)
        boundary_zoom_dict["{0}".format(zoom_level)] = boundary_dict

    return Response(json.dumps(boundary_zoom_dict), mimetype='application/json')


@main.route("/get-metadata")
def get_metadata():
    full_start_time = datetime.now()
    # start_time = datetime.now()

    # Get parameters from querystring

    # # census year
    # census_year = request.args.get('c')

    # comma separated list of stat ids (i.e. sequential_ids) AND/OR equations contains stat ids
    raw_stats = request.args.get('stats').upper()
    searchStatsStr = "'"+raw_stats+"'"
    search_stats = raw_stats.upper().split(",")

    
    # get number of map classes
    try:
        num_classes = int(request.args.get('n'))
    except TypeError:
        num_classes = 7
    '''
    # replace all maths operators to get list of all the stats we need to query for
    search_stats = raw_stats.upper().replace(" ", "").replace("(", "").replace(")", "") \
        .replace("+", ",").replace("-", ",").replace("/", ",").replace("*", ",").split(",")

    # TODO: add support for numbers in equations - need to strip them from search_stats list

    # equation_stats = raw_stats.lower().split(",")

    # print(equation_stats)
    # print(search_stats)
    '''
    # get stats tuple for query input (convert to lower case)
    search_stats_tuple = tuple([stat for stat in search_stats])

    '''
    # get all boundary names in all zoom levels
    boundary_names = list()
    test_names = list()

    for zoom_level in range(0, 16):
        bdy_name, min_val = get_boundary(zoom_level)

        # only add if bdy not in list
        if bdy_name not in test_names:
            bdy_dict = dict()
            bdy_dict["name"] = bdy_name
            bdy_dict["min"] = min_val
            boundary_names.append(bdy_dict)

            test_names.append(bdy_name)
    '''

    # get stats metadata, including the all important table number and map type (raw values based or normalised by pop)
    sql = "SELECT sequential_id AS id, " \
          "lower(table_number) AS \"table\", " \
          "replace(long_id, '_', ' ') AS description, " \
          "column_heading_description AS type, " \
          "'values' as maptype " \
          "FROM {0}.metadata_stats " \
          "WHERE sequential_id IN %s " \
          "ORDER BY sequential_id".format('census_2016_data')

    print("===>views.py::get_metadata: ",raw_stats)
    print(sql)
    
    #with db.engine as pg_cur:
    with get_db_cursor() as pg_cur:
        try:
            #pg_cur.execute(sql, (search_stats_tuple,))
            pg_cur.execute(sql, (search_stats_tuple,))
        except psycopg2.Error:
            return "I can't SELECT:<br/><br/>" + sql

        # Retrieve the results of the query
        rows = pg_cur.fetchall()
    

    #rows = db.engine.execute(sql)    

    # output is the main content, row_output is the content from each record returned
    response_dict = dict()
    response_dict["type"] = "StatsCollection"
    response_dict["classes"] = num_classes

    feature_array = list()

    # For each row returned assemble a dictionary
    for row in rows:
        feature_dict = dict(row)
        feature_dict["id"] = feature_dict["id"].lower()
        feature_dict["table"] = feature_dict["table"].lower()
        #print(feature_dict)
        # add dict to output array of metadata
        feature_array.append(feature_dict)

    response_dict["stats"] = feature_array
    print(response_dict)
    # output_array.append(output_dict)

    # print("Got metadata for {0} in {1}".format(boundary_name, datetime.now() - start_time))

    # # Assemble the JSON
    # response_dict["boundaries"] = output_array

    print("Returned metadata in {0}".format(datetime.now() - full_start_time))

    return Response(json.dumps(response_dict), mimetype='application/json')


@main.route("/get-data")
def get_data():

    full_start_time = datetime.now()
    # start_time = datetime.now()

    # # Get parameters from querystring
    # census_year = request.args.get('c')

    map_left = request.args.get('ml')
    map_bottom = request.args.get('mb')
    map_right = request.args.get('mr')
    map_top = request.args.get('mt')

    stat_id = request.args.get('s')
    table_id = request.args.get('t')
    boundary_name = request.args.get('b')
    zoom_level = int(request.args.get('z'))
    InputSSC = request.args.get('InputSSC')
    #print("==>main/views.py::get_data: enter InputSSC="+InputSSC)

    # TODO: add support for equations

    # get the boundary table name from zoom level
    if boundary_name is None:
        boundary_name, min_val = get_boundary(zoom_level)

    display_zoom = str(zoom_level).zfill(2)
    #print("==>main/views.py::get_data: enter line 361")
    with get_db_cursor() as pg_cur:
        # print("Connected to database in {0}".format(datetime.now() - start_time))
        # start_time = datetime.now()

        # build SQL with SQL injection protection
        # yes, this is ridiculous - if someone can find a shorthand way of doing this then fire up the pull requests!
        '''
        sql_template = "SELECT bdy.id, bdy.name, bdy.population, tab.%s / bdy.area AS density, " \
              "CASE WHEN bdy.population > 0 THEN tab.%s / bdy.population * 100.0 ELSE 0 END AS percent, " \
              "tab.%s, geojson_%s AS geometry " \
              "FROM {0}.%s AS bdy " \
              "INNER JOIN {1}.%s_%s AS tab ON bdy.id = tab.{2} " \
              "WHERE bdy.geom && ST_MakeEnvelope(%s, %s, %s, %s, 4283)" \
              .format(settings['web_schema'], settings['data_schema'], settings['region_id_field'])

        sql = pg_cur.mogrify(sql_template, (AsIs(stat_id), AsIs(stat_id), AsIs(stat_id), AsIs(display_zoom),
                                            AsIs(boundary_name), AsIs(boundary_name), AsIs(table_id), AsIs(map_left),
                                            AsIs(map_bottom), AsIs(map_right), AsIs(map_top)))
        '''
        #print("==>main/views.py::get_data: enter line 381")
        sql_template = "SELECT bdy.id, bdy.name, bdy.population, tab.%s / bdy.area AS density, " \
              "CASE WHEN bdy.population > 0 THEN tab.%s / bdy.population * 100.0 ELSE 0 END AS percent, " \
              "tab.%s, geojson_%s AS geometry " \
              "FROM {0}.%s AS bdy " \
              "INNER JOIN {1}.%s_%s AS tab ON bdy.id = tab.{2} " \
              "WHERE bdy.id = '%s'" \
              .format('census_2016_web', 'census_2016_data', "region_id")
        #print("==>main/views.py::get_data: enter line 389")

        sql = pg_cur.mogrify(sql_template, (AsIs(stat_id), AsIs(stat_id), AsIs(stat_id), AsIs(display_zoom),
                                            AsIs(boundary_name), AsIs(boundary_name), AsIs(table_id), AsIs(InputSSC)))

        print("views.py::get_data: ",end=' ')
        print(sql)
        try:
            pg_cur.execute(sql)
        except psycopg2.Error:
            return "I can't SELECT:<br/><br/>" + str(sql)

        # Retrieve the results of the query
        rows = pg_cur.fetchall()

        # Get the column names returned
        col_names = [desc[0] for desc in pg_cur.description]

    # print("Got records from Postgres in {0}".format(datetime.now() - start_time))
    # start_time = datetime.now()

    # output is the main content, row_output is the content from each record returned
    output_dict = dict()
    output_dict["type"] = "FeatureCollection"

    i = 0
    feature_array = list()

    # For each row returned...
    for row in rows:
        feature_dict = dict()
        feature_dict["type"] = "Feature"

        properties_dict = dict()

        # For each field returned, assemble the feature and properties dictionaries
        for col in col_names:
            if col == 'geometry':
                feature_dict["geometry"] = ast.literal_eval(str(row[col]))
            elif col == 'id':
                feature_dict["id"] = row[col]
            else:
                properties_dict[col] = row[col]

        feature_dict["properties"] = properties_dict

        feature_array.append(feature_dict)

        # start over
        i += 1

    # Assemble the GeoJSON
    output_dict["features"] = feature_array
    #print("view.py::get_data",output_dict);

    # print("Parsed records into JSON in {1}".format(i, datetime.now() - start_time))
    print("get-data: returned {0} records  {1}".format(i, datetime.now() - full_start_time))

    return Response(json.dumps(output_dict), mimetype='application/json')

#########################################
## The above codes are for maps
#########################################