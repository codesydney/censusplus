from flask import render_template, flash, redirect, request, url_for, jsonify, Response, current_app 
from app import bootstrap, arguments #,db

from . import main 
from .forms import MainForm, TryAgainForm
from .dbconnection import get_db_connection, get_db_cursor
from .getpopulationdata import get_population_data

import json
import urllib.request
from datetime import datetime
import ast
import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extensions import AsIs
from contextlib import contextmanager

#import operator
#import re
#from datetime import datetime



#########################################
## The above codes are for maps
#########################################

@main.route('/', methods=['GET', 'POST'])
@main.route('/index', methods=['GET', 'POST'])
def index():
    #print("==>main/views.py::index: enter")
    form = MainForm()
    tryagainform = TryAgainForm()
    
    #render the result page
    if form.validate_on_submit() and form.Submit1.data:
        InputAddress = form.InputAddress.data

        #Get the suburb name and mb code of the chosen address
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
                input_suburb = row['locality_name']
                mb_2016_code = row['mb_2016_code']

            #get ssc code from mb code
            #I seperate this query from the above one 
            #because different year may have different correspondence between suburb and other area.
            # sql_template = "SELECT ms.ssc_code " \
            #     "from {0}.mb_ssc_2016 as ms " \
            #     "where mb_code_2016 = ( '%s') " \
            #     .format('public')
            # sql = pg_cur.mogrify(sql_template, (AsIs(mb_2016_code),))            

            sql_template = "SELECT ms.ssc_code, ST_X(st_centroid(bdy.geom)) as lng, " \
                "ST_Y(st_centroid(bdy.geom)) as lat " \
                "from {0}.mb_ssc_2016 as ms " \
                "INNER JOIN {1}.ssc AS bdy ON ms.ssc_code = bdy.id "\
                "where mb_code_2016 = ( '%s') " \
                .format('public', 'census_2016_web')
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
                input_ssc = row['ssc_code']
                suburb_center_lat = row['lat']
                suburb_center_lng = row['lng']

        print("view.py::index: input_ssc = ",input_ssc,"lat=",suburb_center_lat,"lng=",suburb_center_lng)

        # get datailed population data.
        result_data = get_population_data(input_ssc, input_suburb);
        
        return render_template('result.html',
                                input_suburb=input_suburb,
                                mb_2016_code=mb_2016_code,
                                input_ssc=input_ssc,
                                suburb_center_lng=suburb_center_lng,
                                suburb_center_lat=suburb_center_lat,
                                result_data=result_data,
                                mapstats="g3") #g3: population                             
                                
    #elif resultform.validate_on_submit() and resultform.Submit2.data:   
         #return redirect(url_for('main.index'))
    # render the serach page
    else:       
        return render_template('mainform.html',
                                form=form)

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

    contributors=[]

    person_001 = {
                'name': 'Bin Liu (Lead Programmer)',
                'link': 'https://github.com/Interest1024'}
    contributors.append(person_001)

    person_002 = {
                'name': 'Engramar Bollas',
                'link': 'https://github.com/engramar'}
    contributors.append(person_002)

    person_003 = {
                'name': 'Jagrati Paranjpe',
                'link': 'https://github.com/jagratiparanjpe'}
    contributors.append(person_003)

    person_004 = {
                'name': 'Albert Molina',
                'link': 'https://github.com/IamTheVine'}
    contributors.append(person_004)

    return render_template('about.html', contributors = contributors);


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
    # print(response_dict)
    # output_array.append(output_dict)

    # print("Got metadata for {0} in {1}".format(boundary_name, datetime.now() - start_time))

    # # Assemble the JSON
    # response_dict["boundaries"] = output_array

    print("Returned metadata in {0}".format(datetime.now() - full_start_time))

    return Response(json.dumps(response_dict), mimetype='application/json')


@main.route("/get-data")
def get_data():
    """Get census data of every suburb in the scope of the map.
    """

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
    input_ssc = request.args.get('input_ssc')
    #print("==>main/views.py::get_data: enter input_ssc="+input_ssc)

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

        #sql for entire Australia
        # sql_template = "SELECT bdy.id, bdy.name, bdy.population, tab.%s / bdy.area AS density, " \
        #       "CASE WHEN bdy.population > 0 THEN tab.%s / bdy.population * 100.0 ELSE 0 END AS percent, " \
        #       "tab.%s, geojson_%s AS geometry " \
        #       "FROM {0}.%s AS bdy " \
        #       "INNER JOIN {1}.%s_%s AS tab ON bdy.id = tab.{2} " \
        #       "WHERE bdy.geom && ST_MakeEnvelope(%s, %s, %s, %s, 4283) " \
        #       .format('census_2016_web', 'census_2016_data', "region_id")

        # sql for NSW
        sql_template = "SELECT bdy.id, bdy.name, bdy.population, tab.%s / bdy.area AS density, " \
              "CASE WHEN bdy.population > 0 THEN tab.%s / bdy.population * 100.0 ELSE 0 END AS percent, " \
              "tab.%s, geojson_%s AS geometry " \
              "FROM {0}.%s AS bdy " \
              "INNER JOIN {1}.%s_%s AS tab ON bdy.id = tab.{2} " \
              "INNER JOIN {3}.%s_2016_aust AS def on bdy.id = def.ssc_code16 " \
              "WHERE bdy.geom && ST_MakeEnvelope(%s, %s, %s, %s, 4283) " \
              "AND def.ste_code16 = '1' " \
              .format('census_2016_web', 'census_2016_data', "region_id", "census_2016_bdys")
        # "WHERE bdy.id = '%s'" \
        #print("==>main/views.py::get_data: enter line 389")

        sql = pg_cur.mogrify(sql_template, (AsIs(stat_id), AsIs(stat_id), AsIs(stat_id), AsIs(display_zoom),
                                            AsIs(boundary_name), AsIs(boundary_name), 
                                            AsIs(table_id), AsIs(boundary_name), 
                                            AsIs(map_left),AsIs(map_bottom), AsIs(map_right), AsIs(map_top)))
                                            #AsIs(input_ssc)))

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
                properties_dict["id"]=row[col]
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



