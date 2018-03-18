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
import random

#bokeh:
from bokeh.models import (HoverTool, FactorRange, Plot, LinearAxis, Grid,
                          Range1d)
from bokeh.models.glyphs import VBar
from bokeh.plotting import figure
from bokeh.charts import Bar
from bokeh.embed import components
from bokeh.models.sources import ColumnDataSource

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

        # get datailed population data.
        result_data = get_population_data(InputSSC, InputSuburb);
        
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
    # render the serach page
    else:       
        return render_template('mainform.html',
                                form=form)


def get_population_data(InputSSC, InputSuburb):
    """get census data about population 
    from census_2016_data.ssc_g01.
    """
    result_data = [];

    # get column's description from census_2016_data.metadata_stats
    with get_db_cursor() as pg_cur:

        search_stats_tuple = tuple(["G"+str(no) for no in range(1,4)]) 
        #hardcode: 4
        #I only need G1 (total males), G2 (total females) and G3 (total persons) 
        #They are all in table: census_2016_data.ccs_g1
        print ("views.py::get_population_data: search_stats_tuple = ",search_stats_tuple);

        sql_template = "SELECT sequential_id AS id, " \
              "lower(table_number) AS \"table\", " \
              "replace(long_id, '_', ' ') AS description, " \
              "column_heading_description AS type, " \
              "'values' as maptype " \
              "FROM {0}.metadata_stats " \
              "WHERE sequential_id IN %s " \
              "ORDER BY sequential_id".format('census_2016_data')

        sql = pg_cur.mogrify(sql_template, (AsIs(search_stats_tuple),)) 

        print("===>views.py::get_population_data: sql:", sql)
    
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
        #no determine the order in result page.
        #feature_dict["no"] = int(re.sub("[A-Za-z]","",feature_dict["id"]))
        feature_dict["no"] = 1;
        if feature_dict["id"] == 'G1':
            feature_dict["no"] = 2;
        elif feature_dict["id"] == 'G2':
            feature_dict["no"] = 3;
        elif feature_dict["id"] == 'G3':
            feature_dict["no"] = 1;            
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
    #print("views:py::get_population_data: response_dict = ",response_dict)


    #get values of census item from g1 to g108
    with get_db_cursor() as pg_cur:

        search_stats_tuple = tuple(["G"+str(no) for no in range(1,10)]) 
        #hardcode: 10
        #the max value can be set up to 109. They are all in table: census_2016_data.ccs_g1
        print ("views.py::get_population_data: search_stats_tuple = ",search_stats_tuple);

        #hardcode
        sql_template2 = "SELECT tab.g1, tab.g2, tab.g3, tab.g4, tab.g5, tab.g6, tab.g7, tab.g8, tab.g9, " \
            "tab.g10, tab.g11, tab.g12, tab.g13, tab.g14, tab.g15, tab.g16, tab.g17, tab.g18, tab.g19, " \
            "tab.g20, tab.g21, tab.g22, tab.g23, tab.g24, tab.g25, tab.g26, tab.g27, tab.g28, tab.g29, " \
            "tab.g30, tab.g31, tab.g32, tab.g33, tab.g34, tab.g35, tab.g36 " \
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
        #print("views.py::get_result_metadata the result of sql2:",value_dict)

        response2_list = []
        for response_item in response_dict:
        # add more data to response_item 1:
            response2_item = {}
            response2_item["no"] = response_item["no"]
            response2_item["id"] = response_item["id"]
            response2_item["description"] = response_item["description"]
            print(response_item["id"].lower());
            # for total persons
            if response_item["id"].lower() == "g3": 
                table1 = []
                table1.append(["suburb","year","value"])
                table1.append([InputSuburb,"2016",int(value_dict["g3"])])
                print("enter",table1);
                response2_item['numoftable'] = 1
                response2_item['table'] = [table1]
                response2_item['numofchart'] = 1
            # for total males    
            elif response_item["id"].lower() == "g2": 
                table1 = []
                table1.append(["suburb","year","value"])
                table1.append([InputSuburb,"2016",int(value_dict["g2"])])
                print("enter",table1);
                response2_item['numoftable'] = 1
                response2_item['table'] = [table1]
                response2_item['numofchart'] = 1
            # for total females    
            elif response_item["id"].lower() == "g1": 
                table1 = []
                table1.append(["suburb","year","value"])
                table1.append([InputSuburb,"2016",int(value_dict["g1"])])
                print("enter",table1);
                response2_item['numoftable'] = 1
                response2_item['table'] = [table1]
                response2_item['numofchart'] = 1

            response2_list.append(response2_item)

    print(response2_list);    
    return response2_list;

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
    # print(response_dict)
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


@main.route("/chart/<int:bars_count>/")
def chart(bars_count):
    """Try to show chart"""
    if bars_count <= 0:
        bars_count = 1

    data = {"days": [], "bugs": [], "costs": []}
    for i in range(1, bars_count + 1):
        data['days'].append(i)
        data['bugs'].append(random.randint(1,100))
        data['costs'].append(random.uniform(1.00, 1000.00))

    hover = create_hover_tool()
    plot = create_bar_chart(data, "Bugs found per day", "days",
                            "bugs", hover)
    script, div = components(plot)

    return render_template("chart.html", bars_count=bars_count,
                           the_div=div, the_script=script)

def create_hover_tool():
    """Generates the HTML for the Bokeh's hover data tool on our graph."""
    hover_html = """
      <div>
        <span class="hover-tooltip">$x</span>
      </div>
      <div>
        <span class="hover-tooltip">@bugs bugs</span>
      </div>
      <div>
        <span class="hover-tooltip">$@costs{0.00}</span>
      </div>
    """
    return HoverTool(tooltips=hover_html)

def create_bar_chart(data, title, x_name, y_name, hover_tool=None,
                     width=1200, height=300):
    """Creates a bar chart plot with the exact styling for the centcom
       dashboard. Pass in data as a dictionary, desired plot title,
       name of x axis, y axis and the hover tool HTML.
    """
    source = ColumnDataSource(data)
    xdr = FactorRange(factors=data[x_name])
    ydr = Range1d(start=0,end=max(data[y_name])*1.5)

    tools = []
    if hover_tool:
        tools = [hover_tool,]

    plot = figure(title=title, x_range=xdr, y_range=ydr, plot_width=width,
                  plot_height=height, h_symmetry=False, v_symmetry=False,
                  min_border=0, toolbar_location="above", tools=tools,
                  responsive=True, outline_line_color="#666666")

    glyph = VBar(x=x_name, top=y_name, bottom=0, width=.8,
                 fill_color="#e12127")
    plot.add_glyph(source, glyph)

    xaxis = LinearAxis()
    yaxis = LinearAxis()

    plot.add_layout(Grid(dimension=0, ticker=xaxis.ticker))
    plot.add_layout(Grid(dimension=1, ticker=yaxis.ticker))
    plot.toolbar.logo = None
    plot.min_border_top = 0
    plot.xgrid.grid_line_color = None
    plot.ygrid.grid_line_color = "#999999"
    plot.yaxis.axis_label = "Bugs found"
    plot.ygrid.grid_line_alpha = 0.1
    plot.xaxis.axis_label = "Days after app deployment"
    plot.xaxis.major_label_orientation = 1
    return plot    